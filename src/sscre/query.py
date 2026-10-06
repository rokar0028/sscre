import hashlib
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from sscre.metadata import extract_metadata
from sscre.metrics import RequestMetrics
from sscre.safety import QueryMetadata

MAX_QUERY_LENGTH = 8000


def normalize_query(raw_query: str) -> str:
    """Trim a query and collapse all runs of whitespace to one space."""
    normalized = re.sub(r"\s+", " ", raw_query.strip())
    if not normalized:
        raise ValueError("query must not be empty")
    return normalized


def hash_query(normalized_query: str) -> str:
    """Return the SHA-256 cache key for a normalized query."""
    return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)

    @field_validator("query")
    @classmethod
    def normalize_and_validate_query(cls, value: str) -> str:
        return normalize_query(value)


class QueryPreprocessResponse(BaseModel):
    normalized_query: str
    query_hash: str
    metadata: QueryMetadata = QueryMetadata()


class QueryResponse(BaseModel):
    """Public query outcome.

    ``decision`` uses the safety vocabulary only: ``SAFE`` means the cached
    answer was served; ``UNSAFE`` and ``UNCERTAIN`` mean generation was used
    instead. Only ``SAFE`` responses include ``selected_candidate_query_hash``.
    See ``docs/phase-2/SAFETY_EVALUATION_CONTRACT_v1.md``.

    ``candidate_traces`` uses the boundary serializer (``null`` when no traces
    were collected). See ``docs/phase-2/SERIALIZATION_BOUNDARY_v1.md``.
    """

    answer: str
    source: Literal["cache", "generated"]
    strategy: Literal["exact", "semantic", "generated"]
    decision: Literal["SAFE", "UNSAFE", "UNCERTAIN"]
    similarity: float | None = Field(default=None, ge=-1, le=1)
    selected_candidate_query_hash: str | None = None
    reason: str | None = None
    freshness_class: Literal["stable", "semi_dynamic", "dynamic"] | None = None
    cache_control_reason: str | None = None
    candidate_traces: list[dict[str, object]] | None = None
    metrics: RequestMetrics

    @model_validator(mode="after")
    def selection_matches_decision(self) -> "QueryResponse":
        if self.decision == "SAFE":
            if self.selected_candidate_query_hash is None:
                raise ValueError("SAFE response requires a selected candidate")
            if self.similarity is None:
                raise ValueError("SAFE response requires a similarity")
        else:
            if self.selected_candidate_query_hash is not None:
                raise ValueError("non-SAFE response cannot select a candidate")
            if self.similarity is not None:
                raise ValueError("non-SAFE response cannot include a similarity")
        return self


def preprocess_query(request: QueryRequest) -> QueryPreprocessResponse:
    return QueryPreprocessResponse(
        normalized_query=request.query,
        query_hash=hash_query(request.query),
        metadata=extract_metadata(request.query),
    )
