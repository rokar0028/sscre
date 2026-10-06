"""Benchmark category coverage targets and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from sscre.benchmark import BenchmarkRecord

CoverageCategory = Literal[
    "exact_duplicate",
    "whitespace_variant",
    "paraphrase",
    "low_overlap_compatible",
    "high_similarity_incompatible",
    "intent_change",
    "constraint_change",
    "entity_change",
    "format_change",
    "temporal_freshness",
    "domain_change",
    "ambiguity",
    "stale_answer",
    "insufficient_evidence",
]

REQUIRED_COVERAGE_CATEGORIES: tuple[CoverageCategory, ...] = (
    "exact_duplicate",
    "whitespace_variant",
    "paraphrase",
    "low_overlap_compatible",
    "high_similarity_incompatible",
    "intent_change",
    "constraint_change",
    "entity_change",
    "format_change",
    "temporal_freshness",
    "domain_change",
    "ambiguity",
    "stale_answer",
    "insufficient_evidence",
)

CATEGORY_INCLUSION_RULES: dict[CoverageCategory, str] = {
    "exact_duplicate": "Query texts match after normalization.",
    "whitespace_variant": "Same intent with whitespace or line-break differences only.",
    "paraphrase": "Same intent and constraints with lexical rewording.",
    "low_overlap_compatible": "Low lexical overlap but reviewed compatible reuse.",
    "high_similarity_incompatible": "High similarity with a reviewed incompatibility.",
    "intent_change": "The user task or goal changed.",
    "constraint_change": "Language, length, numeric, or other explicit constraint changed.",
    "entity_change": "Subject, product, API, location, or version entity changed.",
    "format_change": "Requested response structure or output format changed.",
    "temporal_freshness": "Time-sensitive wording or freshness expectation changed.",
    "domain_change": "Topic domain changed in a way that affects reuse.",
    "ambiguity": "Underspecified or ambiguous query pair.",
    "stale_answer": "Previously acceptable answer would be stale for the new query.",
    "insufficient_evidence": "Reviewed uncertain; reuse cannot be established safely.",
}

# Minimum counts for the checked-in 24-pair working baseline.
WORKING_BASELINE_CATEGORY_MINIMUMS: dict[CoverageCategory, int] = {
    "exact_duplicate": 1,
    "whitespace_variant": 1,
    "paraphrase": 1,
    "low_overlap_compatible": 1,
    "high_similarity_incompatible": 1,
    "intent_change": 1,
    "constraint_change": 1,
    "entity_change": 1,
    "format_change": 1,
    "temporal_freshness": 1,
    "domain_change": 1,
    "ambiguity": 1,
    "stale_answer": 1,
    "insufficient_evidence": 1,
}

# Targets for the Phase 2 reviewed benchmark (500+ pairs).
PHASE2_CATEGORY_MINIMUMS: dict[CoverageCategory, int] = {
    category: 1 for category in REQUIRED_COVERAGE_CATEGORIES
}

WORKING_BASELINE_MIN_POSITIVE_FRACTION = 0.25
WORKING_BASELINE_MIN_NEGATIVE_FRACTION = 0.25
WORKING_BASELINE_MAX_PARAPHRASE_FRACTION = 0.45

PHASE2_MIN_POSITIVE_FRACTION = 0.20
PHASE2_MIN_NEGATIVE_FRACTION = 0.20
PHASE2_MAX_PARAPHRASE_FRACTION = 0.35


@dataclass(frozen=True)
class CoveragePolicy:
    """Minimum category counts and balance limits for a benchmark artifact."""

    category_minimums: dict[CoverageCategory, int]
    min_positive_fraction: float
    min_negative_fraction: float
    max_paraphrase_fraction: float
    min_freshness_class_counts: dict[str, int] | None = None
    min_record_count: int | None = None


WORKING_BASELINE_COVERAGE = CoveragePolicy(
    category_minimums=WORKING_BASELINE_CATEGORY_MINIMUMS,
    min_positive_fraction=WORKING_BASELINE_MIN_POSITIVE_FRACTION,
    min_negative_fraction=WORKING_BASELINE_MIN_NEGATIVE_FRACTION,
    max_paraphrase_fraction=WORKING_BASELINE_MAX_PARAPHRASE_FRACTION,
    min_freshness_class_counts={
        "stable": 1,
        "semi_dynamic": 1,
        "dynamic": 1,
    },
)

PHASE2_REVIEWED_COVERAGE = CoveragePolicy(
    category_minimums=PHASE2_CATEGORY_MINIMUMS,
    min_positive_fraction=PHASE2_MIN_POSITIVE_FRACTION,
    min_negative_fraction=PHASE2_MIN_NEGATIVE_FRACTION,
    max_paraphrase_fraction=PHASE2_MAX_PARAPHRASE_FRACTION,
    min_freshness_class_counts={
        "stable": 1,
        "semi_dynamic": 1,
        "dynamic": 1,
    },
    min_record_count=500,
)


def coverage_counts(records: list[BenchmarkRecord]) -> dict[str, int]:  # noqa: F821
    """Count records per reviewed coverage category."""
    counts: dict[str, int] = {category: 0 for category in REQUIRED_COVERAGE_CATEGORIES}
    for record in records:
        if record.coverage_category is None:
            continue
        key = record.coverage_category
        counts[key] = counts.get(key, 0) + 1
    return counts


def freshness_class_counts(records: list[BenchmarkRecord]) -> dict[str, int]:  # noqa: F821
    counts: dict[str, int] = {}
    for record in records:
        counts[record.freshness_class] = counts.get(record.freshness_class, 0) + 1
    return counts


def build_coverage_report(
    records: list[BenchmarkRecord],  # noqa: F821
    *,
    policy: CoveragePolicy,
) -> dict[str, object]:
    """Summarize category and balance metrics for an artifact."""
    total = len(records)
    positive = sum(1 for record in records if record.reusable)
    negative = total - positive
    categories = coverage_counts(records)
    paraphrase_count = categories.get("paraphrase", 0)
    return {
        "record_count": total,
        "positive_count": positive,
        "negative_count": negative,
        "positive_fraction": positive / total if total else 0.0,
        "negative_fraction": negative / total if total else 0.0,
        "paraphrase_fraction": paraphrase_count / total if total else 0.0,
        "coverage_category_counts": categories,
        "freshness_class_counts": freshness_class_counts(records),
        "policy": {
            "category_minimums": dict(policy.category_minimums),
            "min_positive_fraction": policy.min_positive_fraction,
            "min_negative_fraction": policy.min_negative_fraction,
            "max_paraphrase_fraction": policy.max_paraphrase_fraction,
            "min_freshness_class_counts": policy.min_freshness_class_counts,
        },
    }


def validate_coverage(
    records: list[BenchmarkRecord],  # noqa: F821
    *,
    policy: CoveragePolicy = WORKING_BASELINE_COVERAGE,
) -> None:
    """Fail closed when category or balance targets are not met."""
    from sscre.benchmark import BenchmarkValidationError

    if not records:
        raise BenchmarkValidationError("benchmark must contain at least one record")

    if policy.min_record_count is not None and len(records) < policy.min_record_count:
        raise BenchmarkValidationError(
            f"benchmark requires at least {policy.min_record_count} records; "
            f"observed {len(records)}"
        )

    report = build_coverage_report(records, policy=policy)
    total = report["record_count"]
    assert isinstance(total, int)

    for category, minimum in policy.category_minimums.items():
        if minimum <= 0:
            continue
        observed = report["coverage_category_counts"].get(category, 0)
        if observed < minimum:
            raise BenchmarkValidationError(
                f"coverage category {category!r} requires at least {minimum} "
                f"records; observed {observed}"
            )

    positive_fraction = report["positive_fraction"]
    negative_fraction = report["negative_fraction"]
    assert isinstance(positive_fraction, float)
    assert isinstance(negative_fraction, float)
    if positive_fraction < policy.min_positive_fraction:
        raise BenchmarkValidationError(
            "positive fraction "
            f"{positive_fraction:.3f} is below {policy.min_positive_fraction}"
        )
    if negative_fraction < policy.min_negative_fraction:
        raise BenchmarkValidationError(
            "negative fraction "
            f"{negative_fraction:.3f} is below {policy.min_negative_fraction}"
        )

    paraphrase_fraction = report["paraphrase_fraction"]
    assert isinstance(paraphrase_fraction, float)
    if paraphrase_fraction > policy.max_paraphrase_fraction:
        raise BenchmarkValidationError(
            "paraphrase fraction "
            f"{paraphrase_fraction:.3f} exceeds {policy.max_paraphrase_fraction}"
        )

    if policy.min_freshness_class_counts:
        freshness = report["freshness_class_counts"]
        assert isinstance(freshness, dict)
        for freshness_class, minimum in policy.min_freshness_class_counts.items():
            if freshness.get(freshness_class, 0) < minimum:
                raise BenchmarkValidationError(
                    f"freshness class {freshness_class!r} requires at least "
                    f"{minimum}; observed {freshness.get(freshness_class, 0)}"
                )
