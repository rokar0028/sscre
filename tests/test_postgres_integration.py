import hashlib
import os
from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, DuplicateCacheEntryError
from sscre.config import Settings
from sscre.llm import MockLLMClient
from sscre.postgres_cache import PostgresExactCacheRepository


DATABASE_URL = os.getenv("SSCRE_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="SSCRE_DATABASE_URL is required for PostgreSQL integration tests",
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
    query = cache_entry.normalized_query
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
