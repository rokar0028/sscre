"""Apply post-review fixes from the WS5 second-pass audit."""

from __future__ import annotations

import argparse
import json
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

REMEDIATION_OVERRIDES: dict[str, dict] = {
    "pair-0628": {
        "reason": (
            "'yeah' and 'nope' express opposite affirmation polarity; "
            "serving A's reply for B inverts the user's stance."
        ),
    },
    "pair-0637": {
        "reason": "Request to keep going differs from request to stop now.",
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
    },
    "pair-0639": {
        "reason": (
            "Affirmation 'perfect' differs from negation 'not perfect'; "
            "reuse would flip evaluation polarity."
        ),
    },
    "pair-0648": {
        "reason": (
            "Affirmation 'sure' differs from hedged 'not sure'; "
            "reuse would misread user confidence."
        ),
    },
    "pair-0702": {
        "reason": (
            "Affirmation 'that's correct' differs from rejection "
            "'that's incorrect'; reuse inverts feedback polarity."
        ),
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
    },
    "pair-0665": {
        "compatibility_label": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "expected_compatibility": "incompatible",
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
        "reason": (
            "Dormant-or-close guidance differs from delete-account and "
            "erase-PII steps; same product topic but different user goals."
        ),
    },
    "pair-0675": {
        "compatibility_label": "incompatible",
        "reusable": False,
        "expected_reuse": False,
        "expected_compatibility": "incompatible",
        "failure_category": "intent_mismatch",
        "coverage_category": "intent_change",
        "reason": (
            "Top-up frequency policy differs from maximum top-up amount; "
            "adjacent banking intents must not cross-serve."
        ),
    },
}


def apply_remediation(records: list[BenchmarkRecord]) -> tuple[list[BenchmarkRecord], list[str]]:
    updated_ids: list[str] = []
    out: list[BenchmarkRecord] = []
    for record in records:
        patch = REMEDIATION_OVERRIDES.get(record.id)
        if not patch:
            out.append(record)
            continue
        payload = record.model_dump(mode="json")
        payload.update(patch)
        updated = BenchmarkRecord.model_validate(payload)
        validate_candidate_record(updated)
        out.append(updated)
        updated_ids.append(record.id)
    return out, updated_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("benchmarks/candidates/fresh_held_out_reviewed.jsonl"),
    )
    parser.add_argument(
        "--draft",
        type=Path,
        default=Path("benchmarks/candidates/fresh_held_out_draft.jsonl"),
    )
    args = parser.parse_args(argv)

    records = load_benchmark_jsonl(args.input)
    remediated, touched = apply_remediation(records)
    validate_review_policy(remediated, split="held-out")
    write_candidate_jsonl(args.input, remediated)

    if args.draft.is_file():
        draft_records = load_benchmark_jsonl(args.draft)
        draft_out, _ = apply_remediation(draft_records)
        write_candidate_jsonl(args.draft, draft_out)

    compat = Counter(r.compatibility_label for r in remediated)
    print(
        json.dumps(
            {
                "updated_ids": touched,
                "compatibility_counts": dict(compat),
                "compatible": compat.get("compatible", 0),
                "incompatible": compat.get("incompatible", 0),
                "uncertain": compat.get("uncertain", 0),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
