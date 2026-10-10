from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from threading import RLock
from math import sqrt
from typing import Protocol

from sscre.canonical import CanonicalAnswer, canonical_answer, hash_answer
from sscre.cache_controls import CacheControlPolicy
from sscre.safety import QueryMetadata

_MISSING_TTL = object()


@dataclass(frozen=True)
class CacheEntry:
    query_hash: str
    normalized_query: str
    answer: str
    embedding: tuple[float, ...] | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    metadata: QueryMetadata | None = None
    ttl_expires_at: datetime | None | object = field(
        default=_MISSING_TTL,
        repr=False,
    )
    canonical_answer_hash: str | None = None

    @property
    def answer_hash(self) -> str:
        """Return the content identity used by canonical-answer storage."""
        return hash_answer(self.answer)

    def __post_init__(self) -> None:
        if self.ttl_expires_at is _MISSING_TTL:
            freshness_class = (
                self.metadata.temporal_class
                if self.metadata is not None
                else "stable"
            )
            ttl = CacheControlPolicy().ttl_for(freshness_class)
            object.__setattr__(
                self,
                "ttl_expires_at",
                (
                    datetime.now(timezone.utc) + ttl
                    if ttl is not None
                    else None
                ),
            )
        if self.canonical_answer_hash is None:
            object.__setattr__(
                self,
                "canonical_answer_hash",
                self.answer_hash,
            )
        if (
            self.canonical_answer_hash is not None
            and self.canonical_answer_hash != self.answer_hash
        ):
            raise ValueError("canonical_answer_hash does not match answer")
        metadata = (self.embedding_model, self.embedding_dimension)
        if self.embedding is None:
            if any(value is not None for value in metadata):
                raise ValueError(
                    "embedding metadata requires an embedding vector"
                )
            return
        if self.embedding_model is None or self.embedding_dimension is None:
            raise ValueError(
                "embedding vector requires model and dimension metadata"
            )
        if self.embedding_dimension != len(self.embedding):
            raise ValueError("embedding dimension does not match vector length")


@dataclass(frozen=True)
class CacheCandidate:
    """A vector-search result with the data needed for a reuse decision."""

    query_hash: str
    normalized_query: str
    answer: str
    similarity: float
    embedding_model: str
    embedding_dimension: int
    metadata: QueryMetadata | None = None
    ttl_expires_at: datetime | None = None
    canonical_answer_hash: str | None = None


class CacheRepositoryError(RuntimeError):
    """Base error for cache storage failures."""


@dataclass(frozen=True)
class CacheStorageStats:
    entries: int
    canonical_answers: int
    total_bytes: int
    deduplication_hits: int = 0
    deduplication_savings_bytes: int = 0
    expirations: int = 0
    evictions: int = 0

    def __post_init__(self) -> None:
        # PostgreSQL COUNT/SUM arrive as Decimal and are not JSON-serializable.
        for name in (
            "entries",
            "canonical_answers",
            "total_bytes",
            "deduplication_hits",
            "deduplication_savings_bytes",
            "expirations",
            "evictions",
        ):
            object.__setattr__(self, name, int(getattr(self, name) or 0))

    @property
    def average_entry_bytes(self) -> float:
        return self.total_bytes / self.entries if self.entries else 0.0


class DuplicateCacheEntryError(CacheRepositoryError):
    """Raised when an entry already exists for the query hash."""


class ExactCacheRepository(Protocol):
    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        """Return an entry or None when the query hash is not cached."""
        ...

    def insert(self, entry: CacheEntry) -> None:
        """Insert without enforcing storage limits.

        Production callers must use ``insert_and_evict`` so insertion and
        cap enforcement happen as one repository operation.
        """
        ...

    def insert_and_evict(
        self,
        entry: CacheEntry,
        max_entries: int,
        max_bytes: int,
        eviction_strategy: str = "lru",
    ) -> None:
        """Insert and enforce both storage caps atomically."""
        ...


class SemanticCacheRepository(ExactCacheRepository, Protocol):
    def search_by_embedding(
        self,
        embedding: tuple[float, ...],
        top_k: int,
        embedding_model: str | None = None,
    ) -> tuple[CacheCandidate, ...]:
        """Return nearest model-compatible candidates in descending similarity."""
        ...


def validate_vector_search(
    embedding: tuple[float, ...],
    top_k: int,
    max_top_k: int,
    expected_dimension: int | None,
) -> None:
    if not embedding:
        raise ValueError("embedding must not be empty")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if top_k > max_top_k:
        raise ValueError(f"top_k must not exceed {max_top_k}")
    if expected_dimension is not None and len(embedding) != expected_dimension:
        raise ValueError(
            "embedding dimension does not match configured dimension"
        )


