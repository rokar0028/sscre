import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

import sscre.baseline as baseline_module
from sscre.baseline import (
    run_compatibility_cache_baseline,
    run_embedding_cache_baseline,
    run_exact_cache_baseline,
    run_no_cache_baseline,
    run_embedding_threshold_sweep,
    save_compatibility_cache_report,
    save_exact_cache_report,
    save_no_cache_report,
)
from sscre.benchmark import (
    BENCHMARK_SCHEMA_VERSION,
    BenchmarkRecord,
    BenchmarkValidationError,
    load_benchmark_jsonl,
)
from sscre.benchmark_annotation import (
    ANNOTATION_GUIDE_VERSION,
    validate_review_policy,
)
from sscre.benchmark_splits import (
    load_split_manifest,
    resolve_rebuild_split_ids,
    validate_benchmark_dataset,
    validate_cross_split_leakage,
    validate_no_duplicate_pair_keys,
)
from sscre.benchmark_validate import main as validate_main
from sscre.benchmark_coverage import (
    PHASE2_REVIEWED_COVERAGE,
    WORKING_BASELINE_COVERAGE,
    build_coverage_report,
    validate_coverage,
)
from sscre.llm import LLMResult
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.evaluate import main
from sscre.serialization import BOUNDARY_SERIALIZATION_VERSION
from sscre.safety import (
    CANDIDATE_TRACE_CONTRACT_VERSION,
    SAFETY_EVALUATION_CONTRACT_VERSION,
)


def valid_record(record_id: str = "pair-0001") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "id": record_id,
        "query_a": "Give me Python code for binary search.",
        "query_b": "Give me Java code for binary search.",
        "reusable": False,
        "correctness_label": "correct",
        "compatibility_label": "incompatible",
        "reason": "programming language constraint differs",
    }


def valid_record_1_1(record_id: str = "pair-0001") -> dict[str, object]:
    return {
        **valid_record(record_id),
        "schema_version": "1.1",
        "correctness_label": None,
        "failure_category": "constraint_mismatch",
        "coverage_category": "constraint_change",
        "review_status": "final",
        "annotation_source": "human_review",
    }


def test_benchmark_record_keeps_labels_separate() -> None:
    record = BenchmarkRecord.model_validate(valid_record())

    assert record.id == "pair-0001"
    assert record.reusable is False
    assert record.expected_reuse is False
    assert record.correctness_label == "correct"
    assert record.compatibility_label == "incompatible"
    assert record.expected_compatibility == "incompatible"
    assert record.directionality == "ordered"
    assert record.freshness_class == "stable"
    assert record.answer_availability == "none"


def test_benchmark_record_supports_versioned_phase_2_metadata() -> None:
    record = BenchmarkRecord.model_validate(
        {
            **valid_record_1_1("pair-0002"),
            "directionality": "ordered",
            "expected_reuse": False,
            "expected_compatibility": "incompatible",
            "failure_category": "constraint_mismatch",
            "freshness_class": "semi_dynamic",
            "metadata": {
                "intent": "code_generation",
                "domain": "programming",
                "entities": ["binary_search"],
                "constraints": {"language": "python"},
                "output_format": "source_code",
            },
            "answer_availability": "none",
            "review_status": "final",
            "annotator_count": 2,
        }
    )

    assert record.schema_version == "1.1"
    assert record.failure_category == "constraint_mismatch"
    assert record.metadata.entities == ("binary_search",)
    assert record.metadata.constraints == {"language": "python"}
    assert record.annotator_count == 2


def test_benchmark_record_rejects_mismatched_canonical_labels() -> None:
    payload = valid_record()
    payload["expected_reuse"] = True

    with pytest.raises(ValidationError, match="expected_reuse"):
        BenchmarkRecord.model_validate(payload)


def test_schema_1_1_incompatible_requires_failure_category() -> None:
    payload = valid_record_1_1()
    payload["failure_category"] = "none"

    with pytest.raises(ValidationError, match="failure_category"):
        BenchmarkRecord.model_validate(payload)


def test_schema_1_1_reusable_compatible_requires_none_failure_category() -> None:
    payload = valid_record_1_1("pair-pos")
    payload.update(
        {
            "reusable": True,
            "compatibility_label": "compatible",
            "reason": None,
            "failure_category": "none",
            "correctness_label": None,
        }
    )

    record = BenchmarkRecord.model_validate(payload)

    assert record.reusable is True
    assert record.failure_category == "none"


