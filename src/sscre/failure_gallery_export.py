"""CLI to consolidate Workstream 7 quality-analysis JSON and optional HTML."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping

from sscre.failure_gallery import (
    DEFAULT_HELD_OUT_COMPARISON_PATH,
    DEFAULT_HELD_OUT_FRESHNESS_PATH,
    DEFAULT_QUALITY_ANALYSIS_OUTPUT_PATH,
    package_consolidated_quality_analysis,
    write_consolidated_quality_analysis,
)
from sscre.gallery_export import render_consolidated_quality_gallery_html
from sscre.serialization import validate_redacted_report_payload


def export_consolidated_failure_gallery(
    *,
    comparison_path: Path,
    freshness_companion_path: Path,
    output_path: Path,
    html_path: Path | None = None,
    allow_manifest_mismatch: bool = False,
) -> dict[str, object]:
    payload = package_consolidated_quality_analysis(
        comparison_path=comparison_path,
        freshness_companion_path=freshness_companion_path,
        output_path=output_path,
        allow_manifest_mismatch=allow_manifest_mismatch,
    )
    validate_redacted_report_payload(payload)
    write_consolidated_quality_analysis(output_path, payload)
    if html_path is not None:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_text = render_consolidated_quality_gallery_html(payload)
        html_path.write_text(html_text, encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build workstream7-quality-analysis.json from WS5 comparison and "
            "WS6 freshness companion artifacts."
        ),
    )
    parser.add_argument(
        "--comparison",
        type=Path,
        default=Path(DEFAULT_HELD_OUT_COMPARISON_PATH),
        help="Held-out WS5 comparison JSON path.",
    )
    parser.add_argument(
        "--freshness-companion",
        type=Path,
        default=Path(DEFAULT_HELD_OUT_FRESHNESS_PATH),
        help="Held-out WS6 freshness artifact path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_QUALITY_ANALYSIS_OUTPUT_PATH),
        help="Consolidated quality-analysis JSON output path.",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="Optional static HTML export path.",
    )
    parser.add_argument(
        "--allow-manifest-mismatch",
        action="store_true",
        help=(
            "Allow dataset_version or split_manifest_sha256 mismatch between inputs "
            "(diagnostic only; records limitations in the artifact)."
        ),
    )
    args = parser.parse_args(argv)
    try:
        export_consolidated_failure_gallery(
            comparison_path=args.comparison,
            freshness_companion_path=args.freshness_companion,
            output_path=args.output,
            html_path=args.html,
            allow_manifest_mismatch=args.allow_manifest_mismatch,
        )
    except (OSError, ValueError) as exc:
        print(f"failure gallery export failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.output.as_posix()}")
    if args.html is not None:
        print(f"wrote {args.html.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
