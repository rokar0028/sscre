"""Policy-aligned storage pairing for freshness replay (Workstream 6 Step 8)."""

from __future__ import annotations

from typing import Any, Mapping

from sscre.baseline import CompatibilityCacheReport
from sscre.freshness_evaluation import FreshnessPolicySpec
from sscre.storage_evaluation import build_reuse_storage_pareto_point

FRESHNESS_STORAGE_PAIRING_VERSION = "1.0"


def build_policy_storage_pairing(
    policy: FreshnessPolicySpec,
    report: CompatibilityCacheReport,
    *,
    dataset_version: str,
    config_version: str,
) -> dict[str, object]:
    snapshot = report.policy_storage_snapshot
    if not snapshot:
        return {
            "definition_version": FRESHNESS_STORAGE_PAIRING_VERSION,
            "status": "unavailable",
            "policy_name": policy.name,
            "dataset_version": dataset_version,
            "config_version": config_version,
            "reason": "storage_snapshot_missing_use_freshness_replay_clock",
            "measurement_environment": "synthetic_storage_simulation",
        }

    return {
        "definition_version": FRESHNESS_STORAGE_PAIRING_VERSION,
        "status": "evaluated",
        "measurement_environment": "synthetic_storage_simulation",
        "dataset_version": dataset_version,
        "config_version": config_version,
        "policy_name": policy.name,
        "policy_ttl": policy.to_dict(),
        "entries": snapshot.get("entries_before_cleanup", 0),
        "total_bytes": snapshot.get("total_bytes_before_cleanup", 0),
        "canonical_answers": snapshot.get("canonical_answers_before_cleanup", 0),
        "eviction_count": snapshot.get("eviction_count", 0),
        "expiration_counter": snapshot.get("expiration_counter", 0),
        "lazy_expired_rejection_count": snapshot.get(
            "lazy_expired_rejection_count",
            0,
        ),
        "physical_expiration_cleanup_count": snapshot.get(
            "physical_expiration_cleanup_count",
            0,
        ),
        "entries_after_physical_cleanup": snapshot.get("entries_after_cleanup", 0),
        "total_bytes_after_physical_cleanup": snapshot.get(
            "total_bytes_after_cleanup",
            0,
        ),
        "distinction": {
            "lazy_expired_rejection": (
                "read-path cache_control rejects expired candidates without deleting "
                "entries during replay"
            ),
            "physical_expiration_cleanup": (
                "post-replay cleanup_expired removes expired rows from storage"
            ),
        },
    }


def build_reuse_vs_storage_point_for_policy(
    pairing: Mapping[str, object],
    report: CompatibilityCacheReport,
    *,
    evaluation_config: Mapping[str, object],
) -> dict[str, Any] | None:
    if pairing.get("status") != "evaluated":
        return None
    adapter = {
        "dataset_version": pairing["dataset_version"],
        "measurement_environment": "synthetic_storage_simulation",
        "total_bytes": pairing["total_bytes"],
        "entries": pairing["entries"],
        "eviction_count": pairing["eviction_count"],
        "safe_reuse_coverage": report.safe_reuse_coverage,
        "input_cost_per_1k_tokens": report.input_cost_per_1k_tokens,
        "output_cost_per_1k_tokens": report.output_cost_per_1k_tokens,
    }
    point = build_reuse_storage_pareto_point(
        adapter,
        evaluation_config=evaluation_config,
    )
    point["policy_name"] = pairing.get("policy_name")
    return point


def build_storage_sections_for_policies(
    policies: tuple[FreshnessPolicySpec, ...] | list[FreshnessPolicySpec],
    reports_by_policy: Mapping[str, CompatibilityCacheReport],
    *,
    dataset_version: str,
    config_version: str,
    evaluation_config: Mapping[str, object],
) -> dict[str, object]:
    storage_by_policy: dict[str, object] = {}
    reuse_vs_storage_points: list[dict[str, object]] = []
    for policy in policies:
        report = reports_by_policy[policy.name]
        pairing = build_policy_storage_pairing(
            policy,
            report,
            dataset_version=dataset_version,
            config_version=config_version,
        )
        storage_by_policy[policy.name] = pairing
        point = build_reuse_vs_storage_point_for_policy(
            pairing,
            report,
            evaluation_config=evaluation_config,
        )
        if point is not None:
            reuse_vs_storage_points.append(point)

    overall_name = next(
        (policy.name for policy in policies if policy.name == "default"),
        policies[0].name,
    )
    return {
        "storage_by_policy": storage_by_policy,
        "storage_overall": storage_by_policy.get(overall_name),
        "reuse_vs_storage_points": reuse_vs_storage_points,
    }
