"""Failure gallery enrichment and read-only quality analysis (Workstream 7).

See ``docs/phase-2/FAILURE_GALLERY_CONTRACT_v1.md``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sscre.benchmark import BenchmarkRecord, load_benchmark_jsonl
from sscre.evaluation_labels import build_evaluation_labels

DEFAULT_HELD_OUT_BENCHMARK_PATH = Path("benchmarks/held_out_test.jsonl")
from sscre.freshness_artifacts import validate_freshness_artifact_package
from sscre.serialization import validate_redacted_report_payload

CATEGORY_SOURCE_REVIEWED = "reviewed_benchmark"
CATEGORY_SOURCE_RUNTIME = "runtime_outcome"

MITIGATION_COMPATIBILITY_VALIDATOR = "compatibility_validator"
MITIGATION_EMBEDDING_SIMILARITY = "embedding_similarity_threshold"
MITIGATION_UNKNOWN = "unknown"

RUNTIME_FAILURE_CATEGORY_DISPLAY: dict[str, str] = {
    "false_positive": "Strategy C compatibility false positive",
    "false_negative": "Strategy C compatibility false negative",
    "unnecessary_abstention": "Strategy C unnecessary abstention",
}

REVIEWED_FAILURE_CATEGORY_DISPLAY: dict[str, str] = {
    "none": "Reviewed: no failure category (compatible reuse)",
    "constraint_mismatch": "Reviewed: constraint mismatch",
    "entity_mismatch": "Reviewed: entity mismatch",
    "intent_mismatch": "Reviewed: intent mismatch",
    "format_mismatch": "Reviewed: format mismatch",
    "domain_mismatch": "Reviewed: domain mismatch",
    "temporal_mismatch": "Reviewed: temporal mismatch",
    "ambiguity": "Reviewed: ambiguity",
    "stale_answer": "Reviewed: stale answer",
    "insufficient_evidence": "Reviewed: insufficient evidence",
    "other": "Reviewed: other",
}


def runtime_failure_category_display(category: str) -> str:
    return RUNTIME_FAILURE_CATEGORY_DISPLAY.get(
        category,
        f"Runtime outcome: {category.replace('_', ' ')}",
    )


def reviewed_failure_category_display(category: str) -> str:
    return REVIEWED_FAILURE_CATEGORY_DISPLAY.get(
        category,
        f"Reviewed: {category.replace('_', ' ')}",
    )


def bounded_evaluation_labels_for_gallery(labels: object) -> dict[str, object]:
    """Export only compatibility (and optional annotation) from label records."""
    if not isinstance(labels, dict):
        return {}
    compatibility = labels.get("compatibility")
    if not isinstance(compatibility, dict):
        return {}
    bounded: dict[str, object] = {"compatibility": dict(compatibility)}
    annotation = labels.get("annotation")
    if isinstance(annotation, dict) and annotation:
        bounded["annotation"] = dict(annotation)
    return bounded


def _pair_key(example: Mapping[str, object]) -> tuple[str, str]:
    pair_id = example.get("id")
    direction = example.get("direction")
    if not isinstance(pair_id, str) or not isinstance(direction, str):
        raise ValueError("gallery example requires string id and direction")
    return pair_id, direction


def _enrich_embedding_example(
    example: dict[str, object],
    *,
    record: BenchmarkRecord | None,
    caught_by_strategy_c: bool,
) -> dict[str, object]:
    enriched = dict(example)
    if record is not None and record.failure_category is not None:
        category = record.failure_category
        enriched["failure_category"] = category
        enriched["category_source"] = CATEGORY_SOURCE_REVIEWED
        enriched["failure_category_display"] = reviewed_failure_category_display(
            category
        )
    else:
        enriched["category_unavailable"] = True
        enriched["category_unavailable_reason"] = (
            "benchmark_failure_category_missing"
        )
        enriched["category_source"] = CATEGORY_SOURCE_REVIEWED
    if caught_by_strategy_c:
        enriched["mitigation"] = MITIGATION_COMPATIBILITY_VALIDATOR
        enriched["open_limitation"] = (
            "embedding_unsafe_reuse_blocked_by_strategy_c"
        )
    else:
        enriched["mitigation"] = MITIGATION_EMBEDDING_SIMILARITY
        enriched["open_limitation"] = "similarity_threshold_only_unsafe_reuse"
    if record is not None:
        labels = build_evaluation_labels(
            record=record,
            observed_decision="SAFE",
        ).to_artifact_dict()
        bounded = bounded_evaluation_labels_for_gallery(labels)
        if bounded:
            enriched["evaluation_labels"] = bounded
    return enriched


def _strategy_c_mitigation(failure_category: str) -> tuple[str, str | None]:
    if failure_category == "unnecessary_abstention":
        return MITIGATION_COMPATIBILITY_VALIDATOR, None
    if failure_category == "false_positive":
        return MITIGATION_UNKNOWN, "residual_compatibility_false_positive"
    if failure_category == "false_negative":
        return MITIGATION_UNKNOWN, "residual_unsafe_on_compatible_expectation"
    return MITIGATION_UNKNOWN, None


def _enrich_strategy_c_example(example: dict[str, object]) -> dict[str, object]:
    enriched = dict(example)
    category = enriched.get("failure_category")
    if isinstance(category, str):
        enriched["category_source"] = CATEGORY_SOURCE_RUNTIME
        enriched["failure_category_display"] = runtime_failure_category_display(
            category
        )
        mitigation, open_limitation = _strategy_c_mitigation(category)
        enriched["mitigation"] = mitigation
        if open_limitation is not None:
            enriched["open_limitation"] = open_limitation
    labels = enriched.get("evaluation_labels")
    if labels is not None:
        bounded = bounded_evaluation_labels_for_gallery(labels)
        if bounded:
            enriched["evaluation_labels"] = bounded
        else:
            enriched.pop("evaluation_labels", None)
    return enriched


def enrich_failure_gallery(
    gallery: Mapping[str, object],
    records: Sequence[BenchmarkRecord],
) -> dict[str, list[dict[str, object]]]:
    """Add category display, mitigation metadata, and bounded labels to gallery rows."""
    records_by_id = {record.id: record for record in records}
    caught_keys = frozenset(
        _pair_key(example)
        for example in gallery.get(
            "embedding_only_false_positives_caught_by_strategy_c", []
        )
        if isinstance(example, dict)
    )
    result: dict[str, list[dict[str, object]]] = {}
    for section, examples in gallery.items():
        if not isinstance(examples, list):
            raise ValueError(f"failure_gallery.{section} must be a list")
        enriched_rows: list[dict[str, object]] = []
        for example in examples:
            if not isinstance(example, dict):
                raise ValueError(f"failure_gallery.{section} entries must be objects")
            if section in (
                "embedding_only_false_positives",
                "embedding_only_false_positives_caught_by_strategy_c",
            ):
                pair_id, direction = _pair_key(example)
                record = records_by_id.get(pair_id)
                enriched_rows.append(
                    _enrich_embedding_example(
                        dict(example),
                        record=record,
                        caught_by_strategy_c=(pair_id, direction) in caught_keys,
                    )
                )
            elif section == "strategy_c_failures":
                enriched_rows.append(_enrich_strategy_c_example(dict(example)))
            else:
                enriched_rows.append(dict(example))
        result[str(section)] = enriched_rows
    return result


def _compatibility_cache_strata(
    payload: Mapping[str, object],
) -> dict[str, object]:
    statistics = payload.get("statistics")
    if not isinstance(statistics, dict):
        raise ValueError("comparison payload missing statistics")
    by_baseline = statistics.get("by_baseline")
    if not isinstance(by_baseline, dict):
        raise ValueError("statistics.by_baseline required for quality_analysis")
    compatibility = by_baseline.get("compatibility-cache")
    if not isinstance(compatibility, dict):
        raise ValueError("statistics.by_baseline.compatibility-cache required")
    strata = compatibility.get("strata")
    if not isinstance(strata, dict):
        raise ValueError("compatibility-cache.strata required")
    return strata


def _annotate_sparse_stratum(summary: dict[str, object]) -> dict[str, object]:
    """Flag strata below declared minimum_n_proportion as diagnostic-only."""
    annotated = dict(summary)
    sample_count = annotated.get("sample_count")
    minimum_n = annotated.get("minimum_n_proportion")
    if (
        isinstance(sample_count, int)
        and isinstance(minimum_n, int)
        and sample_count < minimum_n
    ):
        flags = list(annotated.get("diagnostic_flags") or [])
        if "sparse_sample" not in flags:
            flags.append("sparse_sample")
        annotated["diagnostic_flags"] = flags
    return annotated


def _copy_strata_block(block: object) -> dict[str, dict[str, object]]:
    if not isinstance(block, dict):
        return {}
    copied: dict[str, dict[str, object]] = {}
    for label, summary in block.items():
        if isinstance(label, str) and isinstance(summary, dict):
            copied[label] = _annotate_sparse_stratum(dict(summary))
    return copied


def build_quality_analysis(comparison_payload: Mapping[str, object]) -> dict[str, object]:
    """Build read-only quality tables from WS5 comparison statistics."""
    statistics = comparison_payload.get("statistics")
    if not isinstance(statistics, dict):
        raise ValueError("comparison payload missing statistics")
    strata = _compatibility_cache_strata(comparison_payload)
    by_failure_category = strata.get("by_failure_category")
    if not isinstance(by_failure_category, dict):
        raise ValueError("strata.by_failure_category required")
    by_freshness_class = _copy_strata_block(strata.get("by_freshness_class"))
    enriched_categories = _copy_strata_block(by_failure_category)
    sparse_failure_categories = sorted(
        category
        for category, summary in enriched_categories.items()
        if "sparse_sample" in (summary.get("diagnostic_flags") or [])
    )
    by_baseline = statistics.get("by_baseline")
    compatibility = (
        by_baseline.get("compatibility-cache") if isinstance(by_baseline, dict) else None
    )
    quality: dict[str, object] = {
        "source_baseline": "compatibility-cache",
        "statistics_schema_version": statistics.get("statistics_schema_version"),
        "sample_unit": (
            compatibility.get("sample_unit")
            if isinstance(compatibility, dict)
            else None
        )
        or statistics.get("sample_unit"),
        "by_failure_category": enriched_categories,
    }
    if by_freshness_class:
        quality["by_freshness_class"] = by_freshness_class
    if sparse_failure_categories:
        quality["sparse_failure_categories"] = sparse_failure_categories
    return quality


def extract_by_failure_category_strata(
    payload: Mapping[str, object],
) -> dict[str, dict[str, Any]]:
    """Resolve failure-category strata from comparison or legacy report shapes."""
    try:
        strata = _compatibility_cache_strata(payload)
        by_category = strata.get("by_failure_category")
        if isinstance(by_category, dict):
            return dict(by_category)
    except ValueError:
        pass
    statistics = payload.get("statistics")
    if not isinstance(statistics, dict):
        return {}
    legacy_strata = statistics.get("strata")
    if isinstance(legacy_strata, dict):
        by_category = legacy_strata.get("by_failure_category")
        if isinstance(by_category, dict):
            return dict(by_category)
    return {}


def quality_analysis_category_rows(
    payload: Mapping[str, object],
) -> list[dict[str, Any]]:
    """Flatten category strata for static HTML export (point estimates when present)."""
    strata = extract_by_failure_category_strata(payload)
    rows: list[dict[str, Any]] = []
    for category in sorted(strata):
        summary = strata[category]
        if not isinstance(summary, dict):
            continue
        proportions = summary.get("proportions")
        false_positive_rate = None
        if isinstance(proportions, dict):
            fp_interval = proportions.get("false_positive_rate")
            if isinstance(fp_interval, dict):
                false_positive_rate = fp_interval.get("point")
        row: dict[str, Any] = {
            "category": category,
            "sample_count": summary.get("sample_count"),
            "false_positive_rate": false_positive_rate,
        }
        diagnostic_flags = summary.get("diagnostic_flags")
        if diagnostic_flags:
            row["diagnostic_flags"] = diagnostic_flags
        rows.append(row)
    return rows


def _benchmark_manifest_sha256(report: Mapping[str, object]) -> str | None:
    artifact = report.get("benchmark_artifact")
    if not isinstance(artifact, dict):
        return None
    manifest_sha = artifact.get("split_manifest_sha256")
    return manifest_sha if isinstance(manifest_sha, str) else None


def _selected_policy_name(freshness_experiment: Mapping[str, object]) -> str | None:
    selected = freshness_experiment.get("selected_policy")
    if isinstance(selected, dict):
        name = selected.get("name")
        if isinstance(name, str) and name:
            return name
    stale = freshness_experiment.get("stale_exposure_accounting")
    if isinstance(stale, dict):
        policy_name = stale.get("policy_name")
        if isinstance(policy_name, str) and policy_name:
            return policy_name
    return None


def build_freshness_failure_companion_unavailable(
    *,
    source_artifact_path: str,
    reason: str,
    dataset_version: str = "unknown",
    measurement_environment: str = "unknown",
) -> dict[str, object]:
    """Explicit unavailable companion block when WS6 input is missing or invalid."""
    path = source_artifact_path.strip() or (
        "artifacts/evaluation/workstream6-held-out-freshness.json"
    )
    return {
        "unavailable": True,
        "reason": reason,
        "source_artifact_path": path,
        "measurement_environment": measurement_environment,
        "dataset_version": dataset_version,
    }


def build_freshness_failure_companion_from_report(
    report: Mapping[str, object],
    *,
    source_artifact_path: str,
) -> dict[str, object]:
    """Copy bounded WS6 stale-exposure summaries (no freshness replay)."""
    freshness = report.get("freshness_experiment")
    if not isinstance(freshness, dict):
        raise ValueError("freshness report missing freshness_experiment")
    stale_exposure = freshness.get("stale_exposure_accounting")
    if not isinstance(stale_exposure, dict):
        raise ValueError("freshness_experiment missing stale_exposure_accounting")
    protection_counts = stale_exposure.get("protection_counts")
    if not isinstance(protection_counts, dict):
        raise ValueError("stale_exposure_accounting missing protection_counts")
    validate_redacted_report_payload(stale_exposure)
    validate_redacted_report_payload(protection_counts)
    dataset_version = report.get("dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version:
        raise ValueError("freshness report missing dataset_version")
    measurement_environment = report.get("measurement_environment")
    if not isinstance(measurement_environment, str) or not measurement_environment:
        measurement_environment = freshness.get("measurement_environment")
    if not isinstance(measurement_environment, str) or not measurement_environment:
        raise ValueError("freshness report missing measurement_environment")
    companion: dict[str, object] = {
        "source_artifact_path": source_artifact_path,
        "source_schema_version": report.get("freshness_evaluation_schema_version"),
        "measurement_environment": measurement_environment,
        "dataset_version": dataset_version,
        "split_manifest_sha256": _benchmark_manifest_sha256(report),
        "selected_policy": _selected_policy_name(freshness),
        "stale_exposure_accounting": dict(stale_exposure),
        "protection_counts": dict(protection_counts),
    }
    held_out_scope = freshness.get("held_out_freshness_scope")
    if isinstance(held_out_scope, dict):
        companion["held_out_freshness_scope"] = dict(held_out_scope)
    return companion


def load_held_out_records_for_gallery(
    *,
    benchmark_path: Path | None = None,
) -> list[BenchmarkRecord]:
    path = benchmark_path or DEFAULT_HELD_OUT_BENCHMARK_PATH
    return load_benchmark_jsonl(path, require_final_review=True)


def audit_false_positive_category_completeness(
    gallery: Mapping[str, object],
) -> list[str]:
    """Return pair keys (id:direction) missing category or category_unavailable."""
    missing: list[str] = []
    for section in (
        "embedding_only_false_positives",
        "embedding_only_false_positives_caught_by_strategy_c",
    ):
        examples = gallery.get(section)
        if not isinstance(examples, list):
            continue
        for example in examples:
            if not isinstance(example, dict):
                continue
            if example.get("failure_category") or example.get("category_unavailable"):
                continue
            pair_id = example.get("id")
            direction = example.get("direction")
            missing.append(f"{pair_id}:{direction}")
    return missing


def build_freshness_failure_companion(
    freshness_artifact_path: Path | str | None,
    *,
    validate_artifact: bool = True,
) -> dict[str, object]:
    """Load WS6 held-out freshness JSON and build the WS7 companion block."""
    if freshness_artifact_path is None:
        return build_freshness_failure_companion_unavailable(
            source_artifact_path=(
                "artifacts/evaluation/workstream6-held-out-freshness.json"
            ),
            reason="freshness_companion_path_not_provided",
        )
    path = Path(freshness_artifact_path)
    if not path.is_file():
        return build_freshness_failure_companion_unavailable(
            source_artifact_path=path.as_posix(),
            reason="freshness_companion_artifact_missing",
        )
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("freshness artifact must be a JSON object")
    if validate_artifact:
        validate_freshness_artifact_package(report)
    return build_freshness_failure_companion_from_report(
        report,
        source_artifact_path=path.as_posix(),
    )
