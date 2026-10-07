import pytest

from sscre.cache import CacheCandidate
from sscre.compatibility import evaluate_candidate
from sscre.safety import QueryMetadata


def metadata(
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


def candidate(candidate_metadata: QueryMetadata | None = None) -> CacheCandidate:
    return CacheCandidate(
        query_hash="candidate-1",
        normalized_query="write python code for binary search",
        answer="cached answer",
        similarity=0.98,
        embedding_model="test-embedding",
        embedding_dimension=2,
        metadata=candidate_metadata,
    )


def test_compatible_candidate_is_safe() -> None:
    query_metadata = metadata()

    result = evaluate_candidate(
        query_metadata,
        candidate(query_metadata),
        similarity_threshold=0.95,
    )

    assert result.decision == "SAFE"
    assert result.reason == "compatible_metadata"


def test_similarity_below_threshold_is_unsafe() -> None:
    low_similarity = CacheCandidate(
        **{**candidate(metadata()).__dict__, "similarity": 0.8}
    )

    result = evaluate_candidate(
        metadata(),
        low_similarity,
        similarity_threshold=0.95,
    )

    assert result.decision == "UNSAFE"
    assert result.reason == "similarity_below_threshold"


def test_incomplete_constraint_evidence_is_uncertain() -> None:
    result = evaluate_candidate(
        metadata(constraints=(("language", "python"),)),
        candidate(metadata(constraints=())),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNCERTAIN"
    assert result.reason == "incomplete_constraint_evidence"


def test_incomplete_entity_evidence_is_uncertain() -> None:
    result = evaluate_candidate(
        metadata(entities=("binary search",)),
        candidate(metadata(entities=())),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNCERTAIN"
    assert result.reason == "incomplete_entity_evidence"


def test_dynamic_candidate_is_unsafe() -> None:
    result = evaluate_candidate(
        metadata(),
        candidate(metadata(temporal_class="dynamic")),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNSAFE"
    assert result.reason == "candidate_is_dynamic"


def test_missing_candidate_metadata_is_uncertain() -> None:
    result = evaluate_candidate(
        metadata(),
        candidate(),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNCERTAIN"
    assert result.reason == "candidate_metadata_missing"


@pytest.mark.parametrize(
    ("query_metadata", "candidate_metadata", "reason"),
    [
        (
            metadata(),
            metadata(constraints=(("language", "java"),)),
            "constraint_mismatch:language",
        ),
        (
            metadata(),
            metadata(entities=("sorting",)),
            "entity_mismatch",
        ),
        (
            metadata(),
            metadata(intent="explain"),
            "intent_mismatch",
        ),
        (
            metadata(),
            metadata(domain="finance"),
            "domain_mismatch",
        ),
        (
            metadata(),
            metadata(output_format="json"),
            "format_mismatch",
        ),
    ],
)
def test_explicit_incompatibility_is_unsafe(
    query_metadata: QueryMetadata,
    candidate_metadata: QueryMetadata,
    reason: str,
) -> None:
    result = evaluate_candidate(
        query_metadata,
        candidate(candidate_metadata),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNSAFE"
    assert result.reason == reason


def test_dynamic_query_is_not_reusable() -> None:
    result = evaluate_candidate(
        metadata(temporal_class="dynamic"),
        candidate(metadata()),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNSAFE"
    assert result.reason == "dynamic_query_not_reusable"


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("intent", "missing_intent_evidence"),
        ("domain", "missing_domain_evidence"),
        ("output_format", "missing_output_format_evidence"),
    ],
)
def test_missing_field_evidence_is_uncertain(field: str, reason: str) -> None:
    result = evaluate_candidate(
        metadata(**{field: "unknown"}),
        candidate(metadata()),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNCERTAIN"
    assert result.reason == reason


def test_missing_metadata_is_uncertain_instead_of_safe() -> None:
    result = evaluate_candidate(
        metadata(output_format="unknown"),
        candidate(metadata(output_format="unknown")),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNCERTAIN"
    assert result.reason == "missing_output_format_evidence"


def test_temporal_class_mismatch_is_uncertain() -> None:
    result = evaluate_candidate(
        metadata(temporal_class="semi_dynamic"),
        candidate(metadata(temporal_class="stable")),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNCERTAIN"
    assert result.reason == "temporal_class_mismatch"


def test_constraint_mismatch_uses_sorted_key() -> None:
    result = evaluate_candidate(
        metadata(constraints=(("version", "3"), ("language", "python"))),
        candidate(
            metadata(constraints=(("language", "java"), ("version", "2")))
        ),
        similarity_threshold=0.95,
    )

    assert result.decision == "UNSAFE"
    assert result.reason == "constraint_mismatch:language"


def test_threshold_must_be_valid() -> None:
    with pytest.raises(ValueError, match="similarity_threshold"):
        evaluate_candidate(
            metadata(),
            candidate(metadata()),
            similarity_threshold=1.1,
        )
