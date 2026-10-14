"""Default-suite checks that scoped eviction cannot target other rows."""

from __future__ import annotations

import ast
from pathlib import Path

from sscre.postgres_cache import PostgresExactCacheRepository

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCOPE_KEYWORDS = frozenset({"only_query_hashes"})
_GUARDED_CALLS = frozenset({"insert_and_evict", "cleanup_expired"})


class _Cursor:
    def __init__(self, fetches: list[object]) -> None:
        self.calls: list[tuple[str, object]] = []
        self._fetches = list(fetches)

    def execute(self, query: str, params: object = None) -> None:
        self.calls.append((" ".join(query.split()), params))

    def fetchone(self) -> object:
        if not self._fetches:
            raise AssertionError("unexpected fetch")
        return self._fetches.pop(0)


def _deletes(cursor: _Cursor) -> list[tuple[str, object]]:
    return [call for call in cursor.calls if "DELETE FROM cache_entries" in call[0]]


def _repository() -> PostgresExactCacheRepository:
    return PostgresExactCacheRepository.__new__(PostgresExactCacheRepository)


def test_scoped_eviction_deletes_only_inside_the_hash_list() -> None:
    repository = _repository()
    owned = "a" * 64
    cursor = _Cursor([(2, 10), (owned,), (1, 10)])

    assert (
        repository._evict_cursor(cursor, 1, 100, only_query_hashes=[owned]) == 1
    )

    deletes = _deletes(cursor)
    assert len(deletes) == 1
    assert "query_hash = ANY(%s)" in deletes[0][0]
    assert deletes[0][1] == ([owned],)
    canonical_deletes = [
        call for call in cursor.calls if "DELETE FROM canonical_answers" in call[0]
    ]
    assert canonical_deletes[0][1] == (owned,)


def test_unscoped_eviction_keeps_the_global_oldest_delete() -> None:
    repository = _repository()
    cursor = _Cursor([(2, 10), ("b" * 64,), (1, 10)])

    assert repository._evict_cursor(cursor, 1, 100, only_query_hashes=None) == 1

    deletes = _deletes(cursor)
    assert len(deletes) == 1
    assert "ANY(%s)" not in deletes[0][0]
    assert deletes[0][1] in (None, ())


def test_scoped_eviction_stops_when_the_owned_set_is_within_the_cap() -> None:
    repository = _repository()
    cursor = _Cursor([(1, 10)])

    assert (
        repository._evict_cursor(cursor, 1, 100, only_query_hashes=["owned"]) == 0
    )
    assert _deletes(cursor) == []


def test_empty_scope_does_not_read_or_delete_rows() -> None:
    repository = _repository()
    cursor = _Cursor([])

    assert repository._evict_cursor(cursor, 1, 100, only_query_hashes=[]) == 0
    assert cursor.calls == []


def _postgres_sources() -> list[Path]:
    files = list((_REPO_ROOT / "tests").glob("test_*.py"))
    files.extend(
        [
            _REPO_ROOT / "src/sscre/load_test.py",
            _REPO_ROOT / "src/sscre/postgres_failure_harness.py",
            _REPO_ROOT / "src/sscre/postgres_cache.py",
        ]
    )
    selected: list[Path] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if (
            "postgres_cache" in text
            or "postgres_failure_harness" in text
            or "PostgresExactCacheRepository" in text
        ):
            selected.append(path)
    return selected


def _unguarded_shared_deletes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _GUARDED_CALLS:
            continue
        if any(keyword.arg in _SCOPE_KEYWORDS for keyword in node.keywords):
            continue
        missing.append(f"{path.as_posix()}:{node.lineno} {node.func.attr}")
    return missing


def test_postgres_callers_scope_eviction_and_cleanup() -> None:
    """Shared-database deletes must name the rows they are allowed to remove."""
    missing: list[str] = []
    for path in _postgres_sources():
        missing.extend(_unguarded_shared_deletes(path))
    assert missing == []
