"""Versioned benchmark records and JSONL validation."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from sscre.query import MAX_QUERY_LENGTH, normalize_query

BENCHMARK_SCHEMA_VERSION = "1.0"
_RECORD_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class BenchmarkRecord(BaseModel):
    """One reviewed query pair in the benchmark."""

    schema_version: Literal["1.0"] = BENCHMARK_SCHEMA_VERSION
    id: str = Field(pattern=_RECORD_ID_PATTERN)
    query_a: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    query_b: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    reusable: bool
    correctness_label: Literal["correct", "incorrect"]
    compatibility_label: Literal["compatible", "incompatible"]
    reason: str | None = None

    @model_validator(mode="after")
    def validate_record(self) -> "BenchmarkRecord":
        for field_name in ("query_a", "query_b"):
            value = getattr(self, field_name)
            normalize_query(value)

        if not self.reusable and not self.reason:
            raise ValueError("reason is required when reusable is false")
        if self.reason is not None and not self.reason.strip():
            raise ValueError("reason must not be blank")
        return self


class BenchmarkValidationError(ValueError):
    """Raised when a benchmark JSONL file is invalid."""


def load_benchmark_jsonl(path: str | Path) -> list[BenchmarkRecord]:
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
            record = BenchmarkRecord.model_validate(payload)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise BenchmarkValidationError(
                f"{benchmark_path}:{line_number}: invalid benchmark record: {exc}"
            ) from exc

        if record.id in seen_ids:
            raise BenchmarkValidationError(
                f"{benchmark_path}:{line_number}: duplicate record id: {record.id}"
            )
        seen_ids.add(record.id)
        records.append(record)

    return records
