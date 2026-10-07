import hashlib
import os
from datetime import datetime, timedelta, timezone
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, CacheRepositoryError, DuplicateCacheEntryError
from sscre.config import Settings
from sscre.llm import MockLLMClient
from sscre.postgres_cache import PostgresExactCacheRepository


DATABASE_URL = os.getenv("SSCRE_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="SSCRE_DATABASE_URL is required for PostgreSQL integration tests",
)


def _cleanup_query_hashes(query_hashes: list[str]) -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM cache_entries WHERE query_hash = ANY(%s)",
                (query_hashes,),
            )
            cursor.execute(
                """
                DELETE FROM canonical_answers AS ca
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM cache_entries
                    WHERE canonical_answer_hash = ca.answer_hash
                )
                """
            )


@pytest.fixture
def cache_entry() -> CacheEntry:
    normalized_query = f"integration query {uuid4()}"
    return CacheEntry(
        query_hash=hashlib.sha256(normalized_query.encode()).hexdigest(),
        normalized_query=normalized_query,
        answer="integration answer",
    )


@pytest.fixture
def repository(cache_entry: CacheEntry) -> Iterator[PostgresExactCacheRepository]:
    repository = PostgresExactCacheRepository(DATABASE_URL)
    yield repository
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM cache_entries WHERE query_hash = %s",
                (cache_entry.query_hash,),
            )


def test_insert_and_exact_lookup(
    repository: PostgresExactCacheRepository,
    cache_entry: CacheEntry,
) -> None:
    repository.insert(cache_entry)

    assert repository.get_by_query_hash(cache_entry.query_hash) == cache_entry


def test_embedding_round_trip(
    repository: PostgresExactCacheRepository,
    cache_entry: CacheEntry,
) -> None:
    entry = CacheEntry(
        query_hash=cache_entry.query_hash,
        normalized_query=cache_entry.normalized_query,
        answer=cache_entry.answer,
        embedding=(0.1, -0.2),
        embedding_model="test-embedding",
        embedding_dimension=2,
    )

    repository.insert(entry)

    assert repository.get_by_query_hash(entry.query_hash) == entry


def test_top_k_embedding_search_returns_ranked_candidates(
    repository: PostgresExactCacheRepository,
) -> None:
    entries = [
        CacheEntry(
            query_hash=hashlib.sha256(b"vector near").hexdigest(),
            normalized_query="vector near",
            answer="near answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
        ),
        CacheEntry(
            query_hash=hashlib.sha256(b"vector far").hexdigest(),
            normalized_query="vector far",
            answer="far answer",
            embedding=(0.0, 1.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
        ),
    ]
    try:
        for entry in entries:
            repository.insert(entry)

        candidates = repository.search_by_embedding((1.0, 0.0), top_k=1)

        assert len(candidates) == 1
        assert candidates[0].query_hash == entries[0].query_hash
        assert candidates[0].similarity == pytest.approx(1.0)
    finally:
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM cache_entries WHERE query_hash = ANY(%s)",
                    ([entry.query_hash for entry in entries],),
                )


def test_missing_hash_returns_none(
    repository: PostgresExactCacheRepository,
) -> None:
    missing_hash = hashlib.sha256(b"missing integration query").hexdigest()

    assert repository.get_by_query_hash(missing_hash) is None


def test_duplicate_hash_is_rejected(
    repository: PostgresExactCacheRepository,
    cache_entry: CacheEntry,
) -> None:
    repository.insert(cache_entry)

    with pytest.raises(DuplicateCacheEntryError):
        repository.insert(cache_entry)


def test_invalid_query_hash_is_rejected_by_database(
    repository: PostgresExactCacheRepository,
) -> None:
    entry = CacheEntry(
        query_hash="not-a-sha256-hash",
        normalized_query=f"invalid hash query {uuid4()}",
        answer="answer",
    )

    with pytest.raises(CacheRepositoryError):
        repository.insert(entry)


def test_parameterized_sql_like_text_is_stored_safely(
    repository: PostgresExactCacheRepository,
    cache_entry: CacheEntry,
) -> None:
    entry = CacheEntry(
        query_hash=cache_entry.query_hash,
        normalized_query="Robert'); DROP TABLE cache_entries; --",
        answer="It remains plain text.",
    )

    repository.insert(entry)

    assert repository.get_by_query_hash(entry.query_hash) == entry


