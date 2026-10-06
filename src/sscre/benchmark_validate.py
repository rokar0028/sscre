"""CLI entry point for benchmark dataset validation."""

import argparse
import json
import sys
from pathlib import Path

from sscre.benchmark import BenchmarkValidationError, load_benchmark_jsonl
from sscre.benchmark_coverage import PHASE2_REVIEWED_COVERAGE, validate_coverage
from sscre.benchmark_splits import file_sha256, validate_benchmark_dataset


def _print_validation_summary(benchmark_dir: Path) -> None:
    manifest_path = benchmark_dir / "split_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    development = manifest.get("development", {})
    held_out = manifest.get("held_out_test", {})
    source = manifest.get("source_dataset", {})
    coverage = manifest.get("coverage_summary", {})
    leakage = manifest.get("leakage_validation", {})

    print(f"dataset_version={manifest.get('dataset_version')}")
    print(f"schema_version={manifest.get('schema_version')}")
    print(f"annotation_guide_version={manifest.get('annotation_guide_version')}")
    print(
        "split_counts="
        f"development:{development.get('record_count')} "
        f"held_out:{held_out.get('record_count')} "
        f"source:{source.get('record_count')}"
    )
    category_counts = coverage.get("coverage_category_counts")
    if isinstance(category_counts, dict):
        print(f"category_counts={json.dumps(category_counts, sort_keys=True)}")
    print(f"leakage_status={leakage.get('status')}")
    if manifest.get("frozen_at"):
        print(f"frozen_at={manifest.get('frozen_at')}")
    print(f"split_manifest_sha256={file_sha256(manifest_path)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate benchmark JSONL, manifest, coverage, and split leakage.",
    )
    parser.add_argument(
        "--benchmark-dir",
        default="benchmarks",
        help="Directory containing split_manifest.json and dataset files.",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Require final review status on every source record.",
    )
    parser.add_argument(
        "--phase2",
        action="store_true",
        help="Also require Phase 2 coverage policy (500+ records).",
    )
    args = parser.parse_args(argv)
    benchmark_dir = Path(args.benchmark_dir)

    try:
        report = validate_benchmark_dataset(
            benchmark_dir,
            production=args.production,
        )
        if args.phase2:
            records = load_benchmark_jsonl(
                benchmark_dir / "reviewed_query_pairs.jsonl",
                require_final_review=args.production,
            )
            validate_coverage(records, policy=PHASE2_REVIEWED_COVERAGE)
    except (OSError, BenchmarkValidationError, ValueError, TypeError) as exc:
        print(f"benchmark validation failed: {exc}", file=sys.stderr)
        return 2

    _print_validation_summary(benchmark_dir)
    print(
        "benchmark validation passed "
        f"(cross_split_fingerprint_overlaps={report.cross_split_fingerprint_overlaps})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
