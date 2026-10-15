"""Client authentication and request context for external API exposure."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from sscre.config import Settings

CLIENT_AUTH_SCHEMA = "sscre-client-auth-registry-1.0"

# Client credential scopes (`ClientAuthRegistry` only).
QUERY_EXECUTE_SCOPE = "query:execute"

# Admin bearer scopes (`SSCRE_ADMIN_*` tokens only).
CACHE_READ_SCOPE = "cache:read"
CACHE_WRITE_SCOPE = "cache:write"
HEALTH_READY_SCOPE = "health:ready"

# Reserved for future operator routes (no HTTP handlers yet).
CACHE_PURGE_SCOPE = "cache:purge"
CACHE_INSPECT_SCOPE = "cache:inspect"
CACHE_EXPORT_SCOPE = "cache:export"
EVALUATION_RUN_SCOPE = "evaluation:run"

FUTURE_ROUTE_SCOPES: dict[str, str] = {
    "POST /v1/cache/purge": CACHE_PURGE_SCOPE,
    "GET /v1/cache/entries": CACHE_INSPECT_SCOPE,
    "POST /v1/cache/export": CACHE_EXPORT_SCOPE,
    "POST /v1/evaluation/run": EVALUATION_RUN_SCOPE,
}

TRUSTED_LOCAL_PRINCIPAL = "trusted-local"
TRUSTED_LOCAL_TENANT = "trusted-local"
DEFAULT_NAMESPACE = "default"


@dataclass(frozen=True)
class RequestContext:
    """Authenticated caller context for one HTTP request."""

    request_id: UUID
    principal_id: str
    tenant_id: str
    namespace_id: str
    scopes: frozenset[str]

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


@dataclass(frozen=True)
class ClientCredentialRecord:
    principal_id: str
    token: str
    tenant_id: str
    namespace_id: str
    scopes: frozenset[str]
    expires_at: datetime | None

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("principal_id must not be empty")
        if len(self.token) < 16:
            raise ValueError("client token must be at least 16 characters")
        if not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty")
        if not self.namespace_id.strip():
            raise ValueError("namespace_id must not be empty")
        if QUERY_EXECUTE_SCOPE not in self.scopes:
            raise ValueError(f"client credentials must include {QUERY_EXECUTE_SCOPE}")


class ClientAuthError(Exception):
    """Raised when client authentication or authorization fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ClientAuthRegistry:
    credentials: tuple[ClientCredentialRecord, ...]

    def __post_init__(self) -> None:
        if not self.credentials:
            raise ValueError("client auth registry must contain credentials")

    def authenticate_bearer(
        self,
        authorization: str | None,
        *,
        settings: Settings,
        required_scope: str,
        request_id: UUID,
    ) -> RequestContext:
        presented = _parse_bearer_token(authorization)
        _reject_admin_token(presented, settings)
        now = datetime.now(timezone.utc)
        for record in self.credentials:
            if not hmac.compare_digest(presented, record.token):
                continue
            if record.expires_at is not None and now >= record.expires_at:
                raise ClientAuthError(401, "authentication expired")
            if required_scope not in record.scopes:
                raise ClientAuthError(403, "insufficient privileges")
            return RequestContext(
                request_id=request_id,
                principal_id=record.principal_id,
                tenant_id=record.tenant_id,
                namespace_id=record.namespace_id,
                scopes=record.scopes,
            )
        raise ClientAuthError(401, "invalid authentication")


def trusted_local_request_context(request_id: UUID) -> RequestContext:
    return RequestContext(
        request_id=request_id,
        principal_id=TRUSTED_LOCAL_PRINCIPAL,
        tenant_id=TRUSTED_LOCAL_TENANT,
        namespace_id=DEFAULT_NAMESPACE,
        scopes=frozenset({QUERY_EXECUTE_SCOPE}),
    )


def resolve_query_request_context(
    settings: Settings,
    registry: ClientAuthRegistry | None,
    authorization: str | None,
    request_id: UUID,
) -> RequestContext:
    if settings.api_exposure_mode == "trusted_local":
        return trusted_local_request_context(request_id)
    if registry is None:
        raise ClientAuthError(503, "client authentication unavailable")
    return registry.authenticate_bearer(
        authorization,
        settings=settings,
        required_scope=QUERY_EXECUTE_SCOPE,
        request_id=request_id,
    )


def load_client_auth_registry(path: Path) -> ClientAuthRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("client auth registry must be a JSON object")
    schema = payload.get("schema_version")
    if schema != CLIENT_AUTH_SCHEMA:
        raise ValueError(
            f"client auth registry schema_version must be {CLIENT_AUTH_SCHEMA!r}"
        )
    raw_credentials = payload.get("credentials")
    if not isinstance(raw_credentials, list) or not raw_credentials:
        raise ValueError("client auth registry credentials must be a non-empty list")
    records: list[ClientCredentialRecord] = []
    for index, item in enumerate(raw_credentials):
        if not isinstance(item, Mapping):
            raise ValueError(f"credentials[{index}] must be an object")
        scopes_raw = item.get("scopes")
        if not isinstance(scopes_raw, list) or not scopes_raw:
            raise ValueError(f"credentials[{index}].scopes must be a non-empty list")
        scopes = frozenset(str(scope) for scope in scopes_raw)
        expires_at = _parse_expires_at(item.get("expires_at"))
        token = item.get("token")
        if not isinstance(token, str):
            raise ValueError(f"credentials[{index}].token must be a string")
        principal_id = item.get("principal_id")
        tenant_id = item.get("tenant_id")
        if not isinstance(principal_id, str) or not isinstance(tenant_id, str):
            raise ValueError(
                f"credentials[{index}] requires principal_id and tenant_id strings"
            )
        namespace_raw = item.get("namespace_id", DEFAULT_NAMESPACE)
        if not isinstance(namespace_raw, str):
            raise ValueError(f"credentials[{index}].namespace_id must be a string")
        records.append(
            ClientCredentialRecord(
                principal_id=principal_id,
                token=token,
                tenant_id=tenant_id,
                namespace_id=namespace_raw,
                scopes=scopes,
                expires_at=expires_at,
            )
        )
    return ClientAuthRegistry(tuple(records))


def validate_api_exposure_configuration(settings: Settings) -> list[str]:
    errors: list[str] = []
    if settings.api_exposure_mode == "external":
        path_value = settings.client_auth_json
        if not path_value or not path_value.strip():
            errors.append(
                "SSCRE_CLIENT_AUTH_JSON is required when SSCRE_API_EXPOSURE_MODE=external"
            )
            return errors
        path = Path(path_value)
        if not path.is_file():
            errors.append(
                f"SSCRE_CLIENT_AUTH_JSON must reference an existing file ({path_value})"
            )
            return errors
        try:
            load_client_auth_registry(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"SSCRE_CLIENT_AUTH_JSON is invalid: {exc}")
    return errors


def _parse_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise ClientAuthError(401, "authentication required")
    scheme, separator, presented_token = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not presented_token
        or " " in presented_token
    ):
        raise ClientAuthError(401, "invalid authentication")
    return presented_token


def _reject_admin_token(presented_token: str, settings: Settings) -> None:
    for configured in (settings.admin_token, settings.admin_read_token):
        if configured is not None and hmac.compare_digest(
            presented_token, configured
        ):
            raise ClientAuthError(401, "invalid authentication")


def _parse_expires_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expires_at must be an ISO-8601 timestamp or null")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("expires_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("expires_at must include a timezone")
    return parsed.astimezone(timezone.utc)
