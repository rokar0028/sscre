from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.config import Settings
from sscre.safety import QueryMetadata


def _entry(query_hash: str, answer: str) -> CacheEntry:
    return CacheEntry(
        query_hash=query_hash,
        normalized_query=query_hash,
        answer=answer,
    )


def test_lru_eviction_preserves_recently_used_entry() -> None:
    cache = InMemoryExactCache()
    cache.insert(_entry("older", "older answer"))
    cache.insert(_entry("newer", "newer answer"))
    cache.record_hit("older")

    assert cache.evict_to_limits(max_entries=1, max_bytes=10_000) == 1
    assert cache.get_by_query_hash("older") is not None
    assert cache.get_by_query_hash("newer") is None


def test_insert_and_evict_enforces_caps_in_one_operation() -> None:
    cache = InMemoryExactCache()

    cache.insert_and_evict(_entry("first", "first answer"), 1, 10_000)
    cache.insert_and_evict(_entry("second", "second answer"), 1, 10_000)

    assert cache.storage_stats().entries == 1
    assert cache.get_by_query_hash("first") is None
    assert cache.get_by_query_hash("second") is not None


def test_byte_cap_evicts_until_within_budget_and_removes_orphan() -> None:
    cache = InMemoryExactCache()
    cache.insert(_entry("first", "same answer"))
    cache.insert(_entry("second", "same answer"))
    canonical_hash = cache.get_by_query_hash("first").canonical_answer_hash

    evicted = cache.evict_to_limits(max_entries=10, max_bytes=1)

    assert evicted == 2
    assert cache.storage_bytes() == 0
    assert cache.canonical_answer_count() == 0
    assert canonical_hash is not None
    assert cache.get_canonical_answer(canonical_hash) is None


def test_lru_ties_are_broken_by_query_hash() -> None:
    cache = InMemoryExactCache()
    cache.insert(_entry("b", "answer"))
    cache.insert(_entry("a", "answer"))
    cache._access_order["a"] = cache._access_order["b"]

    cache.evict_to_limits(max_entries=1, max_bytes=10_000)

    assert cache.get_by_query_hash("a") is None
    assert cache.get_by_query_hash("b") is not None


def test_pattern_eviction_prioritizes_low_hits_within_freshness_class() -> None:
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash="stable",
            normalized_query="stable",
            answer="stable answer",
            metadata=QueryMetadata(temporal_class="stable"),
        )
    )
    cache.insert(
        CacheEntry(
            query_hash="semi",
            normalized_query="semi",
            answer="semi answer",
            metadata=QueryMetadata(temporal_class="semi_dynamic"),
        )
    )
    cache.record_hit("stable")

    assert (
        cache.evict_to_limits(
            max_entries=1,
            max_bytes=10_000,
            eviction_strategy="pattern",
        )
        == 1
    )
    assert cache.get_by_query_hash("stable") is not None
    assert cache.get_by_query_hash("semi") is None


def test_storage_stats_and_bounded_expired_cleanup() -> None:
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash="expired",
            normalized_query="expired",
            answer="answer",
            ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )
    cache.insert(_entry("fresh", "answer"))

    stats = cache.storage_stats()
    assert stats.entries == 2
    assert stats.canonical_answers == 1
    assert stats.total_bytes > 0
    assert stats.average_entry_bytes > 0
    assert cache.cleanup_expired(limit=1) == 1
    assert cache.get_by_query_hash("expired") is None
    assert cache.get_by_query_hash("fresh") is not None


def test_cache_stats_endpoint_reports_bounded_storage_metrics() -> None:
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            repository=cache,
            settings=Settings(admin_token="test-admin-token"),
        )
    )
    client.post(
        "/v1/query",
        json={"query": "Write Python code for cache stats"},
    )
    client.post(
        "/v1/query",
        json={"query": "Write Python code for cache stats"},
    )

    response = client.get(
        "/v1/cache/stats",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["storage"]["entries"] == 1
    assert body["storage"]["canonical_answers"] == 1
    assert body["storage"]["total_bytes"] > 0
    assert body["request_metrics"]["cache_hits"] == 1
    assert body["limits"]["max_entries"] > 0


def test_interleaved_inserts_keep_one_canonical_answer() -> None:
    cache = InMemoryExactCache()
    entries = [
        _entry(f"query-{index}", "shared concurrent answer")
        for index in range(20)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(cache.insert, entries))

    stats = cache.storage_stats()
    assert stats.entries == len(entries)
    assert stats.canonical_answers == 1
    assert stats.deduplication_hits == len(entries) - 1
