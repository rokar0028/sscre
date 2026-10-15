"""WS4 Step 5 — PostgreSQL candidate filtering and scope safety."""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from sscre.api_auth import DEFAULT_NAMESPACE, TRUSTED_LOCAL_TENANT
from sscre.app import create_app
from sscre.cache import CacheEntry
from sscre.config import Settings
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.llm import MockLLMClient
from sscre.postgres_cache import (
    PostgresExactCacheRepository,
    ScopedPostgresExactCacheRepository,
    delete_entries_by_query_hashes,
)
from sscre.query import CacheScope, MissingCacheScopeError, scoped_cache_key
from sscre.safety import QueryMetadata

DATABASE_URL = os.getenv("SSCRE_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="SSCRE_DATABASE_URL is required for PostgreSQL candidate filtering tests",
)

TENANT = TRUSTED_LOCAL_TENANT
NAMESPACE = DEFAULT_NAMESPACE
DIM = 2


def _model_name() -> str:
    return f"ws4-filter-{uuid4()}"


def _cleanup(hashes: list[str]) -> None:
    assert DATABASE_URL is not None
    delete_entries_by_query_hashes(DATABASE_URL, hashes)


def _scoped_entry(
    normalized_query: str,
    answer: str,
    *,
    embedding: tuple[float, ...] | None = None,
    ttl_expires_at: datetime | None = None,
    metadata: QueryMetadata | None = None,
    tenant_id: str = TENANT,
    namespace_id: str = NAMESPACE,
    embedding_model: str | None = None,
) -> CacheEntry:
    model = embedding_model or _model_name()
    scope_key = scoped_cache_key(
        CacheScope(tenant_id, namespace_id),
        normalized_query,
    )
    return CacheEntry(
        query_hash=scope_key,
        normalized_query=normalized_query,
        answer=answer,
        tenant_id=tenant_id,
        namespace_id=namespace_id,
        embedding=embedding,
        embedding_model=model if embedding else None,
        embedding_dimension=DIM if embedding else None,
        metadata=metadata,
        ttl_expires_at=ttl_expires_at,
    )


def test_postgres_requires_scope_predicates_when_configured() -> None:
    assert DATABASE_URL is not None
    repo = PostgresExactCacheRepository(
        DATABASE_URL,
        require_scoped_operations=True,
    )
    digest = hashlib.sha256(b"scope-required").hexdigest()
    with pytest.raises(MissingCacheScopeError):
        repo.get_by_query_hash(digest)
    with pytest.raises(MissingCacheScopeError):
        repo.storage_stats()
    with pytest.raises(MissingCacheScopeError):
        repo.cleanup_expired(only_query_hashes=None)


def test_postgres_vector_tie_breaks_on_query_hash() -> None:
    assert DATABASE_URL is not None
    repo = PostgresExactCacheRepository(DATABASE_URL)
    model = _model_name()
    embedding = (1.0, 0.0)
    first = _scoped_entry(
        f"tie-a {uuid4()}",
        "answer-a",
        embedding=embedding,
        embedding_model=model,
    )
    second = _scoped_entry(
        f"tie-b {uuid4()}",
        "answer-b",
        embedding=embedding,
        embedding_model=model,
    )
    hashes = sorted([first.query_hash, second.query_hash])
    try:
        repo.insert(first)
        repo.insert(second)
        candidates = repo.search_by_embedding(
            embedding,
            top_k=2,
            embedding_model=model,
            tenant_id=TENANT,
            namespace_id=NAMESPACE,
        )
        assert len(candidates) == 2
        assert candidates[0].similarity == pytest.approx(1.0)
        assert candidates[1].similarity == pytest.approx(1.0)
        assert candidates[0].query_hash <= candidates[1].query_hash
        assert candidates[0].query_hash == hashes[0]
    finally:
        _cleanup([first.query_hash, second.query_hash])


def test_postgres_db_returns_expired_but_semantic_path_does_not_serve_it() -> None:
    assert DATABASE_URL is not None
    expired_query = f"ws4 semantic expired winner {uuid4()}"
    fresh_query = f"ws4 semantic fresh runner-up {uuid4()}"
    probe_query = f"ws4 semantic probe wording {uuid4()}"
    model = _model_name()
    expired = _scoped_entry(
        expired_query,
        "expired-should-not-serve",
        embedding=(1.0, 0.0),
        ttl_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        metadata=QueryMetadata(intent="factual", domain="general"),
        embedding_model=model,
    )
    fresh = _scoped_entry(
        fresh_query,
        "fresh-should-serve",
        embedding=(0.99, 0.14),
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        metadata=QueryMetadata(intent="factual", domain="general"),
        embedding_model=model,
    )
    hashes = [expired.query_hash, fresh.query_hash]
    repo = ScopedPostgresExactCacheRepository(DATABASE_URL, hashes)
    try:
        repo.insert(expired)
        repo.insert(fresh)
        db_hits = repo.search_by_embedding(
            (1.0, 0.0),
            top_k=2,
            embedding_model=model,
            tenant_id=TENANT,
            namespace_id=NAMESPACE,
        )
        assert db_hits[0].normalized_query == expired_query

        embedding_client = FakeEmbeddingClient(
            config=EmbeddingConfig(model_name=model, dimension=DIM),
            vectors={probe_query: (1.0, 0.0)},
        )
        llm = MockLLMClient()
        client = TestClient(
            create_app(
                repository=repo,
                settings=Settings(database_url=DATABASE_URL),
                llm_client=llm,
                embedding_client=embedding_client,
                semantic_strategy="B",
                semantic_similarity_threshold=0.5,
            )
        )
        response = client.post("/v1/query", json={"query": probe_query})
        body = response.json()
        assert response.status_code == 200
        assert body["answer"] != "expired-should-not-serve"
        assert body.get("source") != "cache" or body["answer"] == "fresh-should-serve"
    finally:
        _cleanup(hashes)


def test_postgres_cross_namespace_candidate_not_in_scoped_search() -> None:
    assert DATABASE_URL is not None
    repo = PostgresExactCacheRepository(DATABASE_URL)
    model = _model_name()
    embedding = (1.0, 0.0)
    query = f"ws4 cross-ns {uuid4()}"
    in_scope = _scoped_entry(
        query,
        "in-scope",
        embedding=embedding,
        embedding_model=model,
    )
    out_scope = _scoped_entry(
        query,
        "out-of-scope",
        embedding=embedding,
        namespace_id="other-namespace",
        embedding_model=model,
    )
    hashes = [in_scope.query_hash, out_scope.query_hash]
    try:
        repo.insert(in_scope)
        repo.insert(out_scope)
        hits = repo.search_by_embedding(
            embedding,
            top_k=5,
            embedding_model=model,
            tenant_id=TENANT,
            namespace_id=NAMESPACE,
        )
        assert len(hits) == 1
        assert hits[0].answer == "in-scope"
    finally:
        _cleanup(hashes)
