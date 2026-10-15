from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import inspect
from threading import RLock
from math import sqrt
from typing import Protocol

from sscre.api_auth import DEFAULT_NAMESPACE, TRUSTED_LOCAL_TENANT
from sscre.canonical import CanonicalAnswer, canonical_answer, hash_answer
from sscre.cache_controls import CacheControlPolicy
from sscre.query import (
    CacheScope,
    content_query_hash,
    entry_matches_scope,
    resolve_operation_scope,
    scoped_cache_key,
)
from sscre.safety import QueryMetadata

_MISSING_TTL = object()


@dataclass(frozen=True)
class CacheEntry:
    query_hash: str
    normalized_query: str
    answer: str
    tenant_id: str = TRUSTED_LOCAL_TENANT
    namespace_id: str = DEFAULT_NAMESPACE
    content_query_hash: str | None = None
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
        content_hash = self.content_query_hash or content_query_hash(
            self.normalized_query
        )
        if self.content_query_hash is None:
            object.__setattr__(self, "content_query_hash", content_hash)
        scoped_key = scoped_cache_key(
            CacheScope(self.tenant_id, self.namespace_id),
            self.normalized_query,
        )
        if self.query_hash == content_hash:
            object.__setattr__(self, "query_hash", scoped_key)
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
class CacheByteBreakdown:
    """Component bytes that sum to ``InMemoryExactCache.storage_bytes``."""

    query_bytes: int
    metadata_bytes: int
    embedding_bytes: int
    answer_bytes: int

    @property
    def total_bytes(self) -> int:
        return (
            self.query_bytes
            + self.metadata_bytes
            + self.embedding_bytes
            + self.answer_bytes
        )

    @property
    def embedding_share(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return self.embedding_bytes / self.total_bytes


def entry_byte_components(
    entry: CacheEntry,
    *,
    include_answer: bool,
) -> CacheByteBreakdown:
    """Byte parts of one entry using the same rules as cache storage accounting.

    When deduplication is on, pass ``include_answer=False``. Answer bytes are
    then counted once from the canonical store, not on every entry.
    """
    metadata = json.dumps(
        entry.metadata.to_dict() if entry.metadata is not None else {},
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return CacheByteBreakdown(
        query_bytes=len(entry.normalized_query.encode("utf-8")),
        metadata_bytes=len(metadata.encode("utf-8")),
        embedding_bytes=len(entry.embedding or ()) * 4,
        answer_bytes=len(entry.answer.encode("utf-8")) if include_answer else 0,
    )


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


def _call_with_optional_scope(
    operation: object,
    *args: object,
    tenant_id: str,
    namespace_id: str,
) -> object:
    try:
        parameters = inspect.signature(operation).parameters
    except (TypeError, ValueError):
        parameters = None
    accepts_scope = parameters is None or (
        "tenant_id" in parameters
        and "namespace_id" in parameters
    ) or (
        parameters is not None
        and any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
    )
    if accepts_scope:
        return operation(
            *args,
            tenant_id=tenant_id,
            namespace_id=namespace_id,
        )
    else:
        return operation(*args)


def _validate_scoped_insert_entry(
    entry: CacheEntry,
    *,
    require_predicates: bool,
) -> CacheScope | None:
    if not require_predicates:
        return None
    scope = resolve_operation_scope(
        tenant_id=entry.tenant_id,
        namespace_id=entry.namespace_id,
        require_predicates=True,
        operation="cache insert",
    )
    expected_key = scoped_cache_key(scope, entry.normalized_query)
    if entry.query_hash != expected_key:
        raise ValueError(
            "query_hash does not match tenant_id and namespace_id scope"
        )
    return scope


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
        *,
        tenant_id: str,
        namespace_id: str,
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
        require_scoped_operations: bool = False,
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
        self._require_scoped_operations = require_scoped_operations

    def get_by_query_hash(
        self,
        query_hash: str,
        *,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> CacheEntry | None:
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="cache lookup",
        )
        with self._lock:
            entry = self._entries.get(query_hash)
            if entry is None:
                return None
            if scope is not None and not entry_matches_scope(
                entry.tenant_id,
                entry.namespace_id,
                scope,
            ):
                return None
            return entry

    def insert(self, entry: CacheEntry) -> None:
        _validate_scoped_insert_entry(
            entry,
            require_predicates=self._require_scoped_operations,
        )
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
                    tenant_id=entry.tenant_id,
                    namespace_id=entry.namespace_id,
                    content_query_hash=entry.content_query_hash,
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
                scope=CacheScope(entry.tenant_id, entry.namespace_id),
            )

    def record_hit(
        self,
        query_hash: str,
        *,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> None:
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="cache hit accounting",
        )
        with self._lock:
            entry = self._entries.get(query_hash)
            if entry is None:
                return
            if scope is not None and not entry_matches_scope(
                entry.tenant_id,
                entry.namespace_id,
                scope,
            ):
                return
            self._access_sequence += 1
            self._access_order[query_hash] = self._access_sequence
            self._hit_counts[query_hash] += 1

    def hit_count(self, query_hash: str) -> int:
        return self._hit_counts.get(query_hash, 0)

    def _entry_size(self, entry: CacheEntry) -> int:
        return entry_byte_components(
            entry,
            include_answer=not self._deduplicate,
        ).total_bytes

    def byte_breakdown(self) -> CacheByteBreakdown:
        """Aggregate query, metadata, embedding, and answer bytes."""
        with self._lock:
            return self._byte_breakdown_unlocked()

    def _byte_breakdown_unlocked(self) -> CacheByteBreakdown:
        query_bytes = 0
        metadata_bytes = 0
        embedding_bytes = 0
        answer_bytes = 0
        for entry in self._entries.values():
            parts = entry_byte_components(
                entry,
                include_answer=not self._deduplicate,
            )
            query_bytes += parts.query_bytes
            metadata_bytes += parts.metadata_bytes
            embedding_bytes += parts.embedding_bytes
            answer_bytes += parts.answer_bytes
        if self._deduplicate:
            answer_bytes += sum(
                len(answer.answer.encode("utf-8"))
                for answer in self._canonical_answers.values()
            )
        return CacheByteBreakdown(
            query_bytes=query_bytes,
            metadata_bytes=metadata_bytes,
            embedding_bytes=embedding_bytes,
            answer_bytes=answer_bytes,
        )

    def storage_bytes(self) -> int:
        with self._lock:
            return self._byte_breakdown_unlocked().total_bytes

    def storage_stats(
        self,
        *,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> CacheStorageStats:
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="cache statistics",
        )
        with self._lock:
            if scope is None:
                return CacheStorageStats(
                    entries=len(self._entries),
                    canonical_answers=len(self._canonical_answers),
                    total_bytes=self.storage_bytes(),
                    deduplication_hits=self._deduplication_hits,
                    deduplication_savings_bytes=self._deduplication_savings_bytes,
                    expirations=self._expiration_count,
                    evictions=self._eviction_count,
                )
            scoped_entries = self._scoped_entries(scope)
            canonical_hashes = {
                entry.canonical_answer_hash
                for entry in scoped_entries.values()
                if entry.canonical_answer_hash
            }
            return CacheStorageStats(
                entries=len(scoped_entries),
                canonical_answers=len(canonical_hashes),
                total_bytes=self._scoped_storage_bytes(scope),
                deduplication_hits=self._deduplication_hits,
                deduplication_savings_bytes=self._deduplication_savings_bytes,
                expirations=self._expiration_count,
                evictions=self._eviction_count,
            )

    def delete_by_query_hash(
        self,
        query_hash: str,
        *,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> None:
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="cache delete",
        )
        with self._lock:
            entry = self._entries.get(query_hash)
            if entry is None:
                return
            if scope is not None and not entry_matches_scope(
                entry.tenant_id,
                entry.namespace_id,
                scope,
            ):
                return
            entry = self._entries.pop(query_hash)
            self._access_order.pop(query_hash, None)
            self._hit_counts.pop(query_hash, None)
            canonical_hash = entry.canonical_answer_hash
            if canonical_hash and not any(
                other.canonical_answer_hash == canonical_hash
                for other in self._entries.values()
            ):
                self._canonical_answers.pop(canonical_hash, None)

    def cleanup_expired(
        self,
        limit: int = 100,
        *,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> int:
        if limit <= 0:
            raise ValueError("cleanup limit must be positive")
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="cache expiration cleanup",
        )
        with self._lock:
            now = datetime.now(timezone.utc)
            source = self._scoped_entries(scope)
            expired = [
                query_hash
                for query_hash, entry in source.items()
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

    def _scoped_entries(self, scope: CacheScope | None) -> dict[str, CacheEntry]:
        if scope is None:
            return self._entries
        return {
            query_hash: entry
            for query_hash, entry in self._entries.items()
            if entry.tenant_id == scope.tenant_id
            and entry.namespace_id == scope.namespace_id
        }

    def _scoped_storage_bytes(self, scope: CacheScope | None) -> int:
        scoped = self._scoped_entries(scope)
        total = 0
        for entry in scoped.values():
            total += self._entry_size(entry)
        if scope is not None and self._deduplicate:
            canonical_hashes = {
                entry.canonical_answer_hash
                for entry in scoped.values()
                if entry.canonical_answer_hash
            }
            total += sum(
                len(self._canonical_answers[answer_hash].answer.encode("utf-8"))
                for answer_hash in canonical_hashes
                if answer_hash in self._canonical_answers
            )
        elif scope is None:
            return self.storage_bytes()
        return total

    def _evict_to_limits(
        self,
        max_entries: int,
        max_bytes: int,
        *,
        eviction_strategy: str = "lru",
        scope: CacheScope | None = None,
    ) -> int:
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("cache limits must be positive")
        evicted = 0
        scoped = self._scoped_entries(scope)
        while (
            len(scoped) > max_entries
            or self._scoped_storage_bytes(scope) > max_bytes
        ):
            query_hash = min(
                scoped,
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
            scoped = self._scoped_entries(scope)
        self._eviction_count += evicted
        return evicted

    def evict_to_limits(
        self,
        max_entries: int,
        max_bytes: int,
        *,
        eviction_strategy: str = "lru",
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> int:
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="cache eviction",
        )
        with self._lock:
            return self._evict_to_limits(
                max_entries,
                max_bytes,
                eviction_strategy=eviction_strategy,
                scope=scope,
            )

    def get_canonical_answer(
        self,
        answer_hash: str,
        *,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> CanonicalAnswer | None:
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="canonical answer lookup",
        )
        with self._lock:
            canonical = self._canonical_answers.get(answer_hash)
            if canonical is None:
                return None
            if scope is None:
                return canonical
            referenced = any(
                entry.canonical_answer_hash == answer_hash
                for entry in self._scoped_entries(scope).values()
            )
            if not referenced:
                return None
            return canonical

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
        *,
        tenant_id: str,
        namespace_id: str,
    ) -> tuple[CacheCandidate, ...]:
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=True,
            operation="semantic cache search",
        )
        assert scope is not None
        validate_vector_search(
            embedding,
            top_k,
            self._max_top_k,
            self._embedding_dimension,
        )
        candidates: list[CacheCandidate] = []
        with self._lock:
            entries = tuple(self._scoped_entries(scope).values())
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
