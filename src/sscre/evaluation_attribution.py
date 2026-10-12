"""Candidate-level reuse attribution for evaluation replay."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from sscre.benchmark import BenchmarkRecord
from sscre.query import hash_query, normalize_query

RequestDirection = Literal["a_to_b", "b_to_a"]


@dataclass(frozen=True)
class ServedCandidateProvenance:
    """Identity of the cache candidate actually served on a directed request."""

    candidate_query_hash: str
    candidate_normalized_query: str
    candidate_answer_hash: str
    source_pair_id: str | None
    source_direction: RequestDirection | None
    current_query_hash: str
    current_normalized_query: str

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_query_hash": self.candidate_query_hash,
            "candidate_normalized_query": self.candidate_normalized_query,
            "candidate_answer_hash": self.candidate_answer_hash,
            "source_pair_id": self.source_pair_id,
            "source_direction": self.source_direction,
            "current_query_hash": self.current_query_hash,
            "current_normalized_query": self.current_normalized_query,
        }


@dataclass(frozen=True)
class AttributedReuseOutcome:
    false_positive: int
    safe_reuse_hit: int
    unlabeled_candidate_reuse: int
    provenance: ServedCandidateProvenance | None


class DirectedPairReuseIndex:
    """Map directed (query_a, query_b) identities to reviewed benchmark records."""

    def __init__(self) -> None:
        self._by_edge: dict[tuple[str, str], BenchmarkRecord] = {}
        self._ambiguous_edges: set[tuple[str, str]] = set()

    @classmethod
    def from_records(cls, records: list[BenchmarkRecord]) -> DirectedPairReuseIndex:
        index = cls()
        for record in records:
            candidate_hash = hash_query(normalize_query(record.query_a))
            current_hash = hash_query(normalize_query(record.query_b))
            key = (candidate_hash, current_hash)
            existing = index._by_edge.get(key)
            if existing is not None and existing.id != record.id:
                index._ambiguous_edges.add(key)
            else:
                index._by_edge[key] = record
        return index

    def lookup(self, candidate_query_hash: str, current_query_hash: str) -> BenchmarkRecord | None:
        key = (candidate_query_hash, current_query_hash)
        if key in self._ambiguous_edges:
            return None
        return self._by_edge.get(key)


def attribute_served_reuse_outcome(
    *,
    direction: RequestDirection,
    served_reuse: bool,
    candidate_normalized_query: str,
    candidate_answer_hash: str,
    current_normalized_query: str,
    pair_index: DirectedPairReuseIndex,
    source_pair_id: str | None = None,
    source_direction: RequestDirection | None = None,
) -> AttributedReuseOutcome:
    """Score reuse against the served candidate/current relation when labeled."""
    if direction != "b_to_a" or not served_reuse:
        return AttributedReuseOutcome(0, 0, 0, None)

    candidate_hash = hash_query(candidate_normalized_query)
    current_hash = hash_query(current_normalized_query)
    provenance = ServedCandidateProvenance(
        candidate_query_hash=candidate_hash,
        candidate_normalized_query=candidate_normalized_query,
        candidate_answer_hash=candidate_answer_hash,
        source_pair_id=source_pair_id,
        source_direction=source_direction,
        current_query_hash=current_hash,
        current_normalized_query=current_normalized_query,
    )

    grounding = pair_index.lookup(candidate_hash, current_hash)
    if grounding is None:
        return AttributedReuseOutcome(0, 0, 1, provenance)
    if grounding.reusable:
        return AttributedReuseOutcome(0, 1, 0, provenance)
    return AttributedReuseOutcome(1, 0, 0, provenance)


@dataclass(frozen=True)
class LabeledFalsePositiveRate:
    """Headline FPR over labeled b_to_a reuse (excludes unlabeled)."""

    value: float | None
    unavailable_reason: str | None
    labeled_reuse_hits: int


def labeled_false_positive_rate_details(
    unsafe_reuse_hits: int,
    safe_reuse_hits: int,
) -> LabeledFalsePositiveRate:
    labeled = safe_reuse_hits + unsafe_reuse_hits
    if labeled == 0:
        return LabeledFalsePositiveRate(
            value=None,
            unavailable_reason="no_labeled_reuse_hits",
            labeled_reuse_hits=0,
        )
    return LabeledFalsePositiveRate(
        value=unsafe_reuse_hits / labeled,
        unavailable_reason=None,
        labeled_reuse_hits=labeled,
    )


def labeled_false_positive_rate(
    unsafe_reuse_hits: int,
    safe_reuse_hits: int,
) -> float:
    """Constraint/selection FPR; unknown labeled denominator is ineligible (inf)."""
    details = labeled_false_positive_rate_details(
        unsafe_reuse_hits,
        safe_reuse_hits,
    )
    if details.value is None:
        return math.inf
    return details.value


def false_positive_rate_for_constraint(
    unsafe_reuse_hits: int,
    safe_reuse_hits: int,
    reported_rate: float | None,
) -> float:
    """Use reported rate when present; unknown rate is ineligible (inf)."""
    if reported_rate is not None:
        return reported_rate
    return labeled_false_positive_rate(unsafe_reuse_hits, safe_reuse_hits)
