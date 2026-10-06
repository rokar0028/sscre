"""Command-line entry point for benchmark evaluation."""

import argparse
from dataclasses import asdict
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sscre.baseline import (
    run_compatibility_cache_baseline,
    run_exact_cache_baseline,
    run_embedding_cache_baseline,
    run_embedding_threshold_sweep,
    run_no_cache_baseline,
    save_exact_cache_report,
    save_embedding_sweep_report,
    save_embedding_cache_report,
    save_compatibility_cache_report,
    save_no_cache_report,
)
from sscre.benchmark import load_benchmark_jsonl
from sscre import __version__

_COST_FIELDS = (
    "input_cost_per_1k_tokens",
    "output_cost_per_1k_tokens",
    "embedding_cost_per_1k_tokens",
    "cache_lookup_cost_usd",
    "preprocessing_cost_usd",
)
_SPLIT_FILENAMES = {
    "development": "development.jsonl",
    "held-out": "held_out_test.jsonl",
}
_SPLIT_MANIFEST_KEYS = {
    "development": "development",
    "held-out": "held_out_test",
}


def _load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid configuration {config_path}: {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    dataset_version = config.get("dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise ValueError("configuration requires a non-empty dataset_version")
    config_version = config.get("config_version")
    if not isinstance(config_version, str) or not config_version.strip():
        raise ValueError("configuration requires a non-empty config_version")

    for field_name in _COST_FIELDS:
        value = config.get(field_name, 0.0)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{field_name} must be a finite non-negative number")
        config[field_name] = float(value)

    thresholds = config.get("embedding_thresholds", [0.8, 0.9, 0.95])
    if (
        not isinstance(thresholds, list)
        or not thresholds
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not -1.0 <= value <= 1.0
            for value in thresholds
        )
    ):
        raise ValueError(
            "embedding_thresholds must be a non-empty list between -1 and 1"
        )
    config["embedding_thresholds"] = [float(value) for value in thresholds]

    top_k = config.get("embedding_top_k", 5)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("embedding_top_k must be a positive integer")
    config["embedding_top_k"] = top_k

    max_false_positive_rate = config.get("max_false_positive_rate", 0.0)
    if (
        isinstance(max_false_positive_rate, bool)
        or not isinstance(max_false_positive_rate, (int, float))
        or not math.isfinite(max_false_positive_rate)
        or not 0.0 <= max_false_positive_rate <= 1.0
    ):
        raise ValueError("max_false_positive_rate must be between 0 and 1")
    config["max_false_positive_rate"] = float(max_false_positive_rate)
    return config


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def _git_worktree_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def _validate_split(
    benchmark_path: Path,
    split: str,
    dataset_version: str,
    records: list,
) -> None:
    expected_filename = _SPLIT_FILENAMES[split]
    if benchmark_path.name != expected_filename:
        raise ValueError(
            f"--split {split!r} requires {expected_filename!r}"
        )

    manifest_path = benchmark_path.parent / "split_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid split manifest {manifest_path}: {exc}") from exc

    if manifest.get("dataset_version") != dataset_version:
        raise ValueError("split manifest and configuration dataset versions differ")

    split_metadata = manifest.get(_SPLIT_MANIFEST_KEYS[split])
    if not isinstance(split_metadata, dict):
        raise ValueError(f"split manifest has no {split!r} entry")

    manifest_path_value = split_metadata.get("path")
    if not isinstance(manifest_path_value, str):
        raise ValueError(f"split manifest has no path for {split!r}")
    manifest_root = manifest_path.parent.parent
    manifest_benchmark_path = (manifest_root / manifest_path_value).resolve()
    if manifest_benchmark_path != benchmark_path.resolve():
        raise ValueError(f"benchmark path does not match the {split!r} manifest entry")

    record_count = split_metadata.get("record_count")
    if record_count != len(records):
        raise ValueError(f"benchmark record count does not match the {split!r} manifest")

    data_dir = manifest_benchmark_path.parent
    full_path = data_dir / "reviewed_query_pairs.jsonl"
    other_split = "held-out" if split == "development" else "development"
    other_path = data_dir / _SPLIT_FILENAMES[other_split]
    full_ids = {record.id for record in load_benchmark_jsonl(full_path)}
    selected_ids = {record.id for record in records}
    other_ids = {
        record.id for record in load_benchmark_jsonl(other_path)
    }
    if not selected_ids <= full_ids:
        raise ValueError(f"{split!r} split contains IDs outside the reviewed dataset")
    if selected_ids & other_ids:
        raise ValueError("development and held-out split IDs overlap")
    if selected_ids | other_ids != full_ids:
        raise ValueError("development and held-out splits do not cover the reviewed dataset")
    if selected_ids | other_ids != full_ids:
        raise ValueError("development and held-out splits do not cover the reviewed dataset")


