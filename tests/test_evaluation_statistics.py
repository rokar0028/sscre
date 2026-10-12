import json
import math

import pytest

from sscre.baseline import run_embedding_cache_baseline
from sscre.benchmark import load_benchmark_jsonl
from sscre.evaluation_statistics import (
    EVALUATION_STATISTICS_SCHEMA_VERSION,
    BootstrapResampler,
    StatisticsConfig,
    apply_statistics_config_defaults,
    attach_evaluation_statistics_schema,
    bootstrap_percentile_interval,
    clopper_pearson_interval,
    proportion_interval,
    statistics_config_from_mapping,
    summarize_request_sample_statistics,
    unavailable_interval,
    validate_interval_dict,
    wilson_score_interval,
)
from pathlib import Path
from sscre.evaluate import _load_config
from sscre.serialization import (
    attach_evaluation_report_schema,
    redact_operational_evaluation_report,
    validate_redacted_report_payload,
    validate_statistics_preserves_redaction,
)


def test_wilson_interval_known_bounds() -> None:
    point, lower, upper = wilson_score_interval(60, 100, confidence_level=0.95)
    assert point == pytest.approx(0.6)
    assert 0.50 < lower < 0.55
    assert 0.65 < upper < 0.71
    validate_interval_dict(
        {
            "point": point,
            "lower": lower,
            "upper": upper,
            "method": "wilson",
            "n": 100,
            "confidence_level": 0.95,
        }
    )


def test_wilson_rejects_inverted_inputs() -> None:
    with pytest.raises(ValueError, match="successes must not exceed"):
        wilson_score_interval(5, 3)


def test_validate_interval_rejects_non_finite_and_inverted() -> None:
    with pytest.raises(ValueError, match="finite"):
        validate_interval_dict(
            {
                "point": float("nan"),
                "lower": 0.0,
                "upper": 1.0,
                "method": "wilson",
                "n": 10,
                "confidence_level": 0.95,
            }
        )
    with pytest.raises(ValueError, match="lower <= point"):
        validate_interval_dict(
            {
                "point": 0.5,
                "lower": 0.8,
                "upper": 0.9,
                "method": "wilson",
                "n": 10,
                "confidence_level": 0.95,
            }
        )


def test_unavailable_interval_shape() -> None:
    payload = unavailable_interval(
        point=0.2,
        n=3,
        confidence_level=0.95,
        reason="n_below_minimum_bootstrap",
    )
    assert payload["method"] == "unavailable"
    assert payload["lower"] is None
    assert payload["upper"] is None


def test_bootstrap_mean_is_deterministic_with_seed() -> None:
    settings = StatisticsConfig(
        confidence_level=0.95,
        bootstrap_seed=42,
        bootstrap_iterations=1000,
        proportion_interval_method="wilson",
        minimum_n_proportion=1,
        minimum_n_bootstrap=5,
    )
    samples = [10.0, 12.0, 11.0, 13.0, 9.0]
    first = bootstrap_percentile_interval(samples, settings)
    second = bootstrap_percentile_interval(samples, settings)
    assert first == second
    assert first["method"] == "bootstrap_percentile"
    assert first["lower"] <= first["point"] <= first["upper"]


def test_proportion_interval_respects_minimum_n() -> None:
    settings = StatisticsConfig(
        confidence_level=0.95,
        bootstrap_seed=1,
        bootstrap_iterations=1000,
        proportion_interval_method="wilson",
        minimum_n_proportion=5,
        minimum_n_bootstrap=5,
    )
    payload = proportion_interval(1, 3, settings)
    assert payload["method"] == "unavailable"
    assert payload["reason"] == "n_below_minimum_proportion"


def test_evaluation_config_defaults_and_validation(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "config_version": "evaluation-config-1.0",
                "dataset_version": "reviewed-query-pairs-1.1",
            }
        ),
        encoding="utf-8",
    )
    config = _load_config(config_path)
    assert config["confidence_level"] == 0.95
    assert config["bootstrap_seed"] == 42
    assert config["bootstrap_iterations"] == 1000
    assert config["proportion_interval_method"] == "wilson"


def test_apply_statistics_config_rejects_invalid_bootstrap_iterations() -> None:
    with pytest.raises(ValueError, match="bootstrap_iterations"):
        apply_statistics_config_defaults({"bootstrap_iterations": 10})


def test_attach_statistics_schema_on_report() -> None:
    statistics = {
        "hit_rate": {
            "point": 0.5,
            "lower": 0.3,
            "upper": 0.7,
            "method": "wilson",
            "n": 20,
            "confidence_level": 0.95,
        }
    }
    payload = attach_evaluation_report_schema(
        {"baseline": "compatibility-cache", "statistics": statistics}
    )
    assert payload["statistics_schema_version"] == EVALUATION_STATISTICS_SCHEMA_VERSION
    assert payload["statistics"] == statistics


def test_redaction_preserves_statistics_block() -> None:
    payload = {
        "baseline": "comparison",
        "statistics": {
            "hit_rate": unavailable_interval(
                point=0.1,
                n=2,
                confidence_level=0.95,
                reason="n_below_minimum_bootstrap",
            )
        },
        "false_positive_examples": [{"id": "pair-1", "query_a": "secret"}],
    }
    validate_statistics_preserves_redaction(payload)
    redacted = redact_operational_evaluation_report(payload)
    validate_redacted_report_payload(redacted["statistics"])
    assert redacted["statistics"] == payload["statistics"]
    assert "query_a" not in json.dumps(redacted["false_positive_examples"])


