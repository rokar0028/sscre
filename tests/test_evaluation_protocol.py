"""Tests for Phase 4 evaluation protocol helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from sscre.benchmark import BenchmarkRecord, load_benchmark_jsonl
from sscre.evaluate import _load_config
from sscre.evaluation_protocol import (
    apply_primary_headline_population_filter,
    max_abstention_rate,
    primary_headline_excluded_pair_ids,
    validate_semantic_validity_cli_options,
)


def test_semantic_validity_config_loads() -> None:
    config = _load_config(
        Path("experiments/semantic-validity-evaluation-config-v1.json")
    )
    assert config["config_version"] == "semantic-validity-evaluation-config-1.0"
    assert max_abstention_rate(config) == 0.5
    assert len(primary_headline_excluded_pair_ids(config)) == 27


def test_primary_headline_filter_excludes_context_required_pairs() -> None:
    config = _load_config(
        Path("experiments/semantic-validity-evaluation-config-v1.json")
    )
    records = load_benchmark_jsonl(Path("benchmarks/development.jsonl"))
    filtered, provenance = apply_primary_headline_population_filter(records, config)
    assert provenance is not None
    assert provenance["excluded_count"] == 17
    assert provenance["primary_headline_record_count"] == 383
    assert provenance["input_record_count"] == 400
    excluded = primary_headline_excluded_pair_ids(config)
    assert all(record.id not in excluded for record in filtered)


def test_semantic_validity_config_rejects_freshness_policy() -> None:
    config = _load_config(
        Path("experiments/semantic-validity-evaluation-config-v1.json")
    )
    with pytest.raises(ValueError, match="freshness policy"):
        validate_semantic_validity_cli_options(
            config,
            freshness_policy="default",
            adaptive_threshold_map=None,
            adaptive_threshold_map_output=None,
        )


def test_evaluation_config_1_0_does_not_filter_records() -> None:
    config = _load_config(Path("experiments/evaluation_config.json"))
    records = load_benchmark_jsonl(Path("benchmarks/development.jsonl"))
    filtered, provenance = apply_primary_headline_population_filter(records, config)
    assert provenance is None
    assert filtered == records
