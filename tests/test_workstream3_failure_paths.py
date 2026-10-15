"""Workstream 3 step 6: dependency and validator failure-closed behavior."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

try:
    from fastapi.testclient import TestClient
    from sscre.app import create_app
except ImportError:  # pragma: no cover
    pytest.skip(
        "sscre.app unavailable in this environment",
        allow_module_level=True,
    )

from sscre.cache import (
    CacheEntry,
    CacheRepositoryError,
    DuplicateCacheEntryError,
    InMemoryExactCache,
)
from sscre.compatibility import evaluate_candidate_boundary
from sscre.config import Settings
from sscre.embedding import (
    EmbeddingConfig,
    EmbeddingResult,
    FakeEmbeddingClient,
)
from sscre.llm import LLMResult, MockLLMClient
from sscre.safety import CandidateTrace, QueryMetadata


_SENSITIVE_MARKERS = (
    "sk-test-SECRETVALUE",
    "provider-payload-leak",
    "raw-query-leak-phrase",
    "cached-answer-leak",
    "embedding-vector-leak",
)


def _assert_controlled_error_response(
    response,
    *,
    status_code: int,
    detail: str,
    sensitive_query: str | None = None,
) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert body == {"detail": detail}
    assert response.headers.get("X-Request-ID")
    encoded = json.dumps(body)
    for marker in _SENSITIVE_MARKERS:
        assert marker not in encoded
    if sensitive_query is not None:
        assert sensitive_query not in encoded


def _python_meta() -> QueryMetadata:
    return QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", "python"),
        constraints=(("language", "python"),),
        output_format="code",
    )


class WrongDimensionEmbeddingClient:
    config = EmbeddingConfig(model_name="test-embedding", dimension=2)

    def embed(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=(1.0, 0.0, 0.5),
            model_name="test-embedding",
            input_tokens=1,
            latency_ms=0,
        )


class NonFiniteEmbeddingClient:
    config = EmbeddingConfig(model_name="test-embedding", dimension=2)

    def embed(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=(float("inf"), 0.0),
            model_name="test-embedding",
            input_tokens=1,
            latency_ms=0,
        )


class MalformedShapeEmbeddingClient:
    config = EmbeddingConfig(model_name="test-embedding", dimension=2)

    def embed(self, text: str) -> object:
        return object()


class SearchFailingCache(InMemoryExactCache):
    def search_by_embedding(self, *args, **kwargs):
        raise CacheRepositoryError("semantic search unavailable")


class SlowSearchCache(InMemoryExactCache):
    def search_by_embedding(self, *args, **kwargs):
        time.sleep(1.1)
        return super().search_by_embedding(*args, **kwargs)


class FailOnceLookupCache(InMemoryExactCache):
    def __init__(self) -> None:
        super().__init__()
        self._fail_remaining = 1

    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        if self._fail_remaining:
            self._fail_remaining -= 1
            raise CacheRepositoryError("temporary lookup failure")
        return super().get_by_query_hash(query_hash)


class WriteFailCache:
    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        return None

    def insert(self, entry: CacheEntry) -> None:
        raise CacheRepositoryError("write unavailable")


class SlowInsertCache(InMemoryExactCache):
    def insert_and_evict(self, entry: CacheEntry, *args, **kwargs) -> None:
        time.sleep(1.1)
        super().insert_and_evict(entry, *args, **kwargs)


class SlowRecordHitCache(InMemoryExactCache):
    def record_hit(self, query_hash: str, **kwargs) -> None:
        time.sleep(1.1)
        super().record_hit(query_hash, **kwargs)


class SlowEmbeddingClient:
    def __init__(self, delay_seconds: float = 1.1) -> None:
        self._delay_seconds = delay_seconds
        self._inner = FakeEmbeddingClient(
            config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        )

    @property
    def config(self) -> EmbeddingConfig:
        return self._inner.config

    def embed(self, text: str) -> EmbeddingResult:
        time.sleep(self._delay_seconds)
        return self._inner.embed(text)


def test_embedding_failure_after_exact_miss_generates_without_cache() -> None:
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(should_fail=True),
            semantic_strategy="C",
        )
    )
    response = client.post("/v1/query", json={"query": "no exact entry yet"})
    body = response.json()
    assert response.status_code == 200
    assert body["source"] == "generated"
    assert body["reason"] == "embedding_unavailable"
    assert cache.storage_stats().entries == 0


@pytest.mark.parametrize(
    "client_factory",
    [
        MalformedShapeEmbeddingClient,
        WrongDimensionEmbeddingClient,
        NonFiniteEmbeddingClient,
    ],
    ids=["malformed-shape", "wrong-dimension", "non-finite"],
)
def test_invalid_embedding_results_do_not_create_cache_hits(
    client_factory: type,
) -> None:
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=client_factory(),
            semantic_strategy="C",
        )
    )
    response = client.post("/v1/query", json={"query": "embedding validation"})
    body = response.json()
    assert response.status_code == 200
    assert body["source"] == "generated"
    assert body["reason"] == "embedding_unavailable"
    assert cache.storage_stats().entries == 0


def test_semantic_repository_search_failure_fails_closed(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="sscre")
    client = TestClient(
        create_app(
            repository=SearchFailingCache(embedding_dimension=2),
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="fake-embedding", dimension=2),
            ),
            semantic_strategy="C",
        )
    )
    response = client.post("/v1/query", json={"query": "semantic search failure"})
    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    warning = next(
        record.message
        for record in caplog.records
        if "semantic lookup unavailable" in record.message
    )
    assert "error_type=" in warning
    assert "Traceback" not in warning


def test_repository_timeout_on_lookup_returns_503() -> None:
    class SlowLookupCache(InMemoryExactCache):
        def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
            time.sleep(1.1)
            return super().get_by_query_hash(query_hash)

    client = TestClient(
        create_app(
            repository=SlowLookupCache(),
            settings=Settings(repository_timeout_seconds=1),
        )
    )
    sensitive_query = "slow lookup raw-query-leak-phrase"
    response = client.post("/v1/query", json={"query": sensitive_query})
    _assert_controlled_error_response(
        response,
        status_code=503,
        detail="cache unavailable",
        sensitive_query=sensitive_query,
    )


def test_repository_timeout_on_semantic_search_does_not_serve_cache() -> None:
    import hashlib

    cached_answer = "cached-answer-leak semantic neighbor"
    cache = SlowSearchCache(embedding_dimension=2)
    neighbor_query = "write Python code for binary search"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(neighbor_query.encode()).hexdigest(),
            normalized_query=neighbor_query,
            answer=cached_answer,
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=_python_meta(),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"implement Python binary search": (1.0, 0.0)},
            ),
            settings=Settings(repository_timeout_seconds=1),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )
    response = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["source"] == "generated"
    assert body["answer"] != cached_answer
    assert cached_answer not in json.dumps(body)


def test_embedding_timeout_generates_without_cache_entry() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=SlowEmbeddingClient(),
            settings=Settings(embedding_timeout_seconds=1),
            semantic_strategy="C",
        )
    )
    response = client.post(
        "/v1/query",
        json={"query": "embedding timeout raw-query-leak-phrase"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["source"] == "generated"
    assert body["reason"] == "embedding_unavailable"
    assert cache.storage_stats().entries == 0


def test_cache_insert_timeout_returns_generated_without_false_hit() -> None:
    client = TestClient(
        create_app(
            repository=SlowInsertCache(),
            settings=Settings(repository_timeout_seconds=1),
            semantic_enabled=False,
        )
    )
    response = client.post("/v1/query", json={"query": "slow cache insert"})
    body = response.json()
    assert response.status_code == 200
    assert body["source"] == "generated"
    assert body["reason"] == "cache_write_unavailable"
    assert body["decision"] == "UNCERTAIN"


def test_cache_replacement_timeout_does_not_serve_expired_duplicate() -> None:
    import hashlib

    query = "write Python code for replacement timeout"
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    expired_entry = CacheEntry(
        query_hash=query_hash,
        normalized_query=query,
        answer="expired raced answer cached-answer-leak",
        metadata=_python_meta(),
        ttl_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    class SlowReplacementCache(InMemoryExactCache):
        def __init__(self) -> None:
            super().__init__()
            self._duplicate_raised = False

        def insert_and_evict(self, entry: CacheEntry, *args, **kwargs) -> None:
            if not self._duplicate_raised:
                self._duplicate_raised = True
                raise DuplicateCacheEntryError("concurrent insert")
            super().insert_and_evict(entry, *args, **kwargs)

        def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
            if query_hash == expired_entry.query_hash:
                return expired_entry
            return super().get_by_query_hash(query_hash)

        def delete_by_query_hash(self, query_hash: str, **kwargs) -> None:
            time.sleep(1.1)
            super().delete_by_query_hash(query_hash, **kwargs)

    client = TestClient(
        create_app(
            repository=SlowReplacementCache(),
            settings=Settings(repository_timeout_seconds=1),
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )
    body = client.post("/v1/query", json={"query": query}).json()
    assert body["source"] == "generated"
    assert body["answer"] != expired_entry.answer
    assert body["decision"] == "UNSAFE"
    assert body["candidate_traces"][0]["reason"] == "cache_control_expired"


def test_cache_hit_accounting_timeout_still_serves_validated_entry() -> None:
    import hashlib

    query = "write Python code for binary search"
    cache = SlowRecordHitCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="validated exact answer",
            metadata=_python_meta(),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            settings=Settings(repository_timeout_seconds=1),
            semantic_enabled=False,
        )
    )
    body = client.post("/v1/query", json={"query": query}).json()
    assert body["source"] == "cache"
    assert body["answer"] == "validated exact answer"


def test_evaluator_exception_maps_to_safety_validator_error() -> None:
    @dataclass
    class StubCandidate:
        query_hash: str = "candidate-1"
        similarity: float = 0.99
        metadata: QueryMetadata | None = None

    with patch(
        "sscre.compatibility.evaluate_candidate",
        side_effect=RuntimeError("internal validator failure"),
    ):
        trace = evaluate_candidate_boundary(
            _python_meta(),
            StubCandidate(metadata=_python_meta()),  # type: ignore[arg-type]
            similarity_threshold=0.9,
        )
    assert trace.decision == "UNCERTAIN"
    assert trace.reason == "safety_validator_error"


def test_evaluator_failure_at_app_boundary_generates_without_cache_hit() -> None:
    import hashlib

    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "write Python code for binary search"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="should not be served",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=_python_meta(),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"implement Python binary search": (1.0, 0.0)},
            ),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )
    with patch(
        "sscre.compatibility.evaluate_candidate",
        side_effect=RuntimeError("validator exploded"),
    ):
        body = client.post(
            "/v1/query",
            json={"query": "implement Python binary search"},
        ).json()
    assert body["source"] == "generated"
    assert body["decision"] == "UNCERTAIN"
    assert body["answer"] != "should not be served"


def test_oversized_trace_metadata_prevents_cache_reuse() -> None:
    import hashlib

    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "write Python code for binary search"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="should not be served",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=_python_meta(),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"implement Python binary search": (1.0, 0.0)},
            ),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        ),
        raise_server_exceptions=False,
    )
    with patch(
        "sscre.app.boundary_candidate_traces",
        side_effect=ValueError("serialized candidate_traces exceed boundary size limit"),
    ):
        response = client.post(
            "/v1/query",
            json={"query": "implement Python binary search"},
        )
    assert response.status_code == 500
    assert response.headers["x-request-id"]


def test_generation_failure_after_unsafe_candidate_is_non_reusable() -> None:
    import hashlib

    class SlowLLM(MockLLMClient):
        def generate(self, query: str) -> LLMResult:
            time.sleep(1.1)
            return super().generate(query)

    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "write Java code for binary search"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="Java cached answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=QueryMetadata(
                intent="code",
                domain="programming",
                constraints=(("language", "java"),),
                output_format="code",
            ),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            llm_client=SlowLLM(),
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"implement Python binary search": (1.0, 0.0)},
            ),
            settings=Settings(generation_timeout_seconds=1),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )
    sensitive_query = "implement Python binary search raw-query-leak-phrase"
    response = client.post(
        "/v1/query",
        json={"query": sensitive_query},
    )
    _assert_controlled_error_response(
        response,
        status_code=504,
        detail="response generation timed out",
        sensitive_query=sensitive_query,
    )


def test_cache_write_failure_returns_generated_answer_without_false_hit() -> None:
    client = TestClient(create_app(repository=WriteFailCache()))
    body = client.post("/v1/query", json={"query": "write outage"}).json()
    assert body["source"] == "generated"
    assert body["reason"] == "cache_write_unavailable"
    assert body["decision"] == "UNCERTAIN"


def test_repository_recovers_after_transient_lookup_failure() -> None:
    cache = FailOnceLookupCache()
    client = TestClient(create_app(repository=cache))
    first = client.post("/v1/query", json={"query": "transient lookup failure"})
    assert first.status_code == 503
    assert first.headers.get("X-Request-ID")
    second = client.post("/v1/query", json={"query": "transient lookup failure"})
    assert second.status_code == 200
    assert second.json()["source"] == "generated"


def test_repository_recovers_after_lookup_timeout() -> None:
    class TimeoutThenFastLookup(InMemoryExactCache):
        def __init__(self) -> None:
            super().__init__()
            self._slow_remaining = 1

        def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
            if self._slow_remaining:
                self._slow_remaining -= 1
                time.sleep(1.1)
            return super().get_by_query_hash(query_hash)

    client = TestClient(
        create_app(
            repository=TimeoutThenFastLookup(),
            settings=Settings(repository_timeout_seconds=1),
            semantic_enabled=False,
        )
    )
    timed_out = client.post("/v1/query", json={"query": "lookup timeout recovery"})
    assert timed_out.status_code == 503
    assert timed_out.headers.get("X-Request-ID")
    recovered = client.post("/v1/query", json={"query": "lookup timeout recovery"})
    assert recovered.status_code == 200
    assert recovered.json()["source"] == "generated"


def test_dependency_warning_logs_use_bounded_fields_not_payloads(caplog) -> None:
    caplog.set_level(logging.WARNING, logger="sscre")
    client = TestClient(
        create_app(
            repository=SearchFailingCache(embedding_dimension=2),
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="fake-embedding", dimension=2),
            ),
        )
    )
    client.post("/v1/query", json={"query": "secret prompt text"})
    warning = next(
        record.message
        for record in caplog.records
        if "semantic lookup unavailable" in record.message
    )
    assert "secret prompt text" not in warning
    assert "error_type=" in warning
