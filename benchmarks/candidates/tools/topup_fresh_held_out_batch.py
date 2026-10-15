"""Add pairs to the fresh held-out batch from unused CacheEval rows."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from apply_fresh_held_out_remediation import apply_remediation  # noqa: E402
from apply_fresh_held_out_review import _finalize_record  # noqa: E402
from build_fresh_held_out_review import build_review_markdown  # noqa: E402
from convert_cacheeval_candidates import write_candidate_jsonl  # noqa: E402
from extract_fresh_held_out_draft import (  # noqa: E402
    DEFAULT_DOMAINS,
    corpus_pair_keys,
    maybe_regenerate_filtered,
    prepare_draft_records,
    select_fresh_rows,
)
from filter_cacheeval_commercial import load_jsonl  # noqa: E402
from sscre.benchmark import BenchmarkRecord, load_benchmark_jsonl  # noqa: E402
from sscre.benchmark_annotation import validate_review_policy  # noqa: E402
from sscre.benchmark_splits import normalized_pair_key  # noqa: E402


def _pair_keys_from_jsonl(path: Path) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for record in load_benchmark_jsonl(path):
        keys.add(normalized_pair_key(record))
    return keys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reviewed",
        type=Path,
        default=Path("benchmarks/candidates/fresh_held_out_reviewed.jsonl"),
    )
    parser.add_argument(
        "--draft",
        type=Path,
        default=Path("benchmarks/candidates/fresh_held_out_draft.jsonl"),
    )
    parser.add_argument(
        "--review",
        type=Path,
        default=Path("benchmarks/candidates/fresh_held_out_review.md"),
    )
    parser.add_argument("--benchmark-dir", type=Path, default=Path("benchmarks"))
    parser.add_argument("--target-total", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261016)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl"),
    )
    args = parser.parse_args(argv)

    if not args.reviewed.is_file():
        print(f"reviewed batch not found: {args.reviewed}", file=sys.stderr)
        return 1

    existing = load_benchmark_jsonl(args.reviewed)
    add_count = args.target_total - len(existing)
    if add_count <= 0:
        print(
            json.dumps(
                {
                    "status": "noop",
                    "current": len(existing),
                    "target_total": args.target_total,
                },
                indent=2,
            )
        )
        return 0

    audit_path = args.input.parent / "cacheeval_v1_filter_audit.json"
    filter_status = maybe_regenerate_filtered(args.input, audit_path)
    if not args.input.is_file():
        print(json.dumps({"status": "unavailable", "reason": "missing_filtered"}))
        return 2

    excluded = corpus_pair_keys(args.benchmark_dir)
    excluded |= _pair_keys_from_jsonl(args.reviewed)
    domains = set(DEFAULT_DOMAINS)
    rows = load_jsonl(args.input)
    selected, select_stats = select_fresh_rows(
        rows,
        limit=add_count,
        domains=domains,
        excluded_pair_keys=excluded,
        seed=args.seed,
    )
    if len(selected) < add_count:
        print(
            json.dumps(
                {
                    "status": "unavailable",
                    "reason": "insufficient_pool_for_topup",
                    "requested": add_count,
                    "selected": len(selected),
                    "select_stats": select_stats,
                },
                indent=2,
            )
        )
        return 2

    id_sources = [
        args.benchmark_dir / "reviewed_query_pairs.jsonl",
        args.reviewed,
    ]
    existing_ids: set[str] = set()
    for path in id_sources:
        if path.is_file():
            existing_ids |= {r.id for r in load_benchmark_jsonl(path)}

    new_drafts, convert_stats = prepare_draft_records(selected, existing_ids)
    new_finals = [_finalize_record(r) for r in new_drafts]
    merged = list(existing) + new_finals
    remediated, touched = apply_remediation(merged)
    validate_review_policy(remediated, split="held-out")

    write_candidate_jsonl(args.reviewed, remediated)
    prior_draft = load_benchmark_jsonl(args.draft) if args.draft.is_file() else []
    write_candidate_jsonl(args.draft, [*prior_draft, *new_drafts])

    review_text = build_review_markdown(remediated)
    args.review.write_text(review_text, encoding="utf-8")

    compat = Counter(r.compatibility_label for r in remediated)
    print(
        json.dumps(
            {
                "status": "ok",
                "filter_status": filter_status,
                "added": len(new_finals),
                "total": len(remediated),
                "new_ids": [r.id for r in new_finals],
                "remediation_touched": touched,
                "compatibility_counts": dict(compat),
                "select_stats": select_stats,
                "convert_stats": convert_stats,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
