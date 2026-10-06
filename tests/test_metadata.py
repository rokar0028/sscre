import pytest

from sscre.metadata import extract_metadata


@pytest.mark.parametrize(
    ("query", "intent"),
    [
        ("Explain how caching works", "explain"),
        ("Compare PostgreSQL and SQLite", "compare"),
        ("Write a Python function", "code"),
        ("Summarize the main ideas", "summarize"),
        ("Who invented Python?", "factual"),
    ],
)
def test_extracts_unambiguous_intent(query: str, intent: str) -> None:
    assert extract_metadata(query).intent == intent


@pytest.mark.parametrize(
    ("query", "output_format"),
    [
        ("Return the answer as JSON", "json"),
        ("Put the differences in a table", "table"),
        ("Give me a list of benefits", "list"),
        ("Provide a code snippet", "code"),
        ("Answer in plain text", "prose"),
    ],
)
def test_extracts_unambiguous_output_format(
    query: str,
    output_format: str,
) -> None:
    assert extract_metadata(query).output_format == output_format


def test_conflicting_signals_remain_unknown() -> None:
    metadata = extract_metadata("Compare and explain the options as JSON or a table")

    assert metadata.intent == "unknown"
    assert metadata.output_format == "unknown"


def test_missing_signals_remain_unknown() -> None:
    metadata = extract_metadata("binary search")

    assert metadata.intent == "unknown"
    assert metadata.output_format == "unknown"


def test_extraction_is_case_and_whitespace_insensitive() -> None:
    first = extract_metadata("  EXPLAIN   caching  ")
    second = extract_metadata("explain caching")

    assert first == second


def test_empty_query_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        extract_metadata("  ")


def test_extracts_language_audience_platform_entities_and_domain() -> None:
    metadata = extract_metadata(
        "Write Python code for beginners on Linux using PostgreSQL"
    )

    assert metadata.domain == "programming"
    assert metadata.constraints == (
        ("language", "python"),
        ("audience", "beginner"),
        ("platform", "linux"),
    )
    assert metadata.entities == ("postgresql", "python", "linux")


def test_conflicting_constraints_are_not_guessed() -> None:
    metadata = extract_metadata("Write Python or Java code")

    assert ("language", "python") not in metadata.constraints
    assert ("language", "java") not in metadata.constraints
    assert metadata.domain == "programming"


def test_finance_domain_is_detected_without_programming_signals() -> None:
    assert extract_metadata("Explain the current stock price").domain == "finance"


def test_extracts_version_and_library_constraints() -> None:
    metadata = extract_metadata("Use Django version 4.2 on a web platform")

    assert ("library", "django") in metadata.constraints
    assert ("version", "4.2") in metadata.constraints
    assert ("platform", "web") in metadata.constraints


def test_language_neutral_constraint_is_explicit() -> None:
    metadata = extract_metadata("Give a language-neutral algorithm")

    assert ("language", "neutral") in metadata.constraints


@pytest.mark.parametrize(
    ("query", "temporal_class"),
    [
        ("What is the current stock price?", "dynamic"),
        ("Give me the latest Python version", "dynamic"),
        ("Summarize recent database changes", "semi_dynamic"),
        ("Explain binary search", "stable"),
    ],
)
def test_classifies_temporal_freshness(
    query: str,
    temporal_class: str,
) -> None:
    assert extract_metadata(query).temporal_class == temporal_class


def test_dynamic_temporal_signal_takes_precedence() -> None:
    assert (
        extract_metadata("What is the current price this month?").temporal_class
        == "dynamic"
    )


def test_ambiguous_domain_remains_unknown() -> None:
    assert extract_metadata("Compare stock algorithms").domain == "unknown"
