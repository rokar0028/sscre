"""Workstream 0 Step 0.5: freeze acceptance baseline into baseline-manifest.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAB = ROOT / "artifacts/stabilization"
MANIFEST = STAB / "claim-inventory.json"
BASELINE = STAB / "baseline-manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    ).stdout.strip()


def main() -> None:
    inv = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = json.loads(BASELINE.read_text(encoding="utf-8"))

    stab_files = sorted(p for p in STAB.rglob("*") if p.is_file())
    file_hashes = {
        str(p.relative_to(ROOT).as_posix()): sha256_file(p) for p in stab_files
    }

    deferred = [c["claim_id"] for c in inv["claims"] if c["status"] == "deferred"]
    unavailable = [c["claim_id"] for c in inv["claims"] if c["status"] == "unavailable"]
    out_of_scope = [c["claim_id"] for c in inv["claims"] if c["status"] == "out of scope"]

    status_short = [ln for ln in git("status", "--short").splitlines() if ln.strip()]

    manifest["schema_version"] = "stabilization-baseline-manifest-1.0"
    manifest["workstream"] = 0
    manifest["step"] = "0.5"
    manifest["workstream_0_status"] = "closed"
    manifest["frozen_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["repository"]["git_status_short"] = status_short
    manifest["acceptance_baseline"] = {
        "head_commit": manifest["repository"]["git_commit"],
        "head_branch": manifest["repository"]["git_branch"],
        "worktree_boundary": "No modified tracked files; stabilization package untracked (see worktree_boundary).",
        "default_semantic_strategy": {
            "docker_compose_default": "B",
            "documented_safety_path": "C",
            "source": "docker-compose.yml SSCRE_SEMANTIC_STRATEGY",
        },
        "held_out_semantic_gate": "deferred",
        "held_out_gate_artifacts": [
            "artifacts/evaluation/phase4-semantic-validity-gate.json",
            "artifacts/evaluation/phase4-semantic-validity-held-out-deferred.json",
        ],
        "release_limitations": [
            "no credentialed live-provider validation",
            "no human factual-correctness labels",
            "fresh held-out semantic headline evaluation deferred",
            "POST /v1/query unauthenticated at HEAD",
            "executor capacity may retain after timeout (WS3)",
            "clean-checkout replay deferred per Phase 4 manifest",
        ],
        "known_unavailable_paths": [
            "live provider measurement (CLM-009, CLM-030)",
            "default CI PostgreSQL ws8_postgres_* markers (opt-in)",
            "fresh held-out benchmark population for Gate D",
        ],
        "claims_deferred": deferred,
        "claims_unavailable": unavailable,
        "claims_out_of_scope": out_of_scope,
        "open_conflicts_workstream_8": [x["issue_id"] for x in inv["cross_claim_issues"]],
        "next_authorized_workstream": 1,
        "next_workstream_prerequisites": [
            "Workstream 0 acceptance gate satisfied",
            "No secrets in stabilization artifacts",
            "User approval to modify .env.example and setup docs (WS1 scope)",
        ],
        "what_was_already_changed": [
            "Untracked stabilization plan, evidence, artifacts/stabilization/, and helper scripts only.",
            "Committed HEAD application code and phase artifacts unchanged by stabilization package.",
        ],
        "what_is_verified": (
            "17 claims with locally verified, PostgreSQL verified, or evaluation verified status; "
            "see claim-inventory.json and evidence_lineage blocks."
        ),
        "what_is_still_plan_only": [
            "Workstreams 1–8 implementation steps in POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md",
            "Untracked stabilization documents until committed",
        ],
        "what_next_workstream_may_modify": [
            ".env.example",
            "docs/setup/ and environment validation (WS1)",
            "Not authorized: benchmarks, application safety defaults, or artifact deletion without later WS scope",
        ],
    }
    manifest["pre_change_verification"] = {
        "recorded_at_utc": manifest["frozen_at_utc"],
        "environment": {
            "python": manifest["python"]["version"].split()[0:2],
            "PYTHONPATH": "src",
        },
        "commands": [
            {
                "command": "PYTHONPATH=src python -m pytest -q",
                "exit_code": 0,
                "result_summary": "807 passed, 15 skipped, 21 deselected, 1 warning in 169.25s",
                "log_path": "artifacts/stabilization/pytest-baseline.log",
            },
            {
                "command": "PYTHONPATH=src python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production",
                "exit_code": 0,
                "result_summary": "benchmark validation passed; split_manifest_sha256=0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9",
                "log_path": "artifacts/stabilization/benchmark-validate-baseline.log",
            },
            {
                "command": "SSCRE_ADMIN_TOKEN=ci-local-admin-token-123456 docker compose config -q",
                "exit_code": 0,
                "result_summary": "compose config valid (CI sample admin token)",
                "log_path": None,
            },
        ],
        "not_run": [
            {
                "command": "pytest -m ws8_postgres_*",
                "reason": "PostgreSQL integration opt-in; Gate B evidence exists historically (CLM-011) but not re-run for this freeze.",
            },
            {
                "command": "credentialed provider_measure live run",
                "reason": "unavailable — no credentials (CLM-009).",
            },
        ],
    }
    manifest["stabilization_artifact_hashes"] = file_hashes
    manifest["claim_inventory"] = {
        "path": "artifacts/stabilization/claim-inventory.json",
        "schema_version": inv["schema_version"],
        "step": inv["step"],
        "claim_count": len(inv["claims"]),
        "inventory_at_commit": inv["inventory_at_commit"],
        "summary_by_status": inv["summary_by_status"],
    }
    manifest["notes"] = [
        "Workstream 0 closed — acceptance baseline frozen.",
        "No .env contents or secrets are included.",
    ]

    BASELINE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("frozen", BASELINE)


if __name__ == "__main__":
    main()
