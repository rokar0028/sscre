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


def test_normalize_query_preserves_unicode_case_and_punctuation() -> None:
    assert normalize_query("  Café\t— λ?  ") == "Café — λ?"


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


def test_hash_is_sha256_hex() -> None:
    digest = hash_query("Python")

    assert digest == "18885f27b5af9012df19e496460f9294d5ab76128824c6f993787004f6d9a7db"
    assert len(digest) == 64
    assert all(character in "0123456789abcdef" for character in digest)


def test_different_normalized_queries_have_different_hashes() -> None:
    assert hash_query("Python") != hash_query("Java")


def test_preprocess_extracts_metadata_without_changing_normalization() -> None:
    processed = preprocess_query(QueryRequest(query="  Explain   caching  "))

    assert processed.normalized_query == "Explain caching"
    assert processed.metadata.intent == "explain"
