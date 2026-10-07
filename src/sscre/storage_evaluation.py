"""Deterministic evaluation of Milestone 9 storage controls."""

import argparse
import json
import math
import subprocess
from time import perf_counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.metadata import extract_metadata
from sscre.query import hash_query, normalize_query
from sscre import __version__


@dataclass(frozen=True)
class StorageWorkloadItem:
    query: str
    answer: str
    ttl_seconds: int | None = 3600
    input_tokens: int | None = None
    output_tokens: int | None = None
    generation_latency_ms: int | None = None


@dataclass(frozen=True)
class StorageControlReport:
    report_type: str
    dataset_version: str
    workload_count: int
    deduplicated: bool
    requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    entries: int
    canonical_answers: int
    total_bytes: int
    no_dedup_total_bytes: int
    average_entry_bytes: float
    deduplication_hits: int
    deduplication_savings_bytes: int
    eviction_count: int
    expiration_count: int
    max_entries: int
    max_bytes: int
    generated_at: str
    software_version: str
    git_commit: str | None
    git_worktree_dirty: bool | None
    baseline_output_tokens: int
    controlled_output_tokens: int
    output_tokens_saved: int
    baseline_input_tokens: int
    controlled_input_tokens: int
    input_tokens_saved: int
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    baseline_cost_usd: float
    controlled_cost_usd: float
    estimated_generation_latency_ms: float
    estimated_cached_latency_ms: float
    latency_source: str
    token_source: str
    reusable_opportunities: int
    safe_reuse_coverage: float
    expired_reuse_prevented: int
    measurement_environment: str = "synthetic_storage_simulation"


