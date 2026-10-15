"""Tests for P4 held-out gate enforcement and deferred evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.evaluate import main as evaluate_main
from sscre.benchmark import load_benchmark_jsonl
from sscre.semantic_validity_held_out import (
    CONTAMINATED_HELD_OUT_BENCHMARK,
    DEFERRED_ARTIFACT_SCHEMA,
    HELD_OUT_GATE_READY_STATUS,
    build_held_out_deferred_payload,
    load_held_out_gate,
    validate_fresh_held_out_gate_record,
    validate_fresh_held_out_split_benchmark,
    validate_p4_held_out_headline_run,
    write_held_out_deferred_evidence,
)


def test_load_held_out_gate_from_repo() -> None:
    gate = load_held_out_gate(
        Path("benchmarks/semantic-validity-held-out-gate.json")
    )
    assert gate["status"] == HELD_OUT_GATE_READY_STATUS
    assert gate["fresh_held_out_benchmark_path"] == "benchmarks/fresh_held_out.jsonl"
    assert gate["fresh_held_out_manifest_path"] == "benchmarks/fresh_held_out_manifest.json"
    assert gate["step_6_headline_evaluation"]["status"] == "complete"
    assert gate["step_7_gate_scoring"]["headline_verdict"] == "pass"


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


def test_p4_held_out_ready_gate_blocks_unauthorized_benchmark_paths() -> None:
    config = {"protocol_id": "P4-SEMVALID"}
    gate = load_held_out_gate(
        Path("benchmarks/semantic-validity-held-out-gate.json")
    )
    repo_root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="does not match"):
        validate_p4_held_out_headline_run(
            config,
            split="held-out",
            benchmark_path=Path("benchmarks/some-future-held-out.jsonl"),
            gate=gate,
            repo_root=repo_root,
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


def test_fresh_held_out_split_validates_against_ws5_manifest() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    records = load_benchmark_jsonl(repo_root / "benchmarks/fresh_held_out.jsonl")
    manifest = validate_fresh_held_out_split_benchmark(
        repo_root / "benchmarks/fresh_held_out.jsonl",
        records,
        production=True,
    )
    assert manifest["dataset_version"] == "fresh-held-out-1.0"


def test_fresh_held_out_benchmark_is_explicit_not_legacy_split() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    fresh = load_benchmark_jsonl(repo_root / "benchmarks/fresh_held_out.jsonl")
    legacy = load_benchmark_jsonl(repo_root / "benchmarks/held_out_test.jsonl")
    assert len(fresh) == 100
    assert len(legacy) == 215
    assert fresh[0].id == "pair-0616"
    config = {"protocol_id": "P4-SEMVALID"}
    gate = load_held_out_gate(
        repo_root / "benchmarks/semantic-validity-held-out-gate.json",
        repo_root=repo_root,
    )
    validate_p4_held_out_headline_run(
        config,
        split="held-out",
        benchmark_path=repo_root / "benchmarks/fresh_held_out.jsonl",
        gate=gate,
        repo_root=repo_root,
    )


def test_ready_gate_cannot_authorize_contaminated_benchmark_path() -> None:
    gate = {
        "status": HELD_OUT_GATE_READY_STATUS,
        "fresh_held_out_benchmark_path": CONTAMINATED_HELD_OUT_BENCHMARK,
        "existing_held_out_split": {
            "path": CONTAMINATED_HELD_OUT_BENCHMARK,
            "classification": "contaminated_for_headline_gate",
        },
    }
    with pytest.raises(ValueError, match="contaminated"):
        validate_fresh_held_out_gate_record(gate)


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
    gate_path = tmp_path / "deferred-gate.json"
    gate_path.write_text(
        json.dumps({"status": "held-out-deferred", "reason": "test fixture"}),
        encoding="utf-8",
    )
    output_path = tmp_path / "deferred.json"
    payload = write_held_out_deferred_evidence(
        output_path,
        config_path=config_path,
        gate_path=gate_path,
        repo_root=tmp_path,
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
    gate_path = repo / "benchmarks/semantic-validity-held-out-gate.json"
    gate = {
        "status": "held-out-deferred",
        "reason": "historical fixture for deferred payload shape",
        "existing_held_out_split": load_held_out_gate(gate_path)[
            "existing_held_out_split"
        ],
    }
    payload = build_held_out_deferred_payload(
        config=config,
        config_path=config_path,
        gate=gate,
        gate_path=gate_path,
        repo_root=repo,
    )
    assert "phase4-semantic-validity-development.json" in payload[
        "development_threshold_artifact"
    ]
    assert payload.get("development_threshold_artifact_sha256")
    assert payload.get("development_threshold_artifact_config_sha256")
