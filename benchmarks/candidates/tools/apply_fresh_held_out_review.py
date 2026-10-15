"""Apply Step 3 human review decisions to fresh held-out draft pairs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from convert_cacheeval_candidates import write_candidate_jsonl  # noqa: E402

from sscre.benchmark import BenchmarkRecord, load_benchmark_jsonl  # noqa: E402
from sscre.benchmark_annotation import validate_review_policy  # noqa: E402
from sscre.benchmark_build import validate_candidate_record  # noqa: E402

_SOURCE_GROUP_PREFIX = "hand_reviewed_v2:fresh_held_out_ws5"
_TABLE_ROW = re.compile(
    r"^\|\s*(pair-\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|$"
)
_ACTION_KEEP = frozenset({"keep", "k"})
_ACTION_DROP = frozenset({"drop", "d"})
_COMPAT_LABELS = frozenset({"compatible", "incompatible", "uncertain"})
_HIGH_IMPACT = frozenset({"insufficient_evidence", "ambiguity", "stale_answer"})


def _parse_review_actions(path: Path) -> dict[str, str]:
    actions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _TABLE_ROW.match(line.strip())
        if not match:
            continue
        pair_id, _a, _b, _label, action_cell = match.groups()
        action = action_cell.strip().lower()
        if not action:
            continue
        actions[pair_id] = action
    return actions


def _finalize_record(record: BenchmarkRecord) -> BenchmarkRecord:
    payload = record.model_dump(mode="json")
    payload["review_status"] = "final"
    payload["annotation_source"] = "human_review"
    payload["expected_reuse"] = payload["reusable"]
    payload["expected_compatibility"] = payload["compatibility_label"]
    payload["source_group"] = f"{_SOURCE_GROUP_PREFIX}:{record.id}"
    if payload.get("coverage_category") in _HIGH_IMPACT:
        payload["annotator_count"] = 2
    updated = BenchmarkRecord.model_validate(payload)
    validate_candidate_record(updated)
    return updated


def _apply_change(record: BenchmarkRecord, action: str) -> BenchmarkRecord:
    if not action.startswith("change"):
        raise ValueError(f"unsupported change action: {action}")
    parts = action.replace(":", " ").split()
    if len(parts) < 2:
        raise ValueError(f"change action requires label: {action}")
    label = parts[1].lower()
    if label not in _COMPAT_LABELS:
        raise ValueError(f"invalid compatibility label in action: {action}")
    payload = record.model_dump(mode="json")
    payload["compatibility_label"] = label
    if label == "compatible":
        payload["reusable"] = True
        payload["failure_category"] = "none"
        if payload.get("coverage_category") in _HIGH_IMPACT:
            payload["coverage_category"] = "paraphrase"
    else:
        payload["reusable"] = False
        if label == "uncertain":
            payload["failure_category"] = "insufficient_evidence"
            payload["coverage_category"] = "insufficient_evidence"
    return BenchmarkRecord.model_validate(payload)


def apply_decisions(
    records: list[BenchmarkRecord],
    actions: dict[str, str],
    *,
    assume_keep_all: bool,
) -> tuple[list[BenchmarkRecord], dict[str, int]]:
    stats: dict[str, int] = Counter()
    finals: list[BenchmarkRecord] = []
    ids = {r.id for r in records}

    for pair_id, action in actions.items():
        if pair_id not in ids:
            raise ValueError(f"unknown pair id in review sheet: {pair_id}")

    for record in records:
        action = actions.get(record.id, "")
        if not action and assume_keep_all:
            action = "keep"
        if not action:
            stats["missing_action"] += 1
            continue
        if action in _ACTION_DROP:
            stats["dropped"] += 1
            continue
        if action in _ACTION_KEEP:
            stats["kept"] += 1
            finals.append(_finalize_record(record))
            continue
        if action.startswith("change"):
            stats["changed"] += 1
            updated = _apply_change(record, action)
            finals.append(_finalize_record(updated))
            continue
        raise ValueError(f"{record.id}: unsupported action {action!r}")

    stats["final_count"] = len(finals)
    return finals, dict(stats)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/candidates/fresh_held_out_reviewed.jsonl"),
    )
    parser.add_argument(
        "--assume-keep-all",
        action="store_true",
        help="Treat blank Action cells as keep (requires explicit operator OK).",
    )
    args = parser.parse_args(argv)

    if not args.draft.is_file():
        print(f"draft not found: {args.draft}", file=sys.stderr)
        return 1

    records = load_benchmark_jsonl(args.draft)
    actions = _parse_review_actions(args.review) if args.review.is_file() else {}
    if not actions and not args.assume_keep_all:
        print(
            "no Action cells in review sheet; pass --assume-keep-all after operator OK",
            file=sys.stderr,
        )
        return 1

    finals, stats = apply_decisions(
        records, actions, assume_keep_all=args.assume_keep_all
    )
    if stats.get("missing_action"):
        print(json.dumps({"status": "error", "stats": stats}, indent=2))
        return 1
    if stats["final_count"] < 40:
        print(
            json.dumps(
                {
                    "status": "deferred",
                    "reason": "fewer_than_40_pairs_after_review",
                    "stats": stats,
                },
                indent=2,
            )
        )
        return 2

    validate_review_policy(finals, split="held-out")
    write_candidate_jsonl(args.output, finals)
    compat = Counter(r.compatibility_label for r in finals)
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "stats": stats,
                "compatibility_counts": dict(compat),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