def build_reuse_storage_pareto_point(
    report: StorageControlReport | Mapping[str, object],
    *,
    evaluation_config: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Map a storage report to the WS5 reuse-versus-storage point shape."""
    source = asdict(report) if isinstance(report, StorageControlReport) else dict(report)
    dataset_version = source.get("dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version:
        raise ValueError("storage report requires a non-empty dataset_version")
    measurement_environment = source.get("measurement_environment")
    if measurement_environment not in (None, "synthetic_storage_simulation"):
        raise ValueError(
            "storage report must use synthetic_storage_simulation measurement_environment"
        )

    for field_name in ("total_bytes", "entries", "eviction_count"):
        value = source.get(field_name)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            raise ValueError(f"storage report {field_name} must be a non-negative integer")

    safe_reuse_coverage = source.get("safe_reuse_coverage")
    if (
        isinstance(safe_reuse_coverage, bool)
        or not isinstance(safe_reuse_coverage, (int, float))
        or not math.isfinite(safe_reuse_coverage)
        or not 0.0 <= safe_reuse_coverage <= 1.0
    ):
        raise ValueError("storage report safe_reuse_coverage must be between 0 and 1")

    config_metadata: dict[str, object] = {}
    if evaluation_config is not None:
        if evaluation_config.get("dataset_version") != dataset_version:
            raise ValueError(
                "storage report and evaluation config dataset versions differ"
            )
        config_version = evaluation_config.get("config_version")
        if not isinstance(config_version, str) or not config_version:
            raise ValueError("evaluation config requires a non-empty config_version")
        for field_name in (
            "input_cost_per_1k_tokens",
            "output_cost_per_1k_tokens",
            "embedding_cost_per_1k_tokens",
            "cache_lookup_cost_usd",
            "preprocessing_cost_usd",
        ):
            value = evaluation_config.get(field_name, 0.0)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"evaluation config {field_name} must be non-negative")
        for field_name in ("input_cost_per_1k_tokens", "output_cost_per_1k_tokens"):
            if source.get(field_name, 0.0) != evaluation_config.get(field_name, 0.0):
                raise ValueError(
                    f"storage report and evaluation config {field_name} differ"
                )
        config_metadata = {
            "config_version": config_version,
            "costs": {
                field_name: evaluation_config.get(field_name, 0.0)
                for field_name in (
                    "input_cost_per_1k_tokens",
                    "output_cost_per_1k_tokens",
                    "embedding_cost_per_1k_tokens",
                    "cache_lookup_cost_usd",
                    "preprocessing_cost_usd",
                )
            },
        }

    return {
        "plane": "reuse_vs_storage",
        "dataset_version": dataset_version,
        "measurement_environment": "synthetic_storage_simulation",
        "source": "storage_control_report",
        **config_metadata,
        "x": {
            "metric": "safe_reuse_coverage",
            "value": safe_reuse_coverage,
            "direction": "maximize",
        },
        "y": {
            "metric": "total_bytes",
            "value": source["total_bytes"],
            "direction": "minimize",
        },
        "storage": {
            "total_bytes": source["total_bytes"],
            "entries": source["entries"],
            "eviction_count": source["eviction_count"],
        },
    }

def _git_metadata() -> tuple[str | None, bool | None]:
    root = Path(__file__).resolve().parents[2]
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None, None
    commit = (
        commit_result.stdout.strip()
        if commit_result.returncode == 0
        else None
    )
    dirty = (
        bool(status_result.stdout.strip())
        if status_result.returncode == 0
        else None
    )
    return commit or None, dirty


def run_storage_control_evaluation(
    workload: Iterable[StorageWorkloadItem],
    *,
    dataset_version: str,
    max_entries: int = 10_000,
    max_bytes: int = 100_000_000,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
    generation_latency_ms: int = 100,
) -> StorageControlReport:
    """Replay a workload through real deduplication and no-dedup caches."""
    if (
        input_cost_per_1k_tokens < 0
        or output_cost_per_1k_tokens < 0
        or generation_latency_ms < 0
    ):
        raise ValueError("costs and generation latency must not be negative")
    cache = InMemoryExactCache(deduplicate=True)
    no_dedup_cache = InMemoryExactCache(deduplicate=False)
    requests = 0
    hits = 0
    misses = 0
    items = tuple(workload)
    now = datetime.now(timezone.utc)
    baseline_input_tokens = sum(
        item.input_tokens if item.input_tokens is not None else len(item.query.split())
        for item in items
    )
    baseline_output_tokens = sum(
        item.output_tokens
        if item.output_tokens is not None
        else len(item.answer.split())
        for item in items
    )
    controlled_output_tokens = 0
    controlled_input_tokens = 0
    controlled_generation_latency_ms = 0
    reusable_opportunities = 0
    expired_reuse_prevented = 0
    seen_queries: set[str] = set()
    started_at = perf_counter()

    for item in items:
        normalized_query = normalize_query(item.query)
        query_hash = hash_query(normalized_query)
        existing = cache.get_by_query_hash(query_hash)
        if (
            existing is not None
            and existing.ttl_expires_at is not None
            and existing.ttl_expires_at <= now
        ):
            expired_reuse_prevented += 1
        cache.cleanup_expired(limit=100)
        no_dedup_cache.cleanup_expired(limit=100)
        requests += 1
        if query_hash in seen_queries:
            reusable_opportunities += 1
        seen_queries.add(query_hash)
        if cache.get_by_query_hash(query_hash) is not None:
            hits += 1
            cache.record_hit(query_hash)
            continue
        misses += 1
        controlled_generation_latency_ms += (
            item.generation_latency_ms
            if item.generation_latency_ms is not None
            else generation_latency_ms
        )
        controlled_input_tokens += (
            item.input_tokens
            if item.input_tokens is not None
            else len(item.query.split())
        )
        controlled_output_tokens += (
            item.output_tokens
            if item.output_tokens is not None
            else len(item.answer.split())
        )
        expires_at = (
            now + timedelta(seconds=item.ttl_seconds)
            if item.ttl_seconds is not None
            else None
        )
        entry = CacheEntry(
                query_hash=query_hash,
                normalized_query=normalized_query,
                answer=item.answer,
                metadata=extract_metadata(normalized_query),
                ttl_expires_at=expires_at,
            )
        cache.insert_and_evict(
            entry,
            max_entries=max_entries,
            max_bytes=max_bytes,
        )
        no_dedup_cache.insert_and_evict(
            entry,
            max_entries=max_entries,
            max_bytes=max_bytes,
        )
    cache.cleanup_expired(limit=100)
    no_dedup_cache.cleanup_expired(limit=100)

    stats = cache.storage_stats()
    no_dedup_stats = no_dedup_cache.storage_stats()
    cache_processing_ms = (perf_counter() - started_at) * 1000
    git_commit, git_worktree_dirty = _git_metadata()
    baseline_cost_usd = round(
        baseline_input_tokens / 1000 * input_cost_per_1k_tokens
        + baseline_output_tokens / 1000 * output_cost_per_1k_tokens,
        6,
    )
    controlled_cost_usd = round(
        controlled_input_tokens / 1000 * input_cost_per_1k_tokens
        + controlled_output_tokens / 1000 * output_cost_per_1k_tokens,
        6,
    )
    uses_provider_tokens = any(
        item.input_tokens is not None or item.output_tokens is not None
        for item in items
    )
    uses_provider_latency = any(
        item.generation_latency_ms is not None for item in items
    )
    return StorageControlReport(
        report_type="storage_controls",
        dataset_version=dataset_version,
        workload_count=len(items),
        deduplicated=True,
        requests=requests,
        cache_hits=hits,
        cache_misses=misses,
        hit_rate=hits / requests if requests else 0.0,
        entries=stats.entries,
        canonical_answers=stats.canonical_answers,
        total_bytes=stats.total_bytes,
        no_dedup_total_bytes=no_dedup_stats.total_bytes,
        average_entry_bytes=stats.average_entry_bytes,
        deduplication_hits=stats.deduplication_hits,
        deduplication_savings_bytes=stats.deduplication_savings_bytes,
        eviction_count=stats.evictions,
        expiration_count=stats.expirations,
        max_entries=max_entries,
        max_bytes=max_bytes,
        generated_at=datetime.now(timezone.utc).isoformat(),
        software_version=__version__,
        git_commit=git_commit,
        git_worktree_dirty=git_worktree_dirty,
        baseline_output_tokens=baseline_output_tokens,
        controlled_output_tokens=controlled_output_tokens,
        output_tokens_saved=baseline_output_tokens - controlled_output_tokens,
        baseline_input_tokens=baseline_input_tokens,
        controlled_input_tokens=controlled_input_tokens,
        input_tokens_saved=baseline_input_tokens - controlled_input_tokens,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
        baseline_cost_usd=baseline_cost_usd,
        controlled_cost_usd=controlled_cost_usd,
        estimated_generation_latency_ms=(
            sum(
                item.generation_latency_ms
                if item.generation_latency_ms is not None
                else generation_latency_ms
                for item in items
            )
        ),
        estimated_cached_latency_ms=(
            controlled_generation_latency_ms + cache_processing_ms
        ),
        latency_source=(
            "provider_usage_per_item"
            if uses_provider_latency
            else "synthetic_configured_generation_latency_plus_measured_cache_processing"
        ),
        token_source=(
            "provider_usage_per_item"
            if uses_provider_tokens
            else "synthetic_whitespace_token_estimate"
        ),
        reusable_opportunities=reusable_opportunities,
        safe_reuse_coverage=(
            hits / reusable_opportunities
            if reusable_opportunities
            else 0.0
        ),
        expired_reuse_prevented=expired_reuse_prevented,
    )


def save_storage_control_report(
    report: StorageControlReport,
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", required=True, help="JSON workload path")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-entries", type=int, default=10_000)
    parser.add_argument("--max-bytes", type=int, default=100_000_000)
    parser.add_argument("--input-cost-per-1k-tokens", type=float, default=0.0)
    parser.add_argument("--output-cost-per-1k-tokens", type=float, default=0.0)
    parser.add_argument("--generation-latency-ms", type=int, default=100)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.workload).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("workload must be a JSON array")
    workload = tuple(StorageWorkloadItem(**item) for item in payload)
    report = run_storage_control_evaluation(
        workload,
        dataset_version=args.dataset_version,
        max_entries=args.max_entries,
        max_bytes=args.max_bytes,
        input_cost_per_1k_tokens=args.input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=args.output_cost_per_1k_tokens,
        generation_latency_ms=args.generation_latency_ms,
    )
    save_storage_control_report(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
