import pytest

from sscre.safety import (
    MAX_METADATA_CONSTRAINTS,
    MAX_METADATA_ENTITIES,
    CandidateTrace,
    QueryMetadata,
    SafetyResult,
    is_reusable_decision,
    resolve_candidate_traces,
)


def test_only_safe_is_reusable() -> None:
    assert is_reusable_decision("SAFE")
    assert not is_reusable_decision("UNSAFE")
    assert not is_reusable_decision("UNCERTAIN")


def test_query_metadata_round_trips_through_storage_shape() -> None:
    metadata = QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search",),
        constraints=(("language", "python"),),
        temporal_class="stable",
        output_format="code",
    )

    assert QueryMetadata.from_dict(metadata.to_dict()) == metadata


def test_query_metadata_defaults_unknown_values() -> None:
    metadata = QueryMetadata()

    assert metadata.intent == "unknown"
    assert metadata.domain == "unknown"
    assert metadata.output_format == "unknown"
    assert metadata.to_dict()["constraints"] == {}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("entities", tuple(f"entity-{index}" for index in range(MAX_METADATA_ENTITIES + 1)), "entities"),
        (
            "constraints",
            tuple((f"key-{index}", "value") for index in range(MAX_METADATA_CONSTRAINTS + 1)),
            "constraints",
        ),
    ],
)
def test_query_metadata_is_bounded(field: str, value: tuple, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        QueryMetadata(**{field: value})


def test_safe_result_requires_selected_candidate_and_similarity() -> None:
    with pytest.raises(ValueError, match="selected candidate"):
        SafetyResult(
            decision="SAFE",
            strategy="C",
            reason="compatible",
        )

    with pytest.raises(ValueError, match="similarity"):
        SafetyResult(
            decision="SAFE",
            strategy="C",
            reason="compatible",
            selected_candidate_query_hash="candidate-1",
        )


@pytest.mark.parametrize("decision", ["UNSAFE", "UNCERTAIN"])
def test_non_safe_result_cannot_select_candidate(decision: str) -> None:
    with pytest.raises(ValueError, match="non-SAFE"):
        SafetyResult(
            decision=decision,  # type: ignore[arg-type]
            strategy="C",
            reason="insufficient evidence",
            selected_candidate_query_hash="candidate-1",
        )


@pytest.mark.parametrize("decision", ["UNSAFE", "UNCERTAIN"])
def test_non_safe_result_cannot_include_similarity(decision: str) -> None:
    with pytest.raises(ValueError, match="cannot include a similarity"):
        SafetyResult(
            decision=decision,  # type: ignore[arg-type]
            strategy="C",
            reason="insufficient evidence",
            similarity=0.9,
        )


def test_safety_result_rejects_invalid_decision() -> None:
    with pytest.raises(ValueError, match="decision must be SAFE, UNSAFE, or UNCERTAIN"):
        SafetyResult(
            decision="EXACT_HIT",  # type: ignore[arg-type]
            strategy="C",
            reason="compatible",
        )


def test_first_safe_candidate_wins_in_retrieval_order() -> None:
    traces = (
        CandidateTrace(
            "candidate-1",
            0.99,
            "UNCERTAIN",
            "incomplete_constraint_evidence",
        ),
        CandidateTrace("candidate-2", 0.96, "SAFE", "compatible_metadata"),
        CandidateTrace("candidate-3", 0.94, "SAFE", "compatible_metadata"),
    )

    result = resolve_candidate_traces(traces)

    assert result.decision == "SAFE"
    assert result.selected_candidate_query_hash == "candidate-2"
    assert result.similarity == 0.96
    assert result.candidate_traces == traces


def test_uncertain_takes_precedence_over_all_unsafe_candidates() -> None:
    result = resolve_candidate_traces(
        (
            CandidateTrace("candidate-1", 0.95, "UNSAFE", "intent_mismatch"),
            CandidateTrace(
                "candidate-2",
                0.91,
                "UNCERTAIN",
                "missing_output_format_evidence",
            ),
        )
    )

    assert result.decision == "UNCERTAIN"
    assert result.selected_candidate_query_hash is None
    assert result.reason == "no candidate had sufficient compatibility evidence"


def test_all_unsafe_candidates_are_rejected() -> None:
    result = resolve_candidate_traces(
        (CandidateTrace("candidate-1", 0.95, "UNSAFE", "entity_mismatch"),)
    )

    assert result.decision == "UNSAFE"
    assert result.reason == "all candidates were incompatible"


def test_safety_result_trace_serialization_excludes_selection_on_miss() -> None:
    traces = (
        CandidateTrace("candidate-1", 0.95, "UNSAFE", "entity_mismatch"),
    )
    result = resolve_candidate_traces(traces)
    payload = result.to_log_dict()

    assert payload["decision"] == "UNSAFE"
    assert payload["selected_candidate_query_hash"] is None
    assert len(payload["candidate_traces"]) == 1
    assert payload["candidate_traces"][0]["reason"] == "entity_mismatch"


def test_empty_candidates_fail_closed_without_selection() -> None:
    result = resolve_candidate_traces(())

    assert result.decision == "UNSAFE"
    assert result.reason == "no candidates were retrieved"
    assert result.candidate_traces == ()
