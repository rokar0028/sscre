import json

from sscre.baseline import (
    run_compatibility_cache_baseline,
    run_embedding_cache_baseline,
    run_exact_cache_baseline,
    run_no_cache_baseline,
    save_compatibility_cache_report,
)
from sscre.benchmark import load_benchmark_jsonl
from sscre.evaluation_statistics import MAX_BASELINE_REQUEST_SAMPLES
from sscre.serialization import redact_operational_evaluation_report

_PROJECT_ROOT = __file__
_DATASET_VERSION = "reviewed-query-pairs-1.1"


def _development_records():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    return load_benchmark_jsonl(root / "benchmarks" / "development.jsonl")


def test_no_cache_request_samples_match_request_count() -> None:
    records = _development_records()
    report = run_no_cache_baseline(records, dataset_version=_DATASET_VERSION)
    assert report.request_count == len(records) * 2
    assert len(report.request_samples) == report.request_count
    assert {sample["pair_id"] for sample in report.request_samples} == {
        record.id for record in records
    }


def test_exact_cache_samples_are_deterministically_ordered() -> None:
    records = _development_records()
    first = run_exact_cache_baseline(records, dataset_version=_DATASET_VERSION)
    second = run_exact_cache_baseline(records, dataset_version=_DATASET_VERSION)
    assert len(first.request_samples) == first.request_count
    assert first.request_samples == second.request_samples
    directions = [sample["direction"] for sample in first.request_samples]
    assert directions[:2] == ["a_to_b", "b_to_a"]


def test_collect_request_samples_can_be_disabled() -> None:
    records = _development_records()[:1]
    report = run_embedding_cache_baseline(
        records,
        dataset_version=_DATASET_VERSION,
        threshold=0.9,
        collect_request_samples=False,
    )
    assert report.request_count == 2
    assert report.request_samples == ()


def test_compatibility_samples_exclude_query_text(tmp_path) -> None:
    records = _development_records()[:2]
    report = run_compatibility_cache_baseline(
        records,
        dataset_version=_DATASET_VERSION,
        threshold=0.9,
    )
    assert len(report.request_samples) == report.request_count
    encoded = json.dumps(report.request_samples)
    for record in records:
        assert record.query_a not in encoded
        assert record.query_b not in encoded
    assert "query_a" not in encoded
    path = tmp_path / "report.json"
    save_compatibility_cache_report(report, path)
    payload = redact_operational_evaluation_report(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert payload["request_samples"] == list(report.request_samples)


def test_request_sample_indicators_are_binary() -> None:
    records = _development_records()[:1]
    report = run_compatibility_cache_baseline(
        records,
        dataset_version=_DATASET_VERSION,
        threshold=0.9,
    )
    for sample in report.request_samples:
        for key in (
            "cache_hit",
            "generated",
            "false_positive",
            "safe_reuse_hit",
            "unlabeled_candidate_reuse",
        ):
            assert sample[key] in (0, 1)


def test_embedding_latency_samples_align_with_request_count() -> None:
    records = _development_records()
    report = run_embedding_cache_baseline(
        records,
        dataset_version=_DATASET_VERSION,
        threshold=0.9,
    )
    assert len(report.request_samples) == report.request_count
    latencies = [sample["latency_ms"] for sample in report.request_samples]
    assert all(isinstance(value, (int, float)) for value in latencies)


def test_request_sample_bound_constant_covers_phase2_scale() -> None:
    assert MAX_BASELINE_REQUEST_SAMPLES >= 1000
