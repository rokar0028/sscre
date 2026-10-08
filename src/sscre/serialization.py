"""JSON boundaries for safety decisions, traces, and operational logs.

See ``docs/phase-2/SERIALIZATION_BOUNDARY_v1.md``.
"""

import json
from collections.abc import Mapping
from sscre.safety import (
    CANDIDATE_TRACE_CONTRACT_VERSION,
    MAX_CANDIDATE_TRACES,
    MAX_TRACE_METADATA_JSON_BYTES,
    SAFETY_DECISIONS,
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
        "query",
        "query_a",
        "query_b",
        "query_text",
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
    return {
        "schema_version": BOUNDARY_SERIALIZATION_VERSION,
        "safety_contract_version": SAFETY_EVALUATION_CONTRACT_VERSION,
        "trace_contract_version": CANDIDATE_TRACE_CONTRACT_VERSION,
        **result.to_log_dict(),
        "candidate_traces": boundary_candidate_traces(result.candidate_traces),
    }


def attach_evaluation_report_schema(payload: Mapping[str, object]) -> dict[str, object]:
    from sscre.evaluation_statistics import attach_evaluation_statistics_schema
    from sscre.freshness_evaluation import attach_freshness_evaluation_schema

    envelope = {
        "schema_version": BOUNDARY_SERIALIZATION_VERSION,
        "safety_contract_version": SAFETY_EVALUATION_CONTRACT_VERSION,
        "trace_contract_version": CANDIDATE_TRACE_CONTRACT_VERSION,
        **dict(payload),
    }
    with_statistics = attach_evaluation_statistics_schema(envelope)
    return attach_freshness_evaluation_schema(with_statistics)


_OPERATIONAL_QUERY_TEXT_KEYS = frozenset({"query_a", "query_b"})
_FAILURE_EXAMPLE_LIST_KEYS = frozenset(
    {
        "false_positive_examples",
        "failure_examples",
        "observed_pair_records",
    }
)


def _redact_query_text_from_examples(examples: object) -> object:
    if not isinstance(examples, list):
        return examples
    redacted: list[object] = []
    for item in examples:
        if isinstance(item, dict):
            redacted.append(
                {
                    key: value
                    for key, value in item.items()
                    if key not in _OPERATIONAL_QUERY_TEXT_KEYS
                }
            )
        else:
            redacted.append(item)
    return redacted


def redact_operational_evaluation_report(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Remove reviewed query text from saved evaluation failure galleries."""
    result = dict(payload)
    for key in _FAILURE_EXAMPLE_LIST_KEYS:
        if key in result:
            result[key] = _redact_query_text_from_examples(result[key])

    baselines = result.get("baselines")
    if isinstance(baselines, dict):
        result["baselines"] = {
            name: redact_operational_evaluation_report(baseline)
            if isinstance(baseline, dict)
            else baseline
            for name, baseline in baselines.items()
        }

    gallery = result.get("failure_gallery")
    if isinstance(gallery, dict):
        result["failure_gallery"] = {
            key: _redact_query_text_from_examples(value)
            for key, value in gallery.items()
        }

    statistics = result.get("statistics")
    if isinstance(statistics, dict):
        validate_redacted_report_payload(statistics)

    freshness = result.get("freshness_experiment")
    if isinstance(freshness, dict):
        validate_redacted_report_payload(freshness)

    request_samples = result.get("request_samples")
    if request_samples is not None:
        validate_redacted_report_payload(request_samples)

    baselines = result.get("baselines")
    if isinstance(baselines, dict):
        for baseline in baselines.values():
            if isinstance(baseline, dict) and "request_samples" in baseline:
                validate_redacted_report_payload(baseline["request_samples"])

    return result


def build_cache_decision_log(event: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize structured cache decision logs."""
    _reject_forbidden_keys(event)
    normalized = dict(event)
    decision = normalized.get("decision")
    if decision is not None and decision not in SAFETY_DECISIONS:
        raise ValueError("decision must be SAFE, UNSAFE, or UNCERTAIN")
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


def validate_redacted_report_payload(payload: object) -> None:
    """Reject credential-like and raw-content keys from report artifacts."""
    _reject_forbidden_keys(payload)


def validate_statistics_preserves_redaction(
    payload: Mapping[str, object],
) -> None:
    """Ensure statistics blocks survive operational redaction unchanged."""
    if "statistics" not in payload:
        return
    before = payload.get("statistics")
    after = redact_operational_evaluation_report(payload).get("statistics")
    if before != after:
        raise ValueError("statistics block must be preserved by redaction")


def _reject_forbidden_keys(payload: object) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in _FORBIDDEN_LOG_KEYS:
                raise ValueError(f"decision log must not include field {key!r}")
            _reject_forbidden_keys(value)
        return
    if isinstance(payload, (list, tuple)):
        for item in payload:
            _reject_forbidden_keys(item)


def _assert_trace_payload_bounded(traces: object) -> None:
    if traces is None:
        return
    if not isinstance(traces, list):
        raise ValueError("candidate_traces must serialize to a JSON list")
    payload = json.dumps(traces, sort_keys=True, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_BOUNDARY_TRACE_JSON_BYTES:
        raise ValueError("serialized candidate_traces exceed boundary size limit")
    if len(traces) > MAX_CANDIDATE_TRACES:
        raise ValueError("serialized candidate_traces exceed trace count limit")
    for item in traces:
        if not isinstance(item, dict):
            raise ValueError("each candidate trace must be an object")
        _reject_forbidden_keys(item)
        for meta_key in ("query_metadata", "candidate_metadata"):
            metadata = item.get(meta_key)
            if metadata is None:
                continue
            encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > MAX_TRACE_METADATA_JSON_BYTES:
                raise ValueError("trace metadata exceeds serialized size limit")


def cap_traces_for_boundary(
    traces: tuple[CandidateTrace, ...],
) -> tuple[CandidateTrace, ...]:
    """Public alias for trace-count capping at integration boundaries."""
    return cap_candidate_traces(traces)
