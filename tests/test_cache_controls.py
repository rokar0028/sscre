from datetime import datetime, timedelta, timezone

import pytest

from sscre.cache_controls import (
    CacheControlPolicy,
    CacheSizeLimits,
    evaluate_cache_control,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_default_policy_defines_stable_and_semi_dynamic_ttls() -> None:
    policy = CacheControlPolicy()

    assert policy.ttl_for("stable") == timedelta(days=30)
    assert policy.ttl_for("semi_dynamic") == timedelta(hours=24)
    assert policy.ttl_for("dynamic") is None


def test_dynamic_entries_are_disabled_by_default() -> None:
    result = evaluate_cache_control(
        "dynamic",
        NOW + timedelta(minutes=1),
        now=NOW,
    )

    assert result.reusable is False
    assert result.reason == "dynamic_entries_disabled"


def test_dynamic_entries_require_explicit_positive_ttl() -> None:
    with pytest.raises(ValueError, match="dynamic_ttl"):
        CacheControlPolicy(allow_dynamic_entries=True)

    policy = CacheControlPolicy(
        allow_dynamic_entries=True,
        dynamic_ttl=timedelta(minutes=5),
    )
    assert policy.ttl_for("dynamic") == timedelta(minutes=5)


def test_expiration_is_exclusive_at_the_boundary() -> None:
    result = evaluate_cache_control("stable", NOW, now=NOW)

    assert result.reusable is False
    assert result.reason == "expired"


def test_fresh_entry_is_reusable_before_expiration() -> None:
    result = evaluate_cache_control(
        "stable",
        NOW + timedelta(seconds=1),
        now=NOW,
    )

    assert result.reusable is True
    assert result.reason == "fresh"


@pytest.mark.parametrize(
    ("expiration", "reason"),
    [
        (None, "missing_expiration"),
        (datetime(2026, 1, 1), "invalid_expiration"),
    ],
)
def test_missing_or_naive_expiration_fails_closed(
    expiration: datetime | None,
    reason: str,
) -> None:
    result = evaluate_cache_control("stable", expiration, now=NOW)

    assert result.reusable is False
    assert result.reason == reason


def test_now_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_cache_control(
            "stable",
            NOW + timedelta(seconds=1),
            now=datetime(2026, 1, 1),
        )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("answer", "12345", "answer_too_large"),
        ("normalized_query", "12345", "query_too_large"),
    ],
)
def test_cache_size_limits_reject_oversized_text(
    field: str,
    value: str,
    reason: str,
) -> None:
    values = {
        "answer": "a",
        "normalized_query": "query",
        "metadata": None,
    }
    values[field] = value

    limits = CacheSizeLimits(
        max_answer_bytes=4 if field == "answer" else 100,
        max_metadata_bytes=100,
        max_query_bytes=4 if field == "normalized_query" else 100,
    )

    assert limits.rejection_reason(**values) == reason


def test_cache_size_limits_reject_serialized_metadata() -> None:
    class LargeMetadata:
        def to_dict(self) -> dict[str, str]:
            return {"value": "x" * 20}

    limits = CacheSizeLimits(
        max_answer_bytes=100,
        max_metadata_bytes=10,
        max_query_bytes=100,
    )

    assert (
        limits.rejection_reason(
            answer="answer",
            normalized_query="query",
            metadata=LargeMetadata(),
        )
        == "metadata_too_large"
    )


def test_cache_size_limits_use_utf8_bytes_and_allow_empty_values() -> None:
    limits = CacheSizeLimits(
        max_answer_bytes=4,
        max_metadata_bytes=100,
        max_query_bytes=100,
    )

    assert (
        limits.rejection_reason(
            answer="éé",
            normalized_query="query",
            metadata=None,
        )
        is None
    )
    assert (
        limits.rejection_reason(
            answer="ééé",
            normalized_query="query",
            metadata=None,
        )
        == "answer_too_large"
    )
    assert (
        limits.rejection_reason(
            answer="",
            normalized_query="",
            metadata=None,
        )
        is None
    )
