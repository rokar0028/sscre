import json
from uuid import UUID

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.llm import MockLLMClient


def test_response_contains_request_metrics_and_cumulative_counters() -> None:
    client = TestClient(create_app())

    generated = client.post("/v1/query", json={"query": "Explain metrics"})
    cached = client.post("/v1/query", json={"query": "Explain metrics"})

    generated_metrics = generated.json()["metrics"]
    cached_metrics = cached.json()["metrics"]
    UUID(generated_metrics["request_id"])
    UUID(cached_metrics["request_id"])
    assert generated_metrics["total_latency_ms"] >= 0
    assert generated_metrics["llm_input_tokens"] > 0
    assert generated_metrics["llm_output_tokens"] > 0
    assert generated_metrics["cache_hits"] == 0
    assert generated_metrics["cache_misses"] == 1
    assert cached_metrics["cache_hits"] == 1
    assert cached_metrics["cache_misses"] == 1


def test_decision_log_is_structured_and_does_not_include_answer(
    caplog,
) -> None:
    caplog.set_level("INFO", logger="sscre")
    client = TestClient(create_app())

    response = client.post("/v1/query", json={"query": "Explain logs"})

    assert response.status_code == 200
    log = json.loads(next(record.message for record in caplog.records))
    assert log["event"] == "cache_decision"
    assert log["decision"] == "GENERATED"
    assert log["request_id"] == response.json()["metrics"]["request_id"]
    assert "answer" not in log


def test_invalid_query_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/query", json={"query": "   "})

    assert response.status_code == 422


def test_generation_failure_returns_502_and_is_not_cached() -> None:
    model = MockLLMClient(should_fail=True)
    client = TestClient(create_app(model))

    failed = client.post("/v1/query", json={"query": "Will this fail?"})
    model.should_fail = False
    retry = client.post("/v1/query", json={"query": "Will this fail?"})

    assert failed.status_code == 502
    assert retry.status_code == 200
    assert retry.json()["source"] == "generated"
    assert retry.json()["metrics"]["generation_failures"] == 1
