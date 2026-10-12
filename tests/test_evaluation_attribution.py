import pytest

from sscre.baseline import run_embedding_cache_baseline, run_exact_cache_baseline
from sscre.benchmark import BenchmarkRecord
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.evaluation_attribution import (
    labeled_false_positive_rate_details,
    DirectedPairReuseIndex,
    attribute_served_reuse_outcome,
)
from tests.test_benchmark import valid_record


def test_directed_pair_index_flags_ambiguous_edges() -> None:
    shared = {
        **valid_record("pair-a"),
        "query_a": "shared source",
        "query_b": "shared target",
        "reusable": True,
        "compatibility_label": "compatible",
        "reason": None,
    }
    other = {
        **valid_record("pair-b"),
        "query_a": "shared source",
        "query_b": "shared target",
        "reusable": False,
        "compatibility_label": "incompatible",
    }
    index = DirectedPairReuseIndex.from_records(
        [
            BenchmarkRecord.model_validate(shared),
            BenchmarkRecord.model_validate(other),
        ]
    )
    from sscre.query import hash_query, normalize_query

    candidate_hash = hash_query(normalize_query("shared source"))
    current_hash = hash_query(normalize_query("shared target"))
    assert index.lookup(candidate_hash, current_hash) is None


def test_attribute_scores_reviewed_edge_not_request_record() -> None:
    record = BenchmarkRecord.model_validate(
        {
            **valid_record("pair-eval"),
            "query_a": "alpha",
            "query_b": "beta",
            "reusable": True,
            "compatibility_label": "compatible",
            "reason": None,
        }
    )
    grounding = BenchmarkRecord.model_validate(
        {
            **valid_record("pair-ground"),
            "query_a": "gamma",
            "query_b": "delta",
            "reusable": False,
            "compatibility_label": "incompatible",
        }
    )
    index = DirectedPairReuseIndex.from_records([record, grounding])
    outcome = attribute_served_reuse_outcome(
        direction="b_to_a",
        served_reuse=True,
        candidate_normalized_query="gamma",
        candidate_answer_hash="answer-g",
        current_normalized_query="delta",
        pair_index=index,
        source_pair_id="pair-eval",
        source_direction="b_to_a",
    )
    assert outcome.false_positive == 1
    assert outcome.safe_reuse_hit == 0
    assert outcome.unlabeled_candidate_reuse == 0
    assert outcome.provenance is not None
    assert outcome.provenance.source_pair_id == "pair-eval"


def test_attribute_marks_unlabeled_cross_pair_without_reviewed_edge() -> None:
    record = BenchmarkRecord.model_validate(
        {
            **valid_record("pair-1"),
            "query_a": "alpha",
            "query_b": "beta",
            "reusable": False,
        }
    )
    index = DirectedPairReuseIndex.from_records([record])
    outcome = attribute_served_reuse_outcome(
        direction="b_to_a",
        served_reuse=True,
        candidate_normalized_query="alpha",
        candidate_answer_hash="answer-a",
        current_normalized_query="beta",
        pair_index=index,
    )
    assert outcome.false_positive == 1
    assert outcome.safe_reuse_hit == 0
    assert outcome.unlabeled_candidate_reuse == 0

    outcome_cross = attribute_served_reuse_outcome(
        direction="b_to_a",
        served_reuse=True,
        candidate_normalized_query="alpha",
        candidate_answer_hash="answer-a",
        current_normalized_query="unrelated target",
        pair_index=index,
    )
    assert outcome_cross.unlabeled_candidate_reuse == 1


def test_a_to_b_direction_never_scores_reuse_outcomes() -> None:
    record = BenchmarkRecord.model_validate(
        {
            **valid_record("pair-1"),
            "query_a": "alpha",
            "query_b": "beta",
            "reusable": True,
            "compatibility_label": "compatible",
            "reason": None,
        }
    )
    index = DirectedPairReuseIndex.from_records([record])
    outcome = attribute_served_reuse_outcome(
        direction="a_to_b",
        served_reuse=True,
        candidate_normalized_query="alpha",
        candidate_answer_hash="answer-a",
        current_normalized_query="alpha",
        pair_index=index,
    )
    assert outcome == (
        attribute_served_reuse_outcome(
            direction="a_to_b",
            served_reuse=True,
            candidate_normalized_query="alpha",
            candidate_answer_hash="answer-a",
            current_normalized_query="alpha",
            pair_index=index,
        )
    )
    assert outcome.false_positive == 0
    assert outcome.safe_reuse_hit == 0
    assert outcome.unlabeled_candidate_reuse == 0


def test_exact_cache_reports_false_positive_rate_on_labeled_reuse() -> None:
    records = [
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-safe"),
                "query_a": "reuse me",
                "query_b": "reuse me",
                "reusable": True,
                "compatibility_label": "compatible",
                "reason": None,
            }
        ),
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-unsafe"),
                "query_a": "safe source text",
                "query_b": "unsafe target text",
                "reusable": False,
                "compatibility_label": "incompatible",
            }
        ),
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-bridge"),
                "query_a": "unsafe target text",
                "query_b": "unsafe target text",
                "reusable": False,
                "compatibility_label": "incompatible",
            }
        ),
    ]
    report = run_exact_cache_baseline(records, dataset_version="test-v1")
    assert report.unsafe_reuse_hits >= 1
    assert report.false_positive_rate > 0.0
    labeled_samples = [
        sample
        for sample in report.request_samples
        if sample["direction"] == "b_to_a" and sample["cache_hit"] == 1
    ]
    assert any(sample["served_candidate_provenance"] for sample in labeled_samples)


def test_embedding_false_positive_follows_served_candidate_not_request_label() -> None:
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
                "compatibility_label": "incompatible",
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
    assert report.safe_reuse_hits == 1
    assert report.unsafe_reuse_hits == 1
    assert report.unlabeled_candidate_reuse_hits == 0
    assert report.false_positive_rate == pytest.approx(0.5)


def test_context_stripped_identical_text_uses_reviewed_non_reusable_edge() -> None:
    records = [
        BenchmarkRecord.model_validate(
            {
                **valid_record("pair-ctx"),
                "query_a": "Explain caching",
                "query_b": "  Explain   caching ",
                "reusable": False,
                "compatibility_label": "incompatible",
            }
        ),
    ]
    report = run_exact_cache_baseline(records, dataset_version="test-v1")
    b_to_a_hits = [
        sample
        for sample in report.request_samples
        if sample["direction"] == "b_to_a" and sample["cache_hit"] == 1
    ]
    assert len(b_to_a_hits) == 1
    assert b_to_a_hits[0]["false_positive"] == 1
    assert b_to_a_hits[0]["safe_reuse_hit"] == 0


def test_labeled_false_positive_rate_unavailable_when_no_labeled_reuse() -> None:
    details = labeled_false_positive_rate_details(0, 0)
    assert details.value is None
    assert details.unavailable_reason == "no_labeled_reuse_hits"
    assert details.labeled_reuse_hits == 0


def test_labeled_false_positive_rate_fail_closed_for_constraints() -> None:
    import math

    from sscre.evaluation_attribution import (
        false_positive_rate_for_constraint,
        labeled_false_positive_rate,
    )

    assert labeled_false_positive_rate(0, 0) == math.inf
    assert false_positive_rate_for_constraint(0, 0, None) == math.inf
    assert labeled_false_positive_rate(1, 9) == 0.1
