"""Backward-compatible entrypoint for Phase 3 batch 1 (use --batch 1 on cacheeval_review)."""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import apply_phase3_cacheeval_review as review  # noqa: E402


def main() -> int:
    argv = list(sys.argv)
    if "--batch" not in argv:
        argv[1:1] = ["--batch", "1"]
    if "--input" not in argv:
        argv.extend(
            [
                "--input",
                "benchmarks/candidates/cacheeval_batch_01.jsonl",
            ]
        )
    sys.argv = argv
    return review.main()


if __name__ == "__main__":
    raise SystemExit(main())
