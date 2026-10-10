"""Opt-in PostgreSQL failure/recovery injection for WS8 operational verification.

Simulated failures use ``CacheRepositoryError`` at declared repository boundaries.
Live container restart helpers require explicit environment opt-in and must be
labeled separately from simulated drops in evidence artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

import psycopg

from sscre.cache import CacheEntry, CacheRepositoryError
from sscre.postgres_cache import PostgresExactCacheRepository

FailureEventClass = Literal[
    "simulated_drop",
    "simulated_repository_failure",
    "process_restart",
    "container_restart",
]

WS8_LIVE_RESTART_ENV = "SSCRE_WS8_LIVE_POSTGRES_RESTART"


class FailureOperation(str, Enum):
    LOOKUP = "lookup"
    INSERT = "insert"
    INSERT_AND_EVICT = "insert_and_evict"
    CLEANUP = "cleanup"
    SEARCH = "search"


@dataclass
class FailureInjectionConfig:
    """Mutable failure schedule shared with ``PostgresFailureInjectionRepository``."""

    event_class: FailureEventClass = "simulated_drop"
    active_operations: set[FailureOperation] = field(default_factory=set)
    fail_once: bool = False
    scenario_id: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def arm(
        self,
        *operations: FailureOperation,
        scenario_id: str | None = None,
        event_class: FailureEventClass | None = None,
        fail_once: bool = False,
    ) -> None:
        self.active_operations.update(operations)
        if scenario_id is not None:
            self.scenario_id = scenario_id
        if event_class is not None:
            self.event_class = event_class
        self.fail_once = fail_once

    def disarm(self) -> None:
        self.active_operations.clear()
        self.fail_once = False

    def evidence_snapshot(self) -> dict[str, Any]:
        return {
            "event_class": self.event_class,
            "scenario_id": self.scenario_id,
            "recorded_events": list(self.events),
        }


class PostgresFailureInjectionRepository(PostgresExactCacheRepository):
    """PostgreSQL repository that fails selected operations for harness runs."""

    def __init__(
        self,
        database_url: str,
        config: FailureInjectionConfig | None = None,
    ) -> None:
        super().__init__(database_url)
        self._failure_config = config or FailureInjectionConfig()

    @property
    def failure_config(self) -> FailureInjectionConfig:
        return self._failure_config

    def _maybe_fail(self, operation: FailureOperation) -> None:
        if operation not in self._failure_config.active_operations:
            return
        self._failure_config.events.append(
            {
                "operation": operation.value,
                "event_class": self._failure_config.event_class,
                "scenario_id": self._failure_config.scenario_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if self._failure_config.fail_once:
            self._failure_config.active_operations.discard(operation)
        raise CacheRepositoryError(
            f"simulated PostgreSQL {operation.value} failure "
            f"({self._failure_config.event_class})"
        )

    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        self._maybe_fail(FailureOperation.LOOKUP)
        return super().get_by_query_hash(query_hash)

    def insert(self, entry: CacheEntry) -> None:
        self._maybe_fail(FailureOperation.INSERT)
        super().insert(entry)

    def insert_and_evict(
        self,
        entry: CacheEntry,
        max_entries: int,
        max_bytes: int,
    ) -> None:
        self._maybe_fail(FailureOperation.INSERT_AND_EVICT)
        super().insert_and_evict(entry, max_entries, max_bytes)

    def cleanup_expired(self, limit: int = 100) -> int:
        self._maybe_fail(FailureOperation.CLEANUP)
        return super().cleanup_expired(limit)

    def search_by_embedding(
        self,
        embedding: tuple[float, ...],
        top_k: int,
        embedding_model: str | None = None,
    ):
        self._maybe_fail(FailureOperation.SEARCH)
        return super().search_by_embedding(
            embedding,
            top_k,
            embedding_model=embedding_model,
        )


def live_postgres_restart_enabled() -> bool:
    return os.getenv(WS8_LIVE_RESTART_ENV) == "1"


def _default_compose_working_directory() -> Path:
    return Path(__file__).resolve().parents[2]


def restart_postgres_container(
    *,
    compose_file: str | None = None,
    compose_working_directory: Path | str | None = None,
    service: str = "postgres",
    ready_timeout_seconds: float = 120.0,
    database_url: str | None = None,
) -> dict[str, Any]:
    """Restart the compose PostgreSQL service and wait until connections succeed.

    Requires ``SSCRE_WS8_LIVE_POSTGRES_RESTART=1``. This records
    ``event_class=container_restart``; it is not interchangeable with simulated
    repository failures.
    """

    if not live_postgres_restart_enabled():
        raise RuntimeError(
            f"{WS8_LIVE_RESTART_ENV}=1 is required for live container restart"
        )
    resolved_url = database_url or os.getenv("SSCRE_DATABASE_URL")
    if not resolved_url:
        raise RuntimeError("SSCRE_DATABASE_URL is required for live restart")

    command = ["docker", "compose"]
    if compose_file:
        command.extend(["-f", compose_file])
    command.extend(["restart", service])
    started = time.perf_counter()
    subprocess.run(
        command,
        check=True,
        cwd=str(compose_working_directory or _default_compose_working_directory()),
    )
    deadline = time.perf_counter() + ready_timeout_seconds
    last_error: Exception | None = None
    while time.perf_counter() < deadline:
        try:
            with psycopg.connect(resolved_url, connect_timeout=3) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            return {
                "event_class": "container_restart",
                "service": service,
                "ready_seconds": round(time.perf_counter() - started, 3),
            }
        except Exception as exc:  # pragma: no cover - retry loop
            last_error = exc
            time.sleep(1.0)
    raise RuntimeError(
        f"PostgreSQL did not become ready after restart: {last_error}"
    ) from last_error
