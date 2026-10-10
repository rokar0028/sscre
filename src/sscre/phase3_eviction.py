"""Phase 3 pattern-aware eviction selection and replay."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sscre.baseline import (
    compatibility_cache_cost_kwargs_from_config,
    run_compatibility_cache_baseline,
)
from sscre.benchmark import load_benchmark_jsonl
from sscre.evaluate import (
    _git_commit,
    _git_worktree_dirty,
    _load_adaptive_threshold_map,
    _load_config,
    _config_sha256,
    _validate_split,
)
from sscre.freshness_evaluation import (
    DEFAULT_REPLAY_ANCHOR_TIME,
    FreshnessReplayClock,
    freshness_experiment_from_mapping,
)
from sscre.freshness_metrics import compatibility_report_to_policy_metrics

DEFAULT_ENTRY_CAP_GRID = (1, 2, 4, 8, 16, 32)
DEFAULT_MAX_BYTES = 100_000_000


def _run_arm(
    records: list,
    *,
    config: dict[str, Any],
    threshold: float | dict[str, float],
    entry_cap: int,
    eviction_strategy: str,
    split: str,
) -> dict[str, object]:
    experiment = freshness_experiment_from_mapping(config)
    if experiment is None:
        raise ValueError("configuration must include freshness_experiment")
    conservative = next(
        policy
        for policy in experiment.policy_matrix
        if policy.name == "conservative"
    )
    report = run_compatibility_cache_baseline(
        records,
        threshold=threshold,
        top_k=int(config["embedding_top_k"]),
        freshness_replay_clock=FreshnessReplayClock.from_policy_spec(
            conservative,
            DEFAULT_REPLAY_ANCHOR_TIME,
        ),
        max_entries=entry_cap,
        max_bytes=DEFAULT_MAX_BYTES,
        eviction_strategy=eviction_strategy,
        dataset_version=str(config["dataset_version"]),
        **compatibility_cache_cost_kwargs_from_config(config),
    )
    metrics = compatibility_report_to_policy_metrics(
        records,
        report,
        policy=conservative,
    )
    storage = report.policy_storage_snapshot
    return {
        "split": split,
        "entry_cap": entry_cap,
        "eviction_strategy": eviction_strategy,
        "policy": conservative.to_dict(),
        "metrics": metrics,
        "hit_rate": report.hit_rate,
        "safe_reuse_coverage": report.safe_reuse_coverage,
        "false_positive_rate": report.false_positive_rate,
        "stale_exposure_rate": metrics["stale_exposure_rate"],
        "dynamic_reuse_served_rate": metrics["dynamic_reuse_served_rate"],
        "eviction_count": storage.get("eviction_count", 0),
        "entries": storage.get("entries_before_cleanup", 0),
        "total_bytes": storage.get("total_bytes_before_cleanup", 0),
    }


def select_development_eviction_policy(
    records: list,
    *,
    config: dict[str, Any],
    threshold: float | dict[str, float],
    entry_cap_grid: tuple[int, ...] = DEFAULT_ENTRY_CAP_GRID,
) -> dict[str, object]:
    if not entry_cap_grid or any(cap <= 0 for cap in entry_cap_grid):
        raise ValueError("entry cap grid must contain positive integers")
    reference_arms = [
        _run_arm(
            records,
            config=config,
            threshold=threshold,
            entry_cap=entry_cap,
            eviction_strategy="lru",
            split="development",
        )
        for entry_cap in entry_cap_grid
    ]
    selected_cap = next(
        (
            int(arm["entry_cap"])
            for arm in reference_arms
            if int(arm["eviction_count"]) >= 1
        ),
        None,
    )
    if selected_cap is None:
        raise ValueError("entry cap grid produced no reference eviction")
    reference = next(
        arm for arm in reference_arms if arm["entry_cap"] == selected_cap
    )
    candidate = _run_arm(
        records,
        config=config,
        threshold=threshold,
        entry_cap=selected_cap,
        eviction_strategy="pattern",
        split="development",
    )
    candidate_safe = (
        float(candidate["stale_exposure_rate"]) <= 0.0
        and float(candidate["false_positive_rate"]) <= 0.0
        and float(candidate["dynamic_reuse_served_rate"]) <= 0.0
    )
    return {
        "schema_version": "phase3-pattern-eviction-1.0",
        "dataset_version": config["dataset_version"],
        "config_version": config["config_version"],
        "config_sha256": _config_sha256("experiments/evaluation_config.json"),
        "selection_split": "development",
        "selection_rule": (
            "smallest entry cap with reference eviction; maximize safe reuse "
            "under stale, false-positive, and dynamic-reuse constraints"
        ),
        "entry_cap_grid": list(entry_cap_grid),
        "selected_entry_cap": selected_cap,
        "eviction_strategy": "pattern",
        "policy": candidate["policy"],
        "reference_arm": reference,
        "candidate_arm": candidate,
        "constraint_satisfied": candidate_safe,
        "development_arms": reference_arms,
        "git_commit": _git_commit(),
        "git_worktree_dirty": _git_worktree_dirty(),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select or replay Phase 3 pattern-aware eviction."
    )
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--split", choices=("development", "held-out"), default="development")
    parser.add_argument("--output", required=True)
    parser.add_argument("--policy-output")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--adaptive-threshold-map", required=True)
    parser.add_argument("--selected-policy")
    parser.add_argument(
        "--entry-cap-grid",
        default="1,2,4,8,16,32",
        help="Comma-separated development entry-cap grid.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        benchmark_path = Path(args.benchmark)
        records = load_benchmark_jsonl(
            benchmark_path,
            require_final_review=args.production or args.split == "held-out",
        )
        config = _load_config(args.config)
        _validate_split(
            benchmark_path,
            args.split,
            config["dataset_version"],
            records,
            production=args.production,
        )
        threshold_map = _load_adaptive_threshold_map(args.adaptive_threshold_map)
        if args.split == "development":
            caps = tuple(
                int(value.strip())
                for value in args.entry_cap_grid.split(",")
                if value.strip()
            )
            payload = select_development_eviction_policy(
                records,
                config=config,
                threshold=threshold_map,
                entry_cap_grid=caps,
            )
        else:
            if not args.selected_policy:
                raise ValueError("--selected-policy is required for held-out replay")
            selected = json.loads(
                Path(args.selected_policy).read_text(encoding="utf-8")
            )
            if not isinstance(selected, dict):
                raise ValueError("selected policy artifact must be an object")
            selected_cap = selected.get("selected_entry_cap")
            if not isinstance(selected_cap, int) or selected_cap <= 0:
                raise ValueError("selected policy has an invalid entry cap")
            payload = {
                "schema_version": "phase3-pattern-eviction-1.0",
                "dataset_version": config["dataset_version"],
                "config_version": config["config_version"],
                "config_sha256": _config_sha256("experiments/evaluation_config.json"),
                "selection_split": "development",
                "evaluation_split": "held-out",
                "selected_entry_cap": selected_cap,
                "eviction_strategy": "pattern",
                "policy": selected.get("policy"),
                "reference_arm": _run_arm(
                    records,
                    config=config,
                    threshold=threshold_map,
                    entry_cap=selected_cap,
                    eviction_strategy="lru",
                    split="held-out",
                ),
                "candidate_arm": _run_arm(
                    records,
                    config=config,
                    threshold=threshold_map,
                    entry_cap=selected_cap,
                    eviction_strategy="pattern",
                    split="held-out",
                ),
                "git_commit": _git_commit(),
                "git_worktree_dirty": _git_worktree_dirty(),
                "execution_timestamp": datetime.now().astimezone().isoformat(),
            }
            candidate = payload["candidate_arm"]
            reference = payload["reference_arm"]
            payload["constraint_satisfied"] = (
                float(candidate["stale_exposure_rate"]) <= 0.0
                and float(candidate["false_positive_rate"]) <= 0.0
                and float(candidate["dynamic_reuse_served_rate"]) <= 0.0
                and (
                    float(candidate["hit_rate"]) > float(reference["hit_rate"])
                    or float(candidate["safe_reuse_coverage"])
                    > float(reference["safe_reuse_coverage"])
                )
            )
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if args.policy_output and args.split == "development":
            policy_path = Path(args.policy_output)
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(
                json.dumps(
                    {
                        "schema_version": payload["schema_version"],
                        "dataset_version": payload["dataset_version"],
                        "config_version": payload["config_version"],
                        "config_sha256": payload["config_sha256"],
                        "selection_split": "development",
                        "selected_entry_cap": payload["selected_entry_cap"],
                        "eviction_strategy": payload["eviction_strategy"],
                        "policy": payload["policy"],
                        "constraint_satisfied": payload["constraint_satisfied"],
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"pattern eviction failed: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
