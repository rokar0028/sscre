"""Convert filtered CacheEval JSONL to SSCRE benchmark candidates (schema 1.1)."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import sys

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from sscre.benchmark import BenchmarkRecord, BenchmarkValidationError, load_benchmark_jsonl
from sscre.benchmark_build import assign_next_pair_id, validate_candidate_record
from sscre.benchmark_splits import normalized_pair_key
from sscre.query import normalize_query

from filter_cacheeval_commercial import load_jsonl

DEFAULT_DOMAINS = (
    "qa_factual",
    "qa_open",
    "conversational",
    "math",
    "code",
)
SOURCE_GROUP = "cacheeval_v1:filtered"
ANNOTATION_SOURCE = "cacheeval_provisional"
METADATA_VALUE_MAX = 256


def _clip(text: str, limit: int = METADATA_VALUE_MAX) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _pair_key_from_queries(query_a: str, query_b: str) -> tuple[str, str]:
    return (normalize_query(query_a), normalize_query(query_b))


def _infer_related_unsafe(
    subcategory: str,
) -> tuple[str, str]:
    sub = subcategory.lower()
    if any(token in sub for token in ("entity", "capital", "population", "rename")):
        return "entity_change", "entity_mismatch"
    if any(token in sub for token in ("intent", "banking", "domain")):
        return "intent_change", "intent_mismatch"
    if any(token in sub for token in ("format", "json", "yaml", "markdown")):
        return "format_change", "format_mismatch"
    if any(token in sub for token in ("temporal", "time", "date", "current")):
        return "temporal_freshness", "temporal_mismatch"
    return "constraint_change", "constraint_mismatch"


def map_cacheeval_row(row: dict) -> dict:
    """Map one CacheEval row to a schema 1.1 candidate payload (no SSCRE id yet)."""
    label = row.get("label") or ""
    verification = row.get("verification_method") or ""
    domain = (row.get("domain") or "")[:64]
    subcategory = row.get("subcategory") or ""
    query_a = (row.get("query_a") or "").strip()
    query_b = (row.get("query_b") or "").strip()
    if not query_a or not query_b:
        raise ValueError("missing query text")

    policy_no_cache = verification == "policy_no_cache"
    norm_a = normalize_query(query_a)
    norm_b = normalize_query(query_b)
    rationale = _clip(row.get("rationale") or "CacheEval provisional mapping", 512)

    if label in {"EQUIV", "PARA_SAFE"}:
        compatibility_label = "compatible"
        if policy_no_cache:
            reusable = False
            coverage_category = "stale_answer"
            failure_category = "stale_answer"
            reason = rationale
        elif norm_a == norm_b and query_a == query_b:
            reusable = True
            coverage_category = "exact_duplicate"
            failure_category = "none"
            reason = None
        elif norm_a == norm_b:
            reusable = True
            coverage_category = "whitespace_variant"
            failure_category = "none"
            reason = None
        elif label == "EQUIV":
            reusable = True
            coverage_category = "low_overlap_compatible"
            failure_category = "none"
            reason = None
        else:
            reusable = True
            coverage_category = "paraphrase"
            failure_category = "none"
            reason = None
    elif label == "ADVERSARIAL":
        compatibility_label = "incompatible"
        reusable = False
        coverage_category = "high_similarity_incompatible"
        failure_category = "constraint_mismatch"
        reason = rationale
    elif label == "UNRELATED":
        compatibility_label = "incompatible"
        reusable = False
        coverage_category = "intent_change"
        failure_category = "intent_mismatch"
        reason = rationale
    elif label == "RELATED_UNSAFE":
        compatibility_label = "incompatible"
        reusable = False
        coverage_category, failure_category = _infer_related_unsafe(subcategory)
        reason = rationale
    else:
        raise ValueError(f"unsupported CacheEval label {label!r}")

    freshness_class = "stable"
    if domain in {"qa_factual", "qa_open"} and any(
        token in subcategory.lower() for token in ("current", "today", "rate", "price")
    ):
        freshness_class = "semi_dynamic"

    upstream_id = row.get("id") or ""
    return {
        "schema_version": "1.1",
        "query_a": query_a,
        "query_b": query_b,
        "directionality": "ordered",
        "reusable": reusable,
        "correctness_label": None,
        "compatibility_label": compatibility_label,
        "reason": reason,
        "failure_category": failure_category,
        "coverage_category": coverage_category,
        "freshness_class": freshness_class,
        "metadata": {
            "intent": _clip(f"cacheeval:{upstream_id}", 64),
            "domain": domain or None,
            "entities": [],
            "constraints": {
                "cacheeval_label": _clip(label, METADATA_VALUE_MAX),
                "cacheeval_subcategory": _clip(subcategory, METADATA_VALUE_MAX),
            },
            "temporal_class": None,
            "output_format": None,
        },
        "answer_availability": "none",
        "review_status": "draft",
        "annotation_source": ANNOTATION_SOURCE,
        "source_group": SOURCE_GROUP,
    }


def select_cacheeval_rows(
    rows: list[dict],
    *,
    limit: int,
    domains: set[str],
    excluded_pair_keys: set[tuple[str, str]],
    seed: int,
) -> tuple[list[dict], dict[str, int]]:
    """Stratified sample by CacheEval label with dedupe against existing pairs."""
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
        label = row.get("label") or "UNKNOWN"
        buckets[label].append(row)

    rng = random.Random(seed)
    for label_rows in buckets.values():
        rng.shuffle(label_rows)

    labels = sorted(buckets)
    selected: list[dict] = []
    seen_keys: set[tuple[str, str]] = set()
    index = {label: 0 for label in labels}

    while len(selected) < limit and labels:
        progressed = False
        for label in labels:
            if len(selected) >= limit:
                break
            idx = index[label]
            bucket = buckets[label]
            while idx < len(bucket):
                row = bucket[idx]
                idx += 1
                key = _pair_key_from_queries(
                    row.get("query_a", ""), row.get("query_b", "")
                )
                if key in seen_keys:
                    stats["skipped_duplicate_batch"] += 1
                    continue
                seen_keys.add(key)
                excluded_pair_keys.add(key)
                selected.append(row)
                progressed = True
                break
            index[label] = idx
        if not progressed:
            break

    stats["selected"] = len(selected)
    return selected, dict(stats)


def convert_rows(
    cacheeval_rows: list[dict],
    existing_ids: set[str],
) -> tuple[list[BenchmarkRecord], dict[str, int]]:
    records: list[BenchmarkRecord] = []
    stats: dict[str, int] = defaultdict(int)
    used_ids = set(existing_ids)

    for row in cacheeval_rows:
        try:
            payload = map_cacheeval_row(row)
            payload["id"] = assign_next_pair_id(used_ids)
            used_ids.add(payload["id"])
            record = BenchmarkRecord.model_validate(payload)
            validate_candidate_record(record)
        except (ValueError, TypeError, BenchmarkValidationError):
            stats["conversion_failed"] += 1
            continue
        records.append(record)
    stats["converted"] = len(records)
    return records, dict(stats)


def write_candidate_jsonl(path: Path, records: list[BenchmarkRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
        for record in records
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def existing_pair_keys(benchmark_dir: Path) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    source = benchmark_dir / "reviewed_query_pairs.jsonl"
    if source.is_file():
        for record in load_benchmark_jsonl(source):
            keys.add(normalized_pair_key(record))
    return keys


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
        default=Path("benchmarks/candidates/cacheeval_batch_01.jsonl"),
    )
    parser.add_argument("--benchmark-dir", type=Path, default=Path("benchmarks"))
    parser.add_argument("--limit", type=int, default=575)
    parser.add_argument("--seed", type=int, default=20261008)
    parser.add_argument(
        "--domains",
        default=",".join(DEFAULT_DOMAINS),
        help="Comma-separated CacheEval domain filter.",
    )
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(
            f"input not found: {args.input} (run filter_cacheeval_commercial.py first)",
            file=sys.stderr,
        )
        return 1

    domains = {part.strip() for part in args.domains.split(",") if part.strip()}
    rows = load_jsonl(args.input)
    pair_keys = existing_pair_keys(args.benchmark_dir)
    selected, select_stats = select_cacheeval_rows(
        rows,
        limit=args.limit,
        domains=domains,
        excluded_pair_keys=pair_keys,
        seed=args.seed,
    )

    existing_ids = {
        record.id for record in load_benchmark_jsonl(args.benchmark_dir / "reviewed_query_pairs.jsonl")
    }
    records, convert_stats = convert_rows(selected, existing_ids)
    if not records:
        print("no candidates converted", file=sys.stderr)
        return 1

    write_candidate_jsonl(args.output, records)
    summary = {
        "input_rows": len(rows),
        "select_stats": select_stats,
        "convert_stats": convert_stats,
        "output_count": len(records),
        "first_id": records[0].id,
        "last_id": records[-1].id,
        "domains": sorted(domains),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
