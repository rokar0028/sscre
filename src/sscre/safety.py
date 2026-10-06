"""Domain contract for compatibility-aware cache safety decisions.

Embedding similarity from Strategy B is only a retrieval signal. A SAFE result
from this contract represents a later compatibility decision, not similarity
alone.

See ``docs/phase-2/SAFETY_EVALUATION_CONTRACT_v1.md`` for the versioned
evaluation artifact specification.

Candidate trace shape and reason taxonomy:
``docs/phase-2/CANDIDATE_TRACE_CONTRACT_v1.md``.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

SAFETY_EVALUATION_CONTRACT_VERSION = "1.0.0"
CANDIDATE_TRACE_CONTRACT_VERSION = "1.0.0"
MAX_CANDIDATE_TRACES = 100
MAX_TRACE_METADATA_JSON_BYTES = 8 * 1024

SafetyDecision = Literal["SAFE", "UNSAFE", "UNCERTAIN"]
SAFETY_DECISIONS: tuple[SafetyDecision, ...] = ("SAFE", "UNSAFE", "UNCERTAIN")
TraceStage = Literal["retrieval", "compatibility"]


def is_reusable_decision(decision: SafetyDecision) -> bool:
    """Return True only when a cache candidate may be served."""
    return decision == "SAFE"


_DOCUMENTED_CANDIDATE_REASONS = frozenset(
    {
        "similarity_below_threshold",
        "dynamic_query_not_reusable",
        "candidate_metadata_missing",
        "candidate_is_dynamic",
        "incomplete_constraint_evidence",
        "entity_mismatch",
        "incomplete_entity_evidence",
        "intent_mismatch",
        "domain_mismatch",
        "format_mismatch",
        "temporal_class_mismatch",
        "compatible_metadata",
        "safety_validator_error",
        "similarity_threshold_met",
        "exact_query_hash_match",
    }
)
_MISSING_EVIDENCE_REASON = re.compile(r"^missing_[a-z_]+_evidence$")
_CONSTRAINT_MISMATCH_REASON = re.compile(r"^constraint_mismatch:[a-zA-Z0-9_-]+$")


def is_documented_trace_reason(reason: str) -> bool:
    """Return True when ``reason`` follows the candidate trace taxonomy."""
    if reason in _DOCUMENTED_CANDIDATE_REASONS:
        return True
    if _CONSTRAINT_MISMATCH_REASON.fullmatch(reason):
        return True
    return _MISSING_EVIDENCE_REASON.fullmatch(reason) is not None


def validate_trace_reason(reason: str) -> str:
    """Require a non-empty, taxonomy-aligned candidate trace reason."""
    normalized = reason.strip()
    if not normalized:
        raise ValueError("reason must not be empty")
    if not is_documented_trace_reason(normalized):
        raise ValueError(f"unsupported trace reason: {normalized}")
    return normalized


def bound_trace_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    """Return bounded metadata safe for operational trace serialization."""
    if not metadata:
        return {}
    bounded = QueryMetadata.from_dict(metadata).to_dict()
    payload = json.dumps(bounded, sort_keys=True, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_TRACE_METADATA_JSON_BYTES:
        raise ValueError("trace metadata exceeds serialized size limit")
    return bounded


QueryIntent = Literal[
    "explain",
    "code",
    "compare",
    "factual",
    "summarize",
    "unknown",
]
QueryDomain = Literal["programming", "finance", "general", "unknown"]
TemporalClass = Literal["stable", "semi_dynamic", "dynamic"]
OutputFormat = Literal["prose", "code", "list", "table", "json", "unknown"]

MAX_METADATA_ENTITIES = 10
MAX_METADATA_ENTITY_LENGTH = 128
MAX_METADATA_CONSTRAINTS = 20
MAX_METADATA_KEY_LENGTH = 64
MAX_METADATA_VALUE_LENGTH = 256


@dataclass(frozen=True)
class QueryMetadata:
    """Bounded, serializable metadata used by the safety engine.

    Unknown values are intentional: metadata extraction must not infer
    compatibility when a requirement is absent or ambiguous.
    """

    intent: QueryIntent = "unknown"
    domain: QueryDomain = "unknown"
    entities: tuple[str, ...] = ()
    constraints: tuple[tuple[str, str], ...] = ()
    temporal_class: TemporalClass = "stable"
    output_format: OutputFormat = "unknown"

    def __post_init__(self) -> None:
        if self.intent not in {
            "explain",
            "code",
            "compare",
            "factual",
            "summarize",
            "unknown",
        }:
            raise ValueError("unsupported query intent")
        if self.domain not in {"programming", "finance", "general", "unknown"}:
            raise ValueError("unsupported query domain")
        if self.temporal_class not in {"stable", "semi_dynamic", "dynamic"}:
            raise ValueError("unsupported temporal class")
        if self.output_format not in {
            "prose",
            "code",
            "list",
            "table",
            "json",
            "unknown",
        }:
            raise ValueError("unsupported output format")
        if len(self.entities) > MAX_METADATA_ENTITIES:
            raise ValueError(
                f"entities must contain at most {MAX_METADATA_ENTITIES} items"
            )
        if len(self.constraints) > MAX_METADATA_CONSTRAINTS:
            raise ValueError(
                "constraints must contain at most "
                f"{MAX_METADATA_CONSTRAINTS} items"
            )
        if len(set(self.entities)) != len(self.entities):
            raise ValueError("entities must not contain duplicates")
        if len({key for key, _ in self.constraints}) != len(self.constraints):
            raise ValueError("constraint keys must be unique")
        for entity in self.entities:
            if not entity or len(entity) > MAX_METADATA_ENTITY_LENGTH:
                raise ValueError(
                    "entity values must be non-empty and within the length limit"
                )
        for key, value in self.constraints:
            if (
                not key
                or len(key) > MAX_METADATA_KEY_LENGTH
                or not value
                or len(value) > MAX_METADATA_VALUE_LENGTH
            ):
                raise ValueError("constraint keys and values exceed metadata limits")

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON-compatible representation for storage."""
        return {
            "intent": self.intent,
            "domain": self.domain,
            "entities": list(self.entities),
            "constraints": dict(self.constraints),
            "temporal_class": self.temporal_class,
            "output_format": self.output_format,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "QueryMetadata":
        """Build metadata from the representation used in storage and traces."""
        entities = value.get("entities", ())
        constraints = value.get("constraints", {})
        if not isinstance(entities, (list, tuple)):
            raise ValueError("metadata entities must be a list")
        if not isinstance(constraints, Mapping):
            raise ValueError("metadata constraints must be an object")
        if not all(isinstance(item, str) for item in entities):
            raise ValueError("metadata entities must contain strings")
        if not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in constraints.items()
        ):
            raise ValueError("metadata constraints must contain string pairs")
        return cls(
            intent=value.get("intent", "unknown"),  # type: ignore[arg-type]
            domain=value.get("domain", "unknown"),  # type: ignore[arg-type]
            entities=tuple(entities),
            constraints=tuple(constraints.items()),
            temporal_class=value.get("temporal_class", "stable"),  # type: ignore[arg-type]
            output_format=value.get("output_format", "unknown"),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class CandidateTrace:
    """The explainable result of evaluating one retrieved candidate."""

    candidate_query_hash: str
    similarity: float
    decision: SafetyDecision
    reason: str
    candidate_order: int = 0
    stage: TraceStage = "compatibility"
    query_metadata: dict[str, object] = field(default_factory=dict)
    candidate_metadata: dict[str, object] = field(default_factory=dict)
    freshness_class: TemporalClass | None = None
    cache_control_outcome: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in SAFETY_DECISIONS:
            raise ValueError("decision must be SAFE, UNSAFE, or UNCERTAIN")
        if not self.candidate_query_hash:
            raise ValueError("candidate_query_hash must not be empty")
        if not -1.0 <= self.similarity <= 1.0:
            raise ValueError("similarity must be between -1 and 1")
        object.__setattr__(self, "reason", validate_trace_reason(self.reason))
        if self.candidate_order < 0:
            raise ValueError("candidate_order must not be negative")
        object.__setattr__(
            self,
            "query_metadata",
            bound_trace_metadata(self.query_metadata),
        )
        object.__setattr__(
            self,
            "candidate_metadata",
            bound_trace_metadata(self.candidate_metadata),
        )

    def to_log_dict(self) -> dict[str, object]:
        """Stable JSON-compatible trace without prompts, answers, or secrets."""
        payload: dict[str, object] = {
            "cache_control_outcome": self.cache_control_outcome,
            "candidate_metadata": self.candidate_metadata,
            "candidate_order": self.candidate_order,
            "candidate_query_hash": self.candidate_query_hash,
            "decision": self.decision,
            "freshness_class": self.freshness_class,
            "query_metadata": self.query_metadata,
            "reason": self.reason,
            "similarity": self.similarity,
            "stage": self.stage,
        }
        return payload


@dataclass(frozen=True)
class SafetyResult:
    """The final cache-reuse decision for a processed query."""

    decision: SafetyDecision
    strategy: str
    reason: str
    similarity: float | None = None
    selected_candidate_query_hash: str | None = None
    candidate_traces: tuple[CandidateTrace, ...] = ()

    def __post_init__(self) -> None:
        if self.decision not in SAFETY_DECISIONS:
            raise ValueError("decision must be SAFE, UNSAFE, or UNCERTAIN")
        if not self.strategy.strip():
            raise ValueError("strategy must not be empty")
        if not self.reason.strip():
            raise ValueError("reason must not be empty")
        if self.similarity is not None and not -1.0 <= self.similarity <= 1.0:
            raise ValueError("similarity must be between -1 and 1")
        if self.decision == "SAFE":
            if self.selected_candidate_query_hash is None:
                raise ValueError("SAFE result requires a selected candidate")
            if self.similarity is None:
                raise ValueError("SAFE result requires a similarity")
        else:
            if self.selected_candidate_query_hash is not None:
                raise ValueError("non-SAFE result cannot select a candidate")
            if self.similarity is not None:
                raise ValueError("non-SAFE result cannot include a similarity")

    def to_log_dict(self) -> dict[str, object]:
        return {
            "candidate_traces": serialize_candidate_traces(self.candidate_traces),
            "decision": self.decision,
            "reason": self.reason,
            "selected_candidate_query_hash": self.selected_candidate_query_hash,
            "similarity": self.similarity,
            "strategy": self.strategy,
        }


def cap_candidate_traces(
    traces: tuple[CandidateTrace, ...],
    *,
    limit: int = MAX_CANDIDATE_TRACES,
) -> tuple[CandidateTrace, ...]:
    if limit <= 0:
        raise ValueError("trace limit must be positive")
    return traces[:limit]


def serialize_candidate_traces(
    traces: tuple[CandidateTrace, ...],
    *,
    limit: int = MAX_CANDIDATE_TRACES,
) -> list[dict[str, object]]:
    """Serialize traces in deterministic retrieval order with a bounded count."""
    return [trace.to_log_dict() for trace in cap_candidate_traces(traces, limit=limit)]


def resolve_candidate_traces(
    traces: tuple[CandidateTrace, ...],
    *,
    strategy: str = "C",
) -> SafetyResult:
    """Resolve ordered candidate traces using conservative precedence.

    Candidates are expected in descending similarity order. The first SAFE
    candidate is selected. UNSAFE and UNCERTAIN candidates are never served;
    if no candidate is SAFE, the caller must generate a new answer.
    """
    if not strategy.strip():
        raise ValueError("strategy must not be empty")

    for trace in traces:
        if is_reusable_decision(trace.decision):
            return SafetyResult(
                decision="SAFE",
                strategy=strategy,
                reason=trace.reason,
                similarity=trace.similarity,
                selected_candidate_query_hash=trace.candidate_query_hash,
                candidate_traces=cap_candidate_traces(traces),
            )

    if any(trace.decision == "UNCERTAIN" for trace in traces):
        decision: SafetyDecision = "UNCERTAIN"
        reason = "no candidate had sufficient compatibility evidence"
    else:
        decision = "UNSAFE"
        reason = "all candidates were incompatible"

    return SafetyResult(
        decision=decision,
        strategy=strategy,
        reason=reason if traces else "no candidates were retrieved",
        candidate_traces=cap_candidate_traces(traces),
    )
