"""WS8 protocol ``ws8-pg-load-v1``: bounded PostgreSQL load verification."""

from __future__ import annotations

from pathlib import Path

from sscre.load_test import _load_config, run
from tests.ws8_postgres_helpers import WS8_LOAD_MARKS

pytestmark = WS8_LOAD_MARKS

PROTOCOL_ID = "ws8-pg-load-v1"
CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "experiments" / "workstream8_pg_load_v1.json"
)


def test_ws8_pg_load_v1_two_cold_two_warm() -> None:
    report = run(_load_config(CONFIG_PATH))
    assert report["protocol_id"] == PROTOCOL_ID
    assert report["repository"] == "postgres"
    assert report["environment"]["database_mode"] == "postgres"
    assert report["environment"]["postgresql_version"]
    assert report["environment"]["git_commit"]
    assert "SSCRE_DATABASE_URL" not in str(report)
    assert "postgresql://" not in str(report)
    assert report["limitation"]
    passes = report["comparison"]["exact_cache"]
    if report["stopped_reason"] is None:
        assert [item["mode"] for item in passes] == ["cold", "warm", "cold", "warm"]
    else:
        assert report["stopped_reason"] in {
            "error_rate_above_10_percent",
            "timeout_rate_above_5_percent",
            "p99_above_5x_p50",
        }
        assert passes
    for item in passes:
        assert item["request_count"] == 32
        assert item["concurrency"] == 4
        assert set(item["latency_ms"]) >= {"p50", "p95", "p99"}
        assert "throughput_requests_per_second" in item
        assert "cache_hits" in item
        assert "generated_requests" in item
        assert "evictions_delta" in item["storage"]
        assert "bytes_delta" in item["storage"]
    analysis = report["bottleneck_analysis"]
    assert analysis["environment"]["storage"] == "postgresql"
    assert analysis["result_class"] == "observation"
    assert analysis["optimization_decision"] == "none"
    assert "repository_database_span" in analysis["unavailable_components"]
    assert analysis["first_measured_bottleneck"] in {
        "not_reached",
        "error_rate_above_10_percent",
        "timeout_rate_above_5_percent",
        "p99_above_5x_p50",
    }
