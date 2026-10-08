"""Evaluation baselines for reviewed benchmark workloads."""

import json
import math
from dataclasses import asdict, dataclass, field, replace
from time import perf_counter
from pathlib import Path
from typing import Any, Mapping, Protocol

from sscre.benchmark import BenchmarkRecord
from sscre.cache import (
    CacheEntry,
    DuplicateCacheEntryError,
    InMemoryExactCache,
)
from sscre.embedding import EmbeddingClient, FakeEmbeddingClient
from sscre.llm import LLMResult, MockLLMClient
from sscre.cache_control_traces import build_cache_control_trace
from sscre.cache_controls import evaluate_cache_control
from sscre.freshness_evaluation import FreshnessReplayClock
from sscre.compatibility import evaluate_candidate_boundary
from sscre.metadata import extract_metadata
from sscre.query import hash_query, normalize_query
from sscre.serialization import (
    attach_evaluation_report_schema,
    redact_operational_evaluation_report,
    boundary_candidate_traces,
)
from sscre.evaluation_labels import (
    build_evaluation_labels,
    build_label_sections,
    classify_compatibility_disagreement,
    correctness_metrics_bucket,
    expected_compatibility_decision,
)
from sscre.evaluation_statistics import (
    RequestObservationSample,
    RequestSampleCollector,
    enrich_evaluation_payload,
    estimate_request_observation_cost_usd,
    reuse_outcome_indicators,
)
from sscre.safety import (
    CandidateTrace,
    QueryMetadata,
    SafetyDecision,
    is_reusable_decision,
    resolve_candidate_traces,
)


class BaselineLLMClient(Protocol):
    def generate(self, query: str) -> LLMResult:
        ...


def _insert_if_absent(cache: InMemoryExactCache, entry: CacheEntry) -> None:
    try:
        cache.insert(entry)
    except DuplicateCacheEntryError:
        # A reviewed workload may contain the same normalized query more than
        # once. It is already represented by the existing cache entry.
        pass


def _evaluate_baseline_cache_control(
    temporal_class: str,
    ttl_expires_at: object,
    *,
    freshness_replay_clock: FreshnessReplayClock | None,
):
    if freshness_replay_clock is None:
        return evaluate_cache_control(
            temporal_class,  # type: ignore[arg-type]
            ttl_expires_at,  # type: ignore[arg-type]
        )
    return freshness_replay_clock.evaluate_cache_control(
        temporal_class,  # type: ignore[arg-type]
        ttl_expires_at,  # type: ignore[arg-type]
    )


def _baseline_cache_entry_after_generation(
    *,
    query_hash: str,
    normalized_query: str,
    answer: str,
    query_metadata: QueryMetadata,
    embedding_result: object,
    freshness_replay_clock: FreshnessReplayClock | None,
) -> CacheEntry:
    embedding = getattr(embedding_result, "vector", None)
    common = {
        "query_hash": query_hash,
        "normalized_query": normalized_query,
        "answer": answer,
        "embedding": embedding,
        "embedding_model": getattr(embedding_result, "model_name", None),
        "embedding_dimension": len(embedding) if embedding is not None else None,
        "metadata": query_metadata,
    }
    if freshness_replay_clock is None:
        return CacheEntry(**common)
    return CacheEntry(
        **common,
        ttl_expires_at=freshness_replay_clock.ttl_expires_at_for_insert(
            query_metadata
        ),
    )


@dataclass(frozen=True)
class NoCacheReport:
    baseline: str
    dataset_version: str
    request_count: int
    generated_requests: int
    cache_hits: int
    cache_misses: int
    input_tokens: int
    output_tokens: int
    total_latency_ms: int
    average_latency_ms: float
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    estimated_cost_usd: float
    safe_reuse_hits: int = 0
    reusable_opportunities: int = 0
    safe_reuse_coverage: float = 0.0
    input_tokens_saved: int = 0
    output_tokens_saved: int = 0
    tokens_saved: int = 0
    cache_lookup_cost_usd: float = 0.0
    preprocessing_cost_usd: float = 0.0
    cache_miss_categories: dict[str, int] = field(default_factory=dict)
    failure_categories: dict[str, int] = field(default_factory=dict)
    hit_rate: float = 0.0
    request_samples: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class ExactCacheReport:
    baseline: str
    dataset_version: str
    request_count: int
    generated_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    safe_reuse_hits: int
    reusable_opportunities: int
    safe_reuse_coverage: float
    input_tokens: int
    output_tokens: int
    input_tokens_saved: int
    output_tokens_saved: int
    tokens_saved: int
    total_latency_ms: int
    average_latency_ms: float
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    cache_lookup_cost_usd: float
    preprocessing_cost_usd: float
    estimated_cost_usd: float
    cache_miss_categories: dict[str, int]
    failure_categories: dict[str, int]
    request_samples: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class EmbeddingCacheReport:
    baseline: str
    dataset_version: str
    threshold: float
    top_k: int
    embedding_model: str
    embedding_dimension: int
    request_count: int
    generated_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    safe_reuse_hits: int
    unsafe_reuse_hits: int
    reusable_opportunities: int
    safe_reuse_coverage: float
    precision: float
    recall: float
    false_positive_rate: float
    threshold_rejections: int
    semantic_misses: int
    embedding_tokens: int
    input_tokens: int
    output_tokens: int
    tokens_saved: int
    total_latency_ms: int
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    embedding_cost_per_1k_tokens: float
    cache_lookup_cost_usd: float
    preprocessing_cost_usd: float
    estimated_cost_usd: float
    failure_categories: dict[str, int]
    false_positive_examples: list[dict[str, object]]
    request_samples: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class EmbeddingThresholdSweepReport:
    baseline: str
    dataset_version: str
    thresholds: tuple[float, ...]
    selected_threshold: float
    selection_rule: str
    constraint_satisfied: bool
    reports: tuple[EmbeddingCacheReport, ...]


