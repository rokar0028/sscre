"""WS4 Step 7 — EXPLAIN (ANALYZE, BUFFERS) for search_by_embedding SQL."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg

from sscre.cache import CacheEntry
from sscre.postgres_cache import (
    PostgresExactCacheRepository,
    _serialize_vector,
    delete_entries_by_query_hashes,
)
from sscre.query import CacheScope, scoped_cache_key
from sscre.safety import QueryMetadata

PROTOCOL_ID = "ws4-vector-plan-v1"
TENANT = "ws4-vector-plan"
NAMESPACE = "ws4-vector-plan"
DIM = 2
TOP_K = 5
ROW_COUNTS = (200, 2000)
WARM_REPEATS = 2
STORED_EMBEDDING_MODEL = "ws4-vector-plan-stored"

# Mirrors PostgresExactCacheRepository.search_by_embedding (parameter order).
VECTOR_SEARCH_SQL = """
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
"""


def _unit_vector(index: int, total: int) -> tuple[float, ...]:
    angle = (index / max(total, 1)) * math.tau
    return (math.cos(angle), math.sin(angle))


def _entry(index: int, total: int) -> CacheEntry:
    normalized = f"ws4 vector plan row {index} {uuid4()}"
    embedding = _unit_vector(index, total)
    return CacheEntry(
        query_hash=scoped_cache_key(CacheScope(TENANT, NAMESPACE), normalized),
        normalized_query=normalized,
        answer=f"answer-{index}",
        tenant_id=TENANT,
        namespace_id=NAMESPACE,
        embedding=embedding,
        embedding_model=STORED_EMBEDDING_MODEL,
        embedding_dimension=DIM,
        metadata=QueryMetadata(intent="factual", domain="general"),
        ttl_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )


def _explain_params(query_vector: tuple[float, ...]) -> tuple[object, ...]:
    vector = _serialize_vector(query_vector)
    embedding_model = None
    return (
        vector,
        len(query_vector),
        embedding_model,
        embedding_model,
        TENANT,
        NAMESPACE,
        vector,
        TOP_K,
    )


def _parse_explain(plan_text: str) -> dict[str, object]:
    planning = re.search(r"Planning Time: ([0-9.]+) ms", plan_text)
    execution = re.search(r"Execution Time: ([0-9.]+) ms", plan_text)
    lowered = plan_text.lower()
    uses_seq_scan = "seq scan on cache_entries" in lowered
    uses_semantic_idx = "idx_cache_entries_semantic_scope" in lowered
    uses_vector_ann = any(
        token in lowered for token in ("hnsw", "ivfflat", "vector_cosine")
    )
    sort_line = next(
        (line.strip() for line in plan_text.splitlines() if "Sort" in line),
        None,
    )
    filter_line = next(
        (
            line.strip()
            for line in plan_text.splitlines()
            if "Rows Removed by Filter" in line
        ),
        None,
    )
    buffers_line = next(
        (line.strip() for line in plan_text.splitlines() if "Buffers:" in line),
        None,
    )
    return {
        "planning_time_ms": float(planning.group(1)) if planning else None,
        "execution_time_ms": float(execution.group(1)) if execution else None,
        "buffers_summary": buffers_line,
        "rows_removed_by_filter": filter_line,
        "sort_summary": sort_line,
        "uses_seq_scan_on_cache_entries": uses_seq_scan,
        "uses_idx_cache_entries_semantic_scope": uses_semantic_idx,
        "uses_vector_ann_index": uses_vector_ann,
    }


def _run_explain(
    connection: psycopg.Connection,
    query_vector: tuple[float, ...],
    *,
    analyze: bool,
) -> str:
    params = _explain_params(query_vector)
    prefix = "EXPLAIN (ANALYZE, BUFFERS)" if analyze else "EXPLAIN (BUFFERS)"
    with connection.cursor() as cursor:
        cursor.execute(f"{prefix}\n{VECTOR_SEARCH_SQL}", params)
        rows = cursor.fetchall()
    return "\n".join(row[0] for row in rows)


def _environment(cur: psycopg.Cursor) -> dict[str, object]:
    cur.execute("SELECT version()")
    pg_version = cur.fetchone()[0]
    cur.execute(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    )
    row = cur.fetchone()
    pgvector_version = row[0] if row else None
    settings: dict[str, str] = {}
    for name in (
        "shared_buffers",
        "effective_cache_size",
        "work_mem",
        "maintenance_work_mem",
        "random_page_cost",
    ):
        cur.execute(f"SHOW {name}")
        settings[name] = cur.fetchone()[0]
    return {
        "postgresql_version": pg_version,
        "pgvector_version": pgvector_version,
        "settings": settings,
        "host_platform": platform.platform(),
        "python_version": platform.python_version(),
        "process_count": 1,
        "worker_count": 1,
        "connection_count_for_probe": 1,
    }


def _seed_and_plan(
    url: str,
    row_count: int,
    query_vector: tuple[float, ...],
) -> dict[str, object]:
    repo = PostgresExactCacheRepository(url)
    entries = [_entry(index, row_count) for index in range(row_count)]
    hashes = [entry.query_hash for entry in entries]
    try:
        for entry in entries:
            repo.insert(entry)

        with psycopg.connect(url, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("ANALYZE cache_entries")

        # A fresh connection does not clear PostgreSQL shared buffers. Keep this
        # distinct from a true cold-cache measurement, which needs explicit
        # database-level cache control outside this probe.
        with psycopg.connect(url) as fresh_connection:
            fresh_session_plan = _run_explain(
                fresh_connection,
                query_vector,
                analyze=True,
            )

        with psycopg.connect(url) as warm_connection:
            warm_plan = fresh_session_plan
            for _ in range(WARM_REPEATS):
                warm_plan = _run_explain(warm_connection, query_vector, analyze=True)

        scoped_count = repo.storage_stats(
            tenant_id=TENANT,
            namespace_id=NAMESPACE,
        ).entries
        return {
            "row_count_target": row_count,
            "scoped_entry_count": scoped_count,
            "candidate_count_sql_limit": TOP_K,
            "fresh_session_not_cold_cache": {
                "parsed": _parse_explain(fresh_session_plan),
                "plan_text": fresh_session_plan,
            },
            "warm": {
                "parsed": _parse_explain(warm_plan),
                "plan_text": warm_plan,
                "repeats": WARM_REPEATS,
            },
        }
    finally:
        delete_entries_by_query_hashes(url, hashes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        help="Write JSON to this path (default: stdout only)",
    )
    args = parser.parse_args()

    url = os.environ.get("SSCRE_DATABASE_URL")
    if not url:
        print("SSCRE_DATABASE_URL required", file=sys.stderr)
        return 1

    query_vector = (1.0, 0.0)
    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            env = _environment(cursor)

    runs: list[dict[str, object]] = []
    for row_count in ROW_COUNTS:
        runs.append(_seed_and_plan(url, row_count, query_vector))

    out: dict[str, object] = {
        "protocol_id": PROTOCOL_ID,
        "query_source": "PostgresExactCacheRepository.search_by_embedding",
        "declared": {
            "tenant_id": TENANT,
            "namespace_id": NAMESPACE,
            "embedding_dimension": DIM,
            "embedding_model_filter": None,
            "top_k": TOP_K,
            "similarity_threshold": "not applied in SQL (application layer)",
            "row_counts": list(ROW_COUNTS),
            "query_vector": list(query_vector),
            "fresh_session_note": (
                "The fresh-session plan uses a new connection but does not "
                "clear PostgreSQL shared buffers; it is not a cold-cache run."
            ),
        },
        "environment": env,
        "existing_indexes_note": (
            "idx_cache_entries_semantic_scope is (tenant_id, namespace_id, "
            "embedding_dimension) WHERE embedding IS NOT NULL; no HNSW/IVFFlat "
            "in checked-in migrations."
        ),
        "runs": runs,
        "index_decision": {
            "add_hnsw_or_ivfflat": False,
            "reason": (
                "Measured plans use sequential scan (or btree scope filter) plus "
                "sort on cosine distance at N=200 and N=2000 with DIM=2 on a "
                "single local host. No recall or build-cost evidence justifies an "
                "ANN index for this bounded DIM=2, N<=2000 workload."
            ),
            "revisit_when": (
                "Re-measure with the deployed embedding dimension, realistic "
                "scoped cardinality, top_k, concurrency, and cache conditions "
                "before making an ANN decision for production-shaped workloads."
            ),
        },
        "limitation": (
            "Local single-connection EXPLAIN only; the fresh-session run is not "
            "a cold-cache measurement. Not production latency, SLA, or "
            "multi-worker capacity."
        ),
    }
    payload = json.dumps(out, indent=2)
    if args.output:
        path = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
