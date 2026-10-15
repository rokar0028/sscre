"""Workstream 3 Step 3.1/3.3: timeout/capacity boundary probe."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import pytest

from sscre.dependency_runtime import DependencyTimeoutError, run_with_timeout


@dataclass(frozen=True)
class TimeoutCapacityProbeResult:
    timed_out: bool
    slot_available_immediately_after_timeout: bool
    callable_still_running_after_timeout: bool
    slot_released_after_callable_completes: bool
    request_return_elapsed_seconds: float
    callable_completion_elapsed_seconds: float


def run_timeout_capacity_probe(
    *,
    operation_timeout_seconds: float = 0.05,
    callable_block_seconds: float = 0.35,
) -> TimeoutCapacityProbeResult:
    slots = threading.BoundedSemaphore(1)
    started = threading.Event()
    release = threading.Event()

    def slow_operation() -> str:
        started.set()
        release.wait(timeout=callable_block_seconds + 2.0)
        return "done"

    executor = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="sscre-ws3-probe",
    )
    request_started = time.perf_counter()
    timed_out = False
    try:
        run_with_timeout(
            executor,
            slow_operation,
            operation_timeout_seconds,
            "probe",
            slots,
        )
    except DependencyTimeoutError:
        timed_out = True
    request_return_elapsed = time.perf_counter() - request_started

    assert started.wait(timeout=1.0), "slow callable did not start"
    slot_available = slots.acquire(blocking=False)
    if slot_available:
        slots.release()

    callable_still_running = started.is_set() and not release.is_set()

    release.set()
    executor.shutdown(wait=True)
    completion_elapsed = time.perf_counter() - request_started

    slot_after_completion = slots.acquire(blocking=False)
    if slot_after_completion:
        slots.release()

    return TimeoutCapacityProbeResult(
        timed_out=timed_out,
        slot_available_immediately_after_timeout=slot_available,
        callable_still_running_after_timeout=callable_still_running,
        slot_released_after_callable_completes=slot_after_completion,
        request_return_elapsed_seconds=request_return_elapsed,
        callable_completion_elapsed_seconds=completion_elapsed,
    )


def test_run_with_timeout_releases_admission_slot_on_timeout() -> None:
    result = run_timeout_capacity_probe()
    assert result.timed_out
    assert result.slot_available_immediately_after_timeout
    assert result.callable_still_running_after_timeout
    assert result.slot_released_after_callable_completes


def test_follow_up_admits_after_dependency_timeout() -> None:
    slots = threading.BoundedSemaphore(1)
    release = threading.Event()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sscre-ws3-probe")

    def stall() -> None:
        release.wait(timeout=2.0)

    with pytest.raises(DependencyTimeoutError, match="timed out"):
        run_with_timeout(executor, stall, 0.05, "stall", slots)

    release.set()
    assert run_with_timeout(executor, lambda: "ok", 0.05, "follow-up", slots) == "ok"

    executor.shutdown(wait=True)
