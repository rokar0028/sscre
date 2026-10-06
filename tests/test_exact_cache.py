import hashlib
import json
import logging
import time

import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import (
    CacheEntry,
    CacheRepositoryError,
    DuplicateCacheEntryError,
    InMemoryExactCache,
)
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.config import Settings
from sscre.llm import LLMResult, MockLLMClient
from sscre.safety import QueryMetadata


def test_cache_get_and_put() -> None:
    cache = InMemoryExactCache()
    entry = CacheEntry(
        query_hash="hash",
        normalized_query="What is caching?",
        answer="A technique for reusing results.",
    )

    assert cache.get("hash") is None
    cache.put(entry)
    assert cache.get("hash") == entry


def test_duplicate_query_hash_is_rejected() -> None:
    cache = InMemoryExactCache()
    entry = CacheEntry(
        query_hash="hash",
        normalized_query="What is caching?",
        answer="A technique for reusing results.",
    )
    cache.insert(entry)

    with pytest.raises(DuplicateCacheEntryError):
        cache.insert(entry)


def test_first_query_generates_and_repeated_query_uses_cache() -> None:
    model = CountingMockLLMClient()
    client = TestClient(create_app(model))

    first = client.post(
        "/v1/query",
        json={"query": "  Write Python code for binary search  "},
    )
    second = client.post(
        "/v1/query",
        json={"query": "Write   Python code for binary search"},
    )

    assert first.status_code == 200
    assert first.json()["source"] == "generated"
    assert second.status_code == 200
    assert second.json()["source"] == "cache"
    assert second.json()["answer"] == first.json()["answer"]
    assert model.calls == 1


def test_application_instances_have_isolated_caches() -> None:
    first_client = TestClient(create_app())
    second_client = TestClient(create_app())

    first = first_client.post("/v1/query", json={"query": "isolated query"})
    second = second_client.post("/v1/query", json={"query": "isolated query"})

    assert first.json()["source"] == "generated"
    assert second.json()["source"] == "generated"


def test_different_queries_do_not_collide() -> None:
    client = TestClient(create_app())

    first = client.post("/v1/query", json={"query": "What is caching?"})
    second = client.post("/v1/query", json={"query": "What is hashing?"})

    assert first.json()["source"] == "generated"
    assert second.json()["source"] == "generated"
    assert second.json()["answer"] != first.json()["answer"]


def test_generated_entry_stores_embedding_metadata() -> None:
    cache = InMemoryExactCache()
    query = "store an embedding"
    client = TestClient(create_app(repository=cache))

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 200
    entry = cache.get_by_query_hash(hashlib.sha256(query.encode()).hexdigest())
    assert entry is not None
    assert entry.embedding is not None
    assert entry.embedding_model == "fake-embedding"
    assert entry.embedding_dimension == len(entry.embedding)


def test_embedding_failure_does_not_cache_generated_answer() -> None:
    cache = InMemoryExactCache()
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        should_fail=True,
    )
    query = "do not cache without embedding"
    client = TestClient(
        create_app(repository=cache, embedding_client=embedding_client)
    )

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert cache.get_by_query_hash(hashlib.sha256(query.encode()).hexdigest()) is None


def test_semantic_candidate_is_reused_after_exact_miss() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "explain vector search"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="cached semantic answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
        )
    )
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={"new wording for vector search": (1.0, 0.0)},
    )
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            embedding_client=embedding_client,
            semantic_strategy="B",
            semantic_similarity_threshold=0.9,
        )
    )

    response = client.post(
        "/v1/query",
        json={"query": "new wording for vector search"},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "cache"
    assert response.json()["answer"] == "cached semantic answer"
    assert model.calls == 0


def test_default_strategy_does_not_reuse_metadata_less_semantic_candidate() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "explain vector search"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="cached semantic answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
        )
    )
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"new wording for vector search": (1.0, 0.0)},
            ),
            semantic_similarity_threshold=0.9,
        )
    )

    response = client.post(
        "/v1/query",
        json={"query": "new wording for vector search"},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert response.json()["decision"] == "UNCERTAIN"
    assert response.json()["answer"] != "cached semantic answer"
    assert model.calls == 1


def test_exact_hit_bypasses_embedding_lookup() -> None:
    cache = InMemoryExactCache()
    query = "exact query"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="exact answer",
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(should_fail=True),
            semantic_strategy="B",
        )
    )

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 200
    assert response.json()["source"] == "cache"
    assert response.json()["answer"] == "exact answer"


