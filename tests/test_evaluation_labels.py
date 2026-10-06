import pytest
from pydantic import ValidationError

from sscre.benchmark import BenchmarkRecord, BENCHMARK_SCHEMA_VERSION
from sscre.evaluation_labels import (
    EvaluationLabelRecordValidator,
    build_evaluation_labels,
    correctness_metrics_bucket,
    expected_compatibility_decision,
    normalized_correctness_label,
    reject_preference_as_correctness,
)


def _record(**overrides: object) -> BenchmarkRecord:
    payload = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "id": "pair-test",
        "query_a": "query a",
        "query_b": "query b",
        "reusable": True,
        "correctness_label": "correct",
        "compatibility_label": "compatible",
        "reason": None,
    }
    payload.update(overrides)
    return BenchmarkRecord.model_validate(payload)


def test_missing_correctness_does_not_imply_incorrect() -> None:
    assert normalized_correctness_label(None) is None
    assert correctness_metrics_bucket(None) == "not_collected"
    assert correctness_metrics_bucket("correct") == "correct"


def test_reject_preference_tokens_in_correctness_field() -> None:
    with pytest.raises(ValueError, match="preference"):
        reject_preference_as_correctness("A")

    with pytest.raises(ValidationError):
        BenchmarkRecord.model_validate(
            {
                "schema_version": BENCHMARK_SCHEMA_VERSION,
                "id": "pair-bad",
                "query_a": "a",
                "query_b": "b",
                "reusable": False,
                "correctness_label": "tie",
                "compatibility_label": "incompatible",
                "reason": "format differs",
            }
        )


def test_expected_compatibility_decision_from_benchmark() -> None:
    assert expected_compatibility_decision(_record()) == "SAFE"
    assert (
        expected_compatibility_decision(
            _record(reusable=False, compatibility_label="incompatible", reason="x")
        )
        == "UNSAFE"
    )


def test_evaluation_artifact_keeps_labels_separate() -> None:
    artifact = build_evaluation_labels(
        record=_record(),
        observed_decision="UNSAFE",
    )

    payload = artifact.to_artifact_dict()
    assert payload["compatibility"]["expected_decision"] == "SAFE"
    assert payload["compatibility"]["observed_decision"] == "UNSAFE"
    assert payload["correctness"]["cached_answer"] is None
    assert payload["correctness"]["generated_answer"] is None
    assert payload["preference"]["applicable"] is False

    EvaluationLabelRecordValidator.model_validate(payload)
