"""Research track R1 Step 1.2 — bounded provider measurement envelope."""

import json
from pathlib import Path

from sscre.r1_provider_run import (
    DEFAULT_MAX_RECORDS,
    build_r1_step12_record,
    run_r1_step12_measurement,
)


ROOT = Path(__file__).resolve().parents[1]


def test_run_r1_step12_deferred_without_live_opt_in(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SSCRE_REAL_PROVIDER_LIVE", raising=False)
    output = tmp_path / "r1.json"
    from sscre.evaluate import _load_config

    config = _load_config(ROOT / "experiments/semantic-validity-evaluation-config-v1.json")
    record = run_r1_step12_measurement(
        benchmark_path=ROOT / "benchmarks/development.jsonl",
        config_path=ROOT / "experiments/semantic-validity-evaluation-config-v1.json",
        config=config,
        max_records=2,
        gate_c_approval_path=ROOT
        / "artifacts/stabilization/r1-step12-gate-c-approval.json",
    )
    assert record["headline_population"] is False
    assert record["provider_measurement"]["status"] == "unavailable"
    assert record["provider_measurement"]["unavailable_reason"] == "live_opt_in_missing"
    assert record["measurement_protocol"]["max_records"] == 2
    encoded = json.dumps(record)
    assert "api_key" not in encoded.lower()


def test_build_r1_step12_wraps_measurement() -> None:
    record = build_r1_step12_record(
        measurement={
            "schema_version": "real-provider-measurement-1.0",
            "status": "unavailable",
            "measurement_environment": "real_provider",
            "provider_available": False,
            "unavailable_reason": "live_opt_in_missing",
            "execution_timestamp": "2026-01-01T00:00:00+00:00",
            "git_commit": None,
            "runtime_versions": {"python": "3.14.0"},
            "benchmark": {
                "path": "benchmarks/development.jsonl",
                "dataset_version": "reviewed-query-pairs-2.0",
                "split": "development",
                "record_count": 0,
            },
            "configuration": {
                "path": "experiments/evaluation_config.json",
                "config_version": "evaluation-config-1.0",
                "pricing_schedule_id": None,
            },
            "provider": None,
            "requests": {
                "count": 0,
                "generation": 0,
                "embedding": 0,
                "retries": 0,
            },
            "failures": [
                {"category": "authentication", "count": 0},
                {"category": "authorization", "count": 0},
                {"category": "malformed_response", "count": 0},
                {"category": "permanent_provider", "count": 0},
                {"category": "rate_limited", "count": 0},
                {"category": "timeout", "count": 0},
                {"category": "transient_provider", "count": 0},
                {"category": "validation", "count": 0},
            ],
            "tokens": {
                "generation_input": None,
                "generation_output": None,
                "embedding_input": None,
                "usage_sources": {},
            },
            "latency_ms": {
                "generation": None,
                "embedding": None,
                "wrapper": None,
                "total": None,
            },
            "cost_usd": {
                "generation": None,
                "embedding": None,
                "retry": None,
                "wrapper": None,
                "total_estimated": None,
                "source": "unavailable",
            },
            "redaction": {
                "raw_prompts": False,
                "raw_answers": False,
                "credentials": False,
                "provider_payloads": False,
            },
            "limitations": ["test"],
        },
        gate_c_approval={"status": "deferred", "approval_recorded": False},
        benchmark_path=ROOT / "benchmarks/development.jsonl",
        config_path=ROOT / "experiments/semantic-validity-evaluation-config-v1.json",
        population_record_count=383,
        max_records=DEFAULT_MAX_RECORDS,
    )
    assert record["fresh_evaluation_gate"]["workstream_5_headline_authorized"] is False
