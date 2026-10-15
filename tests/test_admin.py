import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import InMemoryExactCache
from sscre.config import Settings


def _client(token: str | None = "test-admin-token") -> TestClient:
    return TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=Settings(admin_token=token),
        )
    )


def test_admin_stats_requires_authentication() -> None:
    response = _client().get("/v1/cache/stats")

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_admin_stats_rejects_malformed_and_invalid_credentials() -> None:
    client = _client()

    malformed = client.get(
        "/v1/cache/stats",
        headers={"Authorization": "Basic credentials"},
    )
    invalid = client.get(
        "/v1/cache/stats",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert malformed.status_code == 401
    assert malformed.json() == {"detail": "invalid authentication"}
    assert invalid.status_code == 401
    assert invalid.json() == {"detail": "invalid authentication"}


def test_admin_stats_accepts_valid_admin_credentials() -> None:
    response = _client().get(
        "/v1/cache/stats",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 200
    assert "storage" in response.json()


def test_admin_stats_accepts_read_only_credentials() -> None:
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=Settings(
                admin_read_token="test-read-token",
            ),
        )
    )

    response = client.get(
        "/v1/cache/stats",
        headers={"Authorization": "Bearer test-read-token"},
    )

    assert response.status_code == 200


def test_admin_stats_rejects_expired_credentials() -> None:
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=Settings(
                admin_token="test-admin-token",
                admin_token_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            ),
        )
    )

    response = client.get(
        "/v1/cache/stats",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication expired"}


def test_admin_stats_fails_closed_when_authentication_is_unconfigured() -> None:
    response = _client(token=None).get(
        "/v1/cache/stats",
        headers={"Authorization": "Bearer test-admin-token"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "admin authentication unavailable"}


def test_production_profile_rejects_default_fake_providers() -> None:
    with pytest.raises(ValueError, match="provider clients"):
        create_app(
            repository=InMemoryExactCache(),
            settings=Settings(
                runtime_profile="production",
                database_url="postgresql://localhost/sscre",
                admin_token="a-production-token",
                admin_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                api_exposure_mode="external",
                client_auth_json="registry-placeholder.json",
                rate_limit_requests_per_minute=100,
                tenant_provider_budget_per_minute=100,
            ),
        )
