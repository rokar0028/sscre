import json
from pathlib import Path

from sscre.evaluate import main
from sscre.serialization import (
    redact_operational_evaluation_report,
    validate_redacted_report_payload,
)

_ROOT = Path(__file__).resolve().parents[1]
_CONFIG = _ROOT / "experiments" / "evaluation_config.json"
_DEVELOPMENT = _ROOT / "benchmarks" / "development.jsonl"


def _assert_hit_rate_interval(stats: dict) -> None:
    hit_rate = stats["proportions"]["hit_rate"]
    assert hit_rate["method"] in {"wilson", "clopper_pearson", "unavailable"}
    assert hit_rate["n"] > 0


def test_compatibility_cli_attaches_statistics(tmp_path: Path) -> None:
    output_path = tmp_path / "compatibility.json"
    assert (
        main(
            [
                "--benchmark",
                str(_DEVELOPMENT),
                "--config",
                str(_CONFIG),
                "--baseline",
                "compatibility-cache",
                "--split",
                "development",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["statistics_schema_version"] == "evaluation-statistics-1.0"
    assert payload["measurement_environment"] == "synthetic_replay"
    assert "statistics" in payload
    _assert_hit_rate_interval(payload["statistics"])
    assert payload["statistics"]["label_metrics"]["sample_unit"] == "reviewed_pair"
    assert "cached_answer" in payload["statistics"]["label_metrics"]["correctness"]
    assert "winner_counts" in payload["statistics"]["label_metrics"]["preference"]
    assert "confidence_interval" not in payload
    redacted = redact_operational_evaluation_report(payload)
    validate_redacted_report_payload(redacted["statistics"])


def test_baseline_all_attaches_comparison_statistics(tmp_path: Path) -> None:
    output_path = tmp_path / "comparison.json"
    assert (
        main(
            [
                "--benchmark",
                str(_DEVELOPMENT),
                "--config",
                str(_CONFIG),
                "--baseline",
                "all",
                "--split",
                "development",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["baseline"] == "comparison"
    statistics = payload["statistics"]
    assert statistics["operating_point"]["baseline"] == "compatibility-cache"
    observed_fpr = statistics["operating_point"]["observed_false_positive_rate"]
    max_fpr = statistics["operating_point"]["max_false_positive_rate"]
    if observed_fpr is None:
        assert statistics["operating_point"][
            "observed_false_positive_rate_unavailable_reason"
        ]
        assert statistics["operating_point"]["constraint_satisfied"] is False
    else:
        assert observed_fpr <= max_fpr
        assert statistics["operating_point"]["constraint_satisfied"] is True
    assert "by_baseline" in statistics
    assert set(statistics["by_baseline"]) == {
        "no-cache",
        "exact-cache",
        "embedding-cache",
        "compatibility-cache",
    }
    companion = payload.get("freshness_policy_companion_artifacts")
    assert isinstance(companion, dict)
    assert companion.get("integration") == "reference_only"
    artifacts = companion.get("artifacts")
    assert isinstance(artifacts, dict)
    assert "development" in artifacts
    _assert_hit_rate_interval(statistics["overall"])
    _assert_hit_rate_interval(statistics["by_baseline"]["embedding-cache"])


def test_no_statistics_flag_omits_attachment(tmp_path: Path) -> None:
    output_path = tmp_path / "no-stats.json"
    assert (
        main(
            [
                "--benchmark",
                str(_DEVELOPMENT),
                "--config",
                str(_CONFIG),
                "--baseline",
                "compatibility-cache",
                "--split",
                "development",
                "--no-statistics",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "statistics" not in payload
    assert "statistics_schema_version" not in payload
