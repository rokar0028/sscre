"""Read-only Phase 2 remediation artifact inventory (Step 1 baseline)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sscre.benchmark_splits import file_sha256  # noqa: E402

MANIFEST_PATH = ROOT / "benchmarks" / "split_manifest.json"
CONFIG_PATH = ROOT / "experiments" / "evaluation_config.json"

# Documented 2026-10-10 held-out package regen; stale vs current checkout manifest.
STALE_REGEN_MANIFEST = (
    "68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51"
)

EVALUATION_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("artifacts/evaluation/workstream5-development-sweep.json", "ws5"),
    ("artifacts/evaluation/workstream5-held-out-comparison.json", "ws5"),
    ("artifacts/evaluation/workstream5-held-out-pareto.json", "ws5"),
    ("artifacts/evaluation/workstream3-development.json", "ws3"),
    ("artifacts/evaluation/workstream6-development-freshness.json", "ws6"),
    ("artifacts/evaluation/workstream6-held-out-freshness.json", "ws6"),
    ("artifacts/evaluation/workstream6-invalidation.json", "ws6"),
    ("artifacts/evaluation/workstream7-quality-analysis.json", "ws7"),
    ("artifacts/evaluation/workstream9-dashboard.json", "ws9"),
    ("artifacts/evaluation/workstream4-real-provider-unavailable.json", "ws4"),
    ("artifacts/evaluation/workstream4-provider-comparison.json", "ws4"),
    ("artifacts/operations/workstream8-operational-verification.json", "ws8"),
)


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def _manifest_from_payload(payload: dict[str, Any]) -> str | None:
    benchmark = payload.get("benchmark_artifact")
    if isinstance(benchmark, dict):
        manifest = benchmark.get("split_manifest_sha256")
        if isinstance(manifest, str) and manifest:
            return manifest
    manifest = payload.get("split_manifest_sha256")
    if isinstance(manifest, str) and manifest:
        return manifest
    primary = payload.get("primary_evaluation_identity")
    if isinstance(primary, dict):
        manifest = primary.get("split_manifest_sha256")
        if isinstance(manifest, str) and manifest:
            return manifest
    return None


def _provenance(payload: dict[str, Any]) -> dict[str, Any]:
    generation = payload.get("generation")
    git_commit = payload.get("git_commit")
    if git_commit is None and isinstance(generation, dict):
        git_commit = generation.get("git_commit")
    timestamp = payload.get("execution_timestamp")
    if timestamp is None and isinstance(generation, dict):
        timestamp = generation.get("generated_at")
    return {
        "git_commit": git_commit,
        "timestamp": timestamp,
        "measurement_environment": payload.get("measurement_environment"),
        "dataset_version": payload.get("dataset_version"),
        "evaluation_split": payload.get("evaluation_split") or payload.get("split"),
        "status": payload.get("status"),
    }


def _classify(
    *,
    workstream: str,
    rel_path: str,
    manifest: str | None,
    current_manifest: str,
    payload: dict[str, Any],
) -> str:
    if workstream == "ws4":
        if payload.get("status") == "unavailable":
            return "unavailable"
        if payload.get("dataset_version") == "reviewed-query-pairs-1.1":
            return "not_comparable"
    if workstream == "ws8":
        return "out_of_scope_manifest"
    if manifest is None:
        return "unrecorded"
    if manifest == current_manifest:
        return "current"
    if manifest == STALE_REGEN_MANIFEST:
        return "stale"
    return "historical"


def build_inventory() -> dict[str, Any]:
    current_manifest = file_sha256(MANIFEST_PATH)
    rows: list[dict[str, Any]] = []
    for rel_path, workstream in EVALUATION_ARTIFACTS:
        path = ROOT / rel_path
        row: dict[str, Any] = {
            "path": rel_path.replace("\\", "/"),
            "workstream": workstream,
            "present": path.is_file(),
        }
        if not path.is_file():
            row["lineage_status"] = "missing"
            rows.append(row)
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = _manifest_from_payload(payload)
        row.update(
            {
                "file_sha256": file_sha256(path),
                "split_manifest_sha256": manifest,
                "lineage_status": _classify(
                    workstream=workstream,
                    rel_path=rel_path,
                    manifest=manifest,
                    current_manifest=current_manifest,
                    payload=payload,
                ),
                "provenance": _provenance(payload),
            }
        )
        rows.append(row)

    return {
        "repo_root": str(ROOT),
        "git_head": _git_head(),
        "benchmarks_split_manifest_sha256": current_manifest,
        "experiments_evaluation_config_sha256": file_sha256(CONFIG_PATH),
        "stale_regen_manifest_reference": STALE_REGEN_MANIFEST,
        "artifacts": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full inventory as JSON.",
    )
    args = parser.parse_args(argv)
    inventory = build_inventory()
    if args.json:
        print(json.dumps(inventory, indent=2, sort_keys=True))
        return 0

    print(f"git_head={inventory['git_head']}")
    print(f"split_manifest_sha256={inventory['benchmarks_split_manifest_sha256']}")
    print(f"evaluation_config_sha256={inventory['experiments_evaluation_config_sha256']}")
    for row in inventory["artifacts"]:
        manifest = row.get("split_manifest_sha256") or "not_recorded"
        print(
            f"{row['path']}\t{row['lineage_status']}\tmanifest={manifest}\t"
            f"present={row['present']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
