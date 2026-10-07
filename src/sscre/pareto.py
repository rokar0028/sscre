"""Build deterministic Workstream 5 Pareto frontier artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sscre import __version__
from sscre.baseline import (
    run_compatibility_cache_baseline,
    run_embedding_cache_baseline,
)
from sscre.benchmark import load_benchmark_jsonl
from sscre.evaluate import _load_config, _validate_split
from sscre.storage_evaluation import build_reuse_storage_pareto_point

PARETO_SCHEMA_VERSION = "evaluation-pareto-1.0"

_PLANE_DEFINITIONS: dict[str, tuple[str, str, str, str]] = {
    "safety_vs_reuse": (
        "false_positive_rate",
        "minimize",
        "safe_reuse_coverage",
        "maximize",
    ),
    "false_positives_vs_tokens_saved": (
        "false_positive_rate",
        "minimize",
        "tokens_saved",
        "maximize",
    ),
    "cost_vs_safety": (
        "estimated_cost_usd",
        "minimize",
        "false_positive_rate",
        "minimize",
    ),
    "latency_vs_cost": (
        "p95_latency_ms",
        "minimize",
        "estimated_cost_usd",
        "minimize",
    ),
    "reuse_vs_storage": (
        "safe_reuse_coverage",
        "maximize",
        "total_bytes",
        "minimize",
    ),
}


def _metric_value(point: Mapping[str, Any], metric: str) -> float | None:
    value = point.get("metrics", {}).get(metric)
    if value is None:
        storage = point.get("storage", {})
        if isinstance(storage, Mapping):
            value = storage.get(metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _at_least_as_good(left: float, right: float, direction: str) -> bool:
    return left <= right if direction == "minimize" else left >= right


def _strictly_better(left: float, right: float, direction: str) -> bool:
    return left < right if direction == "minimize" else left > right


def dominates(
    candidate: Mapping[str, Any],
    other: Mapping[str, Any],
    *,
    x_metric: str,
    x_direction: str,
    y_metric: str,
    y_direction: str,
) -> bool:
    """Return whether candidate dominates other on one trade-off plane."""
    candidate_x = _metric_value(candidate, x_metric)
    candidate_y = _metric_value(candidate, y_metric)
    other_x = _metric_value(other, x_metric)
    other_y = _metric_value(other, y_metric)
    if None in (candidate_x, candidate_y, other_x, other_y):
        return False
    no_worse = (
        _at_least_as_good(candidate_x, other_x, x_direction)
        and _at_least_as_good(candidate_y, other_y, y_direction)
    )
    strictly_better = (
        _strictly_better(candidate_x, other_x, x_direction)
        or _strictly_better(candidate_y, other_y, y_direction)
    )
    return no_worse and strictly_better


def frontier_thresholds(
    points: Sequence[Mapping[str, Any]],
    *,
    x_metric: str,
    x_direction: str,
    y_metric: str,
    y_direction: str,
) -> list[float]:
    """Return sorted threshold values for the non-dominated points."""
    complete_points = [
        point
        for point in points
        if _metric_value(point, x_metric) is not None
        and _metric_value(point, y_metric) is not None
    ]
    frontier = [
        point
        for point in complete_points
        if not any(
            dominates(
                candidate,
                point,
                x_metric=x_metric,
                x_direction=x_direction,
                y_metric=y_metric,
                y_direction=y_direction,
            )
            for candidate in complete_points
            if candidate is not point
        )
    ]
    return sorted(float(point["threshold"]) for point in frontier)


def _report_metrics(report: Mapping[str, Any]) -> dict[str, float]:
    fields = (
        "false_positive_rate",
        "safe_reuse_coverage",
        "estimated_cost_usd",
        "p95_latency_ms",
        "tokens_saved",
    )
    metrics: dict[str, float] = {}
    for field in fields:
        value = report.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"held-out report requires numeric {field}")
        metrics[field] = float(value)
    return metrics


def build_pareto_artifact(
    points: Sequence[Mapping[str, Any]],
    *,
    dataset_version: str,
    config_version: str,
    selected_threshold: float,
    max_false_positive_rate: float,
    storage_point: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the versioned artifact from threshold-specific held-out points."""
    if not points:
        raise ValueError("at least one held-out threshold point is required")
    normalized_points: list[dict[str, Any]] = []
    for point in points:
        normalized = dict(point)
        normalized["selected"] = (
            float(normalized["threshold"]) == float(selected_threshold)
        )
        observed_fpr = normalized["metrics"]["false_positive_rate"]
        normalized["constraint"] = {
            "name": "max_false_positive_rate",
            "limit": max_false_positive_rate,
            "observed": observed_fpr,
            "satisfied": observed_fpr <= max_false_positive_rate,
        }
        if storage_point is not None:
            normalized["storage"] = dict(storage_point["storage"])
            normalized["metrics"]["total_bytes"] = float(
                storage_point["storage"]["total_bytes"]
            )
        else:
            normalized["storage"] = None
        normalized_points.append(normalized)

    frontiers: dict[str, list[float]] = {}
    for plane, (x_metric, x_direction, y_metric, y_direction) in (
        _PLANE_DEFINITIONS.items()
    ):
        frontiers[plane] = frontier_thresholds(
            normalized_points,
            x_metric=x_metric,
            x_direction=x_direction,
            y_metric=y_metric,
            y_direction=y_direction,
        )

    selected_point = next(
        (
            point
            for point in normalized_points
            if point["selected"]
        ),
        None,
    )
    if selected_point is None:
        raise ValueError("selected threshold is absent from held-out points")

    return {
        "pareto_schema_version": PARETO_SCHEMA_VERSION,
        "software_version": __version__,
        "dataset_version": dataset_version,
        "config_version": config_version,
        "evaluation_split": "held-out",
        "measurement_environment": "synthetic_replay",
        "threshold_selection_split": "development",
        "selected_threshold": selected_threshold,
        "selected_constraint": selected_point["constraint"],
        "storage_measurement_environment": (
            storage_point.get("measurement_environment")
            if storage_point is not None
            else "unavailable"
        ),
        "dominance": {
            plane: {
                "x": {"metric": definition[0], "direction": definition[1]},
                "y": {"metric": definition[2], "direction": definition[3]},
            }
            for plane, definition in _PLANE_DEFINITIONS.items()
        },
        "points": normalized_points,
        "frontier_thresholds": frontiers,
    }