@dataclass(frozen=True)
class CompatibilityCacheReport:
    baseline: str
    dataset_version: str
    threshold: float
    top_k: int
    embedding_model: str
    embedding_dimension: int
    request_count: int
    generated_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
    safe_reuse_hits: int
    unsafe_reuse_hits: int
    uncertain_decisions: int
    reusable_opportunities: int
    safe_reuse_coverage: float
    precision: float
    recall: float
    false_positive_rate: float
    abstention_rate: float
    embedding_tokens: int
    input_tokens: int
    output_tokens: int
    tokens_saved: int
    total_latency_ms: int
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    embedding_cost_per_1k_tokens: float
    cache_lookup_cost_usd: float
    preprocessing_cost_usd: float
    estimated_cost_usd: float
    decision_counts: dict[str, int]
    decision_breakdowns: dict[str, dict[str, int]]
    failure_categories: dict[str, int]
    failure_examples: list[dict[str, object]]
    correctness_label_counts: dict[str, int]
    compatibility_label_counts: dict[str, int]
    preference_label_counts: dict[str, int]
    label_sections: dict[str, dict[str, int]]
    false_positive_examples: list[dict[str, object]]
    observed_pair_records: list[dict[str, object]]
    disagreement_class_counts: dict[str, int]
    cache_control_outcome_counts: dict[str, int] = field(default_factory=dict)
    freshness_replay_policy_name: str | None = None
    policy_storage_snapshot: dict[str, int] = field(default_factory=dict)
    request_samples: tuple[dict[str, object], ...] = ()


def _benchmark_strata(record: BenchmarkRecord) -> tuple[str | None, str | None]:
    failure = record.failure_category
    freshness = str(record.freshness_class)
    return failure, freshness


def no_cache_cost_kwargs_from_config(config: Mapping[str, Any]) -> dict[str, float]:
    """Build keyword arguments accepted by ``run_no_cache_baseline``."""
    return {
        "input_cost_per_1k_tokens": float(config["input_cost_per_1k_tokens"]),
        "output_cost_per_1k_tokens": float(config["output_cost_per_1k_tokens"]),
    }


def compatibility_cache_cost_kwargs_from_config(
    config: Mapping[str, Any],
) -> dict[str, float]:
    """Build cost kwargs for semantic/compatibility baseline runners.

    Do not pass this dict to ``run_no_cache_baseline``; it includes embedding
    and cache lookup fields that runner does not accept.
    """
    return {
        **no_cache_cost_kwargs_from_config(config),
        "embedding_cost_per_1k_tokens": float(
            config["embedding_cost_per_1k_tokens"]
        ),
        "cache_lookup_cost_usd": float(config["cache_lookup_cost_usd"]),
        "preprocessing_cost_usd": float(config["preprocessing_cost_usd"]),
    }


def run_no_cache_baseline(
    records: list[BenchmarkRecord],
    *,
    dataset_version: str,
    llm_client: BaselineLLMClient | None = None,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
    collect_request_samples: bool = True,
) -> NoCacheReport:
    """Replay both query directions without performing cache lookup."""
    if input_cost_per_1k_tokens < 0 or output_cost_per_1k_tokens < 0:
        raise ValueError("token costs must not be negative")

    model_client = llm_client or MockLLMClient()
    sample_collector = RequestSampleCollector(enabled=collect_request_samples)
    request_count = 0
    input_tokens = 0
    output_tokens = 0
    total_latency_ms = 0

    for record in records:
        failure_category, freshness_class = _benchmark_strata(record)
        for direction, query in (
            ("a_to_b", record.query_a),
            ("b_to_a", record.query_b),
        ):
            result = model_client.generate(normalize_query(query))
            request_count += 1
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
            total_latency_ms += result.latency_ms
            sample_collector.record(
                RequestObservationSample(
                    pair_id=record.id,
                    direction=direction,
                    cache_hit=0,
                    generated=1,
                    false_positive=0,
                    safe_reuse_hit=0,
                    latency_ms=float(result.latency_ms),
                    embedding_tokens=0,
                    generation_input_tokens=result.input_tokens,
                    generation_output_tokens=result.output_tokens,
                    estimated_cost_usd=estimate_request_observation_cost_usd(
                        generation_input_tokens=result.input_tokens,
                        generation_output_tokens=result.output_tokens,
                        embedding_tokens=0,
                        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
                        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
                        embedding_cost_per_1k_tokens=0.0,
                        cache_lookup_cost_usd=0.0,
                        preprocessing_cost_usd=0.0,
                    ),
                    failure_category=failure_category,
                    freshness_class=freshness_class,
                )
            )

    estimated_cost_usd = round(
        input_tokens * input_cost_per_1k_tokens / 1000
        + output_tokens * output_cost_per_1k_tokens / 1000,
        6,
    )
    average_latency_ms = (
        total_latency_ms / request_count if request_count else 0.0
    )
    return NoCacheReport(
        baseline="no-cache",
        dataset_version=dataset_version,
        request_count=request_count,
        generated_requests=request_count,
        cache_hits=0,
        cache_misses=0,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_latency_ms=total_latency_ms,
        average_latency_ms=average_latency_ms,
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
        estimated_cost_usd=estimated_cost_usd,
        request_samples=sample_collector.as_tuple(),
    )