def test_statistics_config_from_mapping() -> None:
    settings = statistics_config_from_mapping(
        {
            "confidence_level": 0.9,
            "bootstrap_seed": 7,
            "bootstrap_iterations": 1000,
        }
    )
    assert settings.confidence_level == 0.9
    assert "proportion_metrics" in settings.interval_methods_metadata()


def test_clopper_pearson_known_bounds() -> None:
    point, lower, upper = clopper_pearson_interval(7, 10, confidence_level=0.95)
    assert point == pytest.approx(0.7)
    assert 0.34 < lower < 0.37
    assert 0.92 < upper < 0.96


def test_clopper_pearson_via_proportion_interval() -> None:
    settings = StatisticsConfig(
        confidence_level=0.95,
        bootstrap_seed=1,
        bootstrap_iterations=1000,
        proportion_interval_method="clopper_pearson",
        minimum_n_proportion=1,
        minimum_n_bootstrap=5,
    )
    payload = proportion_interval(7, 10, settings)
    assert payload["method"] == "clopper_pearson"
    assert payload["lower"] <= payload["point"] <= payload["upper"]


def test_bootstrap_quantile_interval_with_shared_rng() -> None:
    settings = StatisticsConfig(
        confidence_level=0.95,
        bootstrap_seed=99,
        bootstrap_iterations=1000,
        proportion_interval_method="wilson",
        minimum_n_proportion=1,
        minimum_n_bootstrap=5,
    )
    samples = [1.0, 2.0, 3.0, 4.0, 20.0]
    resampler = BootstrapResampler(settings)
    mean_interval = resampler.percentile_interval(samples, statistic="mean")
    p95_interval = resampler.percentile_interval(
        samples,
        statistic="quantile",
        quantile=0.95,
    )
    assert mean_interval["method"] == "bootstrap_percentile"
    assert p95_interval["method"] == "bootstrap_percentile"
    assert mean_interval != p95_interval
    repeat = BootstrapResampler(settings)
    assert repeat.percentile_interval(
        samples,
        statistic="mean",
    ) == mean_interval
    assert repeat.percentile_interval(
        samples,
        statistic="quantile",
        quantile=0.95,
    ) == p95_interval


def test_summarize_request_samples_from_baseline_replay() -> None:
    root = Path(__file__).resolve().parents[1]
    records = load_benchmark_jsonl(root / "benchmarks" / "development.jsonl")[:3]
    report = run_embedding_cache_baseline(
        records,
        dataset_version="reviewed-query-pairs-1.1",
        threshold=0.9,
    )
    settings = statistics_config_from_mapping(
        {
            "confidence_level": 0.95,
            "bootstrap_seed": 42,
            "bootstrap_iterations": 1000,
        }
    )
    summary = summarize_request_sample_statistics(
        report.request_samples,
        settings,
    )
    assert summary["sample_count"] == report.request_count
    assert summary["sample_unit"] == "directed_request"
    assert summary["proportions"]["hit_rate"]["n"] == report.request_count
    assert "latency_ms_p95" in summary["distributions"]
    attach_evaluation_statistics_schema({"statistics": summary})


def test_summarize_request_samples_by_failure_and_freshness() -> None:
    root = Path(__file__).resolve().parents[1]
    records = load_benchmark_jsonl(root / "benchmarks" / "development.jsonl")
    report = run_embedding_cache_baseline(
        records,
        dataset_version="reviewed-query-pairs-1.1",
        threshold=0.9,
    )
    settings = statistics_config_from_mapping(
        {
            "confidence_level": 0.95,
            "bootstrap_seed": 42,
            "bootstrap_iterations": 1000,
        }
    )

    summary = summarize_request_sample_statistics(report.request_samples, settings)
    strata = summary["strata"]
    failure_strata = strata["by_failure_category"]
    freshness_strata = strata["by_freshness_class"]

    assert failure_strata
    assert freshness_strata
    assert set(failure_strata) == {
        str(record.failure_category) for record in records
    }
    assert set(freshness_strata) == {record.freshness_class for record in records}
    assert sum(
        entry["sample_count"] for entry in failure_strata.values()
    ) == report.request_count
    assert sum(
        entry["sample_count"] for entry in freshness_strata.values()
    ) == report.request_count
    for entry in (*failure_strata.values(), *freshness_strata.values()):
        assert entry["sample_unit"] == "directed_request"
        assert entry["proportions"]["hit_rate"]["n"] == entry["sample_count"]


def test_summarize_request_samples_without_unlabeled_field_defaults_to_zero() -> None:
    settings = statistics_config_from_mapping(
        {
            "confidence_level": 0.95,
            "bootstrap_seed": 42,
            "bootstrap_iterations": 1000,
        }
    )
    legacy_samples = (
        {
            "pair_id": "pair-1",
            "direction": "b_to_a",
            "cache_hit": 1,
            "generated": 0,
            "false_positive": 1,
            "safe_reuse_hit": 0,
            "latency_ms": 1.0,
            "embedding_tokens": 0,
            "generation_input_tokens": 0,
            "generation_output_tokens": 0,
            "estimated_cost_usd": 0.0,
        },
    )
    summary = summarize_request_sample_statistics(legacy_samples, settings)
    assert summary["proportions"]["false_positive_rate"]["point"] == 1.0
