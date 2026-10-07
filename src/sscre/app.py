import json
import logging
import hmac
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from threading import BoundedSemaphore, Lock
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Header
from fastapi import HTTPException

from sscre.cache_control_traces import build_cache_control_trace
from sscre.cache_controls import evaluate_cache_control
from sscre.compatibility import evaluate_candidate_boundary
from sscre.cache import (
    CacheCandidate,
    CacheEntry,
    CacheRepositoryError,
    DuplicateCacheEntryError,
    ExactCacheRepository,
    InMemoryExactCache,
)
from sscre.config import Settings
from sscre.embedding import (
    EmbeddingClient,
    FakeEmbeddingClient,
    validate_embedding_result,
)
from sscre.llm import LLMClient, MockLLMClient, validate_llm_result
from sscre.metrics import MetricsCollector
from sscre.postgres_cache import PostgresExactCacheRepository
from pathlib import Path

from sscre.pricing import (
    CostBreakdown,
    PricingSchedule,
    estimate_request_cost,
    load_pricing_schedule_from_json,
)
from sscre.provider_config import RealProviderConfig
from sscre.query import QueryRequest, QueryResponse, preprocess_query
from sscre.remote_embedding import OpenAICompatibleEmbeddingClient
from sscre.remote_llm import OpenAICompatibleLLMClient
from sscre.serialization import (
    boundary_candidate_traces,
    dumps_cache_decision_log,
)
from sscre.safety import (
    MAX_CANDIDATE_TRACES,
    CandidateTrace,
    SafetyDecision,
    SafetyResult,
    is_reusable_decision,
    resolve_candidate_traces,
)

logger = logging.getLogger("sscre")


def _cost_metric_fields(cost: CostBreakdown) -> dict[str, object]:
    return {
        "generation_cost_usd": cost.generation_cost_usd,
        "embedding_cost_usd": cost.embedding_cost_usd,
        "retry_cost_usd": cost.retry_cost_usd,
        "wrapper_cost_usd": cost.wrapper_cost_usd,
        "total_estimated_cost_usd": cost.total_estimated_cost_usd,
        "cost_source": cost.cost_source,
        "pricing_schedule_id": cost.pricing_schedule_id,
    }


class DependencyTimeoutError(RuntimeError):
    """Raised when a bounded dependency operation exceeds its budget."""


def run_with_timeout(
    executor: ThreadPoolExecutor,
    operation: Callable[[], object],
    timeout_seconds: float,
    operation_name: str,
    slots: BoundedSemaphore | None = None,
) -> object:
    if timeout_seconds <= 0:
        raise DependencyTimeoutError(f"{operation_name} timed out")
    if slots is not None and not slots.acquire(timeout=timeout_seconds):
        raise DependencyTimeoutError(f"{operation_name} capacity exhausted")
    future = executor.submit(operation)
    if slots is not None:
        future.add_done_callback(lambda _: slots.release())
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        raise DependencyTimeoutError(f"{operation_name} timed out") from exc