def run_exact_cache_baseline(
    records: list[BenchmarkRecord],
    *,
    dataset_version: str,
    llm_client: BaselineLLMClient | None = None,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
    cache_lookup_cost_usd: float = 0.0,
    preprocessing_cost_usd: float = 0.0,
    collect_request_samples: bool = True,
) -> ExactCacheReport:
    """Replay both query directions with normalized exact-cache lookup."""
    costs = (
        input_cost_per_1k_tokens,
        output_cost_per_1k_tokens,
        cache_lookup_cost_usd,
        preprocessing_cost_usd,
    )
    if any(cost < 0 for cost in costs):
        raise ValueError("costs must not be negative")

    model_client = llm_client or MockLLMClient()
    cache = InMemoryExactCache()
    sample_collector = RequestSampleCollector(enabled=collect_request_samples)
    request_count = 0
    generated_requests = 0
    cache_hits = 0
    cache_misses = 0
    safe_reuse_hits = 0
    reusable_opportunities = sum(record.reusable for record in records)
    input_tokens = 0
    output_tokens = 0
    input_tokens_saved = 0
    output_tokens_saved = 0
    total_latency_ms = 0
    cache_miss_categories = {"not_cached": 0}
    failure_categories: dict[str, int] = {}

    for record in records:
        failure_category, freshness_class = _benchmark_strata(record)
        for direction, query in (("a_to_b", record.query_a), ("b_to_a", record.query_b)):
            started_at = perf_counter()
            normalized_query = normalize_query(query)
            query_hash = hash_query(normalized_query)
            cached_entry = cache.get_by_query_hash(query_hash)
            request_count += 1

            if cached_entry is not None:
                cache_hits += 1
                hit_input_tokens = len(normalized_query.split())
                hit_output_tokens = len(cached_entry.answer.split())
                input_tokens_saved += hit_input_tokens
                output_tokens_saved += hit_output_tokens
                false_positive, safe_reuse_hit = reuse_outcome_indicators(
                    direction=direction,
                    reusable=record.reusable,
                    served_reuse=True,
                )
                if safe_reuse_hit:
                    safe_reuse_hits += 1
                request_latency_ms = float(
                    int((perf_counter() - started_at) * 1000)
                )
                total_latency_ms += int(request_latency_ms)
                sample_collector.record(
                    RequestObservationSample(
                        pair_id=record.id,
                        direction=direction,
                        cache_hit=1,
                        generated=0,
                        false_positive=false_positive,
                        safe_reuse_hit=safe_reuse_hit,
                        latency_ms=request_latency_ms,
                        embedding_tokens=0,
                        generation_input_tokens=0,
                        generation_output_tokens=0,
                        estimated_cost_usd=estimate_request_observation_cost_usd(
                            generation_input_tokens=0,
                            generation_output_tokens=0,
                            embedding_tokens=0,
                            input_cost_per_1k_tokens=input_cost_per_1k_tokens,
                            output_cost_per_1k_tokens=output_cost_per_1k_tokens,
                            embedding_cost_per_1k_tokens=0.0,
                            cache_lookup_cost_usd=cache_lookup_cost_usd,
                            preprocessing_cost_usd=preprocessing_cost_usd,
                        ),
                        failure_category=failure_category,
                        freshness_class=freshness_class,
                    )
                )
                continue

            cache_misses += 1
            cache_miss_categories["not_cached"] += 1
            result = model_client.generate(normalized_query)
            generated_requests += 1
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
            total_latency_ms += result.latency_ms
            sample_collector.record(
                RequestObservationSample(
                    pair_id=record.id,
                    direction=direction,
                    cache_hit=0,
                    generated=1,
                    false_positive=0,
                    safe_reuse_hit=0,
                    latency_ms=float(result.latency_ms),
                    embedding_tokens=0,
                    generation_input_tokens=result.input_tokens,
                    generation_output_tokens=result.output_tokens,
                    estimated_cost_usd=estimate_request_observation_cost_usd(
                        generation_input_tokens=result.input_tokens,
                        generation_output_tokens=result.output_tokens,
                        embedding_tokens=0,
                        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
                        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
                        embedding_cost_per_1k_tokens=0.0,
                        cache_lookup_cost_usd=cache_lookup_cost_usd,
                        preprocessing_cost_usd=preprocessing_cost_usd,
                    ),
                    failure_category=failure_category,
                    freshness_class=freshness_class,
                )
            )
            _insert_if_absent(
                cache,
                CacheEntry(
                    query_hash=query_hash,
                    normalized_query=normalized_query,
                    answer=result.text,
                )
            )

    tokens_saved = input_tokens_saved + output_tokens_saved
    estimated_cost_usd = round(
        input_tokens * input_cost_per_1k_tokens / 1000
        + output_tokens * output_cost_per_1k_tokens / 1000
        + request_count * cache_lookup_cost_usd
        + request_count * preprocessing_cost_usd,
        6,
    )
    return ExactCacheReport(
        baseline="exact-cache",
        dataset_version=dataset_version,
        request_count=request_count,
        generated_requests=generated_requests,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        hit_rate=cache_hits / request_count if request_count else 0.0,
        safe_reuse_hits=safe_reuse_hits,
        reusable_opportunities=reusable_opportunities,
        safe_reuse_coverage=(
            safe_reuse_hits / reusable_opportunities
            if reusable_opportunities
            else 0.0
        ),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_saved=input_tokens_saved,
        output_tokens_saved=output_tokens_saved,
        tokens_saved=tokens_saved,
        total_latency_ms=total_latency_ms,
        average_latency_ms=(
            total_latency_ms / request_count if request_count else 0.0
        ),
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
        cache_lookup_cost_usd=cache_lookup_cost_usd,
        preprocessing_cost_usd=preprocessing_cost_usd,
        estimated_cost_usd=estimated_cost_usd,
        cache_miss_categories=cache_miss_categories,
        failure_categories=failure_categories,
        request_samples=sample_collector.as_tuple(),
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def run_embedding_cache_baseline(
    records: list[BenchmarkRecord],
    *,
    dataset_version: str,
    threshold: float,
    top_k: int = 5,
    llm_client: BaselineLLMClient | None = None,
    embedding_client: EmbeddingClient | None = None,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
    embedding_cost_per_1k_tokens: float = 0.0,
    cache_lookup_cost_usd: float = 0.0,
    preprocessing_cost_usd: float = 0.0,
    collect_request_samples: bool = True,
) -> EmbeddingCacheReport:
    """Replay the development workload with embedding-only reuse."""
    if not math.isfinite(threshold) or not -1.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between -1 and 1")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    costs = (
        input_cost_per_1k_tokens,
        output_cost_per_1k_tokens,
        embedding_cost_per_1k_tokens,
        cache_lookup_cost_usd,
        preprocessing_cost_usd,
    )
    if any(cost < 0 for cost in costs):
        raise ValueError("costs must not be negative")

    model_client = llm_client or MockLLMClient()
    vector_client = embedding_client or FakeEmbeddingClient()
    cache = InMemoryExactCache(
        max_top_k=top_k,
        embedding_dimension=vector_client.config.dimension,
    )
    sample_collector = RequestSampleCollector(enabled=collect_request_samples)
    request_count = 0
    generated_requests = 0
    cache_hits = 0
    cache_misses = 0
    safe_reuse_hits = 0
    unsafe_reuse_hits = 0
    threshold_rejections = 0
    semantic_misses = 0
    reusable_opportunities = sum(record.reusable for record in records)
    embedding_tokens = 0
    input_tokens = 0
    output_tokens = 0
    tokens_saved = 0
    total_latency_ms = 0
    request_latencies: list[float] = []
    false_positive_examples: list[dict[str, object]] = []

    for record in records:
        failure_category, freshness_class = _benchmark_strata(record)
        for direction, query in (
            ("a_to_b", record.query_a),
            ("b_to_a", record.query_b),
        ):
            started_at = perf_counter()
            normalized_query = normalize_query(query)
            embedding_result = vector_client.embed(normalized_query)
            embedding_tokens += embedding_result.input_tokens
            candidates = cache.search_by_embedding(
                embedding_result.vector,
                top_k,
            )
            request_count += 1
            candidate = candidates[0] if candidates else None
            if candidate is not None and candidate.similarity >= threshold:
                cache_hits += 1
                tokens_saved += len(normalized_query.split())
                tokens_saved += len(candidate.answer.split())
                false_positive, safe_reuse_hit = reuse_outcome_indicators(
                    direction=direction,
                    reusable=record.reusable,
                    served_reuse=True,
                )
                if direction == "b_to_a":
                    if safe_reuse_hit:
                        safe_reuse_hits += 1
                    elif false_positive:
                        unsafe_reuse_hits += 1
                        false_positive_examples.append(
                            {
                                "id": record.id,
                                "direction": direction,
                                "query_a": record.query_a,
                                "query_b": record.query_b,
                                "similarity": candidate.similarity,
                                "reason": record.reason,
                            }
                        )
                request_latency_ms = float(
                    embedding_result.latency_ms
                    + int((perf_counter() - started_at) * 1000)
                )
                request_latencies.append(request_latency_ms)
                total_latency_ms += int(request_latency_ms)
                sample_collector.record(
                    RequestObservationSample(
                        pair_id=record.id,
                        direction=direction,
                        cache_hit=1,
                        generated=0,
                        false_positive=false_positive,
                        safe_reuse_hit=safe_reuse_hit,
                        latency_ms=request_latency_ms,
                        embedding_tokens=embedding_result.input_tokens,
                        generation_input_tokens=0,
                        generation_output_tokens=0,
                        estimated_cost_usd=estimate_request_observation_cost_usd(
                            generation_input_tokens=0,
                            generation_output_tokens=0,
                            embedding_tokens=embedding_result.input_tokens,
                            input_cost_per_1k_tokens=input_cost_per_1k_tokens,
                            output_cost_per_1k_tokens=output_cost_per_1k_tokens,
                            embedding_cost_per_1k_tokens=embedding_cost_per_1k_tokens,
                            cache_lookup_cost_usd=cache_lookup_cost_usd,
                            preprocessing_cost_usd=preprocessing_cost_usd,
                        ),
                        failure_category=failure_category,
                        freshness_class=freshness_class,
                    )
                )
                continue

            cache_misses += 1
            if candidate is None:
                semantic_misses += 1
            else:
                threshold_rejections += 1
            result = model_client.generate(normalized_query)
            generated_requests += 1
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
            request_latency_ms = float(
                embedding_result.latency_ms + result.latency_ms
            )
            request_latencies.append(request_latency_ms)
            total_latency_ms += int(request_latency_ms)
            sample_collector.record(
                RequestObservationSample(
                    pair_id=record.id,
                    direction=direction,
                    cache_hit=0,
                    generated=1,
                    false_positive=0,
                    safe_reuse_hit=0,
                    latency_ms=request_latency_ms,
                    embedding_tokens=embedding_result.input_tokens,
                    generation_input_tokens=result.input_tokens,
                    generation_output_tokens=result.output_tokens,
                    estimated_cost_usd=estimate_request_observation_cost_usd(
                        generation_input_tokens=result.input_tokens,
                        generation_output_tokens=result.output_tokens,
                        embedding_tokens=embedding_result.input_tokens,
                        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
                        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
                        embedding_cost_per_1k_tokens=embedding_cost_per_1k_tokens,
                        cache_lookup_cost_usd=cache_lookup_cost_usd,
                        preprocessing_cost_usd=preprocessing_cost_usd,
                    ),
                    failure_category=failure_category,
                    freshness_class=freshness_class,
                )
            )
            _insert_if_absent(
                cache,
                CacheEntry(
                    query_hash=hash_query(normalized_query),
                    normalized_query=normalized_query,
                    answer=result.text,
                    embedding=embedding_result.vector,
                    embedding_model=embedding_result.model_name,
                    embedding_dimension=len(embedding_result.vector),
                )
            )

    evaluated_hits = safe_reuse_hits + unsafe_reuse_hits
    return EmbeddingCacheReport(
        baseline="embedding-cache",
        dataset_version=dataset_version,
        threshold=threshold,
        top_k=top_k,
        embedding_model=vector_client.config.model_name,
        embedding_dimension=vector_client.config.dimension,
        request_count=request_count,
        generated_requests=generated_requests,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        hit_rate=cache_hits / request_count if request_count else 0.0,
        safe_reuse_hits=safe_reuse_hits,
        unsafe_reuse_hits=unsafe_reuse_hits,
        reusable_opportunities=reusable_opportunities,
        safe_reuse_coverage=(
            safe_reuse_hits / reusable_opportunities
            if reusable_opportunities
            else 0.0
        ),
        precision=safe_reuse_hits / evaluated_hits if evaluated_hits else 0.0,
        recall=(
            safe_reuse_hits / reusable_opportunities
            if reusable_opportunities
            else 0.0
        ),
        false_positive_rate=(
            unsafe_reuse_hits / cache_hits
            if cache_hits
            else 0.0
        ),
        threshold_rejections=threshold_rejections,
        semantic_misses=semantic_misses,
        embedding_tokens=embedding_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tokens_saved=tokens_saved,
        total_latency_ms=total_latency_ms,
        average_latency_ms=(
            total_latency_ms / request_count if request_count else 0.0
        ),
        p50_latency_ms=_percentile(request_latencies, 0.50),
        p95_latency_ms=_percentile(request_latencies, 0.95),
        p99_latency_ms=_percentile(request_latencies, 0.99),
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
        embedding_cost_per_1k_tokens=embedding_cost_per_1k_tokens,
        cache_lookup_cost_usd=cache_lookup_cost_usd,
        preprocessing_cost_usd=preprocessing_cost_usd,
        estimated_cost_usd=round(
            input_tokens * input_cost_per_1k_tokens / 1000
            + output_tokens * output_cost_per_1k_tokens / 1000
            + embedding_tokens * embedding_cost_per_1k_tokens / 1000
            + request_count
            * (cache_lookup_cost_usd + preprocessing_cost_usd),
            6,
        ),
        failure_categories={},
        false_positive_examples=false_positive_examples,
        request_samples=sample_collector.as_tuple(),
    )


