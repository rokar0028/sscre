"""Deterministic freshness-policy replay (Workstream 6)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from sscre.baseline import (
    CompatibilityCacheReport,
    NoCacheReport,
    compatibility_cache_cost_kwargs_from_config,
    no_cache_cost_kwargs_from_config,
    run_compatibility_cache_baseline,
    run_no_cache_baseline,
)
from sscre.benchmark import BenchmarkRecord
from sscre.freshness_evaluation import (
    DEFAULT_REPLAY_ANCHOR_TIME,
    FreshnessExperimentConfig,
    FreshnessPolicySpec,
    FreshnessReplayClock,
    freshness_experiment_from_mapping,
)
from sscre.freshness_metrics import assemble_freshness_metric_sections
from sscre.serialization import (
    attach_evaluation_report_schema,
    redact_operational_evaluation_report,
)


def _reference_no_cache_metrics(report: NoCacheReport) -> dict[str, object]:
    return {
        "request_count": report.request_count,
        "generated_request_count": report.generated_requests,
        "estimated_cost_usd": report.estimated_cost_usd,
        "input_tokens": report.input_tokens,
        "output_tokens": report.output_tokens,
        "average_latency_ms": report.average_latency_ms,
    }


def _policies_for_split(
    experiment: FreshnessExperimentConfig,
    split: str,
    selected_policy_name: str | None,
) -> tuple[FreshnessPolicySpec, ...]:
    if split == "development":
        return experiment.policy_matrix
    if selected_policy_name is None:
        raise ValueError(
            "held-out freshness replay requires selected_policy_name "
            "(development selection must be frozen first)"
        )
    for policy in experiment.policy_matrix:
        if policy.name == selected_policy_name:
            return (policy,)
    raise ValueError(
        f"selected policy {selected_policy_name!r} is not in the policy matrix"
    )


def run_freshness_policy_replay(
    records: list[BenchmarkRecord],
    *,
    config: dict[str, Any],
    split: str,
    selected_threshold: float,
    threshold_selection_rule: str,
    selected_policy_name: str | None = None,
    frozen_development_selection: Mapping[str, object] | None = None,
    git_commit: str | None = None,
    git_worktree_dirty: bool | None = None,
    anchor_time: datetime | None = None,
) -> dict[str, object]:
    """Replay compatibility-cache under each policy arm with isolated cache state."""
    experiment = freshness_experiment_from_mapping(config)
    if experiment is None:
        raise ValueError("configuration must include freshness_experiment")

    if split == "held-out":
        if frozen_development_selection is None:
            raise ValueError(
                "held-out replay requires frozen development selection"
            )
        from sscre.freshness_policy_selection import (
            assert_frozen_policy_matches_matrix,
            assert_frozen_selection_matches_run,
        )

        assert_frozen_selection_matches_run(
            frozen_development_selection,
            config_version=str(config["config_version"]),
            dataset_version=str(config["dataset_version"]),
        )
        assert_frozen_policy_matches_matrix(
            frozen_development_selection,
            experiment,
        )
        frozen_name = frozen_development_selection.get("name")
        if selected_policy_name is not None and frozen_name != selected_policy_name:
            raise ValueError(
                "selected_policy_name must match frozen development selection"
            )
        if selected_policy_name is None and isinstance(frozen_name, str):
            selected_policy_name = frozen_name

    if split == "held-out" and experiment.scope == "development_only":
        for class_name in ("semi_dynamic", "dynamic"):
            if experiment.held_out_freshness_scope.get(class_name) == "evaluated":
                raise ValueError(
                    "Option A held-out scope cannot evaluate "
                    f"{class_name} on held-out split"
                )

    anchor = anchor_time or DEFAULT_REPLAY_ANCHOR_TIME
    if anchor.tzinfo is None or anchor.utcoffset() is None:
        raise ValueError("anchor_time must be timezone-aware")

    policies = _policies_for_split(experiment, split, selected_policy_name)
    dataset_version = str(config["dataset_version"])
    compatibility_options = {
        "dataset_version": dataset_version,
        **compatibility_cache_cost_kwargs_from_config(config),
    }
    top_k = int(config["embedding_top_k"])

    no_cache_report = run_no_cache_baseline(
        records,
        dataset_version=dataset_version,
        **no_cache_cost_kwargs_from_config(config),
    )
    reports_by_policy: dict[str, CompatibilityCacheReport] = {}
    policy_runs: list[dict[str, object]] = []

    for policy in policies:
        clock = FreshnessReplayClock.from_policy_spec(policy, anchor)
        report = run_compatibility_cache_baseline(
            records,
            threshold=selected_threshold,
            top_k=top_k,
            freshness_replay_clock=clock,
            **compatibility_options,
        )
        reports_by_policy[policy.name] = report
        policy_runs.append(
            {
                "policy_name": policy.name,
                "policy": policy.to_dict(),
                "replay_anchor_time": anchor.isoformat(),
                "replay_clock_step_seconds": clock.step.total_seconds(),
            }
        )

    metric_sections = assemble_freshness_metric_sections(
        experiment=experiment,
        records=records,
        reports_by_policy=reports_by_policy,
        policies=policies,
        evaluation_config=config,
        selected_policy_name=selected_policy_name,
    )
    metrics_by_policy = metric_sections["metrics_by_policy"]
    assert isinstance(metrics_by_policy, dict)
    for run in policy_runs:
        policy_name = run["policy_name"]
        assert isinstance(policy_name, str)
        run["metrics"] = metrics_by_policy[policy_name]

    selected_policy_block: dict[str, object] | None = None
    policy_selection_block: object | None = None
    if split == "development":
        from sscre.freshness_policy_selection import (
            assert_development_selection_has_no_held_out_outcomes,
            select_development_freshness_policy,
        )

        selection_result = select_development_freshness_policy(
            experiment,
            metrics_by_policy,  # type: ignore[arg-type]
            config_version=str(config["config_version"]),
            dataset_version=str(config["dataset_version"]),
            git_commit=git_commit,
            git_worktree_dirty=git_worktree_dirty,
        )
        selected_policy_block = selection_result["selected_policy"]  # type: ignore[assignment]
        assert isinstance(selected_policy_block, dict)
        assert_development_selection_has_no_held_out_outcomes(selected_policy_block)
        policy_selection_block = selection_result["policy_candidates"]
    elif split == "held-out":
        from sscre.freshness_policy_selection import (
            build_held_out_selected_policy_record,
        )

        assert frozen_development_selection is not None
        assert selected_policy_name is not None
        held_metrics = metrics_by_policy[selected_policy_name]
        assert isinstance(held_metrics, dict)
        selected_policy_block = build_held_out_selected_policy_record(
            frozen_development_selection,
            held_metrics,
            experiment,
        )

    limitations: list[str] = []
    if split == "held-out":
        for class_name in ("semi_dynamic", "dynamic"):
            if experiment.held_out_freshness_scope.get(class_name) == "unavailable":
                limitations.append(
                    f"held_out_{class_name}_claims_unavailable"
                )
    if all(record.answer_availability == "none" for record in records):
        limitations.append("answer_level_stale_exposure_unavailable")

    freshness_block: dict[str, object] = {
        **experiment.to_dict(),
        "evaluation_split": split,
        "measurement_environment": "synthetic_replay",
        "replay_anchor_time": anchor.isoformat(),
        "compatibility_threshold": selected_threshold,
        "threshold_selection_rule": threshold_selection_rule,
        **metric_sections,
        "reference_baselines": {
            "no-cache": _reference_no_cache_metrics(no_cache_report),
        },
        "policy_runs": policy_runs,
        "limitations": limitations,
    }
    if selected_policy_block is not None:
        freshness_block["selected_policy"] = selected_policy_block
    if policy_selection_block is not None:
        freshness_block["policy_selection"] = policy_selection_block
    if selected_policy_name is not None:
        freshness_block["selected_policy_name"] = selected_policy_name
    if split == "held-out" and frozen_development_selection is not None:
        freshness_block["frozen_development_selection"] = {
            "name": frozen_development_selection.get("name"),
            "selection_split": frozen_development_selection.get("selection_split"),
            "config_version": frozen_development_selection.get("config_version"),
            "dataset_version": frozen_development_selection.get("dataset_version"),
            "constraint_satisfied": frozen_development_selection.get(
                "constraint_satisfied"
            ),
        }

    payload: dict[str, object] = {
        "baseline": "freshness-policy-replay",
        "config_version": config["config_version"],
        "dataset_version": config["dataset_version"],
        "evaluation_split": split,
        "measurement_environment": "synthetic_replay",
        "freshness_experiment": freshness_block,
    }
    return payload


def build_freshness_replay_report(
    records: list[BenchmarkRecord],
    *,
    config: dict[str, Any],
    split: str,
    selected_threshold: float,
    threshold_selection_rule: str,
    selected_policy_name: str | None = None,
    frozen_development_selection: Mapping[str, object] | None = None,
    git_commit: str | None = None,
    git_worktree_dirty: bool | None = None,
    anchor_time: datetime | None = None,
) -> dict[str, object]:
    payload = run_freshness_policy_replay(
        records,
        config=config,
        split=split,
        selected_threshold=selected_threshold,
        threshold_selection_rule=threshold_selection_rule,
        selected_policy_name=selected_policy_name,
        frozen_development_selection=frozen_development_selection,
        git_commit=git_commit,
        git_worktree_dirty=git_worktree_dirty,
        anchor_time=anchor_time,
    )
    return redact_operational_evaluation_report(
        attach_evaluation_report_schema(payload)
    )


def write_freshness_replay_report(
    path: Path,
    report: Mapping[str, object],
) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
