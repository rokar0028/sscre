"""Workstream 1 contract and regression tests (step 6).

Targeted suite:

    python -m pytest -q tests/test_safety.py tests/test_compatibility.py \\
        tests/test_trace_contract.py tests/test_serialization_boundary.py \\
        tests/test_workstream1_contract.py tests/test_evaluation_labels.py
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from sscre.app import create_app
from sscre.query import QueryResponse
from sscre.serialization import BOUNDARY_SERIALIZATION_VERSION


def _response_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "answer": "ok",
        "source": "generated",
        "strategy": "generated",
        "decision": "UNCERTAIN",
        "metrics": {
            "request_id": "00000000-0000-4000-8000-000000000001",
            "total_latency_ms": 1,
            "cache_hits": 0,
            "cache_misses": 1,
            "generation_failures": 0,
        },
    }
    payload.update(overrides)
    return payload


def test_query_response_accepts_canonical_decisions() -> None:
    safe = QueryResponse.model_validate(
        _response_payload(
            source="cache",
            strategy="exact",
            decision="SAFE",
            similarity=1.0,
            selected_candidate_query_hash="a" * 64,
        )
    )
    assert safe.decision == "SAFE"
    for decision in ("UNSAFE", "UNCERTAIN"):
        response = QueryResponse.model_validate(_response_payload(decision=decision))
        assert response.decision == decision


def test_query_response_rejects_safe_without_selection() -> None:
    with pytest.raises(ValidationError):
        QueryResponse.model_validate(_response_payload(decision="SAFE"))


def test_query_response_rejects_similarity_on_non_safe_decision() -> None:
    with pytest.raises(ValidationError):
        QueryResponse.model_validate(
            _response_payload(decision="UNSAFE", similarity=0.9)
        )


def test_query_response_rejects_invalid_decision() -> None:
    with pytest.raises(ValidationError):
        QueryResponse.model_validate(
            {
                "answer": "ok",
                "source": "generated",
                "strategy": "generated",
                "decision": "EXACT_HIT",
                "metrics": {
                    "request_id": "00000000-0000-4000-8000-000000000001",
                    "total_latency_ms": 1,
                    "cache_hits": 0,
                    "cache_misses": 1,
                    "generation_failures": 0,
                },
            }
        )


def test_query_cache_decision_log_includes_schema_version(caplog) -> None:
    caplog.set_level(logging.INFO, logger="sscre")
    client = TestClient(create_app())
    client.post("/v1/query", json={"query": "schema version log check"})

    event = json.loads(
        next(record.message for record in caplog.records if "cache_decision" in record.message)
    )
    assert event["schema_version"] == BOUNDARY_SERIALIZATION_VERSION
    assert "answer" not in event


def test_safe_exact_hit_trace_is_bounded_without_secrets(caplog) -> None:
    caplog.set_level(logging.INFO, logger="sscre")
    client = TestClient(create_app())
    query = "Write Python code for binary search sk-test-SECRETVALUE"
    first = client.post("/v1/query", json={"query": query})
    second = client.post("/v1/query", json={"query": query})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["source"] == "cache"
    assert second.json()["decision"] == "SAFE"
    answer = second.json()["answer"]
    traces = second.json()["candidate_traces"]
    assert traces is not None
    encoded = json.dumps(traces)
    assert "authorization" not in encoded.casefold()
    assert "sk-test-SECRETVALUE" not in encoded
    assert query not in encoded
    assert answer not in encoded

    event = json.loads(
        next(
            record.message
            for record in caplog.records
            if "cache_decision" in record.message and "cache_reused" in record.message
        )
    )
    event_text = json.dumps(event)
    assert event["candidate_traces"] is not None
    assert "sk-test-SECRETVALUE" not in event_text
    assert answer not in event_text
