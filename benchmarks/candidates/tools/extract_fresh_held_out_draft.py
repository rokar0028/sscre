"""Extract unused CacheEval rows into a fresh held-out draft batch (WS5 Step 1)."""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from fresh_held_out_annotation import refine_draft_payload, sampling_bucket  # noqa: E402

from convert_cacheeval_candidates import (  # noqa: E402
    DEFAULT_DOMAINS,
    SOURCE_GROUP,
    convert_rows,
    map_cacheeval_row,
    write_candidate_jsonl,
    _pair_key_from_queries,
)
from filter_cacheeval_commercial import load_jsonl  # noqa: E402

from sscre.benchmark import BenchmarkRecord, BenchmarkValidationError, load_benchmark_jsonl  # noqa: E402
from sscre.benchmark_build import validate_candidate_record  # noqa: E402
from sscre.benchmark_splits import normalized_pair_key  # noqa: E402

ANNOTATION_SOURCE = "assistant_draft"
DEFAULT_LIMIT = 80
MIX_SHARES = {"compatible": 0.30, "incompatible": 0.50, "uncertain": 0.20}
CORPUS_JSONL = (
    "reviewed_query_pairs.jsonl",
    "development.jsonl",
    "held_out_test.jsonl",
)
def corpus_pair_keys(benchmark_dir: Path) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for name in CORPUS_JSONL:
        path = benchmark_dir / name
        if not path.is_file():
            continue
        for record in load_benchmark_jsonl(path):
            keys.add(normalized_pair_key(record))
    return keys


def mix_targets(limit: int) -> dict[str, int]:
    raw = {kind: limit * share for kind, share in MIX_SHARES.items()}
    counts = {kind: int(raw[kind]) for kind in MIX_SHARES}
    remainder = limit - sum(counts.values())
    for kind in ("incompatible", "compatible", "uncertain"):
        if remainder <= 0:
            break
        counts[kind] += 1
        remainder -= 1
    return counts


def select_fresh_rows(
    rows: list[dict],
    *,
    limit: int,
    domains: set[str],
    excluded_pair_keys: set[tuple[str, str]],
    seed: int,
) -> tuple[list[dict], dict[str, int]]:
    targets = mix_targets(limit)
    buckets: dict[str, list[dict]] = defaultdict(list)
    stats: dict[str, int] = defaultdict(int)

    for row in rows:
        if row.get("domain") not in domains:
            stats["skipped_domain"] += 1
            continue
        key = _pair_key_from_queries(row.get("query_a", ""), row.get("query_b", ""))
        if key in excluded_pair_keys:
            stats["skipped_existing_pair"] += 1
            continue
        try:
            mapped = map_cacheeval_row(row)
        except ValueError:
            stats["conversion_failed"] += 1
            continue
        bucket = sampling_bucket(row, mapped)
        buckets[bucket].append(row)

    rng = random.Random(seed)
    for bucket_rows in buckets.values():
        rng.shuffle(bucket_rows)

    selected: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    index = {kind: 0 for kind in targets}
    mix_counts = {kind: 0 for kind in targets}

    def pull(kind: str) -> bool:
        bucket = buckets.get(kind, [])
        idx = index[kind]
        while idx < len(bucket):
            row = bucket[idx]
            idx += 1
            key = _pair_key_from_queries(row.get("query_a", ""), row.get("query_b", ""))
            if key in seen_keys:
                stats["skipped_duplicate_batch"] += 1
                continue
            seen_keys.add(key)
            selected.append(row)
            mix_counts[kind] += 1
            index[kind] = idx
            return True
        index[kind] = idx
        return False

    kinds = ("incompatible", "compatible", "uncertain")
    for kind in kinds:
        while mix_counts[kind] < targets[kind] and len(selected) < limit:
            if not pull(kind):
                break

    while len(selected) < limit:
        progressed = False
        for kind in kinds:
            if len(selected) >= limit:
                break
            if pull(kind):
                progressed = True
        if not progressed:
            break

    stats["selected"] = len(selected)
    stats["target_mix"] = targets
    stats["selected_mix"] = dict(mix_counts)
    stats["pool_after_collision"] = sum(len(v) for v in buckets.values())
    return selected, dict(stats)


