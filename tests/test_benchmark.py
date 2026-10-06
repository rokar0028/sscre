import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from sscre.baseline import (
    run_compatibility_cache_baseline,
    run_embedding_cache_baseline,
    run_exact_cache_baseline,
    run_no_cache_baseline,
    run_embedding_threshold_sweep,
    save_exact_cache_report,
    save_no_cache_report,
)
from sscre.benchmark import (
    BENCHMARK_SCHEMA_VERSION,
    BenchmarkRecord,
    BenchmarkValidationError,
    load_benchmark_jsonl,
)
from sscre.llm import LLMResult
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.evaluate import main


def valid_record(record_id: str = "pair-0001") -> dict[str, object]:
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "id": record_id,
        "query_a": "Give me Python code for binary search.",
        "query_b": "Give me Java code for binary search.",
        "reusable": False,
        "correctness_label": "correct",
        "compatibility_label": "incompatible",
        "reason": "programming language constraint differs",
    }


def test_benchmark_record_keeps_labels_separate() -> None:
    record = BenchmarkRecord.model_validate(valid_record())

    assert record.id == "pair-0001"
    assert record.reusable is False
    assert record.correctness_label == "correct"
    assert record.compatibility_label == "incompatible"


def test_non_reusable_record_requires_reason() -> None:
    payload = valid_record()
    payload["reason"] = None

    with pytest.raises(ValidationError, match="reason is required"):
        BenchmarkRecord.model_validate(payload)


def test_record_id_must_be_stable_format() -> None:
    payload = valid_record("Pair 1")

    with pytest.raises(ValidationError):
        BenchmarkRecord.model_validate(payload)


def test_jsonl_loader_validates_records_and_duplicate_ids(tmp_path) -> None:
    benchmark_path = tmp_path / "benchmark.jsonl"
    benchmark_path.write_text(
        "\n".join(
            [
                json.dumps(valid_record()),
                json.dumps(valid_record("pair-0002")),
            ]
        ),
        encoding="utf-8",
    )

    records = load_benchmark_jsonl(benchmark_path)

    assert [record.id for record in records] == ["pair-0001", "pair-0002"]

    benchmark_path.write_text(
        json.dumps(valid_record()) + "\n" + json.dumps(valid_record()),
        encoding="utf-8",
    )
    with pytest.raises(BenchmarkValidationError, match="duplicate record id"):
        load_benchmark_jsonl(benchmark_path)


def test_jsonl_loader_reports_invalid_line(tmp_path) -> None:
    benchmark_path = tmp_path / "benchmark.jsonl"
    benchmark_path.write_text(
        json.dumps(valid_record()) + "\nnot-json\n",
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkValidationError, match=r"benchmark\.jsonl:2"):
        load_benchmark_jsonl(benchmark_path)


def test_reviewed_dataset_has_required_coverage() -> None:
    dataset_path = (
        Path(__file__).resolve().parents[1]
        / "benchmarks"
        / "reviewed_query_pairs.jsonl"
    )

    records = load_benchmark_jsonl(dataset_path)

    assert len(records) >= 20
    assert any(
        record.query_a == record.query_b and record.reusable for record in records
    )
    assert any(
        record.query_a != record.query_b
        and "  " in record.query_b
        and record.reusable
        for record in records
    )
    assert any(
        not record.reusable
        and record.compatibility_label == "incompatible"
        and record.reason
        for record in records
    )


def test_development_and_held_out_splits_are_disjoint() -> None:
    benchmark_dir = Path(__file__).resolve().parents[1] / "benchmarks"
    development = load_benchmark_jsonl(benchmark_dir / "development.jsonl")
    held_out = load_benchmark_jsonl(benchmark_dir / "held_out_test.jsonl")
    full_dataset = load_benchmark_jsonl(
        benchmark_dir / "reviewed_query_pairs.jsonl"
    )

    development_ids = {record.id for record in development}
    held_out_ids = {record.id for record in held_out}
    full_dataset_ids = {record.id for record in full_dataset}

    assert len(development) == 16
    assert len(held_out) == 8
    assert development_ids.isdisjoint(held_out_ids)
    assert development_ids | held_out_ids == full_dataset_ids


class FixedLLMClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def generate(self, query: str) -> LLMResult:
        self.queries.append(query)
        return LLMResult(
            text="fixed answer",
            input_tokens=3,
            output_tokens=2,
            latency_ms=7,
        )


