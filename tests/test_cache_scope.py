from sscre.api_auth import DEFAULT_NAMESPACE, TRUSTED_LOCAL_TENANT
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.query import (
    CACHE_KEY_VERSION,
    CacheScope,
    QueryRequest,
    content_query_hash,
    preprocess_query,
    scoped_cache_key,
    trusted_local_scope,
)


def test_scoped_cache_key_versions_and_separates_tenants() -> None:
    normalized = "shared query text"
    tenant_a = scoped_cache_key(
        CacheScope("tenant-a", DEFAULT_NAMESPACE),
        normalized,
    )
    tenant_b = scoped_cache_key(
        CacheScope("tenant-b", DEFAULT_NAMESPACE),
        normalized,
    )
    content = content_query_hash(normalized)

    assert tenant_a != tenant_b
    assert tenant_a != content
    assert tenant_b != content
    assert CACHE_KEY_VERSION == "v2"


def test_same_query_different_namespace_has_different_storage_key() -> None:
    normalized = "namespace isolation"
    first = scoped_cache_key(CacheScope("tenant-a", "ns-one"), normalized)
    second = scoped_cache_key(CacheScope("tenant-a", "ns-two"), normalized)
    assert first != second


def test_preprocess_binds_authenticated_scope() -> None:
    scope = CacheScope("tenant-z", "workspace-1")
    processed = preprocess_query(QueryRequest(query="hello"), scope)

    assert processed.tenant_id == "tenant-z"
    assert processed.namespace_id == "workspace-1"
    assert processed.content_query_hash == content_query_hash("hello")
    assert processed.query_hash == scoped_cache_key(scope, "hello")


def test_vector_search_does_not_cross_tenant_boundaries() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    embedding = (1.0, 0.0)
    cache.insert(
        CacheEntry(
            query_hash=scoped_cache_key(
                CacheScope("tenant-a", DEFAULT_NAMESPACE),
                "tenant a query",
            ),
            normalized_query="tenant a query",
            answer="answer a",
            tenant_id="tenant-a",
            embedding=embedding,
            embedding_model="fixture",
            embedding_dimension=2,
        )
    )
    cache.insert(
        CacheEntry(
            query_hash=scoped_cache_key(
                CacheScope("tenant-b", DEFAULT_NAMESPACE),
                "tenant b query",
            ),
            normalized_query="tenant b query",
            answer="answer b",
            tenant_id="tenant-b",
            embedding=embedding,
            embedding_model="fixture",
            embedding_dimension=2,
        )
    )

    tenant_a_hits = cache.search_by_embedding(
        embedding,
        top_k=5,
        tenant_id="tenant-a",
        namespace_id=DEFAULT_NAMESPACE,
    )
    tenant_b_hits = cache.search_by_embedding(
        embedding,
        top_k=5,
        tenant_id="tenant-b",
        namespace_id=DEFAULT_NAMESPACE,
    )

    assert len(tenant_a_hits) == 1
    assert tenant_a_hits[0].answer == "answer a"
    assert len(tenant_b_hits) == 1
    assert tenant_b_hits[0].answer == "answer b"


def test_cache_entry_upgrades_legacy_content_hash_to_scoped_storage_key() -> None:
    normalized = "upgrade me"
    content = content_query_hash(normalized)
    entry = CacheEntry(
        query_hash=content,
        normalized_query=normalized,
        answer="ok",
        tenant_id=TRUSTED_LOCAL_TENANT,
        namespace_id=DEFAULT_NAMESPACE,
    )

    assert entry.content_query_hash == content
    assert entry.query_hash == scoped_cache_key(trusted_local_scope(), normalized)
