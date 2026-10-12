import json
from types import SimpleNamespace

import pytest

from sscre.baseline import (
    _threshold_for_record,
    run_compatibility_cache_baseline,
    select_adaptive_domain_thresholds,
)
from sscre.benchmark import BenchmarkMetadata, BenchmarkRecord
from sscre.evaluate import _load_adaptive_threshold_map


def _record(index: int, domain: str) -> BenchmarkRecord:
    query = f"Explain cache policy {index}"
    return BenchmarkRecord(
        id=f"pair-{index:04d}",
        query_a=query,
        query_b=query,
        reusable=True,
        compatibility_label="compatible",
        coverage_category="paraphrase",
        metadata=BenchmarkMetadata(domain=domain),
        review_status="final",
    )


def test_adaptive_selection_falls_back_for_small_strata() -> None:
    selected, diagnostics = select_adaptive_domain_thresholds(
        [_record(index, "large") for index in range(1, 11)]
        + [_record(11, "small")],
        dataset_version="reviewed-query-pairs-2.0",
        thresholds=[0.8, 0.9, 0.95],
    )

    assert selected["small"] == 0.95
    assert diagnostics["domains"]["small"]["selection_rule"] == (
        "fallback_small_stratum"
    )


def test_adaptive_selection_uses_lowest_threshold_on_equal_safe_hit_rate() -> None:
    selected, diagnostics = select_adaptive_domain_thresholds(
        [_record(index, "large") for index in range(1, 11)],
        dataset_version="reviewed-query-pairs-2.0",
        thresholds=[0.8, 0.9, 0.95],
    )

    assert selected["large"] == 0.8
    assert diagnostics["domains"]["large"]["pair_count"] == 10


def test_adaptive_selection_rejects_domain_without_safe_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [
        BenchmarkRecord(
            id=f"incompatible-{index:04d}",
            query_a=f"Explain cache policy {index}",
            query_b=f"Explain cache policy {index}",
            reusable=False,
            compatibility_label="incompatible",
            coverage_category="intent_change",
            failure_category="intent_mismatch",
            reason="different intent",
            metadata=BenchmarkMetadata(domain="large"),
            review_status="final",
        )
        for index in range(10)
    ]

    monkeypatch.setattr(
        "sscre.baseline.run_compatibility_cache_baseline",
        lambda records, *, threshold, **kwargs: SimpleNamespace(
            threshold=threshold,
            hit_rate=0.0,
            false_positive_rate=1.0,
            estimated_cost_usd=0.0,
            p95_latency_ms=0.0,
        ),
    )

    with pytest.raises(ValueError, match="no threshold satisfying"):
        select_adaptive_domain_thresholds(
            records,
            dataset_version="reviewed-query-pairs-2.0",
            thresholds=[0.8, 0.9, 0.95],
        )


def test_threshold_policy_uses_domain_and_unknown_fallback() -> None:
    record = _record(1, "large")
    unknown = _record(2, "")
    policy = {"large": 0.8, "__default__": 0.95}

    assert _threshold_for_record(policy, record) == 0.8
    assert _threshold_for_record(policy, unknown) == 0.95


def test_adaptive_threshold_map_rejects_malformed_entries(tmp_path) -> None:
    path = tmp_path / "threshold-map.json"
    path.write_text(
        json.dumps(
            {
                "selection_split": "development",
                "default_threshold": 0.95,
                "threshold_map": {"large": "low"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid entry"):
        _load_adaptive_threshold_map(path)


def test_adaptive_policy_preserves_compatibility_safety() -> None:
    report = run_compatibility_cache_baseline(
        [_record(1, "large")],
        dataset_version="reviewed-query-pairs-2.0",
        threshold={"large": 0.8, "__default__": 0.95},
    )

    assert report.unsafe_reuse_hits == 0
    if report.labeled_reuse_hits == 0:
        assert report.false_positive_rate is None
        assert (
            report.false_positive_rate_unavailable_reason
            == "no_labeled_reuse_hits"
        )
    else:
        assert report.false_positive_rate == 0.0
