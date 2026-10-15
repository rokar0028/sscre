"""Tests for P4 pre-registered gate scoring (Step 7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.semantic_validity_gate import (
    GATE_ARTIFACT_SCHEMA,
    evaluate_pre_registered_requirements,
    score_p4_pre_registered_gate,
    write_gate_scoring_evidence,
)
from sscre.semantic_validity_held_out import (
    HELD_OUT_GATE_READY_STATUS,
    load_held_out_gate,
)


def _minimal_held_out_artifact(
    *,
    a_coverage: float,
    c_coverage: float,
    c_fpr: float | None,
    c_abstention: float,
    c_unlabeled: int = 0,
) -> dict[str, object]:
    c_report: dict[str, object] = {
        "safe_reuse_coverage": c_coverage,
        "abstention_rate": c_abstention,
        "reusable_opportunities": 100,
        "labeled_reuse_hits": 10,
        "unlabeled_candidate_reuse_hits": c_unlabeled,
    }
    if c_fpr is not None:
        c_report["false_positive_rate"] = c_fpr
    else:
        c_report["false_positive_rate_unavailable_reason"] = (
            "no_labeled_reuse_hits"
        )
    return {
        "evaluation_split": "held-out",
        "measurement_environment": "local_embedding_replay",
        "config_sha256": "abc",
        "baselines": {
            "exact-cache": {
                "safe_reuse_coverage": a_coverage,
                "reusable_opportunities": 100,
                "labeled_reuse_hits": 5,
            },
            "compatibility-cache": c_report,
        },
    }


def test_score_gate_deferred_when_held_out_gate_not_ready() -> None:
    config = {"protocol_id": "P4-SEMVALID", "config_version": "v1"}
    gate = load_held_out_gate(
        Path("benchmarks/semantic-validity-held-out-gate.json")
    )
    payload = score_p4_pre_registered_gate(config, gate=gate)
    assert payload["status"] == "deferred"
    assert payload["conservative_stack_retained"] is True
    assert payload["requirement_checks"] == []


def test_score_gate_rejects_development_split() -> None:
    config = {
        "protocol_id": "P4-SEMVALID",
        "max_false_positive_rate": 0.0,
        "max_abstention_rate": 0.5,
    }
    gate = {"status": HELD_OUT_GATE_READY_STATUS}
    artifact = _minimal_held_out_artifact(
        a_coverage=0.01,
        c_coverage=0.02,
        c_fpr=0.0,
        c_abstention=0.1,
    )
    artifact["evaluation_split"] = "development"
    with pytest.raises(ValueError, match="held-out"):
        score_p4_pre_registered_gate(
            config,
            gate=gate,
            held_out_artifact=artifact,
            config_sha256="abc",
        )


def test_requirement_checks_pass_and_fail() -> None:
    config = {
        "max_false_positive_rate": 0.0,
        "max_abstention_rate": 0.5,
    }
    passing = evaluate_pre_registered_requirements(
        config,
        strategy_a={"safe_reuse_coverage": 0.1},
        strategy_c={
            "safe_reuse_coverage": 0.2,
            "false_positive_rate": 0.0,
            "abstention_rate": 0.1,
            "unlabeled_candidate_reuse_hits": 0,
        },
    )
    assert all(check["satisfied"] for check in passing)

    failing = evaluate_pre_registered_requirements(
        config,
        strategy_a={"safe_reuse_coverage": 0.2},
        strategy_c={
            "safe_reuse_coverage": 0.2,
            "false_positive_rate": 0.1,
            "abstention_rate": 0.1,
            "unlabeled_candidate_reuse_hits": 1,
        },
    )
    assert not all(check["satisfied"] for check in failing)


def test_score_gate_pass_on_synthetic_held_out() -> None:
    config = {
        "protocol_id": "P4-SEMVALID",
        "config_version": "semantic-validity-evaluation-config-1.0",
        "max_false_positive_rate": 0.0,
        "max_abstention_rate": 0.5,
    }
    gate = {"status": HELD_OUT_GATE_READY_STATUS}
    artifact = _minimal_held_out_artifact(
        a_coverage=0.05,
        c_coverage=0.10,
        c_fpr=0.0,
        c_abstention=0.2,
    )
    payload = score_p4_pre_registered_gate(
        config,
        gate=gate,
        held_out_artifact=artifact,
        config_sha256="abc",
    )
    assert payload["status"] == "pass"
    assert payload["semantic_claim_supported"] is True
    assert payload["conservative_stack_retained"] is False


def test_write_gate_scoring_evidence_deferred(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    config_path = repo / "experiments/semantic-validity-evaluation-config-v1.json"
    gate_path = tmp_path / "deferred-gate.json"
    gate_path.write_text(
        json.dumps({"status": "held-out-deferred", "reason": "test fixture"}),
        encoding="utf-8",
    )
    output_path = tmp_path / "gate.json"
    payload = write_gate_scoring_evidence(
        output_path,
        config_path=config_path,
        gate_path=gate_path,
        repo_root=tmp_path,
    )
    assert payload["artifact_schema_version"] == GATE_ARTIFACT_SCHEMA
    assert payload["status"] == "deferred"
    on_disk = json.loads(output_path.read_text(encoding="utf-8"))
    assert on_disk["status"] == "deferred"
    assert on_disk["gate_status"] == "held-out-deferred"
