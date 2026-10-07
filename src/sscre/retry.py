"""Bounded retry execution for remote-provider calls."""

from collections.abc import Callable
from time import monotonic, sleep
from typing import TypeVar


T = TypeVar("T")
_RETRYABLE_CATEGORIES = frozenset({"rate_limited", "timeout", "transient_provider"})


def run_with_bounded_retries(
    operation: Callable[[], T],
    *,
    retry_limit: int,
    min_backoff_seconds: float,
    max_backoff_seconds: float,
    max_elapsed_seconds: float,
    is_retryable: Callable[[BaseException], bool] | None = None,
    sleep_fn: Callable[[float], None] = sleep,
    clock_fn: Callable[[], float] = monotonic,
) -> tuple[T, int]:
    """Run an operation and return its value plus the number of retries.

    The operation is never retried after a non-retryable error, after the
    attempt limit, or when sleeping for another attempt would exceed the
    elapsed retry budget.
    """
    if retry_limit < 0:
        raise ValueError("retry_limit must not be negative")
    if min_backoff_seconds < 0 or max_backoff_seconds < min_backoff_seconds:
        raise ValueError("backoff bounds are invalid")
    if max_elapsed_seconds <= 0:
        raise ValueError("max_elapsed_seconds must be positive")

    retryable = is_retryable or _default_retryable
    started_at = clock_fn()
    retries = 0
    while True:
        try:
            return operation(), retries
        except Exception as exc:
            if retries >= retry_limit or not retryable(exc):
                raise
            elapsed = clock_fn() - started_at
            remaining = max_elapsed_seconds - elapsed
            if remaining <= 0:
                raise
            exponential = min(
                max_backoff_seconds,
                min_backoff_seconds * (2**retries),
            )
            provider_delay = getattr(exc, "retry_after_seconds", None)
            if isinstance(provider_delay, (int, float)) and provider_delay >= 0:
                delay = min(max_backoff_seconds, max(exponential, provider_delay))
            else:
                delay = exponential
            if delay > remaining:
                raise
            if delay > 0:
                sleep_fn(delay)
            retries += 1


def _default_retryable(exc: BaseException) -> bool:
    return getattr(exc, "category", None) in _RETRYABLE_CATEGORIES
