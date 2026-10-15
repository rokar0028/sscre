"""Workstream 3 step 4: ordering, aggregation, caps, and boundary stability."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient
from sscre.query import QueryResponse
from sscre.serialization import (
    boundary_candidate_traces,
    build_cache_decision_log,
    dumps_cache_decision_log,
    serialize_safety_result_for_boundary,
)
from sscre.safety import (
    MAX_CANDIDATE_TRACES,
    CandidateTrace,
    SafetyResult,
    cap_candidate_traces,
    resolve_candidate_traces,
    serialize_candidate_traces,
)

try:
    from fastapi.testclient import TestClient
    from sscre.app import create_app
except ImportError:  # pragma: no cover - environment without libpq/psycopg
    create_app = None  # type: ignore[misc, assignment]
    TestClient = None  # type: ignore[misc, assignment]

from sscre.safety import QueryMetadata


def _trace(
    name: str,
    decision: str,
    *,
    similarity: float,
    reason: str = "compatible_metadata",
    order: int = 0,
) -> CandidateTrace:
    return CandidateTrace(
        candidate_query_hash=name,
        similarity=similarity,
        decision=decision,  # type: ignore[arg-type]
        reason=reason,
        candidate_order=order or 1,
    )


@pytest.mark.parametrize(
    ("traces", "expected_decision", "selected", "expected_reason"),
    [
        ((), "UNSAFE", None, "no candidates were retrieved"),
        (
            (_trace("only-safe", "SAFE", similarity=0.99),),
            "SAFE",
            "only-safe",
            "compatible_metadata",
        ),
        (
            (_trace("only-unsafe", "UNSAFE", similarity=0.99, reason="entity_mismatch"),),
            "UNSAFE",
            None,
            "all candidates were incompatible",
        ),
        (
            (
                _trace(
                    "only-uncertain",
                    "UNCERTAIN",
                    similarity=0.99,
                    reason="missing_intent_evidence",
                ),
            ),
            "UNCERTAIN",
            None,
            "no candidate had sufficient compatibility evidence",
        ),
    ],
    ids=["empty", "single-safe", "single-unsafe", "single-uncertain"],
)
def test_resolve_aggregate_matrix(
    traces: tuple[CandidateTrace, ...],
    expected_decision: str,
    selected: str | None,
    expected_reason: str,
) -> None:
    result = resolve_candidate_traces(traces, strategy="C")
    assert result.decision == expected_decision
    assert result.reason == expected_reason
    assert result.selected_candidate_query_hash == selected
    if expected_decision == "SAFE":
        assert result.similarity is not None
    else:
        assert result.selected_candidate_query_hash is None
        assert result.similarity is None


def test_unsafe_then_safe_selects_safe_candidate() -> None:
    traces = (
        _trace("unsafe-first", "UNSAFE", similarity=0.99, reason="intent_mismatch"),
        _trace("safe-second", "SAFE", similarity=0.97),
    )
    result = resolve_candidate_traces(traces)
    assert result.decision == "SAFE"
    assert result.selected_candidate_query_hash == "safe-second"
    assert result.similarity == 0.97


def test_safe_then_safe_keeps_first_safe_candidate() -> None:
    traces = (
        _trace("safe-first", "SAFE", similarity=0.99),
        _trace("safe-second", "SAFE", similarity=0.98),
    )
    result = resolve_candidate_traces(traces)
    assert result.selected_candidate_query_hash == "safe-first"
    assert result.similarity == 0.99


def test_unsafe_then_uncertain_aggregate_is_uncertain() -> None:
    traces = (
        _trace("unsafe", "UNSAFE", similarity=0.99, reason="entity_mismatch"),
        _trace(
            "uncertain",
            "UNCERTAIN",
            similarity=0.98,
            reason="missing_domain_evidence",
        ),
    )
    result = resolve_candidate_traces(traces)
    assert result.decision == "UNCERTAIN"


def test_multiple_unsafe_candidates_aggregate_unsafe() -> None:
    traces = (
        _trace("u1", "UNSAFE", similarity=0.99, reason="entity_mismatch"),
        _trace("u2", "UNSAFE", similarity=0.98, reason="intent_mismatch"),
        _trace("u3", "UNSAFE", similarity=0.97, reason="format_mismatch"),
    )
    result = resolve_candidate_traces(traces)
    assert result.decision == "UNSAFE"
    assert result.reason == "all candidates were incompatible"
    assert len(result.candidate_traces) == 3


def test_cap_preserves_retrieval_order_without_reordering() -> None:
    traces = tuple(
        _trace(f"c-{index}", "UNSAFE", similarity=1.0 - index * 0.01, reason="entity_mismatch")
        for index in range(MAX_CANDIDATE_TRACES + 3)
    )
    capped = cap_candidate_traces(traces, limit=MAX_CANDIDATE_TRACES)
    assert len(capped) == MAX_CANDIDATE_TRACES
    assert [trace.candidate_query_hash for trace in capped] == [
        f"c-{index}" for index in range(MAX_CANDIDATE_TRACES)
    ]


def test_resolve_retained_traces_are_capped_in_order() -> None:
    traces = tuple(
        _trace(f"c-{index}", "UNSAFE", similarity=1.0 - index * 0.01, reason="entity_mismatch")
        for index in range(MAX_CANDIDATE_TRACES + 2)
    )
    result = resolve_candidate_traces(traces)
    assert len(result.candidate_traces) == MAX_CANDIDATE_TRACES
    assert result.candidate_traces[0].candidate_query_hash == "c-0"


def test_safe_beyond_evaluation_window_not_selected_when_slice_matches_app() -> None:
    """``app.py`` evaluates only ``candidates[:MAX_CANDIDATE_TRACES]``."""
    beyond = MAX_CANDIDATE_TRACES
    traces = tuple(
        _trace(
            f"c-{index}",
            "UNSAFE",
            similarity=1.0 - index * 0.001,
            reason="entity_mismatch",
        )
        for index in range(beyond)
    ) + (_trace("hidden-safe", "SAFE", similarity=0.5),)
    app_window = traces[:MAX_CANDIDATE_TRACES]
    assert resolve_candidate_traces(app_window).decision == "UNSAFE"
    assert resolve_candidate_traces(traces).selected_candidate_query_hash == "hidden-safe"


def test_boundary_trace_json_is_byte_stable() -> None:
    metadata = QueryMetadata(intent="code").to_dict()
    traces = tuple(
        CandidateTrace(
            f"candidate-{index}",
            1.0 - index * 0.01,
            "UNSAFE",
            "similarity_below_threshold",
            candidate_order=index + 1,
            query_metadata=metadata,
        )
        for index in range(3)
    )
    serialized = boundary_candidate_traces(traces)
    assert serialized is not None
    first = json.dumps(serialized, sort_keys=True)
    second = json.dumps(boundary_candidate_traces(traces), sort_keys=True)
    assert first == second
    assert [trace["candidate_order"] for trace in serialized] == [1, 2, 3]


def test_cache_decision_log_preserves_trace_order() -> None:
    traces = (
        _trace("first", "UNSAFE", similarity=0.99, reason="entity_mismatch"),
        _trace("second", "UNCERTAIN", similarity=0.98, reason="missing_intent_evidence"),
    )
    payload = build_cache_decision_log(
        {
            "event": "cache_decision",
            "decision": "UNCERTAIN",
            "candidate_traces": traces,
        }
    )
    assert payload["candidate_traces"][0]["candidate_query_hash"] == "first"
    assert payload["candidate_traces"][1]["candidate_query_hash"] == "second"
    log_line = dumps_cache_decision_log(
        {"event": "cache_decision", "decision": "UNSAFE", "candidate_traces": traces}
    )
    assert json.loads(log_line)["candidate_traces"][1]["decision"] == "UNCERTAIN"


def test_serialize_safety_result_for_boundary_non_safe_has_no_selection() -> None:
    result = resolve_candidate_traces(
        (_trace("u1", "UNSAFE", similarity=0.9, reason="entity_mismatch"),),
        strategy="C",
    )
    payload = serialize_safety_result_for_boundary(result)
    assert payload["selected_candidate_query_hash"] is None
    assert payload["similarity"] is None


def test_query_response_rejects_selection_fields_on_non_safe() -> None:
    with pytest.raises(Exception):
        QueryResponse.model_validate(
            {
                "answer": "generated",
                "source": "generated",
                "strategy": "generated",
                "decision": "UNSAFE",
                "similarity": 0.9,
                "selected_candidate_query_hash": "abc",
                "metrics": {
                    "request_id": "00000000-0000-4000-8000-000000000001",
                    "total_latency_ms": 1,
                    "cache_hits": 0,
                    "cache_misses": 1,
                    "generation_failures": 0,
                },
            }
        )


def test_safety_result_constructor_enforces_safe_only_selection() -> None:
    with pytest.raises(ValueError, match="non-SAFE"):
        SafetyResult(
            decision="UNSAFE",
            strategy="C",
            reason="all candidates were incompatible",
            selected_candidate_query_hash="forbidden",
        )


@pytest.mark.skipif(create_app is None, reason="app import unavailable (psycopg/libpq)")
def test_strategy_c_api_selects_first_safe_in_retrieval_order() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    java_query = "write Java code for binary search"
    python_query = "write Python code for binary search"
    ttl = datetime.now(timezone.utc) + timedelta(hours=1)
    meta = lambda lang: QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", lang),
        constraints=(("language", lang),),
        output_format="code",
    )
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(java_query.encode()).hexdigest(),
            normalized_query=java_query,
            answer="java answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=meta("java"),
            ttl_expires_at=ttl,
        )
    )
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(python_query.encode()).hexdigest(),
            normalized_query=python_query,
            answer="python answer",
            embedding=(0.99, 0.01),
            embedding_model="test-embedding",
            embedding_dimension=2,
            metadata=meta("python"),
            ttl_expires_at=ttl,
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"implement Python binary search": (1.0, 0.0)},
            ),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
            semantic_top_k=2,
        )
    )
    response = client.post(
        "/v1/query",
        json={"query": "implement Python binary search"},
    )
    body = response.json()
    assert body["source"] == "cache"
    assert body["decision"] == "SAFE"
    assert body["answer"] == "python answer"
    traces = body["candidate_traces"]
    assert traces[0]["decision"] == "UNSAFE"
    assert traces[0]["reason"] == "constraint_mismatch:language"
    assert traces[1]["decision"] == "SAFE"
    from sscre.query import storage_query_hash

    assert body["selected_candidate_query_hash"] == storage_query_hash(
        python_query
    )
