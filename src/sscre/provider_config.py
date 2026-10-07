"""Opt-in, redacted configuration for real-provider experiments.

This module deliberately contains no provider SDK or transport code. It freezes
the configuration boundary that adapters will consume in later workstream
steps while keeping fake providers as the default path.
"""

from dataclasses import dataclass, field
from math import isfinite
import os
from typing import Mapping
from urllib.parse import urlsplit


PROVIDER_CONFIG_VERSION = "real-provider-config-1.0"
MAX_IDENTIFIER_LENGTH = 128
MAX_ENDPOINT_LENGTH = 2048
MAX_REQUEST_PARAMETERS = 32
MAX_REQUEST_PARAMETER_LENGTH = 128
_RESERVED_REQUEST_PARAMETER_KEYS = frozenset({"model", "messages", "input"})


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} is required when real-provider mode is enabled")
    return value.strip()


def _environment_int(name: str, *, minimum: int = 0) -> int:
    raw = _required_environment(name)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _environment_float(name: str, *, minimum: float = 0.0) -> float:
    raw = _required_environment(name)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _environment_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return normalized == "true"


def _bounded_identifier(name: str, value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{name} must not be empty")
    if len(value) > MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{name} exceeds {MAX_IDENTIFIER_LENGTH} characters")
    return value


@dataclass(frozen=True)
class RealProviderConfig:
    """Validated configuration for one explicitly enabled provider run."""

    provider: str
    endpoint: str
    generation_model: str
    embedding_model: str
    embedding_dimension: int
    request_timeout_seconds: float
    generation_timeout_seconds: float
    embedding_timeout_seconds: float
    connect_timeout_seconds: float
    retry_limit: int
    min_backoff_seconds: float
    max_backoff_seconds: float
    max_retry_elapsed_seconds: float
    experiment_id: str
    dataset_version: str
    split: str
    pricing_schedule_id: str
    allowed_hosts: tuple[str, ...] = ()
    request_parameters: tuple[tuple[str, str], ...] = ()
    credential: str | None = field(default=None, repr=False, compare=False)
    config_version: str = PROVIDER_CONFIG_VERSION
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.enabled:
            raise ValueError("RealProviderConfig must be explicitly enabled")
        if self.config_version != PROVIDER_CONFIG_VERSION:
            raise ValueError("unsupported real-provider configuration version")

        for name in (
            "provider",
            "generation_model",
            "embedding_model",
            "experiment_id",
            "dataset_version",
            "split",
            "pricing_schedule_id",
        ):
            _bounded_identifier(name, getattr(self, name))

        if not isinstance(self.endpoint, str) or len(self.endpoint) > MAX_ENDPOINT_LENGTH:
            raise ValueError("endpoint must be a bounded URL")
        parsed = urlsplit(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("endpoint must use an http or https URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("endpoint must not include user info")
        if parsed.query:
            raise ValueError("endpoint must not include a URL query")
        if parsed.fragment:
            raise ValueError("endpoint must not include a URL fragment")

        if self.embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")
        for name in (
            "request_timeout_seconds",
            "generation_timeout_seconds",
            "embedding_timeout_seconds",
            "connect_timeout_seconds",
            "max_retry_elapsed_seconds",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.generation_timeout_seconds > self.request_timeout_seconds:
            raise ValueError("generation timeout exceeds request timeout")
        if self.embedding_timeout_seconds > self.request_timeout_seconds:
            raise ValueError("embedding timeout exceeds request timeout")
        if self.connect_timeout_seconds > self.request_timeout_seconds:
            raise ValueError("connect timeout exceeds request timeout")
        if self.max_retry_elapsed_seconds > self.request_timeout_seconds:
            raise ValueError("retry budget exceeds request timeout")
        if (
            max(self.generation_timeout_seconds, self.embedding_timeout_seconds)
            + self.max_retry_elapsed_seconds
            > self.request_timeout_seconds
        ):
            raise ValueError(
                "provider timeout plus retry budget exceeds request timeout"
            )

        if self.retry_limit < 0:
            raise ValueError("retry_limit must not be negative")
        if (
            not isfinite(self.min_backoff_seconds)
            or not isfinite(self.max_backoff_seconds)
            or self.min_backoff_seconds < 0
        ):
            raise ValueError("min_backoff_seconds must not be negative")
        if self.max_backoff_seconds < self.min_backoff_seconds:
            raise ValueError("max_backoff_seconds must not be below minimum backoff")
        if self.max_backoff_seconds > self.max_retry_elapsed_seconds:
            raise ValueError("maximum backoff exceeds retry budget")

        host = parsed.hostname
        if host is None:
            raise ValueError("endpoint must include a hostname")
        normalized_hosts = tuple(hostname.strip().lower() for hostname in self.allowed_hosts)
        if any(not hostname for hostname in normalized_hosts):
            raise ValueError("allowed_hosts must not contain blank values")
        if normalized_hosts and host.lower() not in normalized_hosts:
            raise ValueError("endpoint host is not in allowed_hosts")

        if len(self.request_parameters) > MAX_REQUEST_PARAMETERS:
            raise ValueError("too many request parameters")
        seen_keys: set[str] = set()
        for key, value in self.request_parameters:
            if (
                not isinstance(key, str)
                or not isinstance(value, str)
                or not key.strip()
                or len(key) > MAX_REQUEST_PARAMETER_LENGTH
                or len(value) > MAX_REQUEST_PARAMETER_LENGTH
            ):
                raise ValueError("request parameters must be bounded string pairs")
            normalized_key = key.strip().lower()
            if normalized_key in seen_keys:
                raise ValueError("request parameter keys must be unique")
            if normalized_key in _RESERVED_REQUEST_PARAMETER_KEYS:
                raise ValueError("request parameters must not override reserved fields")
            if any(secret_word in normalized_key for secret_word in (
                "key",
                "secret",
                "token",
                "password",
                "authorization",
            )):
                raise ValueError("request parameters must not contain credentials")
            seen_keys.add(normalized_key)

    @property
    def credential_configured(self) -> bool:
        return bool(self.credential)

    @property
    def endpoint_origin(self) -> str:
        parsed = urlsplit(self.endpoint)
        return f"{parsed.scheme}://{parsed.netloc}"

    def redacted(self) -> dict[str, object]:
        """Return the only configuration shape permitted in reports/logs."""
        return {
            "config_version": self.config_version,
            "enabled": self.enabled,
            "provider": self.provider,
            "endpoint_origin": self.endpoint_origin,
            "generation_model": self.generation_model,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "request_timeout_seconds": self.request_timeout_seconds,
            "generation_timeout_seconds": self.generation_timeout_seconds,
            "embedding_timeout_seconds": self.embedding_timeout_seconds,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "retry_limit": self.retry_limit,
            "min_backoff_seconds": self.min_backoff_seconds,
            "max_backoff_seconds": self.max_backoff_seconds,
            "max_retry_elapsed_seconds": self.max_retry_elapsed_seconds,
            "experiment_id": self.experiment_id,
            "dataset_version": self.dataset_version,
            "split": self.split,
            "pricing_schedule_id": self.pricing_schedule_id,
            "allowed_hosts": list(self.allowed_hosts),
            "request_parameters": dict(self.request_parameters),
            "credential_configured": self.credential_configured,
        }

    @classmethod
    def from_environment(cls) -> "RealProviderConfig | None":
        """Load config only when explicitly enabled.

        Disabled mode returns ``None`` so callers can retain the deterministic
        fake-provider path. Enabled mode fails closed on missing configuration.
        """
        if not _environment_bool("SSCRE_REAL_PROVIDER", default=False):
            return None

        allowed_hosts = tuple(
            host.strip().lower()
            for host in os.getenv("SSCRE_PROVIDER_ALLOWED_HOSTS", "").split(",")
            if host.strip()
        )
        return cls(
            provider=_required_environment("SSCRE_PROVIDER"),
            endpoint=_required_environment("SSCRE_PROVIDER_ENDPOINT"),
            generation_model=_required_environment("SSCRE_PROVIDER_GENERATION_MODEL"),
            embedding_model=_required_environment("SSCRE_PROVIDER_EMBEDDING_MODEL"),
            embedding_dimension=_environment_int(
                "SSCRE_PROVIDER_EMBEDDING_DIMENSION",
                minimum=1,
            ),
            request_timeout_seconds=_environment_float(
                "SSCRE_PROVIDER_REQUEST_TIMEOUT_SECONDS",
                minimum=0.001,
            ),
            generation_timeout_seconds=_environment_float(
                "SSCRE_PROVIDER_GENERATION_TIMEOUT_SECONDS",
                minimum=0.001,
            ),
            embedding_timeout_seconds=_environment_float(
                "SSCRE_PROVIDER_EMBEDDING_TIMEOUT_SECONDS",
                minimum=0.001,
            ),
            connect_timeout_seconds=_environment_float(
                "SSCRE_PROVIDER_CONNECT_TIMEOUT_SECONDS",
                minimum=0.001,
            ),
            retry_limit=_environment_int("SSCRE_PROVIDER_RETRY_LIMIT"),
            min_backoff_seconds=_environment_float(
                "SSCRE_PROVIDER_MIN_BACKOFF_SECONDS",
            ),
            max_backoff_seconds=_environment_float(
                "SSCRE_PROVIDER_MAX_BACKOFF_SECONDS",
            ),
            max_retry_elapsed_seconds=_environment_float(
                "SSCRE_PROVIDER_MAX_RETRY_ELAPSED_SECONDS",
                minimum=0.001,
            ),
            experiment_id=_required_environment("SSCRE_PROVIDER_EXPERIMENT_ID"),
            dataset_version=_required_environment("SSCRE_PROVIDER_DATASET_VERSION"),
            split=_required_environment("SSCRE_PROVIDER_SPLIT"),
            pricing_schedule_id=_required_environment(
                "SSCRE_PROVIDER_PRICING_SCHEDULE_ID"
            ),
            allowed_hosts=allowed_hosts,
            credential=os.getenv("SSCRE_PROVIDER_CREDENTIAL") or None,
        )


def redacted_provider_config(
    config: RealProviderConfig | None,
) -> Mapping[str, object] | None:
    """Return a report-safe config or ``None`` when real mode is disabled."""
    return config.redacted() if config is not None else None