def run_compatibility_cache_baseline(
    records: list[BenchmarkRecord],
    *,
    dataset_version: str,
    threshold: float,
    top_k: int = 5,
    llm_client: BaselineLLMClient | None = None,
    embedding_client: EmbeddingClient | None = None,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
    embedding_cost_per_1k_tokens: float = 0.0,
    cache_lookup_cost_usd: float = 0.0,
    preprocessing_cost_usd: float = 0.0,
    collect_request_samples: bool = True,
    freshness_replay_clock: FreshnessReplayClock | None = None,
) -> CompatibilityCacheReport:
    """Replay the workload with rule-based compatibility-aware reuse."""
    if not math.isfinite(threshold) or not -1.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between -1 and 1")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    costs = (
        input_cost_per_1k_tokens,
        output_cost_per_1k_tokens,
        embedding_cost_per_1k_tokens,
        cache_lookup_cost_usd,
        preprocessing_cost_usd,
    )
    if any(cost < 0 for cost in costs):
        raise ValueError("costs must not be negative")

    model_client = llm_client or MockLLMClient()
    vector_client = embedding_client or FakeEmbeddingClient()
    cache = InMemoryExactCache(
        max_top_k=top_k,
        embedding_dimension=vector_client.config.dimension,
    )
    sample_collector = RequestSampleCollector(enabled=collect_request_samples)
    request_count = generated_requests = cache_hits = cache_misses = 0
    safe_reuse_hits = unsafe_reuse_hits = uncertain_decisions = 0
    reusable_opportunities = sum(record.reusable for record in records)
    embedding_tokens = input_tokens = output_tokens = tokens_saved = 0
    total_latency_ms = 0
    request_latencies: list[float] = []
    decision_counts: dict[str, int] = {}
    decision_breakdowns: dict[str, dict[str, int]] = {}
    failure_categories: dict[str, int] = {}
    false_positive_examples: list[dict[str, object]] = []
    failure_examples: list[dict[str, object]] = []
    correctness_label_counts: dict[str, int] = {}
    compatibility_label_counts: dict[str, int] = {}
    preference_label_counts: dict[str, int] = {}
    compatibility_agreement_counts: dict[str, int] = {}
    observed_pair_records: list[dict[str, object]] = []
    disagreement_class_counts: dict[str, int] = {}
    cache_control_outcome_counts: dict[str, int] = {}

    def record_compatibility_agreement(
        record: BenchmarkRecord,
        observed: SafetyDecision,
    ) -> None:
        expected = expected_compatibility_decision(record)
        bucket = "match" if observed == expected else "mismatch"
        compatibility_agreement_counts[bucket] = (
            compatibility_agreement_counts.get(bucket, 0) + 1
        )

    def record_pair_observation(
        record: BenchmarkRecord,
        *,
        observed: SafetyDecision,
        reason: str,
        traces: tuple[CandidateTrace, ...],
    ) -> None:
        expected = expected_compatibility_decision(record)
        disagreement = classify_compatibility_disagreement(
            expected_decision=expected,
            observed_decision=observed,
            reason=reason,
            has_traces=bool(traces),
        )
        if disagreement is not None:
            disagreement_class_counts[disagreement] = (
                disagreement_class_counts.get(disagreement, 0) + 1
            )
        record_compatibility_agreement(record, observed)
        observed_pair_records.append(
            {
                "id": record.id,
                "direction": "b_to_a",
                "expected_compatibility": record.compatibility_label,
                "expected_decision": expected,
                "observed_decision": observed,
                "reason": reason,
                "disagreement_class": disagreement,
                "candidate_traces": boundary_candidate_traces(traces),
                "evaluation_labels": build_evaluation_labels(
                    record=record,
                    observed_decision=observed,
                ).to_artifact_dict(),
            }
        )

    def example_with_labels(
        example: dict[str, object],
        record: BenchmarkRecord,
        observed: SafetyDecision,
    ) -> dict[str, object]:
        enriched = dict(example)
        enriched["evaluation_labels"] = build_evaluation_labels(
            record=record,
            observed_decision=observed,
        ).to_artifact_dict()
        return enriched

    def record_breakdown(query_metadata: QueryMetadata, outcome: str) -> None:
        dimensions = {
            "intent": query_metadata.intent,
            "domain": query_metadata.domain,
            "format": query_metadata.output_format,
            "temporal": query_metadata.temporal_class,
        }
        for key, value in dimensions.items():
            labels = decision_breakdowns.setdefault(key, {})
            label = f"{value}:{outcome}"
            labels[label] = labels.get(label, 0) + 1
        constraint_labels = (
            [f"{key}={value}" for key, value in query_metadata.constraints]
            or ["none"]
        )
        entity_labels = list(query_metadata.entities) or ["none"]
        for key, values in (
            ("constraint", constraint_labels),
            ("entity", entity_labels),
        ):
            labels = decision_breakdowns.setdefault(key, {})
            for value in values:
                label = f"{value}:{outcome}"
                labels[label] = labels.get(label, 0) + 1

    for record in records:
        failure_category, freshness_class = _benchmark_strata(record)
        compatibility_label_counts[record.compatibility_label] = (
            compatibility_label_counts.get(record.compatibility_label, 0) + 1
        )
        preference_bucket = (
            record.preference_label
            if record.preference_label is not None
            else "not_collected"
        )
        preference_label_counts[preference_bucket] = (
            preference_label_counts.get(preference_bucket, 0) + 1
        )
        correctness_bucket = correctness_metrics_bucket(
            record.correctness_label  # type: ignore[arg-type]
        )
        correctness_label_counts[correctness_bucket] = (
            correctness_label_counts.get(correctness_bucket, 0) + 1
        )
        for direction, query in (
            ("a_to_b", record.query_a),
            ("b_to_a", record.query_b),
        ):
            started_at = perf_counter()
            normalized_query = normalize_query(query)
            query_metadata = extract_metadata(normalized_query)
            embedding_result = vector_client.embed(normalized_query)
            embedding_tokens += embedding_result.input_tokens
            candidates = cache.search_by_embedding(
                embedding_result.vector,
                top_k,
            )
            request_count += 1

            safe_candidate = None
            evaluated_traces = []
            for index, candidate in enumerate(candidates):
                temporal_class = (
                    candidate.metadata.temporal_class
                    if candidate.metadata is not None
                    else "stable"
                )
                control = _evaluate_baseline_cache_control(
                    temporal_class,
                    candidate.ttl_expires_at,
                    freshness_replay_clock=freshness_replay_clock,
                )
                if control.reusable:
                    candidate_trace = replace(
                        evaluate_candidate_boundary(
                            query_metadata,
                            candidate,
                            similarity_threshold=threshold,
                        ),
                        candidate_order=index + 1,
                        freshness_class=temporal_class,
                        cache_control_outcome=control.reason,
                    )
                else:
                    candidate_trace = build_cache_control_trace(
                        candidate,
                        control,
                        candidate_order=index + 1,
                        query_metadata=query_metadata.to_dict(),
                    )
                evaluated_traces.append(candidate_trace)
                outcome = candidate_trace.cache_control_outcome
                if outcome is not None:
                    cache_control_outcome_counts[outcome] = (
                        cache_control_outcome_counts.get(outcome, 0) + 1
                    )
                if (
                    safe_candidate is None
                    and is_reusable_decision(candidate_trace.decision)
                ):
                    safe_candidate = candidate

            if safe_candidate is not None:
                cache_hits += 1
                decision_counts["SAFE"] = decision_counts.get("SAFE", 0) + 1
                record_breakdown(query_metadata, "SAFE")
                tokens_saved += len(normalized_query.split())
                tokens_saved += len(safe_candidate.answer.split())
                false_positive, safe_reuse_hit = reuse_outcome_indicators(
                    direction=direction,
                    reusable=record.reusable,
                    served_reuse=True,
                )
                if direction == "b_to_a":
                    winning = next(
                        trace
                        for trace in evaluated_traces
                        if is_reusable_decision(trace.decision)
                    )
                    record_pair_observation(
                        record,
                        observed="SAFE",
                        reason=winning.reason,
                        traces=tuple(evaluated_traces),
                    )
                    if safe_reuse_hit:
                        safe_reuse_hits += 1
                    elif false_positive:
                        unsafe_reuse_hits += 1
                        example = example_with_labels(
                            {
                                "id": record.id,
                                "direction": direction,
                                "query_a": record.query_a,
                                "query_b": record.query_b,
                                "similarity": safe_candidate.similarity,
                                "predicted_decision": "SAFE",
                                "expected_reusable": record.reusable,
                                "expected_compatibility": record.compatibility_label,
                                "reason": record.reason,
                                "failure_category": "false_positive",
                                "candidate_traces": boundary_candidate_traces(
                                    tuple(evaluated_traces)
                                ),
                            },
                            record,
                            "SAFE",
                        )
                        false_positive_examples.append(example)
                        failure_examples.append(example)
                request_latency_ms = float(
                    embedding_result.latency_ms
                    + int((perf_counter() - started_at) * 1000)
                )
                request_latencies.append(request_latency_ms)
                total_latency_ms += int(request_latency_ms)
                sample_collector.record(
                    RequestObservationSample(
                        pair_id=record.id,
                        direction=direction,
                        cache_hit=1,
                        generated=0,
                        false_positive=false_positive,
                        safe_reuse_hit=safe_reuse_hit,
                        latency_ms=request_latency_ms,
                        embedding_tokens=embedding_result.input_tokens,
                        generation_input_tokens=0,
                        generation_output_tokens=0,
                        estimated_cost_usd=estimate_request_observation_cost_usd(
                            generation_input_tokens=0,
                            generation_output_tokens=0,
                            embedding_tokens=embedding_result.input_tokens,
                            input_cost_per_1k_tokens=input_cost_per_1k_tokens,
                            output_cost_per_1k_tokens=output_cost_per_1k_tokens,
                            embedding_cost_per_1k_tokens=embedding_cost_per_1k_tokens,
                            cache_lookup_cost_usd=cache_lookup_cost_usd,
                            preprocessing_cost_usd=preprocessing_cost_usd,
                        ),
                        observed_decision="SAFE",
                        failure_category=failure_category,
                        freshness_class=freshness_class,
                        runtime_temporal_class=query_metadata.temporal_class,
                    )
                )
                if freshness_replay_clock is not None:
                    freshness_replay_clock.advance()
                continue

            cache_misses += 1
            request_decision: SafetyDecision | None = None
            if candidates:
                aggregate = resolve_candidate_traces(
                    tuple(evaluated_traces),
                    strategy="C",
                )
                decision = aggregate.decision
                request_decision = decision
                reason = aggregate.reason
                decision_counts[decision] = decision_counts.get(decision, 0) + 1
                record_breakdown(query_metadata, decision)
                if decision == "UNCERTAIN":
                    uncertain_decisions += 1
                candidate_trace = evaluated_traces[-1] if evaluated_traces else None
                category = reason.split(":", 1)[0]
                failure_categories[category] = (
                    failure_categories.get(category, 0) + 1
                )
                if direction == "b_to_a":
                    record_pair_observation(
                        record,
                        observed=decision,
                        reason=reason,
                        traces=tuple(evaluated_traces),
                    )
                    failure_category = None
                    if record.reusable:
                        failure_category = "false_negative"
                    elif decision == "UNCERTAIN":
                        failure_category = "unnecessary_abstention"
                    if failure_category is not None:
                        failure_examples.append(
                            example_with_labels(
                                {
                                    "id": record.id,
                                    "direction": direction,
                                    "query_a": record.query_a,
                                    "query_b": record.query_b,
                                    "similarity": (
                                        candidate_trace.similarity
                                        if candidate_trace is not None
                                        else None
                                    ),
                                    "predicted_decision": decision,
                                    "expected_reusable": record.reusable,
                                    "expected_compatibility": (
                                        record.compatibility_label
                                    ),
                                    "reason": reason,
                                    "failure_category": failure_category,
                                    "candidate_traces": boundary_candidate_traces(
                                        tuple(evaluated_traces)
                                    ),
                                },
                                record,
                                decision,
                            )
                        )
            else:
                empty_result = resolve_candidate_traces((), strategy="C")
                request_decision = empty_result.decision
                decision_counts[empty_result.decision] = (
                    decision_counts.get(empty_result.decision, 0) + 1
                )
                record_breakdown(query_metadata, empty_result.decision)
                failure_categories["semantic_miss"] = (
                    failure_categories.get("semantic_miss", 0) + 1
                )
                if direction == "b_to_a":
                    record_pair_observation(
                        record,
                        observed=empty_result.decision,
                        reason=empty_result.reason,
                        traces=(),
                    )
                    if record.reusable:
                        failure_examples.append(
                            example_with_labels(
                                {
                                    "id": record.id,
                                    "direction": direction,
                                    "query_a": record.query_a,
                                    "query_b": record.query_b,
                                    "similarity": None,
                                    "predicted_decision": empty_result.decision,
                                    "expected_reusable": record.reusable,
                                    "expected_compatibility": record.compatibility_label,
                                    "reason": empty_result.reason,
                                    "failure_category": "false_negative",
                                },
                                record,
                                empty_result.decision,
                            )
                        )
            result = model_client.generate(normalized_query)
            generated_requests += 1
            input_tokens += result.input_tokens
            output_tokens += result.output_tokens
            request_latency_ms = float(
                embedding_result.latency_ms + result.latency_ms
            )
            request_latencies.append(request_latency_ms)
            total_latency_ms += int(request_latency_ms)
            sample_collector.record(
                RequestObservationSample(
                    pair_id=record.id,
                    direction=direction,
                    cache_hit=0,
                    generated=1,
                    false_positive=0,
                    safe_reuse_hit=0,
                    latency_ms=request_latency_ms,
                    embedding_tokens=embedding_result.input_tokens,
                    generation_input_tokens=result.input_tokens,
                    generation_output_tokens=result.output_tokens,
                    estimated_cost_usd=estimate_request_observation_cost_usd(
                        generation_input_tokens=result.input_tokens,
                        generation_output_tokens=result.output_tokens,
                        embedding_tokens=embedding_result.input_tokens,
                        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
                        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
                        embedding_cost_per_1k_tokens=embedding_cost_per_1k_tokens,
                        cache_lookup_cost_usd=cache_lookup_cost_usd,
                        preprocessing_cost_usd=preprocessing_cost_usd,
                    ),
                    observed_decision=request_decision,
                    failure_category=failure_category,
                    freshness_class=freshness_class,
                    runtime_temporal_class=query_metadata.temporal_class,
                )
            )
            _insert_if_absent(
                cache,
                _baseline_cache_entry_after_generation(
                    query_hash=hash_query(normalized_query),
                    normalized_query=normalized_query,
                    answer=result.text,
                    query_metadata=query_metadata,
                    embedding_result=embedding_result,
                    freshness_replay_clock=freshness_replay_clock,
                ),
            )
            if freshness_replay_clock is not None:
                freshness_replay_clock.advance()

    evaluated_hits = safe_reuse_hits + unsafe_reuse_hits
    evaluated_decisions = (
        decision_counts.get("SAFE", 0)
        + decision_counts.get("UNSAFE", 0)
        + decision_counts.get("UNCERTAIN", 0)
    )
    storage_stats = cache.storage_stats()
    policy_storage_snapshot: dict[str, int] = {}
    if freshness_replay_clock is not None:
        physical_cleanup = cache.cleanup_expired(limit=10_000)
        post_cleanup_stats = cache.storage_stats()
        policy_storage_snapshot = {
            "entries_before_cleanup": storage_stats.entries,
            "total_bytes_before_cleanup": storage_stats.total_bytes,
            "canonical_answers_before_cleanup": storage_stats.canonical_answers,
            "eviction_count": storage_stats.evictions,
            "expiration_counter": storage_stats.expirations,
            "lazy_expired_rejection_count": cache_control_outcome_counts.get(
                "expired",
                0,
            ),
            "physical_expiration_cleanup_count": physical_cleanup,
            "entries_after_cleanup": post_cleanup_stats.entries,
            "total_bytes_after_cleanup": post_cleanup_stats.total_bytes,
        }

    return CompatibilityCacheReport(
        baseline="compatibility-cache",
        dataset_version=dataset_version,
        threshold=threshold,
        top_k=top_k,
        embedding_model=vector_client.config.model_name,
        embedding_dimension=vector_client.config.dimension,
        request_count=request_count,
        generated_requests=generated_requests,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        hit_rate=cache_hits / request_count if request_count else 0.0,
        safe_reuse_hits=safe_reuse_hits,
        unsafe_reuse_hits=unsafe_reuse_hits,
        uncertain_decisions=uncertain_decisions,
        reusable_opportunities=reusable_opportunities,
        safe_reuse_coverage=(
            safe_reuse_hits / reusable_opportunities
            if reusable_opportunities
            else 0.0
        ),
        precision=safe_reuse_hits / evaluated_hits if evaluated_hits else 0.0,
        recall=(
            safe_reuse_hits / reusable_opportunities
            if reusable_opportunities
            else 0.0
        ),
        false_positive_rate=(
            unsafe_reuse_hits / cache_hits
            if cache_hits
            else 0.0
        ),
        abstention_rate=(
            uncertain_decisions / evaluated_decisions
            if evaluated_decisions
            else 0.0
        ),
        embedding_tokens=embedding_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tokens_saved=tokens_saved,
        total_latency_ms=total_latency_ms,
        average_latency_ms=(
            total_latency_ms / request_count if request_count else 0.0
        ),
        p50_latency_ms=_percentile(request_latencies, 0.50),
        p95_latency_ms=_percentile(request_latencies, 0.95),
        p99_latency_ms=_percentile(request_latencies, 0.99),
        input_cost_per_1k_tokens=input_cost_per_1k_tokens,
        output_cost_per_1k_tokens=output_cost_per_1k_tokens,
        embedding_cost_per_1k_tokens=embedding_cost_per_1k_tokens,
        cache_lookup_cost_usd=cache_lookup_cost_usd,
        preprocessing_cost_usd=preprocessing_cost_usd,
        estimated_cost_usd=round(
            input_tokens * input_cost_per_1k_tokens / 1000
            + output_tokens * output_cost_per_1k_tokens / 1000
            + embedding_tokens * embedding_cost_per_1k_tokens / 1000
            + request_count
            * (cache_lookup_cost_usd + preprocessing_cost_usd),
            6,
        ),
        decision_counts=decision_counts,
        decision_breakdowns=decision_breakdowns,
        failure_categories=failure_categories,
        failure_examples=failure_examples,
        correctness_label_counts=correctness_label_counts,
        compatibility_label_counts=compatibility_label_counts,
        preference_label_counts=preference_label_counts,
        label_sections=build_label_sections(
            compatibility_label_counts=compatibility_label_counts,
            correctness_label_counts=correctness_label_counts,
            preference_label_counts=preference_label_counts,
            compatibility_agreement_counts=compatibility_agreement_counts,
            decision_counts=decision_counts,
        ),
        false_positive_examples=false_positive_examples,
        observed_pair_records=observed_pair_records,
        disagreement_class_counts=disagreement_class_counts,
        cache_control_outcome_counts=cache_control_outcome_counts,
        freshness_replay_policy_name=(
            freshness_replay_clock.policy_name
            if freshness_replay_clock is not None
            else None
        ),
        policy_storage_snapshot=policy_storage_snapshot,
        request_samples=sample_collector.as_tuple(),
    )


