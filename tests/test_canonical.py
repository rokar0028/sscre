from datetime import datetime, timezone

import pytest

from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.canonical import CanonicalAnswer, canonical_answer, hash_answer
from sscre.safety import QueryMetadata


def test_answer_hash_is_stable_and_utf8_based() -> None:
    answer = "Résumé: use a cache."

    assert hash_answer(answer) == hash_answer(answer)
    assert canonical_answer(answer).answer_hash == hash_answer(answer)


def test_cache_entry_exposes_content_identity_without_query_metadata() -> None:
    entry = CacheEntry(
        query_hash="query-hash",
        normalized_query="query",
        answer="same canonical answer",
        metadata=QueryMetadata(temporal_class="stable"),
    )

    assert entry.answer_hash == hash_answer(entry.answer)


def test_canonical_answer_rejects_hash_mismatch() -> None:
    with pytest.raises(ValueError, match="answer_hash"):
        CanonicalAnswer(answer_hash="0" * 64, answer="answer")


def test_canonical_answer_keeps_provenance_bounded_to_labels() -> None:
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    record = canonical_answer(
        "shared answer",
        model_source="model-a",
        preference_label="A",
        correctness_label="correct",
        validation_status="human",
        created_at=created_at,
    )

    assert record.model_source == "model-a"
    assert record.preference_label == "A"
    assert record.correctness_label == "correct"
    assert record.validation_status == "human"
    assert record.created_at == created_at


def test_canonical_answer_requires_timezone_aware_creation_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        canonical_answer(
            "answer",
            created_at=datetime(2026, 1, 1),
        )


def test_in_memory_cache_reuses_one_canonical_answer_body() -> None:
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash="query-1",
            normalized_query="first query",
            answer="shared answer",
            metadata=QueryMetadata(temporal_class="stable"),
        )
    )
    cache.insert(
        CacheEntry(
            query_hash="query-2",
            normalized_query="second query",
            answer="shared answer",
            metadata=QueryMetadata(temporal_class="semi_dynamic"),
        )
    )

    first = cache.get_by_query_hash("query-1")
    second = cache.get_by_query_hash("query-2")
    assert first is not None
    assert second is not None
    assert first.canonical_answer_hash == second.canonical_answer_hash
    assert cache.canonical_answer_count() == 1
    assert first.metadata != second.metadata
