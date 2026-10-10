from pathlib import Path

import pytest

from sscre.gallery_export import (
    export_failure_gallery,
    failure_category_rows,
    render_failure_gallery_html,
    validate_gallery_payload,
)


def test_failure_category_rows_from_comparison_statistics() -> None:
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
    rows = failure_category_rows(payload)
    assert rows == [
        {
            "category": "intent_change",
            "sample_count": 10,
            "false_positive_rate": 0.05,
        }
    ]


def test_validate_gallery_payload_rejects_query_text() -> None:
    with pytest.raises(ValueError, match="query_a"):
        validate_gallery_payload(
            {
                "failure_gallery": {
                    "strategy_c_failures": [{"id": "pair-1", "query_a": "secret"}]
                }
            }
        )


def test_render_failure_gallery_html_redacted_example(tmp_path: Path) -> None:
    payload = {
        "baseline": "comparison",
        "evaluation_split": "held-out",
        "dataset_version": "reviewed-query-pairs-2.0",
        "execution_timestamp": "2026-10-09T00:00:00+00:00",
        "measurement_environment": "synthetic_replay",
        "statistics": {
            "strata": {
                "by_failure_category": {
                    "paraphrase": {"sample_count": 2, "proportions": {}},
                }
            }
        },
        "failure_gallery": {
            "embedding_only_false_positives": [
                {
                    "id": "pair-0001",
                    "direction": "b_to_a",
                    "similarity": 0.99,
                    "reason": "reviewed reason text",
                }
            ],
            "strategy_c_failures": [],
        },
    }
    html = render_failure_gallery_html(payload)
    assert "pair-0001" in html
    assert "reviewed reason text" in html
    assert "query_a" not in html

    out = tmp_path / "gallery.html"
    export_failure_gallery(
        _write_json(tmp_path / "report.json", payload),
        out,
    )
    assert out.is_file()
    assert "Failure category strata" in out.read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict) -> Path:
    import json

    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
