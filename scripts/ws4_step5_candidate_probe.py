"""WS4 Step 5 recall probe: DB retrieval vs application cache-control filtering."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sscre.cache_controls import evaluate_cache_control
from sscre.config import Settings
from sscre.postgres_cache import PostgresExactCacheRepository, delete_entries_by_query_hashes
from sscre.query import CacheScope, scoped_cache_key
from sscre.cache import CacheEntry
from sscre.safety import QueryMetadata

TENANT = "ws4-step5-probe"
NAMESPACE = "ws4-step5-probe"
MODEL = "test-embedding"


def _entry(
    label: str,
    answer: str,
    embedding: tuple[float, ...],
    *,
    expired: bool = False,
    namespace_id: str = NAMESPACE,
) -> CacheEntry:
    normalized = f"{label} {uuid4()}"
    ttl = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
        if expired
        else datetime.now(timezone.utc) + timedelta(hours=1)
    )
    return CacheEntry(
        query_hash=scoped_cache_key(CacheScope(TENANT, namespace_id), normalized),
        normalized_query=normalized,
        answer=answer,
        tenant_id=TENANT,
        namespace_id=namespace_id,
        embedding=embedding,
        embedding_model=MODEL,
        embedding_dimension=len(embedding),
        metadata=QueryMetadata(intent="factual", domain="general"),
        ttl_expires_at=ttl,
    )


def main() -> int:
    url = os.environ.get("SSCRE_DATABASE_URL")
    if not url:
        print("SSCRE_DATABASE_URL required", file=sys.stderr)
        return 1

    policy = Settings(runtime_profile="development").cache_control_policy()
    repo = PostgresExactCacheRepository(url)
    query_vector = (1.0, 0.0)

    expired_best = _entry("expired-best", "expired", query_vector, expired=True)
    fresh_second = _entry("fresh-second", "fresh", (0.99, 0.14))
    cross_ns = _entry(
        "cross-ns",
        "foreign",
        query_vector,
        namespace_id="foreign-ns",
    )
    population = [expired_best, fresh_second, cross_ns]
    hashes = [entry.query_hash for entry in population]

    try:
        for entry in population:
            repo.insert(entry)

        db_top1 = repo.search_by_embedding(
            query_vector,
            top_k=1,
            embedding_model=MODEL,
            tenant_id=TENANT,
            namespace_id=NAMESPACE,
        )
        db_top2 = repo.search_by_embedding(
            query_vector,
            top_k=2,
            embedding_model=MODEL,
            tenant_id=TENANT,
            namespace_id=NAMESPACE,
        )

        def reusable_count(rows: tuple) -> int:
            total = 0
            for row in rows:
                temporal = (
                    row.metadata.temporal_class
                    if row.metadata is not None
                    else "stable"
                )
                expires = row.ttl_expires_at
                control = evaluate_cache_control(
                    temporal,
                    expires if isinstance(expires, datetime) else None,
                    policy=policy,
                )
                if control.reusable:
                    total += 1
            return total

        out = {
            "protocol_id": "ws4-candidate-filter-v1",
            "tenant_id": TENANT,
            "namespace_id": NAMESPACE,
            "top_k_declared": 5,
            "embedding_dimension": 2,
            "population": {
                "total_inserted": len(population),
                "expired": 1,
                "fresh_allowed": 1,
                "cross_namespace": 1,
            },
            "db_sql_predicates": [
                "tenant_id",
                "namespace_id",
                "embedding IS NOT NULL",
                "embedding_dimension",
                "optional embedding_model",
            ],
            "db_does_not_filter": ["ttl_expires_at", "cache_control_policy"],
            "db_top1_count": len(db_top1),
            "db_top1_includes_expired": bool(
                db_top1 and db_top1[0].query_hash == expired_best.query_hash
            ),
            "db_top2_count": len(db_top2),
            "db_top2_reusable_count": reusable_count(db_top2),
            "recall_probe": {
                "top_k_1_valid_reachable": reusable_count(db_top1) > 0,
                "top_k_2_valid_reachable": reusable_count(db_top2) > 0,
                "limitation": (
                    "Post-query cache_control filtering is required; "
                    "top_k must include enough rows after SQL scope filters "
                    "for a valid candidate to appear when an expired row ranks higher."
                ),
            },
        }
        print(json.dumps(out, indent=2))
        return 0
    finally:
        delete_entries_by_query_hashes(url, hashes)


if __name__ == "__main__":
    raise SystemExit(main())
