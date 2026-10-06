"""Versioned benchmark records and JSONL validation."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from sscre.evaluation_labels import (
    AdjudicationStatus,
    BenchmarkPreferenceLabel,
    reject_preference_as_correctness,
)
from sscre.benchmark_coverage import CoverageCategory
from sscre.query import MAX_QUERY_LENGTH, normalize_query
from sscre.safety import (
    MAX_METADATA_CONSTRAINTS,
    MAX_METADATA_ENTITIES,
    MAX_METADATA_ENTITY_LENGTH,
    MAX_METADATA_KEY_LENGTH,
    MAX_METADATA_VALUE_LENGTH,
)

BENCHMARK_SCHEMA_VERSION = "1.1"
SUPPORTED_BENCHMARK_SCHEMA_VERSIONS = frozenset({"1.0", "1.1"})
BenchmarkSchemaVersion = Literal["1.0", "1.1"]
Directionality = Literal["ordered", "symmetric"]
FreshnessClass = Literal["stable", "semi_dynamic", "dynamic"]
AnswerAvailability = Literal["none", "query_a", "query_b", "both"]
FailureCategory = Literal[
    "none",
    "constraint_mismatch",
    "entity_mismatch",
    "intent_mismatch",
    "format_mismatch",
    "domain_mismatch",
    "temporal_mismatch",
    "ambiguity",
    "stale_answer",
    "insufficient_evidence",
    "other",
]
_UNCERTAIN_FAILURE_CATEGORIES = frozenset(
    {"insufficient_evidence", "ambiguity", "other"}
)
_COMPATIBLE_FALSE_FAILURE_CATEGORIES = frozenset(
    {"stale_answer", "temporal_mismatch"}
)
_RECORD_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class BenchmarkMetadata(BaseModel):
    """Bounded reviewed metadata used for coverage and later evaluation."""

    intent: str | None = Field(default=None, max_length=64)
    domain: str | None = Field(default=None, max_length=64)
    entities: tuple[str, ...] = Field(default_factory=tuple)
    constraints: dict[str, str] = Field(default_factory=dict)
    temporal_class: str | None = Field(default=None, max_length=32)
    output_format: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_bounds(self) -> "BenchmarkMetadata":
        if len(self.entities) > MAX_METADATA_ENTITIES:
            raise ValueError(
                f"entities must contain at most {MAX_METADATA_ENTITIES} items"
            )
        if len(self.constraints) > MAX_METADATA_CONSTRAINTS:
            raise ValueError(
                "constraints must contain at most "
                f"{MAX_METADATA_CONSTRAINTS} items"
            )
        if len(set(self.entities)) != len(self.entities):
            raise ValueError("entities must not contain duplicates")
        for entity in self.entities:
            if not entity or len(entity) > MAX_METADATA_ENTITY_LENGTH:
                raise ValueError(
                    "entity values must be non-empty and within the length limit"
                )
        for key, value in self.constraints.items():
            if (
                not key
                or len(key) > MAX_METADATA_KEY_LENGTH
                or not value
                or len(value) > MAX_METADATA_VALUE_LENGTH
            ):
                raise ValueError("constraint keys and values exceed metadata limits")
        return self


class BenchmarkRecord(BaseModel):
    """One reviewed query pair in the benchmark."""

    schema_version: BenchmarkSchemaVersion = BENCHMARK_SCHEMA_VERSION
    id: str = Field(pattern=_RECORD_ID_PATTERN)
    query_a: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    query_b: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    directionality: Directionality = "ordered"
    reusable: bool
    expected_reuse: bool | None = None
    correctness_label: Literal["correct", "incorrect"] | None = None
    compatibility_label: Literal["compatible", "incompatible", "uncertain"]
    expected_compatibility: Literal[
        "compatible", "incompatible", "uncertain"
    ] | None = None
    reason: str | None = None
    failure_category: FailureCategory | None = None
    coverage_category: CoverageCategory | None = None
    freshness_class: FreshnessClass = "stable"
    metadata: BenchmarkMetadata = Field(default_factory=BenchmarkMetadata)
    answer_availability: AnswerAvailability = "none"
    preference_label: BenchmarkPreferenceLabel | None = None
    annotation_source: str | None = None
    adjudication_status: AdjudicationStatus | None = None
    review_status: Literal["final", "draft", "disputed"] | None = None
    annotator_count: int | None = Field(default=None, ge=1)
    source_group: str | None = Field(default=None, max_length=64)

    @field_validator("correctness_label")
    @classmethod
    def correctness_is_not_preference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return reject_preference_as_correctness(value)

    @model_validator(mode="after")
    def validate_record(self) -> "BenchmarkRecord":
        for field_name in ("query_a", "query_b"):
            value = getattr(self, field_name)
            normalize_query(value)

        if self.expected_reuse is None:
            self.expected_reuse = self.reusable
        elif self.expected_reuse != self.reusable:
            raise ValueError("expected_reuse must match reusable")

        if self.expected_compatibility is None:
            self.expected_compatibility = self.compatibility_label
        elif self.expected_compatibility != self.compatibility_label:
            raise ValueError(
                "expected_compatibility must match compatibility_label"
            )

        if not self.reusable and not self.reason:
            raise ValueError("reason is required when reusable is false")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("reason must not be blank")
        if self.annotation_source is not None and not self.annotation_source.strip():
            raise ValueError("annotation_source must not be blank")
        if self.review_status == "disputed" and self.adjudication_status != "disputed":
            raise ValueError(
                "disputed records require disputed adjudication status"
            )

        if self.preference_label is not None and self.answer_availability == "none":
            raise ValueError(
                "preference_label requires answer_availability other than none"
            )

        if self.schema_version == "1.1":
            _validate_schema_1_1_semantics(self)
            from sscre.benchmark_splits import validate_coverage_category_consistency

            validate_coverage_category_consistency(self)

        return self


def _validate_schema_1_1_semantics(record: BenchmarkRecord) -> None:
    if not record.coverage_category:
        raise ValueError("coverage_category is required when schema_version is 1.1")

    if record.correctness_label is not None and record.answer_availability == "none":
        raise ValueError(
            "correctness_label requires answer_availability when schema_version is 1.1"
        )

    category = record.failure_category
    if record.compatibility_label == "uncertain":
        if record.reusable:
            raise ValueError("uncertain compatibility requires reusable false")
        if category not in _UNCERTAIN_FAILURE_CATEGORIES:
            raise ValueError(
                "uncertain compatibility requires failure_category "
                "insufficient_evidence, ambiguity, or other"
            )
        return

    if record.reusable:
        if record.compatibility_label != "compatible":
            raise ValueError("reusable true requires compatible compatibility_label")
        if category not in (None, "none"):
            raise ValueError(
                "reusable compatible pairs must use failure_category none"
            )
        return

    if record.compatibility_label == "incompatible":
        if category in (None, "none"):
            raise ValueError(
                "incompatible pairs require an explicit failure_category"
            )
        if category in _UNCERTAIN_FAILURE_CATEGORIES:
            raise ValueError(
                "incompatible pairs cannot use uncertain failure categories"
            )
        return

    if record.compatibility_label == "compatible" and not record.reusable:
        if category not in _COMPATIBLE_FALSE_FAILURE_CATEGORIES:
            raise ValueError(
                "compatible but non-reusable pairs require failure_category "
                "stale_answer or temporal_mismatch"
            )


class BenchmarkValidationError(ValueError):
    """Raised when a benchmark JSONL file is invalid."""


def load_benchmark_jsonl(
    path: str | Path,
    *,
    require_final_review: bool = False,
) -> list[BenchmarkRecord]:
    """Load and validate every non-blank JSONL record from a benchmark file."""
    records: list[BenchmarkRecord] = []
    seen_ids: set[str] = set()
    benchmark_path = Path(path)

    try:
        lines = benchmark_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BenchmarkValidationError(
            f"could not read benchmark {benchmark_path}: {exc}"
        ) from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, TypeError) as exc:
            raise BenchmarkValidationError(
                f"{benchmark_path}:{line_number}: invalid benchmark record: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise BenchmarkValidationError(
                f"{benchmark_path}:{line_number}: benchmark record must be a JSON object"
            )

        schema_version = payload.get("schema_version", BENCHMARK_SCHEMA_VERSION)
        if schema_version not in SUPPORTED_BENCHMARK_SCHEMA_VERSIONS:
            raise BenchmarkValidationError(
                f"{benchmark_path}:{line_number}: unsupported schema_version: "
                f"{schema_version!r}"
            )

        try:
            record = BenchmarkRecord.model_validate(payload)
        except (ValueError, TypeError) as exc:
            raise BenchmarkValidationError(
                f"{benchmark_path}:{line_number}: invalid benchmark record: {exc}"
            ) from exc

        if require_final_review and record.review_status != "final":
            raise BenchmarkValidationError(
                f"{benchmark_path}:{line_number}: review_status must be final"
            )

        if record.id in seen_ids:
            raise BenchmarkValidationError(
                f"{benchmark_path}:{line_number}: duplicate record id: {record.id}"
            )
        seen_ids.add(record.id)
        records.append(record)

    return records
