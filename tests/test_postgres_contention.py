"""WS8 protocol ``ws8-contention-v1``: uniqueness, transactions, eviction.

Bounded concurrent PostgreSQL writes and reads. Does not claim production
capacity. Eviction uses a relative cap window so the run does not shrink the
pre-existing table below its prior size.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import (
    CacheEntry,
    CacheRepositoryError,
    DuplicateCacheEntryError,
)
from sscre.config import Settings
from sscre.llm import MockLLMClient
from sscre.postgres_cache import PostgresExactCacheRepository
from sscre.query import hash_query
from sscre.safety import QueryMetadata
from tests.ws8_postgres_helpers import (
    DATABASE_URL,
    WS8_CONTENTION_MARKS,
    cleanup_query_hashes,
    count_all_cache_entries,
    count_rows_for_query_hash,
)

pytestmark = WS8_CONTENTION_MARKS

PROTOCOL_ID = "ws8-contention-v1"
DUP_KEY_THREADS = 8
MIXED_RW_THREADS = 8
EVICT_THREADS = 8
CLEANUP_THREADS = 4
LOOKUP_THREADS = 8
PHASE4_ENTRY_CAP = 8
PHASE4_BYTE_CAP = 10_000


def _classify(exc: BaseException) -> str:
    if isinstance(exc, DuplicateCacheEntryError):
        return "duplicate_conflict"
    if isinstance(exc, ValueError):
        return "validation_error"
    if isinstance(exc, CacheRepositoryError):
        return "database_error"
    return "other_error"


def _entry(
    query: str,
    answer: str,
    *,
    metadata: QueryMetadata | None = None,
    ttl_expires_at: datetime | None = None,
) -> CacheEntry:
    kwargs: dict[str, object] = {
        "query_hash": hash_query(query),
        "normalized_query": query,
        "answer": answer,
        "metadata": metadata,
    }
    if ttl_expires_at is not None:
        kwargs["ttl_expires_at"] = ttl_expires_at
    return CacheEntry(**kwargs)  # type: ignore[arg-type]


def _repo() -> PostgresExactCacheRepository:
    assert DATABASE_URL is not None
    return PostgresExactCacheRepository(DATABASE_URL)


def test_ct_dup_key_duplicate_insert_is_deterministic() -> None:
    """CT-dup-key: eight threads, one query_hash, one surviving row."""
    query = f"ws8 ct-dup-key {uuid4()}"
    query_hash = hash_query(query)
    repo = _repo()
    barrier = Barrier(DUP_KEY_THREADS)

    def write(index: int) -> BaseException | None:
        barrier.wait()
        try:
            repo.insert(
                _entry(query, f"ct-dup-key-answer-{index}-{uuid4()}")
            )
        except Exception as exc:
            return exc
        return None

    try:
        with ThreadPoolExecutor(max_workers=DUP_KEY_THREADS) as pool:
            results = list(pool.map(write, range(DUP_KEY_THREADS)))
        classes = [_classify(exc) for exc in results if exc is not None]
        successes = sum(exc is None for exc in results)
        assert successes == 1
        assert classes.count("duplicate_conflict") == DUP_KEY_THREADS - 1
        assert "database_error" not in classes
        assert "validation_error" not in classes
        assert count_rows_for_query_hash(query_hash) == 1
        stored = repo.get_by_query_hash(query_hash)
        assert stored is not None
        assert stored.answer.startswith("ct-dup-key-answer-")
        assert stored.canonical_answer_hash == stored.answer_hash
    finally:
        cleanup_query_hashes([query_hash])


def test_ct_mixed_rw_concurrent_insert_and_lookup() -> None:
    """CT-mixed-rw: interleaved lookup and insert on distinct keys."""
    repo = _repo()
    seeded = [
        _entry(f"ws8 ct-mixed seeded {uuid4()}", f"seeded-answer-{index}")
        for index in range(4)
    ]
    hashes = [entry.query_hash for entry in seeded]
    missing_query = f"ws8 ct-mixed missing {uuid4()}"
    new_entries = [
        _entry(f"ws8 ct-mixed new {uuid4()}", f"new-answer-{index}")
        for index in range(4)
    ]
    hashes.extend(entry.query_hash for entry in new_entries)
    barrier = Barrier(MIXED_RW_THREADS)

    def work(index: int) -> tuple[str, object]:
        barrier.wait()
        try:
            if index < 4:
                found = repo.get_by_query_hash(seeded[index].query_hash)
                return ("lookup_hit", found)
            repo.insert(new_entries[index - 4])
            return ("insert", "ok")
        except Exception as exc:
            return (_classify(exc), exc)

    try:
        for entry in seeded:
            repo.insert(entry)
        with ThreadPoolExecutor(max_workers=MIXED_RW_THREADS) as pool:
            outcomes = list(pool.map(work, range(MIXED_RW_THREADS)))
        assert all(kind != "database_error" for kind, _ in outcomes)
        assert all(kind != "validation_error" for kind, _ in outcomes)
        hits = [found for kind, found in outcomes if kind == "lookup_hit"]
        assert len(hits) == 4
        for found, expected in zip(hits, seeded, strict=True):
            assert isinstance(found, CacheEntry)
            assert found.answer == expected.answer
            assert found.query_hash == expected.query_hash
        assert repo.get_by_query_hash(hash_query(missing_query)) is None
        assert [kind for kind, _ in outcomes].count("insert") == 4
        for entry in new_entries:
            stored = repo.get_by_query_hash(entry.query_hash)
            assert stored is not None
            assert stored.answer == entry.answer
    finally:
        cleanup_query_hashes(hashes)


def test_ct_evict_cap_holds_under_concurrent_writes() -> None:
    """CT-evict-cap: eight threads, Phase 4 entry/byte windows as added caps."""
    repo = _repo()
    before = repo.storage_stats()
    max_entries = before.entries + PHASE4_ENTRY_CAP
    max_bytes = before.total_bytes + PHASE4_BYTE_CAP
    entries = [
        _entry(f"ws8 ct-evict {uuid4()}", f"evict-answer-{index}")
        for index in range(EVICT_THREADS * 2)
    ]
    hashes = [entry.query_hash for entry in entries]
    barrier = Barrier(EVICT_THREADS)

    def write(index: int) -> BaseException | None:
        barrier.wait()
        try:
            repo.insert_and_evict(entries[index * 2], max_entries, max_bytes)
            repo.insert_and_evict(entries[index * 2 + 1], max_entries, max_bytes)
        except Exception as exc:
            return exc
        return None

    try:
        with ThreadPoolExecutor(max_workers=EVICT_THREADS) as pool:
            errors = list(pool.map(write, range(EVICT_THREADS)))
        assert all(exc is None for exc in errors)
        after = repo.storage_stats()
        assert after.entries == count_all_cache_entries()
        assert after.entries <= max_entries
        assert after.total_bytes <= max_bytes
        evicted = after.evictions - before.evictions
        assert after.entries == before.entries + len(entries) - evicted
        assert evicted >= len(entries) - PHASE4_ENTRY_CAP
        remaining = [
            repo.get_by_query_hash(entry.query_hash) for entry in entries
        ]
        present = [entry for entry in remaining if entry is not None]
        assert present
        by_hash = {entry.query_hash: entry for entry in entries}
        for stored in present:
            expected = by_hash[stored.query_hash]
            assert stored.answer == expected.answer
            assert stored.canonical_answer_hash == stored.answer_hash
    finally:
        cleanup_query_hashes(hashes)


def test_ct_cleanup_race_does_not_remove_fresh_entry() -> None:
    """CT-cleanup-race: cleanup must not delete a newly valid row."""
    repo = _repo()
    stale = [
        _entry(
            f"ws8 ct-cleanup stale {uuid4()}",
            f"stale-answer-{index}",
            ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=30),
        )
        for index in range(2)
    ]
    fresh = [
        _entry(
            f"ws8 ct-cleanup fresh {uuid4()}",
            f"fresh-answer-{index}",
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        for index in range(2)
    ]
    extra_fresh = [
        _entry(
            f"ws8 ct-cleanup extra {uuid4()}",
            f"fresh-answer-extra-{index}",
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        for index in range(2)
    ]
    hashes = [entry.query_hash for entry in (*stale, *fresh, *extra_fresh)]
    barrier = Barrier(CLEANUP_THREADS)

    def work(index: int) -> tuple[str, object]:
        barrier.wait()
        try:
            if index < 2:
                return ("cleanup", repo.cleanup_expired(limit=50))
            repo.insert(extra_fresh[index - 2])
            return ("insert_fresh", extra_fresh[index - 2].query_hash)
        except Exception as exc:
            return (_classify(exc), type(exc).__name__)

    try:
        for entry in (*stale, *fresh):
            repo.insert(entry)
        with ThreadPoolExecutor(max_workers=CLEANUP_THREADS) as pool:
            outcomes = list(pool.map(work, range(CLEANUP_THREADS)))
        kinds = [kind for kind, _ in outcomes]
        assert "database_error" not in kinds
        assert "validation_error" not in kinds
        assert kinds.count("cleanup") == 2
        assert kinds.count("insert_fresh") == 2
        for entry in (*fresh, *extra_fresh):
            stored = repo.get_by_query_hash(entry.query_hash)
            assert stored is not None
            assert stored.answer == entry.answer
        for entry in stale:
            assert repo.get_by_query_hash(entry.query_hash) is None
    finally:
        cleanup_query_hashes(hashes)


def test_expired_and_disallowed_cannot_win_concurrent_lookup() -> None:
    assert DATABASE_URL is not None
    expired_query = f"ws8 ct-lookup expired {uuid4()}"
    missing_meta_query = f"ws8 ct-lookup meta {uuid4()}"
    incompatible_query = f"write Python code ct-lookup {uuid4()}"
    expired = _entry(
        expired_query,
        "expired-stale-answer",
        metadata=QueryMetadata(intent="factual", domain="unknown"),
        ttl_expires_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    missing_meta = _entry(
        missing_meta_query,
        "metadata-less-stale-answer",
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    incompatible = _entry(
        incompatible_query,
        "incompatible-stale-answer",
        metadata=QueryMetadata(
            intent="code",
            domain="programming",
            constraints=(("language", "java"),),
            output_format="code",
        ),
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    repo = _repo()
    client = TestClient(
        create_app(
            repository=repo,
            settings=Settings(
                database_url=DATABASE_URL,
                semantic_enabled=False,
                semantic_strategy="C",
            ),
            llm_client=MockLLMClient(),
            semantic_enabled=False,
            semantic_strategy="C",
        )
    )
    hashes = [expired.query_hash, missing_meta.query_hash, incompatible.query_hash]
    cases = (
        (expired_query, "expired-stale-answer"),
        (missing_meta_query, "metadata-less-stale-answer"),
        (incompatible_query, "incompatible-stale-answer"),
    )
    try:
        for entry in (expired, missing_meta, incompatible):
            repo.insert(entry)
        for query, banned in cases:
            barrier = Barrier(LOOKUP_THREADS)

            def post(_: int, posted_query: str = query) -> dict[str, object]:
                barrier.wait()
                response = client.post("/v1/query", json={"query": posted_query})
                body = response.json()
                return {
                    "status_code": response.status_code,
                    "source": body.get("source"),
                    "decision": body.get("decision"),
                    "answer": body.get("answer"),
                }

            with ThreadPoolExecutor(max_workers=LOOKUP_THREADS) as pool:
                bodies = list(pool.map(post, range(LOOKUP_THREADS)))
            assert all(item["status_code"] == 200 for item in bodies)
            assert all(item["answer"] != banned for item in bodies)
            assert all(
                item["source"] != "cache" or item["answer"] != banned
                for item in bodies
            )
    finally:
        cleanup_query_hashes(hashes)


def test_database_errors_recorded_separately_from_validation() -> None:
    repo = _repo()
    valid = _entry(f"ws8 ct-errors valid {uuid4()}", "valid-answer")
    hashes = [valid.query_hash]
    barrier = Barrier(3)

    def work(kind: str) -> str:
        barrier.wait()
        try:
            if kind == "validation":
                repo.insert_and_evict(valid, 0, PHASE4_BYTE_CAP)
            elif kind == "database":
                repo.insert(
                    CacheEntry(
                        query_hash="not-a-sha256-hash",
                        normalized_query=f"ws8 ct-errors invalid {uuid4()}",
                        answer="invalid-hash-answer",
                    )
                )
            else:
                repo.insert(valid)
                repo.insert(valid)
        except Exception as exc:
            return _classify(exc)
        return "success"

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            classes = list(pool.map(work, ("validation", "database", "duplicate")))
        assert "validation_error" in classes
        assert "database_error" in classes
        assert "duplicate_conflict" in classes
        assert classes.count("validation_error") == 1
        assert classes.count("database_error") == 1
        assert classes.count("duplicate_conflict") == 1
    finally:
        cleanup_query_hashes(hashes)
