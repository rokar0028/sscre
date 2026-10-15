"""Run a bounded, deterministic SSCRE load test and write JSON evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import platform
import random
import subprocess
import sys
from pathlib import Path
from threading import Lock, local
from time import perf_counter
from typing import Any
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.api_auth import DEFAULT_NAMESPACE, TRUSTED_LOCAL_TENANT
from sscre.benchmark import load_benchmark_jsonl
from sscre.benchmark_splits import file_sha256
from sscre.cache import CacheStorageStats, InMemoryExactCache
from sscre.config import Settings
from sscre.embedding import (
    EmbeddingConfig,
    EmbeddingProviderError,
    FakeEmbeddingClient,
)
from sscre.llm import LLMResult, MockLLMClient
from sscre.postgres_cache import (
    ScopedPostgresExactCacheRepository,
    delete_entries_by_query_hashes,
)
from sscre.query import CacheScope, hash_query, normalize_query, scoped_cache_key


@dataclass(frozen=True)
class WorkloadItem:
    query: str
    label: str


def _storage_query_hash(query: str) -> str:
    return scoped_cache_key(
        CacheScope(TRUSTED_LOCAL_TENANT, DEFAULT_NAMESPACE),
        normalize_query(query),
    )


class LoadTestEmbeddingClient(FakeEmbeddingClient):
    def __init__(self, *args: Any, timing_hub: "TimingHub | None" = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._timing_hub = timing_hub

    def embed(self, text: str):  # type: ignore[no-untyped-def]
        hub = self._timing_hub

        def publish(elapsed_ms: float) -> None:
            if hub is not None:
                hub.add_query(text, "embed", elapsed_ms)

        with _component_timer(publish if hub is not None else None):
            if text.startswith("[fail_embedding]"):
                raise EmbeddingProviderError("synthetic embedding failure")
            if text.startswith("[semantic]"):
                result = super().embed("[semantic-shared-vector]")
            else:
                result = super().embed(text)
        if hub is not None:
            hub.note_vector(text, result.vector)
        return result


class LoadTestLLMClient(MockLLMClient):
    def __init__(self, timing_hub: "TimingHub | None" = None) -> None:
        super().__init__()
        self._timing_hub = timing_hub

    def generate(self, query: str) -> LLMResult:
        hub = self._timing_hub

        def publish(elapsed_ms: float) -> None:
            if hub is not None:
                hub.add_query(query, "generation", elapsed_ms)

        with _component_timer(publish if hub is not None else None):
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
        *,
        tenant_id: str = "",
        namespace_id: str = "",
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


_LADDER_COMPONENTS = (
    "embed",
    "vector_search",
    "repository",
    "generation",
    "wrapper_other",
)
_LADDER_UNAVAILABLE = ("compatibility_check",)
_TIMER_LOCAL = local()


@contextmanager
def _component_timer(publish: Callable[[float], None] | None):
    """Record elapsed milliseconds on this thread, then hand them to `publish`.

    Dependency work runs on the app's thread pool, not the request thread.
    The thread-local stack keeps overlapping calls on one thread from sharing
    a single global number. `publish` assigns the duration to the request.
    """
    if publish is None:
        yield
        return
    started = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (perf_counter() - started) * 1000
        _TIMER_LOCAL.last_ms = elapsed_ms
        publish(elapsed_ms)


class _RequestTimings:
    def __init__(self) -> None:
        self.ms = {name: 0.0 for name in _LADDER_COMPONENTS if name != "wrapper_other"}


class TimingHub:
    """Attribute component time to the oldest in-flight request for a key.

    Identical queries that overlap can share a key. Each finished call goes
    to the oldest request still waiting on that key.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_query: dict[str, list[_RequestTimings]] = {}
        self._by_hash: dict[str, list[_RequestTimings]] = {}
        self._by_vector: dict[tuple[float, ...], list[_RequestTimings]] = {}

    def start(self, query: str) -> _RequestTimings:
        normalized = normalize_query(query)
        bucket = _RequestTimings()
        with self._lock:
            self._by_query.setdefault(normalized, []).append(bucket)
            self._by_hash.setdefault(hash_query(normalized), []).append(bucket)
        return bucket

    def finish(self, query: str, bucket: _RequestTimings) -> None:
        normalized = normalize_query(query)
        with self._lock:
            self._drop(self._by_query, normalized, bucket)
            self._drop(self._by_hash, hash_query(normalized), bucket)
            for vector, buckets in list(self._by_vector.items()):
                self._drop_bucket(buckets, bucket)
                if not buckets:
                    del self._by_vector[vector]

    def add_query(self, query: str, component: str, elapsed_ms: float) -> None:
        with self._lock:
            self._add(self._by_query.get(normalize_query(query), []), component, elapsed_ms)

    def add_hash(self, query_hash: str, component: str, elapsed_ms: float) -> None:
        with self._lock:
            self._add(self._by_hash.get(query_hash, []), component, elapsed_ms)

    def add_vector(
        self,
        vector: tuple[float, ...],
        component: str,
        elapsed_ms: float,
    ) -> None:
        with self._lock:
            self._add(self._by_vector.get(vector, []), component, elapsed_ms)

    def note_vector(self, query: str, vector: tuple[float, ...]) -> None:
        with self._lock:
            current = list(self._by_query.get(normalize_query(query), []))
            aliases = self._by_vector.setdefault(vector, [])
            for bucket in current:
                if bucket not in aliases:
                    aliases.append(bucket)

    def _add(
        self,
        buckets: list[_RequestTimings],
        component: str,
        elapsed_ms: float,
    ) -> None:
        if buckets and component in buckets[0].ms:
            buckets[0].ms[component] += elapsed_ms

    def _drop(
        self,
        mapping: dict[Any, list[_RequestTimings]],
        key: Any,
        bucket: _RequestTimings,
    ) -> None:
        buckets = mapping.get(key)
        if not buckets:
            return
        self._drop_bucket(buckets, bucket)
        if not buckets:
            del mapping[key]

    @staticmethod
    def _drop_bucket(buckets: list[_RequestTimings], bucket: _RequestTimings) -> None:
        for index, item in enumerate(buckets):
            if item is bucket:
                del buckets[index]
                return


