import pytest

from sscre.retry import run_with_bounded_retries


class RetryableError(RuntimeError):
    category = "transient_provider"


class PermanentError(RuntimeError):
    category = "permanent_provider"


def test_retry_helper_caps_attempts_and_backoff() -> None:
    attempts = 0
    delays: list[float] = []

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 4:
            raise RetryableError()
        return "ok"

    result, retry_count = run_with_bounded_retries(
        operation,
        retry_limit=3,
        min_backoff_seconds=1,
        max_backoff_seconds=2,
        max_elapsed_seconds=30,
        sleep_fn=delays.append,
    )

    assert result == "ok"
    assert retry_count == 3
    assert attempts == 4
    assert delays == [1, 2, 2]


def test_retry_after_is_capped_by_max_backoff() -> None:
    attempts = 0
    delays: list[float] = []

    class RateLimitedError(RuntimeError):
        category = "rate_limited"
        retry_after_seconds = 10

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RateLimitedError()
        return "ok"

    result, retry_count = run_with_bounded_retries(
        operation,
        retry_limit=1,
        min_backoff_seconds=1,
        max_backoff_seconds=3,
        max_elapsed_seconds=30,
        sleep_fn=delays.append,
    )

    assert result == "ok"
    assert retry_count == 1
    assert delays == [3]


def test_non_retryable_error_is_raised_without_retry() -> None:
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise PermanentError()

    with pytest.raises(PermanentError):
        run_with_bounded_retries(
            operation,
            retry_limit=3,
            min_backoff_seconds=0,
            max_backoff_seconds=1,
            max_elapsed_seconds=10,
        )

    assert attempts == 1


def test_retry_does_not_sleep_past_elapsed_budget() -> None:
    attempts = 0
    delays: list[float] = []
    current_time = 0.0

    def clock() -> float:
        return current_time

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise RetryableError()

    with pytest.raises(RetryableError):
        run_with_bounded_retries(
            operation,
            retry_limit=3,
            min_backoff_seconds=2,
            max_backoff_seconds=2,
            max_elapsed_seconds=1,
            sleep_fn=delays.append,
            clock_fn=clock,
        )

    assert attempts == 1
    assert delays == []
