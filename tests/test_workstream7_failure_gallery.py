"""Workstream 7 failure gallery contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.benchmark import BenchmarkRecord
from sscre.failure_gallery import (
    FAILURE_GALLERY_SCHEMA_VERSION,
    attach_failure_gallery_schema,
    package_consolidated_quality_analysis,
    validate_consolidated_quality_analysis,
    validate_failure_gallery,
    validate_freshness_failure_companion,
    write_consolidated_quality_analysis,
)
from sscre.failure_quality import (
    MITIGATION_COMPATIBILITY_VALIDATOR,
    MITIGATION_EMBEDDING_SIMILARITY,
    build_freshness_failure_companion,
    build_freshness_failure_companion_unavailable,
    build_quality_analysis,
    enrich_failure_gallery,
    quality_analysis_category_rows,
)
from sscre.serialization import (
    attach_evaluation_report_schema,
    redact_operational_evaluation_report,
    validate_redacted_report_payload,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HELD_OUT_COMPARISON = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream5-held-out-comparison.json"
)
_HELD_OUT_FRESHNESS = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream6-held-out-freshness.json"
)
_HELD_OUT_QUALITY = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream7-quality-analysis.json"
)


def _freshness_copy_with_manifest_sha(
    tmp_path: Path,
    *,
    manifest_sha256: str,
) -> Path:
    payload = json.loads(_HELD_OUT_FRESHNESS.read_text(encoding="utf-8"))
    artifact = payload.setdefault("benchmark_artifact", {})
    if not isinstance(artifact, dict):
        raise TypeError("benchmark_artifact must be an object")
    artifact["split_manifest_sha256"] = manifest_sha256
    path = tmp_path / "workstream6-held-out-freshness-mismatch.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _minimal_gallery() -> dict[str, list[dict[str, object]]]:
    embedding = [
        {
            "id": "pair-0001",
            "direction": "b_to_a",
            "similarity": 0.99,
            "reason": "reviewed",
        }
    ]
    strategy_c = [
        {
            "id": "pair-0002",
            "direction": "a_to_b",
            "similarity": 0.88,
            "reason": "all candidates were incompatible",
            "predicted_decision": "UNSAFE",
            "expected_reusable": False,
            "expected_compatibility": "compatible",
            "failure_category": "false_negative",
        }
    ]
    return {
        "embedding_only_false_positives": embedding,
        "embedding_only_false_positives_caught_by_strategy_c": list(embedding),
        "strategy_c_failures": strategy_c,
    }


def _sample_record() -> BenchmarkRecord:
    return BenchmarkRecord.model_validate(
        {
            "schema_version": "1.1",
            "id": "pair-0001",
            "query_a": "q a",
            "query_b": "q b",
            "reusable": False,
            "compatibility_label": "incompatible",
            "failure_category": "intent_mismatch",
            "coverage_category": "intent_change",
            "review_status": "final",
            "reason": "reviewed reason",
        }
    )


def test_enrich_embedding_example_adds_reviewed_category_and_mitigation() -> None:
    gallery = _minimal_gallery()
    enriched = enrich_failure_gallery(gallery, [_sample_record()])
    row = enriched["embedding_only_false_positives_caught_by_strategy_c"][0]
    assert row["failure_category"] == "intent_mismatch"
    assert row["mitigation"] == MITIGATION_COMPATIBILITY_VALIDATOR
    assert row["category_source"] == "reviewed_benchmark"
    assert "failure_category_display" in row
    labels = row.get("evaluation_labels")
    assert isinstance(labels, dict)
    assert "compatibility" in labels
    assert "correctness" not in labels


def test_enrich_strategy_c_adds_runtime_display_and_bounded_labels() -> None:
    record = BenchmarkRecord.model_validate(
        {
            "schema_version": "1.1",
            "id": "pair-0002",
            "query_a": "q a",
            "query_b": "q b",
            "reusable": True,
            "compatibility_label": "compatible",
            "failure_category": "none",
            "coverage_category": "paraphrase",
            "review_status": "final",
            "reason": "ok",
        }
    )
    gallery = _minimal_gallery()
    gallery["strategy_c_failures"][0]["evaluation_labels"] = {
        "compatibility": {
            "expected_decision": "SAFE",
            "observed_decision": "UNSAFE",
        },
        "correctness": {"cached_answer": None, "generated_answer": None},
        "preference": {"winner": None, "applicable": False},
    }
    enriched = enrich_failure_gallery(gallery, [_sample_record(), record])
    row = enriched["strategy_c_failures"][0]
    assert row["category_source"] == "runtime_outcome"
    assert row["failure_category_display"].startswith("Strategy C")
    assert row["mitigation"] == "unknown"
    labels = row["evaluation_labels"]
    assert "compatibility" in labels
    assert "preference" not in labels


def test_enrich_then_redact_strips_query_text() -> None:
    gallery = _minimal_gallery()
    gallery["embedding_only_false_positives"][0]["query_a"] = "secret"
    enriched = enrich_failure_gallery(gallery, [_sample_record()])
    payload = redact_operational_evaluation_report(
        {"failure_gallery": enriched, "failure_examples": []}
    )
    assert "query_a" not in json.dumps(payload)


def test_attach_adds_schema_version_for_enriched_gallery() -> None:
    enriched = enrich_failure_gallery(_minimal_gallery(), [_sample_record()])
    payload = attach_evaluation_report_schema(
        {"baseline": "comparison", "failure_gallery": enriched}
    )
    assert payload["failure_gallery_schema_version"] == FAILURE_GALLERY_SCHEMA_VERSION


def test_validate_failure_gallery_rejects_forbidden_query_text() -> None:
    from sscre.failure_gallery import validate_failure_gallery_redacted

    gallery = _minimal_gallery()
    gallery["strategy_c_failures"][0]["query_a"] = "secret"
    with pytest.raises(ValueError, match="query_a"):
        validate_failure_gallery_redacted(gallery)


def test_validate_failure_gallery_requires_strategy_c_failure_category() -> None:
    gallery = _minimal_gallery()
    del gallery["strategy_c_failures"][0]["failure_category"]
    with pytest.raises(ValueError, match="failure_category"):
        validate_failure_gallery(gallery)


def test_consolidated_quality_analysis_fixture_validates() -> None:
    payload = {
        "failure_gallery_schema_version": FAILURE_GALLERY_SCHEMA_VERSION,
        "selected_sample": {
            "evaluation_split": "held-out",
            "dataset_version": "reviewed-query-pairs-2.0",
            "directed_request_count": 430,
            "compatibility_threshold": 0.95,
            "measurement_environment": "synthetic_replay",
        },
        "input_artifacts": {
            "comparison": {
                "path": "artifacts/evaluation/workstream5-held-out-comparison.json",
                "schema_version": "1.0.0",
                "statistics_schema_version": "evaluation-statistics-1.0",
                "split_manifest_sha256": "abc",
                "dataset_version": "reviewed-query-pairs-2.0",
            },
            "freshness": {
                "path": "artifacts/evaluation/workstream6-held-out-freshness.json",
                "schema_version": "1.0.0",
                "split_manifest_sha256": "def",
                "dataset_version": "reviewed-query-pairs-2.0",
            },
        },
        "failure_gallery": _minimal_gallery(),
        "quality_analysis": {
            "by_failure_category": {
                "intent_mismatch": {"sample_count": 55, "proportions": {}},
            }
        },
        "freshness_failure_companion": {
            "source_artifact_path": "artifacts/evaluation/workstream6-held-out-freshness.json",
            "measurement_environment": "synthetic_replay",
            "dataset_version": "reviewed-query-pairs-2.0",
            "stale_exposure_accounting": {"numerators": {}},
            "protection_counts": {"dynamic_reuse_blocked_count": 0},
        },
        "unavailable_sections": [
            "correctness_labeled_failures",
            "real_provider_failures",
        ],
        "limitations": ["manifest_mismatch: true"],
    }
    validate_consolidated_quality_analysis(payload)
    attached = attach_failure_gallery_schema(payload)
    assert attached["failure_gallery_schema_version"] == FAILURE_GALLERY_SCHEMA_VERSION


@pytest.mark.skipif(
    not _HELD_OUT_COMPARISON.is_file(),
    reason="checked-in WS5 held-out comparison artifact missing",
)
def test_quality_analysis_category_rows_legacy_statistics_shape() -> None:
    payload = {
        "statistics": {
            "by_baseline": {
                "compatibility-cache": {
                    "strata": {
                        "by_failure_category": {
                            "intent_change": {
                                "sample_count": 10,
                                "proportions": {
                                    "false_positive_rate": {"point": 0.05},
                                },
                            }
                        }
                    }
                }
            }
        }
    }
    rows = quality_analysis_category_rows(payload)
    assert rows == [
        {
            "category": "intent_change",
            "sample_count": 10,
            "false_positive_rate": 0.05,
        }
    ]


def test_build_quality_analysis_copies_interval_metadata_and_sparse_flags() -> None:
    payload = {
        "statistics": {
            "statistics_schema_version": "evaluation-statistics-1.0",
            "sample_unit": "directed_request",
            "by_baseline": {
                "compatibility-cache": {
                    "sample_unit": "directed_request",
                    "strata": {
                        "by_failure_category": {
                            "ambiguity": {
                                "sample_count": 1,
                                "minimum_n_proportion": 5,
                                "proportions": {
                                    "decision_rate_unsafe": {
                                        "point": 1.0,
                                        "method": "wilson",
                                        "n": 1,
                                    }
                                },
                                "interval_methods": {"proportion": "wilson"},
                            }
                        },
                        "by_freshness_class": {
                            "stable": {
                                "sample_count": 400,
                                "minimum_n_proportion": 5,
                                "proportions": {},
                            }
                        },
                    },
                }
            },
        }
    }
    quality = build_quality_analysis(payload)
    assert quality["source_baseline"] == "compatibility-cache"
    assert quality["statistics_schema_version"] == "evaluation-statistics-1.0"
    ambiguity = quality["by_failure_category"]["ambiguity"]
    assert ambiguity["proportions"]["decision_rate_unsafe"]["method"] == "wilson"
    assert ambiguity["diagnostic_flags"] == ["sparse_sample"]
    assert quality["sparse_failure_categories"] == ["ambiguity"]
    assert "stable" in quality["by_freshness_class"]


@pytest.mark.skipif(
    not _HELD_OUT_COMPARISON.is_file(),
    reason="checked-in WS5 held-out comparison artifact missing",
)
def test_freshness_failure_companion_unavailable_when_missing() -> None:
    companion = build_freshness_failure_companion(
        _REPO_ROOT / "artifacts/evaluation/does-not-exist.json"
    )
    validate_freshness_failure_companion(companion)
    assert companion["unavailable"] is True
    assert companion["reason"] == "freshness_companion_artifact_missing"


def test_freshness_failure_companion_unavailable_explicit() -> None:
    companion = build_freshness_failure_companion_unavailable(
        source_artifact_path="artifacts/evaluation/workstream6-held-out-freshness.json",
        reason="manifest_mismatch",
        dataset_version="reviewed-query-pairs-2.0",
        measurement_environment="synthetic_replay",
    )
    validate_freshness_failure_companion(companion)


@pytest.mark.skipif(
    not _HELD_OUT_FRESHNESS.is_file(),
    reason="checked-in WS6 held-out freshness artifact missing",
)
def test_package_consolidated_quality_analysis_rejects_manifest_mismatch(
    tmp_path: Path,
) -> None:
    if not _HELD_OUT_COMPARISON.is_file() or not _HELD_OUT_FRESHNESS.is_file():
        pytest.skip("checked-in WS5/WS6 held-out artifacts missing")
    mismatched = _freshness_copy_with_manifest_sha(
        tmp_path,
        manifest_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="split_manifest_sha256 mismatch"):
        package_consolidated_quality_analysis(
            comparison_path=_HELD_OUT_COMPARISON,
            freshness_companion_path=mismatched,
            allow_manifest_mismatch=False,
        )


@pytest.mark.skipif(
    not _HELD_OUT_COMPARISON.is_file() or not _HELD_OUT_FRESHNESS.is_file(),
    reason="checked-in WS5/WS6 held-out artifacts missing",
)
def test_package_enriches_stale_embedding_gallery_at_pack_time(
    tmp_path: Path,
) -> None:
    if not _HELD_OUT_COMPARISON.is_file():
        pytest.skip("checked-in WS5 held-out comparison artifact missing")
    payload = package_consolidated_quality_analysis(
        comparison_path=_HELD_OUT_COMPARISON,
        freshness_companion_path=_HELD_OUT_FRESHNESS,
        output_path=tmp_path / "out.json",
        allow_manifest_mismatch=True,
    )
    assert payload.get("false_positive_category_complete") is True
    row = payload["failure_gallery"]["embedding_only_false_positives"][0]
    assert row.get("failure_category") or row.get("category_unavailable")


def test_package_consolidated_quality_analysis_builds_valid_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "workstream7-quality-analysis.json"
    payload = package_consolidated_quality_analysis(
        comparison_path=_HELD_OUT_COMPARISON,
        freshness_companion_path=_HELD_OUT_FRESHNESS,
        output_path=output,
        allow_manifest_mismatch=True,
    )
    validate_consolidated_quality_analysis(payload)
    assert payload["artifact_kind"] == "workstream7-quality-analysis"
    assert payload["quality_analysis"]["source_baseline"] == "compatibility-cache"
    assert "regeneration_commands" in payload
    assert payload.get("false_positive_category_complete") is True
    write_consolidated_quality_analysis(output, payload)
    reloaded = json.loads(output.read_text(encoding="utf-8"))
    validate_consolidated_quality_analysis(reloaded)


def test_freshness_failure_companion_merges_ws6_stale_exposure() -> None:
    report = json.loads(_HELD_OUT_FRESHNESS.read_text(encoding="utf-8"))
    stale = report["freshness_experiment"]["stale_exposure_accounting"]
    expected_counts = stale["protection_counts"]
    companion = build_freshness_failure_companion(_HELD_OUT_FRESHNESS)
    validate_freshness_failure_companion(companion)
    assert companion.get("unavailable") is not True
    assert companion["selected_policy"] == "conservative"
    assert companion["protection_counts"] == expected_counts
    scope = companion.get("held_out_freshness_scope")
    assert isinstance(scope, dict)
    assert scope.get("dynamic") == "unavailable"
    assert scope.get("stable") == "evaluated"
    assert (
        companion["stale_exposure_accounting"]["protection_counts"] == expected_counts
    )
    encoded = json.dumps(companion)
    assert "query_a" not in encoded


def test_build_quality_analysis_from_checked_in_comparison() -> None:
    payload = json.loads(_HELD_OUT_COMPARISON.read_text(encoding="utf-8"))
    quality = build_quality_analysis(payload)
    assert "intent_mismatch" in quality["by_failure_category"]
    assert quality["by_failure_category"]["intent_mismatch"]["sample_count"] >= 1
    assert "by_freshness_class" in quality


@pytest.mark.skipif(
    not _HELD_OUT_QUALITY.is_file(),
    reason="checked-in WS7 consolidated artifact missing",
)
def test_checked_in_workstream7_quality_analysis_redacted_and_complete() -> None:
    payload = json.loads(_HELD_OUT_QUALITY.read_text(encoding="utf-8"))
    validate_consolidated_quality_analysis(payload)
    validate_redacted_report_payload(payload)
    assert payload.get("false_positive_category_complete") is True


def test_checked_in_held_out_comparison_gallery_matches_contract() -> None:
    payload = json.loads(_HELD_OUT_COMPARISON.read_text(encoding="utf-8"))
    validate_failure_gallery(payload["failure_gallery"])
    attached = attach_failure_gallery_schema(
        {"baseline": "comparison", "failure_gallery": payload["failure_gallery"]}
    )
    assert attached["failure_gallery_schema_version"] == FAILURE_GALLERY_SCHEMA_VERSION