class _TimedRepository:
    def __init__(self, inner: Any, hub: TimingHub) -> None:
        self._inner = inner
        self._hub = hub

    def get_by_query_hash(self, query_hash: str) -> Any:
        with _component_timer(lambda elapsed: self._hub.add_hash(query_hash, "repository", elapsed)):
            return self._inner.get_by_query_hash(query_hash)

    def search_by_embedding(
        self,
        embedding: tuple[float, ...],
        top_k: int,
        embedding_model: str | None = None,
        *,
        tenant_id: str,
        namespace_id: str,
    ) -> Any:
        with _component_timer(
            lambda elapsed: self._hub.add_vector(embedding, "vector_search", elapsed)
        ):
            return self._inner.search_by_embedding(
                embedding,
                top_k,
                embedding_model,
                tenant_id=tenant_id,
                namespace_id=namespace_id,
            )

    def insert_and_evict(self, entry: Any, max_entries: int, max_bytes: int) -> Any:
        # Forward as a plain call. The scoped PostgreSQL repository adds
        # only_query_hashes itself; the in-memory repository has no SQL delete.
        insert_and_evict = self._inner.insert_and_evict
        with _component_timer(
            lambda elapsed: self._hub.add_hash(entry.query_hash, "repository", elapsed)
        ):
            return insert_and_evict(entry, max_entries, max_bytes)

    def record_hit(self, query_hash: str) -> Any:
        with _component_timer(lambda elapsed: self._hub.add_hash(query_hash, "repository", elapsed)):
            return self._inner.record_hit(query_hash)

    def insert(self, entry: Any) -> Any:
        with _component_timer(
            lambda elapsed: self._hub.add_hash(entry.query_hash, "repository", elapsed)
        ):
            return self._inner.insert(entry)

    def storage_stats(self) -> Any:
        return self._inner.storage_stats()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


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
# p99 on fewer samples is the max; do not treat that as a workload stop.
P99_STOP_MIN_REQUESTS = 16


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


def _git_worktree_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())


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
    delete_entries_by_query_hashes(database_url, query_hashes)


def _stop_reason(pass_result: dict[str, Any]) -> str | None:
    errors = pass_result["errors"]
    if errors["rate"] > ERROR_RATE_STOP:
        return "error_rate_above_10_percent"
    timeout_rate = errors.get("timeout_rate", 0.0)
    if timeout_rate > TIMEOUT_RATE_STOP:
        return "timeout_rate_above_5_percent"
    request_count = int(pass_result.get("request_count") or 0)
    p50 = float(pass_result["latency_ms"]["p50"])
    p99 = float(pass_result["latency_ms"]["p99"])
    if (
        request_count >= P99_STOP_MIN_REQUESTS
        and p50 > 0
        and p99 > P99_TO_P50_STOP * p50
    ):
        return "p99_above_5x_p50"
    return None


