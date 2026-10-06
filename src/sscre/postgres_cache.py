import json

import psycopg
from psycopg.errors import UniqueViolation
from collections.abc import Sequence
from pathlib import Path

from sscre.cache import (
    CacheCandidate,
    CacheEntry,
    CacheRepositoryError,
    CacheStorageStats,
    DuplicateCacheEntryError,
    ExactCacheRepository,
    validate_vector_search,
)
from sscre.config import Settings
from sscre.safety import QueryMetadata
from sscre.migrate import validate_migration_state


def _serialize_vector(vector: tuple[float, ...] | None) -> str | None:
    if vector is None:
        return None
    return "[" + ",".join(repr(value) for value in vector) + "]"


def _parse_vector(value: str | Sequence[float] | None) -> tuple[float, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        raw_values = value.strip().strip("[]")
        if not raw_values:
            return ()
        return tuple(float(item) for item in raw_values.split(","))
    return tuple(float(item) for item in value)


def _serialize_metadata(metadata: QueryMetadata | None) -> str:
    return json.dumps(metadata.to_dict() if metadata is not None else {})


def _entry_storage_bytes(entry: CacheEntry) -> int:
    metadata = _serialize_metadata(entry.metadata)
    return (
        len(entry.normalized_query.encode("utf-8"))
        + len(metadata.encode("utf-8"))
        + (len(entry.embedding) * 4 if entry.embedding is not None else 0)
    )


def _parse_metadata(value: object) -> QueryMetadata | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict) or not value:
        return None
    return QueryMetadata.from_dict(value)


