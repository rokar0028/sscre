import json
from pathlib import Path

from sscre.evaluate import main as evaluate_main
from sscre.pareto import PARETO_SCHEMA_VERSION, main


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments" / "evaluation_config.json"
DEVELOPMENT = ROOT / "benchmarks" / "development.jsonl"
HELD_OUT = ROOT / "benchmarks" / "held_out_test.jsonl"


def test_pareto_cli_regeneration_is_deterministic(tmp_path: Path) -> None:
    sweep_path = tmp_path / "development-sweep.json"
    assert (
        evaluate_main(
            [
                "--benchmark",
                str(DEVELOPMENT),
                "--config",
                str(CONFIG),
                "--baseline",
                "embedding-cache",
                "--split",
                "development",
                "--output",
                str(sweep_path),
            ]
        )
        == 0
    )

    first_path = tmp_path / "first-pareto.json"
    second_path = tmp_path / "second-pareto.json"
    arguments = [
        "--development-sweep",
        str(sweep_path),
        "--held-out-benchmark",
        str(HELD_OUT),
        "--config",
        str(CONFIG),
    ]
    assert main([*arguments, "--output", str(first_path)]) == 0
    assert main([*arguments, "--output", str(second_path)]) == 0

    first = json.loads(first_path.read_text(encoding="utf-8"))
    second = json.loads(second_path.read_text(encoding="utf-8"))
    assert first == second
    assert first["pareto_schema_version"] == PARETO_SCHEMA_VERSION
    assert first["threshold_selection_split"] == "development"
    assert len(first["points"]) == 3
    assert first["selected_threshold"] in {0.8, 0.9, 0.95}
    assert set(first["frontier_thresholds"]) == {
        "safety_vs_reuse",
        "false_positives_vs_tokens_saved",
        "cost_vs_safety",
        "latency_vs_cost",
        "reuse_vs_storage",
    }
    assert all(point["constraint"]["satisfied"] is True for point in first["points"])
