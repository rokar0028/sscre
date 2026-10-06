import pytest

from sscre.cache import CacheEntry, InMemoryExactCache


def make_entry(query_hash: str, vector: tuple[float, ...]) -> CacheEntry:
    return CacheEntry(
        query_hash=query_hash,
        normalized_query=query_hash,
        answer=f"answer for {query_hash}",
        embedding=vector,
        embedding_model="test-embedding",
        embedding_dimension=len(vector),
    )


def test_in_memory_search_returns_nearest_candidates_in_order() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cache.insert(make_entry("far", (0.0, 1.0)))
    cache.insert(make_entry("near", (1.0, 0.0)))

    candidates = cache.search_by_embedding((1.0, 0.0), top_k=2)

    assert [candidate.query_hash for candidate in candidates] == ["near", "far"]
    assert candidates[0].similarity == pytest.approx(1.0)
    assert candidates[1].similarity == pytest.approx(0.0)


def test_in_memory_search_breaks_similarity_ties_by_query_hash() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)
    cache.insert(make_entry("b", (1.0, 0.0)))
    cache.insert(make_entry("a", (1.0, 0.0)))

    candidates = cache.search_by_embedding((1.0, 0.0), top_k=2)

    assert [candidate.query_hash for candidate in candidates] == ["a", "b"]


def test_in_memory_search_returns_empty_for_empty_repository() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)

    assert cache.search_by_embedding((1.0, 0.0), top_k=1) == ()


@pytest.mark.parametrize("top_k", [0, -1, 3])
def test_in_memory_search_rejects_invalid_top_k(top_k: int) -> None:
    cache = InMemoryExactCache(max_top_k=2, embedding_dimension=2)

    with pytest.raises(ValueError):
        cache.search_by_embedding((1.0, 0.0), top_k=top_k)


def test_in_memory_search_rejects_incompatible_query_dimension() -> None:
    cache = InMemoryExactCache(embedding_dimension=2)

    with pytest.raises(ValueError, match="configured dimension"):
        cache.search_by_embedding((1.0, 0.0, 0.0), top_k=1)