def maybe_regenerate_filtered(
    filtered_path: Path,
    audit_path: Path,
) -> str | None:
    """Regenerate filtered JSONL when missing; return status note for evidence."""
    if filtered_path.is_file():
        return "used_existing_filtered"
    candidates = [
        Path(__file__).resolve().parents[3] / "CacheEval" / "cachebench.jsonl",
        Path.home() / "CacheEval" / "cachebench.jsonl",
    ]
    import os
    import tempfile

    temp = Path(os.environ.get("TEMP", tempfile.gettempdir())) / "CacheEval" / "cachebench.jsonl"
    candidates.append(temp)
    upstream = next((p for p in candidates if p.is_file()), None)
    if upstream is None:
        return None
    filter_script = _TOOLS_DIR / "filter_cacheeval_commercial.py"
    cmd = [
        sys.executable,
        str(filter_script),
        "--input",
        str(upstream),
        "--output",
        str(filtered_path),
        "--audit",
        str(audit_path),
    ]
    subprocess.run(cmd, check=True)
    return "regenerated_filtered"


def prepare_draft_records(
    cacheeval_rows: list[dict],
    existing_ids: set[str],
) -> tuple[list[BenchmarkRecord], dict[str, int]]:
    records, stats = convert_rows(cacheeval_rows, existing_ids)
    updated: list[BenchmarkRecord] = []
    stats["guide_relabeled"] = 0
    for record, cacheeval_row in zip(records, cacheeval_rows, strict=True):
        payload = record.model_dump(mode="json")
        payload["annotation_source"] = ANNOTATION_SOURCE
        payload["source_group"] = SOURCE_GROUP
        payload["review_status"] = "draft"
        before = payload.get("compatibility_label")
        payload = refine_draft_payload(payload, cacheeval_row)
        if payload.get("compatibility_label") != before:
            stats["guide_relabeled"] += 1
        updated.append(BenchmarkRecord.model_validate(payload))
    stats["draft_records"] = len(updated)
    return updated, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/candidates/fresh_held_out_draft.jsonl"),
    )
    parser.add_argument("--benchmark-dir", type=Path, default=Path("benchmarks"))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--seed", type=int, default=20261015)
    parser.add_argument(
        "--domains",
        default=",".join(DEFAULT_DOMAINS),
        help="Comma-separated CacheEval domain filter.",
    )
    args = parser.parse_args(argv)

    audit_path = args.input.parent / "cacheeval_v1_filter_audit.json"
    filter_status = maybe_regenerate_filtered(args.input, audit_path)
    if not args.input.is_file():
        summary = {
            "status": "unavailable",
            "reason": "filtered_cacheeval_missing",
            "filter_status": filter_status,
        }
        print(json.dumps(summary, indent=2))
        return 2

    domains = {part.strip() for part in args.domains.split(",") if part.strip()}
    rows = load_jsonl(args.input)
    pair_keys = corpus_pair_keys(args.benchmark_dir)
    selected, select_stats = select_fresh_rows(
        rows,
        limit=args.limit,
        domains=domains,
        excluded_pair_keys=pair_keys,
        seed=args.seed,
    )

    if len(selected) < args.limit:
        summary = {
            "status": "unavailable",
            "reason": "insufficient_unused_rows_after_collision",
            "filter_status": filter_status,
            "input_rows": len(rows),
            "corpus_pair_keys": len(pair_keys),
            "select_stats": select_stats,
        }
        print(json.dumps(summary, indent=2))
        return 2

    reviewed = args.benchmark_dir / "reviewed_query_pairs.jsonl"
    existing_ids = {record.id for record in load_benchmark_jsonl(reviewed)}
    records, convert_stats = prepare_draft_records(selected, existing_ids)
    if not records:
        print(json.dumps({"status": "unavailable", "reason": "no_candidates_converted"}, indent=2))
        return 2

    for record in records:
        try:
            validate_candidate_record(record)
        except BenchmarkValidationError as exc:
            print(json.dumps({"status": "unavailable", "reason": str(exc)}, indent=2))
            return 2

    write_candidate_jsonl(args.output, records)
    summary = {
        "status": "ok",
        "filter_status": filter_status,
        "input_rows": len(rows),
        "corpus_pair_keys": len(pair_keys),
        "select_stats": select_stats,
        "convert_stats": convert_stats,
        "output_count": len(records),
        "output_path": str(args.output),
        "first_id": records[0].id,
        "last_id": records[-1].id,
        "domains": sorted(domains),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
