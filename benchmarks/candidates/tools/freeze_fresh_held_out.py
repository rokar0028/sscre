"""Step 4: freeze fresh held-out JSONL + manifest and update the P4 gate."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


def _repo_root() -> Path:
    candidates = (
        _TOOLS_DIR.parents[3],
        Path.cwd(),
    )
    for root in candidates:
        if (root / "benchmarks" / "candidates" / "fresh_held_out_reviewed.jsonl").is_file():
            return root.resolve()
    return _TOOLS_DIR.parents[3].resolve()

from sscre.benchmark import load_benchmark_jsonl  # noqa: E402
from sscre.benchmark_annotation import ANNOTATION_GUIDE_VERSION, validate_review_policy  # noqa: E402
from sscre.benchmark_splits import file_sha256  # noqa: E402
from sscre.semantic_validity_held_out import (  # noqa: E402
    HELD_OUT_GATE_READY_STATUS,
    _git_commit,
    _git_worktree_dirty,
    validate_fresh_held_out_gate_record,
)

DATASET_VERSION = "fresh-held-out-1.0"
MANIFEST_SCHEMA = "fresh-held-out-manifest-1.0"
DEFAULT_REVIEWED = Path("benchmarks/candidates/fresh_held_out_reviewed.jsonl")
DEFAULT_BENCHMARK = Path("benchmarks/fresh_held_out.jsonl")
DEFAULT_MANIFEST = Path("benchmarks/fresh_held_out_manifest.json")
DEFAULT_GATE = Path("benchmarks/semantic-validity-held-out-gate.json")


def _validate_finals(path: Path) -> list:
    records = load_benchmark_jsonl(path)
    if not records:
        raise ValueError(f"no records in {path}")
    for record in records:
        if record.review_status != "final":
            raise ValueError(f"{record.id}: expected review_status final before freeze")
    validate_review_policy(records, split="held-out")
    return records


def build_manifest(
    *,
    repo_root: Path,
    benchmark_path: Path,
    records: list,
    reviewed_path: Path,
    git_commit: str | None,
) -> dict:
    rel_benchmark = benchmark_path.relative_to(repo_root).as_posix()
    return {
        "manifest_schema_version": MANIFEST_SCHEMA,
        "dataset_version": DATASET_VERSION,
        "schema_version": "1.1",
        "annotation_guide_version": ANNOTATION_GUIDE_VERSION,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "held_out_influence": "none",
        "source_population": {
            "path": rel_benchmark,
            "sha256": file_sha256(benchmark_path),
            "record_count": len(records),
            "record_ids": [record.id for record in records],
            "id_range": {
                "first": records[0].id,
                "last": records[-1].id,
            },
        },
        "source_license": {
            "families": ["cacheeval_v1:filtered", "hand_reviewed_v2"],
            "policy_doc": "docs/phase-2/BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md",
            "note": "Rows derived from commercially filtered CacheEval; human-reviewed finals.",
        },
        "provenance": {
            "reviewed_candidates_path": reviewed_path.relative_to(repo_root).as_posix(),
            "collision_excluded_corpus": [
                "benchmarks/reviewed_query_pairs.jsonl",
                "benchmarks/development.jsonl",
                "benchmarks/held_out_test.jsonl",
            ],
        },
    }


def update_gate(
    gate_path: Path,
    *,
    manifest_path: Path,
    benchmark_path: Path,
    manifest_sha256: str,
) -> dict:
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    repo_root = _repo_root()
    rel_manifest = manifest_path.relative_to(repo_root).as_posix()
    rel_benchmark = benchmark_path.relative_to(repo_root).as_posix()
    gate["status"] = HELD_OUT_GATE_READY_STATUS
    gate["decided_at"] = datetime.now(timezone.utc).isoformat()
    gate["fresh_held_out_manifest_path"] = rel_manifest
    gate["fresh_held_out_benchmark_path"] = rel_benchmark
    gate["fresh_held_out_manifest_sha256"] = manifest_sha256
    gate["reason"] = (
        "Fresh held-out population frozen for P4-SEMVALID headline evaluation; "
        "the legacy 215-record split remains contaminated and forbidden."
    )
    authorized = gate.get("authorized_actions")
    if isinstance(authorized, dict):
        authorized["held_out_headline_gate"] = (
            "allowed_on_fresh_held_out_benchmark_when_gate_status_is_fresh-held-out-ready"
        )
    gate["next_step_to_resolve"] = (
        "Run one authorized local-embedding A/B/C evaluation on "
        f"{rel_benchmark} (WS5 Step 6) before inspecting headline metrics."
    )
    return gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed", type=Path, default=DEFAULT_REVIEWED)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    reviewed = args.reviewed if args.reviewed.is_absolute() else repo_root / args.reviewed
    benchmark = args.benchmark if args.benchmark.is_absolute() else repo_root / args.benchmark
    manifest = args.manifest if args.manifest.is_absolute() else repo_root / args.manifest
    gate_path = args.gate if args.gate.is_absolute() else repo_root / args.gate

    records = _validate_finals(reviewed)
    shutil.copyfile(reviewed, benchmark)
    commit = _git_commit(repo_root)
    manifest_payload = build_manifest(
        repo_root=repo_root,
        benchmark_path=benchmark,
        records=records,
        reviewed_path=reviewed,
        git_commit=commit,
    )
    manifest.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
    manifest_sha = file_sha256(manifest)
    gate_payload = update_gate(
        gate_path,
        manifest_path=manifest,
        benchmark_path=benchmark,
        manifest_sha256=manifest_sha,
    )
    validate_fresh_held_out_gate_record(gate_payload, repo_root=repo_root)
    gate_path.write_text(json.dumps(gate_payload, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "benchmark": str(args.benchmark),
                "manifest": str(args.manifest),
                "record_count": len(records),
                "benchmark_sha256": manifest_payload["source_population"]["sha256"],
                "manifest_sha256": manifest_sha,
                "gate_status": gate_payload["status"],
                "git_commit": commit,
                "git_worktree_dirty": _git_worktree_dirty(repo_root),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