def select_embedding_threshold(
    reports: list[EmbeddingCacheReport],
    *,
    max_false_positive_rate: float = 0.0,
) -> EmbeddingCacheReport:
    """Select maximum safe reuse coverage under a development FPR limit."""
    if not reports:
        raise ValueError("at least one threshold report is required")
    if not 0.0 <= max_false_positive_rate <= 1.0:
        raise ValueError("max_false_positive_rate must be between 0 and 1")

    eligible = [
        report
        for report in reports
        if report.false_positive_rate <= max_false_positive_rate
    ]
    if eligible:
        return max(
            eligible,
            key=lambda report: (
                report.safe_reuse_coverage,
                -report.false_positive_rate,
                report.threshold,
            ),
        )
    return min(
        reports,
        key=lambda report: (
            report.false_positive_rate,
            -report.safe_reuse_coverage,
            -report.threshold,
        ),
    )


def run_embedding_threshold_sweep(
    records: list[BenchmarkRecord],
    *,
    dataset_version: str,
    thresholds: list[float],
    top_k: int = 5,
    max_false_positive_rate: float = 0.0,
    llm_client: BaselineLLMClient | None = None,
    embedding_client: EmbeddingClient | None = None,
    input_cost_per_1k_tokens: float = 0.0,
    output_cost_per_1k_tokens: float = 0.0,
    embedding_cost_per_1k_tokens: float = 0.0,
    cache_lookup_cost_usd: float = 0.0,
    preprocessing_cost_usd: float = 0.0,
) -> EmbeddingThresholdSweepReport:
    if not thresholds:
        raise ValueError("thresholds must not be empty")
    if any(not math.isfinite(value) for value in thresholds):
        raise ValueError("thresholds must be finite")
    reports = tuple(
        run_embedding_cache_baseline(
            records,
            dataset_version=dataset_version,
            threshold=threshold,
            top_k=top_k,
            llm_client=llm_client,
            embedding_client=embedding_client,
            input_cost_per_1k_tokens=input_cost_per_1k_tokens,
            output_cost_per_1k_tokens=output_cost_per_1k_tokens,
            embedding_cost_per_1k_tokens=embedding_cost_per_1k_tokens,
            cache_lookup_cost_usd=cache_lookup_cost_usd,
            preprocessing_cost_usd=preprocessing_cost_usd,
        )
        for threshold in thresholds
    )
    selected = select_embedding_threshold(
        list(reports),
        max_false_positive_rate=max_false_positive_rate,
    )
    constraint_satisfied = any(
        report.false_positive_rate <= max_false_positive_rate
        for report in reports
    )
    return EmbeddingThresholdSweepReport(
        baseline="embedding-cache-threshold-sweep",
        dataset_version=dataset_version,
        thresholds=tuple(thresholds),
        selected_threshold=selected.threshold,
        selection_rule=(
            "maximize safe reuse coverage subject to the development "
            f"false-positive rate <= {max_false_positive_rate}"
        ),
        constraint_satisfied=constraint_satisfied,
        reports=reports,
    )