def create_app(
    llm_client: LLMClient | None = None,
    repository: ExactCacheRepository | None = None,
    settings: Settings | None = None,
    embedding_client: EmbeddingClient | None = None,
    semantic_enabled: bool | None = None,
    semantic_strategy: str | None = None,
    semantic_top_k: int | None = None,
    semantic_similarity_threshold: float | None = None,
    pricing_schedule: PricingSchedule | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings.from_environment()
    logger.setLevel(getattr(logging, runtime_settings.log_level))
    semantic_enabled = (
        runtime_settings.semantic_enabled
        if semantic_enabled is None
        else semantic_enabled
    )
    semantic_top_k = (
        runtime_settings.semantic_top_k
        if semantic_top_k is None
        else semantic_top_k
    )
    semantic_strategy = (
        runtime_settings.semantic_strategy
        if semantic_strategy is None
        else semantic_strategy
    )
    if semantic_strategy not in {"B", "C"}:
        raise ValueError("semantic_strategy must be B or C")
    semantic_similarity_threshold = (
        runtime_settings.semantic_similarity_threshold
        if semantic_similarity_threshold is None
        else semantic_similarity_threshold
    )
    if semantic_top_k <= 0:
        raise ValueError("semantic_top_k must be positive")
    if not -1.0 <= semantic_similarity_threshold <= 1.0:
        raise ValueError("semantic_similarity_threshold must be between -1 and 1")
    real_provider_config = RealProviderConfig.from_environment()
    if pricing_schedule is None and real_provider_config is not None:
        pricing_path = os.getenv("SSCRE_PROVIDER_PRICING_JSON")
        if pricing_path:
            pricing_schedule = load_pricing_schedule_from_json(
                Path(pricing_path),
                schedule_id=real_provider_config.pricing_schedule_id,
            )
    if real_provider_config is not None:
        if llm_client is None:
            llm_client = OpenAICompatibleLLMClient(real_provider_config)
        elif isinstance(llm_client, MockLLMClient):
            raise ValueError(
                "real-provider mode does not accept fake generation clients"
            )
        if semantic_enabled and embedding_client is None:
            embedding_client = OpenAICompatibleEmbeddingClient(
                real_provider_config
            )
        elif semantic_enabled and isinstance(embedding_client, FakeEmbeddingClient):
            raise ValueError(
                "real-provider mode does not accept fake embedding clients"
            )
    if runtime_settings.runtime_profile == "production" and (
        llm_client is None
        or (semantic_enabled and embedding_client is None)
    ):
        raise ValueError(
            "production profile requires explicitly configured provider clients"
        )
    cache_policy = runtime_settings.cache_control_policy()
    cache_size_limits = runtime_settings.cache_size_limits()
    max_cache_entries = runtime_settings.max_cache_entries
    max_cache_bytes = runtime_settings.max_cache_bytes

    app = FastAPI(title="SSCRE")
    if repository is not None:
        cache = repository
    elif runtime_settings.database_url:
        cache = PostgresExactCacheRepository(runtime_settings.database_url)
    else:
        cache = InMemoryExactCache()
    model_client = llm_client or MockLLMClient()
    vector_client = embedding_client or FakeEmbeddingClient()
    if runtime_settings.runtime_profile == "production" and (
        type(model_client) is MockLLMClient
        or (semantic_enabled and type(vector_client) is FakeEmbeddingClient)
    ):
        raise ValueError(
            "development fake providers are unavailable in production profile"
        )
    metrics = MetricsCollector()
    generation_lock = Lock()
    dependency_executor = ThreadPoolExecutor(
        max_workers=8,
        thread_name_prefix="sscre-dependency",
    )
    dependency_slots = BoundedSemaphore(8)

    def cache_control_for(entry: CacheEntry | CacheCandidate):
        # Rows loaded from storage without TTL metadata fail closed. New
        # in-memory entries receive a default TTL in CacheEntry.__post_init__.
        temporal_class = (
            entry.metadata.temporal_class
            if entry.metadata is not None
            else "stable"
        )
        expires_at = entry.ttl_expires_at
        return evaluate_cache_control(
            temporal_class,
            expires_at if isinstance(expires_at, datetime) else None,
            policy=cache_policy,
        )

    def cache_entry_is_reusable(entry: CacheEntry | CacheCandidate) -> bool:
        return cache_control_for(entry).reusable

    def record_cache_hit(query_hash: str) -> None:
        record_hit = getattr(cache, "record_hit", None)
        if callable(record_hit):
            try:
                run_with_timeout(
                    dependency_executor,
                    lambda: record_hit(query_hash),
                    runtime_settings.repository_timeout_seconds,
                    "cache access accounting",
                    dependency_slots,
                )
            except (CacheRepositoryError, DependencyTimeoutError) as exc:
                logger.warning(
                    "cache access accounting unavailable query_hash=%s error_type=%s",
                    query_hash,
                    type(exc).__name__,
                )

    def require_admin(
        authorization: str | None,
        required_scope: str,
    ) -> None:
        if (
            runtime_settings.admin_token is None
            and runtime_settings.admin_read_token is None
        ):
            raise HTTPException(
                status_code=503,
                detail="admin authentication unavailable",
            )
        if authorization is None:
            raise HTTPException(
                status_code=401,
                detail="authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        scheme, separator, presented_token = authorization.partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not presented_token
            or " " in presented_token
        ):
            raise HTTPException(
                status_code=401,
                detail="invalid authentication",
                headers={"WWW-Authenticate": "Bearer"},
            )
        credentials = (
            (
                "admin",
                runtime_settings.admin_token,
                runtime_settings.admin_token_expires_at,
                {"cache:read", "cache:write"},
            ),
            (
                "read_only",
                runtime_settings.admin_read_token,
                runtime_settings.admin_read_token_expires_at,
                {"cache:read"},
            ),
        )
        role = None
        permissions: set[str] = set()
        for candidate_role, configured_token, expires_at, candidate_permissions in (
            credentials
        ):
            if (
                configured_token is not None
                and hmac.compare_digest(presented_token, configured_token)
            ):
                if expires_at is not None and datetime.now(timezone.utc) >= expires_at:
                    raise HTTPException(
                        status_code=401,
                        detail="authentication expired",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                role = candidate_role
                permissions = candidate_permissions
                break
        if role is None:
            raise HTTPException(
                status_code=401,
                detail="invalid authentication",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if required_scope not in permissions:
            raise HTTPException(
                status_code=403,
                detail="insufficient privileges",
            )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, str]:
        check_ready = getattr(cache, "check_ready", None)
        if callable(check_ready):
            try:
                check_ready(
                    timeout_seconds=runtime_settings.health_timeout_seconds
                )
            except (CacheRepositoryError, ValueError) as exc:
                raise HTTPException(
                    status_code=503,
                    detail="service not ready",
                ) from exc
            return {"status": "ready", "repository": "postgres"}
        return {"status": "ready", "repository": "memory"}

    @app.get("/v1/cache/stats")
    def cache_stats(
        authorization: str | None = Header(default=None),
    ) -> dict[str, object]:
        require_admin(authorization, "cache:read")
        stats_method = getattr(cache, "storage_stats", None)
        if not callable(stats_method):
            raise HTTPException(
                status_code=503,
                detail="cache statistics unavailable",
            )
        try:
            stats = run_with_timeout(
                dependency_executor,
                stats_method,
                runtime_settings.admin_timeout_seconds,
                "cache statistics",
                dependency_slots,
            )
        except (CacheRepositoryError, DependencyTimeoutError) as exc:
            raise HTTPException(
                status_code=503,
                detail="cache statistics unavailable",
            ) from exc
        return {
            "storage": asdict(stats),
            "limits": {
                "max_entries": max_cache_entries,
                "max_bytes": max_cache_bytes,
            },
            "request_metrics": metrics.snapshot(
                request_id=uuid4(),
                total_latency_ms=0,
            ).model_dump(mode="json"),
        }

    @app.post("/v1/query", response_model=QueryResponse)
    def query(request: QueryRequest) -> QueryResponse:
        request_id = uuid4()
        started_at = perf_counter()
        processed = preprocess_query(request)
        decision_traces: tuple[CandidateTrace, ...] = ()
        cache_skip_reason: str | None = None
        reuse_block_reason: str | None = None

        def serialized_boundary_traces(traces: tuple[CandidateTrace, ...]):
            try:
                return boundary_candidate_traces(traces)
            except ValueError as exc:
                raise HTTPException(
                    status_code=500,
                    detail="cache decision unavailable",
                    headers={"X-Request-ID": str(request_id)},
                ) from exc

        def logged_strategy() -> str:
            if semantic_strategy == "C" or semantic_enabled:
                return semantic_strategy
            return "A"

        def merge_decision_traces(
            extra: tuple[CandidateTrace, ...],
        ) -> tuple[CandidateTrace, ...]:
            merged = list(decision_traces)
            index_by_hash = {
                trace.candidate_query_hash: index
                for index, trace in enumerate(merged)
            }
            for trace in extra:
                existing = index_by_hash.get(trace.candidate_query_hash)
                if existing is None:
                    index_by_hash[trace.candidate_query_hash] = len(merged)
                    merged.append(trace)
                else:
                    merged[existing] = trace
            return tuple(
                replace(trace, candidate_order=order)
                for order, trace in enumerate(merged, start=1)
            )

        def dependency_budget(configured_seconds: int) -> float:
            remaining = runtime_settings.request_timeout_seconds - (
                perf_counter() - started_at
            )
            if remaining <= 0:
                raise DependencyTimeoutError("request timeout exceeded")
            return min(float(configured_seconds), remaining)

        def ensure_request_budget() -> None:
            if (
                perf_counter() - started_at
                > runtime_settings.request_timeout_seconds
            ):
                raise HTTPException(
                    status_code=504,
                    detail="request timed out",
                    headers={"X-Request-ID": str(request_id)},
                )

        ensure_request_budget()

        @contextmanager
        def generation_guard() -> object:
            acquired = generation_lock.acquire(
                timeout=dependency_budget(
                    runtime_settings.generation_timeout_seconds
                )
            )
            if not acquired:
                raise DependencyTimeoutError("generation lock timed out")
            try:
                yield
            finally:
                generation_lock.release()

        def cached_response(
            entry: CacheEntry,
            *,
            decision: SafetyDecision = "SAFE",
            reason: str | None = "exact_query_hash_match",
            traces: tuple[CandidateTrace, ...] = (),
        ) -> QueryResponse:
            if not is_reusable_decision(decision):
                raise ValueError("cache responses require a reusable SAFE decision")
            ensure_request_budget()
            record_cache_hit(entry.query_hash)
            metrics.record_exact_hit()
            response_metrics = metrics.snapshot(
                request_id=request_id,
                total_latency_ms=int((perf_counter() - started_at) * 1000),
                provider_name=None,
            )
            effective_traces = traces or (
                exact_entry_boundary_trace(entry),
            )
            serialized_traces = serialized_boundary_traces(effective_traces)
            logger.info(
                dumps_cache_decision_log(
                    {
                        "event": "cache_decision",
                        "request_id": str(request_id),
                        "decision": decision,
                        "outcome": "cache_reused",
                        "source": "cache",
                        "strategy": "C" if traces else "A",
                        "candidate_traces": serialized_traces,
                        "latency_ms": response_metrics.total_latency_ms,
                        "llm_input_tokens": 0,
                        "llm_output_tokens": 0,
                    }
                )
            )
            return QueryResponse(
                answer=entry.answer,
                source="cache",
                strategy="exact",
                decision=decision,
                similarity=1.0,
                selected_candidate_query_hash=entry.query_hash,
                reason=reason,
                candidate_traces=serialized_traces,
                freshness_class=(
                    entry.metadata.temporal_class
                    if entry.metadata is not None
                    else None
                ),
                cache_control_reason=(
                    "fresh" if entry.ttl_expires_at is not None else None
                ),
                metrics=response_metrics,
            )

        def semantic_cached_response(
            candidate: CacheCandidate,
            safety_result: SafetyResult | None = None,
            traces: tuple[CandidateTrace, ...] = (),
        ) -> QueryResponse:
            if safety_result is not None and not is_reusable_decision(
                safety_result.decision
            ):
                raise ValueError("semantic cache responses require a SAFE decision")
            ensure_request_budget()
            record_cache_hit(candidate.query_hash)
            metrics.record_semantic_hit()
            response_metrics = metrics.snapshot(
                request_id=request_id,
                total_latency_ms=int((perf_counter() - started_at) * 1000),
                embedding_latency_ms=(
                    embedding_result.latency_ms if embedding_result is not None else 0
                ),
                embedding_input_tokens=(
                    embedding_result.input_tokens
                    if embedding_result is not None
                    else 0
                ),
                embedding_usage_source=(
                    embedding_result.usage_source
                    if embedding_result is not None
                    else None
                ),
                embedding_attempts=(
                    embedding_result.attempts if embedding_result is not None else 0
                ),
                embedding_retry_count=(
                    embedding_result.retry_count
                    if embedding_result is not None
                    else 0
                ),
                provider_name=(
                    embedding_result.provider_name
                    if embedding_result is not None
                    else None
                ),
                embedding_model=(
                    embedding_result.model_name
                    if embedding_result is not None
                    else None
                ),
            )
            serialized_traces = serialized_boundary_traces(traces)
            logger.info(
                dumps_cache_decision_log(
                    {
                        "event": "cache_decision",
                        "request_id": str(request_id),
                        "decision": (
                            safety_result.decision
                            if safety_result is not None
                            else "SAFE"
                        ),
                        "outcome": "cache_reused",
                        "source": "cache",
                        "strategy": "C" if safety_result is not None else "B",
                        "similarity": candidate.similarity,
                        "candidate_traces": serialized_traces,
                        "latency_ms": response_metrics.total_latency_ms,
                        "llm_input_tokens": 0,
                        "llm_output_tokens": 0,
                    }
                )
            )
            return QueryResponse(
                answer=candidate.answer,
                source="cache",
                strategy="semantic",
                decision=(
                    safety_result.decision
                    if safety_result is not None
                    else "SAFE"
                ),
                similarity=candidate.similarity,
                selected_candidate_query_hash=candidate.query_hash,
                reason=(
                    safety_result.reason
                    if safety_result is not None
                    else "similarity_threshold_met"
                ),
                candidate_traces=serialized_traces,
                freshness_class=(
                    candidate.metadata.temporal_class
                    if candidate.metadata is not None
                    else None
                ),
                cache_control_reason=(
                    "fresh" if candidate.ttl_expires_at is not None else None
                ),
                metrics=response_metrics,
            )

        def candidate_freshness_fields(
            candidate: CacheCandidate,
        ) -> tuple[str, str]:
            temporal_class = (
                candidate.metadata.temporal_class
                if candidate.metadata is not None
                else "stable"
            )
            if candidate.ttl_expires_at is None:
                return temporal_class, "missing_expiration"
            return (
                temporal_class,
                evaluate_cache_control(
                    temporal_class,
                    candidate.ttl_expires_at,
                    policy=cache_policy,
                ).reason,
            )

        def trace_with_context(
            trace: CandidateTrace,
            candidate: CacheCandidate,
            order: int,
        ) -> CandidateTrace:
            temporal_class, cache_control_outcome = candidate_freshness_fields(
                candidate
            )
            return CandidateTrace(
                candidate_query_hash=trace.candidate_query_hash,
                similarity=trace.similarity,
                decision=trace.decision,
                reason=trace.reason,
                candidate_order=order,
                stage=trace.stage,
                query_metadata=processed.metadata.to_dict(),
                candidate_metadata=(
                    candidate.metadata.to_dict()
                    if candidate.metadata is not None
                    else {}
                ),
                freshness_class=temporal_class,
                cache_control_outcome=cache_control_outcome,
            )

        def exact_entry_boundary_trace(entry: CacheEntry) -> CandidateTrace:
            candidate = exact_candidate(entry)
            temporal_class, cache_control_outcome = candidate_freshness_fields(
                candidate
            )
            return CandidateTrace(
                candidate_query_hash=entry.query_hash,
                similarity=1.0,
                decision="SAFE",
                reason="exact_query_hash_match",
                candidate_order=1,
                stage="compatibility",
                query_metadata=processed.metadata.to_dict(),
                candidate_metadata=(
                    candidate.metadata.to_dict()
                    if candidate.metadata is not None
                    else {}
                ),
                freshness_class=temporal_class,  # type: ignore[arg-type]
                cache_control_outcome=cache_control_outcome,
            )

        def exact_candidate(entry: CacheEntry) -> CacheCandidate:
            return CacheCandidate(
                query_hash=entry.query_hash,
                normalized_query=entry.normalized_query,
                answer=entry.answer,
                similarity=1.0,
                embedding_model=entry.embedding_model or "",
                embedding_dimension=entry.embedding_dimension or 0,
                metadata=entry.metadata,
                ttl_expires_at=entry.ttl_expires_at,
                canonical_answer_hash=entry.canonical_answer_hash,
            )

        def evaluate_exact_entry(entry: CacheEntry) -> CandidateTrace:
            candidate = exact_candidate(entry)
            trace = evaluate_candidate_boundary(
                processed.metadata,
                candidate,
                similarity_threshold=semantic_similarity_threshold,
            )
            return trace_with_context(trace, candidate, 1)

        try:
            cached_entry = run_with_timeout(
                dependency_executor,
                lambda: cache.get_by_query_hash(processed.query_hash),
                dependency_budget(runtime_settings.repository_timeout_seconds),
                "cache lookup",
                dependency_slots,
            )
        except (CacheRepositoryError, DependencyTimeoutError) as exc:
            logger.warning(
                "cache unavailable request_id=%s",
                request_id,
            )
            raise HTTPException(
                status_code=503,
                detail="cache unavailable",
                headers={"X-Request-ID": str(request_id)},
            ) from exc
        if cached_entry is not None:
            exact_control = cache_control_for(cached_entry)
            if exact_control.reusable:
                if semantic_strategy == "C":
                    decision_traces = (evaluate_exact_entry(cached_entry),)
                    exact_safety = decision_traces[0]
                    if is_reusable_decision(exact_safety.decision):
                        return cached_response(
                            cached_entry,
                            decision=exact_safety.decision,
                            reason=exact_safety.reason,
                            traces=decision_traces,
                        )
                else:
                    return cached_response(cached_entry)
            else:
                decision_traces = (
                    build_cache_control_trace(
                        exact_candidate(cached_entry),
                        exact_control,
                        candidate_order=1,
                        query_metadata=processed.metadata.to_dict(),
                    ),
                )
                if reuse_block_reason is None:
                    reuse_block_reason = exact_control.reason

        embedding_result = None
        if semantic_enabled:
            try:
                embedding_result = run_with_timeout(
                    dependency_executor,
                    lambda: vector_client.embed(processed.normalized_query),
                    dependency_budget(runtime_settings.embedding_timeout_seconds),
                    "embedding",
                    dependency_slots,
                )
                if not hasattr(embedding_result, "vector"):
                    raise ValueError("embedding provider returned an invalid result")
                validate_embedding_result(
                    embedding_result,
                    vector_client.config,
                )
                search = getattr(cache, "search_by_embedding", None)
                if callable(search):
                    candidates = run_with_timeout(
                            dependency_executor,
                            lambda: search(
                                embedding_result.vector,
                                semantic_top_k,
                                embedding_model=embedding_result.model_name,
                            ),
                            dependency_budget(
                                runtime_settings.repository_timeout_seconds
                            ),
                            "semantic cache search",
                            dependency_slots,
                    )
                    reusable_candidates = tuple(
                        candidate
                        for candidate in candidates
                        if cache_entry_is_reusable(candidate)
                    )
                    if candidates and semantic_strategy == "C":
                        evaluated_candidates = candidates[:MAX_CANDIDATE_TRACES]
                        trace_rows: list[CandidateTrace] = []
                        for candidate in evaluated_candidates:
                            control = cache_control_for(candidate)
                            if control.reusable:
                                trace_rows.append(
                                    trace_with_context(
                                        evaluate_candidate_boundary(
                                            processed.metadata,
                                            candidate,
                                            similarity_threshold=(
                                                semantic_similarity_threshold
                                            ),
                                        ),
                                        candidate,
                                        1,
                                    )
                                )
                            else:
                                trace_rows.append(
                                    build_cache_control_trace(
                                        candidate,
                                        control,
                                        candidate_order=1,
                                        query_metadata=processed.metadata.to_dict(),
                                    )
                                )
                        decision_traces = merge_decision_traces(tuple(trace_rows))
                        safety_result = resolve_candidate_traces(
                            decision_traces,
                            strategy="C",
                        )
                        if is_reusable_decision(safety_result.decision):
                            selected = next(
                                (
                                    candidate
                                    for candidate in evaluated_candidates
                                    if candidate.query_hash
                                    == safety_result.selected_candidate_query_hash
                                ),
                                None,
                            )
                            if selected is None:
                                raise HTTPException(
                                    status_code=500,
                                    detail="cache decision unavailable",
                                    headers={"X-Request-ID": str(request_id)},
                                )
                            return semantic_cached_response(
                                selected,
                                safety_result,
                                traces=decision_traces,
                            )
                    elif (
                        reusable_candidates
                        and reusable_candidates[0].similarity
                        >= semantic_similarity_threshold
                    ):
                        freshness_class, cache_control_outcome = (
                            candidate_freshness_fields(reusable_candidates[0])
                        )
                        decision_traces = merge_decision_traces((
                            CandidateTrace(
                                candidate_query_hash=reusable_candidates[0].query_hash,
                                similarity=reusable_candidates[0].similarity,
                                decision="SAFE",
                                reason="similarity_threshold_met",
                                candidate_order=1,
                                stage="retrieval",
                                query_metadata=processed.metadata.to_dict(),
                                candidate_metadata=(
                                    reusable_candidates[0].metadata.to_dict()
                                    if reusable_candidates[0].metadata is not None
                                    else {}
                                ),
                                freshness_class=freshness_class,  # type: ignore[arg-type]
                                cache_control_outcome=cache_control_outcome,
                            ),
                        ))
                        return semantic_cached_response(
                            reusable_candidates[0],
                            traces=decision_traces,
                        )
                    elif reusable_candidates:
                        freshness_class, cache_control_outcome = (
                            candidate_freshness_fields(reusable_candidates[0])
                        )
                        decision_traces = merge_decision_traces((
                            CandidateTrace(
                                candidate_query_hash=reusable_candidates[0].query_hash,
                                similarity=reusable_candidates[0].similarity,
                                decision="UNSAFE",
                                reason="similarity_below_threshold",
                                candidate_order=1,
                                stage="retrieval",
                                query_metadata=processed.metadata.to_dict(),
                                candidate_metadata=(
                                    reusable_candidates[0].metadata.to_dict()
                                    if reusable_candidates[0].metadata is not None
                                    else {}
                                ),
                                freshness_class=freshness_class,  # type: ignore[arg-type]
                                cache_control_outcome=cache_control_outcome,
                            ),
                        ))
                        metrics.record_threshold_rejection()
                    elif candidates:
                        metrics.record_semantic_miss()
                    else:
                        metrics.record_semantic_miss()
            except HTTPException:
                raise
            except Exception as exc:
                embedding_result = None
                metrics.record_cache_rejection("semantic_lookup_unavailable")
                logger.warning(
                    "semantic lookup unavailable; generating response request_id=%s error_type=%s",
                    request_id,
                    type(exc).__name__,
                )

        metrics.record_miss()
        with generation_guard():
            # Recheck after waiting so concurrent requests do not generate the
            # same uncached query more than once in this process.
            try:
                cached_entry = run_with_timeout(
                    dependency_executor,
                    lambda: cache.get_by_query_hash(processed.query_hash),
                    dependency_budget(runtime_settings.repository_timeout_seconds),
                    "cache lookup",
                    dependency_slots,
                )
            except (CacheRepositoryError, DependencyTimeoutError) as exc:
                logger.warning(
                    "cache unavailable request_id=%s",
                    request_id,
                )
                raise HTTPException(
                    status_code=503,
                    detail="cache unavailable",
                    headers={"X-Request-ID": str(request_id)},
                ) from exc
            if cached_entry is not None:
                exact_control = cache_control_for(cached_entry)
                if exact_control.reusable:
                    if semantic_strategy != "C":
                        return cached_response(cached_entry)
                    exact_safety = evaluate_exact_entry(cached_entry)
                    decision_traces = merge_decision_traces((exact_safety,))
                    if is_reusable_decision(exact_safety.decision):
                        return cached_response(
                            cached_entry,
                            decision=exact_safety.decision,
                            reason=exact_safety.reason,
                            traces=decision_traces,
                        )
                else:
                    decision_traces = merge_decision_traces((
                        build_cache_control_trace(
                            exact_candidate(cached_entry),
                            exact_control,
                            candidate_order=1,
                            query_metadata=processed.metadata.to_dict(),
                        ),
                    ))
                    if reuse_block_reason is None:
                        reuse_block_reason = exact_control.reason

            try:
                result = run_with_timeout(
                    dependency_executor,
                    lambda: model_client.generate(processed.normalized_query),
                    dependency_budget(runtime_settings.generation_timeout_seconds),
                    "generation",
                    dependency_slots,
                )
                result = validate_llm_result(result)
            except Exception as exc:
                metrics.record_generation_failure()
                latency_ms = int((perf_counter() - started_at) * 1000)
                logger.info(
                    dumps_cache_decision_log(
                        {
                            "event": "cache_decision",
                            "request_id": str(request_id),
                            "decision": "UNCERTAIN",
                            "reason": "generation_failed",
                            "outcome": "generation_failed",
                            "source": "error",
                            "candidate_traces": None,
                            "latency_ms": latency_ms,
                            "llm_input_tokens": 0,
                            "llm_output_tokens": 0,
                        }
                    )
                )
                raise HTTPException(
                    status_code=502,
                    detail="response generation failed",
                    headers={"X-Request-ID": str(request_id)},
                ) from exc

            if embedding_result is None and semantic_enabled:
                try:
                    embedding_result = run_with_timeout(
                        dependency_executor,
                        lambda: vector_client.embed(processed.normalized_query),
                        dependency_budget(runtime_settings.embedding_timeout_seconds),
                        "embedding",
                        dependency_slots,
                    )
                    validate_embedding_result(
                        embedding_result,
                        vector_client.config,
                    )
                except Exception as exc:
                    # A generated answer remains usable for this response, but
                    # an answer without a valid embedding must not enter cache.
                    embedding_result = None
                    cache_skip_reason = "embedding_unavailable"
                    metrics.record_cache_rejection("embedding_unavailable")
                    logger.warning(
                        "embedding unavailable; skipping cache insert request_id=%s error_type=%s",
                        request_id,
                        type(exc).__name__,
                    )

            ttl = cache_policy.ttl_for(processed.metadata.temporal_class)
            if cache_skip_reason is None:
                if ttl is None:
                    cache_skip_reason = "dynamic_entries_disabled"
                else:
                    cache_skip_reason = cache_size_limits.rejection_reason(
                        answer=result.text,
                        normalized_query=processed.normalized_query,
                        metadata=processed.metadata,
                    )
            if (
                (embedding_result is not None or not semantic_enabled)
                and cache_skip_reason is None
            ):
                try:
                    entry = CacheEntry(
                        query_hash=processed.query_hash,
                        normalized_query=processed.normalized_query,
                        answer=result.text,
                        embedding=(
                            embedding_result.vector
                            if embedding_result is not None
                            else None
                        ),
                        embedding_model=(
                            embedding_result.model_name
                            if embedding_result is not None
                            else None
                        ),
                        embedding_dimension=(
                            len(embedding_result.vector)
                            if embedding_result is not None
                            else None
                        ),
                        metadata=processed.metadata,
                        ttl_expires_at=datetime.now(timezone.utc) + ttl,
                    )
                    insert_and_evict = getattr(cache, "insert_and_evict", None)
                    if callable(insert_and_evict):
                        run_with_timeout(
                            dependency_executor,
                            lambda: insert_and_evict(
                                entry,
                                max_cache_entries,
                                max_cache_bytes,
                            ),
                            dependency_budget(
                                runtime_settings.repository_timeout_seconds
                            ),
                            "cache insert and eviction",
                            dependency_slots,
                        )
                    else:
                        run_with_timeout(
                            dependency_executor,
                            lambda: cache.insert(entry),
                            dependency_budget(
                                runtime_settings.repository_timeout_seconds
                            ),
                            "cache insert",
                            dependency_slots,
                        )
                        evict = getattr(cache, "evict_to_limits", None)
                        if callable(evict):
                            try:
                                run_with_timeout(
                                    dependency_executor,
                                    lambda: evict(
                                        max_cache_entries,
                                        max_cache_bytes,
                                    ),
                                    dependency_budget(
                                        runtime_settings.repository_timeout_seconds
                                    ),
                                    "cache eviction",
                                    dependency_slots,
                                )
                            except (CacheRepositoryError, DependencyTimeoutError) as exc:
                                logger.warning(
                                    "cache eviction unavailable request_id=%s error_type=%s",
                                    request_id,
                                    type(exc).__name__,
                                )
                except DuplicateCacheEntryError:
                    # Another process may have filled a shared repository while
                    # this request was generating.
                    try:
                        cached_entry = run_with_timeout(
                            dependency_executor,
                            lambda: cache.get_by_query_hash(
                                processed.query_hash
                            ),
                            dependency_budget(
                                runtime_settings.repository_timeout_seconds
                            ),
                            "cache lookup",
                            dependency_slots,
                        )
                    except (CacheRepositoryError, DependencyTimeoutError) as exc:
                        raise HTTPException(
                            status_code=503,
                            detail="cache unavailable",
                            headers={"X-Request-ID": str(request_id)},
                        ) from exc
                    if cached_entry is None:
                        raise HTTPException(
                            status_code=503,
                            detail="cache write conflict",
                            headers={"X-Request-ID": str(request_id)},
                        )
                    duplicate_control = cache_control_for(cached_entry)
                    if duplicate_control.reusable:
                        if semantic_strategy != "C":
                            return cached_response(cached_entry)
                        duplicate_safety = evaluate_exact_entry(cached_entry)
                        decision_traces = merge_decision_traces((duplicate_safety,))
                        if is_reusable_decision(duplicate_safety.decision):
                            return cached_response(
                                cached_entry,
                                decision=duplicate_safety.decision,
                                reason=duplicate_safety.reason,
                                traces=decision_traces,
                            )
                    else:
                        decision_traces = merge_decision_traces((
                            build_cache_control_trace(
                                exact_candidate(cached_entry),
                                duplicate_control,
                                candidate_order=1,
                                query_metadata=processed.metadata.to_dict(),
                            ),
                        ))
                        delete_entry = getattr(
                            cache, "delete_by_query_hash", None
                        )
                        if callable(delete_entry):
                            try:
                                run_with_timeout(
                                    dependency_executor,
                                    lambda: delete_entry(processed.query_hash),
                                    dependency_budget(
                                        runtime_settings.repository_timeout_seconds
                                    ),
                                    "cache replacement",
                                    dependency_slots,
                                )
                                if callable(insert_and_evict):
                                    run_with_timeout(
                                        dependency_executor,
                                        lambda: insert_and_evict(
                                            entry,
                                            max_cache_entries,
                                            max_cache_bytes,
                                        ),
                                        dependency_budget(
                                            runtime_settings.repository_timeout_seconds
                                        ),
                                        "cache insert and eviction",
                                        dependency_slots,
                                    )
                                else:
                                    run_with_timeout(
                                        dependency_executor,
                                        lambda: cache.insert(entry),
                                        dependency_budget(
                                            runtime_settings.repository_timeout_seconds
                                        ),
                                        "cache insert",
                                        dependency_slots,
                                    )
                            except (
                                CacheRepositoryError,
                                DependencyTimeoutError,
                                DuplicateCacheEntryError,
                            ) as exc:
                                logger.warning(
                                    "cache replacement unavailable "
                                    "request_id=%s error_type=%s",
                                    request_id,
                                    type(exc).__name__,
                                )
                                cache_skip_reason = "cache_write_unavailable"
                except (CacheRepositoryError, DependencyTimeoutError) as exc:
                    logger.warning(
                        "cache write unavailable; returning generated response "
                        "request_id=%s error_type=%s",
                        request_id,
                        type(exc).__name__,
                    )
                    cache_skip_reason = "cache_write_unavailable"

            if cache_skip_reason is not None:
                metrics.record_cache_rejection(cache_skip_reason)

        response_metrics = metrics.snapshot(
            request_id=request_id,
            total_latency_ms=int((perf_counter() - started_at) * 1000),
            llm_latency_ms=result.latency_ms,
            llm_input_tokens=result.input_tokens,
            llm_output_tokens=result.output_tokens,
            llm_usage_source=result.usage_source,
            llm_attempts=result.attempts,
            llm_retry_count=result.retry_count,
            embedding_latency_ms=(
                embedding_result.latency_ms if embedding_result is not None else 0
            ),
            embedding_input_tokens=(
                embedding_result.input_tokens if embedding_result is not None else 0
            ),
            embedding_usage_source=(
                embedding_result.usage_source
                if embedding_result is not None
                else None
            ),
            embedding_attempts=(
                embedding_result.attempts if embedding_result is not None else 0
            ),
            embedding_retry_count=(
                embedding_result.retry_count
                if embedding_result is not None
                else 0
            ),
            provider_name=result.provider_name,
            generation_model=result.model_name,
            embedding_model=(
                embedding_result.model_name if embedding_result is not None else None
            ),
            **_cost_metric_fields(
                estimate_request_cost(
                    pricing_schedule,
                    generation_input_tokens=result.input_tokens,
                    generation_output_tokens=result.output_tokens,
                    embedding_input_tokens=(
                        embedding_result.input_tokens
                        if embedding_result is not None
                        else 0
                    ),
                    generation_retry_count=result.retry_count,
                    embedding_retry_count=(
                        embedding_result.retry_count
                        if embedding_result is not None
                        else 0
                    ),
                )
            ),
        )
        if decision_traces:
            fallback_safety = resolve_candidate_traces(
                decision_traces,
                strategy=logged_strategy(),
            )
            generated_decision = fallback_safety.decision
            generated_reason = fallback_safety.reason
        elif reuse_block_reason is not None:
            generated_decision = "UNCERTAIN"
            generated_reason = reuse_block_reason
        elif cache_skip_reason is not None:
            generated_decision = "UNCERTAIN"
            generated_reason = cache_skip_reason
        else:
            empty_result = resolve_candidate_traces(
                (),
                strategy=logged_strategy(),
            )
            generated_decision = empty_result.decision
            generated_reason = empty_result.reason

        serialized_traces = serialized_boundary_traces(decision_traces)
        logger.info(
            dumps_cache_decision_log(
                {
                    "event": "cache_decision",
                    "request_id": str(request_id),
                    "decision": generated_decision,
                    "reason": generated_reason,
                    "outcome": "generated",
                    "source": "generated",
                    "strategy": logged_strategy(),
                    "cache_skip_reason": cache_skip_reason,
                    "candidate_traces": serialized_traces,
                    "latency_ms": response_metrics.total_latency_ms,
                    "llm_input_tokens": result.input_tokens,
                    "llm_output_tokens": result.output_tokens,
                }
            )
        )
        return QueryResponse(
            answer=result.text,
            source="generated",
            strategy="generated",
            decision=generated_decision,
            reason=generated_reason,
            freshness_class=processed.metadata.temporal_class,
            cache_control_reason=(
                cache_skip_reason or reuse_block_reason or "fresh"
            ),
            candidate_traces=serialized_traces,
            metrics=response_metrics,
        )

    return app


app = create_app(settings=Settings.from_environment())