def ensure_pgvector_available(database_url: str | None = None) -> None:
    """Verify pgvector before any migration creates vector columns."""

    resolved_url = database_url or Settings.from_environment().database_url
    if not resolved_url:
        raise CacheRepositoryError(
            "SSCRE_DATABASE_URL is required to verify pgvector"
        )

    try:
        with psycopg.connect(resolved_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_extension
                        WHERE extname = 'vector'
                    )
                    """
                )
                available = cursor.fetchone()[0]
    except psycopg.Error as exc:
        raise CacheRepositoryError(
            "failed to verify the pgvector extension"
        ) from exc

    if not available:
        raise CacheRepositoryError(
            "pgvector is unavailable; apply "
            "migrations/002_enable_pgvector.sql before creating vector columns"
        )


class PostgresExactCacheRepository(ExactCacheRepository):
    def __init__(
        self,
        database_url: str | None = None,
        *,
        max_top_k: int = 100,
        embedding_dimension: int | None = None,
    ) -> None:
        self._database_url = (
            database_url or Settings.from_environment().database_url
        )
        if not self._database_url:
            raise CacheRepositoryError(
                "SSCRE_DATABASE_URL is required for PostgreSQL storage"
            )
        try:
            validate_migration_state(
                self._database_url,
                Path(__file__).resolve().parents[2] / "migrations",
            )
        except (OSError, RuntimeError, psycopg.Error) as exc:
            raise CacheRepositoryError(
                "PostgreSQL migrations are missing or out of date; run "
                "sscre-migrate before starting SSCRE"
            ) from exc
        if max_top_k <= 0:
            raise ValueError("max_top_k must be positive")
        if embedding_dimension is not None and embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")
        self._max_top_k = max_top_k
        self._embedding_dimension = embedding_dimension

    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT ce.query_hash, ce.normalized_query,
                                  COALESCE(
                                      (
                                          SELECT answer
                                          FROM canonical_answers
                                          WHERE answer_hash = ce.canonical_answer_hash
                                      ),
                                      ce.answer
                                  ),
                                  ce.embedding::text, ce.embedding_model,
                                  ce.embedding_dimension, ce.metadata,
                                  ce.ttl_expires_at,
                                  ce.canonical_answer_hash
                        FROM cache_entries AS ce
                        WHERE ce.query_hash = %s
                        """,
                        (query_hash,),
                    )
                    row = cursor.fetchone()
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to read from PostgreSQL cache"
            ) from exc

        if row is None:
            return None
        return CacheEntry(
            query_hash=row[0],
            normalized_query=row[1],
            answer=row[2],
            embedding=_parse_vector(row[3]),
            embedding_model=row[4],
            embedding_dimension=row[5],
            metadata=_parse_metadata(row[6]),
            ttl_expires_at=row[7],
            canonical_answer_hash=row[8],
        )

    def record_hit(self, query_hash: str) -> None:
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE cache_entries
                        SET hit_count = hit_count + 1,
                            last_accessed_at = now()
                        WHERE query_hash = %s
                        """,
                        (query_hash,),
                    )
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to update PostgreSQL cache access metadata"
            ) from exc

    def _evict_cursor(
        self,
        cursor: object,
        max_entries: int,
        max_bytes: int,
    ) -> int:
        evicted = 0
        while True:
            cursor.execute(
                            """
                            SELECT
                                (SELECT count(*) FROM cache_entries),
                                COALESCE(
                                    (SELECT sum(storage_bytes)
                                     FROM cache_entries),
                                    0
                                )
                                + COALESCE(
                                    (SELECT sum(octet_length(answer))
                                     FROM canonical_answers),
                                    0
                                )
                            """
                        )
            entry_count, byte_count = cursor.fetchone()
            if entry_count <= max_entries and byte_count <= max_bytes:
                break
            cursor.execute(
                            """
                            DELETE FROM cache_entries
                            WHERE query_hash = (
                                SELECT query_hash
                                FROM cache_entries
                                ORDER BY last_accessed_at ASC, query_hash ASC
                                LIMIT 1
                            )
                            RETURNING canonical_answer_hash
                            """
                        )
            deleted = cursor.fetchone()
            if deleted is None:
                break
            canonical_hash = deleted[0]
            if canonical_hash:
                cursor.execute(
                                """
                                DELETE FROM canonical_answers AS ca
                                WHERE ca.answer_hash = %s
                                  AND NOT EXISTS (
                                      SELECT 1
                                      FROM cache_entries
                                      WHERE canonical_answer_hash = ca.answer_hash
                                  )
                                """,
                                (canonical_hash,),
                            )
            evicted += 1
        if evicted:
            cursor.execute(
                """
                UPDATE cache_lifecycle_counters
                SET evictions = evictions + %s
                WHERE singleton
                """,
                (evicted,),
            )
        return evicted

    def evict_to_limits(self, max_entries: int, max_bytes: int) -> int:
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("cache limits must be positive")
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    evicted = self._evict_cursor(
                        cursor,
                        max_entries,
                        max_bytes,
                    )
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to evict PostgreSQL cache entries"
            ) from exc
        return evicted

    def storage_stats(self) -> "CacheStorageStats":
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            (SELECT count(*) FROM cache_entries),
                            (SELECT count(*) FROM canonical_answers),
                            (SELECT COALESCE(sum(storage_bytes), 0)
                             FROM cache_entries)
                            + (SELECT COALESCE(sum(octet_length(answer)), 0)
                               FROM canonical_answers),
                            (SELECT deduplication_hits
                             FROM cache_lifecycle_counters
                             WHERE singleton),
                            (SELECT deduplication_savings_bytes
                             FROM cache_lifecycle_counters
                             WHERE singleton),
                            (SELECT expirations
                             FROM cache_lifecycle_counters
                             WHERE singleton),
                            (SELECT evictions
                             FROM cache_lifecycle_counters
                             WHERE singleton)
                        """
                    )
                    row = cursor.fetchone()
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to read PostgreSQL cache statistics"
            ) from exc
        return CacheStorageStats(
            entries=row[0],
            canonical_answers=row[1],
            total_bytes=row[2],
            deduplication_hits=row[3],
            deduplication_savings_bytes=row[4],
            expirations=row[5],
            evictions=row[6],
        )

    def cleanup_expired(self, limit: int = 100) -> int:
        if limit <= 0:
            raise ValueError("cleanup limit must be positive")
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM cache_entries
                        WHERE query_hash IN (
                            SELECT query_hash
                            FROM cache_entries
                            WHERE ttl_expires_at IS NOT NULL
                              AND ttl_expires_at <= now()
                            ORDER BY ttl_expires_at ASC, query_hash ASC
                            LIMIT %s
                        )
                        """,
                        (limit,),
                    )
                    deleted = cursor.rowcount
                    cursor.execute(
                        """
                        UPDATE cache_lifecycle_counters
                        SET expirations = expirations + %s
                        WHERE singleton
                        """,
                        (deleted,),
                    )
                    cursor.execute(
                        """
                        DELETE FROM canonical_answers AS ca
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM cache_entries
                            WHERE canonical_answer_hash = ca.answer_hash
                        )
                        """
                    )
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to clean up expired PostgreSQL cache entries"
            ) from exc
        return deleted

    def _insert_cursor(self, cursor: object, entry: CacheEntry) -> None:
        answer_hash = entry.answer_hash
        cursor.execute(
                        """
                        INSERT INTO canonical_answers (answer_hash, answer)
                        VALUES (%s, %s)
                        ON CONFLICT (answer_hash) DO NOTHING
                        """,
                        (answer_hash, entry.answer),
                    )
        if cursor.rowcount == 0:
            cursor.execute(
                """
                UPDATE cache_lifecycle_counters
                SET deduplication_hits = deduplication_hits + 1,
                    deduplication_savings_bytes =
                        deduplication_savings_bytes + %s
                WHERE singleton
                """,
                (len(entry.answer.encode("utf-8")),),
            )
        cursor.execute(
                        """
                        INSERT INTO cache_entries (
                            query_hash,
                            normalized_query,
                            answer,
                            embedding,
                            embedding_model,
                            embedding_dimension,
                            metadata,
                            ttl_expires_at,
                            canonical_answer_hash,
                            storage_bytes
                        )
                        VALUES (
                            %s, %s, NULL, %s::vector, %s, %s, %s::jsonb,
                            %s, %s, %s
                        )
                        """,
                        (
                            entry.query_hash,
                            entry.normalized_query,
                            _serialize_vector(entry.embedding),
                            entry.embedding_model,
                            entry.embedding_dimension,
                            _serialize_metadata(entry.metadata),
                            entry.ttl_expires_at,
                            answer_hash,
                            _entry_storage_bytes(entry),
                        ),
                    )

    def insert(self, entry: CacheEntry) -> None:
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    self._insert_cursor(cursor, entry)
        except UniqueViolation as exc:
            raise DuplicateCacheEntryError(
                f"query hash already exists: {entry.query_hash}"
            ) from exc
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to insert into PostgreSQL cache"
            ) from exc

    def insert_and_evict(
        self,
        entry: CacheEntry,
        max_entries: int,
        max_bytes: int,
    ) -> None:
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("cache limits must be positive")
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        ("sscre.cache.write",),
                    )
                    self._insert_cursor(cursor, entry)
                    self._evict_cursor(cursor, max_entries, max_bytes)
        except UniqueViolation as exc:
            raise DuplicateCacheEntryError(
                f"query hash already exists: {entry.query_hash}"
            ) from exc
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to insert and evict PostgreSQL cache"
            ) from exc

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
        vector = _serialize_vector(embedding)
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT ce.query_hash, ce.normalized_query,
                               COALESCE(ca.answer, ce.answer),
                               ce.embedding_model, ce.embedding_dimension,
                               ce.metadata,
                               ce.ttl_expires_at,
                               ce.canonical_answer_hash,
                               1 - (ce.embedding <=> %s::vector) AS similarity
                        FROM cache_entries AS ce
                        LEFT JOIN canonical_answers AS ca
                            ON ca.answer_hash = ce.canonical_answer_hash
                        WHERE ce.embedding IS NOT NULL
                          AND ce.embedding_dimension = %s
                          AND (%s::text IS NULL OR ce.embedding_model = %s)
                          AND ce.ttl_expires_at IS NOT NULL
                          AND ce.ttl_expires_at > now()
                        ORDER BY ce.embedding <=> %s::vector, ce.query_hash
                        LIMIT %s
                        """,
                        (
                            vector,
                            len(embedding),
                            embedding_model,
                            embedding_model,
                            vector,
                            top_k,
                        ),
                    )
                    rows = cursor.fetchall()
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to search PostgreSQL cache embeddings"
            ) from exc

        return tuple(
            CacheCandidate(
                query_hash=row[0],
                normalized_query=row[1],
                answer=row[2],
                embedding_model=row[3],
                embedding_dimension=row[4],
                metadata=_parse_metadata(row[5]),
                ttl_expires_at=row[6],
                canonical_answer_hash=row[7],
                similarity=float(row[8]),
            )
            for row in rows
        )
