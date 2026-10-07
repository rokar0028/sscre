import json

import pytest

from sscre.safety import (
    MAX_CANDIDATE_TRACES,
    CandidateTrace,
    QueryMetadata,
    cap_candidate_traces,
    is_documented_trace_reason,
    serialize_candidate_traces,
    validate_trace_reason,
)


def test_documented_reasons_include_compatibility_outcomes() -> None:
    assert is_documented_trace_reason("compatible_metadata")
    assert is_documented_trace_reason("constraint_mismatch:language")
    assert is_documented_trace_reason("missing_domain_evidence")
    assert is_documented_trace_reason("cache_control_expired")
    assert not is_documented_trace_reason("language mismatch")


def test_candidate_trace_rejects_invalid_decision() -> None:
    with pytest.raises(ValueError, match="decision must be SAFE, UNSAFE, or UNCERTAIN"):
        CandidateTrace(
            "hash-1",
            0.9,
            "EXACT_HIT",  # type: ignore[arg-type]
            "entity_mismatch",
        )


def test_invalid_trace_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported trace reason"):
        CandidateTrace("hash-1", 0.9, "UNSAFE", "not a taxonomy reason")


def test_serialize_traces_is_stable_and_capped() -> None:
    metadata = QueryMetadata(intent="code").to_dict()
    traces = tuple(
        CandidateTrace(
            f"candidate-{index}",
            1.0 - index * 0.01,
            "UNSAFE",
            "similarity_below_threshold",
            candidate_order=index + 1,
            query_metadata=metadata,
        )
        for index in range(MAX_CANDIDATE_TRACES + 5)
    )

    serialized = serialize_candidate_traces(traces)
    assert len(serialized) == MAX_CANDIDATE_TRACES
    assert list(serialized[0]) == sorted(serialized[0])
    assert "answer" not in json.dumps(serialized)
    assert serialized[0]["candidate_order"] == 1


def test_cap_candidate_traces_preserves_order() -> None:
    traces = (
        CandidateTrace("a", 0.9, "UNSAFE", "entity_mismatch", candidate_order=1),
        CandidateTrace("b", 0.8, "UNSAFE", "entity_mismatch", candidate_order=2),
    )

    assert cap_candidate_traces(traces, limit=1)[0].candidate_query_hash == "a"


def test_validate_trace_reason_normalizes_whitespace() -> None:
    assert validate_trace_reason("  compatible_metadata  ") == "compatible_metadata"


def test_trace_metadata_rejects_oversized_raw_payload() -> None:
    with pytest.raises(ValueError, match="trace metadata exceeds"):
        CandidateTrace(
            "hash-1",
            0.5,
            "UNSAFE",
            "entity_mismatch",
            query_metadata={"note": "x" * 9000},
        )


def test_invalid_similarity_is_rejected() -> None:
    with pytest.raises(ValueError, match="similarity"):
        CandidateTrace("hash-1", 1.5, "UNSAFE", "entity_mismatch")


def test_negative_candidate_order_is_rejected() -> None:
    with pytest.raises(ValueError, match="candidate_order"):
        CandidateTrace(
            "hash-1",
            0.5,
            "UNSAFE",
            "entity_mismatch",
            candidate_order=-1,
        )
