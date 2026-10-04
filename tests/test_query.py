import pytest
from pydantic import ValidationError

from sscre.query import (
    MAX_QUERY_LENGTH,
    QueryRequest,
    hash_query,
    normalize_query,
    preprocess_query,
)


def test_normalize_query_collapses_whitespace() -> None:
    assert normalize_query("  Explain\n\tPython   caching  ") == "Explain Python caching"


def test_query_rejects_empty_and_whitespace_only_values() -> None:
    with pytest.raises(ValueError):
        normalize_query(" \n\t ")

    with pytest.raises(ValidationError):
        QueryRequest(query=" \n\t ")


def test_query_rejects_oversized_values() -> None:
    with pytest.raises(ValidationError):
        QueryRequest(query="x" * (MAX_QUERY_LENGTH + 1))


def test_hash_is_stable_and_whitespace_equivalent() -> None:
    first = QueryRequest(query="What is  Python?")
    second = QueryRequest(query=" What is Python? ")

    assert hash_query(first.query) == hash_query(second.query)
    assert preprocess_query(first).query_hash == preprocess_query(second).query_hash


def test_different_normalized_queries_have_different_hashes() -> None:
    assert hash_query("Python") != hash_query("Java")
