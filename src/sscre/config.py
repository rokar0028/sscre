import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from sscre.cache_controls import CacheControlPolicy, CacheSizeLimits


def _environment_bool(name: str, default: str) -> bool:
    value = os.getenv(name, default).lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value == "true"


@dataclass(frozen=True)
class Settings:
    database_url: str | None = None
    semantic_enabled: bool = True
    semantic_strategy: Literal["B", "C"] = "B"
    semantic_top_k: int = 5
    semantic_similarity_threshold: float = 0.95
    stable_ttl_seconds: int = 30 * 24 * 60 * 60
    semi_dynamic_ttl_seconds: int = 24 * 60 * 60
    dynamic_ttl_seconds: int | None = None
    allow_dynamic_entries: bool = False
    max_answer_bytes: int = 64 * 1024
    max_metadata_bytes: int = 8 * 1024
    max_query_bytes: int = 32 * 1024
    max_cache_entries: int = 10_000
    max_cache_bytes: int = 100_000_000

    def __post_init__(self) -> None:
        if self.semantic_strategy not in {"B", "C"}:
            raise ValueError("semantic_strategy must be B or C")
        if self.semantic_top_k <= 0:
            raise ValueError("semantic_top_k must be positive")
        if not -1.0 <= self.semantic_similarity_threshold <= 1.0:
            raise ValueError(
                "semantic_similarity_threshold must be between -1 and 1"
            )
        if self.stable_ttl_seconds <= 0:
            raise ValueError("stable_ttl_seconds must be positive")
        if self.semi_dynamic_ttl_seconds <= 0:
            raise ValueError("semi_dynamic_ttl_seconds must be positive")
        if self.dynamic_ttl_seconds is not None and self.dynamic_ttl_seconds <= 0:
            raise ValueError("dynamic_ttl_seconds must be positive")
        self.cache_control_policy()
        self.cache_size_limits()
        if self.max_cache_entries <= 0:
            raise ValueError("max_cache_entries must be positive")
        if self.max_cache_bytes <= 0:
            raise ValueError("max_cache_bytes must be positive")

    def cache_control_policy(self) -> CacheControlPolicy:
        return CacheControlPolicy(
            stable_ttl=timedelta(seconds=self.stable_ttl_seconds),
            semi_dynamic_ttl=timedelta(seconds=self.semi_dynamic_ttl_seconds),
            dynamic_ttl=(
                timedelta(seconds=self.dynamic_ttl_seconds)
                if self.dynamic_ttl_seconds is not None
                else None
            ),
            allow_dynamic_entries=self.allow_dynamic_entries,
        )

    def cache_size_limits(self) -> CacheSizeLimits:
        return CacheSizeLimits(
            max_answer_bytes=self.max_answer_bytes,
            max_metadata_bytes=self.max_metadata_bytes,
            max_query_bytes=self.max_query_bytes,
        )

    @classmethod
    def from_environment(cls) -> "Settings":
        raw_enabled = os.getenv("SSCRE_SEMANTIC_ENABLED", "true").lower()
        if raw_enabled not in {"true", "false"}:
            raise ValueError("SSCRE_SEMANTIC_ENABLED must be true or false")
        return cls(
            database_url=os.getenv("SSCRE_DATABASE_URL"),
            semantic_enabled=raw_enabled == "true",
            semantic_strategy=os.getenv("SSCRE_SEMANTIC_STRATEGY", "B"),
            semantic_top_k=int(os.getenv("SSCRE_SEMANTIC_TOP_K", "5")),
            semantic_similarity_threshold=float(
                os.getenv("SSCRE_SEMANTIC_SIMILARITY_THRESHOLD", "0.95")
            ),
            stable_ttl_seconds=int(
                os.getenv("SSCRE_CACHE_STABLE_TTL_SECONDS", str(30 * 24 * 60 * 60))
            ),
            semi_dynamic_ttl_seconds=int(
                os.getenv("SSCRE_CACHE_SEMI_DYNAMIC_TTL_SECONDS", str(24 * 60 * 60))
            ),
            dynamic_ttl_seconds=(
                int(value)
                if (value := os.getenv("SSCRE_CACHE_DYNAMIC_TTL_SECONDS"))
                else None
            ),
            allow_dynamic_entries=_environment_bool(
                "SSCRE_CACHE_ALLOW_DYNAMIC_ENTRIES",
                "false",
            ),
            max_answer_bytes=int(
                os.getenv("SSCRE_CACHE_MAX_ANSWER_BYTES", str(64 * 1024))
            ),
            max_metadata_bytes=int(
                os.getenv("SSCRE_CACHE_MAX_METADATA_BYTES", str(8 * 1024))
            ),
            max_query_bytes=int(
                os.getenv("SSCRE_CACHE_MAX_QUERY_BYTES", str(32 * 1024))
            ),
            max_cache_entries=int(
                os.getenv("SSCRE_CACHE_MAX_ENTRIES", "10000")
            ),
            max_cache_bytes=int(
                os.getenv("SSCRE_CACHE_MAX_BYTES", "100000000")
            ),
        )