def test_schema_1_1_correctness_requires_answer_availability() -> None:
    payload = valid_record_1_1()
    payload["correctness_label"] = "correct"
    payload["answer_availability"] = "none"

    with pytest.raises(ValidationError, match="answer_availability"):
        BenchmarkRecord.model_validate(payload)


def test_preference_requires_answer_availability() -> None:
    payload = valid_record_1_1()
    payload["preference_label"] = "A"
    payload["answer_availability"] = "none"

    with pytest.raises(ValidationError, match="preference_label"):
        BenchmarkRecord.model_validate(payload)


def test_metadata_rejects_oversized_constraints() -> None:
    payload = valid_record_1_1()
    payload["metadata"] = {
        "constraints": {"language": "x" * 300},
    }

    with pytest.raises(ValidationError, match="constraint"):
        BenchmarkRecord.model_validate(payload)


def test_jsonl_loader_rejects_unsupported_schema_version(tmp_path) -> None:
    benchmark_path = tmp_path / "benchmark.jsonl"
    payload = valid_record()
    payload["schema_version"] = "2.0"
    benchmark_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(BenchmarkValidationError, match="unsupported schema_version"):
        load_benchmark_jsonl(benchmark_path)


def test_jsonl_loader_can_require_final_review_status(tmp_path) -> None:
    benchmark_path = tmp_path / "benchmark.jsonl"
    benchmark_path.write_text(json.dumps(valid_record_1_1()), encoding="utf-8")

    load_benchmark_jsonl(benchmark_path, require_final_review=True)

    draft = valid_record_1_1("pair-0002")
    draft["review_status"] = "draft"
    benchmark_path.write_text(
        json.dumps(valid_record_1_1()) + "\n" + json.dumps(draft),
        encoding="utf-8",
    )
    with pytest.raises(BenchmarkValidationError, match="review_status must be final"):
        load_benchmark_jsonl(benchmark_path, require_final_review=True)


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

    assert len(records) >= 32
    assert all(record.schema_version == "1.1" for record in records)
    assert all(record.coverage_category for record in records)
    validate_coverage(records, policy=WORKING_BASELINE_COVERAGE)
    report = build_coverage_report(records, policy=WORKING_BASELINE_COVERAGE)
    assert report["positive_count"] >= 6
    assert report["negative_count"] >= 6
    validate_coverage(records, policy=PHASE2_REVIEWED_COVERAGE)


