"""WS4 Step 3: local migration vs application roles (no secrets on stdout).

Requires:
  SSCRE_DATABASE_URL — admin/owner connection (compose ``sscre`` user)
Optional:
  SSCRE_WS4_MIGRATE_PASSWORD, SSCRE_WS4_APP_PASSWORD — local-only role passwords
  SSCRE_POSTGRES_PORT — used only when building role URLs from .env parts
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse, urlunparse

import psycopg
from psycopg import sql

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, CacheRepositoryError
from sscre.config import Settings
from sscre.postgres_cache import PostgresExactCacheRepository, ScopedPostgresExactCacheRepository
from sscre.migrate import apply_migrations, default_migrations_dir

MIGRATE_ROLE = "sscre_migrate"
APP_ROLE = "sscre_app"
PROBE_DB = "sscre_migrate_probe"
TENANT = "ws4-priv-probe"
NAMESPACE = "ws4-priv-probe"


def _password(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _url_for_role(admin_url: str, role: str, password: str, database: str) -> str:
    parsed = urlparse(admin_url)
    userinfo = f"{quote(role, safe='')}:{quote(password, safe='')}"
    return urlunparse(
        (
            parsed.scheme,
            f"{userinfo}@{parsed.hostname}:{parsed.port}",
            f"/{database}",
            "",
            "",
            "",
        )
    )


def _admin_connect(admin_url: str) -> psycopg.Connection:
    return psycopg.connect(admin_url)


def _ensure_roles(conn: psycopg.Connection, migrate_pw: str, app_pw: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s",
            (MIGRATE_ROLE,),
        )
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(MIGRATE_ROLE),
                    sql.Literal(migrate_pw),
                )
            )
        else:
            cur.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(MIGRATE_ROLE),
                    sql.Literal(migrate_pw),
                )
            )
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
        if cur.fetchone() is None:
            cur.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(APP_ROLE),
                    sql.Literal(app_pw),
                )
            )
        else:
            cur.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(APP_ROLE),
                    sql.Literal(app_pw),
                )
            )
    conn.commit()


def _database_url(admin_url: str, database: str) -> str:
    parsed = urlparse(admin_url)
    return urlunparse(
        (parsed.scheme, parsed.netloc, f"/{database}", "", "", "")
    )


def _transfer_public_ownership(admin_url: str, database: str) -> None:
    with psycopg.connect(_database_url(admin_url, database)) as db_conn:
        with db_conn.cursor() as cur:
            cur.execute(
                f"""
                DO $$
                DECLARE
                    obj record;
                BEGIN
                    FOR obj IN
                        SELECT tablename AS name
                        FROM pg_tables
                        WHERE schemaname = 'public'
                    LOOP
                        EXECUTE format(
                            'ALTER TABLE public.%I OWNER TO {MIGRATE_ROLE}',
                            obj.name
                        );
                    END LOOP;
                END
                $$;
                """
            )
        db_conn.commit()


def _grant_migrate_on_database(admin_url: str, database: str) -> None:
    with _admin_connect(admin_url) as conn:
        with conn.cursor() as cur:
            cur.execute(f"GRANT CONNECT ON DATABASE {database} TO {MIGRATE_ROLE}")
            cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {database} TO {MIGRATE_ROLE}")
        conn.commit()
    with psycopg.connect(_database_url(admin_url, database)) as db_conn:
        with db_conn.cursor() as cur:
            cur.execute(f"GRANT ALL ON SCHEMA public TO {MIGRATE_ROLE}")
            cur.execute(
                f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {MIGRATE_ROLE}"
            )
            cur.execute(
                f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {MIGRATE_ROLE}"
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f"GRANT ALL ON TABLES TO {MIGRATE_ROLE}"
            )
        db_conn.commit()
    _transfer_public_ownership(admin_url, database)


def _grant_app_runtime(admin_url: str, database: str) -> None:
    with psycopg.connect(_database_url(admin_url, database)) as db_conn:
        with db_conn.cursor() as cur:
            cur.execute(f"GRANT CONNECT ON DATABASE {database} TO {APP_ROLE}")
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
            cur.execute(
                f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE}"
            )
            for table in (
                "cache_entries",
                "canonical_answers",
                "cache_lifecycle_counters",
            ):
                cur.execute(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO {APP_ROLE}"
                )
            cur.execute(f"REVOKE ALL ON TABLE schema_migrations FROM {APP_ROLE}")
            cur.execute(
                f"GRANT SELECT ON TABLE schema_migrations TO {APP_ROLE}"
            )
            cur.execute(f"REVOKE CREATE ON SCHEMA public FROM {APP_ROLE}")
        db_conn.commit()


def _bootstrap_extensions(admin_url: str, database: str) -> None:
    """Superuser-only extension install (documented deployment bootstrap)."""

    with psycopg.connect(_database_url(admin_url, database)) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()


def _ensure_probe_database(admin_url: str) -> None:
    with _admin_connect(admin_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (PROBE_DB,),
            )
            if cur.fetchone() is None:
                cur.execute(f"CREATE DATABASE {PROBE_DB} OWNER {MIGRATE_ROLE}")
    _grant_migrate_on_database(admin_url, PROBE_DB)


def _app_runtime_exercise(app_url: str) -> dict[str, str]:
    repo = PostgresExactCacheRepository(app_url, require_scoped_operations=True)
    repo.check_ready(timeout_seconds=5)
    settings = Settings(database_url=app_url, runtime_profile="development")
    ready = TestClient(
        create_app(repository=repo, settings=settings)
    ).get("/ready")
    if ready.status_code != 200:
        raise RuntimeError(f"/ready returned {ready.status_code}")
    normalized = f"ws4 step3 probe {datetime.now(timezone.utc).isoformat()}"
    qhash = hashlib.sha256(normalized.encode()).hexdigest()
    content_hash = hashlib.sha256(b"content").hexdigest()
    entry = CacheEntry(
        query_hash=qhash,
        normalized_query=normalized,
        answer="probe answer",
        tenant_id=TENANT,
        namespace_id=NAMESPACE,
        content_query_hash=content_hash,
        embedding=(1.0, 0.0),
        embedding_model="ws4-probe",
        embedding_dimension=2,
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    scoped = ScopedPostgresExactCacheRepository(app_url, [qhash])
    scoped.insert_and_evict(entry, max_entries=100, max_bytes=1_000_000)
    if repo.get_by_query_hash(qhash, tenant_id=TENANT, namespace_id=NAMESPACE) is None:
        raise RuntimeError("exact lookup failed after insert")
    repo.record_hit(qhash, tenant_id=TENANT, namespace_id=NAMESPACE)
    hits = repo.search_by_embedding(
        (1.0, 0.0),
        top_k=1,
        embedding_model="ws4-probe",
        tenant_id=TENANT,
        namespace_id=NAMESPACE,
    )
    if not hits:
        raise RuntimeError("vector search returned no candidates")
    repo.evict_to_limits(10_000, 1_000_000, tenant_id=TENANT, namespace_id=NAMESPACE)
    scoped.cleanup_expired(limit=10)
    with psycopg.connect(app_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM cache_entries
                WHERE query_hash = %s AND tenant_id = %s AND namespace_id = %s
                """,
                (qhash, TENANT, NAMESPACE),
            )
        conn.commit()
    return {
        "repository_init": "ok",
        "check_ready": "ok",
        "api_ready_http": str(ready.status_code),
        "exact_lookup": "ok",
        "insert_and_evict": "ok",
        "record_hit": "ok",
        "vector_search": "ok",
        "evict_to_limits": "ok",
        "cleanup_expired": "ok",
    }


