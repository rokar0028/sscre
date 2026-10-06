"""Build and merge reviewed benchmark candidates into the source dataset."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from sscre.benchmark import BenchmarkRecord, BenchmarkValidationError, load_benchmark_jsonl
from sscre.benchmark_splits import (
    file_sha256,
    freeze_split_manifest,
    resolve_rebuild_split_ids,
    validate_benchmark_dataset,
)

_REDACTION_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bapi[_-]?key\b", re.IGNORECASE),
    re.compile(r"\bpassword\b\s*[:=]", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+\b", re.IGNORECASE),
)
_RECORD_ID_PATTERN = re.compile(r"^pair-(\d+)$")


def validate_redaction(text: str) -> None:
    for pattern in _REDACTION_PATTERNS:
        if pattern.search(text):
            raise BenchmarkValidationError(
                "candidate text matches a prohibited redaction pattern"
            )


def validate_candidate_record(record: BenchmarkRecord) -> None:
    validate_redaction(record.query_a)
    validate_redaction(record.query_b)
    if not record.source_group:
        raise BenchmarkValidationError(
            f"{record.id}: candidates require source_group for leakage tracking"
        )


def load_candidates_jsonl(path: str | Path) -> list[BenchmarkRecord]:
    records = load_benchmark_jsonl(path)
    for record in records:
        validate_candidate_record(record)
    return records


def assign_next_pair_id(existing_ids: set[str]) -> str:
    numbers = []
    for record_id in existing_ids:
        match = _RECORD_ID_PATTERN.fullmatch(record_id)
        if match:
            numbers.append(int(match.group(1)))
    next_number = max(numbers, default=0) + 1
    return f"pair-{next_number:04d}"


def merge_candidate_records(
    base_records: list[BenchmarkRecord],
    candidates: list[BenchmarkRecord],
    *,
    reject_duplicate_ids: bool = True,
) -> list[BenchmarkRecord]:
    merged = list(base_records)
    seen = {record.id for record in base_records}
    for candidate in candidates:
        if candidate.id in seen:
            if reject_duplicate_ids:
                raise BenchmarkValidationError(
                    f"duplicate candidate id {candidate.id} in merge target"
                )
            continue
        validate_candidate_record(candidate)
        merged.append(candidate)
        seen.add(candidate.id)
    return merged


def write_jsonl(path: Path, records: list[BenchmarkRecord]) -> None:
    lines = [
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        for record in records
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def merge_candidates_into_dataset(
    *,
    benchmark_dir: Path,
    candidates_path: Path,
) -> list[BenchmarkRecord]:
    """Append validated candidates to reviewed_query_pairs.jsonl."""
    source_path = benchmark_dir / "reviewed_query_pairs.jsonl"
    base_records = load_benchmark_jsonl(source_path)
    candidates = load_candidates_jsonl(candidates_path)
    merged = merge_candidate_records(base_records, candidates)
    write_jsonl(source_path, merged)
    return merged


def rebuild_splits(
    benchmark_dir: Path,
    *,
    development_ids: set[str],
    held_out_ids: set[str],
) -> None:
    records = load_benchmark_jsonl(benchmark_dir / "reviewed_query_pairs.jsonl")
    by_id = {record.id: record for record in records}
    if development_ids & held_out_ids:
        raise BenchmarkValidationError("development and held-out id sets overlap")
    if development_ids | held_out_ids != set(by_id):
        raise BenchmarkValidationError("split ids must cover the merged dataset")

    dev_records = [by_id[record_id] for record_id in sorted(development_ids)]
    held_records = [by_id[record_id] for record_id in sorted(held_out_ids)]
    write_jsonl(benchmark_dir / "development.jsonl", dev_records)
    write_jsonl(benchmark_dir / "held_out_test.jsonl", held_records)


def update_manifest_counts(benchmark_dir: Path) -> str:
    manifest_path = benchmark_dir / "split_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_path = benchmark_dir / "reviewed_query_pairs.jsonl"
    manifest["source_dataset"]["sha256"] = file_sha256(source_path)
    manifest["development"]["record_count"] = len(
        load_benchmark_jsonl(benchmark_dir / "development.jsonl")
    )
    manifest["held_out_test"]["record_count"] = len(
        load_benchmark_jsonl(benchmark_dir / "held_out_test.jsonl")
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest["source_dataset"]["sha256"]


def _apply_baseline_source_groups(benchmark_dir: Path) -> None:
    source_path = benchmark_dir / "reviewed_query_pairs.jsonl"
    records = load_benchmark_jsonl(source_path)
    updated = [
        record.model_copy(
            update={
                "source_group": record.source_group
                or f"hand_authored_v1:{record.id}"
            }
        )
        for record in records
    ]
    write_jsonl(source_path, updated)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge reviewed benchmark candidates.")
    parser.add_argument(
        "--benchmark-dir",
        default="benchmarks",
        help="Benchmark directory containing reviewed_query_pairs.jsonl",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    merge_parser = subparsers.add_parser("merge", help="Merge candidates into source dataset")
    merge_parser.add_argument("--candidates", required=True, help="Candidate JSONL path")
    merge_parser.add_argument(
        "--rebuild-splits",
        action="store_true",
        help="Rebuild split JSONL files from split_manifest.json record_ids",
    )

    validate_parser = subparsers.add_parser(
        "validate-candidates",
        help="Validate candidate JSONL without merging",
    )
    validate_parser.add_argument("--candidates", required=True)

    subparsers.add_parser(
        "freeze-splits",
        help="Validate and freeze split_manifest.json identity metadata",
    )

    args = parser.parse_args(argv)
    benchmark_dir = Path(args.benchmark_dir)

    try:
        if args.command == "validate-candidates":
            load_candidates_jsonl(args.candidates)
            print("candidates validation passed")
            return 0

        if args.command == "freeze-splits":
            manifest = freeze_split_manifest(benchmark_dir)
            print(
                "froze split manifest "
                f"dataset_version={manifest.get('dataset_version')} "
                f"frozen_at={manifest.get('frozen_at')}"
            )
            return 0

        if args.command == "merge":
            _apply_baseline_source_groups(benchmark_dir)
            merged = merge_candidates_into_dataset(
                benchmark_dir=benchmark_dir,
                candidates_path=Path(args.candidates),
            )
            if args.rebuild_splits:
                dev_ids, held_ids = resolve_rebuild_split_ids(benchmark_dir)
                rebuild_splits(
                    benchmark_dir,
                    development_ids=dev_ids,
                    held_out_ids=held_ids,
                )
                freeze_split_manifest(benchmark_dir)
                print(f"merged {len(merged)} records and froze split manifest")
            else:
                print(f"merged {len(merged)} records into reviewed_query_pairs.jsonl")
                try:
                    validate_benchmark_dataset(benchmark_dir)
                except BenchmarkValidationError as exc:
                    print(
                        "benchmark build failed: merged source dataset but splits "
                        "or manifest are stale; rerun with --rebuild-splits, then "
                        "freeze-splits",
                        file=sys.stderr,
                    )
                    print(f"detail: {exc}", file=sys.stderr)
                    return 2
            return 0
    except (OSError, BenchmarkValidationError, ValueError, TypeError) as exc:
        print(f"benchmark build failed: {exc}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
