"""Workstream 3 step 7: concurrent and duplicate-write decision safety."""

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
from sscre.llm import LLMResult, MockLLMClient
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


class CountingMockLLMClient(MockLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0
        self._lock = threading.Lock()

    def generate(self, query: str) -> LLMResult:
        with self._lock:
            self.calls += 1
        return super().generate(query)


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


class DuplicateThenProvidesCache:
    """Simulate a peer insert during generation; ``get`` returns the raced entry."""

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


def _post_same_query(client: TestClient, query: str):
    return client.post("/v1/query", json={"query": query})


def test_concurrent_same_query_shared_repository_strategy_c() -> None:
    query = "Write Python code for concurrent Strategy C reuse"
    model = CountingSlowLLM()
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda _: _post_same_query(client, query), range(2))
        )
    assert all(response.status_code == 200 for response in responses)
    bodies = [response.json() for response in responses]
    assert model.calls == 1
    assert sorted(body["source"] for body in bodies) == ["cache", "generated"]
    cached = next(body for body in bodies if body["source"] == "cache")
    assert cached["decision"] == "SAFE"
    assert cached["candidate_traces"][0]["stage"] == "compatibility"
    generated = next(body for body in bodies if body["source"] == "generated")
    assert generated["decision"] != "SAFE"
    assert generated.get("selected_candidate_query_hash") is None


def test_concurrent_same_query_only_one_cache_reuse_response() -> None:
    query = "Write Python code for single cache reuse under race"
    model = CountingSlowLLM()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=InMemoryExactCache(),
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda _: _post_same_query(client, query), range(2))
        )
    bodies = [response.json() for response in responses]
    cache_hits = [body for body in bodies if body["source"] == "cache"]
    assert len(cache_hits) == 1
    assert cache_hits[0]["decision"] == "SAFE"


def test_concurrent_requests_do_not_reuse_metadata_less_raced_entry() -> None:
    query = "write Python code under metadata-less duplicate race"
    query_hash = _query_hash(query)
    raced_entry = CacheEntry(
        query_hash=query_hash,
        normalized_query=query,
        answer="metadata-less raced answer",
        metadata=None,
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    model = CountingMockLLMClient()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=DuplicateThenProvidesCache(raced_entry),
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda _: _post_same_query(client, query), range(2))
        )
    bodies = [response.json() for response in responses]
    assert all(response.status_code == 200 for response in responses)
    assert all(body["source"] == "generated" for body in bodies)
    assert all(body["decision"] != "SAFE" for body in bodies)
    assert all(body["answer"] != "metadata-less raced answer" for body in bodies)
    assert model.calls == 2
    assert all(
        body["candidate_traces"][0]["reason"] == "candidate_metadata_missing"
        for body in bodies
    )


def test_duplicate_write_incompatible_entry_evaluated_not_served() -> None:
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
    assert body["source"] == "generated"
    assert body["decision"] == "UNSAFE"
    assert body["answer"] != "incompatible raced answer"
    assert body["candidate_traces"][0]["stage"] == "compatibility"
    assert body["candidate_traces"][0]["reason"] == "constraint_mismatch:language"
    assert model.calls == 1


def test_duplicate_write_expired_entry_emits_retrieval_trace() -> None:
    query = "write Python code for expired duplicate recovery"
    duplicate_entry = CacheEntry(
        query_hash=hashlib.sha256(query.encode()).hexdigest(),
        normalized_query=query,
        answer="expired raced answer",
        metadata=_python_search_meta(),
        ttl_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
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
    assert body["source"] == "generated"
    assert body["decision"] == "UNSAFE"
    assert body["answer"] != "expired raced answer"
    trace = body["candidate_traces"][0]
    assert trace["stage"] == "retrieval"
    assert trace["reason"] == "cache_control_expired"
    assert model.calls == 1


def test_duplicate_write_compatible_entry_reuses_after_compatibility_check() -> None:
    query = "Write Python code for binary search"
    query_hash = _query_hash(query)
    duplicate_entry = CacheEntry(
        query_hash=query_hash,
        normalized_query=query,
        answer="compatible raced answer",
        metadata=_python_search_meta(),
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
    assert body["source"] == "cache"
    assert body["decision"] == "SAFE"
    assert body["answer"] == "compatible raced answer"
    assert body["selected_candidate_query_hash"] == query_hash
    assert body["candidate_traces"][0]["stage"] == "compatibility"
    assert model.calls == 1


def test_concurrent_exact_expired_entries_never_served() -> None:
    query = "Write Python code for concurrent expired exact hit"
    query_hash = _query_hash(query)
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=query_hash,
            normalized_query=query,
            answer="stale exact answer",
            metadata=_python_search_meta(),
            ttl_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
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
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(
            executor.map(lambda _: _post_same_query(client, query), range(4))
        )
    assert all(response.status_code == 200 for response in responses)
    bodies = [response.json() for response in responses]
    assert all(body["answer"] != "stale exact answer" for body in bodies)
    assert model.calls == 1
    generated = [body for body in bodies if body["source"] == "generated"]
    reused = [body for body in bodies if body["source"] == "cache"]
    assert len(generated) == 1
    assert generated[0]["decision"] != "SAFE"
    assert len(reused) == 3
    assert all(body["decision"] == "SAFE" for body in reused)
    assert all(
        body["candidate_traces"][0]["cache_control_outcome"] == "fresh"
        for body in reused
    )
