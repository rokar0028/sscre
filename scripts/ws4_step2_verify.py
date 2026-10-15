"""One-off WS4 Step 2 schema probes (no secrets on stdout)."""

import json
import os
import sys

import psycopg

from sscre.postgres_cache import PostgresExactCacheRepository


def main() -> int:
    url = os.environ.get("SSCRE_DATABASE_URL")
    if not url:
        print("SSCRE_DATABASE_URL required", file=sys.stderr)
        return 1

    repo = PostgresExactCacheRepository(url)
    repo.check_ready(timeout_seconds=5)

    out: dict[str, object] = {"repository_init": "ok", "check_ready": "ok"}

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT to_regclass('public.cache_entries'),
                       to_regclass('public.canonical_answers'),
                       to_regclass('public.cache_lifecycle_counters'),
                       to_regclass('public.schema_migrations')
                """
            )
            row = cur.fetchone()
            out["tables"] = {
                name: reg is not None
                for name, reg in zip(
                    (
                        "cache_entries",
                        "canonical_answers",
                        "cache_lifecycle_counters",
                        "schema_migrations",
                    ),
                    row,
                )
            }
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'cache_entries'
                ORDER BY ordinal_position
                """
            )
            out["cache_entries_columns"] = [r[0] for r in cur.fetchall()]
            cur.execute(
                """
                SELECT count(*)
                FROM information_schema.table_constraints
                WHERE table_schema = 'public'
                  AND table_name = 'cache_entries'
                  AND constraint_type IN ('CHECK', 'FOREIGN KEY', 'UNIQUE')
                """
            )
            out["cache_entries_constraint_count"] = cur.fetchone()[0]
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'cache_entries'
                ORDER BY indexname
                """
            )
            out["cache_entries_indexes"] = [r[0] for r in cur.fetchall()]
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_operator AS o
                    JOIN pg_namespace AS n ON n.oid = o.oprnamespace
                    WHERE n.nspname = 'public' AND o.oprname = '<=>'
                )
                """
            )
            out["vector_cosine_distance_operator"] = cur.fetchone()[0]
            try:
                cur.execute(
                    """
                    INSERT INTO cache_entries (
                        query_hash, normalized_query, answer,
                        tenant_id, namespace_id, content_query_hash,
                        canonical_answer_hash
                    ) VALUES (
                        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                        'fk-probe', 'x', 't1', 'n1',
                        'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
                        'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
                    )
                    """
                )
                conn.commit()
                out["fk_probe"] = "unexpected_insert_ok"
            except psycopg.Error:
                conn.rollback()
                out["fk_probe"] = "rejected"

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
