"""Workstream 4 accounting and boundary test plan."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.pricing import PricingSchedule, estimate_request_cost
from sscre.provider_compare import build_measurement_comparison
from sscre.provider_config import RealProviderConfig
from sscre.provider_measure import build_unavailable_measurement
from sscre.remote_llm import OpenAICompatibleLLMClient
from sscre.safety import MAX_CANDIDATE_TRACES, CandidateTrace, QueryMetadata
from sscre.serialization import (
    BOUNDARY_SERIALIZATION_VERSION,
    build_cache_decision_log,
    boundary_candidate_traces,
)


class FakeTransport:
    def __init__(self, status: int = 200, response: dict | None = None) -> None:
        self.status = status
        self.response = response or {
            "choices": [{"message": {"content": "A remote answer"}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3},
        }

    def post(self, url, *, headers, payload, timeout_seconds):
        return self.status, self.response


def _remote_config() -> RealProviderConfig:
    return RealProviderConfig(
        provider="test-provider",
        endpoint="https://api.example.test/v1",
        generation_model="generation-test",
        embedding_model="embedding-test",
        embedding_dimension=8,
        request_timeout_seconds=30,
        generation_timeout_seconds=25,
        embedding_timeout_seconds=5,
        retry_limit=0,
        min_backoff_seconds=0,
        max_backoff_seconds=1,
        max_retry_elapsed_seconds=5,
        experiment_id="experiment",
        dataset_version="dataset",
        split="development",
        pricing_schedule_id="prices",
        credential="credential-value",
    )


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_REPORT_KEYS = (
    "authorization",
    "api_key",
    "password",
    "provider_secret",
    "prompt",
    "answer",
)


def _schedule() -> PricingSchedule:
    return PricingSchedule(
        schedule_id="prices-2026-10",
        currency="USD",
        effective_date="2026-10-07",
        source="provider_list_estimate",
        generation_input_per_1k=0.01,
        generation_output_per_1k=0.02,
        embedding_input_per_1k=0.001,
        cache_lookup_per_request=0.0001,
        preprocessing_per_request=0.0002,
    )


def test_provider_reported_and_estimated_usage_sources_remain_distinct() -> None:
    reported = OpenAICompatibleLLMClient(
        _remote_config(),
        transport=FakeTransport(),
    ).generate("one two three")
    estimated = OpenAICompatibleLLMClient(
        _remote_config(),
        transport=FakeTransport(
            response={
                "choices": [{"message": {"content": "four five six seven"}}],
            }
        ),
    ).generate("one two")

    assert reported.usage_source == "provider_reported"
    assert estimated.usage_source == "estimated"
    assert reported.usage_source != estimated.usage_source


def test_unavailable_prices_and_usage_remain_unavailable_not_zero() -> None:
    unavailable = build_unavailable_measurement(
        benchmark_path=ROOT / "benchmarks" / "development.jsonl",
        config_path=ROOT / "experiments" / "evaluation_config.json",
        reason="live_opt_in_missing",
    )
    encoded = json.dumps(unavailable)

    assert unavailable["cost_usd"]["total_estimated"] is None
    assert unavailable["tokens"]["generation_input"] is None
    assert '"total_estimated": 0' not in encoded
    assert '"generation_input": 0' not in encoded


def test_measurement_artifacts_carry_distinct_environment_labels() -> None:
    synthetic = {
        "dataset_version": "dataset-1",
        "evaluation_split": "development",
        "baselines": {
            "compatibility-cache": {
                "request_count": 1,
                "average_latency_ms": 1.0,
                "input_tokens": 1,
                "output_tokens": 1,
                "embedding_tokens": 1,
                "estimated_cost_usd": 0.0,
            }
        },
    }
    real = {
        "status": "unavailable",
        "measurement_environment": "real_provider",
        "benchmark": {"dataset_version": "dataset-1", "split": "development"},
        "requests": {"count": 0},
        "latency_ms": {"generation": None, "embedding": None, "total": None},
        "tokens": {
            "generation_input": None,
            "generation_output": None,
            "embedding_input": None,
        },
        "cost_usd": {"total_estimated": None},
        "limitations": ["provider unavailable"],
    }
    comparison = build_measurement_comparison(
        synthetic,
        real,
        synthetic_artifact="synthetic.json",
        real_artifact="real.json",
    )

    assert comparison["measurement_environment"] == "comparison"
    assert comparison["rows"][0]["synthetic"]["measurement_environment"] == "synthetic"
    assert (
        comparison["rows"][0]["real_provider"]["measurement_environment"]
        == "real_provider"
    )


def test_reports_include_dataset_split_configuration_and_schema_versions() -> None:
    payload = build_unavailable_measurement(
        benchmark_path=ROOT / "benchmarks" / "development.jsonl",
        config_path=ROOT / "experiments" / "evaluation_config.json",
        reason="live_opt_in_missing",
    )

    assert payload["schema_version"] == "real-provider-measurement-1.0"
    assert payload["benchmark"]["dataset_version"] == "reviewed-query-pairs-2.0"
    assert payload["benchmark"]["split"] == "development"
    assert payload["configuration"]["config_version"] == "evaluation-config-1.0"


def test_redacted_provider_configuration_excludes_credential_values() -> None:
    config = RealProviderConfig(
        provider="test-provider",
        endpoint="https://api.example.test/v1",
        generation_model="generation-test",
        embedding_model="embedding-test",
        embedding_dimension=8,
        request_timeout_seconds=30,
        generation_timeout_seconds=25,
        embedding_timeout_seconds=5,
        retry_limit=0,
        min_backoff_seconds=0,
        max_backoff_seconds=1,
        max_retry_elapsed_seconds=5,
        experiment_id="experiment",
        dataset_version="dataset",
        split="development",
        pricing_schedule_id="prices-2026-10",
        credential="super-secret-credential",
    )
    encoded = json.dumps(config.redacted())

    assert config.redacted()["credential_configured"] is True
    assert "super-secret-credential" not in encoded
    for forbidden in FORBIDDEN_REPORT_KEYS:
        assert forbidden not in encoded.lower()


@pytest.mark.parametrize("decision", ["SAFE", "UNSAFE", "UNCERTAIN"])
def test_boundary_serialization_preserves_canonical_decisions(decision: str) -> None:
    payload = build_cache_decision_log(
        {
            "event": "cache_decision",
            "decision": decision,
            "candidate_traces": None,
        }
    )
    assert payload["decision"] == decision
    assert payload["schema_version"] == BOUNDARY_SERIALIZATION_VERSION


def test_trace_count_limit_is_enforced_at_boundary() -> None:
    traces = [
        {
            "candidate_query_hash": f"hash-{index}",
            "similarity": 0.5,
            "decision": "UNSAFE",
            "reason": "similarity_below_threshold",
        }
        for index in range(MAX_CANDIDATE_TRACES + 1)
    ]
    with pytest.raises(ValueError, match="trace count limit"):
        build_cache_decision_log(
            {"event": "cache_decision", "decision": "UNSAFE", "candidate_traces": traces}
        )


def test_trace_metadata_size_limit_is_enforced_at_boundary() -> None:
    oversized_metadata = {"detail": "x" * (8 * 1024 + 1)}
    traces = [
        {
            "candidate_query_hash": "hash-1",
            "similarity": 0.5,
            "decision": "UNSAFE",
            "reason": "similarity_below_threshold",
            "query_metadata": oversized_metadata,
        }
    ]
    with pytest.raises(ValueError, match="metadata exceeds"):
        build_cache_decision_log(
            {"event": "cache_decision", "decision": "UNSAFE", "candidate_traces": traces}
        )


def test_boundary_candidate_traces_remain_bounded_without_sensitive_fields() -> None:
    traces = tuple(
        CandidateTrace(
            f"candidate-{index}",
            0.9,
            "UNSAFE",
            "similarity_below_threshold",
            candidate_order=index + 1,
            query_metadata=QueryMetadata(intent="code").to_dict(),
        )
        for index in range(3)
    )
    serialized = boundary_candidate_traces(traces)
    encoded = json.dumps(serialized)
    assert serialized is not None
    assert "answer" not in encoded
    assert "authorization" not in encoded


def test_exact_hit_response_metrics_exclude_provider_cost_components() -> None:
    query = "Write Python code for binary search"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="cached answer",
            metadata=QueryMetadata(
                intent="code",
                domain="programming",
                entities=("binary search", "python"),
                constraints=(("language", "python"),),
                output_format="code",
            ),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )
    metrics = client.post("/v1/query", json={"query": query}).json()["metrics"]

    assert metrics["llm_attempts"] == 0
    assert metrics["embedding_attempts"] == 0
    assert metrics["total_estimated_cost_usd"] is None
    assert metrics["generation_cost_usd"] is None


def test_semantic_hit_response_metrics_include_embedding_not_generation_cost() -> None:
    cached_query = "explain vector search"
    cache = InMemoryExactCache(embedding_dimension=2)
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="semantic cached answer",
            embedding=(1.0, 0.0),
            embedding_model="fake-embedding",
            embedding_dimension=2,
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="fake-embedding", dimension=2),
                vectors={"new wording for vector search": (1.0, 0.0)},
            ),
            semantic_strategy="B",
            semantic_similarity_threshold=0.9,
            pricing_schedule=_schedule(),
        )
    )
    metrics = client.post(
        "/v1/query",
        json={"query": "new wording for vector search"},
    ).json()["metrics"]

    assert metrics["embedding_attempts"] == 1
    assert metrics["llm_attempts"] == 0
    assert metrics["total_estimated_cost_usd"] is None
    assert metrics["embedding_input_tokens"] > 0


def test_miss_response_metrics_include_generation_cost_when_schedule_is_configured() -> None:
    client = TestClient(
        create_app(
            semantic_enabled=False,
            pricing_schedule=_schedule(),
        )
    )
    metrics = client.post("/v1/query", json={"query": "fresh accounting query"}).json()[
        "metrics"
    ]

    assert metrics["llm_attempts"] == 1
    assert metrics["generation_cost_usd"] is not None
    assert metrics["total_estimated_cost_usd"] is not None
    assert metrics["pricing_schedule_id"] == "prices-2026-10"
    assert metrics["cost_source"] == "provider_list_estimate"


def test_retry_billing_rule_marks_total_unavailable_when_retries_occurred() -> None:
    result = estimate_request_cost(
        _schedule(),
        generation_input_tokens=100,
        generation_output_tokens=50,
        generation_retry_count=1,
    )

    assert result.retry_cost_usd is None
    assert result.total_estimated_cost_usd is None
    assert result.generation_cost_usd is not None
