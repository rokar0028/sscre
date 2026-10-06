"""Apply and validate ordered PostgreSQL migrations exactly once."""

import argparse
import hashlib
import os
from pathlib import Path
import re

import psycopg


_MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_[^/]+\.sql$")


def default_migrations_dir() -> Path:
    configured = os.getenv("SSCRE_MIGRATIONS_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "migrations"


def _migration_files(migrations_dir: str | Path) -> tuple[Path, ...]:
    directory = Path(migrations_dir)
    migrations = tuple(sorted(directory.glob("*.sql")))
    if not migrations:
        raise ValueError(f"no migrations found in {directory}")
    versions = []
    for migration in migrations:
        match = _MIGRATION_NAME.fullmatch(migration.name)
        if match is None:
            raise ValueError(
                f"migration filename must be NNN_name.sql: {migration.name}"
            )
        versions.append(match.group("version"))
    if len(versions) != len(set(versions)):
        raise ValueError("migration versions must be unique")
    return migrations


def migration_checksum(migration: Path) -> str:
    return hashlib.sha256(migration.read_bytes()).hexdigest()


def _migration_state(
    cursor: object,
    migrations: tuple[Path, ...],
    *,
    ensure_checksum_column: bool = True,
) -> dict[str, str | None]:
    if ensure_checksum_column:
        cursor.execute(
            """
            ALTER TABLE schema_migrations
            ADD COLUMN IF NOT EXISTS checksum CHAR(64)
            """
        )
    cursor.execute("SELECT version, checksum FROM schema_migrations")
    return {row[0]: row[1] for row in cursor.fetchall()}


def validate_migration_state(
    database_url: str,
    migrations_dir: str | Path,
    *,
    connect_timeout: int | None = None,
    read_only: bool = False,
) -> None:
    """Require every checked-in migration to be applied and unchanged."""

    migrations = _migration_files(migrations_dir)
    expected = {
        migration.stem.split("_", 1)[0]: migration_checksum(migration)
        for migration in migrations
    }
    connection_kwargs = (
        {"connect_timeout": connect_timeout}
        if connect_timeout is not None
        else {}
    )
    with psycopg.connect(database_url, **connection_kwargs) as connection:
        with connection.cursor() as cursor:
            applied = _migration_state(
                cursor,
                migrations,
                ensure_checksum_column=not read_only,
            )
            unknown = set(applied) - set(expected)
            if unknown:
                raise RuntimeError(
                    "database contains unknown migration versions: "
                    + ", ".join(sorted(unknown))
                )
            missing = set(expected) - set(applied)
            if missing:
                raise RuntimeError(
                    "database migrations are incomplete; run sscre-migrate "
                    "(missing: " + ", ".join(sorted(missing)) + ")"
                )
            mismatched = sorted(
                version
                for version, checksum in expected.items()
                if applied[version] != checksum
            )
            if mismatched:
                raise RuntimeError(
                    "database migration checksums do not match checked-in files: "
                    + ", ".join(mismatched)
                )


def apply_migrations(database_url: str, migrations_dir: str | Path) -> tuple[str, ...]:
    migrations = _migration_files(migrations_dir)

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            bootstrap = next(
                (path for path in migrations if path.name.startswith("000_")),
                None,
            )
            if bootstrap is None:
                raise ValueError("000_schema_migrations.sql is required")
            cursor.execute(bootstrap.read_text(encoding="utf-8"))
            applied = _migration_state(cursor, migrations)
            known_versions = {
                migration.stem.split("_", 1)[0] for migration in migrations
            }
            unknown = set(applied) - known_versions
            if unknown:
                raise RuntimeError(
                    "database contains unknown migration versions: "
                    + ", ".join(sorted(unknown))
                )
            applied_now: list[str] = []
            for migration in migrations:
                version = migration.stem.split("_", 1)[0]
                if version in applied:
                    if applied[version] is None:
                        # Adopt databases created before checksum tracking. From
                        # this point onward every migration is integrity-checked.
                        cursor.execute(
                            """
                            UPDATE schema_migrations
                            SET checksum = %s
                            WHERE version = %s AND checksum IS NULL
                            """,
                            (migration_checksum(migration), version),
                        )
                    elif applied[version] != migration_checksum(migration):
                        raise RuntimeError(
                            f"migration checksum mismatch for version {version}"
                        )
                    continue
                cursor.execute(migration.read_text(encoding="utf-8"))
                cursor.execute(
                    """
                    INSERT INTO schema_migrations (version, checksum)
                    VALUES (%s, %s)
                    ON CONFLICT (version) DO NOTHING
                    """,
                    (version, migration_checksum(migration)),
                )
                applied_now.append(version)
    return tuple(applied_now)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument(
        "--migrations-dir",
        default=str(default_migrations_dir()),
    )
    args = parser.parse_args(argv)
    applied = apply_migrations(args.database_url, args.migrations_dir)
    print(f"Applied migrations: {', '.join(applied) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
