"""Shared helpers for opt-in WS8 PostgreSQL operational tests.

Requires ``SSCRE_DATABASE_URL`` and up-to-date migrations (``sscre-migrate``)
before running ``pytest -m ws8_postgres_failure_recovery``,
``pytest -m ws8_postgres_multiprocess``,
``pytest -m ws8_postgres_contention``, or
``pytest -m ws8_postgres_load``.
"""

from __future__ import annotations

import os

import psycopg
import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.config import Settings
from sscre.llm import MockLLMClient
from sscre.postgres_failure_harness import PostgresFailureInjectionRepository

DATABASE_URL = os.getenv("SSCRE_DATABASE_URL")

_SKIP_NO_DATABASE = pytest.mark.skipif(
    not DATABASE_URL,
    reason="SSCRE_DATABASE_URL is required for WS8 PostgreSQL tests",
)

WS8_POSTGRES_MARKS = [
    pytest.mark.ws8_postgres_failure_recovery,
    _SKIP_NO_DATABASE,
]

WS8_MULTIPROCESS_MARKS = [
    pytest.mark.ws8_postgres_multiprocess,
    _SKIP_NO_DATABASE,
]

WS8_CONTENTION_MARKS = [
    pytest.mark.ws8_postgres_contention,
    _SKIP_NO_DATABASE,
]

WS8_LOAD_MARKS = [
    pytest.mark.ws8_postgres_load,
    _SKIP_NO_DATABASE,
]


def cleanup_query_hashes(query_hashes: list[str]) -> None:
    assert DATABASE_URL is not None
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


def row_exists(query_hash: str) -> bool:
    return count_rows_for_query_hash(query_hash) > 0


def count_rows_for_query_hash(query_hash: str) -> int:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM cache_entries WHERE query_hash = %s",
                (query_hash,),
            )
            row = cursor.fetchone()
            return int(row[0]) if row is not None else 0


def count_all_cache_entries() -> int:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM cache_entries")
            row = cursor.fetchone()
            return int(row[0]) if row is not None else 0


def ws8_client(
    repository: PostgresFailureInjectionRepository,
    *,
    semantic_strategy: str = "C",
    semantic_enabled: bool = False,
    settings: Settings | None = None,
    llm_client: MockLLMClient | None = None,
) -> TestClient:
    """Test client with explicit strategy (default C). Use strategy B for exact cache-hit probes without compatibility metadata."""
    assert DATABASE_URL is not None
    resolved_settings = settings or Settings(
        database_url=DATABASE_URL,
        semantic_enabled=semantic_enabled,
        semantic_strategy=semantic_strategy,  # type: ignore[arg-type]
    )
    return TestClient(
        create_app(
            repository=repository,
            settings=resolved_settings,
            llm_client=llm_client or MockLLMClient(),
            semantic_strategy=semantic_strategy,
            semantic_enabled=semantic_enabled,
        )
    )
