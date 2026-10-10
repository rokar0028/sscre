"""WS8 protocol ws8-failure-recovery-v1 (opt-in PostgreSQL failure/recovery harness)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sscre.cache import CacheEntry, CacheRepositoryError
from sscre.query import hash_query
from sscre.postgres_cache import PostgresExactCacheRepository
from sscre.postgres_failure_harness import (
    WS8_LIVE_RESTART_ENV,
    FailureInjectionConfig,
    FailureOperation,
    PostgresFailureInjectionRepository,
    live_postgres_restart_enabled,
    restart_postgres_container,
)
from tests.ws8_postgres_helpers import (
    DATABASE_URL,
    WS8_POSTGRES_MARKS,
    cleanup_query_hashes,
    row_exists,
    ws8_client,
)

pytestmark = WS8_POSTGRES_MARKS


def test_fr_lookup_drop_fails_closed_without_cache_hit() -> None:
    """Scenario FR-lookup-drop: simulated connection loss on lookup."""
    query = f"ws8 lookup drop {uuid4()}"
    cached_answer = "seeded answer must not appear in error response"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer=cached_answer,
    )
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    repository.insert(entry)
    config.arm(
        FailureOperation.LOOKUP,
        scenario_id="FR-lookup-drop",
        event_class="simulated_drop",
    )
    try:
        response = ws8_client(repository).post("/v1/query", json={"query": query})

        body = response.json()
        assert response.status_code == 503
        assert body == {"detail": "cache unavailable"}
        assert response.headers["X-Request-ID"]
        assert cached_answer not in str(body)
        assert config.events[-1]["event_class"] == "simulated_drop"
        assert config.events[-1]["scenario_id"] == "FR-lookup-drop"
    finally:
        config.disarm()
        cleanup_query_hashes([entry.query_hash])


def test_fr_lookup_repository_failure_labeled_separately() -> None:
    """Scenario FR-lookup-simulated-failure: not a live container/process restart."""
    query = f"ws8 lookup repo failure {uuid4()}"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer="seeded answer",
    )
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    repository.insert(entry)
    config.arm(
        FailureOperation.LOOKUP,
        scenario_id="FR-lookup-simulated-failure",
        event_class="simulated_repository_failure",
    )
    try:
        response = ws8_client(repository).post("/v1/query", json={"query": query})

        assert response.status_code == 503
        assert config.events[-1]["event_class"] == "simulated_repository_failure"
    finally:
        config.disarm()
        cleanup_query_hashes([entry.query_hash])


def test_fr_gen_persist_insert_failure_does_not_persist() -> None:
    """Scenario FR-gen-persist: generation succeeds, insert fails."""
    query = f"ws8 gen persist {uuid4()}"
    query_hash = hash_query(query)
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    config.arm(
        FailureOperation.INSERT_AND_EVICT,
        scenario_id="FR-gen-persist",
        event_class="simulated_drop",
    )
    try:
        response = ws8_client(repository).post("/v1/query", json={"query": query})

        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "generated"
        assert not row_exists(query_hash)
        assert config.events[-1]["operation"] == "insert_and_evict"
    finally:
        config.disarm()


def test_fr_insert_failure_returns_generated_without_persist() -> None:
    """Scenario FR-insert: failure during insert on miss path."""
    query = f"ws8 insert fail {uuid4()}"
    query_hash = hash_query(query)
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    config.arm(
        FailureOperation.INSERT,
        FailureOperation.INSERT_AND_EVICT,
        scenario_id="FR-insert",
        event_class="simulated_repository_failure",
    )
    try:
        response = ws8_client(repository).post("/v1/query", json={"query": query})

        assert response.status_code == 200
        assert response.json()["source"] == "generated"
        assert not row_exists(query_hash)
    finally:
        config.disarm()


def test_fr_cleanup_failure_raises_and_leaves_expired_row() -> None:
    """Scenario FR-cleanup: cleanup reports repository failure; row remains."""
    query = f"ws8 cleanup fail {uuid4()}"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer="expired cleanup answer",
        ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    repository.insert(entry)
    config.arm(
        FailureOperation.CLEANUP,
        scenario_id="FR-cleanup",
        event_class="simulated_drop",
    )
    try:
        with pytest.raises(CacheRepositoryError, match="cleanup"):
            repository.cleanup_expired(
                limit=10,
                only_query_hashes=[entry.query_hash],
            )

        assert row_exists(entry.query_hash)
        assert config.events[-1]["scenario_id"] == "FR-cleanup"
    finally:
        config.disarm()
        cleanup_query_hashes([entry.query_hash])


def test_fr_recovery_after_failure_restore() -> None:
    """Scenario FR-recovery: lookup fails once, then serves cache after disarm."""
    query = f"ws8 recovery {uuid4()}"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer="recovery seeded answer",
    )
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    repository.insert(entry)
    client = ws8_client(repository, semantic_strategy="B")
    config.arm(
        FailureOperation.LOOKUP,
        scenario_id="FR-recovery",
        event_class="simulated_drop",
        fail_once=True,
    )
    try:
        failed = client.post("/v1/query", json={"query": query})
        assert failed.status_code == 503

        recovered = client.post("/v1/query", json={"query": query})
        assert recovered.status_code == 200
        assert recovered.json()["source"] == "cache"
    finally:
        config.disarm()
        cleanup_query_hashes([entry.query_hash])


@pytest.mark.skipif(
    not live_postgres_restart_enabled(),
    reason=f"Set {WS8_LIVE_RESTART_ENV}=1 for live container restart",
)
def test_fr_live_container_restart_recovery() -> None:
    """Optional live FR-recovery using real ``docker compose restart postgres``."""
    query = f"ws8 live restart {uuid4()}"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer="live restart seeded answer",
    )
    repo = PostgresExactCacheRepository(DATABASE_URL)
    repo.insert(entry)
    try:
        restart_meta = restart_postgres_container(database_url=DATABASE_URL)
        assert restart_meta["event_class"] == "container_restart"

        client = ws8_client(
            PostgresFailureInjectionRepository(DATABASE_URL),
            semantic_strategy="B",
        )
        response = client.post("/v1/query", json={"query": query})
        assert response.status_code == 200
        assert response.json()["source"] == "cache"
    finally:
        cleanup_query_hashes([entry.query_hash])
