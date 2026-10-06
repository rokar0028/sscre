import json

import pytest

from sscre.serialization import (
    BOUNDARY_SERIALIZATION_VERSION,
    build_cache_decision_log,
    boundary_candidate_traces,
    dumps_cache_decision_log,
    redact_operational_evaluation_report,
    serialize_safety_result_for_boundary,
)
from sscre.safety import CandidateTrace, SafetyResult, resolve_candidate_traces


def test_boundary_traces_use_null_when_empty() -> None:
    assert boundary_candidate_traces(()) is None


def test_cache_decision_log_includes_schema_version() -> None:
    payload = build_cache_decision_log(
        {
            "event": "cache_decision",
            "decision": "UNCERTAIN",
            "candidate_traces": None,
        }
    )
    assert payload["schema_version"] == BOUNDARY_SERIALIZATION_VERSION
    assert payload["candidate_traces"] is None


@pytest.mark.parametrize("field", ["answer", "authorization", "api_key"])
def test_cache_decision_log_rejects_sensitive_fields(field: str) -> None:
    with pytest.raises(ValueError, match="must not include"):
        build_cache_decision_log(
            {
                "event": "cache_decision",
                field: "secret body",
                "candidate_traces": None,
            }
        )


def test_safety_result_boundary_serialization() -> None:
    result = resolve_candidate_traces(
        (CandidateTrace("hash-1", 0.9, "UNSAFE", "entity_mismatch"),)
    )
    payload = serialize_safety_result_for_boundary(result)
    assert payload["decision"] == "UNSAFE"
    assert payload["trace_contract_version"]
    encoded = json.dumps(payload, sort_keys=True)
    again = json.dumps(serialize_safety_result_for_boundary(result), sort_keys=True)
    assert encoded == again
    assert list(json.loads(encoded)) == sorted(json.loads(encoded))


def test_cache_decision_log_rejects_unknown_decision() -> None:
    with pytest.raises(ValueError, match="decision must be SAFE"):
        build_cache_decision_log(
            {
                "event": "cache_decision",
                "decision": "GENERATION_FAILED",
                "candidate_traces": None,
            }
        )


def test_boundary_rejects_oversized_trace_payload() -> None:
    traces = [
        {"candidate_query_hash": "x" * 100_000, "decision": "UNSAFE"}
        for _ in range(20)
    ]
    with pytest.raises(ValueError, match="boundary size limit"):
        build_cache_decision_log(
            {"event": "cache_decision", "candidate_traces": traces}
        )


def test_trace_objects_reject_answer_field() -> None:
    with pytest.raises(ValueError, match="must not include"):
        build_cache_decision_log(
            {
                "event": "cache_decision",
                "candidate_traces": [{"answer": "secret body", "decision": "SAFE"}],
            }
        )


def test_dumps_cache_decision_log_is_sorted_json() -> None:
    raw = dumps_cache_decision_log(
        {"event": "cache_decision", "decision": "SAFE", "candidate_traces": None}
    )
    parsed = json.loads(raw)
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_redact_operational_evaluation_report_removes_query_text() -> None:
    payload = redact_operational_evaluation_report(
        {
            "failure_examples": [
                {
                    "id": "pair-0001",
                    "direction": "b_to_a",
                    "query_a": "secret a",
                    "query_b": "secret b",
                    "predicted_decision": "SAFE",
                }
            ],
            "failure_gallery": {
                "strategy_c_failures": [
                    {"id": "pair-0002", "query_a": "x", "query_b": "y"}
                ]
            },
        }
    )
    assert "query_a" not in json.dumps(payload)
    assert payload["failure_examples"][0]["id"] == "pair-0001"
