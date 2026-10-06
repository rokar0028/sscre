"""Split manifest, leakage detection, and dataset integrity validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sscre import __version__
from sscre.benchmark import BenchmarkRecord, BenchmarkValidationError, load_benchmark_jsonl
from sscre.benchmark_annotation import ANNOTATION_GUIDE_VERSION, validate_review_policy
from sscre.benchmark_coverage import (
    WORKING_BASELINE_COVERAGE,
    build_coverage_report,
    validate_coverage,
)
from sscre.query import normalize_query

SPLIT_MANIFEST_SCHEMA_VERSION = "1.0.0"
SUPPORTED_MANIFEST_SCHEMA_VERSIONS = frozenset({SPLIT_MANIFEST_SCHEMA_VERSION})
NEAR_DUPLICATE_JACCARD_THRESHOLD = 0.95


@dataclass(frozen=True)
class LeakageReport:
    """Summary of dataset-level leakage checks."""

    duplicate_pair_keys: int = 0
    cross_split_fingerprint_overlaps: int = 0
    reversed_pair_overlaps: int = 0
    shared_source_groups: int = 0
    near_duplicate_pairs: int = 0


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_pair_key(record: BenchmarkRecord) -> tuple[str, str]:
    """Direction-aware normalized query pair identity."""
    left = normalize_query(record.query_a)
    right = normalize_query(record.query_b)
    if record.directionality == "symmetric":
        return tuple(sorted((left, right)))
    return (left, right)


def pair_fingerprint(record: BenchmarkRecord) -> frozenset[str]:
    """Order-independent normalized pair identity for split leakage."""
    return frozenset(
        {normalize_query(record.query_a), normalize_query(record.query_b)}
    )


def _token_set(text: str) -> set[str]:
    return set(normalize_query(text).lower().split())


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def is_near_duplicate_pair(
    left: BenchmarkRecord,
    right: BenchmarkRecord,
    *,
    threshold: float = NEAR_DUPLICATE_JACCARD_THRESHOLD,
) -> bool:
    if left.id == right.id:
        return False
    a = jaccard_similarity(_token_set(left.query_a), _token_set(right.query_a))
    b = jaccard_similarity(_token_set(left.query_b), _token_set(right.query_b))
    return a >= threshold and b >= threshold


def validate_coverage_category_consistency(record: BenchmarkRecord) -> None:
    """Validate reviewed coverage category against query and label fields."""
    if record.schema_version != "1.1" or not record.coverage_category:
        return

    def reject(message: str) -> None:
        raise BenchmarkValidationError(f"{record.id}: {message}")

    normalized_a = normalize_query(record.query_a)
    normalized_b = normalize_query(record.query_b)
    category = record.coverage_category

    if category == "exact_duplicate" and normalized_a != normalized_b:
        reject("exact_duplicate requires normalized query equality")
    if category == "whitespace_variant":
        if normalized_a != normalized_b or record.query_a == record.query_b:
            reject(
                "whitespace_variant requires raw text difference with normalized equality"
            )
    if category == "insufficient_evidence" and record.compatibility_label != "uncertain":
        reject("insufficient_evidence requires uncertain compatibility")
    if category in {
        "paraphrase",
        "low_overlap_compatible",
        "exact_duplicate",
        "whitespace_variant",
    }:
        if not record.reusable or record.compatibility_label != "compatible":
            reject(f"{category} requires reusable compatible labels")


def validate_no_duplicate_pair_keys(records: list[BenchmarkRecord]) -> None:
    seen: dict[tuple[str, str], str] = {}
    for record in records:
        key = normalized_pair_key(record)
        other_id = seen.get(key)
        if other_id is not None:
            raise BenchmarkValidationError(
                f"duplicate normalized pair {key!r}: {other_id} and {record.id}"
            )
        seen[key] = record.id


def validate_cross_split_leakage(
    development: list[BenchmarkRecord],
    held_out: list[BenchmarkRecord],
    *,
    near_duplicate_threshold: float = NEAR_DUPLICATE_JACCARD_THRESHOLD,
) -> LeakageReport:
    """Fail closed on normalized overlap, reversed pairs, groups, near-duplicates."""
    report = LeakageReport()

    dev_fingerprints = {pair_fingerprint(record): record.id for record in development}
    dev_ordered = {normalized_pair_key(record) for record in development}
    dev_groups: dict[str, str] = {}
    for record in development:
        if record.source_group:
            dev_groups[record.source_group] = record.id

    for record in held_out:
        fingerprint = pair_fingerprint(record)
        if fingerprint in dev_fingerprints:
            raise BenchmarkValidationError(
                "held-out record "
                f"{record.id} shares a normalized pair fingerprint with development "
                f"record {dev_fingerprints[fingerprint]}"
            )

        ordered = normalized_pair_key(record)
        if record.directionality == "ordered" and (ordered[1], ordered[0]) in dev_ordered:
            raise BenchmarkValidationError(
                f"held-out record {record.id} reverses a development ordered pair"
            )

        if record.source_group and record.source_group in dev_groups:
            raise BenchmarkValidationError(
                f"held-out record {record.id} shares source_group "
                f"{record.source_group!r} with development record "
                f"{dev_groups[record.source_group]}"
            )

        for dev_record in development:
            if is_near_duplicate_pair(
                record,
                dev_record,
                threshold=near_duplicate_threshold,
            ):
                raise BenchmarkValidationError(
                    "held-out record "
                    f"{record.id} is a near-duplicate of development record "
                    f"{dev_record.id} (Jaccard >= {near_duplicate_threshold})"
                )

    return report


def load_split_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkValidationError(
            f"invalid split manifest {manifest_path}: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise BenchmarkValidationError("split manifest must be a JSON object")

    manifest_version = manifest.get("manifest_schema_version", SPLIT_MANIFEST_SCHEMA_VERSION)
    if manifest_version not in SUPPORTED_MANIFEST_SCHEMA_VERSIONS:
        raise BenchmarkValidationError(
            f"unsupported manifest_schema_version: {manifest_version!r}"
        )

    guide_version = manifest.get("annotation_guide_version")
    if guide_version is not None and guide_version != ANNOTATION_GUIDE_VERSION:
        raise BenchmarkValidationError(
            "annotation_guide_version differs from "
            f"{ANNOTATION_GUIDE_VERSION!r}"
        )
    return manifest


def validate_manifest_files(manifest: dict[str, Any], data_dir: Path) -> Path:
    source_meta = manifest.get("source_dataset")
    if not isinstance(source_meta, dict):
        raise BenchmarkValidationError("split manifest requires source_dataset")

    source_path_value = source_meta.get("path")
    if not isinstance(source_path_value, str):
        raise BenchmarkValidationError("source_dataset.path is required")

    repo_root = data_dir.parent
    source_path = (repo_root / source_path_value).resolve()
    if not source_path.is_file():
        raise BenchmarkValidationError(f"missing source dataset {source_path}")

    expected_sha = source_meta.get("sha256")
    if isinstance(expected_sha, str) and expected_sha.strip():
        actual_sha = file_sha256(source_path)
        if actual_sha != expected_sha.strip():
            raise BenchmarkValidationError(
                "source_dataset sha256 mismatch: "
                f"expected {expected_sha}, got {actual_sha}"
            )

    for split_key in ("development", "held_out_test"):
        split_meta = manifest.get(split_key)
        if not isinstance(split_meta, dict):
            raise BenchmarkValidationError(f"split manifest missing {split_key!r}")
        split_path_value = split_meta.get("path")
        if not isinstance(split_path_value, str):
            raise BenchmarkValidationError(f"{split_key} path is required")
        split_path = (repo_root / split_path_value).resolve()
        if not split_path.is_file():
            raise BenchmarkValidationError(f"missing split file {split_path}")

    return source_path


def _split_path(repo_root: Path, manifest: dict[str, Any], split_key: str) -> Path:
    split_meta = manifest[split_key]
    if not isinstance(split_meta, dict):
        raise BenchmarkValidationError(f"split manifest missing {split_key!r}")
    split_path_value = split_meta.get("path")
    if not isinstance(split_path_value, str):
        raise BenchmarkValidationError(f"{split_key} path is required")
    return (repo_root / split_path_value).resolve()


def validate_manifest_split_identity(
    manifest: dict[str, Any],
    *,
    repo_root: Path,
    development: list[BenchmarkRecord],
    held_out: list[BenchmarkRecord],
) -> None:
    """Ensure frozen manifest IDs and checksums match the split files."""
    for split_key, records in (
        ("development", development),
        ("held_out_test", held_out),
    ):
        split_meta = manifest.get(split_key)
        if not isinstance(split_meta, dict):
            raise BenchmarkValidationError(f"split manifest missing {split_key!r}")

        record_count = split_meta.get("record_count")
        if record_count != len(records):
            raise BenchmarkValidationError(
                f"{split_key} record_count does not match the split file"
            )

        expected_ids = split_meta.get("record_ids")
        if expected_ids is not None:
            if not isinstance(expected_ids, list):
                raise BenchmarkValidationError(f"{split_key} record_ids must be a list")
            actual_ids = [record.id for record in records]
            if expected_ids != actual_ids:
                raise BenchmarkValidationError(
                    f"{split_key} record_ids do not match the split file"
                )

        expected_sha = split_meta.get("sha256")
        if isinstance(expected_sha, str) and expected_sha.strip():
            split_path = _split_path(repo_root, manifest, split_key)
            actual_sha = file_sha256(split_path)
            if actual_sha != expected_sha.strip():
                raise BenchmarkValidationError(f"{split_key} sha256 mismatch")


def freeze_split_manifest(benchmark_dir: Path) -> dict[str, Any]:
    """Validate the dataset and write a frozen split manifest."""
    manifest_path = benchmark_dir / "split_manifest.json"
    manifest = load_split_manifest(manifest_path)
    repo_root = benchmark_dir.parent
    source_path = validate_manifest_files(manifest, benchmark_dir)

    full_records = load_benchmark_jsonl(source_path)
    for record in full_records:
        validate_coverage_category_consistency(record)
    validate_no_duplicate_pair_keys(full_records)
    validate_coverage(full_records, policy=WORKING_BASELINE_COVERAGE)

    development_path = _split_path(repo_root, manifest, "development")
    held_out_path = _split_path(repo_root, manifest, "held_out_test")
    development = load_benchmark_jsonl(development_path)
    held_out = load_benchmark_jsonl(held_out_path)

    dev_ids = {record.id for record in development}
    held_ids = {record.id for record in held_out}
    full_ids = {record.id for record in full_records}
    if dev_ids & held_ids:
        raise BenchmarkValidationError("development and held-out IDs overlap")
    if dev_ids | held_ids != full_ids:
        raise BenchmarkValidationError(
            "development and held-out splits do not cover the source dataset"
        )

    validate_review_policy(held_out, split="held-out")
    leakage_report = validate_cross_split_leakage(development, held_out)
    coverage_summary = build_coverage_report(
        full_records,
        policy=WORKING_BASELINE_COVERAGE,
    )

    frozen_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest.update(
        {
            "frozen_at": frozen_at,
            "software_version": __version__,
            "source_dataset": {
                **manifest["source_dataset"],
                "sha256": file_sha256(source_path),
                "record_count": len(full_records),
            },
            "development": {
                **manifest["development"],
                "record_count": len(development),
                "record_ids": [record.id for record in development],
                "sha256": file_sha256(development_path),
            },
            "held_out_test": {
                **manifest["held_out_test"],
                "record_count": len(held_out),
                "record_ids": [record.id for record in held_out],
                "sha256": file_sha256(held_out_path),
            },
            "leakage_validation": {
                "status": "passed",
                "cross_split_fingerprint_overlaps": (
                    leakage_report.cross_split_fingerprint_overlaps
                ),
                "reversed_pair_overlaps": leakage_report.reversed_pair_overlaps,
                "shared_source_groups": leakage_report.shared_source_groups,
                "near_duplicate_pairs": leakage_report.near_duplicate_pairs,
            },
            "coverage_summary": coverage_summary,
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def resolve_rebuild_split_ids(benchmark_dir: Path) -> tuple[set[str], set[str]]:
    """Return development and held-out IDs from the frozen manifest assignment."""
    manifest_path = benchmark_dir / "split_manifest.json"
    manifest = load_split_manifest(manifest_path)
    development_meta = manifest.get("development")
    held_out_meta = manifest.get("held_out_test")
    if not isinstance(development_meta, dict) or not isinstance(held_out_meta, dict):
        raise BenchmarkValidationError("split manifest missing development or held-out")

    dev_ids_raw = development_meta.get("record_ids")
    held_ids_raw = held_out_meta.get("record_ids")
    if not isinstance(dev_ids_raw, list) or not isinstance(held_ids_raw, list):
        raise BenchmarkValidationError(
            "split rebuild requires development and held_out_test record_ids in the manifest"
        )

    development_ids = {str(record_id) for record_id in dev_ids_raw}
    held_out_ids = {str(record_id) for record_id in held_ids_raw}
    if development_ids & held_out_ids:
        raise BenchmarkValidationError("manifest development and held-out record_ids overlap")

    source_path = benchmark_dir / "reviewed_query_pairs.jsonl"
    all_ids = {record.id for record in load_benchmark_jsonl(source_path)}
    assigned = development_ids | held_out_ids
    unassigned = sorted(all_ids - assigned)
    if unassigned:
        raise BenchmarkValidationError(
            "assign new records in split_manifest.json record_ids before rebuild: "
            f"{', '.join(unassigned)}"
        )
    stale = sorted(assigned - all_ids)
    if stale:
        raise BenchmarkValidationError(
            "manifest record_ids reference missing source records: "
            f"{', '.join(stale)}"
        )
    if assigned != all_ids:
        raise BenchmarkValidationError(
            "manifest record_ids must cover the full reviewed source dataset"
        )
    return development_ids, held_out_ids


def validate_benchmark_dataset(
    data_dir: Path,
    *,
    production: bool = False,
) -> LeakageReport:
    """Validate manifest, coverage, review policy, and split leakage."""
    manifest_path = data_dir / "split_manifest.json"
    manifest = load_split_manifest(manifest_path)
    source_path = validate_manifest_files(manifest, data_dir)

    full_records = load_benchmark_jsonl(
        source_path,
        require_final_review=production,
    )
    for record in full_records:
        validate_coverage_category_consistency(record)

    validate_no_duplicate_pair_keys(full_records)
    validate_coverage(full_records, policy=WORKING_BASELINE_COVERAGE)

    repo_root = data_dir.parent
    development_path = _split_path(repo_root, manifest, "development")
    held_out_path = _split_path(repo_root, manifest, "held_out_test")
    development = load_benchmark_jsonl(development_path)
    held_out = load_benchmark_jsonl(held_out_path)

    dev_ids = {record.id for record in development}
    held_ids = {record.id for record in held_out}
    full_ids = {record.id for record in full_records}
    if dev_ids & held_ids:
        raise BenchmarkValidationError("development and held-out IDs overlap")
    if dev_ids | held_ids != full_ids:
        raise BenchmarkValidationError(
            "development and held-out splits do not cover the source dataset"
        )

    validate_review_policy(held_out, split="held-out")
    leakage_report = validate_cross_split_leakage(development, held_out)

    if manifest.get("development", {}).get("record_ids") is not None:
        validate_manifest_split_identity(
            manifest,
            repo_root=repo_root,
            development=development,
            held_out=held_out,
        )

    leakage_meta = manifest.get("leakage_validation")
    if isinstance(leakage_meta, dict) and leakage_meta.get("status") != "passed":
        raise BenchmarkValidationError("manifest leakage_validation status is not passed")

    return leakage_report


def summarize_label_review_status(
    records: list[BenchmarkRecord],
) -> dict[str, int]:
    """Count review states for the evaluated split."""
    counts = {"final": 0, "draft": 0, "disputed": 0, "unavailable": 0}
    for record in records:
        status = record.review_status or "unavailable"
        bucket = status if status in counts else "unavailable"
        counts[bucket] += 1
    return counts


def build_split_record_identity(
    records: list[BenchmarkRecord],
) -> list[dict[str, object]]:
    """Record identifiers for failure analysis without raw prompt text."""
    identity: list[dict[str, object]] = []
    for record in records:
        identity.append(
            {
                "id": record.id,
                "coverage_category": record.coverage_category,
                "failure_category": record.failure_category,
                "review_status": record.review_status or "unavailable",
                "adjudication_status": record.adjudication_status,
                "correctness_label": record.correctness_label,
                "preference_label": record.preference_label,
            }
        )
    return identity


def build_benchmark_report_metadata(
    manifest: dict[str, Any],
    *,
    split: str,
    records: list[BenchmarkRecord],
    manifest_path: Path,
) -> dict[str, object]:
    """Benchmark artifact identity block for evaluation reports."""
    split_key = "development" if split == "development" else "held_out_test"
    split_meta = manifest.get(split_key, {})
    if not isinstance(split_meta, dict):
        split_meta = {}

    coverage_summary = manifest.get("coverage_summary")
    leakage_validation = manifest.get("leakage_validation")

    return {
        "dataset_version": manifest.get("dataset_version"),
        "schema_version": manifest.get("schema_version"),
        "annotation_guide_version": manifest.get("annotation_guide_version"),
        "manifest_schema_version": manifest.get("manifest_schema_version"),
        "split_manifest_sha256": file_sha256(manifest_path),
        "frozen_at": manifest.get("frozen_at"),
        "evaluation_split": split,
        "split_record_count": len(records),
        "split_sha256": split_meta.get("sha256"),
        "split_record_ids": split_meta.get("record_ids"),
        "source_dataset": manifest.get("source_dataset"),
        "coverage_summary": coverage_summary,
        "leakage_validation": leakage_validation,
        "label_review_status_counts": summarize_label_review_status(records),
        "split_record_identity": build_split_record_identity(records),
        "evaluation_directions": manifest.get("evaluation_directions"),
    }
