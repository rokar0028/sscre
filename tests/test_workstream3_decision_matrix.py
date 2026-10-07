"""Guardrails for the frozen Workstream 3 decision matrix."""

from sscre.safety import is_documented_trace_reason, validate_trace_reason

from tests.fixtures.workstream3_decision_matrix import (
    CONTRACT_VERSIONS,
    PURE_EVALUATOR_MATRIX,
    REQUEST_PATH_MATRIX,
    matrix_row_ids,
)


def test_pure_evaluator_matrix_has_unique_row_ids() -> None:
    assert len(matrix_row_ids("pure_evaluator")) == len(PURE_EVALUATOR_MATRIX)


def test_request_path_matrix_has_unique_path_ids() -> None:
    assert len(matrix_row_ids("request_path")) == len(REQUEST_PATH_MATRIX)


def test_pure_evaluator_reasons_use_frozen_taxonomy_or_documented_prefix() -> None:
    for row in PURE_EVALUATOR_MATRIX:
        reason = row.reason
        if reason == "constraint_mismatch:<key>":
            assert is_documented_trace_reason("constraint_mismatch:language")
            continue
        assert is_documented_trace_reason(reason), row.row_id
        assert validate_trace_reason(reason) == reason


def test_contract_versions_are_documented() -> None:
    assert CONTRACT_VERSIONS["safety_evaluation"] == "1.0.0"
    assert CONTRACT_VERSIONS["candidate_trace"] == "1.0.0"
    assert CONTRACT_VERSIONS["serialization_boundary"] == "1.0.0"


def test_request_path_contract_paths_use_strategy_c_or_error() -> None:
    for row in REQUEST_PATH_MATRIX:
        if row.contract_path and row.expected_source != "error":
            assert row.strategy == "C", row.path_id


def test_filtered_paths_do_not_require_compatibility_traces() -> None:
    for row in REQUEST_PATH_MATRIX:
        if row.candidate_disposition == "filtered_before_evaluation":
            assert row.min_trace_count == 0, row.path_id
