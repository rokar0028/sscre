"""Workstream 2 Step 2.5 — scoped lookup, search, and repository predicates."""

from datetime import datetime, timedelta, timezone

import pytest

from sscre.api_auth import DEFAULT_NAMESPACE
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.query import (
    CacheScope,
    MissingCacheScopeError,
    scoped_cache_key,
)


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


def test_external_mode_repository_rejects_missing_scope_predicates() -> None:
    cache = InMemoryExactCache(require_scoped_operations=True)
    scope = CacheScope("tenant-a", DEFAULT_NAMESPACE)
    query_hash = scoped_cache_key(scope, "shared wording")

    with pytest.raises(MissingCacheScopeError):
        cache.get_by_query_hash(query_hash)

    with pytest.raises(MissingCacheScopeError):
        cache.storage_stats()

    with pytest.raises(MissingCacheScopeError):
        cache.cleanup_expired()

    with pytest.raises(MissingCacheScopeError):
        cache.evict_to_limits(1, 10_000)


def test_cross_tenant_exact_lookup_and_hits_stay_isolated() -> None:
    cache = InMemoryExactCache(embedding_dimension=1)
    query = "identical normalized query"
    tenant_a = _entry("tenant-a", DEFAULT_NAMESPACE, query, "answer-a")
    tenant_b = _entry("tenant-b", DEFAULT_NAMESPACE, query, "answer-b")
    cache.insert(tenant_a)
    cache.insert(tenant_b)

    assert (
        cache.get_by_query_hash(
            tenant_a.query_hash,
            tenant_id="tenant-a",
            namespace_id=DEFAULT_NAMESPACE,
        ).answer
        == "answer-a"
    )
    assert (
        cache.get_by_query_hash(
            tenant_b.query_hash,
            tenant_id="tenant-b",
            namespace_id=DEFAULT_NAMESPACE,
        ).answer
        == "answer-b"
    )
    assert cache.get_by_query_hash(
        tenant_a.query_hash,
        tenant_id="tenant-b",
        namespace_id=DEFAULT_NAMESPACE,
    ) is None

    cache.record_hit(
        tenant_a.query_hash,
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    assert cache.hit_count(tenant_a.query_hash) == 1
    cache.record_hit(
        tenant_a.query_hash,
        tenant_id="tenant-b",
        namespace_id=DEFAULT_NAMESPACE,
    )
    assert cache.hit_count(tenant_a.query_hash) == 1


def test_cross_tenant_vector_search_with_identical_embeddings() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    embedding = (1.0, 0.0)
    query = "same semantic surface form"
    cache.insert(
        _entry("tenant-a", DEFAULT_NAMESPACE, query, "a", embedding=embedding)
    )
    cache.insert(
        _entry("tenant-b", DEFAULT_NAMESPACE, query, "b", embedding=embedding)
    )
    cache.insert(
        _entry(
            "tenant-a",
            "workspace-2",
            query,
            "a-alt-ns",
            embedding=embedding,
        )
    )

    hits_a = cache.search_by_embedding(
        embedding,
        top_k=5,
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    hits_b = cache.search_by_embedding(
        embedding,
        top_k=5,
        tenant_id="tenant-b",
        namespace_id=DEFAULT_NAMESPACE,
    )
    hits_overlap_ns = cache.search_by_embedding(
        embedding,
        top_k=5,
        tenant_id="tenant-a",
        namespace_id="workspace-2",
    )

    assert len(hits_a) == 1 and hits_a[0].answer == "a"
    assert len(hits_b) == 1 and hits_b[0].answer == "b"
    assert len(hits_overlap_ns) == 1 and hits_overlap_ns[0].answer == "a-alt-ns"


def test_scoped_delete_and_eviction_do_not_touch_other_tenants() -> None:
    cache = InMemoryExactCache()
    tenant_a = _entry("tenant-a", DEFAULT_NAMESPACE, "evict me", "a")
    tenant_b = _entry("tenant-b", DEFAULT_NAMESPACE, "evict me", "b")
    cache.insert(tenant_a)
    cache.insert(tenant_b)

    cache.delete_by_query_hash(
        tenant_a.query_hash,
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    assert cache.get_by_query_hash(tenant_a.query_hash) is None
    assert cache.get_by_query_hash(tenant_b.query_hash) is not None

    cache.insert(tenant_a)
    cache.evict_to_limits(
        1,
        1,
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    scoped_stats = cache.storage_stats(
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    other_stats = cache.storage_stats(
        tenant_id="tenant-b",
        namespace_id=DEFAULT_NAMESPACE,
    )
    assert scoped_stats.entries == 0
    assert other_stats.entries == 1


def test_scoped_cleanup_expired_and_canonical_reads() -> None:
    cache = InMemoryExactCache()
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    tenant_a = CacheEntry(
        query_hash=scoped_cache_key(CacheScope("tenant-a", DEFAULT_NAMESPACE), "ttl"),
        normalized_query="ttl",
        answer="shared canonical body",
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
        ttl_expires_at=expired_at,
    )
    tenant_b = CacheEntry(
        query_hash=scoped_cache_key(CacheScope("tenant-b", DEFAULT_NAMESPACE), "ttl"),
        normalized_query="ttl",
        answer="shared canonical body",
        tenant_id="tenant-b",
        namespace_id=DEFAULT_NAMESPACE,
        ttl_expires_at=expired_at,
    )
    cache.insert(tenant_a)
    cache.insert(tenant_b)
    shared_hash = tenant_a.canonical_answer_hash
    assert shared_hash is not None

    removed = cache.cleanup_expired(
        limit=10,
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    assert removed == 1
    assert cache.get_by_query_hash(tenant_a.query_hash) is None
    assert cache.get_by_query_hash(tenant_b.query_hash) is not None
    assert (
        cache.get_canonical_answer(
            shared_hash,
            tenant_id="tenant-b",
            namespace_id=DEFAULT_NAMESPACE,
        )
        is not None
    )
    assert (
        cache.get_canonical_answer(
            shared_hash,
            tenant_id="tenant-a",
            namespace_id=DEFAULT_NAMESPACE,
        )
        is None
    )


def test_external_mode_insert_requires_consistent_scoped_identity() -> None:
    cache = InMemoryExactCache(require_scoped_operations=True)
    scope = CacheScope("tenant-a", DEFAULT_NAMESPACE)
    with pytest.raises(ValueError, match="query_hash does not match"):
        cache.insert(
            CacheEntry(
                query_hash="0" * 64,
                normalized_query="mismatch",
                answer="x",
                tenant_id="tenant-a",
                namespace_id=DEFAULT_NAMESPACE,
            )
        )

    cache.insert(_entry("tenant-a", DEFAULT_NAMESPACE, "valid", "ok"))
    scoped_stats = cache.storage_stats(
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    assert scoped_stats.entries == 1
