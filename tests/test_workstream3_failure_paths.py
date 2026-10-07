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
    response = client.post("/v1/query", json={"query": "slow lookup"})
    assert response.status_code == 503
    assert response.json()["detail"] == "cache unavailable"


def test_repository_timeout_on_semantic_search_does_not_serve_cache() -> None:
    client = TestClient(
        create_app(
            repository=SlowSearchCache(embedding_dimension=2),
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="fake-embedding", dimension=2),
            ),
            settings=Settings(repository_timeout_seconds=1),
            semantic_strategy="C",
        )
    )
    response = client.post("/v1/query", json={"query": "slow semantic search"})
    assert response.status_code == 200
    assert response.json()["source"] == "generated"


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


def test_generation_failure_after_unsafe_candidate_is_non_reusable(caplog) -> None:
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
    caplog.set_level(logging.INFO, logger="sscre")
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
    response = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    )
    assert response.status_code == 502
    event = json.loads(
        next(
            record.message
            for record in caplog.records
            if "generation_failed" in record.message
        )
    )
    assert event["decision"] == "UNCERTAIN"
    assert event["reason"] == "generation_failed"
    assert event["candidate_traces"] is None


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
    second = client.post("/v1/query", json={"query": "transient lookup failure"})
    assert second.status_code == 200
    assert second.json()["source"] == "generated"


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
