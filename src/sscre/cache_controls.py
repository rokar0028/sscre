"""Contract for cache freshness, TTL, and reuse eligibility.

Freshness policy is evaluated before the compatibility evaluator:

1. policy eligibility (including dynamic-entry policy)
2. TTL validity and expiration

The compatibility evaluator then checks the similarity threshold before
other compatibility rules. Aggregation serves a candidate only when the
decision is SAFE.

TTL controls whether an entry is available. It does not prove that the answer
is compatible; compatibility remains the responsibility of the safety engine.
The contract is deliberately failure-closed: missing or invalid expiration
data cannot produce a reusable entry. Expiration cleanup is lazy in this
contract: reads reject expired entries, while bounded deletion is a later
maintenance concern.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sscre.safety import TemporalClass

CacheControlReason = Literal[
    "fresh",
    "dynamic_entries_disabled",
    "missing_expiration",
    "invalid_expiration",
    "expired",
]
CacheSizeReason = Literal[
    "answer_too_large",
    "metadata_too_large",
    "query_too_large",
]


@dataclass(frozen=True)
class CacheSizeLimits:
    """Maximum UTF-8 storage sizes for one cache entry."""

    max_answer_bytes: int = 64 * 1024
    max_metadata_bytes: int = 8 * 1024
    max_query_bytes: int = 32 * 1024

    def __post_init__(self) -> None:
        if self.max_answer_bytes <= 0:
            raise ValueError("max_answer_bytes must be positive")
        if self.max_metadata_bytes <= 0:
            raise ValueError("max_metadata_bytes must be positive")
        if self.max_query_bytes <= 0:
            raise ValueError("max_query_bytes must be positive")

    def rejection_reason(
        self,
        *,
        answer: str,
        normalized_query: str,
        metadata: object,
    ) -> CacheSizeReason | None:
        if len(answer.encode("utf-8")) > self.max_answer_bytes:
            return "answer_too_large"
        if len(normalized_query.encode("utf-8")) > self.max_query_bytes:
            return "query_too_large"
        metadata_json = json.dumps(
            metadata.to_dict() if metadata is not None else {},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        if len(metadata_json.encode("utf-8")) > self.max_metadata_bytes:
            return "metadata_too_large"
        return None


@dataclass(frozen=True)
class CacheControlPolicy:
    """Configured TTL policy for each supported freshness class."""

    stable_ttl: timedelta = timedelta(days=30)
    semi_dynamic_ttl: timedelta = timedelta(hours=24)
    dynamic_ttl: timedelta | None = None
    allow_dynamic_entries: bool = False

    def __post_init__(self) -> None:
        if self.stable_ttl <= timedelta(0):
            raise ValueError("stable_ttl must be positive")
        if self.semi_dynamic_ttl <= timedelta(0):
            raise ValueError("semi_dynamic_ttl must be positive")
        if self.dynamic_ttl is not None and self.dynamic_ttl <= timedelta(0):
            raise ValueError("dynamic_ttl must be positive when configured")
        if self.allow_dynamic_entries and self.dynamic_ttl is None:
            raise ValueError(
                "dynamic_ttl is required when dynamic entries are allowed"
            )

    def ttl_for(self, freshness_class: TemporalClass) -> timedelta | None:
        """Return the configured TTL, or None when the class is not cacheable."""
        if freshness_class == "stable":
            return self.stable_ttl
        if freshness_class == "semi_dynamic":
            return self.semi_dynamic_ttl
        if freshness_class == "dynamic":
            return self.dynamic_ttl if self.allow_dynamic_entries else None
        raise ValueError(f"unsupported freshness class: {freshness_class}")


@dataclass(frozen=True)
class CacheControlResult:
    """Explain whether an entry may proceed to safety evaluation."""

    reusable: bool
    reason: CacheControlReason


def evaluate_cache_control(
    freshness_class: TemporalClass,
    ttl_expires_at: datetime | None,
    *,
    now: datetime | None = None,
    policy: CacheControlPolicy | None = None,
) -> CacheControlResult:
    """Apply policy and expiration rules without making a safety decision."""
    active_policy = policy or CacheControlPolicy()
    if freshness_class == "dynamic" and not active_policy.allow_dynamic_entries:
        return CacheControlResult(False, "dynamic_entries_disabled")
    if active_policy.ttl_for(freshness_class) is None:
        return CacheControlResult(False, "dynamic_entries_disabled")
    if ttl_expires_at is None:
        return CacheControlResult(False, "missing_expiration")
    if ttl_expires_at.tzinfo is None or ttl_expires_at.utcoffset() is None:
        return CacheControlResult(False, "invalid_expiration")

    comparison_time = now or datetime.now(timezone.utc)
    if comparison_time.tzinfo is None or comparison_time.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if comparison_time >= ttl_expires_at:
        return CacheControlResult(False, "expired")
    return CacheControlResult(True, "fresh")
