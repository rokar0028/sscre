"""Workstream 3 step 2: pure ``evaluate_candidate`` contract tests."""

from __future__ import annotations

import pytest

from sscre.cache import CacheCandidate
from sscre.compatibility import evaluate_candidate, evaluate_candidate_boundary
from sscre.safety import validate_trace_reason
from tests.fixtures.workstream3_decision_matrix import PURE_EVALUATOR_MATRIX
from tests.fixtures.workstream3_evaluator_cases import (
    DEFAULT_THRESHOLD,
    _candidate,
    _meta,
    evaluator_case,
)


def _assert_reason(expected: str, actual: str) -> None:
    if expected == "constraint_mismatch:<key>":
        assert actual.startswith("constraint_mismatch:")
        validate_trace_reason(actual)
        return
    assert actual == expected
    validate_trace_reason(actual)


@pytest.mark.parametrize("row", PURE_EVALUATOR_MATRIX, ids=lambda row: row.row_id)
def test_pure_evaluator_matrix_row(row) -> None:
    query_metadata, candidate, threshold = evaluator_case(row.row_id)
    result = evaluate_candidate(
        query_metadata,
        candidate,
        similarity_threshold=threshold,
    )
    assert result.decision == row.decision
    _assert_reason(row.reason, result.reason)
    assert result.candidate_query_hash == candidate.query_hash


@pytest.mark.parametrize("similarity", [-1.0, 1.0])
def test_similarity_at_threshold_is_not_below_threshold(similarity: float) -> None:
    meta = _meta()
    result = evaluate_candidate(
        meta,
        _candidate(meta, similarity=similarity),
        similarity_threshold=similarity,
    )
    assert result.decision == "SAFE"


def test_similarity_just_below_threshold_is_unsafe() -> None:
    meta = _meta()
    result = evaluate_candidate(
        meta,
        _candidate(meta, similarity=0.949),
        similarity_threshold=0.95,
    )
    assert result.decision == "UNSAFE"
    assert result.reason == "similarity_below_threshold"


@pytest.mark.parametrize("threshold", [-1.1, 1.1])
def test_invalid_similarity_threshold_is_rejected(threshold: float) -> None:
    meta = _meta()
    with pytest.raises(ValueError, match="similarity_threshold"):
        evaluate_candidate(meta, _candidate(meta), similarity_threshold=threshold)


def test_similarity_check_precedes_known_incompatibility() -> None:
    query = _meta(constraints=(("language", "python"),))
    candidate = _candidate(
        _meta(constraints=(("language", "java"),)),
        similarity=0.5,
    )
    result = evaluate_candidate(query, candidate, similarity_threshold=DEFAULT_THRESHOLD)
    assert result.decision == "UNSAFE"
    assert result.reason == "similarity_below_threshold"


def test_dynamic_query_precedes_missing_candidate_metadata() -> None:
    result = evaluate_candidate(
        _meta(temporal_class="dynamic"),
        _candidate(None, similarity=0.99),
        similarity_threshold=DEFAULT_THRESHOLD,
    )
    assert result.reason == "dynamic_query_not_reusable"


def test_constraint_value_mismatch_precedes_entity_mismatch() -> None:
    query = _meta(
        entities=("binary search",),
        constraints=(("language", "python"),),
    )
    candidate = _candidate(
        _meta(
            entities=("unrelated topic",),
            constraints=(("language", "java"),),
        )
    )
    result = evaluate_candidate(query, candidate, similarity_threshold=DEFAULT_THRESHOLD)
    assert result.reason == "constraint_mismatch:language"


def test_extra_constraint_key_on_query_is_incomplete_not_mismatch() -> None:
    query = _meta(constraints=(("language", "python"), ("runtime", "cpython")))
    candidate = _candidate(_meta(constraints=(("language", "python"),)))
    result = evaluate_candidate(query, candidate, similarity_threshold=DEFAULT_THRESHOLD)
    assert result.decision == "UNCERTAIN"
    assert result.reason == "incomplete_constraint_evidence"


def test_extra_constraint_key_on_candidate_is_incomplete_not_mismatch() -> None:
    query = _meta(constraints=(("language", "python"),))
    candidate = _candidate(_meta(constraints=(("language", "python"), ("runtime", "cpython"))))
    result = evaluate_candidate(query, candidate, similarity_threshold=DEFAULT_THRESHOLD)
    assert result.decision == "UNCERTAIN"
    assert result.reason == "incomplete_constraint_evidence"


def test_entity_overlap_allows_compatible_safe() -> None:
    meta = _meta(entities=("binary search", "python"))
    candidate = _candidate(_meta(entities=("python", "binary search")))
    result = evaluate_candidate(meta, candidate, similarity_threshold=DEFAULT_THRESHOLD)
    assert result.decision == "SAFE"


def test_empty_entities_on_both_sides_can_still_be_safe() -> None:
    meta = _meta(entities=(), constraints=(("language", "python"),))
    candidate = _candidate(_meta(entities=(), constraints=(("language", "python"),)))
    result = evaluate_candidate(meta, candidate, similarity_threshold=DEFAULT_THRESHOLD)
    assert result.decision == "SAFE"


def test_all_unknown_scalar_fields_remain_uncertain_not_safe() -> None:
    meta = _meta(
        intent="unknown",
        domain="unknown",
        output_format="unknown",
        entities=(),
        constraints=(),
    )
    candidate = _candidate(
        _meta(
            intent="unknown",
            domain="unknown",
            output_format="unknown",
            entities=(),
            constraints=(),
        )
    )
    result = evaluate_candidate(meta, candidate, similarity_threshold=DEFAULT_THRESHOLD)
    assert result.decision == "UNCERTAIN"
    assert result.reason == "missing_intent_evidence"


def test_temporal_mismatch_does_not_require_ttl_metadata() -> None:
    """Pure evaluator has no TTL inputs; temporal_class alone drives this reason."""
    result = evaluate_candidate(
        _meta(temporal_class="semi_dynamic"),
        _candidate(_meta(temporal_class="stable")),
        similarity_threshold=DEFAULT_THRESHOLD,
    )
    assert result.decision == "UNCERTAIN"
    assert result.reason == "temporal_class_mismatch"


@pytest.mark.parametrize("row_id", [row.row_id for row in PURE_EVALUATOR_MATRIX if row.decision == "UNCERTAIN"])
def test_uncertain_matrix_rows_never_return_safe(row_id: str) -> None:
    query_metadata, candidate, threshold = evaluator_case(row_id)
    result = evaluate_candidate(
        query_metadata,
        candidate,
        similarity_threshold=threshold,
    )
    assert result.decision != "SAFE"


def test_evaluator_boundary_maps_trace_validation_failure_to_uncertain() -> None:
    invalid = CacheCandidate(
        query_hash="candidate-1",
        normalized_query="q",
        answer="a",
        similarity=2.0,
        embedding_model="test-embedding",
        embedding_dimension=2,
        metadata=_meta(),
    )
    result = evaluate_candidate_boundary(
        _meta(),
        invalid,
        similarity_threshold=DEFAULT_THRESHOLD,
    )
    assert result.decision == "UNCERTAIN"
    assert result.reason == "safety_validator_error"
    assert -1.0 <= result.similarity <= 1.0