def test_api_reads_persisted_entry_across_app_instances(
    cache_entry: CacheEntry,
) -> None:
    settings = Settings(database_url=DATABASE_URL)
    query = f"Write Python code for binary search {uuid4()}"
    first_client = TestClient(create_app(settings=settings))
    second_client = TestClient(create_app(settings=settings))

    first = first_client.post("/v1/query", json={"query": query})
    second = second_client.post("/v1/query", json={"query": query})

    assert first.json()["source"] == "generated"
    assert second.json()["source"] == "cache"

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM cache_entries WHERE query_hash = %s",
                (cache_entry.query_hash,),
            )


def test_generation_failure_does_not_persist_an_entry() -> None:
    query = f"failed generation query {uuid4()}"
    query_hash = hashlib.sha256(query.encode()).hexdigest()
    settings = Settings(database_url=DATABASE_URL)
    client = TestClient(
        create_app(
            settings=settings,
            llm_client=MockLLMClient(should_fail=True),
        )
    )

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 502
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM cache_entries WHERE query_hash = %s",
                (query_hash,),
            )
            assert cursor.fetchone() is None


def test_canonical_answer_deduplication_and_lifecycle_stats(
    repository: PostgresExactCacheRepository,
) -> None:
    queries = [f"dedup integration query {uuid4()}-{index}" for index in range(2)]
    entries = [
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="same canonical integration answer",
        )
        for query in queries
    ]
    try:
        before = repository.storage_stats()
        repository.insert(entries[0])
        repository.insert(entries[1])
        repository.record_hit(entries[0].query_hash)
        after = repository.storage_stats()

        assert after.entries == before.entries + 2
        assert after.canonical_answers == before.canonical_answers + 1
        assert after.deduplication_hits >= before.deduplication_hits + 1
        assert after.deduplication_savings_bytes > (
            before.deduplication_savings_bytes
        )
    finally:
        _cleanup_query_hashes([entry.query_hash for entry in entries])


def test_postgres_search_returns_expired_candidates(
    repository: PostgresExactCacheRepository,
) -> None:
    expired_query = f"expired vector query {uuid4()}"
    fresh_query = f"fresh vector query {uuid4()}"
    entries = [
        CacheEntry(
            query_hash=hashlib.sha256(expired_query.encode()).hexdigest(),
            normalized_query=expired_query,
            answer="expired vector answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
        CacheEntry(
            query_hash=hashlib.sha256(fresh_query.encode()).hexdigest(),
            normalized_query=fresh_query,
            answer="fresh vector answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
    ]
    try:
        for entry in entries:
            repository.insert(entry)

        candidates = repository.search_by_embedding(
            (1.0, 0.0),
            top_k=10,
            embedding_model="test-embedding",
        )

        assert expired_query in {
            candidate.normalized_query for candidate in candidates
        }
        assert fresh_query in {
            candidate.normalized_query for candidate in candidates
        }
    finally:
        _cleanup_query_hashes([entry.query_hash for entry in entries])


def test_cleanup_expired_removes_entry_and_updates_counter(
    repository: PostgresExactCacheRepository,
) -> None:
    query = f"cleanup integration query {uuid4()}"
    entry = CacheEntry(
        query_hash=hashlib.sha256(query.encode()).hexdigest(),
        normalized_query=query,
        answer="cleanup answer",
        ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    try:
        before = repository.storage_stats()
        repository.insert(entry)

        assert repository.cleanup_expired(limit=10) >= 1
        assert repository.get_by_query_hash(entry.query_hash) is None
        after = repository.storage_stats()
        assert after.expirations >= before.expirations + 1
    finally:
        _cleanup_query_hashes([entry.query_hash])


def test_insert_and_evict_enforces_postgres_entry_cap(
    repository: PostgresExactCacheRepository,
) -> None:
    entries = [
        CacheEntry(
            query_hash=hashlib.sha256(
                f"cap integration query {uuid4()}".encode()
            ).hexdigest(),
            normalized_query=f"cap integration query {uuid4()}",
            answer=f"cap answer {index}",
        )
        for index in range(2)
    ]
    try:
        for entry in entries:
            repository.insert_and_evict(entry, max_entries=1, max_bytes=100_000)

        assert repository.storage_stats().entries <= 1
    finally:
        _cleanup_query_hashes([entry.query_hash for entry in entries])
