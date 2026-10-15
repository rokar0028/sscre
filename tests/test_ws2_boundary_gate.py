"""Workstream 2 Step 2.8 — boundary verification helpers (in-memory gate)."""

from pathlib import Path

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.config import Settings
from sscre.query import CacheScope, scoped_cache_key
from tests.test_api_client_auth import _CountingLLM, _registry
from tests.ws2_test_fixtures import external_test_settings as _external_settings

_REPO_ROOT = Path(__file__).resolve().parents[1]

_STEP28_INVENTORY_PATHS = (
    "tests/test_ws2_boundary_gate.py",
    "tests/test_api_client_auth.py",
    "tests/test_api_route_authorization.py",
    "tests/test_api_abuse_controls.py",
    "tests/test_admin.py",
    "tests/test_health.py",
    "tests/test_cache_scope.py",
    "tests/test_cache_scope_enforcement.py",
    "tests/test_postgres_cache_scope.py",
    "tests/test_postgres_eviction_scope.py",
    "tests/test_postgres_integration.py",
    "tests/test_postgres_contention.py",
    "migrations/012_cache_tenant_namespace.sql",
    "migrations/013_cache_scoped_identity.sql",
    "scripts/ws2_step28_verify.py",
)


def test_step28_inventory_paths_exist() -> None:
    missing = [
        path for path in _STEP28_INVENTORY_PATHS if not (_REPO_ROOT / path).is_file()
    ]
    assert not missing, f"missing Step 2.8 inventory paths: {missing}"


def test_cross_tenant_cached_answer_not_served_to_other_tenant() -> None:
    llm = _CountingLLM()
    cache = InMemoryExactCache(require_scoped_operations=True)
    query = "shared gate isolation wording"
    cache.insert(
        CacheEntry(
            query_hash=scoped_cache_key(CacheScope("tenant-b", "default"), query),
            normalized_query=query,
            answer="tenant-b-secret",
            tenant_id="tenant-b",
            namespace_id="default",
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            settings=_external_settings(),
            client_auth_registry=_registry(),
            llm_client=llm,
            semantic_enabled=False,
        )
    )
    response = client.post(
        "/v1/query",
        json={"query": query},
        headers={"Authorization": "Bearer test-client-token-16chars"},
    )
    assert response.status_code == 200
    assert response.json()["answer"] != "tenant-b-secret"
    assert llm.calls == 1


def test_rejected_external_query_includes_request_id_and_no_provider() -> None:
    llm = _CountingLLM()
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=_external_settings(),
            client_auth_registry=_registry(),
            llm_client=llm,
        )
    )
    response = client.post("/v1/query", json={"query": "blocked"})
    assert response.status_code == 401
    assert response.headers.get("X-Request-ID")
    assert llm.calls == 0


def test_health_response_has_no_infrastructure_fields() -> None:
    client = TestClient(
        create_app(
            settings=Settings(api_exposure_mode="trusted_local"),
        )
    )
    body = client.get("/health").json()
    assert body == {"status": "ok"}
    assert "repository" not in body
    assert "database" not in body
