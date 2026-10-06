import hashlib
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.config import Settings
from sscre.llm import LLMResult
from sscre.safety import QueryMetadata


def test_expired_exact_entry_is_not_reused() -> None:
    query = "What is caching?"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="expired answer",
            metadata=QueryMetadata(
                intent="factual",
                domain="unknown",
                output_format="prose",
            ),
            ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )

    response = TestClient(create_app(repository=cache)).post(
        "/v1/query",
        json={"query": query},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "generated"


def test_missing_ttl_metadata_is_not_reused() -> None:
    query = "missing expiration"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="unbounded answer",
            metadata=QueryMetadata(),
            ttl_expires_at=None,
        )
    )

    response = TestClient(create_app(repository=cache)).post(
        "/v1/query",
        json={"query": query},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "generated"


def test_generated_stable_entry_receives_configured_ttl() -> None:
    cache = InMemoryExactCache()
    settings = Settings(
        stable_ttl_seconds=60,
        semi_dynamic_ttl_seconds=30,
    )

    response = TestClient(create_app(repository=cache, settings=settings)).post(
        "/v1/query",
        json={"query": "What is caching?"},
    )

    assert response.status_code == 200
    assert response.json()["freshness_class"] == "stable"
    assert response.json()["cache_control_reason"] == "fresh"
    query_hash = hashlib.sha256(b"What is caching?").hexdigest()
    entry = cache.get_by_query_hash(query_hash)
    assert entry is not None
    assert entry.ttl_expires_at is not None
    assert entry.ttl_expires_at > datetime.now(timezone.utc)


def test_dynamic_entry_is_returned_but_not_cached() -> None:
    cache = InMemoryExactCache()

    response = TestClient(create_app(repository=cache)).post(
        "/v1/query",
        json={"query": "What is the current stock price now?"},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    query_hash = hashlib.sha256(
        b"What is the current stock price now?"
    ).hexdigest()
    assert cache.get_by_query_hash(query_hash) is None


def test_oversized_generated_answer_is_returned_but_not_cached() -> None:
    class LargeAnswerClient:
        def generate(self, query: str) -> LLMResult:
            return LLMResult(
                text="x" * 10,
                input_tokens=1,
                output_tokens=10,
                latency_ms=0,
            )

    cache = InMemoryExactCache()
    settings = Settings(max_answer_bytes=4)

    response = TestClient(
        create_app(
            llm_client=LargeAnswerClient(),
            repository=cache,
            settings=settings,
        )
    ).post("/v1/query", json={"query": "cache this answer"})

    assert response.status_code == 200
    assert response.json()["answer"] == "x" * 10
    assert response.json()["reason"] == "answer_too_large"
    assert cache.get_by_query_hash(
        hashlib.sha256(b"cache this answer").hexdigest()
    ) is None
