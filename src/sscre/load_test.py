"""Run a bounded, deterministic SSCRE load test and write JSON evidence."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter
from typing import Any

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


def _create_client(
    config: dict[str, Any],
    mode: str,
) -> tuple[TestClient, InMemoryExactCache | DisabledCache]:
    cache: InMemoryExactCache | DisabledCache
    cache = (
        DisabledCache()
        if mode == "no_cache"
        else InMemoryExactCache(max_top_k=100)
    )
    semantic_enabled = mode in {"embedding_only", "compatibility"}
    settings = Settings(
        log_level="ERROR",
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
) -> dict[str, Any]:
    client, cache = _create_client(config, mode)
    items = _items(config)
    warmup_requests = int(config.get("warmup_requests", 0)) if warm else 0
    request_count = int(config.get("request_count", len(items)))
    concurrency = int(config.get("concurrency", 1))
    if warmup_requests < 0 or request_count <= 0 or concurrency <= 0:
        raise ValueError("warmup_requests, request_count, and concurrency must be positive")

    for index in range(warmup_requests):
        _request(client, items[index % len(items)])

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

    return {
        "mode": "warm" if warm else "cold",
        "cache_mode": mode,
        "warmup_requests": warmup_requests,
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
            "timeouts": sum(
                1
                for result in errors
                if "timed out" in str(result["reason"])
            ),
        },
        "sources": sources,
        "reasons": reasons,
        "workload_labels": labels,
        "storage": {
            "entries": cache.storage_stats().entries,
            "bytes": cache.storage_stats().total_bytes,
        },
        "synthetic_provider_data": True,
        "results": results,
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
    modes = ("no_cache", "exact_cache", "embedding_only", "compatibility")
    comparison: dict[str, list[dict[str, Any]]] = {}
    for mode in modes:
        comparison[mode] = [
            _run_pass(config, warm=False, mode=mode),
            _run_pass(config, warm=True, mode=mode),
        ]
    all_passes = [item for mode in modes for item in comparison[mode]]
    return {
        "name": config.get("name", "sscre-load-test"),
        "dataset_version": config.get("dataset_version", "unversioned"),
        "strategies": list(modes),
        "cache_policy": {
            "max_entries": int(config.get("max_cache_entries", 8)),
            "max_bytes": int(config.get("max_cache_bytes", 10_000)),
        },
        "comparison": comparison,
        "bottleneck_analysis": _bottleneck_analysis(all_passes),
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