def test_no_cache_baseline_generates_both_directions_and_saves_report(
    tmp_path,
) -> None:
    records = [
        BenchmarkRecord.model_validate(valid_record()),
        BenchmarkRecord.model_validate(valid_record("pair-0002")),
    ]
    client = FixedLLMClient()

    report = run_no_cache_baseline(
        records,
        dataset_version="test-v1",
        llm_client=client,
        input_cost_per_1k_tokens=1.0,
        output_cost_per_1k_tokens=2.0,
    )

    assert report.request_count == 4
    assert report.generated_requests == 4
    assert report.cache_hits == 0
    assert report.cache_misses == 0
    assert report.input_tokens == 12
    assert report.output_tokens == 8
    assert report.total_latency_ms == 28
    assert report.average_latency_ms == 7
    assert report.estimated_cost_usd == 0.028
    assert client.queries == [
        "Give me Python code for binary search.",
        "Give me Java code for binary search.",
    ] * 2

    report_path = tmp_path / "no-cache.json"
    save_no_cache_report(report, report_path)
    assert '"baseline": "no-cache"' in report_path.read_text(encoding="utf-8")


def test_exact_cache_baseline_reports_hits_reuse_and_saved_tokens(tmp_path) -> None:
    records = [
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-0001"),
                "query_a": "What is caching?",
                "query_b": "What is caching?",
                "reusable": True,
                "compatibility_label": "compatible",
                "reason": None,
            }
        ),
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-0002"),
                "query_a": "Explain exact caching.",
                "query_b": "  Explain   exact caching. ",
                "reusable": True,
                "compatibility_label": "compatible",
                "reason": None,
            }
        ),
    ]
    client = FixedLLMClient()

    report = run_exact_cache_baseline(
        records,
        dataset_version="test-v1",
        llm_client=client,
        input_cost_per_1k_tokens=1.0,
        output_cost_per_1k_tokens=2.0,
        cache_lookup_cost_usd=0.001,
        preprocessing_cost_usd=0.0005,
    )

    assert report.request_count == 4
    assert report.generated_requests == 2
    assert report.cache_hits == 2
    assert report.cache_misses == 2
    assert report.hit_rate == 0.5
    assert report.safe_reuse_hits == 2
    assert report.reusable_opportunities == 2
    assert report.safe_reuse_coverage == 1.0
    assert report.tokens_saved == 10
    assert report.estimated_cost_usd == 0.02
    assert report.cache_miss_categories == {"not_cached": 2}

    report_path = tmp_path / "exact-cache.json"
    save_exact_cache_report(report, report_path)
    assert '"baseline": "exact-cache"' in report_path.read_text(encoding="utf-8")


def test_embedding_baseline_reports_reuse_and_false_positives() -> None:
    records = [
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-0001"),
                "query_a": "alpha query",
                "query_b": "beta query",
                "reusable": True,
                "compatibility_label": "compatible",
                "reason": None,
            }
        ),
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-0002"),
                "query_a": "gamma query",
                "query_b": "delta query",
                "reusable": False,
            }
        ),
    ]
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={
            "alpha query": (1.0, 0.0),
            "beta query": (1.0, 0.0),
            "gamma query": (1.0, 0.0),
            "delta query": (1.0, 0.0),
        },
    )

    report = run_embedding_cache_baseline(
        records,
        dataset_version="test-v1",
        threshold=0.9,
        embedding_client=embedding_client,
    )

    assert report.cache_hits == 3
    assert report.safe_reuse_hits == 1
    assert report.unsafe_reuse_hits == 1
    assert report.precision == 0.5
    assert report.false_positive_rate == pytest.approx(1 / 3)
    assert report.embedding_tokens > 0


def test_compatibility_baseline_reports_safety_and_abstention_metrics() -> None:
    records = [
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-0001"),
                "query_a": "Write Python code for binary search",
                "query_b": "Implement Python binary search",
                "reusable": True,
                "compatibility_label": "compatible",
                "reason": None,
            }
        ),
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-0002"),
                "query_a": "Write Java code for binary search",
                "query_b": "Implement Python binary search",
                "reusable": False,
                "compatibility_label": "incompatible",
            }
        ),
    ]
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={
            "Write Python code for binary search": (1.0, 0.0),
            "Implement Python binary search": (1.0, 0.0),
            "Write Java code for binary search": (1.0, 0.0),
        },
    )

    report = run_compatibility_cache_baseline(
        records,
        dataset_version="test-v1",
        threshold=0.9,
        embedding_client=embedding_client,
    )

    assert report.baseline == "compatibility-cache"
    assert report.safe_reuse_hits >= 1
    assert report.unsafe_reuse_hits >= 0
    assert 0.0 <= report.precision <= 1.0
    assert "correct" in report.correctness_label_counts
    assert report.compatibility_label_counts["incompatible"] == 1
    assert "intent" in report.decision_breakdowns
    assert "constraint" in report.decision_breakdowns
    assert set(report.label_sections) == {
        "compatibility",
        "correctness",
        "preference",
    }
    assert "compatible" in report.label_sections["compatibility"]
    assert "correct" in report.label_sections["correctness"]
    assert "not_collected" in report.label_sections["preference"]


