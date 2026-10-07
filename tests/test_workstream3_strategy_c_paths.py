"""Workstream 3 step 5: Strategy C exact/semantic integration paths."""

from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

try:
    from fastapi.testclient import TestClient
    from sscre.app import create_app
except ImportError:  # pragma: no cover - psycopg/libpq unavailable
    pytest.skip(
        "sscre.app unavailable in this environment",
        allow_module_level=True,
    )
from sscre.cache import CacheEntry, DuplicateCacheEntryError, InMemoryExactCache
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.llm import LLMResult, MockLLMClient
from sscre.metadata import extract_metadata
from sscre.query import QueryRequest, preprocess_query
from sscre.safety import QueryMetadata


def _query_hash(query: str) -> str:
    return preprocess_query(QueryRequest(query=query)).query_hash


def _python_search_meta() -> QueryMetadata:
    return QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", "python"),
        constraints=(("language", "python"),),
        output_format="code",
    )


def _assert_generated_not_reusable(body: dict[str, object]) -> None:
    assert body["source"] == "generated"
    assert body["decision"] != "SAFE"
    assert body.get("selected_candidate_query_hash") is None


class CountingMockLLMClient(MockLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def generate(self, query: str) -> LLMResult:
        self.calls += 1
        return super().generate(query)


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


def test_strategy_c_exact_compatible_hit_is_safe_with_selection() -> None:
    query = "Write Python code for binary search"
    query_hash = _query_hash(query)
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=query_hash,
            normalized_query=query,
            answer="exact compatible answer",
            metadata=_python_search_meta(),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )
    response = client.post("/v1/query", json={"query": query})
    body = response.json()
    assert body["source"] == "cache"
    assert body["decision"] == "SAFE"
    assert body["similarity"] == 1.0
    assert body["selected_candidate_query_hash"] == query_hash
    assert body["candidate_traces"][0]["stage"] == "compatibility"


def test_strategy_c_exact_missing_metadata_is_uncertain_and_generates() -> None:
    query = "exact query with missing metadata"
    cache = InMemoryExactCache()
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
    body = client.post("/v1/query", json={"query": query}).json()
    _assert_generated_not_reusable(body)
    assert body["decision"] == "UNCERTAIN"
    assert body["candidate_traces"][0]["reason"] == "candidate_metadata_missing"
    assert model.calls == 1


def test_strategy_c_exact_metadata_mismatch_is_unsafe_and_generates() -> None:
    query = "Write Python code for binary search"
    query_hash = _query_hash(query)
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=query_hash,
            normalized_query=query,
            answer="wrong-language answer",
            metadata=QueryMetadata(
                intent="code",
                domain="programming",
                entities=("binary search", "java"),
                constraints=(("language", "java"),),
                output_format="code",
            ),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
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
    body = client.post("/v1/query", json={"query": query}).json()
    _assert_generated_not_reusable(body)
    assert body["decision"] == "UNSAFE"
    assert body["candidate_traces"][0]["reason"] == "constraint_mismatch:language"
    assert body["answer"] != "wrong-language answer"
    assert model.calls == 1


def test_strategy_c_semantic_selects_later_compatible_candidate() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    java_query = "write Java code for binary search"
    python_query = "write Python code for binary search"
    ttl = datetime.now(timezone.utc) + timedelta(hours=1)
    meta = lambda lang: QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", lang),
        constraints=(("language", lang),),
        output_format="code",
    )
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(java_query.encode()).hexdigest(),
            normalized_query=java_query,
            answer="java answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=meta("java"),
            ttl_expires_at=ttl,
        )
    )
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(python_query.encode()).hexdigest(),
            normalized_query=python_query,
            answer="python answer",
            embedding=(0.99, 0.01),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=meta("python"),
            ttl_expires_at=ttl,
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
            semantic_top_k=2,
        )
    )
    body = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    ).json()
    assert body["source"] == "cache"
    assert body["decision"] == "SAFE"
    assert body["answer"] == "python answer"
    assert body["candidate_traces"][0]["decision"] == "UNSAFE"
    assert body["candidate_traces"][1]["decision"] == "SAFE"


def test_strategy_c_semantic_all_incompatible_generates_with_traces() -> None:
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
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    model = CountingMockLLMClient()
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
    body = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    ).json()
    _assert_generated_not_reusable(body)
    assert body["decision"] == "UNSAFE"
    assert body["candidate_traces"][0]["decision"] == "UNSAFE"
    assert model.calls == 1


def test_strategy_c_semantic_incomplete_evidence_keeps_traces_on_fallback() -> None:
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
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
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
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
        )
    )
    body = client.post(
        "/v1/query",
        json={"query": "new wording for vector search"},
    ).json()
    _assert_generated_not_reusable(body)
    assert body["decision"] == "UNCERTAIN"
    assert body["candidate_traces"][0]["reason"] == "candidate_metadata_missing"
    assert model.calls == 1


