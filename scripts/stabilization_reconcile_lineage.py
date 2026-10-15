"""Workstream 0 Step 0.4: attach evidence lineage to claim inventory."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INV_PATH = ROOT / "artifacts/stabilization/claim-inventory.json"
AUDIT_PATH = ROOT / "artifacts/stabilization/evidence-lineage-audit.json"

LINEAGE: dict[str, dict] = {
    "CLM-001": {
        "primary_evidence": [
            "benchmarks/split_manifest.json",
            "docs/phase-2/PHASE_2_REMEDIATION_EVIDENCE.md",
        ],
        "verification_command": (
            "PYTHONPATH=src python -m sscre.benchmark_validate "
            "--benchmark-dir benchmarks --phase2 --production"
        ),
        "provenance": "committed_head",
        "measurement_environment": "frozen_benchmark",
        "contamination_flags": [],
    },
    "CLM-002": {
        "primary_evidence": ["docs/SSCRE_PLAN.md"],
        "verification_command": None,
        "provenance": "committed_head",
        "measurement_environment": "document_only",
        "contamination_flags": ["stale_documentation"],
    },
    "CLM-003": {
        "primary_evidence": [
            "benchmarks/EVALUATION_LABEL_CONTRACT_v1.md",
            "docs/SSCRE_PLAN.md",
        ],
        "verification_command": None,
        "provenance": "committed_head",
        "measurement_environment": "document_only",
        "deferral_reason": "labels not collected by design",
    },
    "CLM-004": {
        "primary_evidence": [
            "docs/phase-2/WORKSTREAM_1_EVIDENCE.md",
            "src/sscre/baseline.py",
        ],
        "verification_command": "python -m pytest -q (default suite; WS1 safety coverage)",
        "provenance": "committed_head",
        "measurement_environment": "local_unit_tests",
    },
    "CLM-005": {
        "primary_evidence": [
            "artifacts/evaluation/phase3-final-held-out-comparison.json",
        ],
        "verification_command": (
            "PYTHONPATH=src python -m sscre.evaluate "
            "--benchmark benchmarks/held_out_test.jsonl "
            "--config experiments/evaluation_config.json --baseline all "
            "--split held-out --production "
            "--output artifacts/evaluation/phase3-final-held-out-comparison.json"
        ),
        "provenance": "historical_run",
        "measurement_environment": "synthetic_fake_provider",
        "contamination_flags": ["historical", "fake_embeddings", "held_out_split_used"],
    },
    "CLM-006": {
        "primary_evidence": [
            "artifacts/evaluation/phase4-semantic-validity-gate.json",
            "artifacts/evaluation/phase4-semantic-validity-held-out-deferred.json",
        ],
        "verification_command": "P4-SEMVALID gate scorer (see semantic validity evidence)",
        "provenance": "committed_head",
        "measurement_environment": "frozen_gate_artifact",
        "contamination_flags": ["held_out_contaminated_for_fresh_gate"],
        "deferral_reason": "pre-registered deferral; no fresh population",
    },
    "CLM-007": {
        "primary_evidence": [
            "artifacts/evaluation/phase4-semantic-validity-development.json",
        ],
        "verification_command": "PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE Step 5 commands",
        "provenance": "historical_run",
        "measurement_environment": "real_local_embedding_development_only",
        "contamination_flags": ["development_split_only"],
    },
    "CLM-008": {
        "primary_evidence": ["docs/SSCRE_PLAN.md"],
        "verification_command": None,
        "provenance": "committed_head",
        "measurement_environment": "aspirational_success_criterion",
        "deferral_reason": "headline evidence deferred (CLM-006)",
        "workstream_8_resolution": "XCL-002",
    },
    "CLM-009": {
        "primary_evidence": ["artifacts/evaluation/phase4-provider-validation.json"],
        "verification_command": "python -m sscre.provider_measure (exit 0; live_opt_in_missing)",
        "provenance": "committed_head",
        "measurement_environment": "unavailable_conditional_path",
        "unavailable_reason": "no credentialed provider",
    },
    "CLM-010": {
        "primary_evidence": ["benchmarks/semantic-validity-local-embedding-gate.json"],
        "verification_command": "P4 Step 4 local embedding gate workflow",
        "provenance": "committed_head",
        "measurement_environment": "real_local_embedding",
    },
    "CLM-011": {
        "primary_evidence": [
            "artifacts/operations/workstream8-operational-verification.json",
            "artifacts/operations/workstream8-pg-load-v1.json",
        ],
        "verification_command": "pytest -m ws8_postgres_* (opt-in; WS8 evidence)",
        "provenance": "historical_run",
        "measurement_environment": "local_postgresql_bounded",
        "contamination_flags": ["dirty_worktree_at_generation"],
        "artifact_git_commit": "4997e667 per WS8 evidence (may differ from inventory HEAD)",
    },
    "CLM-012": {
        "primary_evidence": ["pyproject.toml"],
        "verification_command": "python -m pytest --collect-only -q",
        "provenance": "committed_head",
        "measurement_environment": "code_inspection",
    },
    "CLM-013": {
        "primary_evidence": ["artifacts/evaluation/phase4-scale-profile.json"],
        "verification_command": "python -m sscre.load_test per PHASE4_SCALE_EVIDENCE",
        "provenance": "historical_run",
        "measurement_environment": "synthetic_fake_provider_in_memory",
        "contamination_flags": ["synthetic", "bounded_workload"],
    },
    "CLM-014": {
        "primary_evidence": [
            "artifacts/operations/phase3-load-ladder-memory.json",
            "artifacts/operations/phase3-load-ladder-postgres.json",
        ],
        "verification_command": "phase3 load ladder per PHASE3_LOAD_EVIDENCE",
        "provenance": "historical_run",
        "measurement_environment": "synthetic_replay",
        "contamination_flags": ["synthetic"],
    },
    "CLM-015": {
        "primary_evidence": ["docs/phase-2/PHASE_2_REMEDIATION_EVIDENCE.md"],
        "provenance": "committed_head",
        "measurement_environment": "explicit_non_claim",
    },
    "CLM-016": {
        "primary_evidence": ["src/sscre/app.py"],
        "verification_command": "code inspection: POST /v1/query",
        "provenance": "committed_head",
        "measurement_environment": "code_inspection",
    },
    "CLM-017": {
        "primary_evidence": ["docs/SSCRE_PLAN.md"],
        "provenance": "committed_head",
        "measurement_environment": "document_only",
    },
    "CLM-018": {
        "primary_evidence": ["docker-compose.yml"],
        "verification_command": "docker compose config",
        "provenance": "committed_head",
        "measurement_environment": "code_inspection",
    },
    "CLM-019": {
        "primary_evidence": ["src/sscre/config.py", "docs/SSCRE_PLAN.md"],
        "provenance": "committed_head",
        "measurement_environment": "code_and_document",
        "contamination_flags": ["deployment_misalignment_with_CLM-018"],
    },
    "CLM-020": {
        "primary_evidence": ["docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md"],
        "provenance": "dirty_worktree",
        "measurement_environment": "stabilization_audit",
        "notes": "Documented gap; dedicated timeout test not run in Step 0.4.",
    },
    "CLM-021": {
        "primary_evidence": [
            "artifacts/evaluation/phase4-paper-artifact-manifest.json",
            "docs/phase-4/PHASE4_RELEASE_EVIDENCE.md",
        ],
        "verification_command": "PHASE4_RELEASE_EVIDENCE verification table",
        "provenance": "historical_run",
        "measurement_environment": "local_audit",
        "contamination_flags": [
            "dirty_worktree_at_generation",
            "clean_checkout_replay_deferred",
        ],
    },
    "CLM-022": {
        "primary_evidence": [
            "docs/phase-3/WORKSTREAM_9_EVIDENCE.md",
            "docs/phase-3/PHASE_3_IMPLEMENTATION_PLAN.md",
        ],
        "verification_command": "WS9 registry audit in WORKSTREAM_9_EVIDENCE",
        "provenance": "committed_head",
        "measurement_environment": "document_audit",
    },
    "CLM-023": {
        "primary_evidence": ["docs/phase-2/PHASE_2_REMEDIATION_EVIDENCE.md"],
        "verification_command": "remediation Step 2 regeneration commands",
        "provenance": "committed_head",
        "measurement_environment": "synthetic_replay_regeneration",
    },
    "CLM-024": {
        "primary_evidence": ["docs/phase-3/PHASE3_FEATURE_3_EVIDENCE.md"],
        "provenance": "committed_head",
        "measurement_environment": "document_only",
        "deferral_reason": "trigger not met",
    },
    "CLM-025": {
        "primary_evidence": [
            "artifacts/evaluation/phase3-embedding-storage-baseline.json",
            "docs/phase-3/PHASE3_QUANTIZATION_EVIDENCE.md",
        ],
        "provenance": "committed_head",
        "measurement_environment": "synthetic_storage_simulation",
        "deferral_reason": "dominance gate not met",
    },
    "CLM-026": {
        "primary_evidence": [
            "artifacts/evaluation/phase3-adaptive-development.json",
            "artifacts/evaluation/phase3-adaptive-held-out.json",
        ],
        "verification_command": "sscre.evaluate per PHASE3_FEATURE_1_EVIDENCE",
        "provenance": "historical_run",
        "measurement_environment": "synthetic_fake_provider",
        "contamination_flags": ["fake_embeddings"],
    },
    "CLM-027": {
        "primary_evidence": [
            "artifacts/evaluation/phase3-pattern-eviction-policy.json",
            "docs/phase-3/PHASE3_FEATURE_2_EVIDENCE.md",
        ],
        "verification_command": "sscre.phase3_eviction per PHASE3_FEATURE_2_EVIDENCE",
        "provenance": "historical_run",
        "measurement_environment": "synthetic_fake_provider",
        "deferral_reason": "failed reuse criterion",
    },
    "CLM-028": {
        "primary_evidence": [
            "benchmarks/split_manifest.json",
            "artifacts/evaluation/phase3-paper-artifact-manifest.json",
        ],
        "verification_command": (
            "PYTHONPATH=src python -m sscre.benchmark_validate "
            "--benchmark-dir benchmarks --phase2 --production"
        ),
        "provenance": "committed_head",
        "measurement_environment": "frozen_benchmark",
        "contamination_flags": ["historical_manifest_in_phase3_artifacts"],
    },
    "CLM-029": {
        "primary_evidence": [
            "artifacts/evaluation/workstream9-dashboard.json",
            "src/sscre/dashboard.py",
        ],
        "verification_command": "dashboard export per WORKSTREAM_9_EVIDENCE",
        "provenance": "committed_head",
        "measurement_environment": "synthetic_replay",
    },
    "CLM-030": {
        "primary_evidence": ["artifacts/evaluation/workstream9-dual-model-v1.json"],
        "provenance": "committed_head",
        "measurement_environment": "unavailable_conditional_path",
        "unavailable_reason": "live dual-model provider not run",
    },
    "CLM-031": {
        "primary_evidence": ["artifacts/evaluation/phase4-selected-stack-pareto.json"],
        "verification_command": "P4 Pareto replay per PHASE4_PARETO_EVIDENCE",
        "provenance": "historical_run",
        "measurement_environment": "synthetic_replay",
        "contamination_flags": ["synthetic", "protocol_reset"],
    },
    "CLM-032": {
        "primary_evidence": [
            "benchmarks/EVALUATION_LABEL_CONTRACT_v1.md",
            "src/sscre/evaluation_labels.py",
        ],
        "provenance": "committed_head",
        "measurement_environment": "code_and_contract",
    },
    "CLM-033": {
        "primary_evidence": ["docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md"],
        "provenance": "dirty_worktree",
        "measurement_environment": "plan_authoring",
    },
    "CLM-034": {
        "primary_evidence": [
            "artifacts/evaluation/phase4-semantic-validity-verification.json",
            "src/sscre/evaluation_attribution.py",
        ],
        "verification_command": "P4-SEMVALID verification / attribution tests",
        "provenance": "committed_head",
        "measurement_environment": "local_unit_tests_and_artifact",
    },
    "CLM-035": {
        "primary_evidence": [
            "docs/phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md",
            "artifacts/evaluation/phase4-semantic-validity-gate.json",
        ],
        "provenance": "committed_head",
        "measurement_environment": "process_close_with_deferred_gate",
        "deferral_reason": "headline gate deferred",
        "workstream_8_resolution": "XCL-002",
    },
}


def norm_ref(ref: str) -> list[str]:
    ref = ref.strip()
    if ref.endswith("/"):
        return [ref.rstrip("/")]
    ref = re.split(r"\s+§|\s+WS", ref)[0].strip()
    return [ref]


def check_paths(refs: list[str]) -> list[dict]:
    rows: list[dict] = []
    for ref in refs:
        for p in norm_ref(ref):
            path = ROOT / p
            if p.endswith("/") or p == "src/sscre/":
                rows.append(
                    {
                        "path": p,
                        "exists": path.is_dir(),
                        "kind": "directory" if path.is_dir() else "missing",
                    }
                )
                continue
            kind = "file" if path.is_file() else ("dir" if path.is_dir() else "missing")
            rows.append({"path": p, "exists": path.exists(), "kind": kind})
    return rows


def main() -> None:
    inv = json.loads(INV_PATH.read_text(encoding="utf-8"))
    head = inv["inventory_at_commit"]
    missing_any: list[dict] = []

    for claim in inv["claims"]:
        cid = claim["claim_id"]
        lin = dict(LINEAGE.get(cid, {}))
        paths = check_paths(claim.get("references", []))
        missing = [p for p in paths if not p["exists"]]
        if missing:
            missing_any.append({"claim_id": cid, "missing": missing})
        lin["path_checks"] = paths
        lin["referenced_paths_all_exist"] = len(missing) == 0
        lin["reconciled_at_utc"] = datetime.now(timezone.utc).isoformat()
        lin["inventory_head_commit"] = head
        claim["evidence_lineage"] = lin

    inv["step"] = "0.4"
    inv["schema_version"] = "stabilization-claim-inventory-1.1"
    inv["lineage_reconciliation"] = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "head_commit": head,
        "verified_claim_count": sum(
            1
            for c in inv["claims"]
            if c["status"]
            in {
                "locally verified",
                "PostgreSQL verified",
                "evaluation verified",
                "provider verified",
            }
        ),
        "claims_with_missing_references": missing_any,
        "contradictions_deferred_to_workstream_8": [
            x["issue_id"] for x in inv["cross_claim_issues"]
        ],
    }
    INV_PATH.write_text(json.dumps(inv, indent=2) + "\n", encoding="utf-8")

    audit = {
        "schema_version": "stabilization-evidence-lineage-audit-1.0",
        "step": "0.4",
        "head_commit": head,
        "recorded_at_utc": inv["lineage_reconciliation"]["recorded_at_utc"],
        "missing_reference_claims": missing_any,
        "all_claims_referenced_paths_exist": len(missing_any) == 0,
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"missing_reference_claims={len(missing_any)}")


if __name__ == "__main__":
    main()