def _create_client(
    config: dict[str, Any],
    mode: str,
    *,
    database_url: str | None = None,
    scope_hashes: list[str] | None = None,
    timing_hub: TimingHub | None = None,
) -> tuple[TestClient, Any]:
    repository = str(config.get("repository", "memory"))
    if repository == "postgres":
        if not database_url:
            raise ValueError(
                "SSCRE_DATABASE_URL is required for repository=postgres"
            )
        cache: Any = ScopedPostgresExactCacheRepository(
            database_url,
            scope_hashes or (),
        )
    elif mode == "no_cache":
        cache = DisabledCache()
    else:
        cache = InMemoryExactCache(max_top_k=100)
    if timing_hub is not None:
        cache = _TimedRepository(cache, timing_hub)
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
        config=EmbeddingConfig(model_name="load-test-embedding", dimension=8),
        timing_hub=timing_hub,
    )
    return (
        TestClient(
            create_app(
                llm_client=LoadTestLLMClient(timing_hub=timing_hub),
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
    items = _isolated_items(_items(config), isolate_token)
    scope_hashes = [_storage_query_hash(item.query) for item in items]
    client, cache = _create_client(
        config,
        mode,
        database_url=database_url,
        scope_hashes=scope_hashes,
    )
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
                _storage_query_hash(item.query)
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    return _repo_root() / candidate


def load_ladder_pool(path: str | Path) -> tuple[str, ...]:
    """Unique normalized development queries, file order, query_a then query_b."""
    pool: list[str] = []
    seen: set[str] = set()
    for record in load_benchmark_jsonl(_resolve_repo_path(path)):
        for raw in (record.query_a, record.query_b):
            query = normalize_query(raw)
            if query in seen:
                continue
            seen.add(query)
            pool.append(query)
    if not pool:
        raise ValueError("load ladder query pool is empty")
    return tuple(pool)


def build_ladder_sequence(
    pool: Sequence[str],
    *,
    length: int,
    seed: int,
    repeat_ratio: float,
) -> tuple[tuple[str, str], ...]:
    """Return (query, label) pairs. Each call starts again from `seed`."""
    if length <= 0:
        raise ValueError("sequence length must be positive")
    if not pool:
        raise ValueError("query pool is empty")
    if not 0 <= repeat_ratio <= 1:
        raise ValueError("repeat_ratio must be between 0 and 1")
    rng = random.Random(seed)
    sequence: list[tuple[str, str]] = []
    pool_index = 0
    for index in range(length):
        if index == 0 or rng.random() >= repeat_ratio:
            query = pool[pool_index % len(pool)]
            pool_index += 1
            label = "development_unique"
        else:
            query = sequence[rng.randrange(index)][0]
            label = "development_repeat"
        sequence.append((query, label))
    return tuple(sequence)


def realized_repeat_ratio(
    sequence: Sequence[tuple[str, str]],
    warmup_requests: int,
) -> float:
    measured = sequence[warmup_requests:]
    if not measured:
        raise ValueError("measured window is empty")
    repeats = sum(1 for _, label in measured if label == "development_repeat")
    return repeats / len(measured)


def ladder_non_fixture_error_rate(
    rows: Sequence[Mapping[str, Any]],
    fixture_labels: Sequence[str],
) -> float | None:
    """Error rate after dropping intentional fixture labels from both sides."""
    fixtures = set(fixture_labels)
    eligible = [row for row in rows if str(row.get("label")) not in fixtures]
    if not eligible:
        return None
    errors = sum(1 for row in eligible if int(row["status_code"]) >= 400)
    return errors / len(eligible)


def select_component_bottleneck(component_p95_ms: Mapping[str, float]) -> str:
    """Largest p95 share. Ties keep the earlier component. Zero sum is unattributed.

    `compatibility_check` and any other unmeasured name are ignored.
    """
    values = [float(component_p95_ms.get(name, 0.0)) for name in _LADDER_COMPONENTS]
    total = sum(values)
    if total == 0:
        return "unattributed"
    best_index = 0
    best_share = values[0] / total
    for index, value in enumerate(values):
        share = value / total
        if share > best_share:
            best_index = index
            best_share = share
    return _LADDER_COMPONENTS[best_index]


def _ladder_http(client: TestClient, item: WorkloadItem, hub: TimingHub) -> dict[str, Any]:
    bucket = hub.start(item.query)
    started = perf_counter()
    try:
        response = client.post("/v1/query", json={"query": item.query})
        latency_ms = (perf_counter() - started) * 1000
        try:
            raw_body = response.json()
            body = raw_body if isinstance(raw_body, dict) else {}
        except ValueError:
            body = {}
        status_code = response.status_code
        reason = body.get("reason", body.get("detail"))
    finally:
        hub.finish(item.query, bucket)
    spent = sum(bucket.ms.values())
    components = dict(bucket.ms)
    components["wrapper_other"] = max(0.0, latency_ms - spent)
    return {
        "label": item.label,
        "status_code": status_code,
        "reason": reason,
        "latency_ms": latency_ms,
        "components": components,
    }


def _measure_ladder_step(
    config: dict[str, Any],
    step: Mapping[str, Any],
    pool: Sequence[str],
) -> dict[str, Any]:
    warmup = int(step["warmup_requests"])
    request_count = int(step["request_count"])
    concurrency = int(step["concurrency"])
    if warmup < 0 or request_count <= 0 or concurrency <= 0:
        raise ValueError(
            "warmup_requests must be >= 0 and request_count and concurrency must be positive"
        )
    sequence = build_ladder_sequence(
        pool,
        length=warmup + request_count,
        seed=int(config["seed"]),
        repeat_ratio=float(config["repeat_ratio"]),
    )
    repository = str(config.get("repository", "memory"))
    token = str(uuid4()) if repository == "postgres" else None
    items = tuple(
        WorkloadItem(
            query=f"{query} ws8:{token}" if token else query,
            label=label,
        )
        for query, label in sequence
    )
    database_url = os.getenv("SSCRE_DATABASE_URL") if repository == "postgres" else None
    hub = TimingHub()
    client, cache = _create_client(
        config,
        "compatibility",
        database_url=database_url,
        scope_hashes=[_storage_query_hash(item.query) for item in items],
        timing_hub=hub,
    )
    for item in items[:warmup]:
        _ladder_http(client, item, hub)
    started = perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        rows = list(
            executor.map(lambda item: _ladder_http(client, item, hub), items[warmup:])
        )
    elapsed = perf_counter() - started
    stats = cache.storage_stats()
    return {
        "rows": rows,
        "entries": int(stats.entries),
        "total_bytes": int(stats.total_bytes),
        "eviction_count": int(stats.evictions),
        "elapsed_seconds": elapsed,
    }


def _score_ladder_step(
    config: Mapping[str, Any],
    step: Mapping[str, Any],
    raw: Mapping[str, Any],
    run_index: int,
    repository: str,
) -> dict[str, Any]:
    rows = list(raw["rows"])
    if not rows:
        raise ValueError("ladder step measured window is empty")
    latencies = [float(row["latency_ms"]) for row in rows]
    fixture_labels = config.get(
        "fixture_labels",
        ["embedding_failure", "generation_failure"],
    )
    error_rate = ladder_non_fixture_error_rate(rows, fixture_labels)
    timeouts = sum(
        1 for row in rows if "timed out" in str(row.get("reason") or "")
    )
    timeout_rate = timeouts / len(rows)
    component_p95 = {
        name: _percentile(
            [float(row["components"][name]) for row in rows],
            0.95,
        )
        for name in _LADDER_COMPONENTS
    }
    p95 = _percentile(latencies, 0.95)
    entries = int(raw["entries"])
    total_bytes = int(raw["total_bytes"])
    cap_compliant = (
        total_bytes <= int(config["max_cache_bytes"])
        and entries <= int(config["max_cache_entries"])
    )
    invalid = error_rate is None
    breached: str | None = None
    if invalid:
        breached = "invalid_non_fixture_window"
    else:
        backend = config["budgets"][
            "postgres" if repository == "postgres" else "memory"
        ]
        if p95 > float(backend["p95_end_to_end_latency_ms"]):
            breached = "p95_end_to_end_latency_ms"
        elif error_rate > float(backend["non_fixture_error_rate"]):
            breached = "non_fixture_error_rate"
        elif timeout_rate > float(config["budgets"]["timeout_rate"]):
            breached = "timeout_rate"
    winner = None
    if (
        cap_compliant
        and breached is not None
        and breached != "invalid_non_fixture_window"
    ):
        winner = select_component_bottleneck(component_p95)
    total_p95 = sum(component_p95.values())
    shares = (
        None
        if total_p95 == 0
        else {
            name: round(component_p95[name] / total_p95, 6)
            for name in _LADDER_COMPONENTS
        }
    )
    simulated = int(step["simulated_q_per_day"])
    simulated_qps = simulated / 86400
    elapsed = float(raw["elapsed_seconds"])
    request_count = len(rows)
    requests_per_second = request_count / elapsed if elapsed else 0.0
    repeats = sum(1 for row in rows if row["label"] == "development_repeat")
    return {
        "step_id": step["id"],
        "run_index": run_index,
        "simulated_q_per_day": simulated,
        "simulated_qps": round(simulated_qps, 6),
        "request_count": int(step["request_count"]),
        "warmup_requests": int(step["warmup_requests"]),
        "concurrency": int(step["concurrency"]),
        "process_count": int(config.get("process_count", 1)),
        "elapsed_seconds": round(elapsed, 6),
        "requests_per_second": round(requests_per_second, 3),
        "compression_factor": (
            round(requests_per_second / simulated_qps, 6) if simulated_qps else None
        ),
        "realized_repeat_ratio": round(repeats / len(rows), 6),
        "p50_latency_ms": round(_percentile(latencies, 0.50), 3),
        "p95_end_to_end_latency_ms": round(p95, 3),
        "p99_latency_ms": round(_percentile(latencies, 0.99), 3),
        "error_count": sum(1 for row in rows if int(row["status_code"]) >= 400),
        "non_fixture_error_rate": None if error_rate is None else round(error_rate, 6),
        "timeout_count": timeouts,
        "timeout_rate": round(timeout_rate, 6),
        "entries": entries,
        "total_bytes": total_bytes,
        "eviction_count": int(raw["eviction_count"]),
        "cap_compliant": cap_compliant,
        "isolate_queries": repository == "postgres",
        "component_p95_ms": {
            name: round(component_p95[name], 3) for name in _LADDER_COMPONENTS
        },
        "component_p95_share": shares,
        "unavailable_components": list(_LADDER_UNAVAILABLE),
        "budget_breached": breached,
        "component_bottleneck": winner,
    }


def _ladder_outcome(step: Mapping[str, Any]) -> str:
    if not step["cap_compliant"]:
        return "cap"
    if step["budget_breached"] is None:
        return "not_reached"
    if step["component_bottleneck"] in {None, "unattributed"}:
        return "unattributed"
    return str(step["component_bottleneck"])


def _pair_ladder_runs(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, Any]:
    left = _ladder_outcome(first)
    right = _ladder_outcome(second)
    step_id = first["step_id"]
    if left != right:
        return {
            "first_bottleneck": None,
            "bottleneck_outcome": None,
            "bottleneck_step": step_id,
            "reproducibility": "disagree",
        }
    if left == "not_reached":
        return {
            "first_bottleneck": "not_reached",
            "bottleneck_outcome": "not_reached",
            "bottleneck_step": None,
            "reproducibility": "agree",
        }
    if left == "unattributed":
        return {
            "first_bottleneck": None,
            "bottleneck_outcome": "unattributed",
            "bottleneck_step": step_id,
            "reproducibility": "agree",
        }
    return {
        "first_bottleneck": left,
        "bottleneck_outcome": left,
        "bottleneck_step": step_id,
        "reproducibility": "agree",
    }


def _unavailable_ladder_report(config: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "report_type": "phase3_load_ladder",
        "protocol_id": config.get("protocol_id"),
        "status": "unavailable",
        "dataset_version": config.get("dataset_version"),
        "split": "development",
        "measurement_environment": "synthetic_replay",
        "repository": "postgres",
        "unavailable_reason": reason,
        "steps": [],
        "first_bottleneck": None,
        "bottleneck_outcome": None,
        "bottleneck_step": None,
        "reproducibility": None,
        "connection_measurement": "not_instrumented",
        "postgresql_version": None,
        "limitation": config.get("limitation"),
    }


def run_ladder(
    config: dict[str, Any],
    *,
    config_path: Path | None = None,
    step_runner: Callable[[dict[str, Any], Mapping[str, Any], int], Mapping[str, Any]]
    | None = None,
) -> dict[str, Any]:
    """Run the Feature 8 ladder. Does not use the milestone 10 / WS8 stop rules."""
    repository = str(config.get("repository", "memory"))
    if repository == "postgres" and not os.getenv("SSCRE_DATABASE_URL"):
        return _unavailable_ladder_report(
            config,
            "SSCRE_DATABASE_URL is not set",
        )
    if repository not in {"memory", "postgres"}:
        raise ValueError("load ladder repository must be memory or postgres")
    modes = config.get("modes", ["compatibility"])
    if list(modes) != ["compatibility"]:
        raise ValueError("phase3 load ladder requires modes ['compatibility']")
    steps = config.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("load ladder configuration requires steps")

    pool_size: dict[str, int | None] = {"value": None}

    def default_runner(
        runner_config: dict[str, Any],
        step: Mapping[str, Any],
        _run_index: int,
    ) -> Mapping[str, Any]:
        pool = load_ladder_pool(runner_config["development_path"])
        pool_size["value"] = len(pool)
        return _measure_ladder_step(runner_config, step, pool)

    runner = step_runner or default_runner
    executed: list[dict[str, Any]] = []
    decision: dict[str, Any] | None = None

    def execute(step: Mapping[str, Any], run_index: int) -> dict[str, Any]:
        raw = runner(config, step, run_index)
        return _score_ladder_step(config, step, raw, run_index, repository)

    for step in steps:
        first = execute(step, 1)
        executed.append(first)
        if not first["cap_compliant"] or first["budget_breached"] == "invalid_non_fixture_window":
            decision = {
                "first_bottleneck": None,
                "bottleneck_outcome": None,
                "bottleneck_step": None,
                "reproducibility": None,
            }
            break
        if first["budget_breached"] is not None:
            second = execute(step, 2)
            executed.append(second)
            decision = _pair_ladder_runs(first, second)
            break
    else:
        if executed:
            second = execute(steps[-1], 2)
            decision = _pair_ladder_runs(executed[-1], second)
            executed.append(second)
    if decision is None:
        decision = {
            "first_bottleneck": None,
            "bottleneck_outcome": None,
            "bottleneck_step": None,
            "reproducibility": None,
        }

    development_path = config.get("development_path")
    database_url = os.getenv("SSCRE_DATABASE_URL") if repository == "postgres" else None
    return {
        "report_type": "phase3_load_ladder",
        "protocol_id": config.get("protocol_id"),
        "status": "complete",
        "dataset_version": config.get("dataset_version"),
        "split": "development",
        "development_sha256": (
            file_sha256(_resolve_repo_path(development_path))
            if development_path
            else None
        ),
        "config_sha256": file_sha256(config_path) if config_path is not None else None,
        "git_commit": _git_commit(),
        "git_worktree_dirty": _git_worktree_dirty(),
        "measurement_environment": "synthetic_replay",
        "threshold_arm": config.get("threshold_arm"),
        "similarity_threshold": config.get("similarity_threshold"),
        "seed": config.get("seed"),
        "repeat_ratio": config.get("repeat_ratio"),
        "pool_size": pool_size["value"],
        "cache_mode": "compatibility",
        "cache_policy": {
            "max_entries": int(config["max_cache_entries"]),
            "max_bytes": int(config["max_cache_bytes"]),
        },
        "repository": repository,
        "unavailable_reason": None,
        "steps": executed,
        "first_bottleneck": decision["first_bottleneck"],
        "bottleneck_outcome": decision["bottleneck_outcome"],
        "bottleneck_step": decision["bottleneck_step"],
        "reproducibility": decision["reproducibility"],
        "connection_measurement": "not_instrumented",
        "postgresql_version": (
            _postgresql_version(database_url) if database_url else None
        ),
        "environment": _measurement_environment(config, database_url=database_url),
        "limitation": config.get("limitation"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repository", choices=("memory", "postgres"), default=None)
    args = parser.parse_args(argv)
    config = _load_config(args.config)
    if args.repository:
        config["repository"] = args.repository
    if config.get("protocol_id") == "phase3-load-ladder-v1":
        report = run_ladder(config, config_path=args.config)
    else:
        report = run(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote load-test report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
