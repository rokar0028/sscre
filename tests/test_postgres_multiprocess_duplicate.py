"""WS8 protocol ``ws8-multiprocess-dup-v1``: multi-process same-query miss.

Two independent application processes share one PostgreSQL database. The
in-process generation lock does not coordinate them. This harness measures
provider generations separately from insert success/conflict and does not add
a distributed lock.
"""

from __future__ import annotations

import json
import multiprocessing
import os
from datetime import datetime, timezone
from multiprocessing.synchronize import Barrier
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import DuplicateCacheEntryError
from sscre.config import Settings
from sscre.llm import LLMResult, MockLLMClient
from sscre.postgres_cache import PostgresExactCacheRepository
from sscre.query import QueryRequest, preprocess_query
from tests.ws8_postgres_helpers import (
    DATABASE_URL,
    WS8_MULTIPROCESS_MARKS,
    cleanup_query_hashes,
    count_rows_for_query_hash,
)

pytestmark = WS8_MULTIPROCESS_MARKS

PROTOCOL_ID = "ws8-multiprocess-dup-v1"
PROCESS_COUNT = 2
RUN_COUNT = 3
MISS_BARRIER_TIMEOUT_S = 8.0
WORKER_JOIN_TIMEOUT_S = 45.0
MAX_ANSWER_BYTES = 64 * 1024


class _CountingMockLLM(MockLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def generate(self, query: str) -> LLMResult:
        self.calls += 1
        return super().generate(query)


class _InsertAccountingRepository:
    """Count insert outcomes and barrier-sync post-lock misses.

    The second ``get_by_query_hash`` miss is the in-process recheck after
    ``generation_lock``. Waiting there keeps both processes on the generate
    path so generation counts are independent of insert races.
    """

    def __init__(self, database_url: str, miss_barrier: Barrier) -> None:
        self._inner = PostgresExactCacheRepository(database_url)
        self._miss_barrier = miss_barrier
        self._lookups = 0
        self.insert_success = 0
        self.insert_conflict = 0
        self.insert_error = 0

    def get_by_query_hash(self, query_hash: str):
        entry = self._inner.get_by_query_hash(query_hash)
        if entry is None:
            self._lookups += 1
            if self._lookups == 2:
                try:
                    self._miss_barrier.wait(timeout=MISS_BARRIER_TIMEOUT_S)
                except multiprocessing.BrokenBarrierError:
                    pass
        return entry

    def insert(self, entry) -> None:
        self._record(lambda: self._inner.insert(entry))

    def insert_and_evict(self, entry, max_entries: int, max_bytes: int) -> None:
        self._record(
            lambda: self._inner.insert_and_evict(entry, max_entries, max_bytes)
        )

    def _record(self, write) -> None:
        try:
            write()
        except DuplicateCacheEntryError:
            self.insert_conflict += 1
            raise
        except Exception:
            self.insert_error += 1
            raise
        else:
            self.insert_success += 1

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


def _write_worker_result(result_path: str, payload: dict[str, object]) -> None:
    path = Path(result_path)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _mp_dup_worker(
    process_id: int,
    query: str,
    database_url: str,
    ready_barrier: Barrier,
    miss_barrier: Barrier,
    result_path: str,
) -> None:
    exit_code = 1
    try:
        llm = _CountingMockLLM()
        repository = _InsertAccountingRepository(database_url, miss_barrier)
        settings = Settings(
            database_url=database_url,
            semantic_enabled=False,
            semantic_strategy="C",
            repository_timeout_seconds=15,
            request_timeout_seconds=30,
            generation_timeout_seconds=25,
        )
        client = TestClient(
            create_app(
                repository=repository,
                settings=settings,
                llm_client=llm,
                semantic_strategy="C",
                semantic_enabled=False,
            )
        )
        ready_barrier.wait(timeout=MISS_BARRIER_TIMEOUT_S)
        response = client.post("/v1/query", json={"query": query})
        body = response.json()
        _write_worker_result(
            result_path,
            {
                "ok": True,
                "process_id": process_id,
                "status_code": response.status_code,
                "source": body.get("source"),
                "decision": body.get("decision"),
                "answer": body.get("answer"),
                "selected_candidate_query_hash": body.get(
                    "selected_candidate_query_hash"
                ),
                "request_id": str(body.get("metrics", {}).get("request_id", "")),
                "generations": llm.calls,
                "insert_success": repository.insert_success,
                "insert_conflict": repository.insert_conflict,
                "insert_error": repository.insert_error,
            },
        )
        exit_code = 0
    except Exception as exc:
        _write_worker_result(
            result_path,
            {
                "ok": False,
                "process_id": process_id,
                "error_type": type(exc).__name__,
            },
        )
    finally:
        # create_app starts a non-daemon ThreadPoolExecutor; force worker exit.
        os._exit(exit_code)


def _run_multiprocess_dup(query: str) -> list[dict[str, object]]:
    assert DATABASE_URL is not None
    ctx = multiprocessing.get_context("spawn")
    ready_barrier = ctx.Barrier(PROCESS_COUNT)
    miss_barrier = ctx.Barrier(PROCESS_COUNT)
    with TemporaryDirectory(prefix="ws8-mp-dup-") as tmp:
        result_paths = [
            str(Path(tmp) / f"worker-{process_id}.json")
            for process_id in range(PROCESS_COUNT)
        ]
        workers = [
            ctx.Process(
                target=_mp_dup_worker,
                args=(
                    process_id,
                    query,
                    DATABASE_URL,
                    ready_barrier,
                    miss_barrier,
                    result_paths[process_id],
                ),
            )
            for process_id in range(PROCESS_COUNT)
        ]
        try:
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=WORKER_JOIN_TIMEOUT_S)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5)
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5)
        outcomes: list[dict[str, object]] = []
        for process_id, result_path in enumerate(result_paths):
            path = Path(result_path)
            if not path.exists():
                exitcode = workers[process_id].exitcode
                outcomes.append(
                    {
                        "ok": False,
                        "process_id": process_id,
                        "error_type": f"missing_result_exit_{exitcode}",
                    }
                )
                continue
            outcomes.append(json.loads(path.read_text(encoding="utf-8")))
        return outcomes


