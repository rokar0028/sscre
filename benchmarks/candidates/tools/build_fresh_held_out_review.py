"""Step 2: refine draft labels and write fresh_held_out_review.md."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from convert_cacheeval_candidates import write_candidate_jsonl  # noqa: E402
from filter_cacheeval_commercial import load_jsonl  # noqa: E402
from fresh_held_out_annotation import refine_draft_payload  # noqa: E402

from sscre.benchmark import BenchmarkRecord, load_benchmark_jsonl  # noqa: E402
from sscre.benchmark_build import validate_candidate_record  # noqa: E402

_REDACT = re.compile(
    r"\b(sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._-]+)\b", re.IGNORECASE
)
_QUERY_CELL_MAX = 72


def _redact(text: str) -> str:
    return _REDACT.sub("[REDACTED]", text)


def _cell(text: str) -> str:
    text = _redact(text.replace("|", "\\|").replace("\n", " "))
    if len(text) <= _QUERY_CELL_MAX:
        return text
    return text[: _QUERY_CELL_MAX - 1] + "…"


def _upstream_id(record: BenchmarkRecord) -> str:
    intent = record.metadata.intent or ""
    prefix = "cacheeval:"
    if not intent.startswith(prefix):
        raise ValueError(f"{record.id}: missing cacheeval intent")
    return intent[len(prefix) :]


def build_review_markdown(records: list[BenchmarkRecord]) -> str:
    lines = [
        "# Fresh held-out review sheet (WS5 Step 2)",
        "",
        "Draft batch for human review. JSONL remains `review_status: draft` until",
        "Step 3. Mark **Action** as `keep`, `change` (note new label in chat), or",
        "`drop` for each row.",
        "",
        "| ID | Query A | Query B | Draft label | Action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            "| {id} | {a} | {b} | {label} | |".format(
                id=record.id,
                a=_cell(record.query_a),
                b=_cell(record.query_b),
                label=record.compatibility_label or "",
            )
        )
    lines.extend(
        [
            "",
            "## Label counts (draft)",
            "",
        ]
    )
    from collections import Counter

    counts = Counter(r.compatibility_label for r in records)
    for label in ("compatible", "incompatible", "uncertain"):
        lines.append(f"- `{label}`: {counts.get(label, 0)}")
    lines.append("")
    return "\n".join(lines)


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
        "--upstream",
        type=Path,
        default=Path("benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl"),
    )
    args = parser.parse_args(argv)

    if not args.draft.is_file():
        print(f"draft not found: {args.draft}", file=sys.stderr)
        return 1
    if not args.upstream.is_file():
        print(f"upstream not found: {args.upstream}", file=sys.stderr)
        return 1

    upstream = {row["id"]: row for row in load_jsonl(args.upstream)}
    refined: list[BenchmarkRecord] = []
    relabeled = 0

    for record in load_benchmark_jsonl(args.draft):
        uid = _upstream_id(record)
        row = upstream.get(uid)
        if row is None:
            print(f"missing upstream row for {record.id} ({uid})", file=sys.stderr)
            return 1
        payload = refine_draft_payload(record.model_dump(mode="json"), row)
        if payload.get("compatibility_label") != record.compatibility_label:
            relabeled += 1
        updated = BenchmarkRecord.model_validate(payload)
        validate_candidate_record(updated)
        refined.append(updated)

    write_candidate_jsonl(args.draft, refined)
    args.review.write_text(build_review_markdown(refined), encoding="utf-8")
    print(
        json.dumps(
            {
                "draft": str(args.draft),
                "review": str(args.review),
                "rows": len(refined),
                "relabeled": relabeled,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
