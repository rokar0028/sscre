"""Run a bounded, deterministic SSCRE load test and write JSON evidence."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheStorageStats, InMemoryExactCache
from sscre.config import Settings
from sscre.embedding import (
    EmbeddingConfig,
    EmbeddingProviderError,
    FakeEmbeddingClient,
)
from sscre.llm import LLMResult, MockLLMClient
from sscre.postgres_cache import PostgresExactCacheRepository
from sscre.query import hash_query, normalize_query


@dataclass(frozen=True)
class WorkloadItem:
    query: str
    label: str


class LoadTestEmbeddingClient(FakeEmbeddingClient):
    def embed(self, text: str):  # type: ignore[no-untyped-def]
        if text.startswith("[fail_embedding]"):
            raise EmbeddingProviderError("synthetic embedding failure")
        if text.startswith("[semantic]"):
            return super().embed("[semantic-shared-vector]")
        return super().embed(text)


class LoadTestLLMClient(MockLLMClient):
    def generate(self, query: str) -> LLMResult:
        if query.startswith("[fail_generation]"):
            raise RuntimeError("synthetic generation failure")
        if query.startswith("[large]"):
            answer = "x" * 70_000
            return LLMResult(
                text=answer,
                input_tokens=len(query.split()),
                output_tokens=len(answer.split()),
                latency_ms=0,
            )
        return super().generate(query)


class DisabledCache:
    """Repository-shaped no-cache baseline for controlled comparisons."""

    def get_by_query_hash(self, query_hash: str) -> None:
        return None

    def search_by_embedding(
        self,
        embedding: tuple[float, ...],
        top_k: int,
        embedding_model: str | None = None,
    ) -> tuple[()]:
        return ()

    def insert_and_evict(
        self,
        entry: object,
        max_entries: int,
        max_bytes: int,
    ) -> None:
        return None

    def record_hit(self, query_hash: str) -> None:
        return None

    def storage_stats(self) -> CacheStorageStats:
        return CacheStorageStats(entries=0, canonical_answers=0, total_bytes=0)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("load-test configuration must be a JSON object")
    return value


def _items(config: dict[str, Any]) -> tuple[WorkloadItem, ...]:
    raw_items = config.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("load-test configuration requires non-empty items")
    result = []
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("each workload item must be an object")
        query = item.get("query")
        label = item.get("label", "unlabeled")
        if not isinstance(query, str) or not query:
            raise ValueError("workload item query must be non-empty text")
        if not isinstance(label, str) or not label:
            raise ValueError("workload item label must be non-empty text")
        result.append(WorkloadItem(query=query, label=label))
    return tuple(result)


DEFAULT_MODES = ("no_cache", "exact_cache", "embedding_only", "compatibility")
ERROR_RATE_STOP = 0.10
TIMEOUT_RATE_STOP = 0.05
P99_TO_P50_STOP = 5.0


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def _postgresql_version(database_url: str) -> str | None:
    try:
        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SHOW server_version")
                row = cursor.fetchone()
    except psycopg.Error:
        return None
    return str(row[0]) if row is not None else None


def _measurement_environment(
    config: dict[str, Any],
    *,
    database_url: str | None,
) -> dict[str, Any]:
    repository = str(config.get("repository", "memory"))
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "git_commit": _git_commit(),
        "process_count": int(config.get("process_count", 1)),
        "worker_count": int(config.get("worker_count", 1)),
        "database_mode": repository,
        "postgresql_version": (
            _postgresql_version(database_url) if database_url else None
        ),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "python_implementation": sys.implementation.name,
    }


def _isolated_items(
    items: tuple[WorkloadItem, ...],
    token: str | None,
) -> tuple[WorkloadItem, ...]:
    if not token:
        return items
    return tuple(
        WorkloadItem(query=f"{item.query} ws8:{token}", label=item.label)
        for item in items
    )


def _cleanup_postgres_hashes(database_url: str, query_hashes: list[str]) -> None:
    if not query_hashes:
        return
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM cache_entries WHERE query_hash = ANY(%s)",
                (query_hashes,),
            )
            cursor.execute(
                """
                DELETE FROM canonical_answers AS ca
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM cache_entries
                    WHERE canonical_answer_hash = ca.answer_hash
                )
                """
            )


def _stop_reason(pass_result: dict[str, Any]) -> str | None:
    errors = pass_result["errors"]
    if errors["rate"] > ERROR_RATE_STOP:
        return "error_rate_above_10_percent"
    timeout_rate = errors.get("timeout_rate", 0.0)
    if timeout_rate > TIMEOUT_RATE_STOP:
        return "timeout_rate_above_5_percent"
    p50 = float(pass_result["latency_ms"]["p50"])
    p99 = float(pass_result["latency_ms"]["p99"])
    if p50 > 0 and p99 > P99_TO_P50_STOP * p50:
        return "p99_above_5x_p50"
    return None


def _create_client(
    config: dict[str, Any],
    mode: str,
    *,
    database_url: str | None = None,
) -> tuple[TestClient, Any]:
    repository = str(config.get("repository", "memory"))
    if repository == "postgres":
        if not database_url:
            raise ValueError(
                "SSCRE_DATABASE_URL is required for repository=postgres"
            )
        cache: Any = PostgresExactCacheRepository(database_url)
    elif mode == "no_cache":
        cache = DisabledCache()
    else:
        cache = InMemoryExactCache(max_top_k=100)
    semantic_enabled = mode in {"embedding_only", "compatibility"}
    settings = Settings(
        log_level="ERROR",
        database_url=database_url if repository == "postgres" else None,
        semantic_enabled=semantic_enabled,
        semantic_strategy="C" if mode == "compatibility" else "B",
        semantic_similarity_threshold=float(
            config.get("similarity_threshold", 0.95)
        ),
        max_cache_entries=int(config.get("max_cache_entries", 8)),
        max_cache_bytes=int(config.get("max_cache_bytes", 10_000)),
    )
    embedding = LoadTestEmbeddingClient(
        config=EmbeddingConfig(model_name="load-test-embedding", dimension=8)
    )
    return (
        TestClient(
            create_app(
                llm_client=LoadTestLLMClient(),
                repository=cache,
                settings=settings,
                embedding_client=embedding,
            )
        ),
        cache,
    )


def _request(client: TestClient, item: WorkloadItem) -> dict[str, Any]:
    started = perf_counter()
    response = client.post("/v1/query", json={"query": item.query})
    latency_ms = (perf_counter() - started) * 1000
    body: dict[str, Any]
    try:
        raw_body = response.json()
        body = raw_body if isinstance(raw_body, dict) else {}
    except ValueError:
        body = {}
    metrics = body.get("metrics")
    api_latency_ms = (
        metrics.get("total_latency_ms")
        if isinstance(metrics, dict)
        else None
    )
    llm_latency_ms = (
        metrics.get("llm_latency_ms")
        if isinstance(metrics, dict)
        else None
    )
    return {
        "label": item.label,
        "status_code": response.status_code,
        "latency_ms": round(latency_ms, 3),
        "source": body.get("source", "error"),
        "decision": body.get("decision"),
        "reason": body.get("reason", body.get("detail")),
        "api_latency_ms": api_latency_ms,
        "llm_latency_ms": llm_latency_ms,
        "wrapper_overhead_ms": (
            max(0, api_latency_ms - llm_latency_ms)
            if isinstance(api_latency_ms, int)
            and isinstance(llm_latency_ms, int)
            else None
        ),
    }


def _run_pass(
    config: dict[str, Any],
    *,
    warm: bool,
    mode: str,
    database_url: str | None = None,
    isolate_token: str | None = None,
) -> dict[str, Any]:
    client, cache = _create_client(config, mode, database_url=database_url)
    items = _isolated_items(_items(config), isolate_token)
    warmup_requests = int(config.get("warmup_requests", 0)) if warm else 0
    request_count = int(config.get("request_count", len(items)))
    concurrency = int(config.get("concurrency", 1))
    if warmup_requests < 0 or request_count <= 0 or concurrency <= 0:
        raise ValueError("warmup_requests, request_count, and concurrency must be positive")

    warmup_errors = 0
    for index in range(warmup_requests):
        warmup = _request(client, items[index % len(items)])
        if int(warmup["status_code"]) >= 400:
            warmup_errors += 1
    storage_before = cache.storage_stats()

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(
            executor.map(
                lambda index: _request(client, items[index % len(items)]),
                range(request_count),
            )
        )
    elapsed_seconds = perf_counter() - started

    latencies = [float(result["latency_ms"]) for result in results]
    errors = [result for result in results if result["status_code"] >= 400]
    timeouts = sum(
        1
        for result in errors
        if "timed out" in str(result["reason"])
    )
    sources: dict[str, int] = {}
    reasons: dict[str, int] = {}
    labels: dict[str, int] = {}
    for result in results:
        source = str(result["source"])
        sources[source] = sources.get(source, 0) + 1
        reason = result["reason"]
        if reason is not None:
            reason_key = str(reason)
            reasons[reason_key] = reasons.get(reason_key, 0) + 1
        label = str(result["label"])
        labels[label] = labels.get(label, 0) + 1

    storage_after = cache.storage_stats()
    cache_hits = sources.get("cache", 0)
    generated = sources.get("generated", 0)

    def _stat(value: object) -> int:
        return int(value or 0)
    return {
        "mode": "warm" if warm else "cold",
        "cache_mode": mode,
        "warmup_requests": warmup_requests,
        "warmup_error_rate": (
            round(warmup_errors / warmup_requests, 6) if warmup_requests else 0.0
        ),
        "request_count": request_count,
        "concurrency": concurrency,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "throughput_requests_per_second": round(
            request_count / elapsed_seconds if elapsed_seconds else 0.0,
            3,
        ),
        "latency_ms": {
            "p50": round(_percentile(latencies, 0.50), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
            "p99": round(_percentile(latencies, 0.99), 3),
            "max": round(max(latencies) if latencies else 0.0, 3),
        },
        "errors": {
            "count": len(errors),
            "rate": round(len(errors) / request_count, 6),
            "timeouts": timeouts,
            "timeout_rate": round(timeouts / request_count, 6),
        },
        "cache_hits": cache_hits,
        "cache_misses": max(0, request_count - cache_hits),
        "generated_requests": generated,
        "sources": sources,
        "reasons": reasons,
        "workload_labels": labels,
        "storage": {
            "entries": _stat(storage_after.entries),
            "bytes": _stat(storage_after.total_bytes),
            "canonical_answers": _stat(storage_after.canonical_answers),
            "evictions": _stat(storage_after.evictions),
            "expirations": _stat(storage_after.expirations),
            "entries_delta": _stat(storage_after.entries) - _stat(storage_before.entries),
            "bytes_delta": _stat(storage_after.total_bytes)
            - _stat(storage_before.total_bytes),
            "evictions_delta": _stat(storage_after.evictions)
            - _stat(storage_before.evictions),
        },
        "synthetic_provider_data": True,
        "results": results,
    }


UNAVAILABLE_PG_LOAD_SPANS = (
    "repository_database_span",
    "embedding_span",
    "real_provider_latency",
)


def classify_first_bottleneck(report: dict[str, Any]) -> dict[str, Any]:
    """Classify the WS8 load result without selecting an optimization.

    Synthetic LLM latency is typically 0 ms, so wrapper overhead must not be
    treated as a production bottleneck. Missing spans stay unavailable.
    """
    passes = [
        item
        for items in report.get("comparison", {}).values()
        for item in items
    ]
    measured = (
        _bottleneck_analysis(passes)["measured_components"]
        if passes
        else {
            "average_wrapper_overhead_ms": 0.0,
            "average_llm_latency_ms": 0.0,
        }
    )
    end_to_end = [
        float(result["latency_ms"])
        for item in passes
        for result in item.get("results", [])
    ]
    stopped = report.get("stopped_reason")
    verdict = stopped or "not_reached"
    if verdict == "not_reached":
        rationale = (
            "Declared ws8-pg-load-v1 workload completed without a stop "
            "condition. Synthetic provider latency is 0 ms, so wrapper "
            "overhead is not an actionable bottleneck. Repository, embedding, "
            "and live-provider spans were not instrumented."
        )
    else:
        rationale = (
            f"Stop condition {verdict} fired on the declared workload. "
            "No optimization is selected from this bounded local run."
        )
    return {
        "protocol_id": report.get("protocol_id") or "ws8-pg-load-v1",
        "first_measured_bottleneck": verdict,
        "result_class": "observation",
        "optimization_decision": "none",
        "measured_components": {
            **measured,
            "end_to_end_average_ms": (
                round(sum(end_to_end) / len(end_to_end), 3) if end_to_end else 0.0
            ),
            "pass_latency_ms": [
                {
                    "mode": item["mode"],
                    "p50": item["latency_ms"]["p50"],
                    "p95": item["latency_ms"]["p95"],
                    "p99": item["latency_ms"]["p99"],
                    "throughput_requests_per_second": item[
                        "throughput_requests_per_second"
                    ],
                }
                for item in passes
            ],
        },
        "unavailable_components": list(UNAVAILABLE_PG_LOAD_SPANS),
        "environment": {
            "concurrency": passes[0]["concurrency"] if passes else 0,
            "provider_data": "synthetic",
            "storage": (
                "postgresql"
                if report.get("repository") == "postgres"
                else "in-memory"
            ),
            "postgresql_version": (report.get("environment") or {}).get(
                "postgresql_version"
            ),
        },
        "stop_conditions": {
            "error_rate_limit": ERROR_RATE_STOP,
            "timeout_rate_limit": TIMEOUT_RATE_STOP,
            "p99_to_p50_limit": P99_TO_P50_STOP,
            "stopped_reason": stopped,
        },
        "rationale": rationale,
        "optimization": (
            "No production optimization selected; wrapper versus synthetic "
            "LLM latency is not an actionable bottleneck."
        ),
    }


def _bottleneck_analysis(passes: list[dict[str, Any]]) -> dict[str, Any]:
    wrapper_values = [
        float(result["wrapper_overhead_ms"])
        for item in passes
        for result in item["results"]
        if result["wrapper_overhead_ms"] is not None
    ]
    llm_values = [
        float(result["llm_latency_ms"])
        for item in passes
        for result in item["results"]
        if result["llm_latency_ms"] is not None
    ]
    average_wrapper = (
        sum(wrapper_values) / len(wrapper_values) if wrapper_values else 0.0
    )
    average_llm = sum(llm_values) / len(llm_values) if llm_values else 0.0
    return {
        "measured_components": {
            "average_wrapper_overhead_ms": round(average_wrapper, 3),
            "average_llm_latency_ms": round(average_llm, 3),
        },
        "first_measured_bottleneck": (
            "wrapper_overhead"
            if average_wrapper >= average_llm
            else "generation"
        ),
        "environment": {
            "concurrency": passes[0]["concurrency"] if passes else 0,
            "provider_data": "synthetic",
            "storage": "in-memory",
        },
        "optimization": (
            "No production optimization selected; this deterministic in-process "
            "run does not justify changing safety-critical request behavior."
        ),
    }


def run(config: dict[str, Any]) -> dict[str, Any]:
    repository = str(config.get("repository", "memory"))
    database_url = os.getenv("SSCRE_DATABASE_URL") if repository == "postgres" else None
    if repository == "postgres" and not database_url:
        raise ValueError("SSCRE_DATABASE_URL is required for repository=postgres")
    raw_modes = config.get("modes")
    modes = tuple(raw_modes) if raw_modes else DEFAULT_MODES
    if not modes or any(not isinstance(mode, str) or not mode for mode in modes):
        raise ValueError("modes must be a non-empty list of mode names")
    cold_passes = int(config.get("cold_passes", 1))
    warm_passes = int(config.get("warm_passes", 1))
    if cold_passes <= 0 or warm_passes < 0:
        raise ValueError("cold_passes must be positive and warm_passes must be >= 0")
    isolate = bool(config.get("isolate_queries", repository == "postgres"))
    comparison: dict[str, list[dict[str, Any]]] = {}
    all_passes: list[dict[str, Any]] = []
    stopped_reason: str | None = None
    for mode in modes:
        comparison[mode] = []
        for repeat in range(cold_passes):
            token = str(uuid4()) if isolate else None
            hashes = [
                hash_query(normalize_query(item.query))
                for item in _isolated_items(_items(config), token)
            ]
            try:
                cold = _run_pass(
                    config,
                    warm=False,
                    mode=mode,
                    database_url=database_url,
                    isolate_token=token,
                )
                comparison[mode].append(cold)
                all_passes.append(cold)
                stopped_reason = _stop_reason(cold)
                if stopped_reason is None and repeat < warm_passes:
                    warm = _run_pass(
                        config,
                        warm=True,
                        mode=mode,
                        database_url=database_url,
                        isolate_token=token,
                    )
                    comparison[mode].append(warm)
                    all_passes.append(warm)
                    stopped_reason = _stop_reason(warm)
            finally:
                if database_url is not None:
                    _cleanup_postgres_hashes(database_url, hashes)
            if stopped_reason is not None:
                break
        if stopped_reason is not None:
            break
    if repository == "postgres":
        bottleneck = classify_first_bottleneck(
            {
                "protocol_id": config.get("protocol_id"),
                "repository": repository,
                "stopped_reason": stopped_reason,
                "comparison": comparison,
                "environment": _measurement_environment(
                    config, database_url=database_url
                ),
            }
        )
    else:
        bottleneck = _bottleneck_analysis(all_passes)
    return {
        "name": config.get("name", "sscre-load-test"),
        "protocol_id": config.get("protocol_id"),
        "dataset_version": config.get("dataset_version", "unversioned"),
        "repository": repository,
        "strategies": list(modes),
        "cache_policy": {
            "max_entries": int(config.get("max_cache_entries", 8)),
            "max_bytes": int(config.get("max_cache_bytes", 10_000)),
        },
        "process_count": int(config.get("process_count", 1)),
        "worker_count": int(config.get("worker_count", 1)),
        "environment": _measurement_environment(config, database_url=database_url),
        "stopped_reason": stopped_reason,
        "limitation": config.get(
            "limitation",
            "Bounded local result. Not a production capacity or SLA guarantee.",
        ),
        "comparison": comparison,
        "bottleneck_analysis": bottleneck,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = run(_load_config(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote load-test report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
