import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import (
    CacheEntry,
    DuplicateCacheEntryError,
    InMemoryExactCache,
)


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
    client = TestClient(create_app())

    first = client.post("/v1/query", json={"query": "  What is caching?  "})
    second = client.post("/v1/query", json={"query": "What   is caching?"})

    assert first.status_code == 200
    assert first.json()["source"] == "generated"
    assert second.status_code == 200
    assert second.json()["source"] == "cache"
    assert second.json()["answer"] == first.json()["answer"]


def test_different_queries_do_not_collide() -> None:
    client = TestClient(create_app())

    first = client.post("/v1/query", json={"query": "What is caching?"})
    second = client.post("/v1/query", json={"query": "What is hashing?"})

    assert first.json()["source"] == "generated"
    assert second.json()["source"] == "generated"
    assert second.json()["answer"] != first.json()["answer"]
