from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.dashboard import (
    DASHBOARD_SCHEMA_VERSION,
    DashboardInputError,
    SECTION_NAMES,
    build_dashboard_view_manifest,
    export_dashboard,
    validate_dashboard_view_manifest,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMPARISON = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream5-held-out-comparison.json"
)
_QUALITY = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream7-quality-analysis.json"
)


@pytest.mark.skipif(
    not _COMPARISON.is_file() or not _QUALITY.is_file(),
    reason="checked-in WS5/WS7 artifacts missing",
)
def test_build_dashboard_manifest_has_frozen_sections_and_source_identity() -> None:
    manifest = build_dashboard_view_manifest()

    assert manifest["dashboard_schema_version"] == DASHBOARD_SCHEMA_VERSION
    assert set(manifest["sections"]) == set(SECTION_NAMES)
    assert (
        manifest["primary_evaluation_identity"]["split_manifest_sha256"]
        == "68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51"
    )
    assert (
        manifest["sections"]["operating_point"]["data"]["selected_threshold"]
        == 0.95
    )
    assert (
        manifest["sections"]["operating_point"]["data"]["selection_split"]
        == "development"
    )
    assert (
        manifest["sections"]["operating_point"]["data"]["development_provenance"][
            "alignment"
        ]
        == "provenance_only_manifest_mismatch"
    )
    assert (
        manifest["sections"]["baseline_comparison"]["data"]["baselines"][
            "compatibility-cache"
        ]["request_count"]
        == 430
    )
    assert manifest["sections"]["provider_measurements"]["status"] == "not_comparable"
    assert set(
        manifest["sections"]["provider_measurements"]["data"]["rows"]
    ) == {"synthetic", "real_provider"}
    assert (
        manifest["sections"]["freshness"]["data"]["development_selection"][
            "alignment"
        ]
        == "provenance_only_manifest_mismatch"
    )
    assert manifest["sections"]["pareto"]["data"]["manifest_status"] == "not_recorded"
    assert (
        manifest["sections"]["pareto"]["data"]["storage_status"] == "unavailable"
    )
    assert (
        "safety_vs_reuse"
        in manifest["sections"]["pareto"]["data"]["dominance"]
    )
    assert (
        manifest["sections"]["failure_categories"]["data"]["source_baseline"]
        == "compatibility-cache"
    )
    validate_dashboard_view_manifest(manifest)


def test_optional_provider_sources_can_be_absent(tmp_path: Path) -> None:
    manifest = build_dashboard_view_manifest(
        provider_comparison_path=tmp_path / "provider-comparison.json",
        provider_unavailable_path=tmp_path / "provider-unavailable.json",
    )

    section = manifest["sections"]["provider_measurements"]
    assert section["status"] == "unavailable"
    assert section["reason"] == "provider_sources_missing"


def test_missing_required_source_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(DashboardInputError, match="required dashboard source"):
        build_dashboard_view_manifest(comparison_path=tmp_path / "missing.json")


def test_metadata_mismatch_is_explicit_and_not_silently_merged(
    tmp_path: Path,
) -> None:
    payload = json.loads(_QUALITY.read_text(encoding="utf-8"))
    payload["split_manifest_sha256"] = "0" * 64
    mismatched = tmp_path / "quality-mismatch.json"
    mismatched.write_text(json.dumps(payload), encoding="utf-8")

    manifest = build_dashboard_view_manifest(quality_path=mismatched)

    section = manifest["sections"]["failure_categories"]
    assert section["status"] == "metadata_mismatch"
    assert "split_manifest_sha256 mismatch" in section["reason"]
    assert "data" not in section


def test_source_redaction_boundary_rejects_forbidden_display_content(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": "provider-measurement-comparison-1.0",
        "dataset_version": "reviewed-query-pairs-1.1",
        "split": "development",
        "answer": "must not be copied",
    }
    source = tmp_path / "provider.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DashboardInputError, match="invalid dashboard source"):
        build_dashboard_view_manifest(provider_comparison_path=source)


def test_export_writes_json_and_html_from_the_view_manifest(tmp_path: Path) -> None:
    json_output = tmp_path / "dashboard.json"
    html_output = tmp_path / "dashboard.html"

    payload = export_dashboard(
        json_output=json_output,
        html_output=html_output,
    )

    assert json_output.is_file()
    assert html_output.is_file()
    reloaded = json.loads(json_output.read_text(encoding="utf-8"))
    validate_dashboard_view_manifest(reloaded)
    assert reloaded["generation"]["git_commit"]
    assert reloaded["export_policy"]["metric_source"] == "upstream_artifacts"
    html_text = html_output.read_text(encoding="utf-8")
    assert "<main>" in html_text
    assert "Operating Point" in html_text
    assert "measurement_environment=synthetic_replay" in html_text
    assert "query_a" not in html_text
    assert payload["sections"] == reloaded["sections"]


def test_export_requires_explicit_override_for_metadata_mismatch(
    tmp_path: Path,
) -> None:
    payload = json.loads(_QUALITY.read_text(encoding="utf-8"))
    payload["split_manifest_sha256"] = "0" * 64
    mismatched = tmp_path / "quality-mismatch.json"
    mismatched.write_text(json.dumps(payload), encoding="utf-8")
    json_output = tmp_path / "dashboard.json"
    html_output = tmp_path / "dashboard.html"

    with pytest.raises(DashboardInputError, match="allow-metadata-mismatch"):
        export_dashboard(
            quality_path=mismatched,
            json_output=json_output,
            html_output=html_output,
        )

    assert not json_output.exists()
    assert not html_output.exists()

    exported = export_dashboard(
        quality_path=mismatched,
        json_output=json_output,
        html_output=html_output,
        allow_metadata_mismatch=True,
    )
    assert exported["export_policy"]["metadata_mismatch_override"] is True
    assert exported["sections"]["failure_categories"]["status"] == (
        "metadata_mismatch"
    )
