"""Development freshness-policy selection (Workstream 6 Step 9)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from sscre.freshness_evaluation import (
    FreshnessExperimentConfig,
    FreshnessPolicySpec,
    FreshnessSelectionConfig,
    _validate_policy_name,
    validate_selected_policy_record,
)

_HELD_OUT_FORBIDDEN_SELECTION_KEYS = frozenset(
    {
        "held_out_constraint_satisfied",
        "held_out_metrics",
        "held_out_evaluation_split",
    }
)


def _metric_rate(metrics: Mapping[str, object], field: str) -> float:
    value = metrics.get(field, 0.0)
    if value is None:
        if field == "false_positive_rate":
            return math.inf
        return 0.0
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value < 0
    ):
        raise ValueError(f"policy metrics {field!r} must be a non-negative number")
    return float(value)


def _policy_spec_by_name(
    experiment: FreshnessExperimentConfig,
    name: str,
) -> FreshnessPolicySpec:
    for policy in experiment.policy_matrix:
        if policy.name == name:
            return policy
    raise ValueError(f"policy {name!r} is not in the policy matrix")


def _constraint_violations(
    metrics: Mapping[str, object],
    constraints: FreshnessSelectionConfig,
) -> list[str]:
    violations: list[str] = []
    stale_rate = _metric_rate(metrics, "stale_exposure_rate")
    if stale_rate > constraints.max_stale_exposure_rate:
        violations.append("max_stale_exposure_rate")
    dynamic_rate = _metric_rate(metrics, "dynamic_reuse_served_rate")
    if dynamic_rate > constraints.max_dynamic_reuse_served_rate:
        violations.append("max_dynamic_reuse_served_rate")
    fpr_value = metrics.get("false_positive_rate")
    if fpr_value is not None:
        false_positive_rate = _metric_rate(metrics, "false_positive_rate")
        if false_positive_rate > constraints.max_false_positive_rate:
            violations.append("max_false_positive_rate")
    return violations


def _objective_value(metrics: Mapping[str, object], objective: str) -> float:
    if objective == "safe_reuse_coverage":
        return _metric_rate(metrics, "safe_reuse_coverage")
    raise ValueError(f"unsupported selection objective: {objective!r}")


def select_development_freshness_policy(
    experiment: FreshnessExperimentConfig,
    metrics_by_policy: Mapping[str, Mapping[str, object]],
    *,
    config_version: str,
    dataset_version: str,
    git_commit: str | None = None,
    git_worktree_dirty: bool | None = None,
) -> dict[str, object]:
    """Constraint-first development selection from replay metrics only."""
    selection = experiment.selection
    candidates: list[dict[str, object]] = []
    eligible_names: list[str] = []

    for policy in experiment.policy_matrix:
        metrics = metrics_by_policy.get(policy.name)
        if not isinstance(metrics, Mapping):
            raise ValueError(
                f"development replay missing metrics for policy {policy.name!r}"
            )
        violations = _constraint_violations(metrics, selection)
        candidate = {
            "name": policy.name,
            "policy": policy.to_dict(),
            "development_sample_count": metrics.get("request_count", 0),
            "eligible": not violations,
            "constraint_violations": violations,
            "development_metrics": {
                "safe_reuse_coverage": metrics.get("safe_reuse_coverage"),
                "stale_exposure_rate": metrics.get("stale_exposure_rate"),
                "dynamic_reuse_served_rate": metrics.get("dynamic_reuse_served_rate"),
                "false_positive_rate": metrics.get("false_positive_rate"),
            },
        }
        candidates.append(candidate)
        if not violations:
            eligible_names.append(policy.name)

    selected_name: str | None = None
    if eligible_names:
        eligible_names.sort(
            key=lambda name: (
                -_objective_value(metrics_by_policy[name], selection.objective),
                name,
            )
        )
        selected_name = eligible_names[0]

    selected_policy: dict[str, object] = {
        "name": selected_name,
        "selection_rule": selection.selection_rule,
        "objective": selection.objective,
        "constraints": selection.constraints_dict(),
        "constraint_satisfied": selected_name is not None,
        "config_version": config_version,
        "dataset_version": dataset_version,
        "selection_split": "development",
        "git_commit": git_commit,
        "git_worktree_dirty": git_worktree_dirty,
    }
    if selected_name is not None:
        selected_policy["policy"] = _policy_spec_by_name(
            experiment,
            selected_name,
        ).to_dict()

    validate_selected_policy_record(selected_policy)
    return {
        "selected_policy": selected_policy,
        "policy_candidates": candidates,
    }


def evaluate_policy_constraints(
    metrics: Mapping[str, object],
    constraints: FreshnessSelectionConfig,
) -> tuple[bool, list[str]]:
    violations = _constraint_violations(metrics, constraints)
    return (not violations, violations)


def build_held_out_selected_policy_record(
    frozen_development_selection: Mapping[str, object],
    held_out_metrics: Mapping[str, object],
    experiment: FreshnessExperimentConfig,
) -> dict[str, object]:
    if frozen_development_selection.get("selection_split") != "development":
        raise ValueError("frozen selection must come from development replay")
    name = frozen_development_selection.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(
            "held-out replay requires a development-selected policy name"
        )
    _validate_policy_name(name)
    constraints = experiment.selection
    satisfied, violations = evaluate_policy_constraints(
        held_out_metrics,
        constraints,
    )
    record = dict(frozen_development_selection)
    record["held_out_constraint_satisfied"] = satisfied
    record["held_out_constraint_violations"] = violations
    record["held_out_evaluation_split"] = "held-out"
    record["held_out_metrics_summary"] = {
        "request_count": held_out_metrics.get("request_count"),
        "safe_reuse_coverage": held_out_metrics.get("safe_reuse_coverage"),
        "stale_exposure_rate": held_out_metrics.get("stale_exposure_rate"),
        "dynamic_reuse_served_rate": held_out_metrics.get(
            "dynamic_reuse_served_rate"
        ),
        "false_positive_rate": held_out_metrics.get("false_positive_rate"),
    }
    return record


def assert_development_selection_has_no_held_out_outcomes(
    selection_block: Mapping[str, object],
) -> None:
    for key in _HELD_OUT_FORBIDDEN_SELECTION_KEYS:
        if key in selection_block:
            raise ValueError(
                f"development selection must not include held-out field {key!r}"
            )
    if selection_block.get("held_out_evaluation_split") is not None:
        raise ValueError(
            "development selection must not include held_out_evaluation_split"
        )


def assert_frozen_selection_matches_run(
    frozen: Mapping[str, object],
    *,
    config_version: str,
    dataset_version: str,
) -> None:
    frozen_config = frozen.get("config_version")
    if frozen_config != config_version:
        raise ValueError(
            "frozen development selection config_version "
            f"{frozen_config!r} does not match run config {config_version!r}"
        )
    frozen_dataset = frozen.get("dataset_version")
    if frozen_dataset != dataset_version:
        raise ValueError(
            "frozen development selection dataset_version "
            f"{frozen_dataset!r} does not match run dataset {dataset_version!r}"
        )


def assert_frozen_policy_matches_matrix(
    frozen: Mapping[str, object],
    experiment: FreshnessExperimentConfig,
) -> None:
    name = frozen.get("name")
    if not isinstance(name, str):
        raise ValueError("frozen selection requires policy name")
    spec = _policy_spec_by_name(experiment, name)
    frozen_policy = frozen.get("policy")
    if frozen_policy is None:
        return
    if not isinstance(frozen_policy, Mapping):
        raise ValueError("frozen selected_policy.policy must be an object")
    if dict(frozen_policy) != spec.to_dict():
        raise ValueError(
            f"frozen policy {name!r} does not match current policy matrix entry"
        )


def load_frozen_development_selection(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    experiment = payload.get("freshness_experiment")
    if not isinstance(experiment, Mapping):
        raise ValueError("development artifact must include freshness_experiment")
    if experiment.get("evaluation_split") != "development":
        raise ValueError(
            "frozen policy selection must be loaded from a development artifact"
        )
    selected = experiment.get("selected_policy")
    if not isinstance(selected, Mapping):
        raise ValueError("development artifact must include selected_policy")
    assert_development_selection_has_no_held_out_outcomes(selected)
    validate_selected_policy_record(selected)
    if selected.get("constraint_satisfied") is not True:
        raise ValueError(
            "development selection did not satisfy constraints; "
            "held-out replay is blocked"
        )
    name = selected.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("development selected_policy.name is required")
    return dict(selected)


def resolve_selected_policy_argument(
    value: str,
) -> tuple[str, dict[str, object] | None]:
    path = Path(value)
    if path.suffix.lower() == ".json":
        if not path.is_file():
            raise ValueError(f"selected-policy file not found: {path}")
        frozen = load_frozen_development_selection(path)
        name = frozen.get("name")
        assert isinstance(name, str)
        return name, frozen
    _validate_policy_name(value)
    return value, None
