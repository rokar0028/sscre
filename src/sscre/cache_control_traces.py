"""Freshness-gate candidate traces (pre-compatibility ``retrieval`` stage).

Cache-control outcomes are recorded on ``CandidateTrace.cache_control_outcome``.
Trace ``reason`` values are taxonomy-aligned; see Workstream 3 freshness policy
in ``docs/phase-2/WORKSTREAM_3_FRESHNESS_TRACE_POLICY.md``.
"""

from sscre.cache import CacheCandidate
from sscre.cache_controls import CacheControlReason, CacheControlResult
from sscre.safety import CandidateTrace, QueryMetadata, SafetyDecision, TemporalClass

_FRESHNESS_GATE: dict[CacheControlReason, tuple[SafetyDecision, str]] = {
    "expired": ("UNSAFE", "cache_control_expired"),
    "dynamic_entries_disabled": ("UNSAFE", "cache_control_dynamic_disabled"),
    "missing_expiration": ("UNCERTAIN", "cache_control_missing_expiration"),
    "invalid_expiration": ("UNCERTAIN", "cache_control_invalid_expiration"),
}


def build_cache_control_trace(
    candidate: CacheCandidate,
    control: CacheControlResult,
    *,
    candidate_order: int,
    query_metadata: dict[str, object],
) -> CandidateTrace:
    """Build a bounded trace for a candidate blocked by cache-control policy."""
    if control.reusable:
        raise ValueError("reusable entries must use compatibility evaluation")
    decision, reason = _FRESHNESS_GATE[control.reason]
    temporal_class: TemporalClass = (
        candidate.metadata.temporal_class
        if candidate.metadata is not None
        else "stable"
    )
    return CandidateTrace(
        candidate_query_hash=candidate.query_hash,
        similarity=candidate.similarity,
        decision=decision,
        reason=reason,
        candidate_order=candidate_order,
        stage="retrieval",
        query_metadata=query_metadata,
        candidate_metadata=(
            candidate.metadata.to_dict() if candidate.metadata is not None else {}
        ),
        freshness_class=temporal_class,
        cache_control_outcome=control.reason,
    )
