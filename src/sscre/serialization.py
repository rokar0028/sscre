"""JSON boundaries for safety decisions, traces, and operational logs.

See ``docs/phase-2/SERIALIZATION_BOUNDARY_v1.md``.
"""

import json
from collections.abc import Mapping
from sscre.safety import (
    CANDIDATE_TRACE_CONTRACT_VERSION,
    MAX_CANDIDATE_TRACES,
    MAX_TRACE_METADATA_JSON_BYTES,
    SAFETY_EVALUATION_CONTRACT_VERSION,
    CandidateTrace,
    SafetyResult,
    cap_candidate_traces,
    serialize_candidate_traces,
)

BOUNDARY_SERIALIZATION_VERSION = "1.0.0"
MAX_BOUNDARY_TRACE_JSON_BYTES = MAX_CANDIDATE_TRACES * (
    MAX_TRACE_METADATA_JSON_BYTES + 512
)

_FORBIDDEN_LOG_KEYS = frozenset(
    {
        "answer",
        "authorization",
        "api_key",
        "normalized_query",
        "password",
        "prompt",
        "provider_secret",
        "secret",
        "token",
    }
)

# Paths that emit decision/trace JSON (audit reference for Workstream 1 step 5).
SERIALIZATION_EMITTERS = (
    "sscre.app.query /v1/query (QueryResponse + cache_decision logs)",
    "sscre.baseline._save_report (evaluation JSON reports)",
    "sscre.baseline failure_examples (evaluation_labels + optional traces)",
    "sscre.safety.SafetyResult.to_log_dict (aggregate artifacts)",
)


def boundary_candidate_traces(
    traces: tuple[CandidateTrace, ...],
) -> list[dict[str, object]] | None:
    """Return capped trace JSON for API fields; ``None`` when no traces exist."""
    if not traces:
        return None
    serialized = serialize_candidate_traces(traces)
    _assert_trace_payload_bounded(serialized)
    return serialized


def serialize_safety_result_for_boundary(
    result: SafetyResult,
) -> dict[str, object]:
    """One JSON object for reports and tooling."""
    payload = {
        "schema_version": BOUNDARY_SERIALIZATION_VERSION,
        "safety_contract_version": SAFETY_EVALUATION_CONTRACT_VERSION,
        "trace_contract_version": CANDIDATE_TRACE_CONTRACT_VERSION,
        **result.to_log_dict(),
    }
    _assert_trace_payload_bounded(payload.get("candidate_traces", []))
    return payload


def attach_evaluation_report_schema(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": BOUNDARY_SERIALIZATION_VERSION,
        **dict(payload),
    }


def build_cache_decision_log(event: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize structured cache decision logs."""
    _reject_forbidden_keys(event)
    normalized = dict(event)
    traces = normalized.get("candidate_traces")
    if traces is None:
        normalized["candidate_traces"] = None
    elif isinstance(traces, tuple):
        normalized["candidate_traces"] = boundary_candidate_traces(traces)
    elif isinstance(traces, list):
        _assert_trace_payload_bounded(traces)
    else:
        raise ValueError("candidate_traces must be a list, tuple, or null")
    normalized.setdefault("schema_version", BOUNDARY_SERIALIZATION_VERSION)
    return normalized


def dumps_cache_decision_log(event: Mapping[str, object]) -> str:
    return json.dumps(build_cache_decision_log(event), sort_keys=True)


def _reject_forbidden_keys(payload: Mapping[str, object]) -> None:
    for key in payload:
        if key.lower() in _FORBIDDEN_LOG_KEYS:
            raise ValueError(f"decision log must not include field {key!r}")


def _assert_trace_payload_bounded(traces: object) -> None:
    if traces is None:
        return
    if not isinstance(traces, list):
        raise ValueError("candidate_traces must serialize to a JSON list")
    payload = json.dumps(traces, sort_keys=True, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_BOUNDARY_TRACE_JSON_BYTES:
        raise ValueError("serialized candidate_traces exceed boundary size limit")
    for item in traces:
        if not isinstance(item, dict):
            raise ValueError("each candidate trace must be an object")
        _reject_forbidden_keys(item)


def cap_traces_for_boundary(
    traces: tuple[CandidateTrace, ...],
) -> tuple[CandidateTrace, ...]:
    """Public alias for trace-count capping at integration boundaries."""
    return cap_candidate_traces(traces)
