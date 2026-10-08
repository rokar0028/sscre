"""Versioned freshness-policy experiment schema (Workstream 6)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Mapping

from sscre.cache_controls import CacheControlPolicy, CacheControlResult, evaluate_cache_control
from sscre.safety import QueryMetadata, TemporalClass

FRESHNESS_EVALUATION_SCHEMA_VERSION = "freshness-evaluation-1.0"

FreshnessExperimentScope = Literal["development_only", "development_and_held_out"]
FreshnessClassReporting = Literal["reviewed", "runtime", "both"]
HeldOutClassScope = Literal["evaluated", "unavailable"]
InvalidationScope = Literal[
    "repository_boundary_only",
    "unavailable",
    "not_evaluated",
]

_POLICY_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")

DEFAULT_STABLE_TTL_SECONDS = 30 * 24 * 60 * 60
DEFAULT_SEMI_DYNAMIC_TTL_SECONDS = 24 * 60 * 60
DEFAULT_REPLAY_ANCHOR_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
DEFAULT_REPLAY_CLOCK_STEP = timedelta(seconds=1)

FRESHNESS_METRIC_FIELDS = frozenset(
    {
        "request_count",
        "cache_hit_rate",
        "safe_reuse_coverage",
        "stale_exposure_count",
        "stale_exposure_rate",
        "freshness_violation_count",
        "freshness_violation_rate",
        "dynamic_reuse_served_count",
        "dynamic_reuse_served_rate",
        "expired_candidate_blocked_count",
        "expired_candidate_blocked_rate",
        "dynamic_disabled_blocked_count",
        "missing_expiration_count",
        "invalid_expiration_count",
    }
)

CACHE_CONTROL_OUTCOME_FIELDS = frozenset(
    {
        "fresh",
        "expired",
        "dynamic_entries_disabled",
        "missing_expiration",
        "invalid_expiration",
    }
)


@dataclass(frozen=True)
class FreshnessPolicySpec:
    name: str
    stable_ttl_seconds: int
    semi_dynamic_ttl_seconds: int
    dynamic_ttl_seconds: int | None
    allow_dynamic_entries: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "stable_ttl_seconds": self.stable_ttl_seconds,
            "semi_dynamic_ttl_seconds": self.semi_dynamic_ttl_seconds,
            "dynamic_ttl_seconds": self.dynamic_ttl_seconds,
            "allow_dynamic_entries": self.allow_dynamic_entries,
        }

    def to_cache_control_policy(self) -> CacheControlPolicy:
        return CacheControlPolicy(
            stable_ttl=timedelta(seconds=self.stable_ttl_seconds),
            semi_dynamic_ttl=timedelta(seconds=self.semi_dynamic_ttl_seconds),
            dynamic_ttl=(
                timedelta(seconds=self.dynamic_ttl_seconds)
                if self.dynamic_ttl_seconds is not None
                else None
            ),
            allow_dynamic_entries=self.allow_dynamic_entries,
        )

    def to_settings(self) -> "Settings":
        from sscre.config import Settings

        return Settings(
            stable_ttl_seconds=self.stable_ttl_seconds,
            semi_dynamic_ttl_seconds=self.semi_dynamic_ttl_seconds,
            dynamic_ttl_seconds=self.dynamic_ttl_seconds,
            allow_dynamic_entries=self.allow_dynamic_entries,
        )


def require_timezone_aware(value: datetime, *, field_name: str = "datetime") -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


@dataclass
class FreshnessReplayClock:
    """Deterministic replay clock; not used on the live request path."""

    policy: CacheControlPolicy
    current_time: datetime
    policy_name: str = "replay"
    step: timedelta = DEFAULT_REPLAY_CLOCK_STEP

    def __post_init__(self) -> None:
        require_timezone_aware(self.current_time, field_name="current_time")
        if self.step <= timedelta(0):
            raise ValueError("step must be positive")

    @classmethod
    def from_policy_spec(
        cls,
        spec: FreshnessPolicySpec,
        anchor_time: datetime,
        *,
        step: timedelta | None = None,
    ) -> FreshnessReplayClock:
        require_timezone_aware(anchor_time, field_name="anchor_time")
        return cls(
            policy=spec.to_cache_control_policy(),
            current_time=anchor_time,
            policy_name=spec.name,
            step=step or DEFAULT_REPLAY_CLOCK_STEP,
        )

    def comparison_time(self) -> datetime:
        return self.current_time

    def advance(self) -> None:
        self.current_time = self.current_time + self.step

    def evaluate_cache_control(
        self,
        freshness_class: TemporalClass,
        ttl_expires_at: datetime | None,
    ) -> CacheControlResult:
        return evaluate_cache_control(
            freshness_class,
            ttl_expires_at,
            now=self.current_time,
            policy=self.policy,
        )

    def ttl_expires_at_for_insert(
        self,
        metadata: QueryMetadata | None,
    ) -> datetime | None:
        temporal_class: TemporalClass = (
            metadata.temporal_class if metadata is not None else "stable"
        )
        ttl = self.policy.ttl_for(temporal_class)
        if ttl is None:
            return None
        return self.current_time + ttl


def build_replay_clocks_for_matrix(
    policies: tuple[FreshnessPolicySpec, ...],
    anchor_time: datetime,
    *,
    step: timedelta | None = None,
) -> dict[str, FreshnessReplayClock]:
    """Return an isolated replay clock per policy arm (fresh cache state each arm)."""
    require_timezone_aware(anchor_time, field_name="anchor_time")
    return {
        spec.name: FreshnessReplayClock.from_policy_spec(
            spec,
            anchor_time,
            step=step,
        )
        for spec in policies
    }


def settings_cache_policy_matches_spec(spec: FreshnessPolicySpec) -> bool:
    settings_policy = spec.to_settings().cache_control_policy()
    spec_policy = spec.to_cache_control_policy()
    return (
        settings_policy.stable_ttl == spec_policy.stable_ttl
        and settings_policy.semi_dynamic_ttl == spec_policy.semi_dynamic_ttl
        and settings_policy.dynamic_ttl == spec_policy.dynamic_ttl
        and settings_policy.allow_dynamic_entries == spec_policy.allow_dynamic_entries
    )


@dataclass(frozen=True)
class FreshnessSelectionConfig:
    selection_rule: str
    objective: str
    max_stale_exposure_rate: float
    max_false_positive_rate: float
    max_dynamic_reuse_served_rate: float

    def constraints_dict(self) -> dict[str, float]:
        return {
            "max_stale_exposure_rate": self.max_stale_exposure_rate,
            "max_false_positive_rate": self.max_false_positive_rate,
            "max_dynamic_reuse_served_rate": self.max_dynamic_reuse_served_rate,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "selection_rule": self.selection_rule,
            "objective": self.objective,
            "constraints": self.constraints_dict(),
        }


@dataclass(frozen=True)
class FreshnessExperimentConfig:
    schema_version: str
    scope: FreshnessExperimentScope
    freshness_class_reporting: FreshnessClassReporting
    held_out_freshness_scope: dict[str, object]
    policy_matrix: tuple[FreshnessPolicySpec, ...]
    selection: FreshnessSelectionConfig
    invalidation_scope: InvalidationScope

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "freshness_class_reporting": self.freshness_class_reporting,
            "held_out_freshness_scope": dict(self.held_out_freshness_scope),
            "policy_matrix": [policy.to_dict() for policy in self.policy_matrix],
            "selection": self.selection.to_dict(),
            "invalidation_scope": self.invalidation_scope,
        }


def default_policy_matrix() -> tuple[FreshnessPolicySpec, ...]:
    return (
        FreshnessPolicySpec(
            name="conservative",
            stable_ttl_seconds=3600,
            semi_dynamic_ttl_seconds=600,
            dynamic_ttl_seconds=None,
            allow_dynamic_entries=False,
        ),
        FreshnessPolicySpec(
            name="default",
            stable_ttl_seconds=DEFAULT_STABLE_TTL_SECONDS,
            semi_dynamic_ttl_seconds=DEFAULT_SEMI_DYNAMIC_TTL_SECONDS,
            dynamic_ttl_seconds=None,
            allow_dynamic_entries=False,
        ),
        FreshnessPolicySpec(
            name="dynamic-short",
            stable_ttl_seconds=DEFAULT_STABLE_TTL_SECONDS,
            semi_dynamic_ttl_seconds=DEFAULT_SEMI_DYNAMIC_TTL_SECONDS,
            dynamic_ttl_seconds=300,
            allow_dynamic_entries=True,
        ),
        FreshnessPolicySpec(
            name="long-lived",
            stable_ttl_seconds=90 * 24 * 60 * 60,
            semi_dynamic_ttl_seconds=7 * 24 * 60 * 60,
            dynamic_ttl_seconds=None,
            allow_dynamic_entries=False,
        ),
    )


def default_held_out_freshness_scope_option_a() -> dict[str, object]:
    return {
        "stable": "evaluated",
        "semi_dynamic": "unavailable",
        "dynamic": "unavailable",
        "reason": (
            "Held-out split has zero reviewed semi-dynamic and zero dynamic "
            "pairs (WS6 Step 1 audit); Option A development-only scope."
        ),
    }


def _validate_policy_name(name: object) -> str:
    if not isinstance(name, str) or not _POLICY_NAME_PATTERN.match(name):
        raise ValueError(
            "policy name must match [a-z][a-z0-9_-]* and be non-empty"
        )
    return name


def _validate_positive_ttl_seconds(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def parse_freshness_policy_spec(raw: Mapping[str, object]) -> FreshnessPolicySpec:
    name = _validate_policy_name(raw.get("name"))
    stable_ttl_seconds = _validate_positive_ttl_seconds(
        "stable_ttl_seconds",
        raw.get("stable_ttl_seconds"),
    )
    semi_dynamic_ttl_seconds = _validate_positive_ttl_seconds(
        "semi_dynamic_ttl_seconds",
        raw.get("semi_dynamic_ttl_seconds"),
    )
    allow_dynamic_entries = raw.get("allow_dynamic_entries", False)
    if not isinstance(allow_dynamic_entries, bool):
        raise ValueError("allow_dynamic_entries must be a boolean")

    dynamic_ttl_raw = raw.get("dynamic_ttl_seconds")
    dynamic_ttl_seconds: int | None
    if dynamic_ttl_raw is None:
        dynamic_ttl_seconds = None
    else:
        dynamic_ttl_seconds = _validate_positive_ttl_seconds(
            "dynamic_ttl_seconds",
            dynamic_ttl_raw,
        )

    if allow_dynamic_entries and dynamic_ttl_seconds is None:
        raise ValueError(
            "dynamic_ttl_seconds is required when allow_dynamic_entries is true"
        )
    if not allow_dynamic_entries and dynamic_ttl_seconds is not None:
        raise ValueError(
            "dynamic_ttl_seconds must be null when allow_dynamic_entries is false"
        )

    spec = FreshnessPolicySpec(
        name=name,
        stable_ttl_seconds=stable_ttl_seconds,
        semi_dynamic_ttl_seconds=semi_dynamic_ttl_seconds,
        dynamic_ttl_seconds=dynamic_ttl_seconds,
        allow_dynamic_entries=allow_dynamic_entries,
    )
    spec.to_cache_control_policy()
    return spec


def validate_freshness_policy_matrix(policies: object) -> tuple[FreshnessPolicySpec, ...]:
    if not isinstance(policies, list) or not policies:
        raise ValueError("policy_matrix must be a non-empty list")
    parsed: list[FreshnessPolicySpec] = []
    seen: set[str] = set()
    for entry in policies:
        if not isinstance(entry, Mapping):
            raise ValueError("each policy_matrix entry must be an object")
        spec = parse_freshness_policy_spec(entry)
        if spec.name in seen:
            raise ValueError(f"duplicate policy name: {spec.name!r}")
        seen.add(spec.name)
        parsed.append(spec)
    return tuple(parsed)


def _validate_rate(name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.0 <= value <= 1.0
    ):
        raise ValueError(f"{name} must be a finite number between 0 and 1")
    return float(value)


def parse_freshness_selection(raw: Mapping[str, object]) -> FreshnessSelectionConfig:
    selection_rule = raw.get("selection_rule")
    objective = raw.get("objective")
    if not isinstance(selection_rule, str) or not selection_rule.strip():
        raise ValueError("selection.selection_rule must be a non-empty string")
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError("selection.objective must be a non-empty string")
    constraints = raw.get("constraints")
    if not isinstance(constraints, Mapping):
        raise ValueError("selection.constraints must be an object")
    return FreshnessSelectionConfig(
        selection_rule=selection_rule.strip(),
        objective=objective.strip(),
        max_stale_exposure_rate=_validate_rate(
            "max_stale_exposure_rate",
            constraints.get("max_stale_exposure_rate", 0.0),
        ),
        max_false_positive_rate=_validate_rate(
            "max_false_positive_rate",
            constraints.get("max_false_positive_rate", 0.0),
        ),
        max_dynamic_reuse_served_rate=_validate_rate(
            "max_dynamic_reuse_served_rate",
            constraints.get("max_dynamic_reuse_served_rate", 0.0),
        ),
    )


def validate_held_out_freshness_scope(scope: object) -> dict[str, object]:
    if not isinstance(scope, Mapping):
        raise ValueError("held_out_freshness_scope must be an object")
    result: dict[str, object] = {}
    for class_name in ("stable", "semi_dynamic", "dynamic"):
        value = scope.get(class_name)
        if value not in {"evaluated", "unavailable"}:
            raise ValueError(
                f"held_out_freshness_scope.{class_name} must be "
                "'evaluated' or 'unavailable'"
            )
        result[class_name] = value
    reason = scope.get("reason")
    if reason is not None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("held_out_freshness_scope.reason must be a non-empty string")
        result["reason"] = reason.strip()
    return result


def apply_freshness_experiment_config_defaults(config: dict[str, Any]) -> None:
    """Validate and normalize the nested freshness_experiment config block."""
    block = config.get("freshness_experiment")
    if block is None:
        return
    if not isinstance(block, dict):
        raise ValueError("freshness_experiment must be an object")

    schema_version = block.get("schema_version", FRESHNESS_EVALUATION_SCHEMA_VERSION)
    if schema_version != FRESHNESS_EVALUATION_SCHEMA_VERSION:
        raise ValueError(
            f"freshness_experiment.schema_version must be "
            f"{FRESHNESS_EVALUATION_SCHEMA_VERSION!r}"
        )
    block["schema_version"] = schema_version

    scope = block.get("scope", "development_only")
    if scope not in {"development_only", "development_and_held_out"}:
        raise ValueError(
            "freshness_experiment.scope must be development_only or "
            "development_and_held_out"
        )
    block["scope"] = scope

    reporting = block.get("freshness_class_reporting", "both")
    if reporting not in {"reviewed", "runtime", "both"}:
        raise ValueError(
            "freshness_class_reporting must be reviewed, runtime, or both"
        )
    block["freshness_class_reporting"] = reporting

    held_out_scope = block.get(
        "held_out_freshness_scope",
        default_held_out_freshness_scope_option_a(),
    )
    block["held_out_freshness_scope"] = validate_held_out_freshness_scope(
        held_out_scope
    )

    if scope == "development_only":
        for class_name in ("semi_dynamic", "dynamic"):
            if block["held_out_freshness_scope"].get(class_name) == "evaluated":
                raise ValueError(
                    "development_only scope cannot mark held-out semi_dynamic or "
                    "dynamic as evaluated"
                )

    policy_matrix = block.get("policy_matrix")
    if policy_matrix is None:
        block["policy_matrix"] = [
            policy.to_dict() for policy in default_policy_matrix()
        ]
    else:
        block["policy_matrix"] = [
            spec.to_dict()
            for spec in validate_freshness_policy_matrix(policy_matrix)
        ]

    selection = block.get("selection")
    if selection is None:
        block["selection"] = FreshnessSelectionConfig(
            selection_rule="constraint_first_then_maximize_safe_reuse_coverage",
            objective="safe_reuse_coverage",
            max_stale_exposure_rate=0.0,
            max_false_positive_rate=float(config.get("max_false_positive_rate", 0.0)),
            max_dynamic_reuse_served_rate=0.0,
        ).to_dict()
    elif isinstance(selection, dict):
        block["selection"] = parse_freshness_selection(selection).to_dict()
    else:
        raise ValueError("freshness_experiment.selection must be an object")

    invalidation_scope = block.get("invalidation_scope", "repository_boundary_only")
    if invalidation_scope not in {
        "repository_boundary_only",
        "unavailable",
        "not_evaluated",
    }:
        raise ValueError("invalidation_scope is not supported")
    block["invalidation_scope"] = invalidation_scope

    config["freshness_experiment"] = block


def freshness_experiment_from_mapping(
    config: Mapping[str, Any],
) -> FreshnessExperimentConfig | None:
    block = config.get("freshness_experiment")
    if block is None:
        return None
    merged = dict(config)
    apply_freshness_experiment_config_defaults(merged)
    normalized = merged["freshness_experiment"]
    assert isinstance(normalized, dict)
    policies = validate_freshness_policy_matrix(normalized["policy_matrix"])
    selection_raw = normalized["selection"]
    assert isinstance(selection_raw, dict)
    selection = parse_freshness_selection(selection_raw)
    held_out_scope = validate_held_out_freshness_scope(
        normalized["held_out_freshness_scope"]
    )
    return FreshnessExperimentConfig(
        schema_version=str(normalized["schema_version"]),
        scope=normalized["scope"],  # type: ignore[arg-type]
        freshness_class_reporting=normalized["freshness_class_reporting"],  # type: ignore[arg-type]
        held_out_freshness_scope=held_out_scope,
        policy_matrix=policies,
        selection=selection,
        invalidation_scope=normalized["invalidation_scope"],  # type: ignore[arg-type]
    )


def _validate_finite_metric(name: str, value: object) -> None:
    if value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be a finite non-negative number or null")


def validate_freshness_policy_metrics(metrics: object) -> None:
    if not isinstance(metrics, Mapping):
        raise ValueError("policy metrics must be an object")
    for field_name in FRESHNESS_METRIC_FIELDS:
        if field_name in metrics:
            _validate_finite_metric(field_name, metrics[field_name])
    outcomes = metrics.get("cache_control_outcome_counts")
    if outcomes is not None:
        if not isinstance(outcomes, Mapping):
            raise ValueError("cache_control_outcome_counts must be an object")
        for key, count in outcomes.items():
            if key not in CACHE_CONTROL_OUTCOME_FIELDS:
                raise ValueError(f"unsupported cache_control_outcome: {key!r}")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(
                    "cache_control_outcome_counts values must be non-negative integers"
                )


def validate_selected_policy_record(record: object) -> None:
    if not isinstance(record, Mapping):
        raise ValueError("selected_policy must be an object")
    name = record.get("name")
    constraint_satisfied = record.get("constraint_satisfied")
    if name is None:
        if constraint_satisfied is not False:
            raise ValueError(
                "selected_policy.name may be null only when "
                "constraint_satisfied is false"
            )
    else:
        _validate_policy_name(name)
    if not isinstance(constraint_satisfied, bool):
        raise ValueError("selected_policy.constraint_satisfied must be a boolean")
    selection_rule = record.get("selection_rule")
    if not isinstance(selection_rule, str) or not selection_rule.strip():
        raise ValueError("selected_policy.selection_rule must be a non-empty string")
    constraints = record.get("constraints")
    if not isinstance(constraints, Mapping):
        raise ValueError("selected_policy.constraints must be an object")
    _validate_rate(
        "max_stale_exposure_rate",
        constraints.get("max_stale_exposure_rate", 0.0),
    )
    _validate_rate(
        "max_false_positive_rate",
        constraints.get("max_false_positive_rate", 0.0),
    )
    _validate_rate(
        "max_dynamic_reuse_served_rate",
        constraints.get("max_dynamic_reuse_served_rate", 0.0),
    )


def validate_freshness_experiment_report(block: object) -> None:
    """Validate a freshness experiment artifact block before persistence."""
    from sscre.evaluation_statistics import _validate_interval_nodes

    if not isinstance(block, Mapping):
        raise ValueError("freshness_experiment report block must be an object")
    schema_version = block.get("schema_version")
    if schema_version != FRESHNESS_EVALUATION_SCHEMA_VERSION:
        raise ValueError(
            f"freshness schema_version must be {FRESHNESS_EVALUATION_SCHEMA_VERSION!r}"
        )

    policy_matrix = block.get("policy_matrix")
    if policy_matrix is not None:
        validate_freshness_policy_matrix(policy_matrix)

    by_policy = block.get("metrics_by_policy")
    if by_policy is not None:
        if not isinstance(by_policy, Mapping):
            raise ValueError("metrics_by_policy must be an object")
        for policy_name, metrics in by_policy.items():
            _validate_policy_name(policy_name)
            validate_freshness_policy_metrics(metrics)

    metrics_overall = block.get("metrics_overall")
    if metrics_overall is not None:
        if not isinstance(metrics_overall, Mapping):
            raise ValueError("metrics_overall must be an object")
        validate_freshness_policy_metrics(metrics_overall)
        statistics = metrics_overall.get("statistics")
        if statistics is not None:
            _validate_interval_nodes(statistics)

    for section_name in (
        "metrics_by_reviewed_freshness_class",
        "metrics_by_runtime_temporal_class",
    ):
        section = block.get(section_name)
        if section is None:
            continue
        if not isinstance(section, Mapping):
            raise ValueError(f"{section_name} must be an object")
        for _label, row in section.items():
            if not isinstance(row, Mapping):
                raise ValueError(f"{section_name} entries must be objects")
            stats = row.get("statistics")
            if stats is not None:
                _validate_interval_nodes(stats)

    cache_outcomes = block.get("metrics_by_cache_control_outcome")
    if cache_outcomes is not None:
        if not isinstance(cache_outcomes, Mapping):
            raise ValueError("metrics_by_cache_control_outcome must be an object")
        _validate_interval_nodes(cache_outcomes)

    statistics_by_policy = block.get("statistics_by_policy")
    if statistics_by_policy is not None:
        if not isinstance(statistics_by_policy, Mapping):
            raise ValueError("statistics_by_policy must be an object")
        _validate_interval_nodes(statistics_by_policy)

    storage_by_policy = block.get("storage_by_policy")
    if storage_by_policy is not None:
        if not isinstance(storage_by_policy, Mapping):
            raise ValueError("storage_by_policy must be an object")

    reuse_points = block.get("reuse_vs_storage_points")
    if reuse_points is not None:
        if not isinstance(reuse_points, list):
            raise ValueError("reuse_vs_storage_points must be a list")

    for accounting_key in (
        "stale_exposure_accounting",
        "stale_exposure_accounting_by_policy",
    ):
        accounting = block.get(accounting_key)
        if accounting is None:
            continue
        if not isinstance(accounting, Mapping):
            raise ValueError(f"{accounting_key} must be an object")
        if accounting_key.endswith("_by_policy"):
            for row in accounting.values():
                if isinstance(row, Mapping):
                    _validate_interval_nodes(row.get("intervals", {}))
        else:
            _validate_interval_nodes(accounting.get("intervals", {}))

    selected = block.get("selected_policy")
    if selected is not None:
        validate_selected_policy_record(selected)

    limitations = block.get("limitations")
    if limitations is not None:
        if not isinstance(limitations, list):
            raise ValueError("limitations must be a list")
        for item in limitations:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("limitations entries must be non-empty strings")

    invalidation = block.get("invalidation")
    if invalidation is not None:
        if not isinstance(invalidation, Mapping):
            raise ValueError("invalidation must be an object")
        from sscre.freshness_invalidation import validate_invalidation_artifact

        validate_invalidation_artifact(invalidation)


def attach_freshness_evaluation_schema(
    payload: Mapping[str, object],
) -> dict[str, object]:
    result = dict(payload)
    block = result.get("freshness_experiment")
    if block is not None:
        validate_freshness_experiment_report(block)
        result["freshness_evaluation_schema_version"] = (
            FRESHNESS_EVALUATION_SCHEMA_VERSION
        )
    return result
