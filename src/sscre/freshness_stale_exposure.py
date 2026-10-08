"""Reviewed stale-exposure accounting (Workstream 6 Step 6)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sscre.baseline import CompatibilityCacheReport
from sscre.benchmark import BenchmarkRecord
from sscre.evaluation_statistics import (
    StatisticsConfig,
    _proportion_from_indicators,
    unavailable_interval,
)
from sscre.freshness_evaluation import FreshnessPolicySpec

STALE_EXPOSURE_ACCOUNTING_VERSION = "1.0"

REVIEWED_STALE_FAILURE_CATEGORIES = frozenset({"stale_answer", "temporal_mismatch"})

SERVED_STALE_NUMERATOR_FIELDS = frozenset({"safe_reuse_hit", "false_positive"})


def reviewed_stale_pair_ids(records: Sequence[BenchmarkRecord]) -> frozenset[str]:
    return frozenset(
        record.id
        for record in records
        if record.failure_category in REVIEWED_STALE_FAILURE_CATEGORIES
    )


def stale_exposure_indicators(
    samples: Sequence[Mapping[str, object]],
    stale_pair_ids: frozenset[str],
) -> list[int]:
    """1 when a directed request served reuse on a reviewed stale-labeled pair."""
    indicators: list[int] = []
    for sample in samples:
        exposed = 0
        if stale_pair_ids and sample.get("pair_id") in stale_pair_ids:
            if sample.get("cache_hit") == 1 and any(
                sample.get(field) == 1 for field in SERVED_STALE_NUMERATOR_FIELDS
            ):
                exposed = 1
        indicators.append(exposed)
    return indicators


def dynamic_reuse_served_indicators(
    samples: Sequence[Mapping[str, object]],
    *,
    allow_dynamic_entries: bool,
) -> list[int]:
    if not allow_dynamic_entries:
        return [0 for _ in samples]
    indicators: list[int] = []
    for sample in samples:
        temporal = sample.get("runtime_temporal_class")
        if temporal is None:
            temporal = sample.get("freshness_class")
        served = (
            temporal == "dynamic"
            and sample.get("cache_hit") == 1
            and sample.get("safe_reuse_hit") == 1
        )
        indicators.append(1 if served else 0)
    return indicators


def _directed_requests_on_labeled_pairs(
    samples: Sequence[Mapping[str, object]],
    stale_pair_ids: frozenset[str],
) -> int:
    if not stale_pair_ids:
        return 0
    return sum(
        1 for sample in samples if sample.get("pair_id") in stale_pair_ids
    )


def _answer_level_stale_exposure_status(
    records: Sequence[BenchmarkRecord],
) -> dict[str, object]:
    if not records:
        return {"status": "unavailable", "reason": "empty_workload"}
    if all(record.answer_availability == "none" for record in records):
        return {
            "status": "unavailable",
            "reason": "answer_availability_none",
        }
    return {"status": "available"}


def build_stale_exposure_accounting(
    records: Sequence[BenchmarkRecord],
    report: CompatibilityCacheReport,
    policy: FreshnessPolicySpec,
    settings: StatisticsConfig,
) -> dict[str, Any]:
    samples = report.request_samples
    stale_ids = reviewed_stale_pair_ids(records)
    stale_indicators = stale_exposure_indicators(samples, stale_ids)
    dynamic_served_indicators = dynamic_reuse_served_indicators(
        samples,
        allow_dynamic_entries=policy.allow_dynamic_entries,
    )

    directed_request_count = report.request_count
    candidate_evaluation_count = sum(report.cache_control_outcome_counts.values())
    labeled_request_count = _directed_requests_on_labeled_pairs(samples, stale_ids)

    served_stale_count = sum(stale_indicators)
    dynamic_served_count = sum(dynamic_served_indicators)
    expired_blocked = report.cache_control_outcome_counts.get("expired", 0)
    dynamic_blocked = report.cache_control_outcome_counts.get(
        "dynamic_entries_disabled",
        0,
    )
    missing_expiration = report.cache_control_outcome_counts.get(
        "missing_expiration",
        0,
    )
    invalid_expiration = report.cache_control_outcome_counts.get(
        "invalid_expiration",
        0,
    )

    stale_per_request_interval = _proportion_from_indicators(
        stale_indicators,
        settings,
    )
    labeled_indicators = [
        indicator
        for sample, indicator in zip(samples, stale_indicators, strict=True)
        if stale_ids and sample.get("pair_id") in stale_ids
    ]
    if labeled_indicators:
        labeled_stale_interval = _proportion_from_indicators(
            labeled_indicators,
            settings,
        )
    else:
        labeled_stale_interval = unavailable_interval(
            point=None,
            n=0,
            confidence_level=settings.confidence_level,
            reason="no_labeled_requests",
        )

    dynamic_served_interval = _proportion_from_indicators(
        dynamic_served_indicators,
        settings,
    )

    return {
        "definition_version": STALE_EXPOSURE_ACCOUNTING_VERSION,
        "measurement_environment": "synthetic_replay",
        "numerators": {
            "served_reviewed_stale_exposure_count": served_stale_count,
            "dynamic_reuse_served_count": dynamic_served_count,
        },
        "denominators": {
            "directed_request_count": directed_request_count,
            "reviewed_stale_labeled_request_count": labeled_request_count,
            "candidate_evaluation_count": candidate_evaluation_count,
        },
        "rates": {
            "served_reviewed_stale_exposure_per_directed_request": (
                served_stale_count / directed_request_count
                if directed_request_count
                else 0.0
            ),
            "served_reviewed_stale_exposure_per_labeled_request": (
                served_stale_count / labeled_request_count
                if labeled_request_count
                else None
            ),
            "dynamic_reuse_served_per_directed_request": (
                dynamic_served_count / directed_request_count
                if directed_request_count
                else 0.0
            ),
        },
        "intervals": {
            "served_reviewed_stale_exposure_per_directed_request": (
                stale_per_request_interval
            ),
            "served_reviewed_stale_exposure_per_labeled_request": (
                labeled_stale_interval
            ),
            "dynamic_reuse_served_per_directed_request": dynamic_served_interval,
        },
        "protection_counts": {
            "expired_candidate_blocked_count": expired_blocked,
            "dynamic_reuse_blocked_count": dynamic_blocked,
            "missing_expiration_count": missing_expiration,
            "invalid_expiration_count": invalid_expiration,
        },
        "answer_level_stale_exposure": _answer_level_stale_exposure_status(records),
        "policy_name": policy.name,
        "allow_dynamic_entries": policy.allow_dynamic_entries,
    }
