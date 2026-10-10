"""CLI tests for Workstream 7 consolidated gallery export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.failure_gallery import validate_consolidated_quality_analysis
from sscre.failure_gallery_export import export_consolidated_failure_gallery, main

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HELD_OUT_COMPARISON = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream5-held-out-comparison.json"
)
_HELD_OUT_FRESHNESS = (
    _REPO_ROOT / "artifacts" / "evaluation" / "workstream6-held-out-freshness.json"
)


@pytest.mark.skipif(
    not _HELD_OUT_COMPARISON.is_file() or not _HELD_OUT_FRESHNESS.is_file(),
    reason="checked-in WS5/WS6 held-out artifacts missing",
)
def test_cli_main_succeeds_when_manifests_align(tmp_path: Path) -> None:
    exit_code = main(
        [
            "--comparison",
            str(_HELD_OUT_COMPARISON),
            "--freshness-companion",
            str(_HELD_OUT_FRESHNESS),
            "--output",
            str(tmp_path / "workstream7-quality-analysis.json"),
        ]
    )
    assert exit_code == 0


def test_cli_main_fails_without_allow_on_manifest_mismatch(tmp_path: Path) -> None:
    freshness = json.loads(_HELD_OUT_FRESHNESS.read_text(encoding="utf-8"))
    artifact = freshness.setdefault("benchmark_artifact", {})
    assert isinstance(artifact, dict)
    artifact["split_manifest_sha256"] = "0" * 64
    mismatched = tmp_path / "ws6-mismatch.json"
    mismatched.write_text(
        json.dumps(freshness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    exit_code = main(
        [
            "--comparison",
            str(_HELD_OUT_COMPARISON),
            "--freshness-companion",
            str(mismatched),
            "--output",
            str(tmp_path / "out.json"),
        ]
    )
    assert exit_code == 1


@pytest.mark.skipif(
    not _HELD_OUT_COMPARISON.is_file() or not _HELD_OUT_FRESHNESS.is_file(),
    reason="checked-in WS5/WS6 held-out artifacts missing",
)
def test_export_consolidated_writes_json_and_html(tmp_path: Path) -> None:
    json_out = tmp_path / "workstream7-quality-analysis.json"
    html_out = tmp_path / "workstream7-quality-gallery.html"
    payload = export_consolidated_failure_gallery(
        comparison_path=_HELD_OUT_COMPARISON,
        freshness_companion_path=_HELD_OUT_FRESHNESS,
        output_path=json_out,
        html_path=html_out,
        allow_manifest_mismatch=True,
    )
    validate_consolidated_quality_analysis(payload)
    assert json_out.is_file()
    assert html_out.is_file()
    reloaded = json.loads(json_out.read_text(encoding="utf-8"))
    validate_consolidated_quality_analysis(reloaded)
    html_text = html_out.read_text(encoding="utf-8")
    assert "Freshness failure companion" in html_text
    assert "failure-gallery" in html_text
    assert "query_a" not in html_text
