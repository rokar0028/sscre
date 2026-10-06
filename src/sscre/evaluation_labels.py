"""Independent evaluation labels for compatibility, correctness, and preference.

See ``benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`` and
``docs/phase-2/SAFETY_EVALUATION_CONTRACT_v1.md``.
"""

from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from sscre.safety import SafetyDecision

EVALUATION_LABEL_CONTRACT_VERSION = "1.0.0"

CorrectnessLabel = Literal["correct", "incorrect", "uncertain"]
CompatibilityGroundLabel = Literal["compatible", "incompatible"]
PreferenceWinner = Literal["cached", "generated", "tie"]
BenchmarkPreferenceLabel = Literal["A", "B", "tie"]
AdjudicationStatus = Literal["final", "draft", "disputed"]


class _BenchmarkGroundTruth(Protocol):
    reusable: bool
    compatibility_label: str
    preference_label: BenchmarkPreferenceLabel | None
    annotation_source: str | None
    adjudication_status: AdjudicationStatus | None

_PREFERENCE_TOKENS = frozenset({"A", "B", "tie", "cached", "generated"})


def reject_preference_as_correctness(value: str) -> str:
    """Reject values that belong in the preference label field."""
    if value in _PREFERENCE_TOKENS:
        raise ValueError(
            "correctness label must not use preference values "
            f"({', '.join(sorted(_PREFERENCE_TOKENS))})"
        )
    return value


def normalized_correctness_label(
    label: CorrectnessLabel | None,
) -> CorrectnessLabel | None:
    """Missing correctness is unknown, not incorrect."""
    return label


def correctness_metrics_bucket(label: CorrectnessLabel | None) -> str:
    """Bucket name for report sections; absence is explicit."""
    if label is None:
        return "not_collected"
    return label


def expected_compatibility_decision(record: _BenchmarkGroundTruth) -> SafetyDecision:
    """Map reviewed benchmark ground truth to an expected safety decision."""
    if record.reusable and record.compatibility_label == "compatible":
        return "SAFE"
    if not record.reusable or record.compatibility_label == "incompatible":
        return "UNSAFE"
    return "UNCERTAIN"


class CompatibilityEvaluation(BaseModel):
    expected_decision: SafetyDecision
    observed_decision: SafetyDecision


class CorrectnessEvaluation(BaseModel):
    cached_answer: CorrectnessLabel | None = None
    generated_answer: CorrectnessLabel | None = None


class PreferenceEvaluation(BaseModel):
    winner: PreferenceWinner | None = None
    applicable: bool = False


class AnnotationProvenance(BaseModel):
    source: str | None = None
    adjudication_status: AdjudicationStatus | None = None


class EvaluationLabelRecord(BaseModel):
    """Canonical evaluation artifact label block."""

    contract_version: str = EVALUATION_LABEL_CONTRACT_VERSION
    compatibility: CompatibilityEvaluation
    correctness: CorrectnessEvaluation = Field(default_factory=CorrectnessEvaluation)
    preference: PreferenceEvaluation = Field(default_factory=PreferenceEvaluation)
    annotation: AnnotationProvenance | None = None

    def to_artifact_dict(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload.pop("contract_version", None)
        return payload


def build_evaluation_labels(
    *,
    record: _BenchmarkGroundTruth,
    observed_decision: SafetyDecision,
    cached_answer: CorrectnessLabel | None = None,
    generated_answer: CorrectnessLabel | None = None,
    preference: PreferenceEvaluation | None = None,
) -> EvaluationLabelRecord:
    """Build a label record with separate compatibility and correctness fields."""
    annotation = None
    if record.annotation_source or record.adjudication_status:
        annotation = AnnotationProvenance(
            source=record.annotation_source,
            adjudication_status=record.adjudication_status,
        )
    pref = preference or PreferenceEvaluation(
        winner=_benchmark_preference_winner(record.preference_label),
        applicable=record.preference_label is not None,
    )
    return EvaluationLabelRecord(
        compatibility=CompatibilityEvaluation(
            expected_decision=expected_compatibility_decision(record),
            observed_decision=observed_decision,
        ),
        correctness=CorrectnessEvaluation(
            cached_answer=cached_answer,
            generated_answer=generated_answer,
        ),
        preference=pref,
        annotation=annotation,
    )


def _benchmark_preference_winner(
    label: BenchmarkPreferenceLabel | None,
) -> PreferenceWinner | None:
    if label is None:
        return None
    if label == "tie":
        return "tie"
    return None


def build_label_sections(
    *,
    compatibility_label_counts: dict[str, int],
    correctness_label_counts: dict[str, int],
    preference_label_counts: dict[str, int],
    compatibility_agreement_counts: dict[str, int],
    decision_counts: dict[str, int],
) -> dict[str, dict[str, int]]:
    """Grouped metrics for reports; each label family stays isolated."""
    return {
        "compatibility": {
            **compatibility_label_counts,
            **compatibility_agreement_counts,
            **{
                f"observed_{key.lower()}": value
                for key, value in decision_counts.items()
            },
        },
        "correctness": dict(correctness_label_counts),
        "preference": preference_label_counts,
    }


class EvaluationLabelRecordValidator(BaseModel):
    """Validate artifact JSON shape for tooling."""

    compatibility: CompatibilityEvaluation
    correctness: CorrectnessEvaluation = Field(default_factory=CorrectnessEvaluation)
    preference: PreferenceEvaluation = Field(default_factory=PreferenceEvaluation)

    @field_validator("correctness", mode="after")
    @classmethod
    def correctness_fields_not_preference(
        cls, value: CorrectnessEvaluation
    ) -> CorrectnessEvaluation:
        for field_name in ("cached_answer", "generated_answer"):
            label = getattr(value, field_name)
            if isinstance(label, str):
                reject_preference_as_correctness(label)
        return value
