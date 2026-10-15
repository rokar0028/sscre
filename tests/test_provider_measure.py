import json
from pathlib import Path

import pytest

from sscre.embedding import EmbeddingResult
from sscre.llm import LLMResult
from sscre.provider_config import RealProviderConfig
from sscre.provider_measure import build_live_measurement, build_unavailable_measurement
from sscre.serialization import validate_redacted_report_payload


ROOT = Path(__file__).resolve().parents[1]


def _provider_config() -> RealProviderConfig:
    return RealProviderConfig(
        provider="test-provider",
        endpoint="https://api.example.test/v1",
        generation_model="generation-test",
        embedding_model="embedding-test",
        embedding_dimension=4,
        request_timeout_seconds=30,
        generation_timeout_seconds=25,
        embedding_timeout_seconds=5,
        retry_limit=0,
        min_backoff_seconds=0,
        max_backoff_seconds=1,
        max_retry_elapsed_seconds=5,
        experiment_id="workstream4-measure",
        dataset_version="reviewed-query-pairs-2.0",
        split="development",
        pricing_schedule_id="prices-2026-10",
        credential="credential-value",
    )


def test_unavailable_measurement_is_redacted_and_explicit() -> None:
    payload = build_unavailable_measurement(
        benchmark_path=ROOT / "benchmarks" / "development.jsonl",
        config_path=ROOT / "experiments" / "evaluation_config.json",
        reason="live_opt_in_missing",
    )
    validate_redacted_report_payload(payload)

    encoded = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "unavailable"
    assert payload["provider_available"] is False
    assert payload["requests"]["count"] == 0
    assert payload["cost_usd"]["source"] == "unavailable"
    assert payload["runtime_versions"]["python"]
    assert any(
        item["category"] == "timeout" and item["count"] == 0
        for item in payload["failures"]
    )
    assert payload["redaction"]["raw_prompts"] is False
    assert payload["redaction"]["raw_answers"] is False
    assert "Write Python" not in encoded
    assert "api_key" not in encoded.lower()
    assert '"authorization": "Bearer' not in encoded


def test_failure_counts_must_not_use_forbidden_category_dict_keys() -> None:
    payload = build_unavailable_measurement(
        benchmark_path=ROOT / "benchmarks" / "development.jsonl",
        config_path=ROOT / "experiments" / "evaluation_config.json",
        reason="live_opt_in_missing",
    )
    regressed = dict(payload)
    regressed["failures"] = {"authorization": 0, "timeout": 0}

    with pytest.raises(ValueError, match="authorization"):
        validate_redacted_report_payload(regressed)


def test_live_measurement_aggregates_without_storing_raw_content() -> None:
    def generate(_query: str) -> LLMResult:
        return LLMResult(
            text="redacted answer text",
            input_tokens=2,
            output_tokens=3,
            latency_ms=10,
            provider_name="test-provider",
            model_name="generation-test",
            usage_source="provider_reported",
        )

    def embed(_text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=(0.1, 0.2, 0.3, 0.4),
            model_name="embedding-test",
            input_tokens=1,
            latency_ms=5,
            provider_name="test-provider",
            usage_source="provider_reported",
        )

    payload = build_live_measurement(
        benchmark_path=ROOT / "benchmarks" / "development.jsonl",
        config_path=ROOT / "experiments" / "evaluation_config.json",
        provider_config=_provider_config(),
        generate=generate,
        embed=embed,
    )
    validate_redacted_report_payload(payload)

    encoded = json.dumps(payload, sort_keys=True)
    assert payload["status"] == "completed"
    assert payload["requests"]["generation"] == payload["benchmark"]["record_count"]
    assert payload["requests"]["embedding"] == payload["benchmark"]["record_count"]
    assert payload["tokens"]["generation_input"] > 0
    assert "redacted answer" not in encoded
    assert "Write Python" not in encoded


def test_live_measurement_honors_max_records() -> None:
    def generate(_query: str) -> LLMResult:
        return LLMResult(
            text="ok",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            provider_name="test-provider",
            model_name="generation-test",
            usage_source="provider_reported",
        )

    def embed(_text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=(0.1, 0.2, 0.3, 0.4),
            model_name="embedding-test",
            input_tokens=1,
            latency_ms=1,
            provider_name="test-provider",
            usage_source="provider_reported",
        )

    payload = build_live_measurement(
        benchmark_path=ROOT / "benchmarks" / "development.jsonl",
        config_path=ROOT / "experiments" / "evaluation_config.json",
        provider_config=_provider_config(),
        generate=generate,
        embed=embed,
        max_records=3,
    )
    assert payload["benchmark"]["record_count"] == 3
    assert payload["benchmark"]["record_count_total"] > 3
    assert payload["requests"]["generation"] == 3


def test_live_measurement_distinguishes_attempted_and_successful_calls() -> None:
    def fail_embed(_text: str) -> EmbeddingResult:
        raise RuntimeError("provider unavailable")

    def fail_generate(_query: str) -> LLMResult:
        raise AssertionError("generation must not run after embedding failure")

    payload = build_live_measurement(
        benchmark_path=ROOT / "benchmarks" / "development.jsonl",
        config_path=ROOT / "experiments" / "evaluation_config.json",
        provider_config=_provider_config(),
        generate=fail_generate,
        embed=fail_embed,
    )

    record_count = payload["benchmark"]["record_count"]
    assert payload["requests"]["count"] == record_count
    assert payload["requests"]["attempted"] == record_count
    assert payload["requests"]["successful"] == 0
    assert payload["requests"]["failed"] == record_count
