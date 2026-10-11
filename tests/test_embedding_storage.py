import json

from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.safety import QueryMetadata


def _entry(
    query_hash: str,
    query: str,
    answer: str,
    *,
    embedding: tuple[float, ...] | None = None,
    metadata: QueryMetadata | None = None,
) -> CacheEntry:
    return CacheEntry(
        query_hash=query_hash,
        normalized_query=query,
        answer=answer,
        embedding=embedding,
        embedding_model="fake-embedding" if embedding is not None else None,
        embedding_dimension=len(embedding) if embedding is not None else None,
        metadata=metadata,
    )


def test_breakdown_without_embedding_matches_storage_bytes() -> None:
    cache = InMemoryExactCache()
    cache.insert(_entry("h1", "café", "answer"))
    parts = cache.byte_breakdown()

    assert parts.embedding_bytes == 0
    assert parts.query_bytes == len("café".encode("utf-8"))
    assert parts.total_bytes == cache.storage_bytes()
    assert parts.total_bytes == cache.storage_stats().total_bytes
    assert parts.embedding_share == 0.0
    metadata = json.dumps({}, separators=(",", ":"), ensure_ascii=False)
    assert parts.metadata_bytes == len(metadata.encode("utf-8"))
    assert (
        parts.query_bytes
        + parts.metadata_bytes
        + parts.embedding_bytes
        + parts.answer_bytes
        == cache.storage_bytes()
    )


def test_embedding_bytes_are_four_per_dimension() -> None:
    embedding = (0.1, -0.2, 0.3, 0.4)
    cache = InMemoryExactCache()
    cache.insert(
        _entry(
            "h1",
            "query",
            "answer",
            embedding=embedding,
            metadata=QueryMetadata(domain="programming", entities=("café",)),
        )
    )
    parts = cache.byte_breakdown()

    assert parts.embedding_bytes == len(embedding) * 4
    assert parts.total_bytes == cache.storage_bytes()
    assert parts.embedding_share == parts.embedding_bytes / parts.total_bytes


def test_dedup_counts_shared_answer_once() -> None:
    answer = "shared-answer"
    embedding = (0.5, 0.5)
    dedup = InMemoryExactCache(deduplicate=True)
    plain = InMemoryExactCache(deduplicate=False)
    for cache in (dedup, plain):
        cache.insert(_entry("h1", "first", answer, embedding=embedding))
        cache.insert(_entry("h2", "second", answer, embedding=embedding))

    dedup_parts = dedup.byte_breakdown()
    plain_parts = plain.byte_breakdown()
    answer_bytes = len(answer.encode("utf-8"))

    assert dedup_parts.answer_bytes == answer_bytes
    assert plain_parts.answer_bytes == answer_bytes * 2
    assert dedup_parts.embedding_bytes == len(embedding) * 4 * 2
    assert dedup_parts.total_bytes == dedup.storage_bytes()
    assert plain_parts.total_bytes == plain.storage_bytes()
    assert dedup_parts.total_bytes < plain_parts.total_bytes


def test_empty_cache_breakdown_is_zero() -> None:
    cache = InMemoryExactCache()
    parts = cache.byte_breakdown()

    assert parts.total_bytes == 0
    assert parts.embedding_bytes == 0
    assert cache.storage_bytes() == 0
    assert parts.embedding_share == 0.0