def test_semantic_candidate_below_threshold_generates_response() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "cached query"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="old answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
        )
    )
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={"different query": (0.0, 1.0)},
    )
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            embedding_client=embedding_client,
            semantic_strategy="B",
            semantic_similarity_threshold=0.9,
        )
    )

    response = client.post("/v1/query", json={"query": "different query"})

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert response.json()["metrics"]["threshold_rejections"] == 1
    assert model.calls == 1


def test_strategy_c_reuses_only_a_compatible_semantic_candidate() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "write Python code for binary search"
    metadata = QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", "python"),
        constraints=(("language", "python"),),
        output_format="code",
    )
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="compatible cached answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=metadata,
        )
    )
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={"implement Python binary search": (1.0, 0.0)},
    )
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            embedding_client=embedding_client,
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )

    response = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "cache"
    assert response.json()["decision"] == "SAFE"
    assert response.json()["strategy"] == "semantic"
    assert response.json()["selected_candidate_query_hash"] == (
        hashlib.sha256(cached_query.encode()).hexdigest()
    )
    assert model.calls == 0


def test_strategy_c_generates_for_an_incompatible_semantic_candidate() -> None:
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
                entities=("binary search", "java"),
                constraints=(("language", "java"),),
                output_format="code",
            ),
        )
    )
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={"implement Python binary search": (1.0, 0.0)},
    )
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            embedding_client=embedding_client,
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )

    response = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "generated"
    assert body["decision"] == "UNSAFE"
    assert body["reason"] == "all candidates were incompatible"
    assert body["selected_candidate_query_hash"] is None
    assert body["answer"] != "Java cached answer"
    assert body["candidate_traces"][0]["decision"] == "UNSAFE"
    assert body["candidate_traces"][0]["reason"] == "constraint_mismatch:language"
    assert model.calls == 1


def test_strategy_c_does_not_reuse_exact_entry_without_metadata() -> None:
    cache = InMemoryExactCache()
    query = "exact query with missing metadata"
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="legacy answer",
        )
    )
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "generated"
    assert body["decision"] == "UNCERTAIN"
    assert body["reason"] == "no candidate had sufficient compatibility evidence"
    assert body["selected_candidate_query_hash"] is None
    assert body["answer"] != "legacy answer"
    assert body["candidate_traces"][0]["reason"] == "candidate_metadata_missing"
    assert model.calls == 1


def test_strategy_c_does_not_reuse_dynamic_exact_entry() -> None:
    cache = InMemoryExactCache()
    query = "What is the current stock price?"
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
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "generated"
    assert body["decision"] == "UNCERTAIN"
    assert body["reason"] == "dynamic_entries_disabled"
    assert body["candidate_traces"] is None
    assert body["answer"] != "stale price answer"
    assert model.calls == 1


def test_strategy_c_does_not_bypass_safety_on_duplicate_cache_write() -> None:
    query = "write Python code"
    duplicate_entry = CacheEntry(
        query_hash=hashlib.sha256(query.encode()).hexdigest(),
        normalized_query=query,
        answer="incompatible raced answer",
        metadata=QueryMetadata(
            intent="code",
            domain="programming",
            constraints=(("language", "java"),),
            output_format="code",
        ),
    )
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=DuplicateThenProvidesCache(duplicate_entry),
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert response.json()["answer"] != duplicate_entry.answer
    assert model.calls == 1


