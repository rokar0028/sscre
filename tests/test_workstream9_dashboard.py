from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre import dashboard as dashboard_module
from sscre.dashboard import (
    DASHBOARD_ARTIFACT_KIND,
    DASHBOARD_SCHEMA_VERSION,
    DashboardInputError,
    SECTION_NAMES,
    build_dashboard_view_manifest,
    export_dashboard,
    main as dashboard_main,
    render_dashboard_html,
    validate_dashboard_view_manifest,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMPARISON = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream5-held-out-comparison.json"
)
_QUALITY = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream7-quality-analysis.json"
)
_OPERATIONS = (
    _REPO_ROOT / "artifacts" / "operations" / "workstream8-operational-verification.json"
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


def test_missing_held_out_manifest_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(_QUALITY.read_text(encoding="utf-8"))
    payload.pop("split_manifest_sha256", None)
    stripped = tmp_path / "quality-no-manifest.json"
    stripped.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DashboardInputError, match="split_manifest_sha256"):
        build_dashboard_view_manifest(quality_path=stripped)


def test_unsupported_statistics_schema_fails_closed(tmp_path: Path) -> None:
    payload = json.loads(_COMPARISON.read_text(encoding="utf-8"))
    payload["statistics_schema_version"] = "unsupported-schema"
    bad = tmp_path / "comparison-bad-stats.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DashboardInputError, match="statistics_schema_version"):
        build_dashboard_view_manifest(comparison_path=bad)


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
    assert '<main id="dashboard-main">' in html_text
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


def _minimal_dashboard_manifest(
    **section_overrides: dict[str, object],
) -> dict[str, object]:
    sections: dict[str, object] = {}
    for name in SECTION_NAMES:
        sections[name] = {
            "status": "available",
            "source_artifacts": [{"path": f"{name}.json", "present": True}],
            "data": {"label": name},
        }
    sections.update(section_overrides)
    return {
        "dashboard_schema_version": DASHBOARD_SCHEMA_VERSION,
        "artifact_kind": DASHBOARD_ARTIFACT_KIND,
        "input_artifacts": {"comparison": {"path": "comparison.json", "present": True}},
        "primary_evaluation_identity": {
            "dataset_version": "reviewed-query-pairs-2.0",
            "evaluation_split": "held-out",
        },
        "sections": sections,
    }


def test_malformed_required_source_json_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "comparison.json"
    source.write_text("{not-json", encoding="utf-8")

    with pytest.raises(DashboardInputError, match="cannot load"):
        build_dashboard_view_manifest(comparison_path=source)


def test_non_object_required_source_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "comparison.json"
    source.write_text("[]", encoding="utf-8")

    with pytest.raises(DashboardInputError, match="JSON object"):
        build_dashboard_view_manifest(comparison_path=source)


def test_view_manifest_rejects_credential_and_raw_content_keys() -> None:
    for key in (
        "api_key",
        "token",
        "secret",
        "query",
        "failure_examples",
        "raw_query",
        "raw_answer",
    ):
        payload = _minimal_dashboard_manifest()
        limitations = payload["sections"]["limitations"]
        assert isinstance(limitations, dict)
        data = limitations["data"]
        assert isinstance(data, dict)
        data[key] = "must-not-appear"
        with pytest.raises(DashboardInputError, match="forbidden field"):
            validate_dashboard_view_manifest(payload)


def test_html_escapes_injected_markup() -> None:
    payload = _minimal_dashboard_manifest(
        limitations={
            "status": "unavailable",
            "reason": "<script>alert(1)</script>",
            "source_artifacts": [{"path": "<img src=x onerror=alert(1)>", "present": True}],
            "data": {
                "limitations": ["</pre><script>alert(1)</script>"],
            },
        }
    )

    html_text = render_dashboard_html(payload)

    assert "<script>alert(1)</script>" not in html_text
    assert "<img src=x onerror=alert(1)>" not in html_text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_text
    assert "&lt;/pre&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in html_text


def test_html_renders_unavailable_and_mismatch_states_as_text() -> None:
    payload = _minimal_dashboard_manifest(
        provider_measurements={
            "status": "unavailable",
            "reason": "provider_sources_missing",
            "source_artifacts": [{"path": "provider.json", "present": False}],
        },
        failure_categories={
            "status": "metadata_mismatch",
            "reason": "split_manifest_sha256 mismatch: expected held-out",
            "source_artifacts": [{"path": "quality.json", "present": True}],
        },
        operating_point={
            "status": "available",
            "source_artifacts": [{"path": "comparison.json", "present": True}],
            "data": {"selected_threshold": None, "constraint_satisfied": False},
        },
    )

    html_text = render_dashboard_html(payload)

    assert "Section status: unavailable." in html_text
    assert "Reason: provider_sources_missing." in html_text
    assert "No copied values are shown because this section is unavailable." in html_text
    assert "Section status: metadata_mismatch." in html_text
    assert "split_manifest_sha256 mismatch: expected held-out" in html_text
    assert "selected_threshold" in html_text
    assert "not recorded" in html_text
    assert "constraint_satisfied" in html_text
    assert ">false<" in html_text
    assert "color:" not in html_text.split("Section status: unavailable.")[1][:80]


