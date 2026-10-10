"""WS8 step 3: PostgreSQL-backed failure-closed request-path behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sscre.cache import CacheEntry
from sscre.config import Settings
from sscre.llm import MockLLMClient
from sscre.postgres_failure_harness import (
    FailureInjectionConfig,
    FailureOperation,
    PostgresFailureInjectionRepository,
)
from sscre.query import hash_query
from sscre.safety import QueryMetadata
from tests.ws8_postgres_helpers import (
    DATABASE_URL,
    WS8_POSTGRES_MARKS,
    cleanup_query_hashes,
    row_exists,
    ws8_client,
)

pytestmark = WS8_POSTGRES_MARKS


def _arm_lookup_fail_once(
    config: FailureInjectionConfig,
    *,
    scenario_id: str,
) -> None:
    config.arm(
        FailureOperation.LOOKUP,
        scenario_id=scenario_id,
        event_class="simulated_drop",
        fail_once=True,
    )


def test_expired_entry_not_served_after_lookup_recovery() -> None:
    query = f"ws8 step3 expired recovery {uuid4()}"
    stale_answer = "expired postgres answer"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer=stale_answer,
        metadata=QueryMetadata(
            intent="factual",
            domain="unknown",
            output_format="prose",
        ),
        ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    repository.insert(entry)
    client = ws8_client(repository)
    _arm_lookup_fail_once(config, scenario_id="step3-expired-recovery")
    try:
        assert client.post("/v1/query", json={"query": query}).status_code == 503

        recovered = client.post("/v1/query", json={"query": query})
        body = recovered.json()

        assert recovered.status_code == 200
        assert body["source"] == "generated"
        assert body["answer"] != stale_answer
        trace = body["candidate_traces"][0]
        assert trace["reason"] == "cache_control_expired"
        assert trace["cache_control_outcome"] == "expired"
    finally:
        config.disarm()
        cleanup_query_hashes([entry.query_hash])


def test_unsafe_metadata_missing_not_served_after_lookup_recovery() -> None:
    query = f"ws8 step3 metadata missing {uuid4()}"
    unsafe_answer = "metadata-less postgres answer"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer=unsafe_answer,
        metadata=None,
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    repository.insert(entry)
    client = ws8_client(repository)
    _arm_lookup_fail_once(config, scenario_id="step3-metadata-missing-recovery")
    try:
        assert client.post("/v1/query", json={"query": query}).status_code == 503

        body = client.post("/v1/query", json={"query": query}).json()

        assert body["source"] == "generated"
        assert body["answer"] != unsafe_answer
        assert body["candidate_traces"][0]["reason"] == "candidate_metadata_missing"
    finally:
        config.disarm()
        cleanup_query_hashes([entry.query_hash])


def test_incompatible_candidate_not_served_after_lookup_recovery() -> None:
    query = f"write Python code ws8 step3 {uuid4()}"
    unsafe_answer = "java-only postgres answer"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer=unsafe_answer,
        metadata=QueryMetadata(
            intent="code",
            domain="programming",
            constraints=(("language", "java"),),
            output_format="code",
        ),
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    repository.insert(entry)
    client = ws8_client(repository)
    _arm_lookup_fail_once(config, scenario_id="step3-incompatible-recovery")
    try:
        assert client.post("/v1/query", json={"query": query}).status_code == 503

        body = client.post("/v1/query", json={"query": query}).json()

        assert body["source"] == "generated"
        assert body["decision"] == "UNSAFE"
        assert body["answer"] != unsafe_answer
        assert body["candidate_traces"][0]["reason"] == "constraint_mismatch:language"
    finally:
        config.disarm()
        cleanup_query_hashes([entry.query_hash])


def test_generation_failure_does_not_persist_entry_or_serve_cache() -> None:
    query = f"ws8 step3 gen fail {uuid4()}"
    query_hash = hash_query(query)
    client = ws8_client(
        PostgresFailureInjectionRepository(DATABASE_URL),
        llm_client=MockLLMClient(should_fail=True),
    )

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 502
    assert response.json() == {"detail": "response generation failed"}
    assert response.headers["X-Request-ID"]
    assert not row_exists(query_hash)


def test_recovery_preserves_query_validation_and_admin_authorization() -> None:
    query = f"ws8 step3 validation {uuid4()}"
    entry = CacheEntry(
        query_hash=hash_query(query),
        normalized_query=query,
        answer="validation probe",
    )
    config = FailureInjectionConfig()
    repository = PostgresFailureInjectionRepository(DATABASE_URL, config)
    repository.insert(entry)
    settings = Settings(
        database_url=DATABASE_URL,
        semantic_enabled=False,
        admin_token="ws8-step3-admin-token",
    )
    client = ws8_client(repository, settings=settings)
    _arm_lookup_fail_once(config, scenario_id="step3-validation-recovery")
    try:
        assert client.post("/v1/query", json={"query": query}).status_code == 503

        invalid = client.post("/v1/query", json={"query": ""})
        assert invalid.status_code == 422

        unauthorized = client.get("/v1/cache/stats")
        assert unauthorized.status_code == 401
        assert unauthorized.json() == {"detail": "authentication required"}
        assert unauthorized.headers["WWW-Authenticate"] == "Bearer"
    finally:
        config.disarm()
        cleanup_query_hashes([entry.query_hash])


def test_controlled_error_responses_remain_bounded() -> None:
    query = f"ws8 step3 bounded errors {uuid4()}"
    config = FailureInjectionConfig()
    lookup_repo = PostgresFailureInjectionRepository(DATABASE_URL, config)
    config.arm(FailureOperation.LOOKUP, scenario_id="step3-bounded-503")
    try:
        unavailable = ws8_client(lookup_repo).post("/v1/query", json={"query": query})
        assert set(unavailable.json().keys()) == {"detail"}
        assert unavailable.status_code == 503
    finally:
        config.disarm()

    gen_fail = ws8_client(
        PostgresFailureInjectionRepository(DATABASE_URL),
        llm_client=MockLLMClient(should_fail=True),
    ).post("/v1/query", json={"query": f"ws8 gen bounded {uuid4()}"})
    assert gen_fail.status_code == 502
    assert set(gen_fail.json().keys()) == {"detail"}
    assert gen_fail.headers["X-Request-ID"]