def _fail_closed_on_missing_migration(app_url: str, admin_url: str) -> dict[str, str]:
    with _admin_connect(admin_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM schema_migrations
                WHERE version = %s
                RETURNING version
                """,
                ("013",),
            )
            if cur.fetchone() is None:
                raise RuntimeError("version 013 missing before delete test")
        conn.commit()
    missing: str
    try:
        PostgresExactCacheRepository(app_url, require_scoped_operations=True)
        missing = "unexpected_ok"
    except CacheRepositoryError:
        missing = "cache_repository_error"
    with _admin_connect(admin_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO schema_migrations (version, checksum)
                VALUES (%s, %s)
                ON CONFLICT (version) DO NOTHING
                """,
                (
                    "013",
                    "12b2d011c1db4de6f36e4b459181d76dc11885ced49c40a0e60b049b34b43a37",
                ),
            )
        conn.commit()
    return {"missing_migration_startup": missing}


def _fail_closed_on_bad_migrations(app_url: str, admin_url: str) -> dict[str, str]:
    parsed = urlparse(admin_url)
    main_db = parsed.path.lstrip("/") or "sscre"
    with _admin_connect(admin_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT checksum FROM schema_migrations WHERE version = %s",
                ("013",),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("version 013 missing")
            good = row[0]
            cur.execute(
                "UPDATE schema_migrations SET checksum = %s WHERE version = %s",
                ("0" * 64, "013"),
            )
        conn.commit()
    stale: str
    try:
        PostgresExactCacheRepository(app_url, require_scoped_operations=True)
        stale = "unexpected_ok"
    except CacheRepositoryError:
        stale = "cache_repository_error"
    with _admin_connect(admin_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE schema_migrations SET checksum = %s WHERE version = %s",
                (good, "013"),
            )
        conn.commit()
    return {"stale_checksum_startup": stale}


def _app_lacks_ddl(app_url: str) -> dict[str, bool]:
    with psycopg.connect(app_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT has_schema_privilege(%s, 'public', 'CREATE'),
                       has_table_privilege(%s, 'schema_migrations', 'INSERT'),
                       has_table_privilege(%s, 'schema_migrations', 'SELECT')
                """,
                (APP_ROLE, APP_ROLE, APP_ROLE),
            )
            create_schema, insert_sm, select_sm = cur.fetchone()
    return {
        "app_can_create_in_public": bool(create_schema),
        "app_can_insert_schema_migrations": bool(insert_sm),
        "app_can_select_schema_migrations": bool(select_sm),
    }


def main() -> int:
    admin_url = os.environ.get("SSCRE_DATABASE_URL")
    if not admin_url:
        print("SSCRE_DATABASE_URL required", file=sys.stderr)
        return 1

    migrate_pw = _password("SSCRE_WS4_MIGRATE_PASSWORD", "ws4-local-migrate-only")
    app_pw = _password("SSCRE_WS4_APP_PASSWORD", "ws4-local-app-only")
    parsed = urlparse(admin_url)
    main_db = parsed.path.lstrip("/") or "sscre"

    migrate_url = _url_for_role(admin_url, MIGRATE_ROLE, migrate_pw, main_db)
    migrate_probe_url = _url_for_role(admin_url, MIGRATE_ROLE, migrate_pw, PROBE_DB)
    app_url = _url_for_role(admin_url, APP_ROLE, app_pw, main_db)

    out: dict[str, object] = {"roles": [MIGRATE_ROLE, APP_ROLE]}

    with _admin_connect(admin_url) as conn:
        _ensure_roles(conn, migrate_pw, app_pw)
    _grant_migrate_on_database(admin_url, main_db)
    _grant_app_runtime(admin_url, main_db)

    applied_main = apply_migrations(migrate_url, default_migrations_dir())
    out["migrate_role_main_db"] = {
        "database": main_db,
        "applied_migrations": list(applied_main),
        "migrate_exit": 0,
    }

    _ensure_probe_database(admin_url)
    _bootstrap_extensions(admin_url, PROBE_DB)
    applied = apply_migrations(migrate_probe_url, default_migrations_dir())
    out["migrate_role_probe_db"] = {
        "database": PROBE_DB,
        "applied_migrations": list(applied),
        "migrate_exit": 0,
    }

    out["app_privileges"] = _app_lacks_ddl(app_url)
    out["runtime_path"] = _app_runtime_exercise(app_url)
    out["fail_closed"] = {
        **_fail_closed_on_bad_migrations(app_url, admin_url),
        **_fail_closed_on_missing_migration(app_url, admin_url),
    }

    with psycopg.connect(app_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT has_schema_privilege(%s, 'public', 'CREATE'),
                       has_table_privilege(%s, 'schema_migrations', 'INSERT')
                """,
                (APP_ROLE, APP_ROLE),
            )
            create_schema, insert_sm = cur.fetchone()
    out["post_check_app_privileges"] = {
        "app_can_create_in_public": bool(create_schema),
        "app_can_insert_schema_migrations": bool(insert_sm),
    }
    PostgresExactCacheRepository(app_url).check_ready(timeout_seconds=5)
    out["runtime_path_after_privilege_recheck"] = {"check_ready": "ok"}

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
