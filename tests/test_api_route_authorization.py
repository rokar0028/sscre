"""Workstream 2 Step 2.6 — route authorization and operational exposure."""

import pytest
from fastapi.testclient import TestClient

from sscre.api_auth import (
    ClientCredentialRecord,
    HEALTH_READY_SCOPE,
    QUERY_EXECUTE_SCOPE,
)
from sscre.app import create_app
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.config import Settings
from sscre.query import CacheScope, scoped_cache_key
from tests.test_api_client_auth import _external_client, _registry


def test_external_ready_requires_health_probe_scope() -> None:
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=Settings(
                api_exposure_mode="external",
                client_auth_json="registry-placeholder.json",
                admin_read_token="probe-token-16-chars-min",
                rate_limit_requests_per_minute=1000,
                tenant_provider_budget_per_minute=1000,
            ),
            client_auth_registry=_registry(),
        )
    )

    unauthorized = client.get("/ready")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"detail": "authentication required"}

    authorized = client.get(
        "/ready",
        headers={"Authorization": "Bearer probe-token-16-chars-min"},
    )
    assert authorized.status_code == 200
    assert authorized.json() == {"status": "ready", "repository": "memory"}


def test_external_health_stays_unauthenticated_and_minimal() -> None:
    client = _external_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert set(response.json()) == {"status"}


def test_client_credentials_must_include_query_execute_scope() -> None:
    with pytest.raises(ValueError, match=QUERY_EXECUTE_SCOPE):
        ClientCredentialRecord(
            principal_id="wrong-scope",
            token="scope-test-token-16c",
            tenant_id="tenant-a",
            namespace_id="default",
            scopes=frozenset({"cache:read"}),
            expires_at=None,
        )


def test_admin_cache_stats_supports_explicit_tenant_scope() -> None:
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=scoped_cache_key(CacheScope("tenant-stats", "default"), "one"),
            normalized_query="one",
            answer="a",
            tenant_id="tenant-stats",
            namespace_id="default",
        )
    )
    cache.insert(
        CacheEntry(
            query_hash=scoped_cache_key(CacheScope("tenant-other", "default"), "two"),
            normalized_query="two",
            answer="b",
            tenant_id="tenant-other",
            namespace_id="default",
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            settings=Settings(admin_token="admin-stats-token-16"),
        )
    )
    headers = {"Authorization": "Bearer admin-stats-token-16"}

    platform = client.get("/v1/cache/stats", headers=headers)
    scoped = client.get(
        "/v1/cache/stats",
        headers=headers,
        params={"tenant_id": "tenant-stats", "namespace_id": "default"},
    )
    partial = client.get(
        "/v1/cache/stats",
        headers=headers,
        params={"tenant_id": "tenant-stats"},
    )

    assert platform.status_code == 200
    assert platform.json()["scope"] == "platform"
    assert platform.json()["storage"]["entries"] == 2
    assert scoped.status_code == 200
    assert scoped.json()["scope"] == "tenant_namespace"
    assert scoped.json()["storage"]["entries"] == 1
    assert partial.status_code == 422


def test_admin_ready_probe_uses_health_ready_scope_constant() -> None:
    assert HEALTH_READY_SCOPE == "health:ready"
