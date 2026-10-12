"""Default-suite coverage for the load-test runner and WS8 protocol config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sscre.load_test import (
    UNAVAILABLE_PG_LOAD_SPANS,
    _load_config,
    _stop_reason,
    build_ladder_sequence,
    classify_first_bottleneck,
    ladder_non_fixture_error_rate,
    main,
    realized_repeat_ratio,
    run,
    run_ladder,
    select_component_bottleneck,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
WS8_LOAD_CONFIG = REPO_ROOT / "experiments" / "workstream8_pg_load_v1.json"
PHASE3_LADDER_CONFIG = REPO_ROOT / "experiments" / "phase3_load_ladder_v1.json"


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


def test_phase3_load_ladder_config_matches_feature_8_card() -> None:
    config = _load_config(PHASE3_LADDER_CONFIG)
    assert config["protocol_id"] == "phase3-load-ladder-v1"
    assert config["dataset_version"] == "reviewed-query-pairs-2.0"
    assert config["development_path"] == "benchmarks/development.jsonl"
    assert (REPO_ROOT / config["development_path"]).is_file()
    assert config["repository"] == "memory"
    assert config["modes"] == ["compatibility"]
    assert config["threshold_arm"] == "global_0.95"
    assert config["similarity_threshold"] == 0.95
    assert config["seed"] == 20261011
    assert config["repeat_ratio"] == 0.3
    assert config["process_count"] == 1
    assert config["max_cache_entries"] == 10000
    assert config["max_cache_bytes"] == 100_000_000
    assert config["fixture_labels"] == ["embedding_failure", "generation_failure"]
    assert config["budgets"] == {
        "memory": {
            "p95_end_to_end_latency_ms": 500,
            "non_fixture_error_rate": 0.01,
        },
        "postgres": {
            "p95_end_to_end_latency_ms": 3000,
            "non_fixture_error_rate": 0.01,
        },
        "timeout_rate": 0.01,
    }
    assert config["steps"] == [
        {
            "id": "L1",
            "simulated_q_per_day": 1000,
            "request_count": 200,
            "warmup_requests": 20,
            "concurrency": 4,
        },
        {
            "id": "L2",
            "simulated_q_per_day": 10000,
            "request_count": 2000,
            "warmup_requests": 200,
            "concurrency": 4,
        },
        {
            "id": "L3",
            "simulated_q_per_day": 100000,
            "request_count": 20000,
            "warmup_requests": 2000,
            "concurrency": 8,
        },
    ]
    assert "items" not in config
    raw = PHASE3_LADDER_CONFIG.read_text(encoding="utf-8")
    assert "[fail_embedding]" not in raw
    assert "[fail_generation]" not in raw
    assert "production capacity" in str(config["limitation"]).lower()


def _ladder_components(**overrides: float) -> dict[str, float]:
    components = {
        "embed": 1.0,
        "vector_search": 1.0,
        "repository": 1.0,
        "generation": 1.0,
        "wrapper_other": 1.0,
    }
    components.update(overrides)
    return components


def _ladder_row(
    *,
    label: str = "development_unique",
    status_code: int = 200,
    latency_ms: float = 10.0,
    reason: str | None = None,
    components: dict[str, float] | None = None,
) -> dict[str, object]:
    return {
        "label": label,
        "status_code": status_code,
        "reason": reason,
        "latency_ms": latency_ms,
        "components": components or _ladder_components(),
    }


def _ladder_raw(
    rows: list[dict[str, object]],
    *,
    entries: int = 1,
    total_bytes: int = 10,
) -> dict[str, object]:
    return {
        "rows": rows,
        "entries": entries,
        "total_bytes": total_bytes,
        "eviction_count": 0,
        "elapsed_seconds": 1.0,
    }


def _synthetic_ladder_config() -> dict[str, object]:
    return {
        "protocol_id": "phase3-load-ladder-v1",
        "repository": "memory",
        "modes": ["compatibility"],
        "seed": 20261011,
        "repeat_ratio": 0.3,
        "process_count": 1,
        "max_cache_entries": 10,
        "max_cache_bytes": 1000,
        "fixture_labels": ["embedding_failure", "generation_failure"],
        "budgets": {
            "memory": {
                "p95_end_to_end_latency_ms": 500,
                "non_fixture_error_rate": 0.01,
            },
            "postgres": {
                "p95_end_to_end_latency_ms": 3000,
                "non_fixture_error_rate": 0.01,
            },
            "timeout_rate": 0.01,
        },
        "steps": [
            {
                "id": "L1",
                "simulated_q_per_day": 1000,
                "request_count": 1,
                "warmup_requests": 0,
                "concurrency": 1,
            },
            {
                "id": "L2",
                "simulated_q_per_day": 10000,
                "request_count": 1,
                "warmup_requests": 0,
                "concurrency": 1,
            },
            {
                "id": "L3",
                "simulated_q_per_day": 100000,
                "request_count": 1,
                "warmup_requests": 0,
                "concurrency": 1,
            },
        ],
    }


def test_ladder_sequence_is_stable_for_a_seed() -> None:
    pool = ("alpha", "beta", "gamma")
    first = build_ladder_sequence(
        pool, length=8, seed=20261011, repeat_ratio=0.3
    )
    second = build_ladder_sequence(
        pool, length=8, seed=20261011, repeat_ratio=0.3
    )
    assert first == second
    assert first[0] == ("alpha", "development_unique")
    assert realized_repeat_ratio(first, 2) == realized_repeat_ratio(second, 2)
    for index, (query, label) in enumerate(first):
        if label == "development_repeat":
            assert query in {item[0] for item in first[:index]}
        else:
            assert label == "development_unique"


def test_non_fixture_error_rate_ignores_failure_fixtures() -> None:
    rows = [
        {"label": "embedding_failure", "status_code": 503},
        {"label": "generation_failure", "status_code": 500},
        {"label": "development_unique", "status_code": 500},
        {"label": "development_repeat", "status_code": 200},
        {"label": "development_unique", "status_code": 200},
    ]
    rate = ladder_non_fixture_error_rate(
        rows,
        ["embedding_failure", "generation_failure"],
    )
    assert rate == 1 / 3
    assert (
        ladder_non_fixture_error_rate(
            [{"label": "embedding_failure", "status_code": 500}],
            ["embedding_failure"],
        )
        is None
    )


def test_component_bottleneck_rules() -> None:
    assert (
        select_component_bottleneck(
            _ladder_components(embed=9, vector_search=1, repository=1, generation=1)
        )
        == "embed"
    )
    assert (
        select_component_bottleneck(
            _ladder_components(embed=4, vector_search=4, repository=0, generation=0, wrapper_other=0)
        )
        == "embed"
    )
    assert (
        select_component_bottleneck(
            {
                "compatibility_check": 1000,
                "embed": 1,
                "vector_search": 0,
                "repository": 0,
                "generation": 0,
                "wrapper_other": 0,
            }
        )
        == "embed"
    )
    assert select_component_bottleneck(_ladder_components(
        embed=0, vector_search=0, repository=0, generation=0, wrapper_other=0
    )) == "unattributed"


def test_ladder_over_budget_names_the_largest_share() -> None:
    config = _synthetic_ladder_config()

    def runner(_config, step, run_index):
        assert run_index in {1, 2}
        assert step["id"] == "L1"
        return _ladder_raw([
            _ladder_row(
                latency_ms=800,
                components=_ladder_components(embed=40),
            )
        ])

    report = run_ladder(config, step_runner=runner)
    assert report["first_bottleneck"] == "embed"
    assert report["bottleneck_step"] == "L1"
    assert report["reproducibility"] == "agree"
    assert [step["step_id"] for step in report["steps"]] == ["L1", "L1"]
    assert "results" not in report["steps"][0]
    assert "query" not in report["steps"][0]


def test_ladder_under_budget_is_not_reached() -> None:
    calls: list[tuple[str, int]] = []

    def runner(_config, step, run_index):
        calls.append((step["id"], run_index))
        return _ladder_raw([_ladder_row()])

    report = run_ladder(_synthetic_ladder_config(), step_runner=runner)
    assert calls == [("L1", 1), ("L2", 1), ("L3", 1), ("L3", 2)]
    assert report["first_bottleneck"] == "not_reached"
    assert report["reproducibility"] == "agree"
    assert report["bottleneck_step"] is None


def test_ladder_disagreement_does_not_continue() -> None:
    calls: list[tuple[str, int]] = []

    def runner(_config, step, run_index):
        calls.append((step["id"], run_index))
        embed = 40 if run_index == 1 else 1
        repository = 1 if run_index == 1 else 40
        return _ladder_raw([
            _ladder_row(
                latency_ms=800,
                components=_ladder_components(embed=embed, repository=repository),
            )
        ])

    report = run_ladder(_synthetic_ladder_config(), step_runner=runner)
    assert calls == [("L1", 1), ("L1", 2)]
    assert report["first_bottleneck"] is None
    assert report["reproducibility"] == "disagree"
    assert report["bottleneck_step"] == "L1"


def test_ladder_zero_share_is_unattributed() -> None:
    def runner(_config, step, run_index):
        assert step["id"] == "L1"
        return _ladder_raw([
            _ladder_row(
                latency_ms=800,
                components=_ladder_components(
                    embed=0,
                    vector_search=0,
                    repository=0,
                    generation=0,
                    wrapper_other=0,
                ),
            )
        ])

    report = run_ladder(_synthetic_ladder_config(), step_runner=runner)
    assert report["first_bottleneck"] is None
    assert report["bottleneck_outcome"] == "unattributed"
    assert report["reproducibility"] == "agree"
    assert [step["step_id"] for step in report["steps"]] == ["L1", "L1"]


def test_ladder_cap_miss_stops_without_a_component_name() -> None:
    calls: list[str] = []

    def runner(_config, step, _run_index):
        calls.append(step["id"])
        return _ladder_raw([_ladder_row()], entries=11, total_bytes=10)

    report = run_ladder(_synthetic_ladder_config(), step_runner=runner)
    assert calls == ["L1"]
    assert report["steps"][0]["cap_compliant"] is False
    assert report["first_bottleneck"] is None
    assert report["steps"][0]["component_bottleneck"] is None


def test_ladder_postgres_without_url_writes_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SSCRE_DATABASE_URL", raising=False)
    report = run_ladder(
        {"protocol_id": "phase3-load-ladder-v1", "repository": "postgres"}
    )
    assert report["status"] == "unavailable"
    assert report["steps"] == []
    assert report["first_bottleneck"] is None
    output = tmp_path / "phase3-load-ladder-postgres.json"
    exit_code = main(
        [
            "--config",
            str(PHASE3_LADDER_CONFIG),
            "--repository",
            "postgres",
            "--output",
            str(output),
        ]
    )
    assert exit_code == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["status"] == "unavailable"
    assert written["measurement_environment"] == "synthetic_replay"
    assert "SSCRE_DATABASE_URL" in written["unavailable_reason"]


def test_ladder_memory_smoke_omits_queries_and_results() -> None:
    report = run_ladder(
        {
            "protocol_id": "phase3-load-ladder-v1",
            "dataset_version": "reviewed-query-pairs-2.0",
            "development_path": "benchmarks/development.jsonl",
            "repository": "memory",
            "modes": ["compatibility"],
            "threshold_arm": "global_0.95",
            "similarity_threshold": 0.95,
            "seed": 20261011,
            "repeat_ratio": 0.3,
            "process_count": 1,
            "max_cache_entries": 100,
            "max_cache_bytes": 1_000_000,
            "budgets": {
                "memory": {
                    "p95_end_to_end_latency_ms": 60_000,
                    "non_fixture_error_rate": 1,
                },
                "postgres": {
                    "p95_end_to_end_latency_ms": 60_000,
                    "non_fixture_error_rate": 1,
                },
                "timeout_rate": 1,
            },
            "steps": [
                {
                    "id": "L1",
                    "simulated_q_per_day": 1000,
                    "request_count": 2,
                    "warmup_requests": 0,
                    "concurrency": 1,
                }
            ],
        }
    )
    assert report["status"] == "complete"
    assert report["measurement_environment"] == "synthetic_replay"
    assert report["pool_size"] > 0
    assert report["first_bottleneck"] == "not_reached"
    assert report["steps"][0]["unavailable_components"] == ["compatibility_check"]
    assert report["steps"][0]["cap_compliant"] is True
    encoded = json.dumps(report)
    assert "\"results\"" not in encoded
    assert "\"query\"" not in encoded


def test_milestone10_config_still_defaults_to_memory() -> None:
    config = json.loads(
        (REPO_ROOT / "experiments" / "milestone10_load_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert "repository" not in config
    assert config["request_count"] == 32