def _save_report(
    report: (
        NoCacheReport
        | ExactCacheReport
        | EmbeddingCacheReport
        | CompatibilityCacheReport
        | EmbeddingThresholdSweepReport
    ),
    path: str | Path,
    metadata: Mapping[str, object] | None,
    *,
    evaluation_config: Mapping[str, object] | None = None,
    attach_statistics: bool = True,
) -> None:
    payload = enrich_evaluation_payload(
        asdict(report),
        evaluation_config,
        attach_statistics=attach_statistics,
    )
    payload = redact_operational_evaluation_report(
        attach_evaluation_report_schema(payload)
    )
    if metadata:
        payload.update(metadata)
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def save_no_cache_report(
    report: NoCacheReport,
    path: str | Path,
    *,
    metadata: Mapping[str, object] | None = None,
    evaluation_config: Mapping[str, object] | None = None,
    attach_statistics: bool = True,
) -> None:
    """Save a no-cache report as indented, machine-readable JSON."""
    _save_report(
        report,
        path,
        metadata,
        evaluation_config=evaluation_config,
        attach_statistics=attach_statistics,
    )


def save_exact_cache_report(
    report: ExactCacheReport,
    path: str | Path,
    *,
    metadata: Mapping[str, object] | None = None,
    evaluation_config: Mapping[str, object] | None = None,
    attach_statistics: bool = True,
) -> None:
    """Save an exact-cache report as indented, machine-readable JSON."""
    _save_report(
        report,
        path,
        metadata,
        evaluation_config=evaluation_config,
        attach_statistics=attach_statistics,
    )


