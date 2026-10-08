"""Freshness metric summaries and stratified sections (Workstream 6 Step 5)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sscre.baseline import CompatibilityCacheReport
from sscre.benchmark import BenchmarkRecord
from sscre.evaluation_statistics import (
    EVALUATION_STATISTICS_SCHEMA_VERSION,
    BootstrapResampler,
    StatisticsConfig,
    _proportion_from_indicators,
    proportion_interval,
    statistics_config_from_mapping,
    summarize_request_sample_statistics,
    unavailable_interval,
)
from sscre.freshness_evaluation import (
    CACHE_CONTROL_OUTCOME_FIELDS,
    FreshnessExperimentConfig,
    FreshnessPolicySpec,
)
from sscre.freshness_stale_exposure import (
    build_stale_exposure_accounting,
    dynamic_reuse_served_indicators,
    reviewed_stale_pair_ids,
    stale_exposure_indicators,
)
from sscre.freshness_storage import build_storage_sections_for_policies


def candidate_evaluation_count(report: CompatibilityCacheReport) -> int:
    return sum(report.cache_control_outcome_counts.values())


def compatibility_report_to_policy_metrics(
    records: list[BenchmarkRecord],
    report: CompatibilityCacheReport,
    *,
    policy: FreshnessPolicySpec,
    storage_pairing: Mapping[str, object] | None = None,
) -> dict[str, object]:
    request_count = report.request_count
    samples = report.request_samples
    stale_pair_ids = reviewed_stale_pair_ids(records)
    stale_exposure = sum(stale_exposure_indicators(samples, stale_pair_ids))
    dynamic_served = sum(
        dynamic_reuse_served_indicators(
            samples,
            allow_dynamic_entries=policy.allow_dynamic_entries,
        )
    )
    expired_blocked = report.cache_control_outcome_counts.get("expired", 0)
    dynamic_disabled = report.cache_control_outcome_counts.get(
        "dynamic_entries_disabled",
        0,
    )
    candidate_count = candidate_evaluation_count(report)
    decision_counts = dict(report.decision_counts)
    request_decisions = sum(decision_counts.values()) or request_count
    safe_rate = (
        decision_counts.get("SAFE", 0) / request_decisions if request_decisions else 0.0
    )
    unsafe_rate = (
        decision_counts.get("UNSAFE", 0) / request_decisions
        if request_decisions
        else 0.0
    )
    uncertain_rate = (
        decision_counts.get("UNCERTAIN", 0) / request_decisions
        if request_decisions
        else 0.0
    )
    reviewed_stale_violations = stale_exposure
    return {
        "request_count": request_count,
        "candidate_count": candidate_count,
        "cache_hit_rate": report.hit_rate,
        "safe_reuse_coverage": report.safe_reuse_coverage,
        "served_reuse_count": report.cache_hits,
        "generated_request_count": report.generated_requests,
        "stale_exposure_count": stale_exposure,
        "stale_exposure_rate": (
            stale_exposure / request_count if request_count else 0.0
        ),
        "freshness_violation_count": stale_exposure,
        "freshness_violation_rate": (
            stale_exposure / request_count if request_count else 0.0
        ),
        "reviewed_stale_answer_violation_count": reviewed_stale_violations,
        "reviewed_stale_answer_violation_rate": (
            reviewed_stale_violations / request_count if request_count else 0.0
        ),
        "dynamic_reuse_served_count": dynamic_served,
        "dynamic_reuse_served_rate": (
            dynamic_served / request_count if request_count else 0.0
        ),
        "expired_candidate_blocked_count": expired_blocked,
        "expired_candidate_blocked_rate": (
            expired_blocked / candidate_count if candidate_count else 0.0
        ),
        "dynamic_disabled_blocked_count": dynamic_disabled,
        "dynamic_disabled_blocked_rate": (
            dynamic_disabled / candidate_count if candidate_count else 0.0
        ),
        "missing_expiration_count": report.cache_control_outcome_counts.get(
            "missing_expiration",
            0,
        ),
        "invalid_expiration_count": report.cache_control_outcome_counts.get(
            "invalid_expiration",
            0,
        ),
        "decision_rate_safe": safe_rate,
        "decision_rate_unsafe": unsafe_rate,
        "decision_rate_uncertain": uncertain_rate,
        "false_positive_rate": report.false_positive_rate,
        "estimated_cost_usd": report.estimated_cost_usd,
        "embedding_tokens": report.embedding_tokens,
        "input_tokens": report.input_tokens,
        "output_tokens": report.output_tokens,
        "tokens_saved": report.tokens_saved,
        "p50_latency_ms": report.p50_latency_ms,
        "p95_latency_ms": report.p95_latency_ms,
        "p99_latency_ms": report.p99_latency_ms,
        "decision_counts": decision_counts,
        "cache_control_outcome_counts": dict(report.cache_control_outcome_counts),
        "storage": storage_pairing
        if storage_pairing is not None
        else {
            "status": "unavailable",
            "reason": "storage_policy_pairing_not_run",
        },
    }


def _freshness_proportion_extensions(
    samples: Sequence[Mapping[str, object]],
    records: Sequence[BenchmarkRecord],
    policy: FreshnessPolicySpec,
    settings: StatisticsConfig,
) -> dict[str, Any]:
    stale_ids = reviewed_stale_pair_ids(records)
    stale_indicators = stale_exposure_indicators(samples, stale_ids)
    dynamic_indicators = dynamic_reuse_served_indicators(
        samples,
        allow_dynamic_entries=policy.allow_dynamic_entries,
    )
    return {
        "stale_exposure_rate": _proportion_from_indicators(
            stale_indicators,
            settings,
        ),
        "freshness_violation_rate": _proportion_from_indicators(
            stale_indicators,
            settings,
        ),
        "dynamic_reuse_served_rate": _proportion_from_indicators(
            dynamic_indicators,
            settings,
        ),
    }


def build_freshness_statistics(
    samples: Sequence[Mapping[str, object]],
    records: Sequence[BenchmarkRecord],
    policy: FreshnessPolicySpec,
    settings: StatisticsConfig,
    *,
    resampler: BootstrapResampler | None = None,
) -> dict[str, Any]:
    bootstrap = resampler or BootstrapResampler(settings)
    base = summarize_request_sample_statistics(
        samples,
        settings,
        resampler=bootstrap,
    )
    base["proportions"].update(
        _freshness_proportion_extensions(samples, records, policy, settings)
    )
    return base


def build_cache_control_outcome_metrics(
    report: CompatibilityCacheReport,
    settings: StatisticsConfig,
) -> dict[str, dict[str, Any]]:
    total = candidate_evaluation_count(report)
    result: dict[str, dict[str, Any]] = {}
    for outcome in sorted(CACHE_CONTROL_OUTCOME_FIELDS):
        count = report.cache_control_outcome_counts.get(outcome, 0)
        if count == 0 and total == 0:
            continue
        rate = count / total if total else 0.0
        rate_interval = (
            proportion_interval(count, total, settings)
            if total > 0
            else unavailable_interval(
                point=None,
                n=0,
                confidence_level=settings.confidence_level,
                reason="no_candidate_evaluations",
            )
        )
        result[outcome] = {
            "candidate_count": count,
            "candidate_rate": rate,
            "candidate_rate_interval": rate_interval,
        }
    return result


def _strata_with_freshness_extensions(
    samples: Sequence[Mapping[str, object]],
    records: Sequence[BenchmarkRecord],
    policy: FreshnessPolicySpec,
    settings: StatisticsConfig,
    field: str,
    *,
    resampler: BootstrapResampler,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for sample in samples:
        value = sample.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value:
            raise ValueError(f"sample field {field!r} must be a non-empty string")
        grouped.setdefault(value, []).append(sample)

    strata: dict[str, dict[str, Any]] = {}
    for label, rows in grouped.items():
        stats = build_freshness_statistics(
            rows,
            records,
            policy,
            settings,
            resampler=resampler,
        )
        strata[label] = {
            "request_count": len(rows),
            "statistics": stats,
        }
    return strata


def _overall_policy_name(
    policies: Sequence[FreshnessPolicySpec],
    selected_policy_name: str | None,
) -> str:
    if selected_policy_name is not None:
        return selected_policy_name
    for policy in policies:
        if policy.name == "default":
            return "default"
    return policies[0].name


def build_invalidation_section(experiment: FreshnessExperimentConfig) -> dict[str, object]:
    from sscre.freshness_invalidation import build_invalidation_artifact

    return build_invalidation_artifact(experiment)


def assemble_freshness_metric_sections(
    *,
    experiment: FreshnessExperimentConfig,
    records: list[BenchmarkRecord],
    reports_by_policy: Mapping[str, CompatibilityCacheReport],
    policies: Sequence[FreshnessPolicySpec],
    evaluation_config: Mapping[str, Any],
    selected_policy_name: str | None,
) -> dict[str, object]:
    settings = statistics_config_from_mapping(dict(evaluation_config))
    resampler = BootstrapResampler(settings)
    overall_name = _overall_policy_name(policies, selected_policy_name)
    overall_report = reports_by_policy[overall_name]
    overall_policy = next(p for p in policies if p.name == overall_name)
    overall_samples = overall_report.request_samples

    config_version = str(evaluation_config.get("config_version", ""))
    dataset_version = str(evaluation_config.get("dataset_version", ""))
    storage_sections = build_storage_sections_for_policies(
        policies,
        reports_by_policy,
        dataset_version=dataset_version,
        config_version=config_version,
        evaluation_config=evaluation_config,
    )
    storage_by_policy = storage_sections["storage_by_policy"]
    assert isinstance(storage_by_policy, dict)

    metrics_by_policy: dict[str, object] = {}
    statistics_by_policy: dict[str, object] = {}
    stale_exposure_accounting_by_policy: dict[str, object] = {}
    for policy in policies:
        report = reports_by_policy[policy.name]
        pairing = storage_by_policy[policy.name]
        assert isinstance(pairing, dict)
        metrics_by_policy[policy.name] = compatibility_report_to_policy_metrics(
            records,
            report,
            policy=policy,
            storage_pairing=pairing,
        )
        statistics_by_policy[policy.name] = build_freshness_statistics(
            report.request_samples,
            records,
            policy,
            settings,
            resampler=resampler,
        )
        stale_exposure_accounting_by_policy[policy.name] = (
            build_stale_exposure_accounting(
                records,
                report,
                policy,
                settings,
            )
        )

    metrics_overall = {
        "policy_name": overall_name,
        "measurement_environment": "synthetic_replay",
        **compatibility_report_to_policy_metrics(
            records,
            overall_report,
            policy=overall_policy,
        ),
        "statistics": build_freshness_statistics(
            overall_samples,
            records,
            overall_policy,
            settings,
            resampler=resampler,
        ),
    }

    reporting = experiment.freshness_class_reporting
    metrics_by_reviewed: dict[str, object] | None = None
    metrics_by_runtime: dict[str, object] | None = None
    if reporting in {"reviewed", "both"}:
        metrics_by_reviewed = _strata_with_freshness_extensions(
            overall_samples,
            records,
            overall_policy,
            settings,
            "freshness_class",
            resampler=resampler,
        )
    if reporting in {"runtime", "both"}:
        metrics_by_runtime = _strata_with_freshness_extensions(
            overall_samples,
            records,
            overall_policy,
            settings,
            "runtime_temporal_class",
            resampler=resampler,
        )

    metrics_by_cache_control_outcome = build_cache_control_outcome_metrics(
        overall_report,
        settings,
    )

    return {
        "metrics_overall": metrics_overall,
        "metrics_by_policy": metrics_by_policy,
        "metrics_by_reviewed_freshness_class": metrics_by_reviewed,
        "metrics_by_runtime_temporal_class": metrics_by_runtime,
        "metrics_by_cache_control_outcome": metrics_by_cache_control_outcome,
        "statistics_by_policy": statistics_by_policy,
        "stale_exposure_accounting": stale_exposure_accounting_by_policy[
            overall_name
        ],
        "stale_exposure_accounting_by_policy": stale_exposure_accounting_by_policy,
        **storage_sections,
        "freshness_statistics_schema_version": EVALUATION_STATISTICS_SCHEMA_VERSION,
        "invalidation": build_invalidation_section(experiment),
    }
