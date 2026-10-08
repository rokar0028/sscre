"""Filter CacheEval cachebench.jsonl for commercial redistribution.

Removes rows flagged in CacheEval ATTRIBUTION.md as Quora QQP (restrictive ToS)
or xLAM-irrelevance (CC BY-NC 4.0). See docs/phase-2/BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

QUORA_QQP_SOURCE = re.compile(r"quora|\bqqp\b", re.IGNORECASE)
XLAM_NC_SOURCE = re.compile(r"xlam-irrelevance", re.IGNORECASE)


def commercial_exclusion_reason(row: dict) -> str | None:
    source = row.get("source") or ""
    if QUORA_QQP_SOURCE.search(source):
        return "quora_qqp_source"
    if XLAM_NC_SOURCE.search(source):
        return "xlam_nc_source"
    return None


def filter_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    kept: list[dict] = []
    excluded: list[dict] = []
    for row in rows:
        reason = commercial_exclusion_reason(row)
        if reason:
            excluded.append({**row, "_exclusion_reason": reason})
        else:
            kept.append(row)
    return kept, excluded


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON") from exc
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_audit(
    *,
    input_path: Path,
    output_path: Path,
    upstream_revision: str | None,
    kept: list[dict],
    excluded: list[dict],
) -> dict:
    reason_counts = Counter(row["_exclusion_reason"] for row in excluded)
    input_display = (
        f"CacheEval@{upstream_revision}/cachebench.jsonl"
        if upstream_revision
        else _repo_relative_path(input_path)
    )
    return {
        "filter": "cacheeval_commercial_v1",
        "policy_doc": "docs/phase-2/BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md",
        "input_path": input_display,
        "output_path": _repo_relative_path(output_path),
        "upstream_revision": upstream_revision,
        "input_row_count": len(kept) + len(excluded),
        "retained_row_count": len(kept),
        "excluded_row_count": len(excluded),
        "excluded_by_reason": dict(sorted(reason_counts.items())),
        "excluded_ids": [
            {
                "id": row["id"],
                "reason": row["_exclusion_reason"],
                "source": row.get("source"),
            }
            for row in excluded
        ],
        "output_sha256": sha256_file(output_path) if output_path.is_file() else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to upstream cachebench.jsonl (unfiltered).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl"),
        help="Filtered JSONL output path.",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json"),
        help="JSON audit manifest (counts and excluded IDs).",
    )
    parser.add_argument(
        "--upstream-revision",
        default=None,
        help="Optional git commit SHA of the CacheEval checkout used for --input.",
    )
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"input not found: {args.input}", file=sys.stderr)
        return 1

    rows = load_jsonl(args.input)
    kept, excluded = filter_rows(rows)
    write_jsonl(args.output, kept)

    audit = build_audit(
        input_path=args.input.resolve(),
        output_path=args.output.resolve(),
        upstream_revision=args.upstream_revision,
        kept=kept,
        excluded=excluded,
    )
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    print(
        f"retained={len(kept)} excluded={len(excluded)} "
        f"output={args.output} audit={args.audit}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
