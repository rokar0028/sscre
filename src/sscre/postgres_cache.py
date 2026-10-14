import json

import psycopg
from psycopg.errors import UniqueViolation
from collections.abc import Sequence

from sscre.cache import (
    CacheCandidate,
    CacheEntry,
    CacheRepositoryError,
    CacheStorageStats,
    DuplicateCacheEntryError,
    ExactCacheRepository,
    _validate_scoped_insert_entry,
    validate_vector_search,
)
from sscre.query import resolve_operation_scope
from sscre.config import Settings
from sscre.safety import QueryMetadata
from sscre.migrate import default_migrations_dir, validate_migration_state


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


def _delete_unreferenced_canonical(cursor: object, canonical_hash: str | None) -> None:
    if not canonical_hash:
        return
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


def delete_entries_by_query_hashes(
    database_url: str,
    query_hashes: Sequence[str],
) -> None:
    """Delete specific cache rows and only their unreferenced canonical answers."""
    if not query_hashes:
        return
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM cache_entries
                WHERE query_hash = ANY(%s)
                RETURNING canonical_answer_hash
                """,
                (list(query_hashes),),
            )
            for row in cursor.fetchall():
                _delete_unreferenced_canonical(cursor, row[0])


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
        require_scoped_operations: bool = False,
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
                default_migrations_dir(),
                connect_timeout=5,
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
        self._require_scoped_operations = require_scoped_operations

    def check_ready(self, timeout_seconds: int = 1) -> None:
        if timeout_seconds <= 0:
            raise ValueError("readiness timeout must be positive")
        try:
            validate_migration_state(
                self._database_url,
                default_migrations_dir(),
                connect_timeout=timeout_seconds,
                read_only=True,
            )
        except (OSError, RuntimeError, ValueError, psycopg.Error) as exc:
            raise CacheRepositoryError(
                "PostgreSQL is unavailable or migrations are invalid"
            ) from exc

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
        params: list[object] = [query_hash]
        scope_sql = ""
        if scope is not None:
            scope_sql = " AND ce.tenant_id = %s AND ce.namespace_id = %s"
            params.extend([scope.tenant_id, scope.namespace_id])
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT ce.query_hash, ce.normalized_query,
                                  COALESCE(
                                      (
                                          SELECT answer
                                          FROM canonical_answers
                                          WHERE answer_hash = ce.canonical_answer_hash
                                      ),
                                      ce.answer
                                  ),
                                  ce.tenant_id, ce.namespace_id,
                                  ce.content_query_hash,
                                  ce.embedding::text, ce.embedding_model,
                                  ce.embedding_dimension, ce.metadata,
                                  ce.ttl_expires_at,
                                  ce.canonical_answer_hash
                        FROM cache_entries AS ce
                        WHERE ce.query_hash = %s{scope_sql}
                        """,
                        tuple(params),
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
            tenant_id=row[3],
            namespace_id=row[4],
            content_query_hash=row[5],
            embedding=_parse_vector(row[6]),
            embedding_model=row[7],
            embedding_dimension=row[8],
            metadata=_parse_metadata(row[9]),
            ttl_expires_at=row[10],
            canonical_answer_hash=row[11],
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
        params: list[object] = [query_hash]
        scope_sql = ""
        if scope is not None:
            scope_sql = " AND tenant_id = %s AND namespace_id = %s"
            params.extend([scope.tenant_id, scope.namespace_id])
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        UPDATE cache_entries
                        SET hit_count = hit_count + 1,
                            last_accessed_at = now()
                        WHERE query_hash = %s{scope_sql}
                        """,
                        tuple(params),
                    )
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to update PostgreSQL cache access metadata"
            ) from exc

    def _scoped_entry_filters(
        self,
        *,
        only_query_hashes: Sequence[str] | None,
        tenant_id: str | None,
        namespace_id: str | None,
    ) -> tuple[str, list[object]]:
        clauses: list[str] = []
        params: list[object] = []
        if tenant_id is not None and namespace_id is not None:
            clauses.append("tenant_id = %s AND namespace_id = %s")
            params.extend([tenant_id, namespace_id])
        if only_query_hashes is not None:
            scope = list(only_query_hashes)
            if not scope:
                return "FALSE", []
            clauses.append("query_hash = ANY(%s)")
            params.append(scope)
        if not clauses:
            return "TRUE", []
        return " AND ".join(clauses), params

    def _evict_cursor(
        self,
        cursor: object,
        max_entries: int,
        max_bytes: int,
        *,
        only_query_hashes: Sequence[str] | None = None,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> int:
        where_sql, where_params = self._scoped_entry_filters(
            only_query_hashes=only_query_hashes,
            tenant_id=tenant_id,
            namespace_id=namespace_id,
        )
        if where_sql == "FALSE":
            return 0
        evicted = 0
        while True:
            cursor.execute(
                f"""
                SELECT
                    (
                        SELECT count(*)
                        FROM cache_entries
                        WHERE {where_sql}
                    ),
                    COALESCE(
                        (
                            SELECT sum(storage_bytes)
                            FROM cache_entries
                            WHERE {where_sql}
                        ),
                        0
                    )
                    + COALESCE(
                        (
                            SELECT sum(octet_length(ca.answer))
                            FROM canonical_answers AS ca
                            WHERE ca.answer_hash IN (
                                SELECT canonical_answer_hash
                                FROM cache_entries
                                WHERE {where_sql}
                                  AND canonical_answer_hash IS NOT NULL
                            )
                        ),
                        0
                    )
                """,
                (*where_params, *where_params, *where_params),
            )
            entry_count, byte_count = cursor.fetchone()
            if entry_count <= max_entries and byte_count <= max_bytes:
                break
            cursor.execute(
                f"""
                DELETE FROM cache_entries
                WHERE query_hash = (
                    SELECT query_hash
                    FROM cache_entries
                    WHERE {where_sql}
                    ORDER BY last_accessed_at ASC, query_hash ASC
                    LIMIT 1
                )
                RETURNING canonical_answer_hash
                """,
                tuple(where_params),
            )
            deleted = cursor.fetchone()
            if deleted is None:
                break
            _delete_unreferenced_canonical(cursor, deleted[0])
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

    def evict_to_limits(
        self,
        max_entries: int,
        max_bytes: int,
        *,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> int:
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("cache limits must be positive")
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="cache eviction",
        )
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    evicted = self._evict_cursor(
                        cursor,
                        max_entries,
                        max_bytes,
                        tenant_id=scope.tenant_id if scope is not None else None,
                        namespace_id=scope.namespace_id if scope is not None else None,
                    )
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to evict PostgreSQL cache entries"
            ) from exc
        return evicted

    def storage_stats(
        self,
        *,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> "CacheStorageStats":
        scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations,
            operation="cache statistics",
        )
        scoped = scope is not None
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    if scoped:
                        cursor.execute(
                            """
                            SELECT
                                (
                                    SELECT count(*)
                                    FROM cache_entries
                                    WHERE tenant_id = %s AND namespace_id = %s
                                ),
                                (
                                    SELECT count(DISTINCT ce.canonical_answer_hash)
                                    FROM cache_entries AS ce
                                    WHERE ce.tenant_id = %s
                                      AND ce.namespace_id = %s
                                      AND ce.canonical_answer_hash IS NOT NULL
                                ),
                                COALESCE(
                                    (
                                        SELECT sum(storage_bytes)
                                        FROM cache_entries
                                        WHERE tenant_id = %s AND namespace_id = %s
                                    ),
                                    0
                                )
                                + COALESCE(
                                    (
                                        SELECT sum(octet_length(ca.answer))
                                        FROM canonical_answers AS ca
                                        WHERE ca.answer_hash IN (
                                            SELECT canonical_answer_hash
                                            FROM cache_entries
                                            WHERE tenant_id = %s
                                              AND namespace_id = %s
                                              AND canonical_answer_hash IS NOT NULL
                                        )
                                    ),
                                    0
                                ),
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
                            """,
                            (
                                scope.tenant_id,
                                scope.namespace_id,
                                scope.tenant_id,
                                scope.namespace_id,
                                scope.tenant_id,
                                scope.namespace_id,
                                scope.tenant_id,
                                scope.namespace_id,
                            ),
                        )
                    else:
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
        params: list[object] = [query_hash]
        scope_sql = ""
        if scope is not None:
            scope_sql = " AND tenant_id = %s AND namespace_id = %s"
            params.extend([scope.tenant_id, scope.namespace_id])
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        DELETE FROM cache_entries
                        WHERE query_hash = %s{scope_sql}
                        RETURNING canonical_answer_hash
                        """,
                        tuple(params),
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        _delete_unreferenced_canonical(cursor, row[0])
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to delete PostgreSQL cache entry"
            ) from exc

    def cleanup_expired(
        self,
        limit: int = 100,
        *,
        only_query_hashes: Sequence[str] | None = None,
        tenant_id: str | None = None,
        namespace_id: str | None = None,
    ) -> int:
        if limit <= 0:
            raise ValueError("cleanup limit must be positive")
        hash_scope = None if only_query_hashes is None else list(only_query_hashes)
        if hash_scope is not None and not hash_scope:
            return 0
        tenant_scope = resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=self._require_scoped_operations
            and hash_scope is None,
            operation="cache expiration cleanup",
        )
        tenant_sql = ""
        tenant_params: list[object] = []
        if tenant_scope is not None:
            tenant_sql = " AND tenant_id = %s AND namespace_id = %s"
            tenant_params = [
                tenant_scope.tenant_id,
                tenant_scope.namespace_id,
            ]
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    if hash_scope is None:
                        cursor.execute(
                            f"""
                            DELETE FROM cache_entries
                            WHERE query_hash IN (
                                SELECT query_hash
                                FROM cache_entries
                                WHERE ttl_expires_at IS NOT NULL
                                  AND ttl_expires_at <= now(){tenant_sql}
                                ORDER BY ttl_expires_at ASC, query_hash ASC
                                LIMIT %s
                            )
                            RETURNING canonical_answer_hash
                            """,
                            (*tenant_params, limit),
                        )
                    else:
                        cursor.execute(
                            f"""
                            DELETE FROM cache_entries
                            WHERE query_hash IN (
                                SELECT query_hash
                                FROM cache_entries
                                WHERE ttl_expires_at IS NOT NULL
                                  AND ttl_expires_at <= now()
                                  AND query_hash = ANY(%s){tenant_sql}
                                ORDER BY ttl_expires_at ASC, query_hash ASC
                                LIMIT %s
                            )
                            RETURNING canonical_answer_hash
                            """,
                            (hash_scope, *tenant_params, limit),
                        )
                    removed = cursor.fetchall()
                    deleted = len(removed)
                    cursor.execute(
                        """
                        UPDATE cache_lifecycle_counters
                        SET expirations = expirations + %s
                        WHERE singleton
                        """,
                        (deleted,),
                    )
                    for row in removed:
                        _delete_unreferenced_canonical(cursor, row[0])
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
                            tenant_id,
                            namespace_id,
                            content_query_hash,
                            embedding,
                            embedding_model,
                            embedding_dimension,
                            metadata,
                            ttl_expires_at,
                            canonical_answer_hash,
                            storage_bytes
                        )
                        VALUES (
                            %s, %s, NULL, %s, %s, %s, %s::vector, %s, %s,
                            %s::jsonb, %s, %s, %s
                        )
                        """,
                        (
                            entry.query_hash,
                            entry.normalized_query,
                            entry.tenant_id,
                            entry.namespace_id,
                            entry.content_query_hash,
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
        _validate_scoped_insert_entry(
            entry,
            require_predicates=self._require_scoped_operations,
        )
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
        *,
        only_query_hashes: Sequence[str] | None = None,
    ) -> None:
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("cache limits must be positive")
        _validate_scoped_insert_entry(
            entry,
            require_predicates=self._require_scoped_operations,
        )
        scope = only_query_hashes
        if scope is not None:
            scope = list(dict.fromkeys([*scope, entry.query_hash]))
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s))",
                        ("sscre.cache.write",),
                    )
                    self._insert_cursor(cursor, entry)
                    self._evict_cursor(
                        cursor,
                        max_entries,
                        max_bytes,
                        only_query_hashes=scope,
                        tenant_id=entry.tenant_id,
                        namespace_id=entry.namespace_id,
                    )
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
        *,
        tenant_id: str,
        namespace_id: str,
    ) -> tuple[CacheCandidate, ...]:
        resolve_operation_scope(
            tenant_id=tenant_id,
            namespace_id=namespace_id,
            require_predicates=True,
            operation="semantic cache search",
        )
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
                          AND ce.tenant_id = %s
                          AND ce.namespace_id = %s
                        ORDER BY ce.embedding <=> %s::vector, ce.query_hash
                        LIMIT %s
                        """,
                        (
                            vector,
                            len(embedding),
                            embedding_model,
                            embedding_model,
                            tenant_id,
                            namespace_id,
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


class ScopedPostgresExactCacheRepository(PostgresExactCacheRepository):
    """Apply cache caps and expiry cleanup only to an explicit set of hashes.

    The application repository still evicts across the whole table. Tests and
    the bounded load runner use this type so a small cap cannot delete rows
    they do not own. The written row is always included in the eviction set.
    """

    def __init__(self, database_url: str, query_hashes: Sequence[str]) -> None:
        super().__init__(database_url)
        self._scoped_query_hashes = tuple(query_hashes)

    def insert_and_evict(
        self,
        entry: CacheEntry,
        max_entries: int,
        max_bytes: int,
    ) -> None:
        super().insert_and_evict(
            entry,
            max_entries,
            max_bytes,
            only_query_hashes=(*self._scoped_query_hashes, entry.query_hash),
        )

    def cleanup_expired(self, limit: int = 100) -> int:
        return super().cleanup_expired(
            limit,
            only_query_hashes=self._scoped_query_hashes,
        )