def test_reviewed_dataset_satisfies_annotation_policy() -> None:
    benchmark_dir = Path(__file__).resolve().parents[1] / "benchmarks"
    full = load_benchmark_jsonl(benchmark_dir / "reviewed_query_pairs.jsonl")
    held_out = load_benchmark_jsonl(benchmark_dir / "held_out_test.jsonl")

    validate_review_policy(full, split="full")
    validate_review_policy(held_out, split="held-out")

    manifest = json.loads(
        (benchmark_dir / "split_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["annotation_guide_version"] == ANNOTATION_GUIDE_VERSION


def test_held_out_review_policy_rejects_draft_records() -> None:
    record = BenchmarkRecord.model_validate(valid_record_1_1("pair-draft"))
    record = record.model_copy(update={"review_status": "draft"})

    with pytest.raises(BenchmarkValidationError, match="held-out split rejects"):
        validate_review_policy([record], split="held-out")


def test_candidate_redaction_rejects_secrets() -> None:
    payload = valid_record_1_1()
    payload["query_a"] = "Use sk-test-SECRETVALUE here"
    payload["source_group"] = "hand_authored_v1:test"

    with pytest.raises(BenchmarkValidationError, match="redaction"):
        from sscre.benchmark_build import validate_candidate_record

        validate_candidate_record(BenchmarkRecord.model_validate(payload))


def test_assign_next_pair_id_increments() -> None:
    from sscre.benchmark_build import assign_next_pair_id

    assert assign_next_pair_id({"pair-0032"}) == "pair-0033"


def test_benchmark_build_reorders_global_benchmark_dir_flag() -> None:
    from sscre.benchmark_build import _reorder_global_benchmark_dir

    assert _reorder_global_benchmark_dir(
        ["freeze-splits", "--benchmark-dir", "benchmarks"]
    ) == ["--benchmark-dir", "benchmarks", "freeze-splits"]
    assert _reorder_global_benchmark_dir(
        ["--benchmark-dir", "benchmarks", "freeze-splits"]
    ) == ["--benchmark-dir", "benchmarks", "freeze-splits"]


def test_resolve_rebuild_split_ids_matches_repository_manifest() -> None:
    benchmark_dir = Path(__file__).resolve().parents[1] / "benchmarks"
    dev_ids, held_ids = resolve_rebuild_split_ids(benchmark_dir)
    assert len(dev_ids) == 400
    assert len(held_ids) == 215
    assert dev_ids.isdisjoint(held_ids)


def test_benchmark_dataset_integrity_passes_for_repository_fixture() -> None:
    benchmark_dir = Path(__file__).resolve().parents[1] / "benchmarks"
    validate_benchmark_dataset(benchmark_dir)
    assert validate_main(["--benchmark-dir", str(benchmark_dir)]) == 0


def test_benchmark_validate_phase2_passes_for_repository_fixture() -> None:
    benchmark_dir = Path(__file__).resolve().parents[1] / "benchmarks"
    assert (
        validate_main(
            ["--benchmark-dir", str(benchmark_dir), "--phase2", "--production"]
        )
        == 0
    )


def test_split_manifest_rejects_sha256_mismatch(tmp_path) -> None:
    project = Path(__file__).resolve().parents[1]
    benchmark_dir = tmp_path / "benchmarks"
    benchmark_dir.mkdir()
    for name in (
        "reviewed_query_pairs.jsonl",
        "development.jsonl",
        "held_out_test.jsonl",
        "split_manifest.json",
    ):
        shutil.copy(project / "benchmarks" / name, benchmark_dir / name)
    manifest_path = benchmark_dir / "split_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_dataset"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(BenchmarkValidationError, match="sha256 mismatch"):
        validate_benchmark_dataset(benchmark_dir)


def test_cross_split_leakage_rejects_shared_fingerprint() -> None:
    dev = BenchmarkRecord.model_validate(valid_record_1_1("pair-dev"))
    held = BenchmarkRecord.model_validate(valid_record_1_1("pair-held"))
    held = held.model_copy(
        update={
            "query_a": dev.query_a,
            "query_b": dev.query_b,
        }
    )

    with pytest.raises(BenchmarkValidationError, match="normalized pair fingerprint"):
        validate_cross_split_leakage([dev], [held])


def test_duplicate_normalized_pair_keys_are_rejected() -> None:
    first = BenchmarkRecord.model_validate(valid_record_1_1("pair-a"))
    second = BenchmarkRecord.model_validate(valid_record_1_1("pair-b"))

    with pytest.raises(BenchmarkValidationError, match="duplicate normalized pair"):
        validate_no_duplicate_pair_keys([first, second])


def test_reversed_pair_leakage_is_rejected() -> None:
    dev = BenchmarkRecord.model_validate(valid_record_1_1("pair-dev"))
    held = BenchmarkRecord.model_validate(
        {
            **valid_record_1_1("pair-held"),
            "query_a": dev.query_b,
            "query_b": dev.query_a,
        }
    )

    with pytest.raises(
        BenchmarkValidationError,
        match="reverses a development|normalized pair fingerprint",
    ):
        validate_cross_split_leakage([dev], [held])


def test_shared_source_group_leakage_is_rejected() -> None:
    dev = BenchmarkRecord.model_validate(
        {
            **valid_record_1_1("pair-dev"),
            "query_a": "dev query alpha",
            "query_b": "dev query beta",
            "source_group": "template_v1:seed-a",
        }
    )
    held = BenchmarkRecord.model_validate(
        {
            **valid_record_1_1("pair-held"),
            "query_a": "held query gamma",
            "query_b": "held query delta",
            "source_group": "template_v1:seed-a",
        }
    )

    with pytest.raises(BenchmarkValidationError, match="shares source_group"):
        validate_cross_split_leakage([dev], [held])


def test_near_duplicate_leakage_is_rejected() -> None:
    query_a = " ".join(f"w{i}" for i in range(20))
    query_b = " ".join(f"x{i}" for i in range(20))
    dev = BenchmarkRecord.model_validate(
        {
            **valid_record_1_1("pair-dev"),
            "query_a": query_a,
            "query_b": query_b,
        }
    )
    held = BenchmarkRecord.model_validate(
        {
            **valid_record_1_1("pair-held"),
            "query_a": f"{query_a} wextra",
            "query_b": f"{query_b} xextra",
        }
    )

    with pytest.raises(BenchmarkValidationError, match="near-duplicate"):
        validate_cross_split_leakage([dev], [held])


def test_unsupported_manifest_schema_version_rejected(tmp_path) -> None:
    manifest_path = tmp_path / "split_manifest.json"
    manifest_path.write_text(
        json.dumps({"manifest_schema_version": "9.9.9"}),
        encoding="utf-8",
    )

    with pytest.raises(BenchmarkValidationError, match="unsupported manifest_schema"):
        load_split_manifest(manifest_path)


def test_development_split_sha256_mismatch_rejected(tmp_path) -> None:
    project = Path(__file__).resolve().parents[1]
    benchmark_dir = tmp_path / "benchmarks"
    benchmark_dir.mkdir()
    for name in (
        "reviewed_query_pairs.jsonl",
        "development.jsonl",
        "held_out_test.jsonl",
        "split_manifest.json",
    ):
        shutil.copy(project / "benchmarks" / name, benchmark_dir / name)
    manifest_path = benchmark_dir / "split_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["development"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(BenchmarkValidationError, match="development sha256 mismatch"):
        validate_benchmark_dataset(benchmark_dir)


def test_validate_coverage_reports_missing_category() -> None:
    records = [
        BenchmarkRecord.model_validate(valid_record_1_1("pair-only")),
    ]

    with pytest.raises(BenchmarkValidationError, match="coverage category .+ requires at least"):
        validate_coverage(records, policy=WORKING_BASELINE_COVERAGE)


def test_disputed_record_requires_adjudication_status() -> None:
    with pytest.raises(ValidationError, match="disputed adjudication"):
        BenchmarkRecord.model_validate(
            {
                **valid_record_1_1("pair-disputed"),
                "review_status": "disputed",
                "adjudication_status": "final",
            }
        )

    record = BenchmarkRecord.model_validate(
        {
            **valid_record_1_1("pair-disputed-ok"),
            "review_status": "disputed",
            "adjudication_status": "disputed",
        }
    )
    validate_review_policy([record], split="full")


def test_manifest_schema_version_is_required() -> None:
    manifest = load_split_manifest(
        Path(__file__).resolve().parents[1] / "benchmarks" / "split_manifest.json"
    )
    assert manifest["manifest_schema_version"] == "1.0.0"


def test_frozen_manifest_records_split_identity() -> None:
    benchmark_dir = Path(__file__).resolve().parents[1] / "benchmarks"
    manifest = json.loads((benchmark_dir / "split_manifest.json").read_text(encoding="utf-8"))

    assert manifest.get("frozen_at")
    assert manifest.get("software_version")
    assert manifest["development"]["record_ids"]
    assert manifest["held_out_test"]["record_ids"]
    assert manifest["leakage_validation"]["status"] == "passed"
    assert "coverage_summary" in manifest

    development = load_benchmark_jsonl(benchmark_dir / "development.jsonl")
    held_out = load_benchmark_jsonl(benchmark_dir / "held_out_test.jsonl")
    assert manifest["development"]["record_ids"] == [record.id for record in development]
    assert manifest["held_out_test"]["record_ids"] == [record.id for record in held_out]


def test_frozen_manifest_scale_counts_match_checked_in_files() -> None:
    benchmark_dir = Path(__file__).resolve().parents[1] / "benchmarks"
    manifest = json.loads((benchmark_dir / "split_manifest.json").read_text(encoding="utf-8"))

    source = load_benchmark_jsonl(benchmark_dir / "reviewed_query_pairs.jsonl")
    development = load_benchmark_jsonl(benchmark_dir / "development.jsonl")
    held_out = load_benchmark_jsonl(benchmark_dir / "held_out_test.jsonl")

    assert manifest["source_dataset"]["record_count"] == len(source) == 615
    assert manifest["development"]["record_count"] == len(development) == 400
    assert manifest["held_out_test"]["record_count"] == len(held_out) == 215
    assert manifest["coverage_summary"]["record_count"] == len(source)
    assert manifest["source_dataset"]["sha256"]
    assert manifest["development"]["sha256"]
    assert manifest["held_out_test"]["sha256"]


def test_evaluate_rejects_config_dataset_version_mismatch(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                **json.loads(
                    (
                        project_root / "experiments" / "evaluation_config.json"
                    ).read_text(encoding="utf-8")
                ),
                "dataset_version": "wrong-version",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    status = main(
        [
            "--benchmark",
            str(project_root / "benchmarks" / "development.jsonl"),
            "--config",
            str(config_path),
            "--baseline",
            "exact-cache",
            "--output",
            str(tmp_path / "report.json"),
        ]
    )

    assert status != 0


def test_evaluate_rejects_tampered_manifest_record_ids(tmp_path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    benchmark_dir = tmp_path / "benchmarks"
    benchmark_dir.mkdir()
    for filename in (
        "development.jsonl",
        "held_out_test.jsonl",
        "reviewed_query_pairs.jsonl",
        "split_manifest.json",
    ):
        shutil.copy(project_root / "benchmarks" / filename, benchmark_dir / filename)

    manifest_path = benchmark_dir / "split_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["development"]["record_ids"] = manifest["development"]["record_ids"][:-1]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    from sscre.benchmark_splits import validate_benchmark_dataset

    with pytest.raises(BenchmarkValidationError, match="record_ids do not match"):
        validate_benchmark_dataset(benchmark_dir)


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

    assert len(development) == 400
    assert len(held_out) == 215
    assert len(full_dataset) == 615
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
            "beta query": (0.99, 0.01),
            "gamma query": (0.0, 1.0),
            "delta query": (0.01, 0.99),
        },
    )

    report = run_embedding_cache_baseline(
        records,
        dataset_version="test-v1",
        threshold=0.9,
        embedding_client=embedding_client,
    )

    assert report.cache_hits == 2
    assert report.safe_reuse_hits == 1
    assert report.unsafe_reuse_hits == 1
    assert report.unlabeled_candidate_reuse_hits == 0
    assert report.precision == 0.5
    assert report.false_positive_rate == pytest.approx(0.5)
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


def test_compatibility_report_keeps_unsafe_and_uncertain_distinct() -> None:
    records = [
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-unsafe"),
                "query_a": "Write Java code for binary search",
                "query_b": "Implement Python binary search",
                "reusable": False,
                "compatibility_label": "incompatible",
            }
        ),
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-uncertain"),
                "query_a": "Explain binary search",
                "query_b": "Explain python binary search",
                "reusable": False,
                "compatibility_label": "incompatible",
                "reason": "language constraint is missing on one side",
            }
        ),
    ]
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={
            "Write Java code for binary search": (1.0, 0.0),
            "Implement Python binary search": (1.0, 0.0),
            "Explain binary search": (0.0, 1.0),
            "Explain python binary search": (0.0, 1.0),
        },
    )

    report = run_compatibility_cache_baseline(
        records,
        dataset_version="test-v1",
        threshold=0.9,
        embedding_client=embedding_client,
    )

    assert report.decision_counts["UNSAFE"] >= 1
    assert report.decision_counts["UNCERTAIN"] >= 1
    assert report.uncertain_decisions == report.decision_counts["UNCERTAIN"]
    uncertain = next(
        example
        for example in report.failure_examples
        if example["predicted_decision"] == "UNCERTAIN"
    )
    assert uncertain["candidate_traces"][0]["decision"] == "UNCERTAIN"
    assert uncertain["candidate_traces"][0]["reason"]
    assert uncertain["candidate_traces"][0]["candidate_order"] == 1


