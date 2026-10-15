"""Workstream 3 step 8: API, log, and report serialization boundaries."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from sscre.query import QueryResponse
from sscre.serialization import (
    BOUNDARY_SERIALIZATION_VERSION,
    MAX_BOUNDARY_TRACE_JSON_BYTES,
    attach_evaluation_report_schema,
    boundary_candidate_traces,
    build_cache_decision_log,
    dumps_cache_decision_log,
    redact_operational_evaluation_report,
    serialize_safety_result_for_boundary,
)
from sscre.safety import (
    CANDIDATE_TRACE_CONTRACT_VERSION,
    MAX_CANDIDATE_TRACES,
    MAX_TRACE_METADATA_JSON_BYTES,
    SAFETY_EVALUATION_CONTRACT_VERSION,
    CandidateTrace,
    resolve_candidate_traces,
)

try:
    from fastapi.testclient import TestClient
    from sscre.app import create_app
except ImportError:  # pragma: no cover - environment without libpq/psycopg
    create_app = None  # type: ignore[misc, assignment]
    TestClient = None  # type: ignore[misc, assignment]

_TRACE_LOG_KEYS = (
    "cache_control_outcome",
    "candidate_metadata",
    "candidate_order",
    "candidate_query_hash",
    "decision",
    "freshness_class",
    "query_metadata",
    "reason",
    "similarity",
    "stage",
)


def _metrics() -> dict[str, object]:
    return {
        "request_id": "00000000-0000-4000-8000-000000000001",
        "total_latency_ms": 1,
        "cache_hits": 0,
        "cache_misses": 1,
        "generation_failures": 0,
    }


def _trace(
    name: str,
    decision: str,
    *,
    similarity: float = 0.91,
    reason: str = "compatible_metadata",
    order: int = 1,
) -> CandidateTrace:
    return CandidateTrace(
        candidate_query_hash=name,
        similarity=similarity,
        decision=decision,  # type: ignore[arg-type]
        reason=reason,
        candidate_order=order,
    )


def _stable_response(body: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_traces": body.get("candidate_traces"),
        "decision": body["decision"],
        "reason": body.get("reason"),
        "selected_candidate_query_hash": body.get("selected_candidate_query_hash"),
        "similarity": body.get("similarity"),
        "source": body["source"],
        "strategy": body["strategy"],
    }


@pytest.mark.parametrize(
    ("decision", "reason", "source", "strategy", "safe"),
    [
        ("SAFE", "compatible_metadata", "cache", "exact", True),
        ("UNSAFE", "entity_mismatch", "generated", "generated", False),
        ("UNCERTAIN", "candidate_metadata_missing", "generated", "generated", False),
    ],
)
def test_api_candidate_traces_for_each_decision(
    decision: str,
    reason: str,
    source: str,
    strategy: str,
    safe: bool,
) -> None:
    traces = [_trace("cand-1", decision, reason=reason).to_log_dict()]
    payload: dict[str, object] = {
        "answer": "cached-or-generated body",
        "source": source,
        "strategy": strategy,
        "decision": decision,
        "reason": reason,
        "candidate_traces": traces,
        "metrics": _metrics(),
    }
    if safe:
        payload["similarity"] = 1.0
        payload["selected_candidate_query_hash"] = "a" * 64
        payload["metrics"] = {**_metrics(), "cache_hits": 1, "cache_misses": 0}
    response = QueryResponse.model_validate(payload)
    dumped = json.loads(json.dumps(response.model_dump(mode="json")))
    assert dumped["decision"] == decision
    assert dumped["candidate_traces"][0]["reason"] == reason
    assert dumped["candidate_traces"][0]["decision"] == decision
    if safe:
        assert dumped["selected_candidate_query_hash"] == "a" * 64
        assert dumped["similarity"] == 1.0
    else:
        assert dumped["selected_candidate_query_hash"] is None
        assert dumped["similarity"] is None


def test_api_candidate_traces_are_null_when_none_considered() -> None:
    response = QueryResponse.model_validate(
        {
            "answer": "generated",
            "source": "generated",
            "strategy": "generated",
            "decision": "UNSAFE",
            "reason": "no candidates were retrieved",
            "candidate_traces": None,
            "metrics": _metrics(),
        }
    )
    dumped = json.loads(json.dumps(response.model_dump(mode="json")))
    assert dumped["candidate_traces"] is None
    assert boundary_candidate_traces(()) is None


def test_log_serialization_uses_deterministic_key_order() -> None:
    traces = (
        _trace("first", "UNSAFE", reason="entity_mismatch", order=1),
        _trace("second", "UNCERTAIN", reason="missing_intent_evidence", order=2),
    )
    raw = dumps_cache_decision_log(
        {
            "event": "cache_decision",
            "decision": "UNCERTAIN",
            "candidate_traces": traces,
        }
    )
    parsed = json.loads(raw)
    assert list(parsed.keys()) == sorted(parsed.keys())
    assert [key for key in parsed["candidate_traces"][0]] == sorted(
        parsed["candidate_traces"][0]
    )
    assert dumps_cache_decision_log(
        {
            "event": "cache_decision",
            "decision": "UNCERTAIN",
            "candidate_traces": traces,
        }
    ) == raw


def test_report_serialization_includes_contract_and_trace_versions() -> None:
    payload = attach_evaluation_report_schema({"baseline": "compatibility-cache"})
    assert payload["schema_version"] == BOUNDARY_SERIALIZATION_VERSION
    assert payload["safety_contract_version"] == SAFETY_EVALUATION_CONTRACT_VERSION
    assert payload["trace_contract_version"] == CANDIDATE_TRACE_CONTRACT_VERSION
    result = serialize_safety_result_for_boundary(
        resolve_candidate_traces((_trace("c1", "SAFE", similarity=0.99),), strategy="C")
    )
    assert result["schema_version"] == BOUNDARY_SERIALIZATION_VERSION
    assert result["safety_contract_version"] == SAFETY_EVALUATION_CONTRACT_VERSION
    assert result["trace_contract_version"] == CANDIDATE_TRACE_CONTRACT_VERSION


def test_trace_count_and_combined_json_byte_limits() -> None:
    traces = tuple(
        _trace(f"c-{index}", "UNSAFE", reason="entity_mismatch", order=index + 1)
        for index in range(MAX_CANDIDATE_TRACES + 3)
    )
    serialized = boundary_candidate_traces(traces)
    assert serialized is not None
    assert len(serialized) == MAX_CANDIDATE_TRACES
    encoded = json.dumps(serialized, sort_keys=True, separators=(",", ":"))
    assert len(encoded.encode("utf-8")) <= MAX_BOUNDARY_TRACE_JSON_BYTES
    oversized = [
        {"candidate_query_hash": "x" * 100_000, "decision": "UNSAFE"} for _ in range(20)
    ]
    with pytest.raises(ValueError, match="boundary size limit"):
        build_cache_decision_log(
            {"event": "cache_decision", "candidate_traces": oversized}
        )
    too_many = [
        {"candidate_query_hash": f"h-{index}", "decision": "UNSAFE"}
        for index in range(MAX_CANDIDATE_TRACES + 1)
    ]
    with pytest.raises(ValueError, match="trace count limit"):
        build_cache_decision_log(
            {"event": "cache_decision", "candidate_traces": too_many}
        )


def test_per_trace_metadata_bounds() -> None:
    with pytest.raises(ValueError, match="trace metadata exceeds"):
        CandidateTrace(
            "hash-1",
            0.5,
            "UNSAFE",
            "entity_mismatch",
            query_metadata={"note": "x" * (MAX_TRACE_METADATA_JSON_BYTES + 8)},
        )
    with pytest.raises(ValueError, match="trace metadata exceeds"):
        build_cache_decision_log(
            {
                "event": "cache_decision",
                "candidate_traces": [
                    {
                        "candidate_query_hash": "hash-1",
                        "decision": "UNSAFE",
                        "query_metadata": {
                            "note": "y" * (MAX_TRACE_METADATA_JSON_BYTES + 8)
                        },
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    "field",
    [
        "answer",
        "prompt",
        "query",
        "query_text",
        "query_a",
        "token",
        "secret",
        "authorization",
        "Authorization",
        "provider_secret",
        "api_key",
        "normalized_query",
    ],
)
def test_forbidden_fields_rejected_on_logs_and_traces(field: str) -> None:
    with pytest.raises(ValueError, match="must not include"):
        build_cache_decision_log(
            {
                "event": "cache_decision",
                field: "sensitive-value",
                "candidate_traces": None,
            }
        )
    with pytest.raises(ValueError, match="must not include"):
        build_cache_decision_log(
            {
                "event": "cache_decision",
                "candidate_traces": [{field: "sensitive-value", "decision": "UNSAFE"}],
            }
        )


def test_nested_forbidden_query_text_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not include"):
        build_cache_decision_log(
            {
                "event": "cache_decision",
                "decision": "UNSAFE",
                "candidate_traces": [
                    {"query_metadata": {"query_text": "hidden question"}}
                ],
            }
        )


def test_non_safe_boundary_omits_selected_identity_and_similarity() -> None:
    for traces, decision in (
        ((_trace("u1", "UNSAFE", reason="entity_mismatch"),), "UNSAFE"),
        ((_trace("n1", "UNCERTAIN", reason="missing_intent_evidence"),), "UNCERTAIN"),
    ):
        payload = serialize_safety_result_for_boundary(
            resolve_candidate_traces(traces, strategy="C")
        )
        assert payload["decision"] == decision
        assert payload["selected_candidate_query_hash"] is None
        assert payload["similarity"] is None
        response = QueryResponse.model_validate(
            {
                "answer": "generated",
                "source": "generated",
                "strategy": "generated",
                "decision": decision,
                "candidate_traces": payload["candidate_traces"],
                "metrics": _metrics(),
            }
        )
        dumped = response.model_dump(mode="json")
        assert dumped["selected_candidate_query_hash"] is None
        assert dumped["similarity"] is None


def test_failure_gallery_and_nested_report_redaction() -> None:
    payload = redact_operational_evaluation_report(
        {
            "false_positive_examples": [
                {"id": "pair-fp", "query_a": "secret a", "query_b": "secret b"}
            ],
            "failure_examples": [
                {"id": "pair-fail", "query_a": "prompt text", "predicted_decision": "SAFE"}
            ],
            "baselines": {
                "compatibility-cache": {
                    "failure_examples": [
                        {"id": "nested", "query_a": "nested prompt", "query_b": "other"}
                    ]
                }
            },
            "failure_gallery": {
                "strategy_c_failures": [
                    {"id": "gallery", "query_a": "gallery prompt", "query_b": "gallery b"}
                ]
            },
        }
    )
    encoded = json.dumps(payload)
    assert "query_a" not in encoded
    assert "query_b" not in encoded
    assert "secret a" not in encoded
    assert "prompt text" not in encoded
    assert "nested prompt" not in encoded
    assert "gallery prompt" not in encoded
    assert payload["failure_examples"][0]["id"] == "pair-fail"
    assert payload["false_positive_examples"][0]["id"] == "pair-fp"
    assert payload["baselines"]["compatibility-cache"]["failure_examples"][0]["id"] == (
        "nested"
    )
    assert payload["failure_gallery"]["strategy_c_failures"][0]["id"] == "gallery"


def test_public_boundary_round_trip_preserves_decisions_order_and_nulls() -> None:
    traces = (
        _trace("first", "UNSAFE", reason="entity_mismatch", order=1, similarity=0.99),
        _trace("second", "SAFE", reason="compatible_metadata", order=2, similarity=0.98),
    )
    result = resolve_candidate_traces(traces, strategy="C")
    payload = serialize_safety_result_for_boundary(result)
    encoded = json.dumps(payload, sort_keys=True)
    loaded = json.loads(encoded)
    assert json.dumps(loaded, sort_keys=True) == encoded
    assert loaded["decision"] == "SAFE"
    assert loaded["selected_candidate_query_hash"] == "second"
    assert [row["candidate_query_hash"] for row in loaded["candidate_traces"]] == [
        "first",
        "second",
    ]
    assert [row["reason"] for row in loaded["candidate_traces"]] == [
        "entity_mismatch",
        "compatible_metadata",
    ]
    empty = serialize_safety_result_for_boundary(resolve_candidate_traces(()))
    assert empty["candidate_traces"] is None
    assert json.loads(json.dumps(empty, sort_keys=True))["candidate_traces"] is None
    log_line = dumps_cache_decision_log(
        {"event": "cache_decision", "decision": "UNSAFE", "candidate_traces": None}
    )
    assert json.loads(log_line)["candidate_traces"] is None


def test_trace_serialization_does_not_copy_cached_answers() -> None:
    answer = "complete cached answer body that must not leak into traces"
    trace = CandidateTrace(
        "hash-safe",
        0.99,
        "SAFE",
        "compatible_metadata",
        candidate_order=1,
    )
    payload = trace.to_log_dict()
    assert tuple(payload) == _TRACE_LOG_KEYS
    encoded = json.dumps(boundary_candidate_traces((trace,)))
    assert "answer" not in encoded
    assert answer not in encoded
    log_line = dumps_cache_decision_log(
        {
            "event": "cache_decision",
            "decision": "SAFE",
            "candidate_traces": (trace,),
        }
    )
    assert answer not in log_line
    assert "complete cached answer" not in log_line


def test_fake_retrieval_boundary_replay_is_byte_stable() -> None:
    traces = (
        _trace("first", "UNSAFE", reason="constraint_mismatch:language", order=1),
        _trace("second", "SAFE", similarity=0.97, order=2),
    )
    first = json.dumps(
        serialize_safety_result_for_boundary(
            resolve_candidate_traces(traces, strategy="C")
        ),
        sort_keys=True,
        separators=(",", ":"),
    )
    second = json.dumps(
        serialize_safety_result_for_boundary(
            resolve_candidate_traces(traces, strategy="C")
        ),
        sort_keys=True,
        separators=(",", ":"),
    )
    assert first == second


@pytest.mark.skipif(create_app is None, reason="app import unavailable (psycopg/libpq)")
def test_api_http_traces_for_safe_unsafe_uncertain_and_null() -> None:
    from sscre.cache import CacheEntry, InMemoryExactCache
    from sscre.query import QueryRequest, preprocess_query
    from sscre.safety import QueryMetadata

    def _hash(query: str) -> str:
        from sscre.query import trusted_local_scope

        return preprocess_query(
            QueryRequest(query=query),
            trusted_local_scope(),
        ).query_hash

    python_meta = QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", "python"),
        constraints=(("language", "python"),),
        output_format="code",
    )
    ttl = datetime.now(timezone.utc) + timedelta(hours=1)
    safe_query = "Write Python code for binary search"
    unsafe_query = "Write Python code for binary search"
    uncertain_query = "exact query with missing metadata"
    miss_query = "a query with no cached candidate"

    safe_cache = InMemoryExactCache()
    safe_hash = _hash(safe_query)
    cached_answer = "exact compatible answer must not appear in traces"
    safe_cache.insert(
        CacheEntry(
            query_hash=safe_hash,
            normalized_query=safe_query,
            answer=cached_answer,
            metadata=python_meta,
            ttl_expires_at=ttl,
        )
    )
    safe_client = TestClient(
        create_app(
            repository=safe_cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    )
    safe_body = safe_client.post("/v1/query", json={"query": safe_query}).json()
    assert safe_body["decision"] == "SAFE"
    assert safe_body["candidate_traces"][0]["decision"] == "SAFE"
    assert cached_answer not in json.dumps(safe_body["candidate_traces"])
    assert safe_query not in json.dumps(safe_body["candidate_traces"])

    replay = safe_client.post("/v1/query", json={"query": safe_query}).json()
    assert _stable_response(safe_body) == _stable_response(replay)
    assert json.dumps(safe_body["candidate_traces"], sort_keys=True) == json.dumps(
        replay["candidate_traces"], sort_keys=True
    )

    java_cache = InMemoryExactCache()
    java_cache.insert(
        CacheEntry(
            query_hash=_hash(unsafe_query),
            normalized_query=unsafe_query,
            answer="wrong-language answer",
            metadata=QueryMetadata(
                intent="code",
                domain="programming",
                entities=("binary search", "java"),
                constraints=(("language", "java"),),
                output_format="code",
            ),
            ttl_expires_at=ttl,
        )
    )
    unsafe_body = TestClient(
        create_app(
            repository=java_cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    ).post("/v1/query", json={"query": unsafe_query}).json()
    assert unsafe_body["decision"] == "UNSAFE"
    assert unsafe_body["selected_candidate_query_hash"] is None
    assert unsafe_body["similarity"] is None
    assert unsafe_body["candidate_traces"][0]["reason"] == "constraint_mismatch:language"

    uncertain_cache = InMemoryExactCache()
    uncertain_cache.insert(
        CacheEntry(
            query_hash=_hash(uncertain_query),
            normalized_query=uncertain_query,
            answer="legacy answer",
        )
    )
    uncertain_body = TestClient(
        create_app(
            repository=uncertain_cache,
            semantic_strategy="C",
            semantic_enabled=False,
        )
    ).post("/v1/query", json={"query": uncertain_query}).json()
    assert uncertain_body["decision"] == "UNCERTAIN"
    assert uncertain_body["selected_candidate_query_hash"] is None
    assert uncertain_body["similarity"] is None

    miss_body = TestClient(
        create_app(semantic_strategy="C", semantic_enabled=False)
    ).post("/v1/query", json={"query": miss_query}).json()
    assert miss_body["source"] == "generated"
    assert miss_body["candidate_traces"] is None
    assert miss_body["selected_candidate_query_hash"] is None
