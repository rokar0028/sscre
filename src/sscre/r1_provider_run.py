"""Research track R1 Step 1.2 — bounded Gate C provider measurement envelope."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sscre.evaluation_protocol import apply_primary_headline_population_filter
from sscre.provider_config import RealProviderConfig
from sscre.provider_measure import (
    MEASUREMENT_SCHEMA_VERSION,
    build_live_measurement,
    build_unavailable_measurement,
    _resolve_pricing_schedule,
)
from sscre.serialization import validate_redacted_report_payload

R1_PROVIDER_SCHEMA_VERSION = "r1-step12-provider-measurement-1.0"
GATE_C_APPROVAL_SCHEMA_VERSION = "r1-step12-gate-c-approval-1.0"
DEFAULT_MAX_RECORDS = 5


def _repo_relative(path: Path) -> str:
    root = Path(__file__).resolve().parents[2]
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def gate_c_approval_from_environment() -> dict[str, Any]:
    approved = os.getenv("SSCRE_R1_GATE_C_APPROVED", "").lower() == "true"
    return {
        "schema_version": GATE_C_APPROVAL_SCHEMA_VERSION,
        "status": "approved" if approved else "deferred",
        "approval_recorded": approved,
        "quota_note": os.getenv("SSCRE_R1_GATE_C_QUOTA_NOTE"),
        "pricing_schedule_path": os.getenv("SSCRE_PROVIDER_PRICING_JSON"),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def load_gate_c_approval(path: Path | None) -> dict[str, Any]:
    if path is None:
        return gate_c_approval_from_environment()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("gate C approval file must be a JSON object")
    return payload


def build_r1_step12_record(
    *,
    measurement: dict[str, Any],
    gate_c_approval: dict[str, Any],
    benchmark_path: Path,
    config_path: Path,
    population_record_count: int,
    max_records: int | None,
) -> dict[str, Any]:
    validate_redacted_report_payload(measurement)
    return {
        "schema_version": R1_PROVIDER_SCHEMA_VERSION,
        "workstream": "R1",
        "step": "R1.2",
        "headline_population": False,
        "population_purpose": (
            "development_split_bounded_provider_measurement_not_fresh_headline"
        ),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "gate_c_approval": gate_c_approval,
        "measurement_protocol": {
            "inner_schema": MEASUREMENT_SCHEMA_VERSION,
            "benchmark_path": _repo_relative(benchmark_path),
            "config_path": _repo_relative(config_path),
            "population_record_count": population_record_count,
            "max_records": max_records,
            "live_requires": [
                "SSCRE_REAL_PROVIDER_LIVE=true",
                "SSCRE_REAL_PROVIDER=true",
                "SSCRE_PROVIDER_CREDENTIAL",
                "SSCRE_R1_GATE_C_APPROVED=true or gate_c approval file status approved",
            ],
        },
        "provider_measurement": measurement,
        "fresh_evaluation_gate": {
            "workstream_5_headline_authorized": False,
            "note": "Provider results are not semantic headline evidence until WS5 passes.",
        },
    }


def run_r1_step12_measurement(
    *,
    benchmark_path: Path,
    config_path: Path,
    config: dict[str, Any],
    max_records: int | None = DEFAULT_MAX_RECORDS,
    gate_c_approval_path: Path | None = None,
) -> dict[str, Any]:
    from sscre.benchmark import load_benchmark_jsonl

    records = load_benchmark_jsonl(benchmark_path)
    records, _ = apply_primary_headline_population_filter(records, config)
    population_count = len(records)

    gate_c = load_gate_c_approval(gate_c_approval_path)
    live_enabled = os.environ.get("SSCRE_REAL_PROVIDER_LIVE", "").lower() == "true"
    provider_config = RealProviderConfig.from_environment()

    if not live_enabled:
        reason = "live_opt_in_missing"
    elif gate_c.get("status") != "approved":
        reason = "gate_c_approval_missing"
    elif provider_config is None:
        reason = "provider_configuration_missing"
    elif not provider_config.credential_configured:
        reason = "provider_credential_missing"
    else:
        reason = None

    if reason is not None:
        measurement = build_unavailable_measurement(
            benchmark_path=benchmark_path,
            config_path=config_path,
            reason=reason,
        )
        measurement["gate_c_status"] = "deferred"
    else:
        measurement = build_live_measurement(
            benchmark_path=benchmark_path,
            config_path=config_path,
            provider_config=provider_config,
            pricing_schedule=_resolve_pricing_schedule(provider_config),
            max_records=max_records,
        )
        measurement["gate_c_status"] = "verified"

    return build_r1_step12_record(
        measurement=measurement,
        gate_c_approval=gate_c,
        benchmark_path=benchmark_path,
        config_path=config_path,
        population_record_count=population_count,
        max_records=max_records,
    )


def write_r1_step12_record(record: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
