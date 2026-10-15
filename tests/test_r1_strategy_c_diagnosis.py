"""Research track R1 Step 1.1 — Strategy C diagnosis aggregation."""

from pathlib import Path

from sscre.strategy_c_diagnosis import (
    aggregate_strategy_c_diagnosis,
    build_diagnosis_record,
    extract_compatibility_report,
    similarity_band,
)


def test_similarity_bands() -> None:
    assert similarity_band(1.0) == "1.0"
    assert similarity_band(0.97) == "[0.95,1.0)"
    assert similarity_band(0.5) == "[-1,0.8)"


def test_aggregate_strategy_c_diagnosis_counts_traces() -> None:
    report = {
        "cache_hits": 1,
        "cache_misses": 2,
        "request_count": 3,
        "decision_counts": {"SAFE": 1, "UNCERTAIN": 2},
        "failure_categories": {
            "no candidate had sufficient compatibility evidence": 2,
            "semantic_miss": 1,
        },
        "unlabeled_candidate_reuse_hits": 0,
        "observed_pair_records": [
            {
                "observed_decision": "SAFE",
                "candidate_traces": [
                    {
                        "decision": "SAFE",
                        "reason": "compatible_metadata",
                        "stage": "compatibility",
                        "similarity": 0.99,
                        "freshness_class": "stable",
                        "cache_control_outcome": "fresh",
                    }
                ],
            },
            {
                "observed_decision": "UNCERTAIN",
                "candidate_traces": [
                    {
                        "decision": "UNCERTAIN",
                        "reason": "missing_domain_evidence",
                        "stage": "compatibility",
                        "similarity": 1.0,
                        "freshness_class": "stable",
                        "cache_control_outcome": "fresh",
                    }
                ],
            },
            {
                "observed_decision": "UNCERTAIN",
                "candidate_traces": [],
            },
        ],
    }
    aggregates = aggregate_strategy_c_diagnosis(report)
    assert aggregates["trace_decision_counts"] == {"SAFE": 1, "UNCERTAIN": 1}
    assert aggregates["trace_reason_category_counts"]["compatible"] == 1
    assert aggregates["trace_reason_category_counts"]["missing_metadata_evidence"] == 1
    assert aggregates["candidate_availability"]["requests_without_candidates"] == 1
    assert aggregates["candidate_rejection"]["served_safe"] == 1
    assert aggregates["candidate_rejection"]["rejected_with_candidates"] == 1


def test_extract_compatibility_report_from_comparison() -> None:
    payload = {
        "baseline": "comparison",
        "baselines": {
            "compatibility-cache": {"baseline": "compatibility-cache", "hit_rate": 0.01},
        },
    }
    section = extract_compatibility_report(payload)
    assert section["baseline"] == "compatibility-cache"


def test_build_diagnosis_record_marks_non_headline() -> None:
    record = build_diagnosis_record(
        compatibility_report={"embedding_model": "fixture", "embedding_dimension": 8},
        source_evaluation_path=None,
        config_path=Path(__file__),
        config={"config_version": "test-config", "protocol_id": "TEST"},
        benchmark_path=Path(__file__),
        population_record_count=10,
        threshold_policy=0.95,
        embedding_provenance=None,
        exact_cache_summary=None,
    )
    assert record["headline_population"] is False
    assert record["population_purpose"].endswith("not_fresh_headline")
