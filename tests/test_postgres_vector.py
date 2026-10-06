import pytest

from sscre.cache import CacheRepositoryError
from sscre.postgres_cache import ensure_pgvector_available


class FakeCursor:
    def __init__(self, available: bool) -> None:
        self.available = available

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str) -> None:
        assert "pg_extension" in query
        assert "vector" in query

    def fetchone(self) -> tuple[bool]:
        return (self.available,)


class FakeConnection:
    def __init__(self, available: bool) -> None:
        self.available = available

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.available)


def test_pgvector_verification_accepts_available_extension(monkeypatch) -> None:
    monkeypatch.setattr(
        "sscre.postgres_cache.psycopg.connect",
        lambda database_url: FakeConnection(available=True),
    )

    ensure_pgvector_available("postgresql://example")


def test_pgvector_verification_reports_missing_extension(monkeypatch) -> None:
    monkeypatch.setattr(
        "sscre.postgres_cache.psycopg.connect",
        lambda database_url: FakeConnection(available=False),
    )

    with pytest.raises(CacheRepositoryError, match="pgvector is unavailable"):
        ensure_pgvector_available("postgresql://example")


def test_pgvector_verification_requires_database_url(monkeypatch) -> None:
    monkeypatch.delenv("SSCRE_DATABASE_URL", raising=False)
    with pytest.raises(CacheRepositoryError, match="SSCRE_DATABASE_URL"):
        ensure_pgvector_available(None)
