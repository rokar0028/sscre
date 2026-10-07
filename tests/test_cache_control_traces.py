from datetime import datetime, timedelta, timezone

from sscre.cache import CacheCandidate
from sscre.cache_control_traces import build_cache_control_trace
from sscre.cache_controls import CacheControlResult, evaluate_cache_control
from sscre.safety import QueryMetadata, validate_trace_reason


def _candidate(*, ttl: datetime | None, temporal: str = "stable") -> CacheCandidate:
    return CacheCandidate(
        query_hash="abc",
        normalized_query="q",
        answer="a",
        similarity=0.99,
        embedding_model="m",
        embedding_dimension=2,
        metadata=QueryMetadata(temporal_class=temporal),  # type: ignore[arg-type]
        ttl_expires_at=ttl,
    )


def test_expired_control_trace_is_unsafe_retrieval() -> None:
    control = CacheControlResult(False, "expired")
    trace = build_cache_control_trace(
        _candidate(ttl=datetime.now(timezone.utc) - timedelta(seconds=1)),
        control,
        candidate_order=1,
        query_metadata={},
    )
    assert trace.stage == "retrieval"
    assert trace.decision == "UNSAFE"
    assert trace.reason == "cache_control_expired"
    assert trace.cache_control_outcome == "expired"
    validate_trace_reason(trace.reason)


def test_missing_expiration_trace_is_uncertain() -> None:
    control = CacheControlResult(False, "missing_expiration")
    trace = build_cache_control_trace(
        _candidate(ttl=None),
        control,
        candidate_order=2,
        query_metadata={"intent": "code"},
    )
    assert trace.decision == "UNCERTAIN"
    assert trace.reason == "cache_control_missing_expiration"
    assert trace.freshness_class == "stable"


def test_semi_dynamic_fresh_control_is_reusable() -> None:
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    control = evaluate_cache_control("semi_dynamic", expires)
    assert control.reusable
    assert control.reason == "fresh"
