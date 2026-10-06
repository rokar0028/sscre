"""Canonical answer records for content-addressable cache storage.

Canonical answers contain reusable answer content and bounded provenance. Query
specific metadata stays on ``CacheEntry`` because two queries may share an
identical answer body while having different compatibility or freshness
requirements. Sharing a canonical body therefore never implies sharing a
reusable cache entry.

Raw prompts, hidden reasoning, credentials, and evaluation transcripts are
intentionally not fields of this record. A canonical answer is owned by its
cache-entry references; its body can be deleted after the final reference is
evicted.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

PreferenceLabel = Literal["A", "B", "tie"]
CorrectnessLabel = Literal["correct", "incorrect", "uncertain"]
ValidationStatus = Literal["auto", "human"]


def hash_answer(answer: str) -> str:
    """Return the stable UTF-8 SHA-256 identity of answer content."""
    if not answer:
        raise ValueError("answer must not be empty")
    return hashlib.sha256(answer.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CanonicalAnswer:
    """Answer body and bounded provenance shared by cache-entry references."""

    answer_hash: str
    answer: str
    model_source: str | None = None
    preference_label: PreferenceLabel | None = None
    correctness_label: CorrectnessLabel | None = None
    validation_status: ValidationStatus | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if self.answer_hash != hash_answer(self.answer):
            raise ValueError("answer_hash does not match answer content")
        if self.model_source is not None and not self.model_source.strip():
            raise ValueError("model_source must not be blank")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")


def canonical_answer(answer: str, **kwargs: object) -> CanonicalAnswer:
    """Build a canonical record from answer content without raw prompt data."""
    return CanonicalAnswer(
        answer_hash=hash_answer(answer),
        answer=answer,
        **kwargs,
    )
