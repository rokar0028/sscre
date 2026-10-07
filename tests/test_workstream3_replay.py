"""Workstream 3 step 9: replay reviewed pairs without rewriting labels."""

from __future__ import annotations

import json
from pathlib import Path

from sscre.baseline import run_compatibility_cache_baseline, save_compatibility_cache_report
from sscre.benchmark import load_benchmark_jsonl
from sscre.evaluate import main
from sscre.evaluation_labels import (
    DISAGREEMENT_CLASSES,
    expected_compatibility_decision,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEVELOPMENT = _PROJECT_ROOT / "benchmarks" / "development.jsonl"
_CONFIG = _PROJECT_ROOT / "experiments" / "evaluation_config.json"
_FROZEN_DATASET_VERSION = "reviewed-query-pairs-1.1"
_FROZEN_THRESHOLD = 0.9


def test_development_replay_records_observed_decisions_by_pair_id() -> None:
    records = load_benchmark_jsonl(_DEVELOPMENT)
    originals = [
        (
            record.id,
            record.compatibility_label,
            record.correctness_label,
            record.preference_label,
            record.reusable,
        )
        for record in records
    ]

    report = run_compatibility_cache_baseline(
        records,
        dataset_version=_FROZEN_DATASET_VERSION,
        threshold=_FROZEN_THRESHOLD,
    )

    assert [
        (
            record.id,
            record.compatibility_label,
            record.correctness_label,
            record.preference_label,
            record.reusable,
        )
        for record in records
    ] == originals
    assert {row["id"] for row in report.observed_pair_records} == {
        record.id for record in records
    }
    assert [row["id"] for row in report.observed_pair_records] == [
        record.id for record in records
    ]
    assert all(row["direction"] == "b_to_a" for row in report.observed_pair_records)

    by_id = {record.id: record for record in records}
    for row in report.observed_pair_records:
        record = by_id[row["id"]]
        assert row["expected_compatibility"] == record.compatibility_label
        assert row["expected_decision"] == expected_compatibility_decision(record)
        assert row["observed_decision"] in {"SAFE", "UNSAFE", "UNCERTAIN"}
        assert row["evaluation_labels"]["compatibility"]["expected_decision"] == (
            row["expected_decision"]
        )
        assert row["evaluation_labels"]["compatibility"]["observed_decision"] == (
            row["observed_decision"]
        )
        assert "query_a" not in row
        assert "query_b" not in row
        if row["disagreement_class"] is not None:
            assert row["disagreement_class"] in DISAGREEMENT_CLASSES
            assert row["expected_decision"] != row["observed_decision"]
        else:
            assert row["expected_decision"] == row["observed_decision"]
        if record.correctness_label is None:
            assert row["evaluation_labels"]["correctness"]["cached_answer"] is None
            assert row["evaluation_labels"]["correctness"]["generated_answer"] is None
        if record.preference_label is None:
            assert row["evaluation_labels"]["preference"]["applicable"] is False
            assert row["evaluation_labels"]["preference"]["winner"] is None
        if row["observed_decision"] == "SAFE":
            assert row["evaluation_labels"]["correctness"]["cached_answer"] is None
        assert "confidence_interval" not in row
        assert "operating_point" not in row

    assert set(report.disagreement_class_counts) <= DISAGREEMENT_CLASSES
    assert "confidence_interval" not in report.label_sections
    assert set(report.label_sections) == {
        "compatibility",
        "correctness",
        "preference",
    }
    assert "not_collected" in report.label_sections["correctness"] or "correct" in (
        report.label_sections["correctness"]
    )
    assert "MISS" not in report.decision_counts
    for row in report.observed_pair_records:
        traces = row["candidate_traces"]
        if isinstance(traces, list):
            assert traces
            assert all(trace["cache_control_outcome"] for trace in traces)


def test_saved_replay_report_keeps_bounded_identity(tmp_path: Path) -> None:
    records = load_benchmark_jsonl(_DEVELOPMENT)
    report = run_compatibility_cache_baseline(
        records,
        dataset_version=_FROZEN_DATASET_VERSION,
        threshold=_FROZEN_THRESHOLD,
    )
    path = tmp_path / "workstream3-development.json"
    save_compatibility_cache_report(report, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    encoded = json.dumps(payload["observed_pair_records"])
    assert "query_a" not in encoded
    assert "query_b" not in encoded
    for record in records:
        assert record.query_a not in encoded
        assert record.query_b not in encoded
    assert payload["dataset_version"] == _FROZEN_DATASET_VERSION
    assert "confidence_interval" not in payload
    assert payload["observed_pair_records"][0]["id"].startswith("pair-")


def test_evaluate_cli_replays_development_without_held_out_tuning(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "workstream3-development.json"
    status = main(
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
    assert status == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["evaluation_split"] == "development"
    assert payload["threshold_selection_split"] == "development"
    assert payload["benchmark_artifact"]["dataset_version"] == _FROZEN_DATASET_VERSION
    assert payload["benchmark_artifact"]["split_record_count"] == 21
    assert len(payload["observed_pair_records"]) == 21
    assert "query_a" not in json.dumps(payload["observed_pair_records"])
    assert "confidence_interval" not in payload
    assert payload["selected_threshold"] in {0.8, 0.9, 0.95}


def test_held_out_compatibility_replay_still_selects_development_threshold(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "workstream3-held-out.json"
    status = main(
        [
            "--benchmark",
            str(_PROJECT_ROOT / "benchmarks" / "held_out_test.jsonl"),
            "--config",
            str(_CONFIG),
            "--baseline",
            "compatibility-cache",
            "--split",
            "held-out",
            "--output",
            str(output_path),
        ]
    )
    assert status == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["evaluation_split"] == "held-out"
    assert payload["threshold_selection_split"] == "development"
    assert payload["benchmark_artifact"]["split_record_count"] == 11
    assert "confidence_interval" not in payload