def _cosine_similarity(
    first: tuple[float, ...],
    second: tuple[float, ...],
) -> float:
    first_norm = sqrt(sum(value * value for value in first))
    second_norm = sqrt(sum(value * value for value in second))
    if first_norm == 0 or second_norm == 0:
        return 0.0
    similarity = sum(a * b for a, b in zip(first, second)) / (
        first_norm * second_norm
    )
    return max(-1.0, min(1.0, similarity))


class InMemoryExactCache:
    def __init__(
        self,
        *,
        max_top_k: int = 100,
        embedding_dimension: int | None = None,
        deduplicate: bool = True,
    ) -> None:
        if max_top_k <= 0:
            raise ValueError("max_top_k must be positive")
        if embedding_dimension is not None and embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")
        self._entries: dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._canonical_answers: dict[str, CanonicalAnswer] = {}
        self._access_order: dict[str, int] = {}
        self._hit_counts: dict[str, int] = {}
        self._access_sequence = 0
        self._deduplication_hits = 0
        self._deduplication_savings_bytes = 0
        self._expiration_count = 0
        self._eviction_count = 0
        self._max_top_k = max_top_k
        self._embedding_dimension = embedding_dimension
        self._deduplicate = deduplicate

    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        with self._lock:
            return self._entries.get(query_hash)

    def insert(self, entry: CacheEntry) -> None:
        with self._lock:
            if entry.query_hash in self._entries:
                raise DuplicateCacheEntryError(
                    f"query hash already exists: {entry.query_hash}"
                )
            answer_hash = entry.answer_hash
            if self._deduplicate:
                canonical = self._canonical_answers.get(answer_hash)
                if canonical is None:
                    canonical = canonical_answer(entry.answer)
                    self._canonical_answers[answer_hash] = canonical
                else:
                    self._deduplication_hits += 1
                    self._deduplication_savings_bytes += len(
                        entry.answer.encode("utf-8")
                    )
                stored_entry = CacheEntry(
                    query_hash=entry.query_hash,
                    normalized_query=entry.normalized_query,
                    answer=canonical.answer,
                    embedding=entry.embedding,
                    embedding_model=entry.embedding_model,
                    embedding_dimension=entry.embedding_dimension,
                    metadata=entry.metadata,
                    ttl_expires_at=entry.ttl_expires_at,
                    canonical_answer_hash=canonical.answer_hash,
                )
            else:
                stored_entry = entry
            self._entries[entry.query_hash] = stored_entry
            self._access_sequence += 1
            self._access_order[entry.query_hash] = self._access_sequence
            self._hit_counts[entry.query_hash] = 0

    def insert_and_evict(
        self,
        entry: CacheEntry,
        max_entries: int,
        max_bytes: int,
        eviction_strategy: str = "lru",
    ) -> None:
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("cache limits must be positive")
        with self._lock:
            self.insert(entry)
            self._evict_to_limits(
                max_entries,
                max_bytes,
                eviction_strategy=eviction_strategy,
            )

    def record_hit(self, query_hash: str) -> None:
        with self._lock:
            if query_hash not in self._entries:
                return
            self._access_sequence += 1
            self._access_order[query_hash] = self._access_sequence
            self._hit_counts[query_hash] += 1

    def hit_count(self, query_hash: str) -> int:
        return self._hit_counts.get(query_hash, 0)

    def _entry_size(self, entry: CacheEntry) -> int:
        metadata = json.dumps(
            entry.metadata.to_dict() if entry.metadata is not None else {},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        embedding_bytes = len(entry.embedding or ()) * 4
        answer_bytes = (
            len(entry.answer.encode("utf-8"))
            if not self._deduplicate
            else 0
        )
        return (
            len(entry.normalized_query.encode("utf-8"))
            + len(metadata.encode("utf-8"))
            + embedding_bytes
            + answer_bytes
        )

    def storage_bytes(self) -> int:
        with self._lock:
            entry_bytes = sum(
                self._entry_size(entry) for entry in self._entries.values()
            )
            canonical_bytes = sum(
                len(answer.answer.encode("utf-8"))
                for answer in self._canonical_answers.values()
            )
            return entry_bytes + canonical_bytes

    def storage_stats(self) -> CacheStorageStats:
        with self._lock:
            return CacheStorageStats(
                entries=len(self._entries),
                canonical_answers=len(self._canonical_answers),
                total_bytes=self.storage_bytes(),
                deduplication_hits=self._deduplication_hits,
                deduplication_savings_bytes=self._deduplication_savings_bytes,
                expirations=self._expiration_count,
                evictions=self._eviction_count,
            )

    def delete_by_query_hash(self, query_hash: str) -> None:
        with self._lock:
            entry = self._entries.pop(query_hash, None)
            if entry is None:
                return
            self._access_order.pop(query_hash, None)
            self._hit_counts.pop(query_hash, None)
            canonical_hash = entry.canonical_answer_hash
            if canonical_hash and not any(
                other.canonical_answer_hash == canonical_hash
                for other in self._entries.values()
            ):
                self._canonical_answers.pop(canonical_hash, None)

    def cleanup_expired(self, limit: int = 100) -> int:
        if limit <= 0:
            raise ValueError("cleanup limit must be positive")
        with self._lock:
            now = datetime.now(timezone.utc)
            expired = [
                query_hash
                for query_hash, entry in self._entries.items()
                if entry.ttl_expires_at is not None
                and entry.ttl_expires_at <= now
            ][:limit]
            for query_hash in expired:
                entry = self._entries.pop(query_hash)
                self._access_order.pop(query_hash, None)
                self._hit_counts.pop(query_hash, None)
                canonical_hash = entry.canonical_answer_hash
                if canonical_hash and not any(
                    other.canonical_answer_hash == canonical_hash
                    for other in self._entries.values()
                ):
                    self._canonical_answers.pop(canonical_hash, None)
            self._expiration_count += len(expired)
            return len(expired)

    def _eviction_key(self, query_hash: str, eviction_strategy: str) -> tuple:
        if eviction_strategy == "lru":
            return (self._access_order[query_hash], query_hash)
        if eviction_strategy != "pattern":
            raise ValueError("eviction_strategy must be lru or pattern")
        entry = self._entries[query_hash]
        freshness_rank = {
            "dynamic": 0,
            "semi_dynamic": 1,
            "stable": 2,
        }.get(
            entry.metadata.temporal_class if entry.metadata is not None else "stable",
            2,
        )
        return (
            self._hit_counts[query_hash],
            freshness_rank,
            self._access_order[query_hash],
            query_hash,
        )

    def _evict_to_limits(
        self,
        max_entries: int,
        max_bytes: int,
        *,
        eviction_strategy: str = "lru",
    ) -> int:
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("cache limits must be positive")
        evicted = 0
        while (
            len(self._entries) > max_entries
            or self.storage_bytes() > max_bytes
        ):
            query_hash = min(
                self._entries,
                key=lambda value: self._eviction_key(value, eviction_strategy),
            )
            entry = self._entries.pop(query_hash)
            self._access_order.pop(query_hash, None)
            self._hit_counts.pop(query_hash, None)
            evicted += 1
            canonical_hash = entry.canonical_answer_hash
            if canonical_hash and not any(
                other.canonical_answer_hash == canonical_hash
                for other in self._entries.values()
            ):
                self._canonical_answers.pop(canonical_hash, None)
        self._eviction_count += evicted
        return evicted

    def evict_to_limits(
        self,
        max_entries: int,
        max_bytes: int,
        *,
        eviction_strategy: str = "lru",
    ) -> int:
        with self._lock:
            return self._evict_to_limits(
                max_entries,
                max_bytes,
                eviction_strategy=eviction_strategy,
            )

    def get_canonical_answer(self, answer_hash: str) -> CanonicalAnswer | None:
        with self._lock:
            return self._canonical_answers.get(answer_hash)

    def canonical_answer_count(self) -> int:
        with self._lock:
            return len(self._canonical_answers)

    def get(self, query_hash: str) -> CacheEntry | None:
        return self.get_by_query_hash(query_hash)

    def put(self, entry: CacheEntry) -> None:
        self.insert(entry)

    def search_by_embedding(
        self,
        embedding: tuple[float, ...],
        top_k: int,
        embedding_model: str | None = None,
    ) -> tuple[CacheCandidate, ...]:
        validate_vector_search(
            embedding,
            top_k,
            self._max_top_k,
            self._embedding_dimension,
        )
        candidates: list[CacheCandidate] = []
        with self._lock:
            entries = tuple(self._entries.values())
        for entry in entries:
            if entry.embedding is None:
                continue
            if (
                embedding_model is not None
                and entry.embedding_model != embedding_model
            ):
                continue
            if len(entry.embedding) != len(embedding):
                raise ValueError(
                    "stored embedding dimension does not match query dimension"
                )
            candidates.append(
                CacheCandidate(
                    query_hash=entry.query_hash,
                    normalized_query=entry.normalized_query,
                    answer=entry.answer,
                    similarity=_cosine_similarity(entry.embedding, embedding),
                    embedding_model=entry.embedding_model or "",
                    embedding_dimension=entry.embedding_dimension or 0,
                    metadata=entry.metadata,
                    ttl_expires_at=entry.ttl_expires_at,
                    canonical_answer_hash=entry.canonical_answer_hash,
                )
            )

        candidates.sort(key=lambda candidate: (-candidate.similarity, candidate.query_hash))
        return tuple(candidates[:top_k])
