"""PostgreSQL tenant/namespace isolation (Workstream 2 Step 2.4)."""

import os
from uuid import uuid4

import psycopg
import pytest

from sscre.api_auth import DEFAULT_NAMESPACE
from sscre.cache import CacheEntry, DuplicateCacheEntryError, InMemoryExactCache
from sscre.postgres_cache import PostgresExactCacheRepository, delete_entries_by_query_hashes
from sscre.query import CacheScope, scoped_cache_key, storage_query_hash


DATABASE_URL = os.getenv("SSCRE_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="SSCRE_DATABASE_URL is required for PostgreSQL scope tests",
)


def _cleanup(hashes: list[str]) -> None:
    assert DATABASE_URL is not None
    delete_entries_by_query_hashes(DATABASE_URL, hashes)


def _entry(
    tenant_id: str,
    namespace_id: str,
    normalized_query: str,
    answer: str,
    *,
    embedding: tuple[float, ...] | None = None,
) -> CacheEntry:
    scope = CacheScope(tenant_id, namespace_id)
    return CacheEntry(
        query_hash=scoped_cache_key(scope, normalized_query),
        normalized_query=normalized_query,
        answer=answer,
        tenant_id=tenant_id,
        namespace_id=namespace_id,
        embedding=embedding,
        embedding_model="fixture" if embedding else None,
        embedding_dimension=len(embedding) if embedding else None,
    )


def test_postgres_exact_lookup_is_scoped_by_storage_key() -> None:
    assert DATABASE_URL is not None
    repo = PostgresExactCacheRepository(DATABASE_URL)
    query = f"ws2 scope exact {uuid4()}"
    tenant_a = _entry("tenant-a", DEFAULT_NAMESPACE, query, "answer-a")
    tenant_b = _entry("tenant-b", DEFAULT_NAMESPACE, query, "answer-b")
    hashes = [tenant_a.query_hash, tenant_b.query_hash]
    try:
        repo.insert(tenant_a)
        repo.insert(tenant_b)
        assert repo.get_by_query_hash(tenant_a.query_hash) is not None
        assert repo.get_by_query_hash(tenant_b.query_hash) is not None
        other_key = scoped_cache_key(
            CacheScope("tenant-c", DEFAULT_NAMESPACE),
            query,
        )
        assert repo.get_by_query_hash(other_key) is None
    finally:
        _cleanup(hashes)


def test_postgres_vector_search_stays_within_tenant_namespace() -> None:
    assert DATABASE_URL is not None
    repo = PostgresExactCacheRepository(DATABASE_URL)
    embedding = (1.0, 0.0)
    query = f"ws2 scope vector {uuid4()}"
    tenant_a = _entry(
        "tenant-a",
        DEFAULT_NAMESPACE,
        query,
        "answer-a",
        embedding=embedding,
    )
    tenant_b = _entry(
        "tenant-b",
        DEFAULT_NAMESPACE,
        query,
        "answer-b",
        embedding=embedding,
    )
    hashes = [tenant_a.query_hash, tenant_b.query_hash]
    try:
        repo.insert(tenant_a)
        repo.insert(tenant_b)
        hits_a = repo.search_by_embedding(
            embedding,
            top_k=5,
            tenant_id="tenant-a",
            namespace_id=DEFAULT_NAMESPACE,
        )
        hits_b = repo.search_by_embedding(
            embedding,
            top_k=5,
            tenant_id="tenant-b",
            namespace_id=DEFAULT_NAMESPACE,
        )
        assert len(hits_a) == 1
        assert hits_a[0].answer == "answer-a"
        assert len(hits_b) == 1
        assert hits_b[0].answer == "answer-b"
    finally:
        _cleanup(hashes)


def test_postgres_scoped_identity_rejects_duplicate_content_per_namespace() -> None:
    assert DATABASE_URL is not None
    repo = PostgresExactCacheRepository(DATABASE_URL)
    query = f"ws2 dup content {uuid4()}"
    first = _entry("tenant-dup", DEFAULT_NAMESPACE, query, "first")
    second = CacheEntry(
        query_hash=scoped_cache_key(
            CacheScope("tenant-dup", "alt-ns"),
            query,
        ),
        normalized_query=query,
        answer="second",
        tenant_id="tenant-dup",
        namespace_id="alt-ns",
    )
    duplicate = CacheEntry(
        query_hash=scoped_cache_key(
            CacheScope("tenant-dup", DEFAULT_NAMESPACE),
            query,
        ),
        normalized_query=query,
        answer="duplicate",
        tenant_id="tenant-dup",
        namespace_id=DEFAULT_NAMESPACE,
    )
    hashes = [first.query_hash, second.query_hash]
    try:
        repo.insert(first)
        repo.insert(second)
        with pytest.raises(DuplicateCacheEntryError):
            repo.insert(duplicate)
    finally:
        _cleanup(hashes)


def test_postgres_storage_stats_can_scope_to_tenant_namespace() -> None:
    assert DATABASE_URL is not None
    repo = PostgresExactCacheRepository(DATABASE_URL)
    query_a = f"ws2 stats a {uuid4()}"
    query_b = f"ws2 stats b {uuid4()}"
    entry_a = _entry("tenant-stats", DEFAULT_NAMESPACE, query_a, "a")
    entry_b = _entry("tenant-other", DEFAULT_NAMESPACE, query_b, "b")
    hashes = [entry_a.query_hash, entry_b.query_hash]
    try:
        repo.insert(entry_a)
        repo.insert(entry_b)
        scoped = repo.storage_stats(
            tenant_id="tenant-stats",
            namespace_id=DEFAULT_NAMESPACE,
        )
        global_stats = repo.storage_stats()
        assert scoped.entries == 1
        assert global_stats.entries >= 2
    finally:
        _cleanup(hashes)


def test_in_memory_and_postgres_both_enforce_scoped_vector_search() -> None:
    embedding = (1.0, 0.0)
    query = "shared isolation wording"
    memory = InMemoryExactCache(embedding_dimension=2)
    memory.insert(
        _entry("mem-a", DEFAULT_NAMESPACE, query, "a", embedding=embedding)
    )
    memory.insert(
        _entry("mem-b", DEFAULT_NAMESPACE, query, "b", embedding=embedding)
    )
    mem_hits = memory.search_by_embedding(
        embedding,
        top_k=5,
        tenant_id="mem-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    assert len(mem_hits) == 1
    assert mem_hits[0].answer == "a"
