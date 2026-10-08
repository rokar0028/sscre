"""Assign Phase 4 split IDs and unique source_group values before merge."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from sscre.benchmark import BenchmarkRecord, BenchmarkValidationError, load_benchmark_jsonl
from sscre.benchmark_build import write_jsonl
from sscre.benchmark_splits import (
    is_near_duplicate_pair,
    normalized_pair_key,
    pair_fingerprint,
    validate_cross_split_leakage,
)

REPO = Path(__file__).resolve().parents[3]
DEFAULT_BENCHMARK_DIR = REPO / "benchmarks"
DEFAULT_CANDIDATES = REPO / "benchmarks/candidates/cacheeval_batch_01_reviewed.jsonl"
SPLIT_SEED = 20261008
HELD_NEW_TARGET = 204  # 11 baseline + 204 = 215 held-out


def _unique_source_group(record: BenchmarkRecord) -> str:
    group = record.source_group or ""
    if group == "cacheeval_v1:filtered":
        return f"hand_reviewed_v2:cacheeval_batch01:{record.id}"
    if group == "hand_reviewed_v2:phase3_batch1_gaps":
        return f"hand_reviewed_v2:phase3_batch1_gaps:{record.id}"
    return group or f"hand_reviewed_v2:{record.id}"


def _apply_source_groups(records: list[BenchmarkRecord]) -> list[BenchmarkRecord]:
    out: list[BenchmarkRecord] = []
    for record in records:
        updated = record.model_copy(update={"source_group": _unique_source_group(record)})
        out.append(updated)
    return out


def _stratum(record: BenchmarkRecord) -> tuple[str, str, bool]:
    return (
        record.coverage_category or "unknown",
        record.compatibility_label or "unknown",
        bool(record.reusable),
    )


def _can_add_to_held(
    candidate: BenchmarkRecord,
    development: list[BenchmarkRecord],
    held_out: list[BenchmarkRecord],
) -> bool:
    dev_fingerprints = {pair_fingerprint(record) for record in development}
    dev_ordered = {normalized_pair_key(record) for record in development}
    dev_groups = {record.source_group for record in development if record.source_group}
    held_fingerprints = {pair_fingerprint(record) for record in held_out}

    fingerprint = pair_fingerprint(candidate)
    if fingerprint in dev_fingerprints or fingerprint in held_fingerprints:
        return False

    ordered = normalized_pair_key(candidate)
    if candidate.directionality == "ordered" and (ordered[1], ordered[0]) in dev_ordered:
        return False

    if candidate.source_group and candidate.source_group in dev_groups:
        return False

    for dev_record in development:
        if is_near_duplicate_pair(candidate, dev_record):
            return False
    for held_record in held_out:
        if is_near_duplicate_pair(candidate, held_record):
            return False
    return True


def _leakage_clusters(records: list[BenchmarkRecord]) -> list[list[BenchmarkRecord]]:
    """Cluster rows that must stay on the same split (fingerprint or near-duplicate)."""
    parent = {record.id: record.id for record in records}
    by_id = {record.id: record for record in records}

    def find(record_id: str) -> str:
        while parent[record_id] != record_id:
            parent[record_id] = parent[parent[record_id]]
            record_id = parent[record_id]
        return record_id

    def union(left_id: str, right_id: str) -> None:
        root_left = find(left_id)
        root_right = find(right_id)
        if root_left != root_right:
            parent[root_right] = root_left

    for left in records:
        for right in records:
            if left.id >= right.id:
                continue
            if pair_fingerprint(left) == pair_fingerprint(right):
                union(left.id, right.id)
                continue
            if is_near_duplicate_pair(left, right):
                union(left.id, right.id)

    clusters: dict[str, list[BenchmarkRecord]] = defaultdict(list)
    for record in records:
        clusters[find(record.id)].append(record)
    return list(clusters.values())


def _assign_with_leakage(
    baseline_dev: list[BenchmarkRecord],
    baseline_held: list[BenchmarkRecord],
    new_records: list[BenchmarkRecord],
    *,
    held_target: int,
    rng: random.Random,
) -> tuple[list[str], list[str]]:
    development = list(baseline_dev)
    held_out = list(baseline_held)
    groups = _leakage_clusters(new_records)
    rng.shuffle(groups)

    held_new: list[str] = []
    dev_new: list[str] = []

    def held_count() -> int:
        return len(held_new)

    def try_move_group_to_held(group: list[BenchmarkRecord]) -> bool:
        if held_count() + len(group) > held_target:
            return False
        for record in group:
            if not _can_add_to_held(record, development, held_out):
                return False
        for record in group:
            held_out.append(record)
            held_new.append(record.id)
        return True

    # Category seeds: pick one smallest eligible group per category first.
    by_category: dict[str, list[list[BenchmarkRecord]]] = defaultdict(list)
    for group in groups:
        cat = group[0].coverage_category or "unknown"
        by_category[cat].append(group)
    for cat in sorted(by_category):
        if held_count() >= held_target:
            break
        eligible = sorted(by_category[cat], key=len)
        for group in eligible:
            if group[0].id in held_new or group[0].id in dev_new:
                continue
            if try_move_group_to_held(group):
                break

    pending = [group for group in groups if group[0].id not in held_new and group[0].id not in dev_new]
    rng.shuffle(pending)
    for group in sorted(pending, key=len, reverse=True):
        if group[0].id in held_new or group[0].id in dev_new:
            continue
        if held_count() < held_target and try_move_group_to_held(group):
            continue
        for record in group:
            development.append(record)
            dev_new.append(record.id)

    if len(held_new) != held_target:
        raise BenchmarkValidationError(
            f"held assignment produced {len(held_new)} ids, expected {held_target}; "
            "try adjusting held_target or seed"
        )
    if len(dev_new) != len(new_records) - held_target:
        raise BenchmarkValidationError("development assignment count mismatch")
    validate_cross_split_leakage(development, held_out)
    return sorted(dev_new), sorted(held_new)


def assign_phase4_splits(
    *,
    benchmark_dir: Path,
    candidates_path: Path,
    dataset_version: str,
    dry_run: bool = False,
) -> dict:
    manifest_path = benchmark_dir / "split_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    baseline_dev = list(manifest["development"]["record_ids"])
    baseline_held = list(manifest["held_out_test"]["record_ids"])
    baseline_ids = set(baseline_dev) | set(baseline_held)

    candidates = _apply_source_groups(load_benchmark_jsonl(candidates_path))
    new_records = [r for r in candidates if r.id not in baseline_ids]
    if len(new_records) != 583:
        raise BenchmarkValidationError(
            f"expected 583 new candidate rows, found {len(new_records)}"
        )

    baseline_records = load_benchmark_jsonl(benchmark_dir / "reviewed_query_pairs.jsonl")
    baseline_dev_records = [r for r in baseline_records if r.id in baseline_dev]
    baseline_held_records = [r for r in baseline_records if r.id in baseline_held]

    rng = random.Random(SPLIT_SEED)
    new_dev_ids, new_held_ids = _assign_with_leakage(
        baseline_dev_records,
        baseline_held_records,
        new_records,
        held_target=HELD_NEW_TARGET,
        rng=rng,
    )

    dev_ids = sorted(baseline_dev + new_dev_ids)
    held_ids = sorted(baseline_held + new_held_ids)

    if not dry_run:
        write_jsonl(candidates_path, candidates)
        manifest["dataset_version"] = dataset_version
        manifest["development"]["record_ids"] = dev_ids
        manifest["held_out_test"]["record_ids"] = held_ids
        manifest["development"].pop("sha256", None)
        manifest["held_out_test"].pop("sha256", None)
        manifest["source_dataset"].pop("sha256", None)
        manifest["source_dataset"]["record_count"] = 32 + len(new_records)
        manifest.pop("frozen_at", None)
        manifest.pop("leakage_validation", None)
        manifest.pop("coverage_summary", None)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "dataset_version": dataset_version,
        "split_seed": SPLIT_SEED,
        "development_total": len(dev_ids),
        "held_out_total": len(held_ids),
        "new_development": len(new_dev_ids),
        "new_held_out": len(new_held_ids),
        "source_group_unique_per_row": True,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-dir", type=Path, default=DEFAULT_BENCHMARK_DIR)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument(
        "--dataset-version",
        default="reviewed-query-pairs-2.0",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = assign_phase4_splits(
        benchmark_dir=args.benchmark_dir,
        candidates_path=args.candidates,
        dataset_version=args.dataset_version,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
