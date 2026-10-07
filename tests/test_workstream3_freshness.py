"""Workstream 3 step 3: freshness gate traces and failure-closed reuse."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.llm import MockLLMClient
from sscre.metadata import extract_metadata
from sscre.query import hash_query
from sscre.safety import QueryMetadata


class _CountingLLM(MockLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def generate(self, query: str):
        self.calls += 1
        return super().generate(query)


def _fresh_meta(**kwargs: object) -> QueryMetadata:
    base = dict(
        intent="code",
        domain="programming",
        entities=("binary search",),
        constraints=(("language", "python"),),
        output_format="code",
        temporal_class="stable",
    )
    base.update(kwargs)
    return QueryMetadata(**base)  # type: ignore[arg-type]


def test_fresh_semantic_hit_includes_freshness_fields_on_trace() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "write Python code for binary search"
    meta = _fresh_meta()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="compatible cached answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=meta,
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
    response = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    )
    body = response.json()
    assert body["source"] == "cache"
    trace = body["candidate_traces"][0]
    assert trace["stage"] == "compatibility"
    assert trace["cache_control_outcome"] == "fresh"
    assert trace["freshness_class"] == "stable"


def test_expired_exact_entry_emits_retrieval_trace_and_does_not_reuse() -> None:
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
    response = TestClient(
        create_app(repository=cache, semantic_strategy="C", semantic_enabled=False)
    ).post("/v1/query", json={"query": query})

    body = response.json()
    assert body["source"] == "generated"
    assert body["decision"] == "UNSAFE"
    trace = body["candidate_traces"][0]
    assert trace["stage"] == "retrieval"
    assert trace["decision"] == "UNSAFE"
    assert trace["reason"] == "cache_control_expired"
    assert trace["cache_control_outcome"] == "expired"
    assert body["answer"] != "expired answer"


def test_stale_compatible_metadata_does_not_become_safe() -> None:
    query = "Write Python code for binary search"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hash_query(query),
            normalized_query=query,
            answer="expired but compatible text",
            metadata=extract_metadata(query),
            ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    response = TestClient(
        create_app(repository=cache, semantic_strategy="C", semantic_enabled=False)
    ).post("/v1/query", json={"query": query})

    body = response.json()
    assert body["decision"] == "UNSAFE"
    assert body["candidate_traces"][0]["reason"] == "cache_control_expired"
    assert body["selected_candidate_query_hash"] is None


def test_fresh_incompatible_semantic_candidate_stays_non_reusable() -> None:
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
            metadata=_fresh_meta(
                entities=("binary search", "java"),
                constraints=(("language", "java"),),
            ),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    model = _CountingLLM()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"implement Python binary search": (1.0, 0.0)},
            ),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )
    response = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    )
    body = response.json()
    assert body["source"] == "generated"
    assert body["decision"] == "UNSAFE"
    trace = body["candidate_traces"][0]
    assert trace["cache_control_outcome"] == "fresh"
    assert trace["reason"] == "constraint_mismatch:language"
    assert model.calls == 1


def test_semantic_expired_candidate_traced_before_generation() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "explain vector search"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="stale semantic answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=QueryMetadata(),
            ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"new wording for vector search": (1.0, 0.0)},
            ),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )
    response = client.post(
        "/v1/query",
        json={"query": "new wording for vector search"},
    )
    body = response.json()
    assert body["source"] == "generated"
    assert body["candidate_traces"][0]["reason"] == "cache_control_expired"


def test_dynamic_exact_entry_emits_dynamic_disabled_trace() -> None:
    query = "What is the current stock price?"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="stale price answer",
            metadata=QueryMetadata(
                intent="factual",
                domain="finance",
                temporal_class="dynamic",
            ),
        )
    )
    response = TestClient(
        create_app(
            repository=cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    ).post("/v1/query", json={"query": query})

    body = response.json()
    assert body["source"] == "generated"
    assert body["decision"] == "UNSAFE"
    trace = body["candidate_traces"][0]
    assert trace["reason"] == "cache_control_dynamic_disabled"
    assert trace["cache_control_outcome"] == "dynamic_entries_disabled"


def test_missing_ttl_emits_missing_expiration_trace() -> None:
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
    response = TestClient(
        create_app(repository=cache, semantic_strategy="C", semantic_enabled=False)
    ).post("/v1/query", json={"query": query})

    body = response.json()
    assert body["source"] == "generated"
    assert body["decision"] == "UNCERTAIN"
    trace = body["candidate_traces"][0]
    assert trace["reason"] == "cache_control_missing_expiration"
    assert trace["cache_control_outcome"] == "missing_expiration"


def test_invalid_ttl_emits_invalid_expiration_trace() -> None:
    query = "invalid expiration"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="bad ttl answer",
            metadata=QueryMetadata(),
            ttl_expires_at=datetime(2026, 1, 1),
        )
    )
    response = TestClient(
        create_app(repository=cache, semantic_strategy="C", semantic_enabled=False)
    ).post("/v1/query", json={"query": query})

    body = response.json()
    assert body["decision"] == "UNCERTAIN"
    trace = body["candidate_traces"][0]
    assert trace["reason"] == "cache_control_invalid_expiration"
    assert trace["cache_control_outcome"] == "invalid_expiration"


def test_expired_exact_trace_is_kept_beside_a_fresh_semantic_candidate() -> None:
    request = "implement Python binary search"
    neighbor = "write Python code for binary search"
    cache = InMemoryExactCache(embedding_dimension=2)
    cache.insert(
        CacheEntry(
            query_hash=hash_query(request),
            normalized_query=request,
            answer="expired exact answer",
            metadata=extract_metadata(request),
            ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    cache.insert(
        CacheEntry(
            query_hash=hash_query(neighbor),
            normalized_query=neighbor,
            answer="fresh semantic answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=extract_metadata(neighbor),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    response = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={request: (1.0, 0.0)},
            ),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    ).post("/v1/query", json={"query": request})

    body = response.json()
    assert body["source"] == "cache"
    assert body["answer"] == "fresh semantic answer"
    assert body["decision"] == "SAFE"
    assert [trace["reason"] for trace in body["candidate_traces"]] == [
        "cache_control_expired",
        "compatible_metadata",
    ]
    assert body["candidate_traces"][0]["cache_control_outcome"] == "expired"
    assert body["candidate_traces"][1]["cache_control_outcome"] == "fresh"


def test_generated_log_uses_strategy_c_when_semantic_search_is_disabled(caplog) -> None:
    import json
    import logging

    caplog.set_level(logging.INFO, logger="sscre")
    response = TestClient(
        create_app(semantic_strategy="C", semantic_enabled=False)
    ).post("/v1/query", json={"query": "What is caching?"})

    assert response.status_code == 200
    logs = [
        json.loads(record.message)
        for record in caplog.records
        if record.message.startswith("{")
    ]
    assert logs[-1]["strategy"] == "C"