def test_embedding_threshold_sweep_selects_dev_threshold() -> None:
    records = [
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-0001"),
                "query_a": "first query",
                "query_b": "second query",
                "reusable": True,
                "compatibility_label": "compatible",
                "reason": None,
            }
        )
    ]
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={
            "first query": (1.0, 0.0),
            "second query": (0.99, 0.141067),
        },
    )

    sweep = run_embedding_threshold_sweep(
        records,
        dataset_version="development-v1",
        thresholds=[0.5, 0.9],
        max_false_positive_rate=0.0,
        embedding_client=embedding_client,
    )

    assert sweep.dataset_version == "development-v1"
    assert sweep.selected_threshold == 0.9
    assert "safe reuse coverage" in sweep.selection_rule
    assert len(sweep.reports) == 2


def test_evaluate_command_writes_selected_baseline_report(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "report.json"

    status = main(
        [
            "--benchmark",
            str(project_root / "benchmarks" / "development.jsonl"),
            "--config",
            str(project_root / "experiments" / "evaluation_config.json"),
            "--baseline",
            "exact-cache",
            "--output",
            str(output_path),
        ]
    )

    assert status == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["baseline"] == "exact-cache"
    assert report["dataset_version"] == "reviewed-query-pairs-1.0"
    assert report["config_version"] == "evaluation-config-1.0"
    assert report["execution_timestamp"].endswith("+00:00")
    assert report["software_version"] == "0.1.0"
    assert "git_commit" in report
    assert report["evaluation_split"] == "development"
    assert "git_worktree_dirty" in report


def test_no_cache_report_uses_comparable_metric_fields(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "no-cache.json"

    status = main(
        [
            "--benchmark",
            str(project_root / "benchmarks" / "development.jsonl"),
            "--config",
            str(project_root / "experiments" / "evaluation_config.json"),
            "--baseline",
            "no-cache",
            "--output",
            str(output_path),
        ]
    )

    assert status == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    for field_name in (
        "safe_reuse_hits",
        "reusable_opportunities",
        "safe_reuse_coverage",
        "input_tokens_saved",
        "output_tokens_saved",
        "tokens_saved",
        "cache_lookup_cost_usd",
        "preprocessing_cost_usd",
        "cache_miss_categories",
        "failure_categories",
    ):
        assert field_name in report


def test_held_out_comparison_uses_development_threshold(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "comparison.json"

    status = main(
        [
            "--benchmark",
            str(project_root / "benchmarks" / "held_out_test.jsonl"),
            "--config",
            str(project_root / "experiments" / "evaluation_config.json"),
            "--baseline",
            "all",
            "--split",
            "held-out",
            "--output",
            str(output_path),
        ]
    )

    assert status == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["evaluation_split"] == "held-out"
    assert report["threshold_selection"]["dataset_version"] == (
        "reviewed-query-pairs-1.0"
    )
    assert set(report["baselines"]) == {
        "no-cache",
        "exact-cache",
        "embedding-cache",
        "compatibility-cache",
    }
    embedding_report = report["baselines"]["embedding-cache"]
    assert embedding_report["embedding_model"] == "fake-embedding"
    assert embedding_report["embedding_dimension"] == 8
    assert embedding_report["top_k"] == 5
    assert "false_positive_examples" in embedding_report
    assert "p50_latency_ms" in embedding_report
    assert "p95_latency_ms" in embedding_report
    assert "p99_latency_ms" in embedding_report
    assert "failure_gallery" in report
    assert "strategy_c_failures" in report["failure_gallery"]


def test_evaluate_requires_declared_split_path(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]

    status = main(
        [
            "--benchmark",
            str(project_root / "benchmarks" / "held_out_test.jsonl"),
            "--config",
            str(project_root / "experiments" / "evaluation_config.json"),
            "--baseline",
            "exact-cache",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )

    assert status != 0


def test_evaluate_rejects_tampered_split_manifest(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    source_dir = project_root / "benchmarks"
    benchmark_dir = tmp_path / "benchmarks"
    benchmark_dir.mkdir()
    for filename in (
        "development.jsonl",
        "held_out_test.jsonl",
        "reviewed_query_pairs.jsonl",
        "split_manifest.json",
    ):
        shutil.copy(source_dir / filename, benchmark_dir / filename)

    development_path = benchmark_dir / "development.jsonl"
    development_path.write_text(
        "\n".join(development_path.read_text(encoding="utf-8").splitlines()[:-1])
        + "\n",
        encoding="utf-8",
    )

    status = main(
        [
            "--benchmark",
            str(development_path),
            "--config",
            str(project_root / "experiments" / "evaluation_config.json"),
            "--baseline",
            "exact-cache",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )

    assert status != 0


def test_evaluate_command_returns_nonzero_for_invalid_benchmark(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]

    status = main(
        [
            "--benchmark",
            str(tmp_path / "missing.jsonl"),
            "--config",
            str(project_root / "experiments" / "evaluation_config.json"),
            "--baseline",
            "no-cache",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )

    assert status != 0
