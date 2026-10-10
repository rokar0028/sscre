"""Default-suite coverage for the load-test runner and WS8 protocol config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.load_test import (
    UNAVAILABLE_PG_LOAD_SPANS,
    _load_config,
    _stop_reason,
    classify_first_bottleneck,
    run,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
WS8_LOAD_CONFIG = REPO_ROOT / "experiments" / "workstream8_pg_load_v1.json"


def test_load_test_memory_exact_cache_reports_required_fields() -> None:
    report = run(
        {
            "name": "memory-smoke",
            "repository": "memory",
            "modes": ["exact_cache"],
            "cold_passes": 1,
            "warm_passes": 1,
            "warmup_requests": 1,
            "request_count": 4,
            "concurrency": 2,
            "max_cache_entries": 8,
            "max_cache_bytes": 10_000,
            "items": [
                {"label": "exact_hit", "query": "What is a cache?"},
            ],
        }
    )
    assert report["repository"] == "memory"
    assert report["stopped_reason"] is None
    passes = report["comparison"]["exact_cache"]
    assert [item["mode"] for item in passes] == ["cold", "warm"]
    cold = passes[0]
    assert "p50" in cold["latency_ms"]
    assert "p95" in cold["latency_ms"]
    assert "p99" in cold["latency_ms"]
    assert "throughput_requests_per_second" in cold
    assert "cache_hits" in cold
    assert "generated_requests" in cold
    assert "evictions_delta" in cold["storage"]
    assert report["environment"]["database_mode"] == "memory"
    assert report["environment"]["postgresql_version"] is None


def test_postgres_repository_requires_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SSCRE_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="SSCRE_DATABASE_URL"):
        run(
            {
                "repository": "postgres",
                "modes": ["exact_cache"],
                "request_count": 1,
                "items": [{"label": "exact_hit", "query": "What is a cache?"}],
            }
        )


def test_ws8_pg_load_config_matches_protocol() -> None:
    config = _load_config(WS8_LOAD_CONFIG)
    assert config["protocol_id"] == "ws8-pg-load-v1"
    assert config["repository"] == "postgres"
    assert config["modes"] == ["exact_cache"]
    assert config["cold_passes"] == 2
    assert config["warm_passes"] == 2
    assert config["warmup_requests"] == 8
    assert config["request_count"] == 32
    assert config["concurrency"] == 4
    assert config["max_cache_entries"] == 8
    assert config["max_cache_bytes"] == 10000
    assert config["process_count"] == 1
    assert config["worker_count"] == 1
    assert "production capacity" in str(config["limitation"]).lower()


def test_stop_reason_error_rate_and_p99_spread() -> None:
    assert (
        _stop_reason(
            {
                "errors": {"rate": 0.11, "timeout_rate": 0.0},
                "latency_ms": {"p50": 10.0, "p99": 12.0},
                "warmup_error_rate": 0.0,
            }
        )
        == "error_rate_above_10_percent"
    )
    assert (
        _stop_reason(
            {
                "errors": {"rate": 0.0, "timeout_rate": 0.0},
                "latency_ms": {"p50": 10.0, "p99": 51.0},
                "warmup_error_rate": 0.0,
                "request_count": 32,
            }
        )
        == "p99_above_5x_p50"
    )
    assert (
        _stop_reason(
            {
                "errors": {"rate": 0.0, "timeout_rate": 0.0},
                "latency_ms": {"p50": 10.0, "p99": 51.0},
                "warmup_error_rate": 0.0,
                "request_count": 4,
            }
        )
        is None
    )
    assert (
        _stop_reason(
            {
                "errors": {"rate": 0.0, "timeout_rate": 0.0},
                "latency_ms": {"p50": 10.0, "p99": 20.0},
                "warmup_error_rate": 0.0,
                "request_count": 32,
            }
        )
        is None
    )


def test_classify_first_bottleneck_not_reached_is_observation() -> None:
    report = {
        "protocol_id": "ws8-pg-load-v1",
        "repository": "postgres",
        "stopped_reason": None,
        "environment": {"postgresql_version": "16.15"},
        "comparison": {
            "exact_cache": [
                {
                    "mode": "cold",
                    "concurrency": 4,
                    "throughput_requests_per_second": 40.0,
                    "latency_ms": {"p50": 63.0, "p95": 199.0, "p99": 262.0},
                    "results": [
                        {
                            "latency_ms": 80.0,
                            "llm_latency_ms": 0,
                            "wrapper_overhead_ms": 80,
                        }
                    ],
                }
            ]
        },
    }
    analysis = classify_first_bottleneck(report)
    assert analysis["first_measured_bottleneck"] == "not_reached"
    assert analysis["result_class"] == "observation"
    assert analysis["optimization_decision"] == "none"
    assert analysis["measured_components"]["average_llm_latency_ms"] == 0.0
    assert set(analysis["unavailable_components"]) == set(UNAVAILABLE_PG_LOAD_SPANS)
    assert analysis["stop_conditions"]["stopped_reason"] is None


def test_classify_first_bottleneck_stop_is_still_not_an_optimization() -> None:
    analysis = classify_first_bottleneck(
        {
            "protocol_id": "ws8-pg-load-v1",
            "repository": "postgres",
            "stopped_reason": "error_rate_above_10_percent",
            "environment": {},
            "comparison": {},
        }
    )
    assert analysis["first_measured_bottleneck"] == "error_rate_above_10_percent"
    assert analysis["result_class"] == "observation"
    assert analysis["optimization_decision"] == "none"


def test_milestone10_config_still_defaults_to_memory() -> None:
    config = json.loads(
        (REPO_ROOT / "experiments" / "milestone10_load_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert "repository" not in config
    assert config["request_count"] == 32
