"""Tests for P4 held-out gate enforcement and deferred evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.evaluate import main as evaluate_main
from sscre.semantic_validity_held_out import (
    DEFERRED_ARTIFACT_SCHEMA,
    HELD_OUT_GATE_READY_STATUS,
    build_held_out_deferred_payload,
    load_held_out_gate,
    validate_p4_held_out_headline_run,
    write_held_out_deferred_evidence,
)


def test_load_held_out_gate_from_repo() -> None:
    gate = load_held_out_gate(
        Path("benchmarks/semantic-validity-held-out-gate.json")
    )
    assert gate["status"] == "held-out-deferred"
    assert gate["step_6_headline_evaluation"]["status"] == "deferred"


def test_p4_held_out_run_blocked_on_development_benchmark() -> None:
    config = json.loads(
        Path("experiments/semantic-validity-evaluation-config-v1.json").read_text(
            encoding="utf-8"
        )
    )
    with pytest.raises(ValueError, match="development.jsonl"):
        validate_p4_held_out_headline_run(
            config,
            split="held-out",
            benchmark_path=Path("benchmarks/development.jsonl"),
        )


def test_p4_held_out_deferred_gate_blocks_other_benchmark_paths() -> None:
    config = {"protocol_id": "P4-SEMVALID"}
    gate = load_held_out_gate(
        Path("benchmarks/semantic-validity-held-out-gate.json")
    )
    with pytest.raises(ValueError, match="held-out-deferred"):
        validate_p4_held_out_headline_run(
            config,
            split="held-out",
            benchmark_path=Path("benchmarks/some-future-held-out.jsonl"),
            gate=gate,
            repo_root=Path(__file__).resolve().parents[1],
        )


def test_p4_held_out_run_blocked_on_contaminated_split() -> None:
    config = json.loads(
        Path("experiments/semantic-validity-evaluation-config-v1.json").read_text(
            encoding="utf-8"
        )
    )
    gate = load_held_out_gate(
        Path("benchmarks/semantic-validity-held-out-gate.json")
    )
    with pytest.raises(ValueError, match="forbidden"):
        validate_p4_held_out_headline_run(
            config,
            split="held-out",
            benchmark_path=Path("benchmarks/held_out_test.jsonl"),
            gate=gate,
        )


def test_p4_held_out_allowed_only_when_gate_ready_and_path_matches(
    tmp_path: Path,
) -> None:
    config = {"protocol_id": "P4-SEMVALID"}
    fresh_benchmark = tmp_path / "fresh-held-out.jsonl"
    fresh_benchmark.write_text("", encoding="utf-8")
    gate = {
        "status": HELD_OUT_GATE_READY_STATUS,
        "fresh_held_out_benchmark_path": str(fresh_benchmark),
    }
    validate_p4_held_out_headline_run(
        config,
        split="held-out",
        benchmark_path=fresh_benchmark,
        gate=gate,
        repo_root=tmp_path,
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_p4_held_out_headline_run(
            config,
            split="held-out",
            benchmark_path=tmp_path / "other.jsonl",
            gate=gate,
            repo_root=tmp_path,
        )


def test_evaluate_cli_blocks_p4_held_out_on_contaminated_split(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "held-out.json"
    status = evaluate_main(
        [
            "--benchmark",
            str(Path("benchmarks/held_out_test.jsonl").resolve()),
            "--config",
            str(Path("experiments/semantic-validity-evaluation-config-v1.json").resolve()),
            "--baseline",
            "exact-cache",
            "--split",
            "held-out",
            "--production",
            "--output",
            str(output_path),
        ]
    )
    assert status != 0
    assert not output_path.exists()


def test_write_held_out_deferred_evidence(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    config_path = repo / "experiments/semantic-validity-evaluation-config-v1.json"
    gate_path = repo / "benchmarks/semantic-validity-held-out-gate.json"
    output_path = tmp_path / "deferred.json"
    payload = write_held_out_deferred_evidence(
        output_path,
        config_path=config_path,
        gate_path=gate_path,
        repo_root=repo,
    )
    assert payload["artifact_schema_version"] == DEFERRED_ARTIFACT_SCHEMA
    assert payload["status"] == "deferred"
    assert payload["gate_status"] == "held-out-deferred"
    assert payload["measurement_environment"] == "not_executed"
    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk["status"] == "deferred"


def test_build_deferred_payload_includes_development_artifact_reference() -> None:
    repo = Path(__file__).resolve().parents[1]
    config_path = repo / "experiments/semantic-validity-evaluation-config-v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    gate = load_held_out_gate(
        repo / "benchmarks/semantic-validity-held-out-gate.json"
    )
    payload = build_held_out_deferred_payload(
        config=config,
        config_path=config_path,
        gate=gate,
        gate_path=repo / "benchmarks/semantic-validity-held-out-gate.json",
        repo_root=repo,
    )
    assert "phase4-semantic-validity-development.json" in payload[
        "development_threshold_artifact"
    ]
    assert payload.get("development_threshold_artifact_sha256")
    assert payload.get("development_threshold_artifact_config_sha256")
