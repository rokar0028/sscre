"""Phase 4 semantic-validity protocol helpers (population filters)."""

from __future__ import annotations

from typing import Any, Mapping

from sscre.benchmark import BenchmarkRecord
from sscre.embedding import EmbeddingClient
from sscre.local_embedding import (
    LocalEmbeddingError,
    create_local_embedding_client_from_mapping,
)


def primary_headline_excluded_pair_ids(
    config: Mapping[str, Any],
) -> frozenset[str]:
    """Pair IDs excluded from primary headline replay when defined in config."""
    block = config.get("context_required_pairs")
    if not isinstance(block, dict):
        return frozenset()
    pair_ids = block.get("pair_ids")
    if not isinstance(pair_ids, list) or not pair_ids:
        return frozenset()
    policy = block.get("policy")
    if not isinstance(policy, str) or "exclude" not in policy:
        return frozenset()
    return frozenset(str(pair_id) for pair_id in pair_ids)


def apply_primary_headline_population_filter(
    records: list[BenchmarkRecord],
    config: Mapping[str, Any],
) -> tuple[list[BenchmarkRecord], dict[str, object] | None]:
    """Drop context-required pairs from headline replay when the config says so."""
    excluded = primary_headline_excluded_pair_ids(config)
    if not excluded:
        return records, None
    filtered = [record for record in records if record.id not in excluded]
    removed_ids = sorted(
        record.id for record in records if record.id in excluded
    )
    return filtered, {
        "policy": config.get("context_required_pairs", {}).get("policy"),
        "context_required_pair_ids_in_config": sorted(excluded),
        "excluded_pair_ids_applied": removed_ids,
        "excluded_count": len(removed_ids),
        "input_record_count": len(records),
        "primary_headline_record_count": len(filtered),
    }


def resolve_semantic_embedding_client(
    config: Mapping[str, Any],
) -> EmbeddingClient | None:
    """Return the configured local embedding client for P4 headline runs."""
    block = config.get("local_embedding_provider")
    if not isinstance(block, dict):
        return None
    try:
        return create_local_embedding_client_from_mapping(block)
    except LocalEmbeddingError:
        raise
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def validate_semantic_validity_cli_options(
    config: Mapping[str, Any],
    *,
    freshness_policy: str | None,
    adaptive_threshold_map: str | None,
    adaptive_threshold_map_output: str | None,
) -> None:
    """Reject headline-incompatible CLI options for the frozen P4 protocol."""
    if config.get("protocol_id") != "P4-SEMVALID":
        return
    scope = config.get("p4_headline_scope")
    if isinstance(scope, dict):
        if freshness_policy is not None:
            raise ValueError(
                "freshness policy replay is disallowed for P4-SEMVALID headline runs"
            )
        if adaptive_threshold_map is not None or adaptive_threshold_map_output is not None:
            raise ValueError(
                "adaptive threshold maps are disallowed for P4-SEMVALID headline runs"
            )


def reuse_attribution_summary(report: Mapping[str, Any]) -> dict[str, int]:
    """Summarize labeled vs unlabeled served-reuse attribution on a baseline."""
    safe = int(report.get("safe_reuse_hits", 0))
    unsafe = int(report.get("unsafe_reuse_hits", 0))
    unlabeled = int(report.get("unlabeled_candidate_reuse_hits", 0))
    return {
        "safe_reuse_hits": safe,
        "unsafe_reuse_hits": unsafe,
        "unlabeled_candidate_reuse_hits": unlabeled,
        "labeled_reuse_hits": int(report.get("labeled_reuse_hits", safe + unsafe)),
    }


def max_abstention_rate(config: Mapping[str, Any]) -> float | None:
    """Return configured Strategy C abstention ceiling when present and finite."""
    value = config.get("max_abstention_rate")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rate = float(value)
    if not 0.0 <= rate <= 1.0:
        return None
    return rate
