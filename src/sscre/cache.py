from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CacheEntry:
    query_hash: str
    normalized_query: str
    answer: str


class CacheRepositoryError(RuntimeError):
    """Base error for cache storage failures."""


class DuplicateCacheEntryError(CacheRepositoryError):
    """Raised when an entry already exists for the query hash."""


class ExactCacheRepository(Protocol):
    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        """Return an entry or None when the query hash is not cached."""
        ...

    def insert(self, entry: CacheEntry) -> None:
        """Insert an entry or raise DuplicateCacheEntryError."""
        ...


class InMemoryExactCache:
    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}

    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        return self._entries.get(query_hash)

    def insert(self, entry: CacheEntry) -> None:
        if entry.query_hash in self._entries:
            raise DuplicateCacheEntryError(
                f"query hash already exists: {entry.query_hash}"
            )
        self._entries[entry.query_hash] = entry

    def get(self, query_hash: str) -> CacheEntry | None:
        return self.get_by_query_hash(query_hash)

    def put(self, entry: CacheEntry) -> None:
        self.insert(entry)
