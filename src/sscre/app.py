import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi import HTTPException

from sscre.cache_controls import evaluate_cache_control
from sscre.compatibility import evaluate_candidate
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
from sscre.llm import MockLLMClient
from sscre.metrics import MetricsCollector
from sscre.postgres_cache import PostgresExactCacheRepository
from sscre.query import QueryRequest, QueryResponse, preprocess_query
from sscre.safety import CandidateTrace, SafetyResult

logger = logging.getLogger("sscre")
MAX_TRACE_CANDIDATES = 100


def create_app(
    llm_client: MockLLMClient | None = None,
    repository: ExactCacheRepository | None = None,
    settings: Settings | None = None,
    embedding_client: EmbeddingClient | None = None,
    semantic_enabled: bool | None = None,
    semantic_strategy: str | None = None,
    semantic_top_k: int | None = None,
    semantic_similarity_threshold: float | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings.from_environment()
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
    metrics = MetricsCollector()
    generation_lock = Lock()

    def cache_entry_is_reusable(entry: CacheEntry | CacheCandidate) -> bool:
        # Rows loaded from storage without TTL metadata fail closed. New
        # in-memory entries receive a default TTL in CacheEntry.__post_init__.
        if entry.ttl_expires_at is None:
            return False
        return evaluate_cache_control(
            (
                entry.metadata.temporal_class
                if entry.metadata is not None
                else "stable"
            ),
            entry.ttl_expires_at,
            policy=cache_policy,
        ).reusable

    def record_cache_hit(query_hash: str) -> None:
        record_hit = getattr(cache, "record_hit", None)
        if callable(record_hit):
            try:
                record_hit(query_hash)
            except CacheRepositoryError:
                logger.warning(
                    "cache access accounting unavailable query_hash=%s",
                    query_hash,
                    exc_info=True,
                )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/cache/stats")
    def cache_stats() -> dict[str, object]:
        stats_method = getattr(cache, "storage_stats", None)
        if not callable(stats_method):
            raise HTTPException(
                status_code=503,
                detail="cache statistics unavailable",
            )
        try:
            stats = stats_method()
        except CacheRepositoryError as exc:
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

        def cached_response(
            entry: CacheEntry,
            *,
            decision: str = "EXACT_HIT",
            reason: str | None = None,
            traces: tuple[CandidateTrace, ...] = (),
        ) -> QueryResponse:
            record_cache_hit(entry.query_hash)
            metrics.record_exact_hit()
            response_metrics = metrics.snapshot(
                request_id=request_id,
                total_latency_ms=int((perf_counter() - started_at) * 1000),
            )
            logger.info(
                json.dumps(
                    {
                        "event": "cache_decision",
                        "request_id": str(request_id),
                        "decision": "HIT" if decision == "EXACT_HIT" else decision,
                        "safety_decision": decision,
                        "outcome": "cache_reused",
                        "source": "cache",
                        "strategy": "C" if traces else "A",
                        "candidate_traces": [
                            asdict(trace) for trace in traces
                        ],
                        "latency_ms": response_metrics.total_latency_ms,
                        "llm_input_tokens": 0,
                        "llm_output_tokens": 0,
                    },
                    sort_keys=True,
                )
            )
            return QueryResponse(
                answer=entry.answer,
                source="cache",
                strategy="exact",
                decision=decision,
                selected_candidate_query_hash=entry.query_hash,
                reason=reason,
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
            record_cache_hit(candidate.query_hash)
            metrics.record_semantic_hit()
            response_metrics = metrics.snapshot(
                request_id=request_id,
                total_latency_ms=int((perf_counter() - started_at) * 1000),
            )
            logger.info(
                json.dumps(
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
                        "candidate_traces": [
                            asdict(trace) for trace in traces
                        ],
                        "latency_ms": response_metrics.total_latency_ms,
                        "llm_input_tokens": 0,
                        "llm_output_tokens": 0,
                    },
                    sort_keys=True,
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

        def trace_with_context(
            trace: CandidateTrace,
            candidate: CacheCandidate,
            order: int,
        ) -> CandidateTrace:
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
            try:
                trace = evaluate_candidate(
                    processed.metadata,
                    candidate,
                    similarity_threshold=semantic_similarity_threshold,
                )
            except Exception:
                trace = CandidateTrace(
                    candidate_query_hash=candidate.query_hash,
                    similarity=candidate.similarity,
                    decision="UNCERTAIN",
                    reason="safety_validator_error",
                )
            return trace_with_context(trace, candidate, 1)

        try:
            cached_entry = cache.get_by_query_hash(processed.query_hash)
        except CacheRepositoryError as exc:
            logger.warning(
                "cache unavailable request_id=%s",
                request_id,
            )
            raise HTTPException(
                status_code=503,
                detail="cache unavailable",
                headers={"X-Request-ID": str(request_id)},
            ) from exc
        if cached_entry is not None and cache_entry_is_reusable(cached_entry):
            if semantic_strategy == "C":
                decision_traces = (evaluate_exact_entry(cached_entry),)
                exact_safety = decision_traces[0]
                if exact_safety.decision == "SAFE":
                    return cached_response(
                        cached_entry,
                        decision=exact_safety.decision,
                        reason=exact_safety.reason,
                        traces=decision_traces,
                    )
            else:
                return cached_response(cached_entry)

        embedding_result = None
        if semantic_enabled:
            try:
                embedding_result = vector_client.embed(
                    processed.normalized_query
                )
                validate_embedding_result(
                    embedding_result,
                    vector_client.config,
                )
                search = getattr(cache, "search_by_embedding", None)
                if callable(search):
                    candidates = search(
                        embedding_result.vector,
                        semantic_top_k,
                        embedding_model=embedding_result.model_name,
                    )
                    candidates = tuple(
                        candidate
                        for candidate in candidates
                        if cache_entry_is_reusable(candidate)
                    )
                    if candidates and semantic_strategy == "C":
                        evaluated_candidates = candidates[:MAX_TRACE_CANDIDATES]
                        traces = tuple(
                            trace_with_context(
                                evaluate_candidate(
                                    processed.metadata,
                                    candidate,
                                    similarity_threshold=(
                                        semantic_similarity_threshold
                                    ),
                                ),
                                candidate,
                                index + 1,
                            )
                            for index, candidate in enumerate(evaluated_candidates)
                        )
                        decision_traces = traces
                        safe_index = next(
                            (
                                index
                                for index, trace in enumerate(traces)
                                if trace.decision == "SAFE"
                            ),
                            None,
                        )
                        if safe_index is not None:
                            return semantic_cached_response(
                                candidates[safe_index],
                                SafetyResult(
                                    decision="SAFE",
                                    strategy="C",
                                    reason=traces[safe_index].reason,
                                    similarity=traces[safe_index].similarity,
                                    selected_candidate_query_hash=(
                                        traces[safe_index].candidate_query_hash
                                    ),
                                    candidate_traces=traces,
                                ),
                                traces=traces,
                            )
                    elif (
                        candidates
                        and candidates[0].similarity
                        >= semantic_similarity_threshold
                    ):
                        decision_traces = (
                            CandidateTrace(
                                candidate_query_hash=candidates[0].query_hash,
                                similarity=candidates[0].similarity,
                                decision="SAFE",
                                reason="similarity_threshold_met",
                                candidate_order=1,
                                stage="retrieval",
                                query_metadata=processed.metadata.to_dict(),
                                candidate_metadata=(
                                    candidates[0].metadata.to_dict()
                                    if candidates[0].metadata is not None
                                    else {}
                                ),
                            ),
                        )
                        return semantic_cached_response(
                            candidates[0],
                            traces=decision_traces,
                        )
                    elif candidates:
                        decision_traces = (
                            CandidateTrace(
                                candidate_query_hash=candidates[0].query_hash,
                                similarity=candidates[0].similarity,
                                decision="UNSAFE",
                                reason="similarity_below_threshold",
                                candidate_order=1,
                                stage="retrieval",
                                query_metadata=processed.metadata.to_dict(),
                                candidate_metadata=(
                                    candidates[0].metadata.to_dict()
                                    if candidates[0].metadata is not None
                                    else {}
                                ),
                            ),
                        )
                    if candidates:
                        metrics.record_threshold_rejection()
                    else:
                        metrics.record_semantic_miss()
            except Exception as exc:
                embedding_result = None
                logger.warning(
                    "semantic lookup unavailable; generating response request_id=%s",
                    request_id,
                    exc_info=exc,
                )

        metrics.record_miss()
        with generation_lock:
            # Recheck after waiting so concurrent requests do not generate the
            # same uncached query more than once in this process.
            try:
                cached_entry = cache.get_by_query_hash(processed.query_hash)
            except CacheRepositoryError as exc:
                logger.warning(
                    "cache unavailable request_id=%s",
                    request_id,
                )
                raise HTTPException(
                    status_code=503,
                    detail="cache unavailable",
                    headers={"X-Request-ID": str(request_id)},
                ) from exc
            if cached_entry is not None and cache_entry_is_reusable(cached_entry):
                if semantic_strategy != "C":
                    return cached_response(cached_entry)
                exact_safety = evaluate_exact_entry(cached_entry)
                decision_traces = (exact_safety,)
                if exact_safety.decision == "SAFE":
                    return cached_response(
                        cached_entry,
                        decision=exact_safety.decision,
                        reason=exact_safety.reason,
                        traces=decision_traces,
                    )

            try:
                result = model_client.generate(processed.normalized_query)
            except Exception as exc:
                metrics.record_generation_failure()
                latency_ms = int((perf_counter() - started_at) * 1000)
                logger.info(
                    json.dumps(
                        {
                            "event": "cache_decision",
                            "request_id": str(request_id),
                            "decision": "GENERATION_FAILED",
                            "source": "error",
                            "latency_ms": latency_ms,
                            "llm_input_tokens": 0,
                            "llm_output_tokens": 0,
                        },
                        sort_keys=True,
                    )
                )
                raise HTTPException(
                    status_code=502,
                    detail="response generation failed",
                    headers={"X-Request-ID": str(request_id)},
                ) from exc

            if embedding_result is None and semantic_enabled:
                try:
                    embedding_result = vector_client.embed(
                        processed.normalized_query
                    )
                    validate_embedding_result(
                        embedding_result,
                        vector_client.config,
                    )
                except Exception as exc:
                    # A generated answer remains usable for this response, but
                    # an answer without a valid embedding must not enter cache.
                    embedding_result = None
                    logger.warning(
                        "embedding unavailable; skipping cache insert request_id=%s",
                        request_id,
                        exc_info=exc,
                    )

            ttl = cache_policy.ttl_for(processed.metadata.temporal_class)
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
                        insert_and_evict(
                            entry,
                            max_cache_entries,
                            max_cache_bytes,
                        )
                    else:
                        cache.insert(entry)
                        evict = getattr(cache, "evict_to_limits", None)
                        if callable(evict):
                            try:
                                evict(max_cache_entries, max_cache_bytes)
                            except CacheRepositoryError:
                                logger.warning(
                                    "cache eviction unavailable request_id=%s",
                                    request_id,
                                    exc_info=True,
                                )
                except DuplicateCacheEntryError:
                    # Another process may have filled a shared repository while
                    # this request was generating.
                    try:
                        cached_entry = cache.get_by_query_hash(
                            processed.query_hash
                        )
                    except CacheRepositoryError as exc:
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
                    if (
                        semantic_strategy != "C"
                        and cache_entry_is_reusable(cached_entry)
                    ):
                        return cached_response(cached_entry)
                    duplicate_safety = evaluate_exact_entry(cached_entry)
                    if duplicate_safety.decision == "SAFE":
                        return cached_response(
                            cached_entry,
                            decision=duplicate_safety.decision,
                            reason=duplicate_safety.reason,
                            traces=(duplicate_safety,),
                        )
                except CacheRepositoryError as exc:
                    logger.warning(
                        "cache unavailable request_id=%s",
                        request_id,
                    )
                    raise HTTPException(
                        status_code=503,
                        detail="cache unavailable",
                        headers={"X-Request-ID": str(request_id)},
                    ) from exc

            if cache_skip_reason is not None:
                metrics.record_cache_rejection(cache_skip_reason)

        response_metrics = metrics.snapshot(
            request_id=request_id,
            total_latency_ms=int((perf_counter() - started_at) * 1000),
            llm_latency_ms=result.latency_ms,
            llm_input_tokens=result.input_tokens,
            llm_output_tokens=result.output_tokens,
        )
        logger.info(
            json.dumps(
                {
                    "event": "cache_decision",
                    "request_id": str(request_id),
                    "decision": "GENERATED",
                        "outcome": "generated",
                    "source": "generated",
                        "strategy": semantic_strategy if semantic_enabled else "A",
                    "cache_skip_reason": cache_skip_reason,
                        "candidate_traces": [
                            asdict(trace) for trace in decision_traces
                        ],
                    "latency_ms": response_metrics.total_latency_ms,
                    "llm_input_tokens": result.input_tokens,
                    "llm_output_tokens": result.output_tokens,
                },
                sort_keys=True,
            )
        )
        return QueryResponse(
            answer=result.text,
            source="generated",
            strategy="generated",
            decision="UNCERTAIN",
            reason=(
                cache_skip_reason
                or "cache candidate was not safely reusable"
            ),
            freshness_class=processed.metadata.temporal_class,
            cache_control_reason=cache_skip_reason or "fresh",
            metrics=response_metrics,
        )

    return app


app = create_app(settings=Settings.from_environment())
