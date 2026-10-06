import json

import pytest

from sscre.serialization import (
    BOUNDARY_SERIALIZATION_VERSION,
    build_cache_decision_log,
    boundary_candidate_traces,
    dumps_cache_decision_log,
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


def test_cache_decision_log_rejects_sensitive_fields() -> None:
    with pytest.raises(ValueError, match="must not include"):
        build_cache_decision_log(
            {
                "event": "cache_decision",
                "answer": "secret body",
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
