"""Package Workstream 8 operational verification evidence.

Reads the bounded PostgreSQL load artifact and first-bottleneck sidecar,
merges recorded protocol outcomes, and writes a credential-free summary.
Does not re-run live PostgreSQL experiments.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sscre.serialization import validate_redacted_report_payload

KIND = "workstream8-operational-verification"
SCHEMA_VERSION = "ws8-ops-1.0"
PROTOCOL_ID = "ws8-operational-verification-v1"
DEFAULT_LOAD_ARTIFACT = Path("artifacts/operations/workstream8-pg-load-v1.json")
DEFAULT_BOTTLENECK_ARTIFACT = Path(
    "artifacts/operations/workstream8-bottleneck-v1.json"
)
DEFAULT_OUTPUT = Path(
    "artifacts/operations/workstream8-operational-verification.json"
)
LIMITATION = (
    "Bounded local PostgreSQL operational verification for declared WS8 "
    "protocols. Not a production capacity, SLA, multi-host, multi-region, "
    "or managed-PostgreSQL guarantee."
)
_SENSITIVE_FRAGMENTS = (
    "postgresql://",
    "postgres://",
    "SSCRE_DATABASE_URL",
    "POSTGRES_PASSWORD",
)
_PASS_FIELDS = (
    "cache_hits",
    "cache_misses",
    "cache_mode",
    "concurrency",
    "elapsed_seconds",
    "errors",
    "generated_requests",
    "latency_ms",
    "mode",
    "reasons",
    "request_count",
    "sources",
    "storage",
    "synthetic_provider_data",
    "throughput_requests_per_second",
    "warmup_error_rate",
    "warmup_requests",
    "workload_labels",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _summarize_pass(item: Mapping[str, Any]) -> dict[str, Any]:
    return {field: item[field] for field in _PASS_FIELDS if field in item}


def _summarize_load(report: Mapping[str, Any]) -> dict[str, Any]:
    comparison = report.get("comparison") or {}
    if not isinstance(comparison, Mapping):
        raise ValueError("load artifact comparison must be an object")
    return {
        protocol_id: [_summarize_pass(item) for item in items]
        for protocol_id, items in comparison.items()
    }


def recorded_protocol_results() -> dict[str, Any]:
    """Outcomes recorded from Steps 2–5. Not recomputed from live PostgreSQL."""
    return {
        "ws8-failure-recovery-v1": {
            "status": "measured_simulated",
            "process_count": 1,
            "worker_count": 1,
            "concurrency": 1,
            "event_classes": [
                "simulated_drop",
                "simulated_repository_failure",
            ],
            "scenarios": [
                {
                    "scenario_id": "FR-lookup-drop",
                    "event_class": "simulated_drop",
                    "injection_point": "lookup",
                    "http_status": 503,
                    "cache_hit": False,
                    "request_id_present": True,
                },
                {
                    "scenario_id": "FR-lookup-simulated-failure",
                    "event_class": "simulated_repository_failure",
                    "injection_point": "lookup",
                    "http_status": 503,
                    "cache_hit": False,
                },
                {
                    "scenario_id": "FR-gen-persist",
                    "event_class": "simulated_drop",
                    "injection_point": "insert_and_evict_after_generation",
                    "http_status": 200,
                    "source": "generated",
                    "persisted": False,
                },
                {
                    "scenario_id": "FR-insert",
                    "event_class": "simulated_repository_failure",
                    "injection_point": "insert",
                    "http_status": 200,
                    "source": "generated",
                    "persisted": False,
                },
                {
                    "scenario_id": "FR-cleanup",
                    "event_class": "simulated_drop",
                    "injection_point": "cleanup_expired",
                    "cleanup_raised": True,
                    "expired_row_remained": True,
                },
                {
                    "scenario_id": "FR-recovery",
                    "event_class": "simulated_drop",
                    "injection_point": "lookup_fail_once_then_restore",
                    "failed_http_status": 503,
                    "recovered_http_status": 200,
                    "recovered_source": "cache",
                    "expired_not_served": True,
                    "disallowed_not_served": True,
                    "generation_failure_does_not_persist": True,
                    "validation_and_admin_auth_preserved": True,
                },
            ],
            "live_container_restart": {
                "status": "skipped",
                "event_class": "container_restart",
                "gate": "SSCRE_WS8_LIVE_POSTGRES_RESTART",
                "reason": "opt-in environment variable unset during packaging",
            },
            "limitations": [
                "Simulated connection drop and repository failure are not a "
                "live PostgreSQL process or container restart.",
                "Live container restart remains unmeasured in this package.",
            ],
        },
        "ws8-multiprocess-dup-v1": {
            "status": "measured",
            "measured_on": "2026-10-10",
            "process_count": 2,
            "worker_count": 2,
            "concurrency": 2,
            "run_count": 3,
            "provider_generations": {"min": 2, "max": 2},
            "insert_success": {"min": 1, "max": 1},
            "insert_conflict": {"min": 1, "max": 1},
            "insert_error": 0,
            "final_row_count": 1,
            "duplicate_generation_prevented": False,
            "duplicate_insert_prevented": True,
            "coordination": "in_process_lock_only",
            "limitations": [
                "Both processes generate. PostgreSQL UNIQUE accepts one insert "
                "and rejects the other. No distributed generation lock exists.",
                "Not a multi-host or multi-worker production guarantee.",
            ],
        },
        "ws8-contention-v1": {
            "status": "measured",
            "measured_on": "2026-10-10",
            "process_count": 1,
            "worker_count": 1,
            "workloads": [
                {
                    "workload_id": "CT-dup-key",
                    "threads": 8,
                    "insert_success": 1,
                    "duplicate_conflict": 7,
                    "surviving_rows": 1,
                },
                {
                    "workload_id": "CT-mixed-rw",
                    "threads": 8,
                    "lookup_hits": 4,
                    "inserts": 4,
                },
                {
                    "workload_id": "CT-cleanup-race",
                    "threads": 4,
                    "fresh_rows_retained": True,
                    "stale_rows_removed": True,
                },
                {
                    "workload_id": "CT-evict-cap",
                    "threads": 8,
                    "entry_window": 8,
                    "byte_window": 10000,
                    "cap_held": True,
                    "row_count_matches_storage_stats": True,
                },
            ],
            "expired_and_disallowed_cannot_win_lookup": True,
            "error_classes_separated": [
                "duplicate_conflict",
                "database_error",
                "validation_error",
            ],
            "limitations": [
                "Eviction and cleanup delete only the run's query hashes. "
                "The 2026-10-10 measurement used a relative cap window before "
                "that guard. Not a production eviction-capacity claim.",
            ],
        },
    }


def _skipped_and_unavailable() -> list[dict[str, str]]:
    return [
        {
            "item": "live_container_restart",
            "protocol_id": "ws8-failure-recovery-v1",
            "reason": "SSCRE_WS8_LIVE_POSTGRES_RESTART unset; opt-in test skipped",
        },
        {
            "item": "repository_database_span",
            "protocol_id": "ws8-pg-load-v1",
            "reason": "not instrumented on the load path",
        },
        {
            "item": "embedding_span",
            "protocol_id": "ws8-pg-load-v1",
            "reason": "not instrumented on the load path",
        },
        {
            "item": "real_provider_latency",
            "protocol_id": "ws8-pg-load-v1",
            "reason": "synthetic LoadTestLLMClient only; latency 0 ms",
        },
        {
            "item": "default_suite_live_postgres",
            "protocol_id": PROTOCOL_ID,
            "reason": (
                "database URL environment unset in the recorded default-suite "
                "run; opt-in WS8 markers remain deselected"
            ),
        },
        {
            "item": "scale_1k_to_100k_q_per_day",
            "protocol_id": "ws8-pg-load-v1",
            "reason": "excluded; requires a separate approved protocol",
        },
        {
            "item": "multi_host_coordination",
            "protocol_id": "ws8-multiprocess-dup-v1",
            "reason": "not tested; in-process lock only",
        },
    ]


def _regeneration_commands() -> list[str]:
    return [
        (
            "python -m pytest -q -m ws8_postgres_failure_recovery "
            "tests/test_postgres_failure_recovery.py "
            "tests/test_postgres_failure_closed.py"
        ),
        (
            "python -m pytest -q -m ws8_postgres_multiprocess "
            "tests/test_postgres_multiprocess_duplicate.py"
        ),
        (
            "python -m pytest -q -m ws8_postgres_contention "
            "tests/test_postgres_contention.py"
        ),
        "python -m pytest -q -m ws8_postgres_load tests/test_postgres_pg_load.py",
        (
            "python -m sscre.load_test "
            "--config experiments/workstream8_pg_load_v1.json "
            "--output artifacts/operations/workstream8-pg-load-v1.json"
        ),
        (
            "python -m sscre.ops_evidence "
            "--output artifacts/operations/workstream8-operational-verification.json"
        ),
        "python -m pytest -q",
    ]


def _reject_sensitive_text(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload)
    for fragment in _SENSITIVE_FRAGMENTS:
        if fragment in serialized:
            raise ValueError(f"operational artifact must not contain {fragment!r}")


def package_operational_verification(
    load_path: Path | None = None,
    bottleneck_path: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    load_file = root / DEFAULT_LOAD_ARTIFACT if load_path is None else load_path
    bottleneck_file = (
        root / DEFAULT_BOTTLENECK_ARTIFACT
        if bottleneck_path is None
        else bottleneck_path
    )
    report = _load_json(load_file)
    bottleneck = _load_json(bottleneck_file)
    if report.get("protocol_id") != "ws8-pg-load-v1":
        raise ValueError("load artifact protocol_id must be ws8-pg-load-v1")
    if bottleneck.get("protocol_id") != "ws8-pg-load-v1":
        raise ValueError("bottleneck artifact protocol_id must be ws8-pg-load-v1")
    environment = dict(report.get("environment") or {})
    payload = {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "limitation": LIMITATION,
        "git_commit": environment.get("git_commit"),
        "measured_at": environment.get("measured_at"),
        "environment": environment,
        "configuration": {
            "repository": report.get("repository"),
            "strategies": report.get("strategies"),
            "cache_policy": report.get("cache_policy"),
            "process_count": report.get("process_count"),
            "worker_count": report.get("worker_count"),
        },
        "source_artifacts": {
            "load": DEFAULT_LOAD_ARTIFACT.as_posix(),
            "bottleneck": DEFAULT_BOTTLENECK_ARTIFACT.as_posix(),
            "load_config": "experiments/workstream8_pg_load_v1.json",
        },
        "protocols": {
            **recorded_protocol_results(),
            "ws8-pg-load-v1": {
                "status": "measured",
                "measured_on": "2026-10-10",
                "process_count": report.get("process_count"),
                "worker_count": report.get("worker_count"),
                "concurrency": 4,
                "warmup_requests": 8,
                "request_count": 32,
                "stopped_reason": report.get("stopped_reason"),
                "limitation": report.get("limitation"),
                "passes": _summarize_load(report),
                "bottleneck": bottleneck,
                "limitations": [
                    "Bounded local result. Not a production capacity or SLA "
                    "guarantee.",
                    "Synthetic provider latency is 0 ms. Wrapper overhead is "
                    "not an actionable bottleneck.",
                ],
            },
        },
        "skipped_or_unavailable": _skipped_and_unavailable(),
        "unsupported_claims": [
            "universal production capacity or SLA",
            "1K-100K queries/day",
            "multi-host or distributed-cache coordination",
            "live process or container restart during write",
            "duplicate generation prevention across processes",
            "real-provider cost or latency",
            "Kubernetes, cloud failover, multi-region, or managed PostgreSQL",
        ],
        "regeneration_commands": _regeneration_commands(),
        "human_evidence": "docs/phase-2/WORKSTREAM_8_EVIDENCE.md",
    }
    validate_redacted_report_payload(payload)
    _reject_sensitive_text(payload)
    return payload


def write_operational_verification(
    output_path: Path,
    payload: Mapping[str, Any] | None = None,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    document = (
        dict(payload)
        if payload is not None
        else package_operational_verification(repo_root=repo_root)
    )
    document["packaged_at"] = datetime.now(timezone.utc).isoformat()
    validate_redacted_report_payload(document)
    _reject_sensitive_text(document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load-artifact", type=Path, default=None)
    parser.add_argument("--bottleneck-artifact", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    root = _repo_root()
    payload = package_operational_verification(
        args.load_artifact,
        args.bottleneck_artifact,
        repo_root=root,
    )
    output = args.output or (root / DEFAULT_OUTPUT)
    write_operational_verification(output, payload, repo_root=root)
    print(f"Wrote operational verification to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
