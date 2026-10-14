import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sscre.cache_controls import CacheControlPolicy, CacheSizeLimits


def _environment_bool(name: str, default: str) -> bool:
    value = os.getenv(name, default).lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value == "true"


def _environment_datetime(name: str) -> datetime | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Settings:
    database_url: str | None = None
    runtime_profile: Literal["test", "development", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    semantic_enabled: bool = True
    semantic_strategy: Literal["B", "C"] = "C"
    semantic_top_k: int = 5
    semantic_similarity_threshold: float = 0.95
    stable_ttl_seconds: int = 30 * 24 * 60 * 60
    semi_dynamic_ttl_seconds: int = 24 * 60 * 60
    dynamic_ttl_seconds: int | None = None
    allow_dynamic_entries: bool = False
    max_answer_bytes: int = 64 * 1024
    max_metadata_bytes: int = 8 * 1024
    max_query_bytes: int = 32 * 1024
    max_cache_entries: int = 10_000
    max_cache_bytes: int = 100_000_000
    request_timeout_seconds: int = 30
    embedding_timeout_seconds: int = 5
    generation_timeout_seconds: int = 25
    repository_timeout_seconds: int = 2
    health_timeout_seconds: int = 1
    admin_timeout_seconds: int = 5
    admin_token: str | None = None
    admin_read_token: str | None = None
    admin_token_expires_at: datetime | None = None
    admin_read_token_expires_at: datetime | None = None
    api_exposure_mode: Literal["trusted_local", "external"] = "trusted_local"
    client_auth_json: str | None = None
    max_request_body_bytes: int = 64 * 1024
    rate_limit_requests_per_minute: int = 0
    tenant_max_concurrent_queries: int = 32
    tenant_provider_budget_per_minute: int = 0

    def __post_init__(self) -> None:
        if self.runtime_profile not in {"test", "development", "production"}:
            raise ValueError(
                "runtime_profile must be test, development, or production"
            )
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(
                "log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL"
            )
        if self.runtime_profile == "production":
            if not self.database_url:
                raise ValueError("database_url is required in production")
            if self.admin_token is None:
                raise ValueError("admin_token is required in production")
            if len(self.admin_token) < 16:
                raise ValueError("admin_token must be at least 16 characters")
            if self.admin_token_expires_at is None:
                raise ValueError("admin_token_expires_at is required in production")
        if self.semantic_strategy not in {"B", "C"}:
            raise ValueError("semantic_strategy must be B or C")
        if self.semantic_top_k <= 0:
            raise ValueError("semantic_top_k must be positive")
        if not -1.0 <= self.semantic_similarity_threshold <= 1.0:
            raise ValueError(
                "semantic_similarity_threshold must be between -1 and 1"
            )
        if self.stable_ttl_seconds <= 0:
            raise ValueError("stable_ttl_seconds must be positive")
        if self.semi_dynamic_ttl_seconds <= 0:
            raise ValueError("semi_dynamic_ttl_seconds must be positive")
        if self.dynamic_ttl_seconds is not None and self.dynamic_ttl_seconds <= 0:
            raise ValueError("dynamic_ttl_seconds must be positive")
        self.cache_control_policy()
        self.cache_size_limits()
        if self.max_cache_entries <= 0:
            raise ValueError("max_cache_entries must be positive")
        if self.max_cache_bytes <= 0:
            raise ValueError("max_cache_bytes must be positive")
        for name, value in (
            ("request_timeout_seconds", self.request_timeout_seconds),
            ("embedding_timeout_seconds", self.embedding_timeout_seconds),
            ("generation_timeout_seconds", self.generation_timeout_seconds),
            ("repository_timeout_seconds", self.repository_timeout_seconds),
            ("health_timeout_seconds", self.health_timeout_seconds),
            ("admin_timeout_seconds", self.admin_timeout_seconds),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.admin_token is not None and not self.admin_token.strip():
            raise ValueError("admin_token must not be blank")
        if (
            self.admin_read_token is not None
            and not self.admin_read_token.strip()
        ):
            raise ValueError("admin_read_token must not be blank")
        if (
            self.admin_token is not None
            and self.admin_read_token is not None
            and self.admin_token == self.admin_read_token
        ):
            raise ValueError("admin tokens must be distinct")
        for name, value in (
            ("admin_token_expires_at", self.admin_token_expires_at),
            ("admin_read_token_expires_at", self.admin_read_token_expires_at),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must include a timezone")
        if self.api_exposure_mode not in {"trusted_local", "external"}:
            raise ValueError("api_exposure_mode must be trusted_local or external")
        if self.api_exposure_mode == "external" and not (
            self.client_auth_json and self.client_auth_json.strip()
        ):
            raise ValueError(
                "client_auth_json is required when api_exposure_mode is external"
            )
        if self.max_request_body_bytes <= 0:
            raise ValueError("max_request_body_bytes must be positive")
        if self.tenant_max_concurrent_queries <= 0:
            raise ValueError("tenant_max_concurrent_queries must be positive")
        if self.api_exposure_mode == "external":
            if self.rate_limit_requests_per_minute <= 0:
                raise ValueError(
                    "rate_limit_requests_per_minute must be positive in external mode"
                )
            if self.tenant_provider_budget_per_minute <= 0:
                raise ValueError(
                    "tenant_provider_budget_per_minute must be positive in external mode"
                )

    def require_scoped_cache_operations(self) -> bool:
        """External API exposure requires explicit tenant/namespace predicates."""
        return self.api_exposure_mode == "external"

    def cache_control_policy(self) -> CacheControlPolicy:
        return CacheControlPolicy(
            stable_ttl=timedelta(seconds=self.stable_ttl_seconds),
            semi_dynamic_ttl=timedelta(seconds=self.semi_dynamic_ttl_seconds),
            dynamic_ttl=(
                timedelta(seconds=self.dynamic_ttl_seconds)
                if self.dynamic_ttl_seconds is not None
                else None
            ),
            allow_dynamic_entries=self.allow_dynamic_entries,
        )

    def cache_size_limits(self) -> CacheSizeLimits:
        return CacheSizeLimits(
            max_answer_bytes=self.max_answer_bytes,
            max_metadata_bytes=self.max_metadata_bytes,
            max_query_bytes=self.max_query_bytes,
        )

    @classmethod
    def from_environment(cls) -> "Settings":
        raw_enabled = os.getenv("SSCRE_SEMANTIC_ENABLED", "true").lower()
        if raw_enabled not in {"true", "false"}:
            raise ValueError("SSCRE_SEMANTIC_ENABLED must be true or false")
        return cls(
            database_url=os.getenv("SSCRE_DATABASE_URL"),
            runtime_profile=os.getenv("SSCRE_RUNTIME_PROFILE", "development"),
            log_level=os.getenv("SSCRE_LOG_LEVEL", "INFO").upper(),
            semantic_enabled=raw_enabled == "true",
            semantic_strategy=os.getenv("SSCRE_SEMANTIC_STRATEGY", "C"),
            semantic_top_k=int(os.getenv("SSCRE_SEMANTIC_TOP_K", "5")),
            semantic_similarity_threshold=float(
                os.getenv("SSCRE_SEMANTIC_SIMILARITY_THRESHOLD", "0.95")
            ),
            stable_ttl_seconds=int(
                os.getenv("SSCRE_CACHE_STABLE_TTL_SECONDS", str(30 * 24 * 60 * 60))
            ),
            semi_dynamic_ttl_seconds=int(
                os.getenv("SSCRE_CACHE_SEMI_DYNAMIC_TTL_SECONDS", str(24 * 60 * 60))
            ),
            dynamic_ttl_seconds=(
                int(value)
                if (value := os.getenv("SSCRE_CACHE_DYNAMIC_TTL_SECONDS"))
                else None
            ),
            allow_dynamic_entries=_environment_bool(
                "SSCRE_CACHE_ALLOW_DYNAMIC_ENTRIES",
                "false",
            ),
            max_answer_bytes=int(
                os.getenv("SSCRE_CACHE_MAX_ANSWER_BYTES", str(64 * 1024))
            ),
            max_metadata_bytes=int(
                os.getenv("SSCRE_CACHE_MAX_METADATA_BYTES", str(8 * 1024))
            ),
            max_query_bytes=int(
                os.getenv("SSCRE_CACHE_MAX_QUERY_BYTES", str(32 * 1024))
            ),
            max_cache_entries=int(
                os.getenv("SSCRE_CACHE_MAX_ENTRIES", "10000")
            ),
            max_cache_bytes=int(
                os.getenv("SSCRE_CACHE_MAX_BYTES", "100000000")
            ),
            request_timeout_seconds=int(
                os.getenv("SSCRE_TIMEOUT_REQUEST_SECONDS", "30")
            ),
            embedding_timeout_seconds=int(
                os.getenv("SSCRE_TIMEOUT_EMBEDDING_SECONDS", "5")
            ),
            generation_timeout_seconds=int(
                os.getenv("SSCRE_TIMEOUT_GENERATION_SECONDS", "25")
            ),
            repository_timeout_seconds=int(
                os.getenv("SSCRE_TIMEOUT_REPOSITORY_SECONDS", "2")
            ),
            health_timeout_seconds=int(
                os.getenv("SSCRE_TIMEOUT_HEALTH_SECONDS", "1")
            ),
            admin_timeout_seconds=int(
                os.getenv("SSCRE_TIMEOUT_ADMIN_SECONDS", "5")
            ),
            admin_token=os.getenv("SSCRE_ADMIN_TOKEN") or None,
            admin_read_token=os.getenv("SSCRE_ADMIN_READ_TOKEN") or None,
            admin_token_expires_at=_environment_datetime(
                "SSCRE_ADMIN_TOKEN_EXPIRES_AT"
            ),
            admin_read_token_expires_at=_environment_datetime(
                "SSCRE_ADMIN_READ_TOKEN_EXPIRES_AT"
            ),
            api_exposure_mode=os.getenv(
                "SSCRE_API_EXPOSURE_MODE", "trusted_local"
            ).strip().lower(),
            client_auth_json=os.getenv("SSCRE_CLIENT_AUTH_JSON") or None,
            max_request_body_bytes=int(
                os.getenv("SSCRE_MAX_REQUEST_BODY_BYTES", str(64 * 1024))
            ),
            rate_limit_requests_per_minute=int(
                os.getenv("SSCRE_RATE_LIMIT_REQUESTS_PER_MINUTE", "0")
            ),
            tenant_max_concurrent_queries=int(
                os.getenv("SSCRE_TENANT_MAX_CONCURRENT_QUERIES", "32")
            ),
            tenant_provider_budget_per_minute=int(
                os.getenv("SSCRE_TENANT_PROVIDER_BUDGET_PER_MINUTE", "0")
            ),
        )
