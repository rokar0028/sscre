"""Assemble Phase 3 paper-artifact previews from recorded JSON outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_METRIC_FIELDS = (
    "hit_rate",
    "false_positive_rate",
    "estimated_cost_usd",
    "p50_latency_ms",
    "p95_latency_ms",
)


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"artifact must be a JSON object: {path}")
    return payload


def _row(
    label: str,
    payload: dict[str, Any],
    *,
    source: str,
    split: str,
    status: str = "measured",
) -> dict[str, Any]:
    return {
        "label": label,
        "source": source,
        "evaluation_split": split,
        "status": status,
        **{field: payload.get(field) for field in _METRIC_FIELDS},
    }


def build_artifacts(
    *,
    output_dir: Path,
    development_comparison: Path,
    threshold_map: Path,
    adaptive_held_out: Path,
    eviction_held_out: Path,
    frozen_held_out_comparison: Path,
    frozen_held_out_pareto: Path,
) -> None:
    development = _read(development_comparison)
    adaptive = _read(adaptive_held_out)
    eviction = _read(eviction_held_out)
    frozen = _read(frozen_held_out_comparison)
    frozen_pareto = _read(frozen_held_out_pareto)
    thresholds = _read(threshold_map)

    frozen_baselines = frozen.get("baselines", {})
    development_baselines = development.get("baselines", {})
    if not isinstance(frozen_baselines, dict) or not isinstance(
        development_baselines, dict
    ):
        raise ValueError("comparison artifacts must contain baselines")

    rows = [
        _row(
            "Strategy A — no cache",
            frozen_baselines["no-cache"],
            source=str(frozen_held_out_comparison),
            split="held-out",
        ),
        _row(
            "Strategy B — embedding cache",
            frozen_baselines["embedding-cache"],
            source=str(frozen_held_out_comparison),
            split="held-out",
        ),
        _row(
            "Strategy C — global 0.95",
            frozen_baselines["compatibility-cache"],
            source=str(frozen_held_out_comparison),
            split="held-out",
        ),
        _row(
            "Feature 1 — adaptive thresholds",
            adaptive,
            source=str(adaptive_held_out),
            split="held-out",
        ),
        _row(
            "Feature 2 — pattern eviction (candidate)",
            eviction["candidate_arm"],
            source=str(eviction_held_out),
            split="held-out",
            status="failed_pass_criterion",
        ),
    ]
    no_cache_cost = rows[0]["estimated_cost_usd"]
    for row in rows:
        cost = row["estimated_cost_usd"]
        row["estimated_cost_savings_vs_no_cache"] = (
            no_cache_cost - cost
            if isinstance(no_cache_cost, (int, float))
            and isinstance(cost, (int, float))
            else None
        )

    threshold_domains = thresholds.get("selection", {}).get("domains", {})
    threshold_curves = {
        "source": str(threshold_map),
        "selection_split": "development",
        "domains": {
            domain: {
                "pair_count": details.get("pair_count"),
                "selected_threshold": details.get("selected_threshold"),
                "points": details.get("reports", []),
            }
            for domain, details in threshold_domains.items()
        },
    }
    ablations = {
        "evaluation_split": "held-out",
        "rows": [
            {"label": "C @ global 0.95", "source": str(frozen_held_out_comparison), "status": "measured"},
            {"label": "Feature 1 only", "source": str(adaptive_held_out), "status": "measured"},
            {"label": "Feature 2 only", "source": str(eviction_held_out), "status": "measured_failed"},
            {
                "label": "Feature 1 + Feature 2",
                "source": str(adaptive_held_out),
                "status": "same_as_feature_1_feature_2_deferred",
                "note": "Feature 2 failed its pre-registered pass criterion and is not retained.",
            },
            {
                "label": "Strategy D",
                "source": "docs/phase-3/PHASE3_FEATURE_3_EVIDENCE.md",
                "status": "deferred_trigger_not_met",
            },
        ],
    }
    manifest = {
        "schema_version": "phase3-paper-artifacts-1.0",
        "status": "preview_before_final_held_out_run",
        "dataset_version": development.get("dataset_version"),
        "config_version": development.get("config_version"),
        "measurement_environment": "synthetic_replay",
        "statistics": {
            "bootstrap_seed": 42,
            "bootstrap_iterations": 1000,
            "confidence_level": 0.95,
        },
        "sources": {
            "development_comparison": str(development_comparison),
            "threshold_map": str(threshold_map),
            "adaptive_held_out": str(adaptive_held_out),
            "eviction_held_out": str(eviction_held_out),
            "frozen_held_out_comparison": str(frozen_held_out_comparison),
            "frozen_held_out_pareto": str(frozen_held_out_pareto),
        },
        "deferred": [
            "final single held-out comparison",
            "Strategy D validator",
            "Feature 2 pattern eviction in shipped stack",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "phase3-results-preview.json": {"status": "preview", "rows": rows},
        "phase3-ablations.json": ablations,
        "phase3-domain-threshold-curves.json": threshold_curves,
        "phase3-pareto-reference.json": {
            "status": "frozen_reference_baseline_before_final_stack_run",
            "source": str(frozen_held_out_pareto),
            "evaluation_split": frozen_pareto.get("evaluation_split", "held-out"),
            "data": frozen_pareto,
        },
        "phase3-paper-artifact-manifest.json": manifest,
    }
    for name, payload in outputs.items():
        (output_dir / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--development-comparison", required=True, type=Path)
    parser.add_argument("--threshold-map", required=True, type=Path)
    parser.add_argument("--adaptive-held-out", required=True, type=Path)
    parser.add_argument("--eviction-held-out", required=True, type=Path)
    parser.add_argument("--frozen-held-out-comparison", required=True, type=Path)
    parser.add_argument("--frozen-held-out-pareto", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        build_artifacts(**vars(args))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