def test_saved_report_uses_boundary_schema_version(tmp_path: Path) -> None:
    report = run_no_cache_baseline(
        [BenchmarkRecord.model_validate(valid_record())],
        dataset_version="test-v1",
    )
    path = tmp_path / "report.json"
    save_no_cache_report(report, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == BOUNDARY_SERIALIZATION_VERSION
    assert payload["safety_contract_version"] == SAFETY_EVALUATION_CONTRACT_VERSION
    assert payload["trace_contract_version"] == CANDIDATE_TRACE_CONTRACT_VERSION
    assert list(payload) == sorted(payload)


def test_saved_compatibility_report_omits_query_text_in_failures(tmp_path) -> None:
    records = [
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-fp"),
                "query_a": "secret prompt alpha",
                "query_b": "secret prompt beta",
                "reusable": False,
                "compatibility_label": "incompatible",
            }
        ),
    ]
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={
            "secret prompt alpha": (1.0, 0.0),
            "secret prompt beta": (1.0, 0.0),
        },
    )
    report = run_compatibility_cache_baseline(
        records,
        dataset_version="test-v1",
        threshold=0.5,
        embedding_client=embedding_client,
    )
    assert report.failure_examples or report.false_positive_examples
    path = tmp_path / "compat.json"
    save_compatibility_cache_report(report, path)
    body = path.read_text(encoding="utf-8")
    assert "secret prompt alpha" not in body
    assert "secret prompt beta" not in body
    assert '"id": "pair-fp"' in body or '"id": "pair-fp",' in body


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
    assert sweep.constraint_satisfied is True
    assert len(sweep.reports) == 2


