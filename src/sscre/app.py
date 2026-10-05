import json
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi import HTTPException

from sscre.cache import CacheEntry, ExactCacheRepository, InMemoryExactCache
from sscre.config import Settings
from sscre.llm import MockLLMClient
from sscre.metrics import MetricsCollector
from sscre.postgres_cache import PostgresExactCacheRepository
from sscre.query import QueryRequest, QueryResponse, preprocess_query

logger = logging.getLogger("sscre")


def create_app(
    llm_client: MockLLMClient | None = None,
    repository: ExactCacheRepository | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app = FastAPI(title="SSCRE")
    if repository is not None:
        cache = repository
    elif settings is not None and settings.database_url:
        cache = PostgresExactCacheRepository(settings.database_url)
    else:
        cache = InMemoryExactCache()
    model_client = llm_client or MockLLMClient()
    metrics = MetricsCollector()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/query", response_model=QueryResponse)
    def query(request: QueryRequest) -> QueryResponse:
        request_id = uuid4()
        started_at = perf_counter()
        processed = preprocess_query(request)
        cached_entry = cache.get_by_query_hash(processed.query_hash)
        if cached_entry is not None:
            metrics.record_hit()
            response_metrics = metrics.snapshot(
                request_id=request_id,
                total_latency_ms=int((perf_counter() - started_at) * 1000),
            )
            logger.info(
                json.dumps(
                    {
                        "event": "cache_decision",
                        "request_id": str(request_id),
                        "decision": "HIT",
                        "source": "cache",
                        "latency_ms": response_metrics.total_latency_ms,
                        "llm_input_tokens": 0,
                        "llm_output_tokens": 0,
                    },
                    sort_keys=True,
                )
            )
            return QueryResponse(
                answer=cached_entry.answer,
                source="cache",
                metrics=response_metrics,
            )

        metrics.record_miss()
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
                    },
                    sort_keys=True,
                )
            )
            raise HTTPException(
                status_code=502,
                detail="response generation failed",
            ) from exc

        cache.insert(
            CacheEntry(
                query_hash=processed.query_hash,
                normalized_query=processed.normalized_query,
                answer=result.text,
            )
        )
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
                    "source": "generated",
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
            metrics=response_metrics,
        )

    return app


app = create_app(settings=Settings.from_environment())
