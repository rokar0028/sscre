"""Annotation guide version and review-policy validation."""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from sscre.benchmark import BenchmarkRecord

ANNOTATION_GUIDE_VERSION = "1.0.0"

_HIGH_IMPACT_COVERAGE_CATEGORIES = frozenset(
    {
        "ambiguity",
        "insufficient_evidence",
        "stale_answer",
    }
)


def validate_review_policy(
    records: list[BenchmarkRecord],  # noqa: F821
    *,
    split: Literal["development", "held-out", "full"] = "full",
) -> None:
    """Fail closed when review metadata violates the annotation guide."""
    from sscre.benchmark import BenchmarkValidationError

    for record in records:
        if record.review_status == "final":
            if not record.annotation_source:
                raise BenchmarkValidationError(
                    f"{record.id}: final records require annotation_source"
                )
        if split == "held-out" and record.review_status != "final":
            raise BenchmarkValidationError(
                f"{record.id}: held-out split rejects review_status "
                f"{record.review_status!r}"
            )
        if record.review_status == "disputed" and record.adjudication_status != "disputed":
            raise BenchmarkValidationError(
                f"{record.id}: disputed records require disputed adjudication_status"
            )
        if (
            record.review_status == "final"
            and record.coverage_category in _HIGH_IMPACT_COVERAGE_CATEGORIES
            and (record.annotator_count or 0) < 2
        ):
            raise BenchmarkValidationError(
                f"{record.id}: high-impact coverage categories require "
                "annotator_count >= 2 before final"
            )
