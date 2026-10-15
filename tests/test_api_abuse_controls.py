"""Workstream 2 Step 2.7 — API abuse controls."""

import pytest
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor

from sscre.api_abuse_controls import AbuseControlError, InProcessAbuseController
from sscre.app import create_app
from sscre.cache import InMemoryExactCache
from sscre.config import Settings
from tests.test_api_client_auth import _CountingLLM, _external_client, _registry
from tests.ws2_test_fixtures import external_test_settings as _external_settings


def test_external_settings_reject_disabled_rate_limits() -> None:
    with pytest.raises(ValueError, match="rate_limit_requests_per_minute"):
        Settings(
            api_exposure_mode="external",
            client_auth_json="registry.json",
            tenant_provider_budget_per_minute=10,
        )


def test_request_body_limit_rejects_oversized_content_length() -> None:
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=_external_settings(
                rate_limit_requests_per_minute=2,
                tenant_provider_budget_per_minute=1,
                tenant_max_concurrent_queries=1,
                max_request_body_bytes=256,
            ),
            client_auth_registry=_registry(),
            llm_client=_CountingLLM(),
        )
    )
    headers = {
        "Authorization": "Bearer test-client-token-16chars",
        "Content-Length": "9999",
    }
    response = client.post(
        "/v1/query",
        content=b"x" * 9999,
        headers=headers,
    )
    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}


def test_rate_limit_returns_429_without_provider_calls() -> None:
    llm = _CountingLLM()
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=_external_settings(
                rate_limit_requests_per_minute=1,
                tenant_provider_budget_per_minute=10,
            ),
            client_auth_registry=_registry(),
            llm_client=llm,
        )
    )
    headers = {"Authorization": "Bearer test-client-token-16chars"}

    first = client.post("/v1/query", json={"query": "one"}, headers=headers)
    second = client.post("/v1/query", json={"query": "two"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {"detail": "rate limit exceeded"}
    assert "Retry-After" in second.headers
    assert llm.calls == 1


def test_provider_budget_blocks_second_generation() -> None:
    llm = _CountingLLM()
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=_external_settings(
                rate_limit_requests_per_minute=10,
                tenant_provider_budget_per_minute=1,
            ),
            client_auth_registry=_registry(),
            llm_client=llm,
            semantic_enabled=False,
        )
    )
    headers = {"Authorization": "Bearer test-client-token-16chars"}

    first = client.post("/v1/query", json={"query": "first"}, headers=headers)
    second = client.post("/v1/query", json={"query": "second"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json() == {"detail": "provider budget exceeded"}
    assert llm.calls == 1


def test_provider_budget_admission_is_atomic_under_concurrency() -> None:
    controller = InProcessAbuseController.from_settings(
        _external_settings(tenant_provider_budget_per_minute=1)
    )

    def admit() -> bool:
        try:
            controller.admit_provider_work("tenant-a")
        except AbuseControlError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        admitted = list(executor.map(lambda _: admit(), range(8)))

    assert sum(admitted) == 1


def test_invalid_json_does_not_invoke_provider() -> None:
    llm = _CountingLLM()
    client = _external_client(llm_client=llm)
    response = client.post(
        "/v1/query",
        content=b"{not-json",
        headers={
            "Authorization": "Bearer test-client-token-16chars",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 422
    assert llm.calls == 0


def test_tenant_concurrency_limit_is_enforced_per_tenant() -> None:
    controller = InProcessAbuseController.from_settings(
        _external_settings(tenant_max_concurrent_queries=1)
    )
    controller.acquire_tenant_slot("tenant-a")
    with pytest.raises(AbuseControlError, match="concurrency"):
        controller.acquire_tenant_slot("tenant-a")
    controller.release_tenant_slot("tenant-a")
    controller.acquire_tenant_slot("tenant-a")
    controller.release_tenant_slot("tenant-a")