def test_strategy_c_logs_bounded_candidate_decision_trace(caplog) -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cached_query = "write Python code for binary search"
    metadata = QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", "python"),
        constraints=(("language", "python"),),
        output_format="code",
    )
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="compatible cached answer sk-test-SECRETVALUE",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=metadata,
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(
                    model_name="test-embedding",
                    dimension=2,
                ),
                vectors={"implement Python binary search": (1.0, 0.0)},
            ),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )

    with caplog.at_level(logging.INFO, logger="sscre"):
        response = client.post(
            "/v1/query",
            json={"query": "implement Python binary search"},
        )

    assert response.status_code == 200
    secret = "sk-test-SECRETVALUE"
    cached_answer = f"compatible cached answer {secret}"
    body = response.json()
    assert body["answer"] == cached_answer
    encoded_traces = json.dumps(body["candidate_traces"])
    assert secret not in encoded_traces
    assert cached_answer not in encoded_traces
    assert cached_query not in encoded_traces
    event = json.loads(
        next(
            record.message
            for record in caplog.records
            if "cache_decision" in record.message
        )
    )
    event_text = json.dumps(event)
    assert secret not in event_text
    assert cached_answer not in event_text
    assert cached_query not in event_text
    trace = event["candidate_traces"][0]
    assert event["outcome"] == "cache_reused"
    assert trace["candidate_order"] == 1
    assert trace["decision"] == "SAFE"
    assert trace["stage"] == "compatibility"
    assert trace["query_metadata"]["constraints"] == {"language": "python"}


def test_cache_repository_failure_returns_503_with_request_id() -> None:
    client = TestClient(create_app(repository=UnavailableCache()))

    response = client.post("/v1/query", json={"query": "database outage"})

    assert response.status_code == 503
    assert response.json() == {"detail": "cache unavailable"}
    assert response.headers["X-Request-ID"]


def test_generation_timeout_returns_controlled_502(caplog) -> None:
    class SlowLLMClient(MockLLMClient):
        def generate(self, query: str) -> LLMResult:
            time.sleep(1.1)
            return super().generate(query)

    client = TestClient(
        create_app(
            llm_client=SlowLLMClient(),
            settings=Settings(generation_timeout_seconds=1),
        )
    )

    caplog.set_level(logging.INFO, logger="sscre")
    response = client.post("/v1/query", json={"query": "slow generation"})

    assert response.status_code == 502
    assert response.json() == {"detail": "response generation failed"}
    assert response.headers["X-Request-ID"]
    event = json.loads(
        next(
            record.message
            for record in caplog.records
            if "generation_failed" in record.message
        )
    )
    event_text = json.dumps(event)
    assert event["decision"] == "UNCERTAIN"
    assert event["reason"] == "generation_failed"
    assert event["outcome"] == "generation_failed"
    assert event["candidate_traces"] is None
    assert "answer" not in event
    assert "authorization" not in event
    assert "slow generation" not in event_text


def test_malformed_generation_result_returns_controlled_502() -> None:
    class MalformedLLMClient:
        def generate(self, query: str) -> object:
            return object()

    client = TestClient(create_app(llm_client=MalformedLLMClient()))

    response = client.post("/v1/query", json={"query": "bad provider"})

    assert response.status_code == 502
    assert response.json() == {"detail": "response generation failed"}


def test_repository_timeout_fails_closed_with_503() -> None:
    class SlowCache(InMemoryExactCache):
        def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
            time.sleep(1.1)
            return super().get_by_query_hash(query_hash)

    client = TestClient(
        create_app(
            repository=SlowCache(),
            settings=Settings(repository_timeout_seconds=1),
        )
    )

    response = client.post("/v1/query", json={"query": "slow repository"})

    assert response.status_code == 503
    assert response.json() == {"detail": "cache unavailable"}
    assert response.headers["X-Request-ID"]


def test_cache_write_failure_preserves_generated_response() -> None:
    class WriteFailCache:
        def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
            return None

        def insert(self, entry: CacheEntry) -> None:
            raise CacheRepositoryError("write unavailable")

    client = TestClient(create_app(repository=WriteFailCache()))

    response = client.post("/v1/query", json={"query": "write outage"})

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert response.json()["reason"] == "cache_write_unavailable"


class CountingMockLLMClient(MockLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def generate(self, query: str) -> LLMResult:
        self.calls += 1
        return super().generate(query)


class UnavailableCache:
    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        raise CacheRepositoryError("database unavailable")

    def insert(self, entry: CacheEntry) -> None:
        raise CacheRepositoryError("database unavailable")


class DuplicateThenProvidesCache:
    def __init__(self, entry: CacheEntry) -> None:
        self.entry = entry
        self.insert_attempted = False

    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        if self.insert_attempted and query_hash == self.entry.query_hash:
            return self.entry
        return None

    def insert(self, entry: CacheEntry) -> None:
        self.insert_attempted = True
        raise DuplicateCacheEntryError("concurrent insert")
