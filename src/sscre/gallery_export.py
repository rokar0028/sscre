"""Export a static HTML failure gallery from saved evaluation JSON artifacts."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Mapping

_FORBIDDEN_EXAMPLE_KEYS = frozenset({"query_a", "query_b", "query_text"})
_GALLERY_SECTIONS = (
    "embedding_only_false_positives",
    "embedding_only_false_positives_caught_by_strategy_c",
    "strategy_c_failures",
)
_DISPLAY_KEYS = (
    "id",
    "direction",
    "failure_category",
    "predicted_decision",
    "expected_reusable",
    "expected_compatibility",
    "similarity",
    "reason",
)


def load_evaluation_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evaluation report must be a JSON object: {path}")
    return payload


def _statistics_strata(payload: Mapping[str, object]) -> dict[str, Any]:
    statistics = payload.get("statistics")
    if not isinstance(statistics, dict):
        return {}
    by_baseline = statistics.get("by_baseline")
    if isinstance(by_baseline, dict):
        compatibility = by_baseline.get("compatibility-cache")
        if isinstance(compatibility, dict):
            strata = compatibility.get("strata")
            if isinstance(strata, dict):
                by_category = strata.get("by_failure_category")
                if isinstance(by_category, dict):
                    return dict(by_category)
    strata = statistics.get("strata")
    if isinstance(strata, dict):
        by_category = strata.get("by_failure_category")
        if isinstance(by_category, dict):
            return dict(by_category)
    return {}


def failure_category_rows(payload: Mapping[str, object]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category in sorted(_statistics_strata(payload)):
        summary = _statistics_strata(payload)[category]
        if not isinstance(summary, dict):
            continue
        proportions = summary.get("proportions")
        fp_point = None
        if isinstance(proportions, dict):
            fp = proportions.get("false_positive_rate")
            if isinstance(fp, dict):
                fp_point = fp.get("point")
        rows.append(
            {
                "category": category,
                "sample_count": summary.get("sample_count"),
                "false_positive_rate": fp_point,
            }
        )
    return rows


def _assert_examples_redacted(examples: object, *, context: str) -> None:
    if not isinstance(examples, list):
        return
    for index, example in enumerate(examples):
        if not isinstance(example, dict):
            continue
        leaked = _FORBIDDEN_EXAMPLE_KEYS.intersection(example)
        if leaked:
            names = ", ".join(sorted(leaked))
            raise ValueError(
                f"{context}[{index}] contains forbidden field(s): {names}"
            )


def validate_gallery_payload(payload: Mapping[str, object]) -> None:
    gallery = payload.get("failure_gallery")
    if gallery is None:
        return
    if not isinstance(gallery, dict):
        raise ValueError("failure_gallery must be an object")
    for section in gallery:
        _assert_examples_redacted(gallery[section], context=f"failure_gallery.{section}")


def _example_display_fields(example: Mapping[str, object]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for key in _DISPLAY_KEYS:
        if key in example:
            row[key] = example[key]
    labels = example.get("evaluation_labels")
    if isinstance(labels, dict):
        compatibility = labels.get("compatibility")
        if isinstance(compatibility, dict):
            reviewed = compatibility.get("reviewed")
            if reviewed is not None:
                row["reviewed_compatibility"] = reviewed
    traces = example.get("candidate_traces")
    if isinstance(traces, list) and traces:
        first = traces[0]
        if isinstance(first, dict):
            row["trace_decision"] = first.get("decision")
            row["trace_reason"] = first.get("reason")
            if "similarity" in first and "similarity" not in row:
                row["similarity"] = first.get("similarity")
    return row


def render_failure_gallery_html(payload: Mapping[str, object]) -> str:
    validate_gallery_payload(payload)
    title_parts = [
        str(payload.get("baseline", "evaluation")),
        str(payload.get("evaluation_split", "")),
    ]
    title = " ".join(part for part in title_parts if part).strip()

    metadata_lines = [
        f"dataset_version={html.escape(str(payload.get('dataset_version', 'unknown')))}",
        f"execution_timestamp={html.escape(str(payload.get('execution_timestamp', 'unknown')))}",
        f"measurement_environment={html.escape(str(payload.get('measurement_environment', 'unknown')))}",
    ]

    category_rows = failure_category_rows(payload)
    category_html = ["<table>", "<tr><th>Category</th><th>n</th><th>false_positive_rate</th></tr>"]
    for row in category_rows:
        fp = row["false_positive_rate"]
        fp_text = "" if fp is None else f"{fp:.4f}"
        category_html.append(
            "<tr>"
            f"<td>{html.escape(str(row['category']))}</td>"
            f"<td>{html.escape(str(row['sample_count']))}</td>"
            f"<td>{html.escape(fp_text)}</td>"
            "</tr>"
        )
    category_html.append("</table>")

    sections_html: list[str] = []
    gallery = payload.get("failure_gallery")
    if isinstance(gallery, dict):
        for section in _GALLERY_SECTIONS:
            examples = gallery.get(section)
            if not isinstance(examples, list) or not examples:
                continue
            sections_html.append(f"<h2>{html.escape(section)}</h2>")
            sections_html.append("<table>")
            sections_html.append(
                "<tr><th>id</th><th>direction</th><th>details</th></tr>"
            )
            for example in examples:
                if not isinstance(example, dict):
                    continue
                display = _example_display_fields(example)
                detail = html.escape(
                    json.dumps(display, sort_keys=True, ensure_ascii=False)
                )
                sections_html.append(
                    "<tr>"
                    f"<td>{html.escape(str(display.get('id', '')))}</td>"
                    f"<td>{html.escape(str(display.get('direction', '')))}</td>"
                    f"<td><code>{detail}</code></td>"
                    "</tr>"
                )
            sections_html.append("</table>")

    body = "\n".join(
        [
            f"<h1>Failure gallery — {html.escape(title)}</h1>",
            "<p>" + "<br/>".join(metadata_lines) + "</p>",
            "<h2>Failure category strata (Strategy C statistics)</h2>",
            *category_html,
            *sections_html,
        ]
    )
    return (
        "<!DOCTYPE html><html><head>"
        '<meta charset="utf-8"/>'
        f"<title>{html.escape(title)} failure gallery</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:1.5rem}"
        "table{border-collapse:collapse;margin:1rem 0;width:100%}"
        "td,th{border:1px solid #ccc;padding:0.35rem 0.5rem;vertical-align:top}"
        "code{white-space:pre-wrap;word-break:break-word}</style>"
        "</head><body>"
        f"{body}</body></html>\n"
    )


def export_failure_gallery(
    input_path: Path,
    output_path: Path,
) -> None:
    payload = load_evaluation_report(input_path)
    html_text = render_failure_gallery_html(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render a static HTML failure gallery from evaluation JSON.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to evaluation report JSON (e.g. workstream5-held-out-comparison.json).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output HTML path (default: <input-stem>-gallery.html beside input).",
    )
    args = parser.parse_args(argv)
    output = args.output
    if output is None:
        output = args.input.with_name(f"{args.input.stem}-gallery.html")
    try:
        export_failure_gallery(args.input, output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"gallery export failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
