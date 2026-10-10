"""Workstream 7 failure gallery contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.failure_gallery import (
    FAILURE_GALLERY_SCHEMA_VERSION,
    attach_failure_gallery_schema,
    validate_consolidated_quality_analysis,
    validate_failure_gallery,
)
from sscre.serialization import attach_evaluation_report_schema

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HELD_OUT_COMPARISON = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream5-held-out-comparison.json"
)


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


def test_attach_adds_schema_version_for_comparison_gallery() -> None:
    payload = attach_evaluation_report_schema(
        {"baseline": "comparison", "failure_gallery": _minimal_gallery()}
    )
    assert payload["failure_gallery_schema_version"] == FAILURE_GALLERY_SCHEMA_VERSION


def test_validate_failure_gallery_rejects_forbidden_query_text() -> None:
    gallery = _minimal_gallery()
    gallery["strategy_c_failures"][0]["query_a"] = "secret"
    with pytest.raises(ValueError, match="query_a"):
        validate_failure_gallery(gallery)


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
def test_checked_in_held_out_comparison_gallery_matches_contract() -> None:
    payload = json.loads(_HELD_OUT_COMPARISON.read_text(encoding="utf-8"))
    validate_failure_gallery(payload["failure_gallery"])
    attached = attach_failure_gallery_schema(
        {"baseline": "comparison", "failure_gallery": payload["failure_gallery"]}
    )
    assert attached["failure_gallery_schema_version"] == FAILURE_GALLERY_SCHEMA_VERSION