@pytest.mark.parametrize(
    "factory",
    [
        "exact_missing_metadata",
        "exact_metadata_mismatch",
        "semantic_incompatible",
    ],
)
def test_strategy_c_generated_responses_are_never_safe(factory: str) -> None:
    if factory == "exact_missing_metadata":
        query = "legacy exact missing meta"
        cache = InMemoryExactCache()
        cache.insert(
            CacheEntry(
                query_hash=hashlib.sha256(query.encode()).hexdigest(),
                normalized_query=query,
                answer="legacy",
            )
        )
        client = TestClient(
            create_app(repository=cache, semantic_strategy="C", semantic_enabled=False)
        )
        body = client.post("/v1/query", json={"query": query}).json()
    elif factory == "exact_metadata_mismatch":
        query = "Write Python code for binary search"
        cache = InMemoryExactCache()
        cache.insert(
            CacheEntry(
                query_hash=hashlib.sha256(query.encode()).hexdigest(),
                normalized_query=query,
                answer="legacy",
                metadata=QueryMetadata(
                    intent="code",
                    domain="programming",
                    constraints=(("language", "java"),),
                    output_format="code",
                ),
            )
        )
        client = TestClient(
            create_app(repository=cache, semantic_strategy="C", semantic_enabled=False)
        )
        body = client.post("/v1/query", json={"query": query}).json()
    else:
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
        body = client.post(
            "/v1/query",
            json={"query": "implement Python binary search"},
        ).json()
    _assert_generated_not_reusable(body)


def test_strategy_b_semantic_hit_skips_compatibility_evaluation() -> None:
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
            metadata=None,
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"new wording for vector search": (1.0, 0.0)},
            ),
            semantic_strategy="B",
            semantic_similarity_threshold=0.9,
        )
    )
    body = client.post(
        "/v1/query",
        json={"query": "new wording for vector search"},
    ).json()
    assert body["source"] == "cache"
    assert body["decision"] == "SAFE"
    assert body["candidate_traces"][0]["stage"] == "retrieval"
    assert body["candidate_traces"][0]["reason"] == "similarity_threshold_met"


def test_strategy_c_evaluates_exact_hit_while_b_can_skip_compatibility() -> None:
    query = "Write Python code for binary search"
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    corrupt = CacheEntry(
        query_hash=query_hash,
        normalized_query=query,
        answer="incompatible cached answer",
        metadata=QueryMetadata(
            intent="code",
            domain="programming",
            constraints=(("language", "java"),),
            output_format="code",
        ),
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    cache_c = InMemoryExactCache()
    cache_c.insert(corrupt)
    body_c = TestClient(
        create_app(
            repository=cache_c,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    ).post("/v1/query", json={"query": query}).json()
    _assert_generated_not_reusable(body_c)

    cache_b = InMemoryExactCache()
    cache_b.insert(corrupt)
    body_b = TestClient(
        create_app(
            repository=cache_b,
            semantic_strategy="B",
            semantic_enabled=False,
        )
    ).post("/v1/query", json={"query": query}).json()
    assert body_b["source"] == "cache"
    assert body_b["answer"] == corrupt.answer


def test_post_generation_exact_recheck_runs_strategy_c_compatibility() -> None:
    class CountingSlowLLM:
        def __init__(self) -> None:
            self.calls = 0
            self._lock = threading.Lock()

        def generate(self, query: str) -> LLMResult:
            with self._lock:
                self.calls += 1
            time.sleep(0.05)
            return LLMResult(
                text=f"answer for {query}",
                input_tokens=1,
                output_tokens=3,
                latency_ms=50,
            )

    query = "Write Python code for post-lock exact recheck"
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            llm_client=CountingSlowLLM(),
            repository=cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post("/v1/query", json={"query": query}),
                range(2),
            )
        )
    bodies = [response.json() for response in responses]
    assert sorted(body["source"] for body in bodies) == ["cache", "generated"]
    cached = next(body for body in bodies if body["source"] == "cache")
    assert cached["decision"] == "SAFE"
    assert cached["candidate_traces"][0]["stage"] == "compatibility"


def test_duplicate_write_recovery_applies_strategy_c_to_raced_entry() -> None:
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
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
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
    body = client.post("/v1/query", json={"query": query}).json()
    _assert_generated_not_reusable(body)
    assert body["decision"] == "UNSAFE"
    assert body["candidate_traces"][0]["reason"] == "constraint_mismatch:language"
    assert model.calls == 1


def test_generated_entry_metadata_matches_preprocess_for_exact_recheck() -> None:
    query = "Write Python code for binary search"
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(repository=cache, semantic_strategy="C", semantic_enabled=False)
    )
    first = client.post("/v1/query", json={"query": query}).json()
    second = client.post("/v1/query", json={"query": query}).json()
    assert first["source"] == "generated"
    assert second["source"] == "cache"
    assert second["decision"] == "SAFE"
    stored = cache.get_by_query_hash(hashlib.sha256(query.encode()).hexdigest())
    assert stored is not None
    assert stored.metadata == extract_metadata(query)