def save_embedding_sweep_report(
    report: EmbeddingThresholdSweepReport,
    path: str | Path,
    *,
    metadata: Mapping[str, object] | None = None,
    evaluation_config: Mapping[str, object] | None = None,
    attach_statistics: bool = True,
) -> None:
    """Save a development-only Strategy B threshold sweep report."""
    _save_report(
        report,
        path,
        metadata,
        evaluation_config=evaluation_config,
        attach_statistics=attach_statistics,
    )


def save_embedding_cache_report(
    report: EmbeddingCacheReport,
    path: str | Path,
    *,
    metadata: Mapping[str, object] | None = None,
    evaluation_config: Mapping[str, object] | None = None,
    attach_statistics: bool = True,
) -> None:
    """Save a single Strategy B evaluation report."""
    _save_report(
        report,
        path,
        metadata,
        evaluation_config=evaluation_config,
        attach_statistics=attach_statistics,
    )


def save_compatibility_cache_report(
    report: CompatibilityCacheReport,
    path: str | Path,
    *,
    metadata: Mapping[str, object] | None = None,
    evaluation_config: Mapping[str, object] | None = None,
    attach_statistics: bool = True,
) -> None:
    """Save a single Strategy C evaluation report."""
    _save_report(
        report,
        path,
        metadata,
        evaluation_config=evaluation_config,
        attach_statistics=attach_statistics,
    )
