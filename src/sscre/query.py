import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sscre.metadata import extract_metadata
from sscre.metrics import RequestMetrics
from sscre.safety import QueryMetadata

MAX_QUERY_LENGTH = 8000
CACHE_KEY_VERSION = "v2"
LEGACY_UNSCOPED_TENANT = "legacy-unscoped"
LEGACY_UNSCOPED_NAMESPACE = "legacy-unscoped"
MAX_SCOPE_PART_LENGTH = 128


@dataclass(frozen=True)
class CacheScope:
    tenant_id: str
    namespace_id: str


class MissingCacheScopeError(ValueError):
    """Raised when a cache operation requires tenant and namespace predicates."""


def resolve_operation_scope(
    *,
    tenant_id: str | None,
    namespace_id: str | None,
    require_predicates: bool,
    operation: str,
) -> CacheScope | None:
    """Return a normalized scope or None when predicates are optional and absent."""
    if tenant_id is None and namespace_id is None:
        if require_predicates:
            raise MissingCacheScopeError(
                f"{operation} requires tenant_id and namespace_id"
            )
        return None
    if tenant_id is None or namespace_id is None:
        raise MissingCacheScopeError(
            f"{operation} requires both tenant_id and namespace_id"
        )
    return CacheScope(
        normalize_scope_part(tenant_id, "tenant_id"),
        normalize_scope_part(namespace_id, "namespace_id"),
    )


def entry_matches_scope(
    tenant_id: str,
    namespace_id: str,
    scope: CacheScope,
) -> bool:
    return tenant_id == scope.tenant_id and namespace_id == scope.namespace_id


def normalize_scope_part(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if len(normalized) > MAX_SCOPE_PART_LENGTH:
        raise ValueError(f"{field_name} must be at most {MAX_SCOPE_PART_LENGTH} characters")
    if "\n" in normalized or "\r" in normalized:
        raise ValueError(f"{field_name} must not contain newlines")
    return normalized


def normalize_query(raw_query: str) -> str:
    """Trim a query and collapse all runs of whitespace to one space."""
    normalized = re.sub(r"\s+", " ", raw_query.strip())
    if not normalized:
        raise ValueError("query must not be empty")
    return normalized


def hash_query(normalized_query: str) -> str:
    """Return the v1 content fingerprint (normalized query only)."""
    return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()


def content_query_hash(normalized_query: str) -> str:
    """Diagnostic fingerprint for the normalized query text."""
    return hash_query(normalized_query)


def scoped_cache_key(scope: CacheScope, normalized_query: str) -> str:
    """Return the versioned storage key for exact lookup and insertion."""
    tenant_id = normalize_scope_part(scope.tenant_id, "tenant_id")
    namespace_id = normalize_scope_part(scope.namespace_id, "namespace_id")
    payload = (
        f"{CACHE_KEY_VERSION}\n{tenant_id}\n{namespace_id}\n{normalized_query}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)

    @field_validator("query")
    @classmethod
    def normalize_and_validate_query(cls, value: str) -> str:
        return normalize_query(value)


class QueryPreprocessResponse(BaseModel):
    normalized_query: str
    query_hash: str
    content_query_hash: str
    tenant_id: str
    namespace_id: str
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


def trusted_local_scope() -> CacheScope:
    from sscre.api_auth import DEFAULT_NAMESPACE, TRUSTED_LOCAL_TENANT

    return CacheScope(
        tenant_id=TRUSTED_LOCAL_TENANT,
        namespace_id=DEFAULT_NAMESPACE,
    )


def storage_query_hash(
    normalized_query: str,
    scope: CacheScope | None = None,
) -> str:
    """Return the repository storage key for a normalized query and scope."""
    resolved = scope or trusted_local_scope()
    return scoped_cache_key(resolved, normalized_query)


def preprocess_query(
    request: QueryRequest,
    scope: CacheScope,
) -> QueryPreprocessResponse:
    normalized = request.query
    tenant_id = normalize_scope_part(scope.tenant_id, "tenant_id")
    namespace_id = normalize_scope_part(scope.namespace_id, "namespace_id")
    content_hash = content_query_hash(normalized)
    return QueryPreprocessResponse(
        normalized_query=normalized,
        query_hash=scoped_cache_key(
            CacheScope(tenant_id, namespace_id),
            normalized,
        ),
        content_query_hash=content_hash,
        tenant_id=tenant_id,
        namespace_id=namespace_id,
        metadata=extract_metadata(normalized),
    )
