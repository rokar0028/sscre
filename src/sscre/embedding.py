import hashlib
from dataclasses import dataclass
from math import isfinite
from collections.abc import Mapping, Sequence
from typing import Literal, Protocol


class EmbeddingClientError(RuntimeError):
    """Base error for embedding-client failures."""


class EmbeddingProviderError(EmbeddingClientError):
    """Raised when an embedding provider cannot create an embedding."""


class EmbeddingValidationError(EmbeddingClientError, ValueError):
    """Raised when an embedding result does not match the configured contract."""


@dataclass(frozen=True)
class EmbeddingConfig:
    """Configuration shared by an embedding client and its consumers."""

    model_name: str
    dimension: int

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name must not be empty")
        if self.dimension <= 0:
            raise ValueError("dimension must be positive")


@dataclass(frozen=True)
class EmbeddingResult:
    """Embedding output plus accounting data for one input query."""

    vector: tuple[float, ...]
    model_name: str
    input_tokens: int
    latency_ms: int
    provider_name: str = "synthetic"
    usage_source: Literal["provider_reported", "estimated"] = "estimated"
    attempts: int = 1
    retry_count: int = 0

    def __post_init__(self) -> None:
        if not self.vector:
            raise EmbeddingValidationError("embedding vector must not be empty")
        if any(not isfinite(value) for value in self.vector):
            raise EmbeddingValidationError(
                "embedding vector values must be finite"
            )
        if not self.model_name.strip():
            raise EmbeddingValidationError("embedding model_name must not be empty")
        if self.input_tokens < 0:
            raise EmbeddingValidationError("input_tokens must not be negative")
        if self.latency_ms < 0:
            raise EmbeddingValidationError("latency_ms must not be negative")
        if not isinstance(self.provider_name, str) or not self.provider_name.strip():
            raise EmbeddingValidationError("embedding provider_name must not be empty")
        if self.usage_source not in {"provider_reported", "estimated"}:
            raise EmbeddingValidationError("invalid embedding usage_source")
        if (
            not isinstance(self.attempts, int)
            or isinstance(self.attempts, bool)
            or self.attempts <= 0
            or not isinstance(self.retry_count, int)
            or isinstance(self.retry_count, bool)
            or self.retry_count < 0
            or self.retry_count != self.attempts - 1
        ):
            raise EmbeddingValidationError("invalid embedding retry metadata")


class EmbeddingClient(Protocol):
    """Provider-independent interface for generating query embeddings."""

    @property
    def config(self) -> EmbeddingConfig:
        """Return the model and vector dimension used by this client."""
        ...

    def embed(self, text: str) -> EmbeddingResult:
        """Embed text or raise an EmbeddingClientError."""
        ...


def validate_embedding_text(text: str) -> str:
    """Reject empty input before making a provider request."""

    if not isinstance(text, str) or not text.strip():
        raise EmbeddingValidationError("embedding text must not be empty")
    return text


def validate_embedding_result(
    result: EmbeddingResult,
    config: EmbeddingConfig,
) -> None:
    """Validate provider output against the configured model and dimension."""

    if result.model_name != config.model_name:
        raise EmbeddingValidationError(
            "embedding model does not match configured model"
        )
    if len(result.vector) != config.dimension:
        raise EmbeddingValidationError(
            "embedding dimension does not match configured dimension"
        )


class FakeEmbeddingClient:
    """Deterministic embedding client for tests and local experiments."""

    def __init__(
        self,
        *,
        config: EmbeddingConfig | None = None,
        vectors: Mapping[str, Sequence[float]] | None = None,
        input_tokens: int | None = None,
        latency_ms: int = 0,
        should_fail: bool = False,
    ) -> None:
        self._config = config or EmbeddingConfig(
            model_name="fake-embedding",
            dimension=8,
        )
        self._vectors = vectors or {}
        self._input_tokens = input_tokens
        self._latency_ms = latency_ms
        self._should_fail = should_fail

        if input_tokens is not None and input_tokens < 0:
            raise ValueError("input_tokens must not be negative")
        if latency_ms < 0:
            raise ValueError("latency_ms must not be negative")

    @property
    def config(self) -> EmbeddingConfig:
        return self._config

    def embed(self, text: str) -> EmbeddingResult:
        text = validate_embedding_text(text)
        if self._should_fail:
            raise EmbeddingProviderError("fake embedding provider failed")

        configured_vector = self._vectors.get(text)
        vector = (
            tuple(configured_vector)
            if configured_vector is not None
            else self._deterministic_vector(text)
        )
        result = EmbeddingResult(
            vector=vector,
            model_name=self._config.model_name,
            input_tokens=(
                self._input_tokens
                if self._input_tokens is not None
                else len(text.split())
            ),
            latency_ms=self._latency_ms,
            provider_name="synthetic",
            usage_source="estimated",
        )
        validate_embedding_result(result, self._config)
        return result

    def _deterministic_vector(self, text: str) -> tuple[float, ...]:
        return tuple(
            (
                int.from_bytes(
                    hashlib.sha256(f"{text}:{index}".encode()).digest()[:8],
                    "big",
                )
                / ((1 << 64) - 1)
            )
            * 2
            - 1
            for index in range(self._config.dimension)
        )
