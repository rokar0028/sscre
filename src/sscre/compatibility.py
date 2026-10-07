"""Pure compatibility checks for retrieved cache candidates."""

from sscre.cache import CacheCandidate
from sscre.safety import CandidateTrace, QueryMetadata


def _constraints(metadata: QueryMetadata) -> dict[str, str]:
    return dict(metadata.constraints)


def evaluate_candidate(
    query_metadata: QueryMetadata,
    candidate: CacheCandidate,
    *,
    similarity_threshold: float,
) -> CandidateTrace:
    """Evaluate one candidate without database or provider dependencies."""
    if not -1.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between -1 and 1")
    if candidate.similarity < similarity_threshold:
        return CandidateTrace(
            candidate.query_hash,
            candidate.similarity,
            "UNSAFE",
            "similarity_below_threshold",
        )

    if query_metadata.temporal_class == "dynamic":
        return CandidateTrace(
            candidate.query_hash,
            candidate.similarity,
            "UNSAFE",
            "dynamic_query_not_reusable",
        )
    if candidate.metadata is None:
        return CandidateTrace(
            candidate.query_hash,
            candidate.similarity,
            "UNCERTAIN",
            "candidate_metadata_missing",
        )
    if candidate.metadata.temporal_class == "dynamic":
        return CandidateTrace(
            candidate.query_hash,
            candidate.similarity,
            "UNSAFE",
            "candidate_is_dynamic",
        )

    query_constraints = _constraints(query_metadata)
    candidate_constraints = _constraints(candidate.metadata)
    shared_keys = query_constraints.keys() & candidate_constraints.keys()
    for key in sorted(shared_keys):
        if query_constraints[key] != candidate_constraints[key]:
            return CandidateTrace(
                candidate.query_hash,
                candidate.similarity,
                "UNSAFE",
                f"constraint_mismatch:{key}",
            )
    if set(query_constraints) != set(candidate_constraints):
        return CandidateTrace(
            candidate.query_hash,
            candidate.similarity,
            "UNCERTAIN",
            "incomplete_constraint_evidence",
        )

    if (
        query_metadata.entities
        and candidate.metadata.entities
        and not set(query_metadata.entities) & set(candidate.metadata.entities)
    ):
        return CandidateTrace(
            candidate.query_hash,
            candidate.similarity,
            "UNSAFE",
            "entity_mismatch",
        )
    if bool(query_metadata.entities) != bool(candidate.metadata.entities):
        return CandidateTrace(
            candidate.query_hash,
            candidate.similarity,
            "UNCERTAIN",
            "incomplete_entity_evidence",
        )

    for field, reason in (
        ("intent", "intent_mismatch"),
        ("domain", "domain_mismatch"),
        ("output_format", "format_mismatch"),
    ):
        query_value = getattr(query_metadata, field)
        candidate_value = getattr(candidate.metadata, field)
        if query_value != "unknown" and candidate_value != "unknown":
            if query_value != candidate_value:
                return CandidateTrace(
                    candidate.query_hash,
                    candidate.similarity,
                    "UNSAFE",
                    reason,
                )
        else:
            return CandidateTrace(
                candidate.query_hash,
                candidate.similarity,
                "UNCERTAIN",
                f"missing_{field}_evidence",
            )

    if query_metadata.temporal_class != candidate.metadata.temporal_class:
        return CandidateTrace(
            candidate.query_hash,
            candidate.similarity,
            "UNCERTAIN",
            "temporal_class_mismatch",
        )

    return CandidateTrace(
        candidate.query_hash,
        candidate.similarity,
        "SAFE",
        "compatible_metadata",
    )


def evaluate_candidate_boundary(
    query_metadata: QueryMetadata,
    candidate: CacheCandidate,
    *,
    similarity_threshold: float,
) -> CandidateTrace:
    """Evaluate one candidate; map validator failures to ``UNCERTAIN``."""
    try:
        return evaluate_candidate(
            query_metadata,
            candidate,
            similarity_threshold=similarity_threshold,
        )
    except Exception:
        similarity = candidate.similarity
        if not -1.0 <= similarity <= 1.0:
            similarity = 0.0
        return CandidateTrace(
            candidate_query_hash=candidate.query_hash,
            similarity=similarity,
            decision="UNCERTAIN",
            reason="safety_validator_error",
        )
