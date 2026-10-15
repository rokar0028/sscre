"""Request admission, rate limits, and provider budgets for the HTTP API."""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Iterator

from sscre.api_auth import RequestContext
from sscre.config import Settings

RATE_LIMIT_WINDOW_SECONDS = 60


class AbuseControlError(Exception):
    """Rejected before cache or provider work."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.retry_after_seconds = retry_after_seconds
        super().__init__(detail)


@dataclass(frozen=True)
class AbuseControlPolicy:
    enabled: bool
    max_request_body_bytes: int
    rate_limit_requests_per_minute: int
    tenant_max_concurrent_queries: int
    tenant_provider_budget_per_minute: int

    @classmethod
    def from_settings(cls, settings: Settings) -> AbuseControlPolicy:
        external = settings.api_exposure_mode == "external"
        return cls(
            enabled=external,
            max_request_body_bytes=settings.max_request_body_bytes,
            rate_limit_requests_per_minute=settings.rate_limit_requests_per_minute,
            tenant_max_concurrent_queries=settings.tenant_max_concurrent_queries,
            tenant_provider_budget_per_minute=settings.tenant_provider_budget_per_minute,
        )


def validate_abuse_control_configuration(settings: Settings) -> list[str]:
    errors: list[str] = []
    if settings.max_request_body_bytes <= 0:
        errors.append("SSCRE_MAX_REQUEST_BODY_BYTES must be positive")
    if settings.tenant_max_concurrent_queries <= 0:
        errors.append("SSCRE_TENANT_MAX_CONCURRENT_QUERIES must be positive")
    if settings.api_exposure_mode != "external":
        return errors
    if settings.rate_limit_requests_per_minute <= 0:
        errors.append(
            "SSCRE_RATE_LIMIT_REQUESTS_PER_MINUTE must be positive when "
            "SSCRE_API_EXPOSURE_MODE=external"
        )
    if settings.tenant_provider_budget_per_minute <= 0:
        errors.append(
            "SSCRE_TENANT_PROVIDER_BUDGET_PER_MINUTE must be positive when "
            "SSCRE_API_EXPOSURE_MODE=external"
        )
    return errors


def _rate_limit_key(context: RequestContext) -> str:
    return f"{context.tenant_id}:{context.principal_id}"


class InProcessAbuseController:
    """Process-local limits; external mode requires this implementation."""

    def __init__(self, policy: AbuseControlPolicy) -> None:
        self._policy = policy
        self._lock = Lock()
        self._request_times: dict[str, deque[float]] = {}
        self._provider_uses: dict[str, deque[float]] = {}
        self._tenant_inflight: dict[str, int] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> InProcessAbuseController:
        return cls(AbuseControlPolicy.from_settings(settings))

    def check_request_rate(self, context: RequestContext) -> None:
        if not self._policy.enabled:
            return
        limit = self._policy.rate_limit_requests_per_minute
        key = _rate_limit_key(context)
        now = monotonic()
        with self._lock:
            window = self._request_times.setdefault(key, deque())
            self._prune(window, now)
            if len(window) >= limit:
                retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - window[0])))
                raise AbuseControlError(
                    429,
                    "rate limit exceeded",
                    retry_after_seconds=retry_after,
                )
            window.append(now)

    def check_provider_budget(self, tenant_id: str) -> None:
        if not self._policy.enabled:
            return
        limit = self._policy.tenant_provider_budget_per_minute
        now = monotonic()
        with self._lock:
            window = self._provider_uses.setdefault(tenant_id, deque())
            self._prune(window, now)
            if len(window) >= limit:
                retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - window[0])))
                raise AbuseControlError(
                    429,
                    "provider budget exceeded",
                    retry_after_seconds=retry_after,
                )

    def record_provider_use(self, tenant_id: str) -> None:
        if not self._policy.enabled:
            return
        now = monotonic()
        with self._lock:
            window = self._provider_uses.setdefault(tenant_id, deque())
            self._prune(window, now)
            window.append(now)

    def acquire_tenant_slot(self, tenant_id: str) -> None:
        if not self._policy.enabled:
            return
        limit = self._policy.tenant_max_concurrent_queries
        with self._lock:
            inflight = self._tenant_inflight.get(tenant_id, 0)
            if inflight >= limit:
                raise AbuseControlError(
                    503,
                    "tenant concurrency limit exceeded",
                )
            self._tenant_inflight[tenant_id] = inflight + 1

    def release_tenant_slot(self, tenant_id: str) -> None:
        if not self._policy.enabled:
            return
        with self._lock:
            remaining = self._tenant_inflight.get(tenant_id, 1) - 1
            if remaining <= 0:
                self._tenant_inflight.pop(tenant_id, None)
            else:
                self._tenant_inflight[tenant_id] = remaining

    @contextmanager
    def tenant_concurrency(self, tenant_id: str) -> Iterator[None]:
        self.acquire_tenant_slot(tenant_id)
        try:
            yield
        finally:
            self.release_tenant_slot(tenant_id)

    def admit_provider_work(self, tenant_id: str) -> None:
        if not self._policy.enabled:
            return
        limit = self._policy.tenant_provider_budget_per_minute
        now = monotonic()
        with self._lock:
            window = self._provider_uses.setdefault(tenant_id, deque())
            self._prune(window, now)
            if len(window) >= limit:
                retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - window[0])))
                raise AbuseControlError(
                    429,
                    "provider budget exceeded",
                    retry_after_seconds=retry_after,
                )
            window.append(now)

    @staticmethod
    def _prune(window: deque[float], now: float) -> None:
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        while window and window[0] <= cutoff:
            window.popleft()
