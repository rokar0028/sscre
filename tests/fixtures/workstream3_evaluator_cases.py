"""Scenario builders for ``PURE_EVALUATOR_MATRIX`` rows (Workstream 3 step 2)."""

from __future__ import annotations

from sscre.cache import CacheCandidate
from sscre.safety import QueryMetadata

DEFAULT_THRESHOLD = 0.95


def _meta(
    *,
    intent: str = "code",
    domain: str = "programming",
    entities: tuple[str, ...] = ("binary search",),
    constraints: tuple[tuple[str, str], ...] = (("language", "python"),),
    temporal_class: str = "stable",
    output_format: str = "code",
) -> QueryMetadata:
    return QueryMetadata(
        intent=intent,  # type: ignore[arg-type]
        domain=domain,  # type: ignore[arg-type]
        entities=entities,
        constraints=constraints,
        temporal_class=temporal_class,  # type: ignore[arg-type]
        output_format=output_format,  # type: ignore[arg-type]
    )


def _candidate(
    meta: QueryMetadata | None,
    *,
    similarity: float = 0.98,
) -> CacheCandidate:
    return CacheCandidate(
        query_hash="candidate-1",
        normalized_query="write python code for binary search",
        answer="cached answer",
        similarity=similarity,
        embedding_model="test-embedding",
        embedding_dimension=2,
        metadata=meta,
    )


def evaluator_case(
    row_id: str,
) -> tuple[QueryMetadata, CacheCandidate, float]:
    """Return query metadata, candidate, and similarity threshold for a matrix row."""
    if row_id == "pe_similarity_below":
        meta = _meta()
        return meta, _candidate(meta, similarity=0.8), DEFAULT_THRESHOLD
    if row_id == "pe_dynamic_query":
        return (
            _meta(temporal_class="dynamic"),
            _candidate(_meta()),
            DEFAULT_THRESHOLD,
        )
    if row_id == "pe_missing_candidate_metadata":
        return _meta(), _candidate(None), DEFAULT_THRESHOLD
    if row_id == "pe_dynamic_candidate":
        return _meta(), _candidate(_meta(temporal_class="dynamic")), DEFAULT_THRESHOLD
    if row_id == "pe_constraint_mismatch":
        query = _meta(constraints=(("language", "python"),))
        return query, _candidate(_meta(constraints=(("language", "java"),))), DEFAULT_THRESHOLD
    if row_id == "pe_incomplete_constraints":
        query = _meta(constraints=(("language", "python"), ("runtime", "cpython")))
        return query, _candidate(_meta(constraints=(("language", "python"),))), DEFAULT_THRESHOLD
    if row_id == "pe_entity_mismatch":
        query = _meta(entities=("binary search",))
        return query, _candidate(_meta(entities=("merge sort",))), DEFAULT_THRESHOLD
    if row_id == "pe_incomplete_entities":
        query = _meta(entities=("binary search",))
        return query, _candidate(_meta(entities=())), DEFAULT_THRESHOLD
    if row_id == "pe_intent_mismatch":
        query = _meta()
        return query, _candidate(_meta(intent="explain")), DEFAULT_THRESHOLD
    if row_id == "pe_domain_mismatch":
        query = _meta()
        return query, _candidate(_meta(domain="finance")), DEFAULT_THRESHOLD
    if row_id == "pe_format_mismatch":
        query = _meta()
        return query, _candidate(_meta(output_format="json")), DEFAULT_THRESHOLD
    if row_id == "pe_missing_intent_evidence":
        query = _meta(intent="unknown")
        return query, _candidate(_meta()), DEFAULT_THRESHOLD
    if row_id == "pe_missing_domain_evidence":
        query = _meta(domain="unknown")
        return query, _candidate(_meta()), DEFAULT_THRESHOLD
    if row_id == "pe_missing_format_evidence":
        query = _meta(output_format="unknown")
        return query, _candidate(_meta()), DEFAULT_THRESHOLD
    if row_id == "pe_temporal_mismatch":
        query = _meta(temporal_class="semi_dynamic")
        return query, _candidate(_meta(temporal_class="stable")), DEFAULT_THRESHOLD
    if row_id == "pe_compatible":
        meta = _meta()
        return meta, _candidate(meta), DEFAULT_THRESHOLD
    raise KeyError(f"unknown pure evaluator row: {row_id}")
