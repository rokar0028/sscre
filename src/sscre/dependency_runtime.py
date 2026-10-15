"""Bounded dependency execution with admission release on timeout."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from collections.abc import Callable
from threading import BoundedSemaphore, Lock
from uuid import UUID

from fastapi import HTTPException


class DependencyTimeoutError(RuntimeError):
    """Raised when a bounded dependency operation exceeds its budget."""

    def __init__(
        self,
        message: str,
        *,
        category: str = "dependency_timeout",
        operation_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.operation_name = operation_name


class RequestCancellation:
    """Per-request flag set when the client-visible dependency budget is exceeded."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._cancelled = False

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled


def dependency_timeout_http_exception(
    exc: DependencyTimeoutError,
    request_id: UUID,
) -> HTTPException:
    headers = {"X-Request-ID": str(request_id)}
    if exc.category == "request_deadline":
        return HTTPException(
            status_code=504,
            detail="request timed out",
            headers=headers,
        )
    if exc.category == "generation_lock_timeout":
        return HTTPException(
            status_code=503,
            detail="generation temporarily unavailable",
            headers=headers,
        )
    if exc.category == "dependency_timeout" and exc.operation_name == "generation":
        return HTTPException(
            status_code=504,
            detail="response generation timed out",
            headers=headers,
        )
    if exc.category == "capacity_exhausted":
        return HTTPException(
            status_code=503,
            detail="service temporarily overloaded",
            headers=headers,
        )
    if exc.category == "dependency_timeout":
        return HTTPException(
            status_code=503,
            detail="dependency temporarily unavailable",
            headers=headers,
        )
    return HTTPException(
        status_code=503,
        detail="service temporarily unavailable",
        headers=headers,
    )


def run_with_timeout(
    executor: ThreadPoolExecutor,
    operation: Callable[[], object],
    timeout_seconds: float,
    operation_name: str,
    slots: BoundedSemaphore | None = None,
    *,
    cancellation: RequestCancellation | None = None,
    request_id: UUID | None = None,
    logger: logging.Logger | None = None,
) -> object:
    if timeout_seconds <= 0:
        raise DependencyTimeoutError(
            f"{operation_name} timed out",
            category="dependency_timeout",
            operation_name=operation_name,
        )
    slot_held = False
    if slots is not None:
        if not slots.acquire(timeout=timeout_seconds):
            raise DependencyTimeoutError(
                f"{operation_name} capacity exhausted",
                category="capacity_exhausted",
                operation_name=operation_name,
            )
        slot_held = True

    released = False

    def release_slot() -> None:
        nonlocal released
        if slots is not None and slot_held and not released:
            released = True
            slots.release()

    def invoke() -> object:
        if cancellation is not None and cancellation.is_cancelled():
            raise DependencyTimeoutError(
                f"{operation_name} cancelled",
                category="request_cancelled",
                operation_name=operation_name,
            )
        result = operation()
        if cancellation is not None and cancellation.is_cancelled():
            if logger is not None and request_id is not None:
                logger.warning(
                    "late_completion request_id=%s operation=%s category=late_completion",
                    request_id,
                    operation_name,
                )
            raise DependencyTimeoutError(
                f"{operation_name} completed after timeout",
                category="late_completion",
                operation_name=operation_name,
            )
        return result

    future = executor.submit(invoke)
    future.add_done_callback(lambda _: release_slot())
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        future.cancel()
        release_slot()
        raise DependencyTimeoutError(
            f"{operation_name} timed out",
            category="dependency_timeout",
            operation_name=operation_name,
        ) from exc
