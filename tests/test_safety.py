import pytest

from sscre.safety import (
    MAX_METADATA_CONSTRAINTS,
    MAX_METADATA_ENTITIES,
    CandidateTrace,
    QueryMetadata,
    SafetyResult,
    resolve_candidate_traces,
)


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


def test_non_safe_result_cannot_select_candidate() -> None:
    with pytest.raises(ValueError, match="non-SAFE"):
        SafetyResult(
            decision="UNCERTAIN",
            strategy="C",
            reason="insufficient evidence",
            selected_candidate_query_hash="candidate-1",
        )


def test_first_safe_candidate_wins_in_retrieval_order() -> None:
    traces = (
        CandidateTrace("candidate-1", 0.99, "UNCERTAIN", "missing constraint"),
        CandidateTrace("candidate-2", 0.96, "SAFE", "constraints match"),
        CandidateTrace("candidate-3", 0.94, "SAFE", "also compatible"),
    )

    result = resolve_candidate_traces(traces)

    assert result.decision == "SAFE"
    assert result.selected_candidate_query_hash == "candidate-2"
    assert result.similarity == 0.96
    assert result.candidate_traces == traces


def test_uncertain_takes_precedence_over_all_unsafe_candidates() -> None:
    result = resolve_candidate_traces(
        (
            CandidateTrace("candidate-1", 0.95, "UNSAFE", "language mismatch"),
            CandidateTrace("candidate-2", 0.91, "UNCERTAIN", "unknown format"),
        )
    )

    assert result.decision == "UNCERTAIN"
    assert result.selected_candidate_query_hash is None
    assert result.reason == "no candidate had sufficient compatibility evidence"


def test_all_unsafe_candidates_are_rejected() -> None:
    result = resolve_candidate_traces(
        (CandidateTrace("candidate-1", 0.95, "UNSAFE", "entity mismatch"),)
    )

    assert result.decision == "UNSAFE"
    assert result.reason == "all candidates were incompatible"


def test_empty_candidates_fail_closed_without_selection() -> None:
    result = resolve_candidate_traces(())

    assert result.decision == "UNSAFE"
    assert result.reason == "no candidates were retrieved"
    assert result.candidate_traces == ()
