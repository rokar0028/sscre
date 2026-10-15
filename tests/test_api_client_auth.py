import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from sscre.api_auth import (
    CLIENT_AUTH_SCHEMA,
    ClientAuthError,
    ClientAuthRegistry,
    ClientCredentialRecord,
    load_client_auth_registry,
)
from sscre.app import create_app
from sscre.cache import InMemoryExactCache
from sscre.config import Settings
from sscre.llm import LLMClient, LLMResult

from tests.ws2_test_fixtures import external_test_settings as _external_settings


def _registry(
    *,
    token: str = "test-client-token-16chars",
    scopes: frozenset[str] = frozenset({"query:execute"}),
    expires_at: datetime | None = None,
) -> ClientAuthRegistry:
    return ClientAuthRegistry(
        (
            ClientCredentialRecord(
                principal_id="tenant-a-client",
                token=token,
                tenant_id="tenant-a",
                namespace_id="default",
                scopes=scopes,
                expires_at=expires_at,
            ),
        )
    )


class _CountingLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, query: str) -> LLMResult:
        self.calls += 1
        return LLMResult(
            text=f"generated:{query}",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
        )


def _external_client(
    registry: ClientAuthRegistry | None = None,
    llm_client: LLMClient | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=_external_settings(),
            client_auth_registry=registry or _registry(),
            llm_client=llm_client,
        )
    )


def test_trusted_local_query_allows_anonymous_access() -> None:
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=Settings(api_exposure_mode="trusted_local"),
        )
    )

    response = client.post("/v1/query", json={"query": "hello trusted local"})

    assert response.status_code == 200


def test_external_mode_requires_client_authentication() -> None:
    llm = _CountingLLM()
    client = _external_client(llm_client=llm)

    response = client.post("/v1/query", json={"query": "needs auth"})

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication required"}
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.headers["X-Request-ID"]
    assert llm.calls == 0


def test_external_mode_accepts_valid_client_token() -> None:
    client = _external_client()

    response = client.post(
        "/v1/query",
        json={"query": "authorized query"},
        headers={"Authorization": "Bearer test-client-token-16chars"},
    )

    assert response.status_code == 200


def test_external_mode_rejects_admin_token_on_query() -> None:
    llm = _CountingLLM()
    client = TestClient(
        create_app(
            repository=InMemoryExactCache(),
            settings=Settings(
                api_exposure_mode="external",
                client_auth_json="registry-placeholder.json",
                admin_token="test-admin-token-16chars",
                rate_limit_requests_per_minute=1000,
                tenant_provider_budget_per_minute=1000,
            ),
            client_auth_registry=_registry(),
            llm_client=llm,
        )
    )

    response = client.post(
        "/v1/query",
        json={"query": "admin must not work"},
        headers={"Authorization": "Bearer test-admin-token-16chars"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid authentication"}
    assert llm.calls == 0


def test_external_mode_rejects_expired_client_token() -> None:
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    client = _external_client(
        registry=_registry(expires_at=expired),
    )

    response = client.post(
        "/v1/query",
        json={"query": "expired"},
        headers={"Authorization": "Bearer test-client-token-16chars"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "authentication expired"}


def test_external_mode_create_app_fails_without_registry(tmp_path: Path) -> None:
    missing = tmp_path / "missing-client-auth.json"
    with pytest.raises(ValueError, match="client auth registry"):
        create_app(
            settings=Settings(
                api_exposure_mode="external",
                client_auth_json=str(missing),
                rate_limit_requests_per_minute=10,
                tenant_provider_budget_per_minute=10,
            ),
        )


def test_settings_external_mode_requires_client_auth_json() -> None:
    with pytest.raises(ValueError, match="client_auth_json"):
        Settings(api_exposure_mode="external")


def test_load_client_auth_registry_from_file(tmp_path: Path) -> None:
    path = tmp_path / "client-auth.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CLIENT_AUTH_SCHEMA,
                "credentials": [
                    {
                        "principal_id": "file-client",
                        "token": "file-client-token-16",
                        "tenant_id": "tenant-file",
                        "namespace_id": "ns",
                        "scopes": ["query:execute"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    registry = load_client_auth_registry(path)

    context = registry.authenticate_bearer(
        "Bearer file-client-token-16",
        settings=Settings(),
        required_scope="query:execute",
        request_id=uuid4(),
    )

    assert context.tenant_id == "tenant-file"
    assert context.namespace_id == "ns"


def test_client_auth_registry_insufficient_scope() -> None:
    registry = _registry(scopes=frozenset({"query:execute"}))

    with pytest.raises(ClientAuthError) as exc_info:
        registry.authenticate_bearer(
            "Bearer test-client-token-16chars",
            settings=Settings(),
            required_scope="cache:write",
            request_id=uuid4(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "insufficient privileges"
