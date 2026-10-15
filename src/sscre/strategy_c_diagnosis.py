"""Research track R1 Step 1.1 — Strategy C diagnostic aggregation (non-headline)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sscre.baseline import run_compatibility_cache_baseline
from sscre.benchmark import load_benchmark_jsonl
from sscre.evaluation_protocol import (
    apply_primary_headline_population_filter,
    resolve_semantic_embedding_client,
)
from sscre.safety import CANDIDATE_TRACE_CONTRACT_VERSION, SAFETY_EVALUATION_CONTRACT_VERSION

DIAGNOSIS_SCHEMA_VERSION = "r1-step11-strategy-c-diagnosis-1.0"
POPULATION_PURPOSE = (
    "development_split_configuration_and_diagnosis_only_not_fresh_headline"
)


def similarity_band(similarity: float | None) -> str:
    if similarity is None:
        return "unknown"
    if similarity >= 1.0:
        return "1.0"
    if similarity >= 0.95:
        return "[0.95,1.0)"
    if similarity >= 0.9:
        return "[0.9,0.95)"
    if similarity >= 0.8:
        return "[0.8,0.9)"
    return "[-1,0.8)"


def _increment(table: dict[str, int], key: str, amount: int = 1) -> None:
    table[key] = table.get(key, 0) + amount


def _reason_category(reason: str) -> str:
    if reason.startswith("missing_") and reason.endswith("_evidence"):
        return "missing_metadata_evidence"
    if reason.startswith("constraint_mismatch:"):
        return "metadata_conflict"
    if reason in {
        "entity_mismatch",
        "intent_mismatch",
        "domain_mismatch",
        "format_mismatch",
        "temporal_class_mismatch",
        "incomplete_constraint_evidence",
        "incomplete_entity_evidence",
    }:
        return "metadata_conflict"
    if reason in {"candidate_metadata_missing"}:
        return "missing_metadata_evidence"
    if reason == "similarity_below_threshold":
        return "below_threshold"
    if reason == "exact_query_hash_match":
        return "exact_hash"
    if reason == "compatible_metadata":
        return "compatible"
    return "other"


def extract_compatibility_report(payload: Mapping[str, object]) -> dict[str, object]:
    baseline = payload.get("baseline")
    if baseline == "compatibility-cache":
        return dict(payload)
    baselines = payload.get("baselines")
    if isinstance(baselines, Mapping):
        section = baselines.get("compatibility-cache")
        if isinstance(section, Mapping):
            return dict(section)
    raise ValueError(
        "report must be compatibility-cache or a comparison with baselines.compatibility-cache"
    )


def extract_exact_cache_summary(payload: Mapping[str, object]) -> dict[str, int] | None:
    baselines = payload.get("baselines")
    if not isinstance(baselines, Mapping):
        return None
    section = baselines.get("exact-cache")
    if not isinstance(section, Mapping):
        return None
    return {
        "cache_hits": int(section.get("cache_hits", 0)),
        "cache_misses": int(section.get("cache_misses", 0)),
        "request_count": int(section.get("request_count", 0)),
    }


def aggregate_strategy_c_diagnosis(
    compatibility_report: Mapping[str, object],
    *,
    exact_cache_summary: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """Aggregate redacted Strategy C trace statistics from a compatibility report."""

    trace_decision_counts: dict[str, int] = {}
    trace_reason_counts: dict[str, int] = {}
    trace_stage_counts: dict[str, int] = {}
    trace_reason_category_counts: dict[str, int] = {}
    similarity_band_counts: dict[str, int] = {}
    freshness_outcome_counts: dict[str, int] = {}
    cache_control_outcome_counts: dict[str, int] = {}

    observed_rows = compatibility_report.get("observed_pair_records")
    if not isinstance(observed_rows, list):
        observed_rows = []

    request_path_counts = {
        "exact_hash_trace": 0,
        "semantic_with_candidates": 0,
        "no_candidates": 0,
    }
    request_outcome_counts = {
        "served_safe": 0,
        "rejected_with_candidates": 0,
        "no_candidates": 0,
    }

    for row in observed_rows:
        if not isinstance(row, Mapping):
            continue
        traces = row.get("candidate_traces")
        if not isinstance(traces, list):
            traces = []
        observed = row.get("observed_decision")
        if not traces:
            request_path_counts["no_candidates"] += 1
            request_outcome_counts["no_candidates"] += 1
        else:
            has_exact = any(
                isinstance(trace, Mapping)
                and trace.get("reason") == "exact_query_hash_match"
                for trace in traces
            )
            if has_exact:
                request_path_counts["exact_hash_trace"] += 1
            else:
                request_path_counts["semantic_with_candidates"] += 1
            if observed == "SAFE":
                request_outcome_counts["served_safe"] += 1
            else:
                request_outcome_counts["rejected_with_candidates"] += 1

        for trace in traces:
            if not isinstance(trace, Mapping):
                continue
            decision = trace.get("decision")
            if isinstance(decision, str):
                _increment(trace_decision_counts, decision)
            reason = trace.get("reason")
            if isinstance(reason, str):
                _increment(trace_reason_counts, reason)
                _increment(trace_reason_category_counts, _reason_category(reason))
            stage = trace.get("stage")
            if isinstance(stage, str):
                _increment(trace_stage_counts, stage)
            similarity = trace.get("similarity")
            band = similarity_band(
                float(similarity) if isinstance(similarity, (int, float)) else None
            )
            _increment(similarity_band_counts, band)
            freshness = trace.get("freshness_class")
            if isinstance(freshness, str):
                _increment(freshness_outcome_counts, freshness)
            control = trace.get("cache_control_outcome")
            if isinstance(control, str):
                _increment(cache_control_outcome_counts, control)

    failure_categories = compatibility_report.get("failure_categories")
    if not isinstance(failure_categories, Mapping):
        failure_categories = {}

    report_control = compatibility_report.get("cache_control_outcome_counts")
    if isinstance(report_control, Mapping):
        for key, value in report_control.items():
            if isinstance(key, str) and isinstance(value, int):
                cache_control_outcome_counts[key] = (
                    cache_control_outcome_counts.get(key, 0) + value
                )

    decision_counts = compatibility_report.get("decision_counts")
    if not isinstance(decision_counts, Mapping):
        decision_counts = {}

    candidate_availability = {
        "observed_pair_sample_count": len(observed_rows),
        "requests_with_candidates": (
            request_path_counts["exact_hash_trace"]
            + request_path_counts["semantic_with_candidates"]
        ),
        "requests_without_candidates": request_path_counts["no_candidates"],
        "semantic_miss_failure_category": int(
            failure_categories.get("semantic_miss", 0)
        ),
    }
    candidate_rejection = {
        "served_safe": request_outcome_counts["served_safe"],
        "rejected_with_candidates": request_outcome_counts["rejected_with_candidates"],
        "no_candidates": request_outcome_counts["no_candidates"],
        "failure_categories": dict(failure_categories),
    }

    exact_vs_semantic = {
        "strategy_c_request_paths": request_path_counts,
        "strategy_c_request_outcomes": request_outcome_counts,
    }
    if exact_cache_summary is not None:
        exact_vs_semantic["strategy_a_exact_cache"] = dict(exact_cache_summary)
        exact_vs_semantic["strategy_c_compatibility_cache"] = {
            "cache_hits": int(compatibility_report.get("cache_hits", 0)),
            "cache_misses": int(compatibility_report.get("cache_misses", 0)),
            "request_count": int(compatibility_report.get("request_count", 0)),
        }

    return {
        "trace_decision_counts": trace_decision_counts,
        "trace_reason_counts": trace_reason_counts,
        "trace_reason_category_counts": trace_reason_category_counts,
        "trace_stage_counts": trace_stage_counts,
        "similarity_band_counts": similarity_band_counts,
        "freshness_outcome_counts": freshness_outcome_counts,
        "cache_control_outcome_counts": cache_control_outcome_counts,
        "request_decision_counts": dict(decision_counts),
        "candidate_availability": candidate_availability,
        "candidate_rejection": candidate_rejection,
        "exact_vs_semantic": exact_vs_semantic,
        "unlabeled_candidate_reuse_hits": int(
            compatibility_report.get("unlabeled_candidate_reuse_hits", 0)
        ),
        "abstention_rate": compatibility_report.get("abstention_rate"),
        "safe_reuse_coverage": compatibility_report.get("safe_reuse_coverage"),
        "hit_rate": compatibility_report.get("hit_rate"),
    }


def _repo_relative_path(path: Path) -> str:
    root = Path(__file__).resolve().parents[2]
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _git_dirty() -> bool | None:
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return bool(status.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def build_diagnosis_record(
    *,
    compatibility_report: Mapping[str, object],
    source_evaluation_path: Path | None,
    config_path: Path,
    config: Mapping[str, object],
    benchmark_path: Path,
    population_record_count: int,
    threshold_policy: object,
    embedding_provenance: Mapping[str, object] | None,
    exact_cache_summary: Mapping[str, int] | None,
) -> dict[str, object]:
    aggregates = aggregate_strategy_c_diagnosis(
        compatibility_report,
        exact_cache_summary=exact_cache_summary,
    )
    dominant = _dominant_abstention_causes(aggregates)
    return {
        "schema_version": DIAGNOSIS_SCHEMA_VERSION,
        "workstream": "R1",
        "step": "R1.1",
        "status": "closed",
        "headline_population": False,
        "population_purpose": POPULATION_PURPOSE,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_head(),
        "git_worktree_dirty": _git_dirty(),
        "protocol": {
            "safety_evaluation_contract": SAFETY_EVALUATION_CONTRACT_VERSION,
            "candidate_trace_contract": CANDIDATE_TRACE_CONTRACT_VERSION,
            "config_version": config.get("config_version"),
            "config_sha256": _sha256_file(config_path),
            "protocol_id": config.get("protocol_id"),
        },
        "population": {
            "benchmark_path": _repo_relative_path(benchmark_path),
            "benchmark_sha256": _sha256_file(benchmark_path),
            "record_count": population_record_count,
            "split": "development",
            "held_out_records_used": False,
        },
        "model_identity": {
            "embedding_model": compatibility_report.get("embedding_model"),
            "embedding_dimension": compatibility_report.get("embedding_dimension"),
            "threshold_policy": threshold_policy,
            "top_k": compatibility_report.get("top_k"),
            "embedding_provenance": embedding_provenance,
        },
        "source_evaluation_artifact": (
            _repo_relative_path(source_evaluation_path)
            if source_evaluation_path
            else None
        ),
        "aggregates": aggregates,
        "dominant_abstention_causes": dominant,
        "safety_note": (
            "Diagnostic only; no threshold or compatibility rule changes from this population."
        ),
    }


def _dominant_abstention_causes(aggregates: Mapping[str, object]) -> list[dict[str, object]]:
    rejection = aggregates.get("candidate_rejection")
    if not isinstance(rejection, Mapping):
        return []
    failure_categories = rejection.get("failure_categories")
    if not isinstance(failure_categories, Mapping):
        return []
    ranked = sorted(
        (
            {"category": key, "count": int(value)}
            for key, value in failure_categories.items()
            if isinstance(key, str) and isinstance(value, int)
        ),
        key=lambda row: row["count"],
        reverse=True,
    )
    reason_categories = aggregates.get("trace_reason_category_counts")
    top_reasons: list[dict[str, object]] = []
    if isinstance(reason_categories, Mapping):
        top_reasons = sorted(
            (
                {"category": key, "trace_count": int(value)}
                for key, value in reason_categories.items()
                if isinstance(key, str) and isinstance(value, int)
            ),
            key=lambda row: row["trace_count"],
            reverse=True,
        )[:5]
    return [
        {
            "failure_category_ranking": ranked[:5],
            "trace_reason_category_ranking": top_reasons,
        }
    ]


def diagnose_from_evaluation_report(
    report_path: Path,
    *,
    config_path: Path,
    benchmark_path: Path,
    config: Mapping[str, object],
    population_record_count: int,
) -> dict[str, object]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("evaluation report must be a JSON object")
    compatibility = extract_compatibility_report(payload)
    exact_summary = extract_exact_cache_summary(payload)
    threshold = compatibility.get("threshold")
    provenance = payload.get("embedding_provenance")
    if not isinstance(provenance, Mapping):
        provenance = None
    return build_diagnosis_record(
        compatibility_report=compatibility,
        source_evaluation_path=report_path,
        config_path=config_path,
        config=config,
        benchmark_path=benchmark_path,
        population_record_count=population_record_count,
        threshold_policy=threshold,
        embedding_provenance=provenance,
        exact_cache_summary=exact_summary,
    )


def run_replay_diagnosis(
    *,
    config_path: Path,
    benchmark_path: Path,
    config: Mapping[str, object],
) -> dict[str, object]:
    from sscre.evaluate import _embedding_run_options, _select_development_threshold

    records = load_benchmark_jsonl(benchmark_path)
    records, _ = apply_primary_headline_population_filter(records, config)
    embedding_client = resolve_semantic_embedding_client(config)
    selection = _select_development_threshold(
        benchmark_path,
        dict(config),
        embedding_client=embedding_client,
    )
    embed_options = _embedding_run_options(dict(config), embedding_client)
    report = run_compatibility_cache_baseline(
        records,
        dataset_version=str(config["dataset_version"]),
        threshold=selection.selected_threshold,
        top_k=int(config["embedding_top_k"]),
        **embed_options,
        collect_request_samples=False,
    )
    provenance: dict[str, object] | None = None
    if embedding_client is not None:
        provenance = {
            "model_name": embedding_client.config.model_name,
            "dimension": embedding_client.config.dimension,
        }
    return build_diagnosis_record(
        compatibility_report=asdict(report),
        source_evaluation_path=None,
        config_path=config_path,
        config=config,
        benchmark_path=benchmark_path,
        population_record_count=len(records),
        threshold_policy=selection.selected_threshold,
        embedding_provenance=provenance,
        exact_cache_summary=None,
    )


def write_diagnosis_record(record: Mapping[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
