import json

import pytest

from sscre.provider_compare import build_measurement_comparison


def _synthetic() -> dict:
    return {
        "dataset_version": "dataset-1",
        "evaluation_split": "development",
        "baselines": {
            "compatibility-cache": {
                "request_count": 2,
                "average_latency_ms": 3.0,
                "input_tokens": 10,
                "output_tokens": 20,
                "embedding_tokens": 4,
                "estimated_cost_usd": 0.0,
            }
        },
    }


def _real(status: str = "unavailable") -> dict:
    return {
        "status": status,
        "benchmark": {
            "dataset_version": "dataset-1",
            "split": "development",
        },
        "requests": {"count": 0},
        "latency_ms": {"generation": None, "embedding": None, "total": None},
        "tokens": {
            "generation_input": None,
            "generation_output": None,
            "embedding_input": None,
        },
        "cost_usd": {"total_estimated": None},
        "limitations": ["provider unavailable"],
    }


def test_comparison_keeps_environments_and_unavailable_values_separate() -> None:
    result = build_measurement_comparison(
        _synthetic(),
        _real(),
        synthetic_artifact="synthetic.json",
        real_artifact="real.json",
    )

    assert result["measurement_environment"] == "comparison"
    assert result["rows"][0]["synthetic"]["measurement_environment"] == "synthetic"
    assert result["rows"][1]["real_provider"]["value"] is None
    assert "combined average" in result["comparison_rules"][0]
    assert "0.0" not in json.dumps(result["rows"][0]["real_provider"])


def test_comparison_rejects_dataset_mismatch() -> None:
    real = _real()
    real["benchmark"]["dataset_version"] = "other"

    with pytest.raises(ValueError, match="dataset versions"):
        build_measurement_comparison(
            _synthetic(),
            real,
            synthetic_artifact="synthetic.json",
            real_artifact="real.json",
        )
