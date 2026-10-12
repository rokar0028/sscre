"""Workstream 6: freshness experiment schema and policy config."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sscre.baseline import (
    compatibility_cache_cost_kwargs_from_config,
    no_cache_cost_kwargs_from_config,
    run_compatibility_cache_baseline,
    run_no_cache_baseline,
)
from sscre.benchmark import BenchmarkRecord
from sscre.cache import InMemoryExactCache, CacheEntry
from sscre.cache_controls import evaluate_cache_control
from sscre.evaluate import _load_config
from sscre.freshness_metrics import compatibility_report_to_policy_metrics
from sscre.freshness_replay import run_freshness_policy_replay
from sscre.freshness_invalidation import (
    build_invalidation_artifact,
    run_in_memory_invalidation_sequence,
    validate_invalidation_artifact,
)
from sscre.freshness_stale_exposure import (
    STALE_EXPOSURE_ACCOUNTING_VERSION,
    build_stale_exposure_accounting,
    stale_exposure_indicators,
)
from sscre.evaluation_statistics import statistics_config_from_mapping
from sscre.freshness_evaluation import (
    DEFAULT_REPLAY_ANCHOR_TIME,
    FRESHNESS_EVALUATION_SCHEMA_VERSION,
    FreshnessPolicySpec,
    FreshnessReplayClock,
    apply_freshness_experiment_config_defaults,
    attach_freshness_evaluation_schema,
    build_replay_clocks_for_matrix,
    default_policy_matrix,
    freshness_experiment_from_mapping,
    parse_freshness_policy_spec,
    settings_cache_policy_matches_spec,
    validate_freshness_experiment_report,
    validate_freshness_policy_matrix,
)
from sscre.query import hash_query
from sscre.safety import QueryMetadata
from sscre.serialization import (
    attach_evaluation_report_schema,
    redact_operational_evaluation_report,
    validate_redacted_report_payload,
)


def test_checked_in_evaluation_config_loads_freshness_block() -> None:
    config = _load_config("experiments/evaluation_config.json")
    experiment = config["freshness_experiment"]
    assert experiment["schema_version"] == FRESHNESS_EVALUATION_SCHEMA_VERSION
    assert experiment["scope"] == "development_only"
    assert experiment["held_out_freshness_scope"]["semi_dynamic"] == "unavailable"
    assert len(experiment["policy_matrix"]) == 4


def test_policy_matrix_builds_cache_control_policies() -> None:
    policies = validate_freshness_policy_matrix(
        [policy.to_dict() for policy in default_policy_matrix()]
    )
    assert [policy.name for policy in policies] == [
        "conservative",
        "default",
        "dynamic-short",
        "long-lived",
    ]
    dynamic_short = policies[2]
    assert dynamic_short.allow_dynamic_entries
    assert dynamic_short.dynamic_ttl_seconds == 300
    dynamic_short.to_cache_control_policy()


def test_rejects_dynamic_entries_without_ttl() -> None:
    with pytest.raises(ValueError, match="dynamic_ttl_seconds is required"):
        parse_freshness_policy_spec(
            {
                "name": "bad",
                "stable_ttl_seconds": 60,
                "semi_dynamic_ttl_seconds": 60,
                "dynamic_ttl_seconds": None,
                "allow_dynamic_entries": True,
            }
        )


def test_rejects_dynamic_ttl_when_entries_disabled() -> None:
    with pytest.raises(ValueError, match="must be null when allow_dynamic_entries"):
        parse_freshness_policy_spec(
            {
                "name": "bad",
                "stable_ttl_seconds": 60,
                "semi_dynamic_ttl_seconds": 60,
                "dynamic_ttl_seconds": 300,
                "allow_dynamic_entries": False,
            }
        )


def test_development_only_scope_rejects_held_out_dynamic_evaluated() -> None:
    config = {
        "max_false_positive_rate": 0.0,
        "freshness_experiment": {
            "schema_version": FRESHNESS_EVALUATION_SCHEMA_VERSION,
            "scope": "development_only",
            "held_out_freshness_scope": {
                "stable": "evaluated",
                "semi_dynamic": "evaluated",
                "dynamic": "unavailable",
            },
            "policy_matrix": [default_policy_matrix()[1].to_dict()],
        },
    }
    with pytest.raises(ValueError, match="development_only scope"):
        apply_freshness_experiment_config_defaults(config)


def test_attach_freshness_schema_on_report_envelope() -> None:
    payload = {
        "freshness_experiment": {
            "schema_version": FRESHNESS_EVALUATION_SCHEMA_VERSION,
            "scope": "development_only",
            "policy_matrix": [default_policy_matrix()[1].to_dict()],
            "selected_policy": {
                "name": "default",
                "selection_rule": "constraint_first_then_maximize_safe_reuse_coverage",
                "constraint_satisfied": True,
                "constraints": {
                    "max_stale_exposure_rate": 0.0,
                    "max_false_positive_rate": 0.0,
                    "max_dynamic_reuse_served_rate": 0.0,
                },
            },
            "metrics_by_policy": {
                "default": {
                    "request_count": 10,
                    "stale_exposure_rate": 0.0,
                    "cache_control_outcome_counts": {"expired": 2, "fresh": 8},
                }
            },
        }
    }
    attached = attach_evaluation_report_schema(payload)
    assert (
        attached["freshness_evaluation_schema_version"]
        == FRESHNESS_EVALUATION_SCHEMA_VERSION
    )
    redacted = redact_operational_evaluation_report(attached)
    validate_redacted_report_payload(redacted["freshness_experiment"])


def test_validate_report_rejects_non_finite_metrics() -> None:
    with pytest.raises(ValueError, match="finite"):
        validate_freshness_experiment_report(
            {
                "schema_version": FRESHNESS_EVALUATION_SCHEMA_VERSION,
                "metrics_by_policy": {
                    "default": {"stale_exposure_rate": float("nan")},
                },
            }
        )


def test_freshness_experiment_from_mapping_round_trip() -> None:
    config = _load_config("experiments/evaluation_config.json")
    experiment = freshness_experiment_from_mapping(config)
    assert experiment is not None
    assert experiment.scope == "development_only"
    assert experiment.freshness_class_reporting == "both"
    assert len(experiment.policy_matrix) == 4
    assert experiment.selection.max_false_positive_rate == 0.0


def test_settings_boundary_matches_cache_control_policy() -> None:
    for spec in default_policy_matrix():
        assert settings_cache_policy_matches_spec(spec)


def test_replay_clock_expiration_boundary_is_exclusive() -> None:
    spec = default_policy_matrix()[0]
    expires_at = DEFAULT_REPLAY_ANCHOR_TIME + timedelta(
        seconds=spec.stable_ttl_seconds
    )
    at_boundary = FreshnessReplayClock(
        policy=spec.to_cache_control_policy(),
        current_time=expires_at,
        policy_name=spec.name,
    )
    result = at_boundary.evaluate_cache_control("stable", expires_at)
    assert result.reusable is False
    assert result.reason == "expired"

    before_boundary = FreshnessReplayClock(
        policy=spec.to_cache_control_policy(),
        current_time=expires_at - timedelta(seconds=1),
        policy_name=spec.name,
    )
    fresh = before_boundary.evaluate_cache_control("stable", expires_at)
    assert fresh.reusable is True
    assert fresh.reason == "fresh"


def test_replay_clocks_are_isolated_per_policy_arm() -> None:
    clocks = build_replay_clocks_for_matrix(
        default_policy_matrix(),
        DEFAULT_REPLAY_ANCHOR_TIME,
    )
    assert set(clocks) == {
        "conservative",
        "default",
        "dynamic-short",
        "long-lived",
    }
    clocks["conservative"].advance()
    assert clocks["default"].current_time == DEFAULT_REPLAY_ANCHOR_TIME


def test_policy_arms_use_separate_baseline_caches() -> None:
    record = BenchmarkRecord(
        id="pair-freshness-replay",
        query_a="What is caching?",
        query_b="Explain caching briefly",
        reusable=True,
        compatibility_label="compatible",
        coverage_category="paraphrase",
        reason="paraphrase",
    )
    clock_a = FreshnessReplayClock.from_policy_spec(
        default_policy_matrix()[0],
        DEFAULT_REPLAY_ANCHOR_TIME,
    )
    clock_b = FreshnessReplayClock.from_policy_spec(
        default_policy_matrix()[3],
        DEFAULT_REPLAY_ANCHOR_TIME,
    )
    first = run_compatibility_cache_baseline(
        [record],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=clock_a,
    )
    second = run_compatibility_cache_baseline(
        [record],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=clock_b,
    )
    assert first.generated_requests == second.generated_requests
    assert first.request_count == second.request_count


def test_replay_clock_sets_insert_ttl_from_policy_not_wall_clock() -> None:
    spec = FreshnessPolicySpec(
        name="short-stable",
        stable_ttl_seconds=120,
        semi_dynamic_ttl_seconds=60,
        dynamic_ttl_seconds=None,
        allow_dynamic_entries=False,
    )
    clock = FreshnessReplayClock.from_policy_spec(spec, DEFAULT_REPLAY_ANCHOR_TIME)
    metadata = QueryMetadata(
        intent="factual",
        domain="unknown",
        output_format="prose",
        temporal_class="stable",
    )
    expires = clock.ttl_expires_at_for_insert(metadata)
    assert expires == DEFAULT_REPLAY_ANCHOR_TIME + timedelta(seconds=120)
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hash_query("cached"),
            normalized_query="cached",
            answer="answer",
            metadata=metadata,
            ttl_expires_at=expires,
        )
    )
    clock.advance()
    clock.advance()
    stored = cache.get_by_query_hash(hash_query("cached"))
    assert stored is not None
    blocked = clock.evaluate_cache_control("stable", stored.ttl_expires_at)
    assert blocked.reusable is True
    for _ in range(120):
        clock.advance()
    blocked = clock.evaluate_cache_control("stable", stored.ttl_expires_at)
    assert blocked.reusable is False
    assert blocked.reason == "expired"


def test_baseline_cost_kwargs_match_runner_signatures() -> None:
    config = _load_config("experiments/evaluation_config.json")
    no_cache_keys = set(no_cache_cost_kwargs_from_config(config))
    compatibility_keys = set(compatibility_cache_cost_kwargs_from_config(config))

    no_cache_params = set(inspect.signature(run_no_cache_baseline).parameters)
    compatibility_params = set(
        inspect.signature(run_compatibility_cache_baseline).parameters
    )

    assert no_cache_keys <= no_cache_params
    assert compatibility_keys <= compatibility_params
    assert "embedding_cost_per_1k_tokens" not in no_cache_keys
    assert "embedding_cost_per_1k_tokens" in compatibility_keys


def _replay_test_record() -> BenchmarkRecord:
    return BenchmarkRecord(
        id="pair-freshness-replay-matrix",
        query_a="What is caching?",
        query_b="Explain caching briefly",
        reusable=True,
        compatibility_label="compatible",
        coverage_category="paraphrase",
        reason="paraphrase",
    )


def test_development_replay_runs_isolated_policy_arms() -> None:
    config = _load_config("experiments/evaluation_config.json")
    block = config["freshness_experiment"]
    block["policy_matrix"] = block["policy_matrix"][:2]
    payload = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    experiment = payload["freshness_experiment"]
    assert isinstance(experiment, dict)
    metrics = experiment["metrics_by_policy"]
    assert set(metrics) == {"conservative", "default"}
    assert experiment["reference_baselines"]["no-cache"]["request_count"] == 2
    assert len(experiment["policy_runs"]) == 2
    assert experiment["metrics_overall"]["policy_name"] == "default"
    assert "statistics" in experiment["metrics_overall"]
    assert experiment["invalidation"]["status"] == "evaluated"
    assert experiment["invalidation"]["ttl_expiration_used"] is False
    storage = experiment["storage_by_policy"]["default"]
    assert storage["status"] == "evaluated"
    assert storage["measurement_environment"] == "synthetic_storage_simulation"
    assert len(experiment["reuse_vs_storage_points"]) == 2
    assert "metrics_by_cache_control_outcome" in experiment
    validate_freshness_experiment_report(experiment)
    redacted = redact_operational_evaluation_report(
        attach_evaluation_report_schema(payload)
    )
    validate_redacted_report_payload(redacted["freshness_experiment"])


def test_held_out_replay_requires_frozen_development_selection() -> None:
    config = _load_config("experiments/evaluation_config.json")
    with pytest.raises(ValueError, match="frozen development selection"):
        run_freshness_policy_replay(
            [_replay_test_record()],
            config=config,
            split="held-out",
            selected_threshold=0.5,
            threshold_selection_rule="test_rule",
            selected_policy_name="default",
        )


def test_development_selection_is_constraint_first() -> None:
    config = _load_config("experiments/evaluation_config.json")
    payload = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
        git_commit="test-commit",
        git_worktree_dirty=False,
    )
    experiment = payload["freshness_experiment"]
    selected = experiment["selected_policy"]
    assert selected["selection_split"] == "development"
    assert "held_out_constraint_satisfied" not in selected
    assert selected["constraint_satisfied"] is True
    assert isinstance(selected["name"], str)
    candidates = experiment["policy_selection"]
    assert isinstance(candidates, list)
    assert len(candidates) == 4
    validate_freshness_experiment_report(experiment)


def test_select_development_rejects_dynamic_reuse_cap_violation() -> None:
    from sscre.freshness_policy_selection import select_development_freshness_policy

    config = _load_config("experiments/evaluation_config.json")
    experiment = freshness_experiment_from_mapping(config)
    assert experiment is not None
    base_metrics = {
        "request_count": 10,
        "stale_exposure_rate": 0.0,
        "dynamic_reuse_served_rate": 0.0,
        "false_positive_rate": 0.0,
    }
    metrics = {
        name: {
            **base_metrics,
            "safe_reuse_coverage": 0.4,
        }
        for name in ("conservative", "long-lived")
    }
    metrics["dynamic-short"] = {
        **base_metrics,
        "safe_reuse_coverage": 0.9,
        "dynamic_reuse_served_rate": 0.1,
    }
    metrics["default"] = {
        **base_metrics,
        "safe_reuse_coverage": 0.5,
    }
    result = select_development_freshness_policy(
        experiment,
        metrics,  # type: ignore[arg-type]
        config_version="evaluation-config-1.0",
        dataset_version="reviewed-query-pairs-2.0",
    )
    selected = result["selected_policy"]
    assert isinstance(selected, dict)
    assert selected["name"] == "default"
    candidates = result["policy_candidates"]
    assert isinstance(candidates, list)
    dynamic_short = next(c for c in candidates if c["name"] == "dynamic-short")
    assert dynamic_short["eligible"] is False


def test_held_out_replay_uses_frozen_development_artifact(tmp_path) -> None:
    config = _load_config("experiments/evaluation_config.json")
    dev_path = tmp_path / "development-freshness.json"
    from sscre.freshness_replay import write_freshness_replay_report

    dev_report = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    write_freshness_replay_report(dev_path, dev_report)
    from sscre.freshness_policy_selection import load_frozen_development_selection

    frozen = load_frozen_development_selection(dev_path)
    held_out = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="held-out",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
        selected_policy_name=frozen["name"],
        frozen_development_selection=frozen,
    )
    held_selected = held_out["freshness_experiment"]["selected_policy"]
    assert held_selected["held_out_evaluation_split"] == "held-out"
    assert isinstance(held_selected["held_out_constraint_satisfied"], bool)


def test_compatibility_replay_records_cache_control_outcomes() -> None:
    report = run_compatibility_cache_baseline(
        [_replay_test_record()],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=FreshnessReplayClock.from_policy_spec(
            default_policy_matrix()[0],
            DEFAULT_REPLAY_ANCHOR_TIME,
        ),
    )
    assert isinstance(report.cache_control_outcome_counts, dict)


def _stale_labeled_record() -> BenchmarkRecord:
    return BenchmarkRecord(
        id="pair-stale-exposure-controlled",
        query_a="What is caching?",
        query_b="Explain caching briefly",
        reusable=False,
        compatibility_label="compatible",
        coverage_category="stale_answer",
        failure_category="stale_answer",
        reason="controlled stale-answer fixture",
    )


def _short_ttl_policy() -> FreshnessPolicySpec:
    return FreshnessPolicySpec(
        name="short-stable",
        stable_ttl_seconds=1,
        semi_dynamic_ttl_seconds=1,
        dynamic_ttl_seconds=None,
        allow_dynamic_entries=False,
    )


def _long_ttl_policy() -> FreshnessPolicySpec:
    return FreshnessPolicySpec(
        name="long-stable",
        stable_ttl_seconds=86400,
        semi_dynamic_ttl_seconds=86400,
        dynamic_ttl_seconds=None,
        allow_dynamic_entries=False,
    )


def test_served_stale_exposure_counts_reviewed_labeled_reuse() -> None:
    record = _stale_labeled_record()
    stale_ids = frozenset({record.id})
    samples = (
        {
            "pair_id": record.id,
            "direction": "b_to_a",
            "cache_hit": 1,
            "false_positive": 1,
            "safe_reuse_hit": 0,
        },
        {
            "pair_id": record.id,
            "direction": "a_to_b",
            "cache_hit": 0,
            "false_positive": 0,
            "safe_reuse_hit": 0,
        },
    )
    assert sum(stale_exposure_indicators(samples, stale_ids)) == 1
    assert sum(stale_exposure_indicators(samples, frozenset())) == 0


def test_short_ttl_blocks_reuse_and_counts_expired_not_stale_exposure() -> None:
    record = BenchmarkRecord(
        id="pair-stale-ttl-block",
        query_a="What is caching?",
        query_b="What is caching?",
        reusable=False,
        compatibility_label="compatible",
        coverage_category="stale_answer",
        failure_category="stale_answer",
        reason="ttl block fixture",
    )
    short_report = run_compatibility_cache_baseline(
        [record],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=FreshnessReplayClock.from_policy_spec(
            _short_ttl_policy(),
            DEFAULT_REPLAY_ANCHOR_TIME,
        ),
    )
    long_report = run_compatibility_cache_baseline(
        [record],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=FreshnessReplayClock.from_policy_spec(
            _long_ttl_policy(),
            DEFAULT_REPLAY_ANCHOR_TIME,
        ),
    )
    short_metrics = compatibility_report_to_policy_metrics(
        [record],
        short_report,
        policy=_short_ttl_policy(),
    )
    long_metrics = compatibility_report_to_policy_metrics(
        [record],
        long_report,
        policy=_long_ttl_policy(),
    )
    assert short_metrics["stale_exposure_count"] == 0
    assert short_metrics["expired_candidate_blocked_count"] >= 1
    assert long_metrics["expired_candidate_blocked_count"] == 0
    assert long_metrics["cache_control_outcome_counts"].get("fresh", 0) >= 1


def test_blocked_expiration_is_not_served_stale_exposure() -> None:
    record = _stale_labeled_record()
    report = run_compatibility_cache_baseline(
        [record],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=FreshnessReplayClock.from_policy_spec(
            _short_ttl_policy(),
            DEFAULT_REPLAY_ANCHOR_TIME,
        ),
    )
    accounting = build_stale_exposure_accounting(
        [record],
        report,
        _short_ttl_policy(),
        statistics_config_from_mapping({"bootstrap_seed": 42}),
    )
    assert accounting["numerators"]["served_reviewed_stale_exposure_count"] == 0
    assert accounting["protection_counts"]["expired_candidate_blocked_count"] >= 1


def test_fresh_incompatible_miss_is_not_freshness_violation() -> None:
    record = BenchmarkRecord(
        id="pair-incompatible-format",
        query_a="Write a Python function for binary search",
        query_b="Summarize caching in one paragraph",
        reusable=False,
        compatibility_label="incompatible",
        coverage_category="format_change",
        failure_category="format_mismatch",
        reason="format mismatch fixture",
    )
    report = run_compatibility_cache_baseline(
        [record],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=FreshnessReplayClock.from_policy_spec(
            _long_ttl_policy(),
            DEFAULT_REPLAY_ANCHOR_TIME,
        ),
    )
    assert compatibility_report_to_policy_metrics(
        [record],
        report,
        policy=_long_ttl_policy(),
    )["stale_exposure_count"] == 0


def test_missing_and_invalid_expiration_are_protection_not_reuse() -> None:
    from sscre.baseline import CompatibilityCacheReport

    record = _stale_labeled_record()
    samples = (
        {
            "pair_id": record.id,
            "direction": "b_to_a",
            "cache_hit": 0,
            "generated": 1,
            "false_positive": 0,
            "safe_reuse_hit": 0,
            "latency_ms": 1.0,
            "embedding_tokens": 0,
            "generation_input_tokens": 1,
            "generation_output_tokens": 1,
            "estimated_cost_usd": 0.0,
        },
    )
    report = CompatibilityCacheReport(
        baseline="compatibility-cache",
        dataset_version="test",
        threshold=0.5,
        top_k=5,
        embedding_model="test-embedding",
        embedding_dimension=2,
        request_count=1,
        generated_requests=1,
        cache_hits=0,
        cache_misses=1,
        hit_rate=0.0,
            safe_reuse_hits=0,
            unsafe_reuse_hits=0,
            unlabeled_candidate_reuse_hits=0,
            uncertain_decisions=0,
        reusable_opportunities=0,
        safe_reuse_coverage=0.0,
        precision=0.0,
        recall=0.0,
        false_positive_rate=0.0,
        abstention_rate=0.0,
        embedding_tokens=0,
        input_tokens=1,
        output_tokens=1,
        tokens_saved=0,
        total_latency_ms=1,
        average_latency_ms=1.0,
        p50_latency_ms=1.0,
        p95_latency_ms=1.0,
        p99_latency_ms=1.0,
        input_cost_per_1k_tokens=0.0,
        output_cost_per_1k_tokens=0.0,
        embedding_cost_per_1k_tokens=0.0,
        cache_lookup_cost_usd=0.0,
        preprocessing_cost_usd=0.0,
        estimated_cost_usd=0.0,
        decision_counts={"UNCERTAIN": 1},
        decision_breakdowns={},
        failure_categories={},
        failure_examples=[],
        correctness_label_counts={},
        compatibility_label_counts={},
        preference_label_counts={},
        label_sections={},
        false_positive_examples=[],
        observed_pair_records=[],
        disagreement_class_counts={},
        cache_control_outcome_counts={
            "missing_expiration": 1,
            "invalid_expiration": 1,
        },
        request_samples=samples,
    )
    accounting = build_stale_exposure_accounting(
        [record],
        report,
        _long_ttl_policy(),
        statistics_config_from_mapping({"bootstrap_seed": 42}),
    )
    assert accounting["numerators"]["served_reviewed_stale_exposure_count"] == 0
    assert accounting["protection_counts"]["missing_expiration_count"] == 1
    assert accounting["protection_counts"]["invalid_expiration_count"] == 1


def test_stale_exposure_intervals_are_deterministic() -> None:
    config = _load_config("experiments/evaluation_config.json")
    settings = statistics_config_from_mapping(config)
    record = _stale_labeled_record()
    stale_ids = frozenset({record.id})
    indicators = [1, 0, 1, 0, 0]
    samples = [
        {
            "pair_id": record.id,
            "cache_hit": 1 if value else 0,
            "safe_reuse_hit": 0,
            "false_positive": value,
        }
        for value in indicators
    ]
    assert stale_exposure_indicators(samples, stale_ids) == indicators
    replay_report = run_compatibility_cache_baseline(
        [record],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=FreshnessReplayClock.from_policy_spec(
            _long_ttl_policy(),
            DEFAULT_REPLAY_ANCHOR_TIME,
        ),
    )
    first = build_stale_exposure_accounting(
        [record],
        replay_report,
        _long_ttl_policy(),
        settings,
    )
    second = build_stale_exposure_accounting(
        [record],
        replay_report,
        _long_ttl_policy(),
        settings,
    )
    assert (
        first["intervals"]["served_reviewed_stale_exposure_per_directed_request"]
        == second["intervals"]["served_reviewed_stale_exposure_per_directed_request"]
    )
    assert first["definition_version"] == STALE_EXPOSURE_ACCOUNTING_VERSION
    assert first["answer_level_stale_exposure"]["status"] == "unavailable"
    experiment = run_freshness_policy_replay(
        [record],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )["freshness_experiment"]
    assert "stale_exposure_accounting" in experiment
    validate_freshness_experiment_report(experiment)


def test_policy_storage_pairing_distinguishes_lazy_and_physical_cleanup() -> None:
    record = BenchmarkRecord(
        id="pair-storage-ttl-block",
        query_a="What is caching?",
        query_b="What is caching?",
        reusable=False,
        compatibility_label="compatible",
        coverage_category="stale_answer",
        failure_category="stale_answer",
        reason="storage ttl fixture",
    )
    short_report = run_compatibility_cache_baseline(
        [record],
        dataset_version="test",
        threshold=0.5,
        freshness_replay_clock=FreshnessReplayClock.from_policy_spec(
            _short_ttl_policy(),
            DEFAULT_REPLAY_ANCHOR_TIME,
        ),
    )
    assert short_report.policy_storage_snapshot["lazy_expired_rejection_count"] >= 1
    assert (
        short_report.policy_storage_snapshot["physical_expiration_cleanup_count"]
        >= 0
    )


def test_storage_sections_include_reuse_vs_storage_plane() -> None:
    config = _load_config("experiments/evaluation_config.json")
    block = config["freshness_experiment"]
    block["policy_matrix"] = block["policy_matrix"][:1]
    payload = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    experiment = payload["freshness_experiment"]
    points = experiment["reuse_vs_storage_points"]
    assert len(points) == 1
    assert points[0]["plane"] == "reuse_vs_storage"
    assert points[0]["measurement_environment"] == "synthetic_storage_simulation"


def test_in_memory_invalidation_sequence_succeeds() -> None:
    result = run_in_memory_invalidation_sequence()
    sequence = result["sequence"]
    assert sequence["insert_verified"] is True
    assert sequence["fresh_reuse_eligible_before_invalidation"] is True
    assert sequence["exact_lookup_empty_after_invalidation"] is True
    assert sequence["semantic_retrieval_excludes_invalidated_entry"] is True
    assert sequence["regeneration_verified"] is True
    assert result["storage_after_invalidation"]["entries"] == 0
    assert result["storage_after_regeneration"]["entries"] == 1


def test_invalidation_artifact_marks_postgresql_not_run() -> None:
    config = _load_config("experiments/evaluation_config.json")
    experiment = freshness_experiment_from_mapping(config)
    assert experiment is not None
    artifact = build_invalidation_artifact(experiment)
    assert artifact["status"] == "evaluated"
    assert artifact["repository"] == "in_memory_exact_cache"
    pg = artifact["postgresql_integration"]
    assert isinstance(pg, dict)
    assert pg["status"] == "not_run"
    validate_invalidation_artifact(artifact)
    validate_redacted_report_payload(artifact)


def test_unavailable_invalidation_scope_emits_explicit_record() -> None:
    from sscre.freshness_evaluation import (
        FreshnessExperimentConfig,
        FreshnessSelectionConfig,
    )

    experiment = FreshnessExperimentConfig(
        schema_version=FRESHNESS_EVALUATION_SCHEMA_VERSION,
        scope="development_only",
        freshness_class_reporting="both",
        held_out_freshness_scope={
            "stable": "evaluated",
            "semi_dynamic": "unavailable",
            "dynamic": "unavailable",
        },
        policy_matrix=default_policy_matrix(),
        selection=FreshnessSelectionConfig(
            selection_rule="test",
            objective="test",
            max_stale_exposure_rate=0.0,
            max_false_positive_rate=0.0,
            max_dynamic_reuse_served_rate=0.0,
        ),
        invalidation_scope="unavailable",
    )
    artifact = build_invalidation_artifact(experiment)
    assert artifact["status"] == "unavailable"
    assert "consequence" in artifact


def test_held_out_regeneration_commands_use_development_benchmark(tmp_path) -> None:
    from sscre.freshness_artifacts import (
        attach_freshness_artifact_metadata,
        development_benchmark_path_for_split,
    )

    held_out_benchmark = tmp_path / "held_out_test.jsonl"
    dev_benchmark = tmp_path / "development.jsonl"
    held_out_benchmark.write_text("{}\n", encoding="utf-8")
    dev_benchmark.write_text("{}\n", encoding="utf-8")
    assert (
        development_benchmark_path_for_split(held_out_benchmark, "held-out")
        == dev_benchmark
    )

    report = {
        "freshness_experiment": {
            "schema_version": FRESHNESS_EVALUATION_SCHEMA_VERSION,
            "evaluation_split": "held-out",
            "limitations": [],
            "held_out_freshness_scope": {
                "stable": "evaluated",
                "semi_dynamic": "unavailable",
                "dynamic": "unavailable",
            },
        }
    }
    config_path = tmp_path / "evaluation_config.json"
    config_path.write_text("{}\n", encoding="utf-8")
    attached = attach_freshness_artifact_metadata(
        report,
        config_path=config_path,
        benchmark_path=held_out_benchmark,
        split="held-out",
        production=True,
        selected_policy_arg="artifacts/evaluation/workstream6-development-freshness.json",
    )
    commands = attached["freshness_artifact_metadata"]["regeneration_commands"]
    assert isinstance(commands, list)
    assert "development.jsonl" in commands[0]
    assert "held_out_test.jsonl" in commands[1]


def test_held_out_replay_rejects_stale_frozen_config_version(tmp_path) -> None:
    from sscre.freshness_policy_selection import load_frozen_development_selection

    config = _load_config("experiments/evaluation_config.json")
    dev_path = tmp_path / "development-freshness.json"
    from sscre.freshness_replay import write_freshness_replay_report

    dev_report = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    write_freshness_replay_report(dev_path, dev_report)
    frozen = load_frozen_development_selection(dev_path)
    stale_config = dict(config)
    stale_config["config_version"] = "evaluation-config-stale"
    with pytest.raises(ValueError, match="config_version"):
        run_freshness_policy_replay(
            [_replay_test_record()],
            config=stale_config,
            split="held-out",
            selected_threshold=0.5,
            threshold_selection_rule="test_rule",
            selected_policy_name=frozen["name"],
            frozen_development_selection=frozen,
        )


def test_freshness_artifact_package_includes_step10_sections(tmp_path) -> None:
    from sscre.freshness_artifacts import (
        attach_freshness_artifact_metadata,
        build_invalidation_sidecar_artifact,
        validate_freshness_artifact_package,
        write_invalidation_sidecar,
    )
    from sscre.freshness_replay import write_freshness_replay_report

    config_path = tmp_path / "evaluation_config.json"
    config_path.write_text(
        Path("experiments/evaluation_config.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    benchmark_path = tmp_path / "benchmark.jsonl"
    benchmark_path.write_text(
        Path("benchmarks/development.jsonl").read_text(encoding="utf-8")[:500],
        encoding="utf-8",
    )
    config = _load_config(str(config_path))
    report = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    report = attach_freshness_artifact_metadata(
        report,
        config_path=config_path,
        benchmark_path=benchmark_path,
        split="development",
        production=False,
        selected_policy_arg=None,
    )
    validate_freshness_artifact_package(report)
    out = tmp_path / "development-freshness.json"
    write_freshness_replay_report(out, report)
    sidecar_path = tmp_path / "invalidation.json"
    sidecar = write_invalidation_sidecar(report, sidecar_path, source_artifact_path=out)
    assert sidecar["artifact_type"] == "workstream6_invalidation"
    assert build_invalidation_sidecar_artifact(report)["invalidation"]["status"] == "evaluated"


_REVIEWED_FRESHNESS_PAIR_IDS = {
    "stable": "pair-ws6-stable",
    "semi_dynamic": "pair-ws6-semidynamic",
    "dynamic": "pair-ws6-dynamic",
}


def _record_for_reviewed_freshness_class(freshness_class: str) -> BenchmarkRecord:
    return BenchmarkRecord(
        id=_REVIEWED_FRESHNESS_PAIR_IDS[freshness_class],
        query_a="What is caching?",
        query_b="Explain caching briefly",
        reusable=True,
        compatibility_label="compatible",
        coverage_category="paraphrase",
        reason="freshness class replay fixture",
        freshness_class=freshness_class,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("temporal_class", "ttl_seconds"),
    (
        ("stable", 120),
        ("semi_dynamic", 60),
        ("dynamic", 300),
    ),
)
def test_replay_insert_ttl_follows_policy_per_freshness_class(
    temporal_class: str,
    ttl_seconds: int,
) -> None:
    spec = FreshnessPolicySpec(
        name="all-classes",
        stable_ttl_seconds=120,
        semi_dynamic_ttl_seconds=60,
        dynamic_ttl_seconds=300,
        allow_dynamic_entries=True,
    )
    clock = FreshnessReplayClock.from_policy_spec(spec, DEFAULT_REPLAY_ANCHOR_TIME)
    metadata = QueryMetadata(
        intent="factual",
        domain="unknown",
        output_format="prose",
        temporal_class=temporal_class,  # type: ignore[arg-type]
    )
    expires = clock.ttl_expires_at_for_insert(metadata)
    assert expires == DEFAULT_REPLAY_ANCHOR_TIME + timedelta(seconds=ttl_seconds)


def test_default_policy_blocks_dynamic_entries_without_ttl() -> None:
    policy = default_policy_matrix()[1].to_cache_control_policy()
    expires = DEFAULT_REPLAY_ANCHOR_TIME + timedelta(days=1)
    result = evaluate_cache_control(
        "dynamic",
        expires,
        now=DEFAULT_REPLAY_ANCHOR_TIME,
        policy=policy,
    )
    assert result.reusable is False
    assert result.reason == "dynamic_entries_disabled"


def test_dynamic_short_policy_respects_dynamic_ttl_boundary() -> None:
    spec = default_policy_matrix()[2]
    assert spec.dynamic_ttl_seconds == 300
    clock = FreshnessReplayClock.from_policy_spec(spec, DEFAULT_REPLAY_ANCHOR_TIME)
    expires = DEFAULT_REPLAY_ANCHOR_TIME + timedelta(seconds=300)
    fresh = clock.evaluate_cache_control("dynamic", expires)
    assert fresh.reusable is True
    assert fresh.reason == "fresh"
    clock.current_time = expires
    expired = clock.evaluate_cache_control("dynamic", expires)
    assert expired.reusable is False
    assert expired.reason == "expired"


@pytest.mark.parametrize("temporal_class", ("stable", "semi_dynamic", "dynamic"))
def test_expired_entries_are_never_served_for_any_freshness_class(
    temporal_class: str,
) -> None:
    spec = FreshnessPolicySpec(
        name="dynamic-enabled",
        stable_ttl_seconds=3600,
        semi_dynamic_ttl_seconds=3600,
        dynamic_ttl_seconds=3600,
        allow_dynamic_entries=True,
    )
    clock = FreshnessReplayClock.from_policy_spec(spec, DEFAULT_REPLAY_ANCHOR_TIME)
    expires = DEFAULT_REPLAY_ANCHOR_TIME + timedelta(seconds=60)
    clock.current_time = expires
    blocked = clock.evaluate_cache_control(
        temporal_class,  # type: ignore[arg-type]
        expires,
    )
    assert blocked.reusable is False
    assert blocked.reason == "expired"


def test_development_replay_breaks_out_all_reviewed_freshness_classes() -> None:
    config = _load_config("experiments/evaluation_config.json")
    block = config["freshness_experiment"]
    block["policy_matrix"] = [default_policy_matrix()[1].to_dict()]
    payload = run_freshness_policy_replay(
        [
            _record_for_reviewed_freshness_class("stable"),
            _record_for_reviewed_freshness_class("semi_dynamic"),
            _record_for_reviewed_freshness_class("dynamic"),
        ],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    by_class = payload["freshness_experiment"]["metrics_by_reviewed_freshness_class"]
    assert set(by_class) == {"stable", "semi_dynamic", "dynamic"}


def test_matrix_replay_arms_do_not_share_cache_state() -> None:
    record = BenchmarkRecord(
        id="pair-ws6-cache-isolation",
        query_a="What is caching?",
        query_b="What is caching?",
        reusable=False,
        compatibility_label="compatible",
        coverage_category="stale_answer",
        failure_category="stale_answer",
        reason="cache isolation fixture",
    )
    config = _load_config("experiments/evaluation_config.json")
    block = config["freshness_experiment"]
    block["policy_matrix"] = [
        _short_ttl_policy().to_dict(),
        _long_ttl_policy().to_dict(),
    ]
    payload = run_freshness_policy_replay(
        [record],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    metrics = payload["freshness_experiment"]["metrics_by_policy"]
    short_arm = metrics["short-stable"]
    long_arm = metrics["long-stable"]
    assert short_arm["expired_candidate_blocked_count"] >= 1
    assert long_arm["expired_candidate_blocked_count"] == 0
    assert (
        long_arm["cache_control_outcome_counts"].get("fresh", 0)
        >= short_arm["cache_control_outcome_counts"].get("fresh", 0)
    )


def test_freshness_artifact_redaction_rejects_raw_query_fields() -> None:
    payload = {
        "freshness_experiment": {
            "schema_version": FRESHNESS_EVALUATION_SCHEMA_VERSION,
            "policy_matrix": [default_policy_matrix()[1].to_dict()],
            "leak": {"query_a": "secret benchmark text"},
        }
    }
    with pytest.raises(ValueError, match="must not include"):
        validate_redacted_report_payload(payload["freshness_experiment"])


def test_checked_in_workstream6_artifacts_pass_operational_redaction() -> None:
    artifact_paths = (
        Path("artifacts/evaluation/workstream6-development-freshness.json"),
        Path("artifacts/evaluation/workstream6-held-out-freshness.json"),
        Path("artifacts/evaluation/workstream6-invalidation.json"),
    )
    missing = [path for path in artifact_paths if not path.is_file()]
    if missing:
        pytest.skip(f"missing checked-in artifacts: {', '.join(str(p) for p in missing)}")
    for path in artifact_paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if path.name.startswith("workstream6-invalidation"):
            validate_redacted_report_payload(raw)
            continue
        attached = attach_evaluation_report_schema(raw)
        redacted = redact_operational_evaluation_report(attached)
        validate_redacted_report_payload(redacted["freshness_experiment"])


def test_freshness_statistics_use_configured_bootstrap_seed() -> None:
    config = _load_config("experiments/evaluation_config.json")
    block = config["freshness_experiment"]
    block["policy_matrix"] = [default_policy_matrix()[1].to_dict()]
    first = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    second = run_freshness_policy_replay(
        [_replay_test_record()],
        config=config,
        split="development",
        selected_threshold=0.5,
        threshold_selection_rule="test_rule",
    )
    stats_a = first["freshness_experiment"]["statistics_by_policy"]["default"]
    stats_b = second["freshness_experiment"]["statistics_by_policy"]["default"]
    assert stats_a == stats_b
