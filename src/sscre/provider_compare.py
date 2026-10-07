"""Compare synthetic and real-provider measurements without mixing them."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


COMPARISON_SCHEMA_VERSION = "provider-measurement-comparison-1.0"
METRICS = (
    "request_count",
    "generation_latency_ms",
    "embedding_latency_ms",
    "total_latency_ms",
    "generation_input_tokens",
    "generation_output_tokens",
    "embedding_input_tokens",
    "estimated_cost_usd",
)


def _get(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _synthetic_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    baselines = payload.get("baselines")
    baseline = (
        payload
        if payload.get("baseline") == "compatibility-cache"
        else baselines.get("compatibility-cache", {})
        if isinstance(baselines, Mapping)
        else {}
    )
    return {
        "request_count": baseline.get("request_count"),
        "generation_latency_ms": baseline.get("average_latency_ms"),
        "embedding_latency_ms": None,
        "total_latency_ms": baseline.get("average_latency_ms"),
        "generation_input_tokens": baseline.get("input_tokens"),
        "generation_output_tokens": baseline.get("output_tokens"),
        "embedding_input_tokens": baseline.get("embedding_tokens"),
        "estimated_cost_usd": baseline.get("estimated_cost_usd"),
    }


def _real_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_count": _get(payload, "requests", "count"),
        "generation_latency_ms": _get(payload, "latency_ms", "generation"),
        "embedding_latency_ms": _get(payload, "latency_ms", "embedding"),
        "total_latency_ms": _get(payload, "latency_ms", "total"),
        "generation_input_tokens": _get(payload, "tokens", "generation_input"),
        "generation_output_tokens": _get(payload, "tokens", "generation_output"),
        "embedding_input_tokens": _get(payload, "tokens", "embedding_input"),
        "estimated_cost_usd": _get(payload, "cost_usd", "total_estimated"),
    }


def build_measurement_comparison(
    synthetic: Mapping[str, Any],
    real: Mapping[str, Any],
    *,
    synthetic_artifact: str,
    real_artifact: str,
) -> dict[str, Any]:
    synthetic_version = _get(synthetic, "dataset_version") or _get(
        synthetic, "benchmark_artifact", "dataset_version"
    )
    real_version = _get(real, "benchmark", "dataset_version")
    if synthetic_version != real_version:
        raise ValueError("synthetic and real dataset versions must match")
    synthetic_split = _get(synthetic, "evaluation_split") or _get(
        synthetic, "benchmark_artifact", "split"
    )
    real_split = _get(real, "benchmark", "split")
    if synthetic_split != real_split:
        raise ValueError("synthetic and real split names must match")

    synthetic_values = _synthetic_metrics(synthetic)
    real_values = _real_metrics(real)
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "measurement_environment": "comparison",
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_version": synthetic_version,
        "split": synthetic_split,
        "rows": [
            {
                "metric": metric,
                "synthetic": {
                    "measurement_environment": "synthetic",
                    "artifact": synthetic_artifact,
                    "value": synthetic_values[metric],
                },
                "real_provider": {
                    "measurement_environment": "real_provider",
                    "artifact": real_artifact,
                    "value": real_values[metric],
                },
            }
            for metric in METRICS
        ],
        "comparison_rules": [
            "Synthetic and real-provider values remain separate; no combined average is computed.",
            "Unavailable real-provider values remain null.",
            "Synthetic zero-cost placeholders are not real-provider costs.",
            "Generated-answer quality is not inferred from synthetic text.",
            "Compare latency and cost only when provider, endpoint origin, "
            "generation model, and embedding model match; otherwise treat "
            "differences as configuration drift, not cache behavior.",
        ],
        "limitations": (
            real.get("limitations", [])
            if real.get("status") == "unavailable"
            else []
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare synthetic and real-provider measurement artifacts"
    )
    parser.add_argument("--synthetic", required=True, type=Path)
    parser.add_argument("--real", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    synthetic = json.loads(args.synthetic.read_text(encoding="utf-8"))
    real = json.loads(args.real.read_text(encoding="utf-8"))
    payload = build_measurement_comparison(
        synthetic,
        real,
        synthetic_artifact=str(args.synthetic).replace("\\", "/"),
        real_artifact=str(args.real).replace("\\", "/"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
