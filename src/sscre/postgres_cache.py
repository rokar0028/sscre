import psycopg
from psycopg.errors import UniqueViolation

from sscre.cache import (
    CacheEntry,
    CacheRepositoryError,
    DuplicateCacheEntryError,
    ExactCacheRepository,
)
from sscre.config import Settings


class PostgresExactCacheRepository(ExactCacheRepository):
    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = (
            database_url or Settings.from_environment().database_url
        )
        if not self._database_url:
            raise CacheRepositoryError(
                "SSCRE_DATABASE_URL is required for PostgreSQL storage"
            )

    def get_by_query_hash(self, query_hash: str) -> CacheEntry | None:
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE cache_entries
                        SET last_accessed_at = now()
                        WHERE query_hash = %s
                        RETURNING query_hash, normalized_query, answer
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
        )

    def insert(self, entry: CacheEntry) -> None:
        try:
            with psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO cache_entries (
                            query_hash,
                            normalized_query,
                            answer
                        )
                        VALUES (%s, %s, %s)
                        """,
                        (
                            entry.query_hash,
                            entry.normalized_query,
                            entry.answer,
                        ),
                    )
        except UniqueViolation as exc:
            raise DuplicateCacheEntryError(
                f"query hash already exists: {entry.query_hash}"
            ) from exc
        except psycopg.Error as exc:
            raise CacheRepositoryError(
                "failed to insert into PostgreSQL cache"
            ) from exc
