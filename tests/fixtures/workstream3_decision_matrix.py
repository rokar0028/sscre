"""Frozen Workstream 3 decision test matrix (step 1).

Rows describe expected compatibility outcomes and request-path behavior.
Step 2+ tests should import expectations from here instead of duplicating
tables in each test module.

See ``docs/phase-2/WORKSTREAM_3_STEP1_AUDIT.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SafetyDecision = Literal["SAFE", "UNSAFE", "UNCERTAIN"]
MatrixLayer = Literal["pure_evaluator", "request_path"]
CandidateDisposition = Literal[
    "evaluated",
    "filtered_before_evaluation",
    "not_retrieved",
]

CONTRACT_VERSIONS: dict[str, str] = {
    "safety_evaluation": "1.0.0",
    "candidate_trace": "1.0.0",
    "serialization_boundary": "1.0.0",
}


@dataclass(frozen=True, slots=True)
class PureEvaluatorExpectation:
    """One row in the pure ``evaluate_candidate`` matrix (step 2 target)."""

    row_id: str
    condition: str
    decision: SafetyDecision
    reason: str
    planned_step: int = 2


@dataclass(frozen=True, slots=True)
class RequestPathExpectation:
    """One row in the HTTP / query orchestration matrix (steps 3–7)."""

    path_id: str
    description: str
    strategy: Literal["A", "B", "C", "generated"]
    contract_path: bool
    generation_required: bool
    expected_source: Literal["cache", "generated", "error"]
    expected_decision: SafetyDecision | None
    reason_pattern: str
    min_trace_count: int
    candidate_disposition: CandidateDisposition
    freshness_gate: str | None
    existing_test: str | None
    planned_step: int
    known_gap: str | None = None


PURE_EVALUATOR_MATRIX: tuple[PureEvaluatorExpectation, ...] = (
    PureEvaluatorExpectation(
        "pe_similarity_below",
        "similarity below threshold",
        "UNSAFE",
        "similarity_below_threshold",
    ),
    PureEvaluatorExpectation(
        "pe_dynamic_query",
        "query temporal_class dynamic",
        "UNSAFE",
        "dynamic_query_not_reusable",
    ),
    PureEvaluatorExpectation(
        "pe_missing_candidate_metadata",
        "candidate.metadata is None",
        "UNCERTAIN",
        "candidate_metadata_missing",
    ),
    PureEvaluatorExpectation(
        "pe_dynamic_candidate",
        "candidate temporal_class dynamic",
        "UNSAFE",
        "candidate_is_dynamic",
    ),
    PureEvaluatorExpectation(
        "pe_constraint_mismatch",
        "shared constraint key, different value",
        "UNSAFE",
        "constraint_mismatch:<key>",
    ),
    PureEvaluatorExpectation(
        "pe_incomplete_constraints",
        "constraint key sets differ",
        "UNCERTAIN",
        "incomplete_constraint_evidence",
    ),
    PureEvaluatorExpectation(
        "pe_entity_mismatch",
        "both sides have entities, no overlap",
        "UNSAFE",
        "entity_mismatch",
    ),
    PureEvaluatorExpectation(
        "pe_incomplete_entities",
        "entity evidence on one side only",
        "UNCERTAIN",
        "incomplete_entity_evidence",
    ),
    PureEvaluatorExpectation(
        "pe_intent_mismatch",
        "known intent values differ",
        "UNSAFE",
        "intent_mismatch",
    ),
    PureEvaluatorExpectation(
        "pe_domain_mismatch",
        "known domain values differ",
        "UNSAFE",
        "domain_mismatch",
    ),
    PureEvaluatorExpectation(
        "pe_format_mismatch",
        "known output_format values differ",
        "UNSAFE",
        "format_mismatch",
    ),
    PureEvaluatorExpectation(
        "pe_missing_intent_evidence",
        "intent unknown on one side",
        "UNCERTAIN",
        "missing_intent_evidence",
    ),
    PureEvaluatorExpectation(
        "pe_missing_domain_evidence",
        "domain unknown on one side",
        "UNCERTAIN",
        "missing_domain_evidence",
    ),
    PureEvaluatorExpectation(
        "pe_missing_format_evidence",
        "output_format unknown on one side",
        "UNCERTAIN",
        "missing_output_format_evidence",
    ),
    PureEvaluatorExpectation(
        "pe_temporal_mismatch",
        "temporal_class differs (non-dynamic policy)",
        "UNCERTAIN",
        "temporal_class_mismatch",
    ),
    PureEvaluatorExpectation(
        "pe_compatible",
        "complete compatible metadata",
        "SAFE",
        "compatible_metadata",
    ),
)


REQUEST_PATH_MATRIX: tuple[RequestPathExpectation, ...] = (
    RequestPathExpectation(
        "rp_exact_pre_embed_c",
        "Exact hash hit before embedding (Strategy C)",
        "C",
        True,
        False,
        "cache",
        "SAFE",
        "exact_query_hash_match|compatible_metadata",
        1,
        "evaluated",
        "fresh",
        "test_strategy_c_exact_compatible_hit_is_safe_with_selection",
        5,
        None,
    ),
    RequestPathExpectation(
        "rp_exact_pre_embed_a",
        "Exact hash hit before embedding (Strategy A / non-C skip)",
        "A",
        False,
        False,
        "cache",
        "SAFE",
        "exact_query_hash_match",
        1,
        "evaluated",
        "fresh",
        None,
        5,
        "Legacy path when semantic_strategy != C on exact hit.",
    ),
    RequestPathExpectation(
        "rp_semantic_b_threshold",
        "Semantic hit from similarity only (Strategy B)",
        "B",
        False,
        False,
        "cache",
        "SAFE",
        "similarity_threshold_met",
        1,
        "evaluated",
        "fresh",
        "test_semantic_candidate_is_reused_after_exact_miss",
        5,
        "Experiment baseline; not the compatibility contract path.",
    ),
    RequestPathExpectation(
        "rp_semantic_c_compatible",
        "Semantic retrieval + compatible metadata (Strategy C)",
        "C",
        True,
        False,
        "cache",
        "SAFE",
        "compatible_metadata",
        1,
        "evaluated",
        "fresh",
        "test_strategy_c_reuses_only_a_compatible_semantic_candidate",
        5,
        None,
    ),
    RequestPathExpectation(
        "rp_semantic_c_incompatible",
        "Semantic retrieval + constraint mismatch (Strategy C)",
        "C",
        True,
        True,
        "generated",
        "UNSAFE",
        "all candidates were incompatible",
        1,
        "evaluated",
        "fresh",
        "test_strategy_c_generates_for_an_incompatible_semantic_candidate",
        5,
        None,
    ),
    RequestPathExpectation(
        "rp_semantic_c_uncertain_metadata",
        "Semantic similarity with missing candidate metadata (Strategy C default)",
        "C",
        True,
        True,
        "generated",
        "UNCERTAIN",
        "no candidate had sufficient compatibility evidence",
        1,
        "evaluated",
        "fresh",
        "test_default_strategy_does_not_reuse_metadata_less_semantic_candidate",
        5,
        None,
    ),
    RequestPathExpectation(
        "rp_exact_recheck_post_lock",
        "Exact recheck after generation lock (Strategy C)",
        "C",
        True,
        False,
        "cache",
        "SAFE",
        "compatible_metadata|exact_query_hash_match",
        1,
        "evaluated",
        "fresh",
        "test_post_generation_exact_recheck_runs_strategy_c_compatibility",
        5,
        None,
    ),
    RequestPathExpectation(
        "rp_duplicate_write_incompatible",
        "Duplicate insert returns incompatible raced entry (Strategy C)",
        "C",
        True,
        True,
        "generated",
        "UNSAFE",
        "all candidates were incompatible",
        1,
        "evaluated",
        "fresh",
        "test_duplicate_write_recovery_applies_strategy_c_to_raced_entry|"
        "test_duplicate_write_incompatible_entry_evaluated_not_served",
        5,
        None,
    ),
    RequestPathExpectation(
        "rp_duplicate_write_expired",
        "Duplicate insert returns expired raced entry (Strategy C)",
        "C",
        True,
        True,
        "generated",
        "UNSAFE",
        "all candidates were incompatible",
        1,
        "evaluated",
        "expired",
        "test_duplicate_write_expired_entry_emits_retrieval_trace",
        7,
        None,
    ),
    RequestPathExpectation(
        "rp_duplicate_write_compatible",
        "Duplicate insert returns compatible raced entry (Strategy C)",
        "C",
        True,
        False,
        "cache",
        "SAFE",
        "compatible_metadata",
        1,
        "evaluated",
        "fresh",
        "test_duplicate_write_compatible_entry_reuses_after_compatibility_check",
        7,
        None,
    ),
    RequestPathExpectation(
        "rp_concurrent_same_query_c",
        "Concurrent same-query race under Strategy C",
        "C",
        True,
        False,
        "cache|generated",
        "SAFE",
        "compatible_metadata",
        1,
        "evaluated",
        "fresh",
        "test_concurrent_same_query_shared_repository_strategy_c",
        7,
        None,
    ),
    RequestPathExpectation(
        "rp_expired_exact",
        "Expired exact entry blocked by cache control",
        "C",
        True,
        True,
        "generated",
        "UNSAFE",
        "all candidates were incompatible",
        1,
        "evaluated",
        "expired",
        "test_expired_exact_entry_emits_retrieval_trace_and_does_not_reuse",
        3,
        None,
    ),
    RequestPathExpectation(
        "rp_dynamic_exact_disabled",
        "Dynamic exact entry blocked by policy",
        "C",
        True,
        True,
        "generated",
        "UNSAFE",
        "all candidates were incompatible",
        1,
        "evaluated",
        "dynamic_entries_disabled",
        "test_dynamic_exact_entry_emits_dynamic_disabled_trace",
        3,
        None,
    ),
    RequestPathExpectation(
        "rp_missing_ttl",
        "Missing TTL on stored entry",
        "C",
        True,
        True,
        "generated",
        "UNCERTAIN",
        "no candidate had sufficient compatibility evidence",
        1,
        "evaluated",
        "missing_expiration",
        "test_missing_ttl_emits_missing_expiration_trace",
        3,
        None,
    ),
    RequestPathExpectation(
        "rp_repo_unavailable",
        "Repository failure on lookup",
        "C",
        True,
        True,
        "error",
        None,
        "n/a",
        0,
        "not_retrieved",
        None,
        "test_cache_repository_failure_returns_503_with_request_id",
        6,
        "HTTP 503; no QueryResponse decision.",
    ),
    RequestPathExpectation(
        "rp_embedding_malformed",
        "Malformed embedding after miss",
        "C",
        True,
        False,
        "generated",
        "UNCERTAIN",
        "embedding_unavailable|no candidates were retrieved",
        0,
        "not_retrieved",
        None,
        "test_malformed_embedding_generates_without_creating_a_cache_hit",
        6,
        None,
    ),
    RequestPathExpectation(
        "rp_generation_failed",
        "LLM generation failure",
        "C",
        True,
        True,
        "error",
        "UNCERTAIN",
        "generation_failed",
        0,
        "not_retrieved",
        None,
        "test_generation_timeout_returns_controlled_502",
        6,
        "HTTP 502; log decision UNCERTAIN.",
    ),
    RequestPathExpectation(
        "rp_validator_error",
        "evaluate_candidate exception wrapped at boundary",
        "C",
        True,
        True,
        "generated",
        "UNCERTAIN",
        "no candidate had sufficient compatibility evidence",
        1,
        "evaluated",
        "fresh",
        "test_strategy_c_does_not_reuse_exact_entry_without_metadata",
        2,
        "Uses candidate_metadata_missing trace, not safety_validator_error row yet.",
    ),
)


def matrix_row_ids(layer: MatrixLayer) -> frozenset[str]:
    rows = PURE_EVALUATOR_MATRIX if layer == "pure_evaluator" else REQUEST_PATH_MATRIX
    return frozenset(row.row_id if layer == "pure_evaluator" else row.path_id for row in rows)