def test_html_has_accessibility_landmarks_tables_and_text_equivalents() -> None:
    html_text = render_dashboard_html(build_dashboard_view_manifest())

    assert 'lang="en"' in html_text
    assert 'href="#dashboard-main">Skip to main content</a>' in html_text
    assert "<header>" in html_text
    assert '<nav aria-label="Dashboard sections">' in html_text
    assert '<main id="dashboard-main">' in html_text
    assert "<footer>" in html_text
    assert 'role="status"' in html_text
    assert 'scope="col"' in html_text
    assert "<caption>" in html_text
    assert "<th" in html_text
    assert "<table>" in html_text
    assert "There are no charts." in html_text
    assert "<svg" not in html_text
    assert "<canvas" not in html_text
    assert "query_a" not in html_text
    assert "api_key" not in html_text


def test_html_size_bound_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = build_dashboard_view_manifest()
    monkeypatch.setattr(dashboard_module, "MAX_DASHBOARD_HTML_BYTES", 100)

    with pytest.raises(DashboardInputError, match="HTML exceeds"):
        render_dashboard_html(payload)


@pytest.mark.skipif(
    not _COMPARISON.is_file() or not _QUALITY.is_file() or not _OPERATIONS.is_file(),
    reason="checked-in WS5/WS7/WS8 artifacts missing",
)
def test_dashboard_sections_match_upstream_artifact_values() -> None:
    comparison = json.loads(_COMPARISON.read_text(encoding="utf-8"))
    quality = json.loads(_QUALITY.read_text(encoding="utf-8"))
    operations = json.loads(_OPERATIONS.read_text(encoding="utf-8"))
    manifest = build_dashboard_view_manifest()

    selection = comparison["threshold_selection"]
    assert (
        manifest["sections"]["operating_point"]["data"]["selected_threshold"]
        == selection["selected_threshold"]
    )
    statistics = comparison["statistics"]
    confidence = manifest["sections"]["confidence_intervals"]["data"]
    assert confidence["sample_unit"] == statistics["sample_unit"]
    assert confidence["measurement_environment"] == statistics["measurement_environment"]
    assert (
        confidence["overall"]["confidence_level"]
        == statistics["overall"]["confidence_level"]
    )
    assert (
        confidence["overall"]["distributions"]["latency_ms_p95"]["point"]
        == statistics["overall"]["distributions"]["latency_ms_p95"]["point"]
    )
    quality_analysis = quality["quality_analysis"]
    failure = manifest["sections"]["failure_categories"]["data"]
    assert failure["source_baseline"] == quality_analysis["source_baseline"]
    assert failure["by_failure_category"] == quality_analysis["by_failure_category"]
    ops = manifest["sections"]["operations"]["data"]
    assert ops["limitation"] == operations["limitation"]
    assert (
        ops["protocols"]["ws8-pg-load-v1"]["bottleneck"]["first_measured_bottleneck"]
        == operations["protocols"]["ws8-pg-load-v1"]["bottleneck"][
            "first_measured_bottleneck"
        ]
    )


@pytest.mark.skipif(not _COMPARISON.is_file(), reason="checked-in WS5 comparison missing")
def test_dashboard_copies_mutated_source_values_without_recomputation(
    tmp_path: Path,
) -> None:
    payload = json.loads(_COMPARISON.read_text(encoding="utf-8"))
    payload["threshold_selection"]["selected_threshold"] = 0.42
    mutated = tmp_path / "comparison-mutated.json"
    mutated.write_text(json.dumps(payload), encoding="utf-8")

    manifest = build_dashboard_view_manifest(comparison_path=mutated)

    assert manifest["sections"]["operating_point"]["data"]["selected_threshold"] == 0.42


@pytest.mark.skipif(not _COMPARISON.is_file(), reason="checked-in WS5 comparison missing")
def test_view_manifest_sections_are_stable_across_rebuilds() -> None:
    first = build_dashboard_view_manifest()
    second = build_dashboard_view_manifest()

    assert first["sections"] == second["sections"]
    assert first["primary_evaluation_identity"] == second["primary_evaluation_identity"]


def test_export_json_is_deterministic_except_generation_metadata(
    tmp_path: Path,
) -> None:
    json_a = tmp_path / "a.json"
    json_b = tmp_path / "b.json"
    html = tmp_path / "unused.html"

    export_dashboard(json_output=json_a, html_output=html)
    export_dashboard(json_output=json_b, html_output=html)

    payload_a = json.loads(json_a.read_text(encoding="utf-8"))
    payload_b = json.loads(json_b.read_text(encoding="utf-8"))
    payload_a.pop("generation", None)
    payload_b.pop("generation", None)

    assert payload_a == payload_b


def test_dashboard_cli_help_and_failure_exit_codes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        dashboard_main(["--help"])
    assert exc.value.code == 0

    missing = tmp_path / "missing-comparison.json"
    json_output = tmp_path / "out.json"
    html_output = tmp_path / "out.html"
    assert (
        dashboard_main(
            [
                "--comparison",
                str(missing),
                "--json-output",
                str(json_output),
                "--html-output",
                str(html_output),
            ]
        )
        == 1
    )
    assert "dashboard export failed" in capsys.readouterr().err
    assert not json_output.exists()