def _select_development_threshold(
    benchmark_path: Path,
    config: dict[str, Any],
) -> Any:
    development_path = benchmark_path.parent / "development.jsonl"
    development_records = load_benchmark_jsonl(development_path)
    _validate_split(
        development_path,
        "development",
        config["dataset_version"],
        development_records,
    )
    return run_embedding_threshold_sweep(
        development_records,
        dataset_version=config["dataset_version"],
        thresholds=config["embedding_thresholds"],
        top_k=config["embedding_top_k"],
        max_false_positive_rate=config["max_false_positive_rate"],
        input_cost_per_1k_tokens=config["input_cost_per_1k_tokens"],
        output_cost_per_1k_tokens=config["output_cost_per_1k_tokens"],
        embedding_cost_per_1k_tokens=config["embedding_cost_per_1k_tokens"],
        cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
        preprocessing_cost_usd=config["preprocessing_cost_usd"],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate an SSCRE benchmark.")
    parser.add_argument("--benchmark", required=True, help="Benchmark JSONL path.")
    parser.add_argument("--config", required=True, help="Evaluation JSON path.")
    parser.add_argument(
        "--baseline",
        required=True,
        choices=(
            "no-cache",
            "exact-cache",
            "embedding-cache",
            "compatibility-cache",
            "all",
        ),
        help="Baseline strategy to run.",
    )
    parser.add_argument(
        "--split",
        choices=tuple(_SPLIT_FILENAMES),
        default="development",
        help="Declared benchmark split; held-out evaluation must be explicit.",
    )
    parser.add_argument("--output", required=True, help="Output report JSON path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run evaluation and return a process exit status."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        benchmark_path = Path(args.benchmark)
        records = load_benchmark_jsonl(benchmark_path)
        config = _load_config(args.config)
        _validate_split(
            benchmark_path,
            args.split,
            config["dataset_version"],
            records,
        )
        common_options = {
            "dataset_version": config["dataset_version"],
            "input_cost_per_1k_tokens": config["input_cost_per_1k_tokens"],
            "output_cost_per_1k_tokens": config["output_cost_per_1k_tokens"],
        }
        metadata = {
            "config_version": config["config_version"],
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "software_version": __version__,
            "git_commit": _git_commit(),
            "git_worktree_dirty": _git_worktree_dirty(),
            "evaluation_split": args.split,
        }
        if args.baseline == "all":
            selection = _select_development_threshold(benchmark_path, config)
            no_cache_report = run_no_cache_baseline(records, **common_options)
            exact_cache_report = run_exact_cache_baseline(
                records,
                **common_options,
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            embedding_report = run_embedding_cache_baseline(
                records,
                **common_options,
                threshold=selection.selected_threshold,
                top_k=config["embedding_top_k"],
                embedding_cost_per_1k_tokens=config[
                    "embedding_cost_per_1k_tokens"
                ],
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            compatibility_report = run_compatibility_cache_baseline(
                records,
                **common_options,
                threshold=selection.selected_threshold,
                top_k=config["embedding_top_k"],
                embedding_cost_per_1k_tokens=config[
                    "embedding_cost_per_1k_tokens"
                ],
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            compatibility_false_positive_keys = {
                (example["id"], example["direction"])
                for example in compatibility_report.false_positive_examples
            }
            caught_embedding_false_positives = [
                example
                for example in embedding_report.false_positive_examples
                if (example["id"], example["direction"])
                not in compatibility_false_positive_keys
            ]
            payload = {
                **metadata,
                "baseline": "comparison",
                "threshold_selection": asdict(selection),
                "baselines": {
                    "no-cache": asdict(no_cache_report),
                    "exact-cache": asdict(exact_cache_report),
                    "embedding-cache": asdict(embedding_report),
                    "compatibility-cache": asdict(compatibility_report),
                },
                "failure_gallery": {
                    "embedding_only_false_positives": (
                        embedding_report.false_positive_examples
                    ),
                    "embedding_only_false_positives_caught_by_strategy_c": (
                        caught_embedding_false_positives
                    ),
                    "strategy_c_failures": compatibility_report.failure_examples,
                },
            }
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        elif args.baseline == "no-cache":
            report = run_no_cache_baseline(records, **common_options)
            save_no_cache_report(report, args.output, metadata=metadata)
        elif args.baseline == "exact-cache":
            report = run_exact_cache_baseline(
                records,
                **common_options,
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            save_exact_cache_report(report, args.output, metadata=metadata)
        elif args.baseline == "compatibility-cache":
            selection = _select_development_threshold(benchmark_path, config)
            report = run_compatibility_cache_baseline(
                records,
                **common_options,
                threshold=selection.selected_threshold,
                top_k=config["embedding_top_k"],
                embedding_cost_per_1k_tokens=config[
                    "embedding_cost_per_1k_tokens"
                ],
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            metadata.update(
                {
                    "selected_threshold": selection.selected_threshold,
                    "threshold_selection_split": "development",
                    "threshold_selection_rule": selection.selection_rule,
                }
            )
            save_compatibility_cache_report(
                report,
                args.output,
                metadata=metadata,
            )
        elif args.split == "development":
            report = run_embedding_threshold_sweep(
                records,
                **common_options,
                thresholds=config["embedding_thresholds"],
                top_k=config["embedding_top_k"],
                max_false_positive_rate=config["max_false_positive_rate"],
                embedding_cost_per_1k_tokens=config[
                    "embedding_cost_per_1k_tokens"
                ],
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            save_embedding_sweep_report(report, args.output, metadata=metadata)
        else:
            selection = _select_development_threshold(benchmark_path, config)
            report = run_embedding_cache_baseline(
                records,
                **common_options,
                threshold=selection.selected_threshold,
                top_k=config["embedding_top_k"],
                embedding_cost_per_1k_tokens=config[
                    "embedding_cost_per_1k_tokens"
                ],
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            metadata.update(
                {
                    "selected_threshold": selection.selected_threshold,
                    "threshold_selection_split": "development",
                    "threshold_selection_rule": selection.selection_rule,
                }
            )
            save_embedding_cache_report(report, args.output, metadata=metadata)
    except (OSError, ValueError, TypeError) as exc:
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
