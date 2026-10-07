"""OpenAI-compatible remote embedding adapter."""

from collections.abc import Mapping
from dataclasses import replace
from math import isfinite
from time import perf_counter

from sscre.embedding import (
    EmbeddingConfig,
    EmbeddingProviderError,
    EmbeddingResult,
    validate_embedding_result,
    validate_embedding_text,
)
from sscre.provider_config import RealProviderConfig
from sscre.remote_llm import (
    JSONTransport,
    RemoteLLMError,
    UrllibJSONTransport,
    _http_error_category,
    _usage_count,
)
from sscre.retry import run_with_bounded_retries


MAX_EMBEDDING_TEXT_BYTES = 32 * 1024


class RemoteEmbeddingError(EmbeddingProviderError):
    """A bounded, non-sensitive remote embedding error."""

    def __init__(
        self,
        category: str,
        message: str = "remote embedding failed",
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retry_after_seconds = retry_after_seconds


class OpenAICompatibleEmbeddingClient:
    """Single-attempt client for providers exposing embeddings shape."""

    def __init__(
        self,
        config: RealProviderConfig,
        *,
        transport: JSONTransport | None = None,
    ) -> None:
        if not config.credential_configured:
            raise ValueError("provider credential is required for embeddings")
        self._provider_config = config
        self._embedding_config = EmbeddingConfig(
            model_name=config.embedding_model,
            dimension=config.embedding_dimension,
        )
        self._transport = transport or UrllibJSONTransport()

    @property
    def config(self) -> EmbeddingConfig:
        return self._embedding_config

    def embed(self, text: str) -> EmbeddingResult:
        text = validate_embedding_text(text)
        if len(text.encode("utf-8")) > MAX_EMBEDDING_TEXT_BYTES:
            raise ValueError("embedding text exceeds size limit")

        started_at = perf_counter()
        result, retry_count = run_with_bounded_retries(
            lambda: self._embed_once(text),
            retry_limit=self._provider_config.retry_limit,
            min_backoff_seconds=self._provider_config.min_backoff_seconds,
            max_backoff_seconds=self._provider_config.max_backoff_seconds,
            max_elapsed_seconds=self._provider_config.max_retry_elapsed_seconds,
        )
        return replace(
            result,
            latency_ms=int((perf_counter() - started_at) * 1000),
            attempts=retry_count + 1,
            retry_count=retry_count,
        )

    def _embed_once(self, text: str) -> EmbeddingResult:
        started_at = perf_counter()
        try:
            status, response = self._transport.post(
                self._embedding_url(),
                headers={
                    "Authorization": f"Bearer {self._provider_config.credential}"
                },
                payload={
                    "model": self._provider_config.embedding_model,
                    "input": text,
                },
                timeout_seconds=self._provider_config.embedding_timeout_seconds,
            )
        except Exception as exc:
            category = getattr(exc, "category", "transient_provider")
            retry_after_seconds = getattr(exc, "retry_after_seconds", None)
            if isinstance(category, str):
                raise RemoteEmbeddingError(
                    category,
                    retry_after_seconds=retry_after_seconds,
                ) from exc
            raise RemoteEmbeddingError("transient_provider") from exc

        if status < 200 or status >= 300:
            raise RemoteEmbeddingError(_http_error_category(status))

        vector = self._parse_vector(response)
        response_model = response.get("model")
        if response_model is not None and response_model != self.config.model_name:
            raise RemoteEmbeddingError("malformed_response")
        usage = response.get("usage")
        try:
            input_tokens, usage_source = _usage_count(
                usage,
                "prompt_tokens",
                fallback_text=text,
            )
        except RemoteLLMError as exc:
            raise RemoteEmbeddingError(exc.category) from exc
        result = EmbeddingResult(
            vector=vector,
            model_name=self.config.model_name,
            input_tokens=input_tokens,
            latency_ms=int((perf_counter() - started_at) * 1000),
            provider_name=self._provider_config.provider,
            usage_source=usage_source,
        )
        try:
            validate_embedding_result(result, self.config)
        except Exception as exc:
            raise RemoteEmbeddingError("malformed_response") from exc
        return result

    def _embedding_url(self) -> str:
        return f"{self._provider_config.endpoint.rstrip('/')}/embeddings"

    @staticmethod
    def _parse_vector(response: Mapping[str, object]) -> tuple[float, ...]:
        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise RemoteEmbeddingError("malformed_response")
        first = data[0]
        if not isinstance(first, Mapping):
            raise RemoteEmbeddingError("malformed_response")
        raw_vector = first.get("embedding")
        if not isinstance(raw_vector, list) or not raw_vector:
            raise RemoteEmbeddingError("malformed_response")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
            for value in raw_vector
        ):
            raise RemoteEmbeddingError("malformed_response")
        return tuple(float(value) for value in raw_vector)