def test_embedding_threshold_sweep_reports_unsatisfied_constraint(
    monkeypatch,
) -> None:
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
    original_runner = baseline_module.run_embedding_cache_baseline

    def always_false_positive(records, **kwargs):
        report = original_runner(records, **kwargs)
        return replace(report, false_positive_rate=1.0)

    monkeypatch.setattr(
        baseline_module,
        "run_embedding_cache_baseline",
        always_false_positive,
    )
    sweep = baseline_module.run_embedding_threshold_sweep(
        records,
        dataset_version="development-v1",
        thresholds=[0.5, 0.9],
        max_false_positive_rate=0.0,
        embedding_client=FakeEmbeddingClient(
            config=EmbeddingConfig(model_name="test-embedding", dimension=2),
            vectors={
                "first query": (1.0, 0.0),
                "second query": (0.99, 0.141067),
            },
        ),
    )

    assert sweep.constraint_satisfied is False
    assert sweep.selected_threshold == 0.9


def test_embedding_threshold_sweep_unknown_fpr_not_eligible(monkeypatch) -> None:
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
    original_runner = baseline_module.run_embedding_cache_baseline

    def unknown_fpr(records, **kwargs):
        report = original_runner(records, **kwargs)
        return replace(
            report,
            false_positive_rate=None,
            false_positive_rate_unavailable_reason="no_labeled_reuse_hits",
            labeled_reuse_hits=0,
        )

    monkeypatch.setattr(
        baseline_module,
        "run_embedding_cache_baseline",
        unknown_fpr,
    )
    sweep = baseline_module.run_embedding_threshold_sweep(
        records,
        dataset_version="development-v1",
        thresholds=[0.5, 0.9],
        max_false_positive_rate=0.0,
        embedding_client=FakeEmbeddingClient(
            config=EmbeddingConfig(model_name="test-embedding", dimension=2),
            vectors={
                "first query": (1.0, 0.0),
                "second query": (0.99, 0.141067),
            },
        ),
    )

    assert sweep.constraint_satisfied is False


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
    assert report["dataset_version"] == "reviewed-query-pairs-2.0"
    assert report["config_version"] == "evaluation-config-1.0"
    assert len(report["config_sha256"]) == 64
    assert report["execution_timestamp"].endswith("+00:00")
    assert report["software_version"] == "0.1.0"
    assert "git_commit" in report
    assert report["evaluation_split"] == "development"
    assert "git_worktree_dirty" in report
    artifact = report["benchmark_artifact"]
    assert artifact["schema_version"] == "1.1"
    assert artifact["annotation_guide_version"] == "1.0.0"
    assert artifact["split_record_count"] == 400
    assert artifact["split_manifest_sha256"]
    assert artifact["coverage_summary"]["record_count"] == 615
    assert "final" in artifact["label_review_status_counts"]
    assert artifact["split_record_identity"]
    assert "query_a" not in json.dumps(artifact["split_record_identity"])


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
            "--freshness-policy",
            "conservative",
            "--output",
            str(output_path),
        ]
    )

    assert status == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["evaluation_split"] == "held-out"
    assert report["freshness_policy_name"] == "conservative"
    assert report["benchmark_artifact"]["split_record_count"] == 215
    assert report["benchmark_artifact"]["leakage_validation"]["status"] == "passed"
    assert report["threshold_selection"]["dataset_version"] == (
        "reviewed-query-pairs-2.0"
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
    assert "query_a" not in json.dumps(report["failure_gallery"])
    assert "query_a" not in json.dumps(report["baselines"]["embedding-cache"])


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
