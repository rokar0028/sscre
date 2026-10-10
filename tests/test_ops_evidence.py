"""Default-suite coverage for the WS8 operational evidence package."""

from __future__ import annotations

import json
from pathlib import Path

from sscre.ops_evidence import (
    DEFAULT_BOTTLENECK_ARTIFACT,
    DEFAULT_LOAD_ARTIFACT,
    DEFAULT_OUTPUT,
    KIND,
    LIMITATION,
    PROTOCOL_ID,
    main,
    package_operational_verification,
)
from sscre.serialization import validate_redacted_report_payload

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_summarizes_load_without_request_rows() -> None:
    payload = package_operational_verification(repo_root=REPO_ROOT)
    assert payload["kind"] == KIND
    assert payload["protocol_id"] == PROTOCOL_ID
    assert payload["git_commit"]
    assert payload["environment"]["database_mode"] == "postgres"
    assert payload["environment"]["postgresql_version"]
    assert payload["configuration"]["process_count"] == 1
    assert payload["configuration"]["worker_count"] == 1
    passes = payload["protocols"]["ws8-pg-load-v1"]["passes"]["exact_cache"]
    assert [item["mode"] for item in passes] == ["cold", "warm", "cold", "warm"]
    for item in passes:
        assert "results" not in item
        assert set(item["latency_ms"]) >= {"p50", "p95", "p99"}
        assert "throughput_requests_per_second" in item
        assert "evictions_delta" in item["storage"]
    bottleneck = payload["protocols"]["ws8-pg-load-v1"]["bottleneck"]
    assert bottleneck["first_measured_bottleneck"] == "not_reached"
    assert bottleneck["result_class"] == "observation"
    assert bottleneck["optimization_decision"] == "none"


def test_package_records_protocols_and_limitations() -> None:
    payload = package_operational_verification(repo_root=REPO_ROOT)
    protocols = payload["protocols"]
    assert protocols["ws8-failure-recovery-v1"]["status"] == "measured_simulated"
    assert (
        protocols["ws8-failure-recovery-v1"]["live_container_restart"]["status"]
        == "skipped"
    )
    multiprocess = protocols["ws8-multiprocess-dup-v1"]
    assert multiprocess["duplicate_generation_prevented"] is False
    assert multiprocess["duplicate_insert_prevented"] is True
    assert multiprocess["provider_generations"] == {"min": 2, "max": 2}
    assert "production capacity" in payload["limitation"].lower()
    assert "production capacity" in LIMITATION.lower()
    assert "universal production capacity or SLA" in payload["unsupported_claims"]
    skipped_items = {item["item"] for item in payload["skipped_or_unavailable"]}
    assert "live_container_restart" in skipped_items
    assert "real_provider_latency" in skipped_items


def test_package_matches_source_load_summaries() -> None:
    payload = package_operational_verification(repo_root=REPO_ROOT)
    raw = json.loads((REPO_ROOT / DEFAULT_LOAD_ARTIFACT).read_text(encoding="utf-8"))
    packaged = payload["protocols"]["ws8-pg-load-v1"]["passes"]["exact_cache"]
    for packaged_pass, raw_pass in zip(
        packaged, raw["comparison"]["exact_cache"], strict=True
    ):
        for field, value in packaged_pass.items():
            assert raw_pass[field] == value
        assert "results" in raw_pass


def test_package_and_checked_in_artifact_are_credential_free() -> None:
    payload = package_operational_verification(repo_root=REPO_ROOT)
    validate_redacted_report_payload(payload)
    serialized = json.dumps(payload)
    for fragment in (
        "postgresql://",
        "postgres://",
        "SSCRE_DATABASE_URL",
        "POSTGRES_PASSWORD",
    ):
        assert fragment not in serialized
    artifact_path = REPO_ROOT / DEFAULT_OUTPUT
    assert artifact_path.is_file()
    saved = json.loads(artifact_path.read_text(encoding="utf-8"))
    validate_redacted_report_payload(saved)
    saved_copy = dict(saved)
    saved_copy.pop("packaged_at", None)
    assert saved_copy == payload
    assert "packaged_at" in saved


def test_handoff_docs_do_not_conflate_ws8_scopes() -> None:
    """Step 9: parent/limitations docs must not treat lite, WS8, and Phase 4 as one claim."""
    phase2 = (
        REPO_ROOT / "docs/phase-2/PHASE_2_IMPLEMENTATION_PLAN.md"
    ).read_text(encoding="utf-8")
    assert "[WORKSTREAM_8_EVIDENCE.md]" in phase2
    assert "[WORKSTREAM_8_OPS_LITE_EVIDENCE.md]" in phase2
    assert "full WS8 load/concurrency still open" not in phase2
    limitations = (
        REPO_ROOT / "docs/reference/SSCRE_EVALUATION_LIMITATIONS.md"
    ).read_text(encoding="utf-8")
    assert "WORKSTREAM_8_EVIDENCE.md" in limitations
    assert "WORKSTREAM_8_OPS_LITE_EVIDENCE.md" in limitations
    scale = (REPO_ROOT / "docs/phase-4/PHASE4_SCALE_EVIDENCE.md").read_text(
        encoding="utf-8"
    )
    assert "in-memory" in scale.lower()
    assert "WORKSTREAM_8_EVIDENCE.md" in scale


def test_ops_evidence_cli_writes_output(tmp_path: Path) -> None:
    output = tmp_path / "ws8-ops.json"
    assert (
        main(
            [
                "--load-artifact",
                str(REPO_ROOT / DEFAULT_LOAD_ARTIFACT),
                "--bottleneck-artifact",
                str(REPO_ROOT / DEFAULT_BOTTLENECK_ARTIFACT),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["kind"] == KIND
    assert saved["protocols"]["ws8-pg-load-v1"]["bottleneck"][
        "first_measured_bottleneck"
    ] == "not_reached"
    validate_redacted_report_payload(saved)
