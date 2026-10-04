import hashlib
import re

from pydantic import BaseModel, Field, field_validator

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


def preprocess_query(request: QueryRequest) -> QueryPreprocessResponse:
    return QueryPreprocessResponse(
        normalized_query=request.query,
        query_hash=hash_query(request.query),
    )
