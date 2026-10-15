"""Phase 4 pre-registered C-versus-A gate scoring (Step 7)."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sscre.semantic_validity_held_out import (
    HELD_OUT_GATE_READY_STATUS,
    load_held_out_gate,
    resolve_held_out_gate_path,
)

GATE_ARTIFACT_SCHEMA = "semantic-validity-gate-1.0"
STRATEGY_A = "exact-cache"
STRATEGY_C = "compatibility-cache"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_commit(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def _git_worktree_dirty(repo_root: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _baseline_report(
    held_out_artifact: Mapping[str, Any],
    baseline_name: str,
) -> dict[str, Any]:
    baselines = held_out_artifact.get("baselines")
    if not isinstance(baselines, Mapping):
        raise ValueError("held-out artifact must include baselines")
    report = baselines.get(baseline_name)
    if not isinstance(report, dict):
        raise ValueError(
            f"held-out artifact missing baseline report {baseline_name!r}"
        )
    return report


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    return float(value)


def _proportion_interval(
    held_out_artifact: Mapping[str, Any],
    baseline_name: str,
    metric: str,
) -> dict[str, Any] | None:
    statistics = held_out_artifact.get("statistics")
    if not isinstance(statistics, Mapping):
        return None
    by_baseline = statistics.get("by_baseline")
    if not isinstance(by_baseline, Mapping):
        return None
    baseline_stats = by_baseline.get(baseline_name)
    if not isinstance(baseline_stats, Mapping):
        return None
    proportions = baseline_stats.get("proportions")
    if not isinstance(proportions, Mapping):
        return None
    interval = proportions.get(metric)
    return dict(interval) if isinstance(interval, Mapping) else None


def _unlabeled_blocks_pass(compatibility_report: Mapping[str, Any]) -> bool:
    """Fail closed when Strategy C reports any unlabeled served reuse."""
    raw = compatibility_report.get("unlabeled_candidate_reuse_hits", 0)
    if isinstance(raw, bool) or not isinstance(raw, int):
        return False
    return raw == 0


def evaluate_pre_registered_requirements(
    config: Mapping[str, Any],
    *,
    strategy_a: Mapping[str, Any],
    strategy_c: Mapping[str, Any],
) -> list[dict[str, Any]]:
    max_fpr = _finite_number(config.get("max_false_positive_rate"))
    if max_fpr is None:
        raise ValueError("config max_false_positive_rate must be finite")
    max_abstention = _finite_number(config.get("max_abstention_rate"))
    if max_abstention is None:
        raise ValueError("config max_abstention_rate must be finite")

    a_coverage = _finite_number(strategy_a.get("safe_reuse_coverage"))
    c_coverage = _finite_number(strategy_c.get("safe_reuse_coverage"))
    if a_coverage is None or c_coverage is None:
        raise ValueError(
            "strategy reports must include finite safe_reuse_coverage"
        )

    c_fpr = _finite_number(strategy_c.get("false_positive_rate"))
    c_fpr_unavailable = strategy_c.get("false_positive_rate_unavailable_reason")
    if c_fpr is None:
        fpr_satisfied = False
        fpr_observed: float | None = None
    else:
        fpr_satisfied = c_fpr <= max_fpr
        fpr_observed = c_fpr

    c_abstention = _finite_number(strategy_c.get("abstention_rate"))
    abstention_satisfied = (
        c_abstention is not None and c_abstention <= max_abstention
    )

    unlabeled_hits = strategy_c.get("unlabeled_candidate_reuse_hits", 0)
    unlabeled_satisfied = _unlabeled_blocks_pass(strategy_c)

    return [
        {
            "requirement": (
                "strategy_c_safe_reuse_coverage_strictly_greater_than_strategy_a"
            ),
            "satisfied": c_coverage > a_coverage,
            "strategy_a_safe_reuse_coverage": a_coverage,
            "strategy_c_safe_reuse_coverage": c_coverage,
        },
        {
            "requirement": (
                "strategy_c_false_positive_rate_at_or_below_max_false_positive_rate"
            ),
            "satisfied": fpr_satisfied,
            "max_false_positive_rate": max_fpr,
            "strategy_c_false_positive_rate": fpr_observed,
            "strategy_c_false_positive_rate_unavailable_reason": (
                c_fpr_unavailable if c_fpr is None else None
            ),
        },
        {
            "requirement": (
                "strategy_c_abstention_rate_at_or_below_max_abstention_rate"
            ),
            "satisfied": abstention_satisfied,
            "max_abstention_rate": max_abstention,
            "strategy_c_abstention_rate": c_abstention,
        },
        {
            "requirement": (
                "unlabeled_candidate_reuse_does_not_materially_change_comparison"
            ),
            "satisfied": unlabeled_satisfied,
            "strategy_c_unlabeled_candidate_reuse_hits": unlabeled_hits,
            "rule": "any_strategy_c_unlabeled_candidate_reuse_hits_fail_closed",
        },
    ]


def score_p4_pre_registered_gate(
    config: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
    held_out_artifact: Mapping[str, Any] | None = None,
    config_sha256: str | None = None,
) -> dict[str, Any]:
    """Score the headline gate or return a deferred payload when unauthorized."""
    gate_status = gate.get("status")
    if gate_status != HELD_OUT_GATE_READY_STATUS:
        reason = gate.get("reason", "held-out gate is not ready")
        return {
            "artifact_schema_version": GATE_ARTIFACT_SCHEMA,
            "protocol_id": config.get("protocol_id", "P4-SEMVALID"),
            "config_version": config.get("config_version"),
            "status": "deferred",
            "gate_status": gate_status,
            "gate_reason": reason,
            "measurement_environment": "not_executed",
            "headline_held_out_artifact": None,
            "requirement_checks": [],
            "conservative_stack_retained": True,
            "semantic_claim_supported": False,
            "limitations": [
                "Headline C-versus-A gate requires fresh held-out evaluation "
                f"artifact and gate status {HELD_OUT_GATE_READY_STATUS!r}."
            ],
        }

    if held_out_artifact is None:
        return {
            "artifact_schema_version": GATE_ARTIFACT_SCHEMA,
            "protocol_id": config.get("protocol_id", "P4-SEMVALID"),
            "config_version": config.get("config_version"),
            "status": "deferred",
            "gate_status": gate_status,
            "measurement_environment": "not_executed",
            "headline_held_out_artifact": None,
            "requirement_checks": [],
            "conservative_stack_retained": True,
            "semantic_claim_supported": False,
            "limitations": [
                "Held-out headline comparison artifact is missing; gate cannot "
                "be scored as pass or fail."
            ],
        }

    evaluation_split = held_out_artifact.get("evaluation_split")
    if evaluation_split != "held-out":
        raise ValueError(
            "gate scoring requires evaluation_split='held-out', got "
            f"{evaluation_split!r}"
        )

    measurement_environment = held_out_artifact.get("measurement_environment")
    if measurement_environment != "local_embedding_replay":
        raise ValueError(
            "headline gate scoring requires measurement_environment="
            "'local_embedding_replay', got "
            f"{measurement_environment!r}"
        )

    if config_sha256 is not None:
        artifact_config_sha = held_out_artifact.get("config_sha256")
        if artifact_config_sha != config_sha256:
            raise ValueError(
                "held-out artifact config_sha256 does not match frozen protocol"
            )

    strategy_a = _baseline_report(held_out_artifact, STRATEGY_A)
    strategy_c = _baseline_report(held_out_artifact, STRATEGY_C)
    checks = evaluate_pre_registered_requirements(
        config,
        strategy_a=strategy_a,
        strategy_c=strategy_c,
    )
    passed = all(bool(check.get("satisfied")) for check in checks)
    status = "pass" if passed else "fail"

    primary_population = held_out_artifact.get("primary_headline_population")
    denominators = {
        "strategy_a_reusable_opportunities": strategy_a.get(
            "reusable_opportunities"
        ),
        "strategy_c_reusable_opportunities": strategy_c.get(
            "reusable_opportunities"
        ),
        "strategy_a_labeled_reuse_hits": strategy_a.get("labeled_reuse_hits"),
        "strategy_c_labeled_reuse_hits": strategy_c.get("labeled_reuse_hits"),
        "primary_headline_population": primary_population,
    }

    confidence_intervals = {
        STRATEGY_A: {
            "safe_reuse_coverage": _proportion_interval(
                held_out_artifact,
                STRATEGY_A,
                "safe_reuse_coverage",
            ),
        },
        STRATEGY_C: {
            "safe_reuse_coverage": _proportion_interval(
                held_out_artifact,
                STRATEGY_C,
                "safe_reuse_coverage",
            ),
            "false_positive_rate": _proportion_interval(
                held_out_artifact,
                STRATEGY_C,
                "false_positive_rate",
            ),
            "decision_rate_uncertain": _proportion_interval(
                held_out_artifact,
                STRATEGY_C,
                "decision_rate_uncertain",
            ),
        },
    }

    limitations: list[str] = []
    if status == "fail":
        limitations.append(
            "Pre-registered pass rule not satisfied; retain conservative stack."
        )
    if not _unlabeled_blocks_pass(strategy_c):
        limitations.append(
            "Strategy C reported unlabeled_candidate_reuse; headline metrics "
            "are not data-sufficient for a positive semantic claim."
        )

    return {
        "artifact_schema_version": GATE_ARTIFACT_SCHEMA,
        "protocol_id": config.get("protocol_id", "P4-SEMVALID"),
        "config_version": config.get("config_version"),
        "config_sha256": config_sha256 or held_out_artifact.get("config_sha256"),
        "status": status,
        "gate_status": gate_status,
        "measurement_environment": measurement_environment,
        "headline_held_out_artifact": held_out_artifact.get("artifact_path"),
        "evaluation_split": evaluation_split,
        "requirement_checks": checks,
        "denominators": denominators,
        "confidence_intervals": confidence_intervals,
        "conservative_stack_retained": status != "pass",
        "semantic_claim_supported": status == "pass",
        "limitations": limitations,
    }


def write_gate_scoring_evidence(
    output_path: Path,
    *,
    config_path: Path,
    gate_path: Path | None = None,
    held_out_artifact_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("protocol config must be a JSON object")
    resolved_gate_path = gate_path or resolve_held_out_gate_path(
        config,
        repo_root=root,
    )
    gate = load_held_out_gate(resolved_gate_path)
    config_sha256 = _sha256_file(config_path)

    held_out_path = held_out_artifact_path
    if held_out_path is None:
        reference = config.get("held_out_headline_artifact")
        if isinstance(reference, str) and reference.strip():
            held_out_path = root / reference
    held_out_payload: dict[str, Any] | None = None
    held_out_path_record: str | None = None
    if held_out_path is not None and held_out_path.is_file():
        held_out_payload = json.loads(held_out_path.read_text(encoding="utf-8"))
        if not isinstance(held_out_payload, dict):
            raise ValueError("held-out artifact must be a JSON object")
        try:
            held_out_path_record = held_out_path.relative_to(root).as_posix()
        except ValueError:
            held_out_path_record = held_out_path.as_posix()
        held_out_payload = dict(held_out_payload)
        held_out_payload["artifact_path"] = held_out_path_record

    deferred_reference = config.get("held_out_deferred_artifact")
    deferred_path_record: str | None = None
    deferred_sha256: str | None = None
    if isinstance(deferred_reference, str) and deferred_reference.strip():
        deferred_path = root / deferred_reference
        if deferred_path.is_file():
            deferred_sha256 = _sha256_file(deferred_path)
            deferred_path_record = deferred_reference

    score = score_p4_pre_registered_gate(
        config,
        gate=gate,
        held_out_artifact=held_out_payload,
        config_sha256=config_sha256,
    )
    try:
        config_path_record = config_path.relative_to(root).as_posix()
    except ValueError:
        config_path_record = str(config_path.as_posix())
    payload = {
        **score,
        "config_path": config_path_record,
        "config_sha256": config_sha256,
        "gate_path": str(resolved_gate_path.relative_to(root).as_posix()),
        "gate_sha256": _sha256_file(resolved_gate_path),
        "held_out_deferred_artifact": deferred_path_record,
        "held_out_deferred_artifact_sha256": deferred_sha256,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(root),
        "git_worktree_dirty": _git_worktree_dirty(root),
    }
    if held_out_path_record is not None:
        payload["headline_held_out_artifact"] = held_out_path_record
        if held_out_path is not None and held_out_path.is_file():
            payload["headline_held_out_artifact_sha256"] = _sha256_file(
                held_out_path
            )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score the P4-SEMVALID pre-registered gate (Step 7).",
    )
    parser.add_argument(
        "--config",
        default="experiments/semantic-validity-evaluation-config-v1.json",
        help="Frozen semantic-validity protocol config path.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/evaluation/phase4-semantic-validity-gate.json",
        help="Gate scoring evidence JSON output path.",
    )
    parser.add_argument(
        "--gate",
        default=None,
        help="Override held-out gate JSON path (default: config reference).",
    )
    parser.add_argument(
        "--held-out-artifact",
        default=None,
        help="Override held-out comparison artifact path (default: config).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = _repo_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    gate_path = Path(args.gate) if args.gate else None
    if gate_path is not None and not gate_path.is_absolute():
        gate_path = root / gate_path
    held_out_path = (
        Path(args.held_out_artifact) if args.held_out_artifact else None
    )
    if held_out_path is not None and not held_out_path.is_absolute():
        held_out_path = root / held_out_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    write_gate_scoring_evidence(
        output_path,
        config_path=config_path,
        gate_path=gate_path,
        held_out_artifact_path=held_out_path,
        repo_root=root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