def _load_development_sweep(path: Path) -> tuple[list[float], float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("baseline") != "embedding-cache-threshold-sweep":
        raise ValueError("development sweep has an unexpected baseline")
    reports = payload.get("reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("development sweep requires non-empty reports")
    thresholds = [report.get("threshold") for report in reports]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in thresholds):
        raise ValueError("development sweep thresholds must be numeric")
    selected = payload.get("selected_threshold")
    if isinstance(selected, bool) or not isinstance(selected, (int, float)):
        raise ValueError("development sweep requires selected_threshold")
    return [float(value) for value in thresholds], float(selected)


def build_from_files(
    *,
    development_sweep_path: str | Path,
    held_out_benchmark_path: str | Path,
    config_path: str | Path,
    storage_report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read checked-in artifacts and replay every development threshold held-out."""
    config = _load_config(config_path)
    benchmark_path = Path(held_out_benchmark_path)
    records = load_benchmark_jsonl(benchmark_path, require_final_review=True)
    _validate_split(
        benchmark_path,
        "held-out",
        config["dataset_version"],
        records,
        production=True,
    )
    thresholds, selected_threshold = _load_development_sweep(
        Path(development_sweep_path)
    )
    common = {
        "dataset_version": config["dataset_version"],
        "input_cost_per_1k_tokens": config["input_cost_per_1k_tokens"],
        "output_cost_per_1k_tokens": config["output_cost_per_1k_tokens"],
        "top_k": config["embedding_top_k"],
        "embedding_cost_per_1k_tokens": config["embedding_cost_per_1k_tokens"],
        "cache_lookup_cost_usd": config["cache_lookup_cost_usd"],
        "preprocessing_cost_usd": config["preprocessing_cost_usd"],
    }
    points: list[dict[str, Any]] = []
    for threshold in thresholds:
        embedding_report = run_embedding_cache_baseline(
            records, threshold=threshold, **common
        )
        compatibility_report = run_compatibility_cache_baseline(
            records, threshold=threshold, **common
        )
        metrics = _report_metrics(compatibility_report.__dict__)
        metrics["embedding_false_positive_rate"] = float(
            embedding_report.false_positive_rate
        )
        metrics["embedding_safe_reuse_coverage"] = float(
            embedding_report.safe_reuse_coverage
        )
        points.append(
            {
                "threshold": threshold,
                "metrics": metrics,
                "embedding_report": {
                    "false_positive_rate": embedding_report.false_positive_rate,
                    "safe_reuse_coverage": embedding_report.safe_reuse_coverage,
                },
            }
        )

    storage_point = None
    if storage_report_path is not None:
        storage_payload = json.loads(
            Path(storage_report_path).read_text(encoding="utf-8")
        )
        storage_point = build_reuse_storage_pareto_point(
            storage_payload,
            evaluation_config=config,
        )
    return build_pareto_artifact(
        points,
        dataset_version=config["dataset_version"],
        config_version=config["config_version"],
        selected_threshold=selected_threshold,
        max_false_positive_rate=config["max_false_positive_rate"],
        storage_point=storage_point,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-sweep", required=True)
    parser.add_argument("--held-out-benchmark", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--storage-report")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        artifact = build_from_files(
            development_sweep_path=args.development_sweep,
            held_out_benchmark_path=args.held_out_benchmark,
            config_path=args.config,
            storage_report_path=args.storage_report,
        )
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