def _assert_valid_http_outcome(
    outcome: dict[str, object],
    *,
    query_hash: str,
    expected_answer_prefix: str,
) -> None:
    assert outcome["ok"] is True
    assert outcome["status_code"] == 200
    assert outcome["source"] in {"generated", "cache"}
    assert outcome["decision"] in {"SAFE", "UNSAFE", "UNCERTAIN"}
    answer = outcome["answer"]
    assert isinstance(answer, str)
    assert answer.startswith(expected_answer_prefix)
    assert 0 < len(answer.encode("utf-8")) <= MAX_ANSWER_BYTES
    request_id = outcome["request_id"]
    assert isinstance(request_id, str) and request_id
    if outcome["source"] == "cache":
        assert outcome["decision"] == "SAFE"
        assert outcome["selected_candidate_query_hash"] == query_hash
    else:
        assert outcome["decision"] != "SAFE"
        assert outcome["selected_candidate_query_hash"] is None


def test_multiprocess_same_query_distinguishes_generation_from_insert() -> None:
    """Protocol ws8-multiprocess-dup-v1: two processes, one miss, three runs."""
    assert DATABASE_URL is not None
    generation_counts: list[int] = []
    insert_success_counts: list[int] = []
    insert_conflict_counts: list[int] = []
    hashes: list[str] = []
    try:
        for _ in range(RUN_COUNT):
            query = f"Write Python code for ws8 multiprocess {uuid4()}"
            processed = preprocess_query(QueryRequest(query=query))
            hashes.append(processed.query_hash)
            outcomes = _run_multiprocess_dup(query)
            assert len(outcomes) == PROCESS_COUNT, (
                f"{PROTOCOL_ID} lost a worker outcome: {outcomes!r}"
            )
            failures = [item for item in outcomes if item.get("ok") is not True]
            assert not failures, f"{PROTOCOL_ID} worker error: {failures!r}"

            expected_prefix = f"Generated answer for: {processed.normalized_query}"
            for outcome in outcomes:
                _assert_valid_http_outcome(
                    outcome,
                    query_hash=processed.query_hash,
                    expected_answer_prefix=expected_prefix,
                )

            generations = sum(int(item["generations"]) for item in outcomes)
            insert_success = sum(int(item["insert_success"]) for item in outcomes)
            insert_conflict = sum(int(item["insert_conflict"]) for item in outcomes)
            insert_error = sum(int(item["insert_error"]) for item in outcomes)
            generation_counts.append(generations)
            insert_success_counts.append(insert_success)
            insert_conflict_counts.append(insert_conflict)

            assert generations == PROCESS_COUNT, (
                "in-process lock does not prevent cross-process generation; "
                f"expected {PROCESS_COUNT} provider calls, got {generations}"
            )
            assert insert_success == 1
            assert insert_conflict == 1
            assert insert_error == 0
            assert count_rows_for_query_hash(processed.query_hash) == 1

            stored = PostgresExactCacheRepository(DATABASE_URL).get_by_query_hash(
                processed.query_hash
            )
            assert stored is not None
            assert stored.query_hash == processed.query_hash
            assert stored.normalized_query == processed.normalized_query
            assert stored.answer.startswith(expected_prefix)
            assert 0 < len(stored.answer.encode("utf-8")) <= MAX_ANSWER_BYTES
            assert stored.metadata is not None
            assert stored.ttl_expires_at is not None
            assert stored.ttl_expires_at > datetime.now(timezone.utc)
            assert stored.canonical_answer_hash == stored.answer_hash
            assert all(item["answer"] == stored.answer for item in outcomes)
    finally:
        if hashes:
            cleanup_query_hashes(hashes)

    assert min(generation_counts) == max(generation_counts) == PROCESS_COUNT
    assert min(insert_success_counts) == max(insert_success_counts) == 1
    assert min(insert_conflict_counts) == max(insert_conflict_counts) == 1
