"""Explicit cache invalidation experiment (Workstream 6 Step 7)."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Mapping

from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.freshness_evaluation import (
    DEFAULT_REPLAY_ANCHOR_TIME,
    FreshnessExperimentConfig,
    FreshnessPolicySpec,
    FreshnessReplayClock,
)
from sscre.query import hash_query, normalize_query
from sscre.safety import QueryMetadata

INVALIDATION_EXPERIMENT_VERSION = "1.0"

_CONTROL_QUERY = "What is explicit cache invalidation?"
_CONTROL_ANSWER_V1 = "invalidation fixture answer v1"
_CONTROL_ANSWER_V2 = "invalidation fixture answer v2"
_SEMANTIC_PROBE = (1.0, 0.0)


def _storage_snapshot(cache: InMemoryExactCache) -> dict[str, int]:
    stats = cache.storage_stats()
    return {
        "entries": stats.entries,
        "canonical_answers": stats.canonical_answers,
        "total_bytes": stats.total_bytes,
    }


def run_in_memory_invalidation_sequence(
    *,
    policy: FreshnessPolicySpec | None = None,
) -> dict[str, Any]:
    """Controlled insert → reuse → delete → regenerate on in-memory repository."""
    spec = policy or FreshnessPolicySpec(
        name="invalidation-probe",
        stable_ttl_seconds=3600,
        semi_dynamic_ttl_seconds=600,
        dynamic_ttl_seconds=None,
        allow_dynamic_entries=False,
    )
    clock = FreshnessReplayClock.from_policy_spec(
        spec,
        DEFAULT_REPLAY_ANCHOR_TIME,
    )
    metadata = QueryMetadata(
        intent="factual",
        domain="unknown",
        output_format="prose",
        temporal_class="stable",
    )
    normalized = normalize_query(_CONTROL_QUERY)
    query_hash = hash_query(normalized)
    cache = InMemoryExactCache(
        max_top_k=5,
        embedding_dimension=len(_SEMANTIC_PROBE),
    )
    ttl_expires_at = clock.ttl_expires_at_for_insert(metadata)
    entry = CacheEntry(
        query_hash=query_hash,
        normalized_query=normalized,
        answer=_CONTROL_ANSWER_V1,
        embedding=_SEMANTIC_PROBE,
        embedding_model="invalidation-fixture",
        embedding_dimension=len(_SEMANTIC_PROBE),
        metadata=metadata,
        ttl_expires_at=ttl_expires_at,
    )
    cache.insert(entry)

    stored = cache.get_by_query_hash(query_hash)
    if stored is None:
        raise RuntimeError("insert did not persist entry")
    control = clock.evaluate_cache_control("stable", stored.ttl_expires_at)
    fresh_reuse_eligible = control.reusable and control.reason == "fresh"

    semantic_before = cache.search_by_embedding(_SEMANTIC_PROBE, top_k=5)
    semantic_hit_before = any(
        candidate.query_hash == query_hash for candidate in semantic_before
    )

    started = perf_counter()
    cache.delete_by_query_hash(query_hash)
    invalidation_latency_ms = (perf_counter() - started) * 1000.0
    storage_after_delete = _storage_snapshot(cache)

    lookup_after_delete = cache.get_by_query_hash(query_hash) is None
    semantic_after = cache.search_by_embedding(_SEMANTIC_PROBE, top_k=5)
    semantic_excludes_deleted = all(
        candidate.query_hash != query_hash for candidate in semantic_after
    )

    replacement = CacheEntry(
        query_hash=query_hash,
        normalized_query=normalized,
        answer=_CONTROL_ANSWER_V2,
        embedding=_SEMANTIC_PROBE,
        embedding_model="invalidation-fixture",
        embedding_dimension=len(_SEMANTIC_PROBE),
        metadata=metadata,
        ttl_expires_at=ttl_expires_at,
    )
    cache.insert(replacement)
    storage_after_regeneration = _storage_snapshot(cache)
    regenerated = cache.get_by_query_hash(query_hash)
    regeneration_verified = (
        regenerated is not None and regenerated.answer == _CONTROL_ANSWER_V2
    )

    return {
        "repository": "in_memory_exact_cache",
        "measurement_environment": "synthetic_repository",
        "invalidation_method": "delete_by_query_hash",
        "policy_name": spec.name,
        "sequence": {
            "insert_verified": True,
            "fresh_reuse_eligible_before_invalidation": fresh_reuse_eligible,
            "exact_lookup_before_invalidation": stored.answer == _CONTROL_ANSWER_V1,
            "semantic_retrieval_includes_entry_before_invalidation": semantic_hit_before,
            "invalidation_latency_ms": round(invalidation_latency_ms, 6),
            "exact_lookup_empty_after_invalidation": lookup_after_delete,
            "semantic_retrieval_excludes_invalidated_entry": semantic_excludes_deleted,
            "regeneration_verified": regeneration_verified,
        },
        "storage_after_invalidation": storage_after_delete,
        "storage_after_regeneration": storage_after_regeneration,
        "ttl_expiration_used": False,
        "notes": [
            "cleanup_expired was not invoked; deletion is explicit invalidation only.",
        ],
    }


def build_invalidation_artifact(
    experiment: FreshnessExperimentConfig,
) -> dict[str, object]:
    scope = experiment.invalidation_scope
    base: dict[str, object] = {
        "definition_version": INVALIDATION_EXPERIMENT_VERSION,
        "scope": scope,
        "measurement_environment": "synthetic_replay",
    }

    if scope == "repository_boundary_only":
        result = run_in_memory_invalidation_sequence()
        sequence = result["sequence"]
        assert isinstance(sequence, dict)
        return {
            **base,
            "status": "evaluated",
            **result,
            "postgresql_integration": {
                "status": "not_run",
                "reason": (
                    "Step 7 uses in-memory repository boundary; PostgreSQL "
                    "delete_by_query_hash is documented but not exercised here."
                ),
            },
            "repository_capabilities": {
                "in_memory_exact_cache": {
                    "delete_by_query_hash": True,
                    "semantic_retrieval_after_delete": "entry_removed_from_index",
                },
                "postgresql_cache": {
                    "delete_by_query_hash": True,
                    "integration_evaluated": False,
                },
            },
            "constraint_satisfied": all(
                bool(sequence.get(key))
                for key in (
                    "insert_verified",
                    "exact_lookup_empty_after_invalidation",
                    "semantic_retrieval_excludes_invalidated_entry",
                    "regeneration_verified",
                )
            ),
        }

    if scope == "unavailable":
        return {
            **base,
            "status": "unavailable",
            "reason": "invalidation_scope_unavailable_in_config",
            "consequence": "TTL protection metrics only; no explicit delete experiment.",
        }

    return {
        **base,
        "status": "not_evaluated",
        "reason": "invalidation_scope_not_evaluated",
    }


def validate_invalidation_artifact(artifact: Mapping[str, object]) -> None:
    status = artifact.get("status")
    if status not in {"evaluated", "unavailable", "not_evaluated"}:
        raise ValueError("invalidation.status is not supported")
    if status == "evaluated":
        sequence = artifact.get("sequence")
        if not isinstance(sequence, Mapping):
            raise ValueError("evaluated invalidation requires sequence object")
        latency = sequence.get("invalidation_latency_ms")
        if (
            isinstance(latency, bool)
            or not isinstance(latency, (int, float))
            or latency < 0
        ):
            raise ValueError("invalidation_latency_ms must be a non-negative number")
