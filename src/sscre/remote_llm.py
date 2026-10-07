"""OpenAI-compatible remote generation adapter."""

from collections.abc import Mapping
from dataclasses import replace
import json
from time import perf_counter
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sscre.llm import LLMResult
from sscre.provider_config import RealProviderConfig
from sscre.retry import run_with_bounded_retries


MAX_QUERY_BYTES = 32 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class RemoteLLMError(RuntimeError):
    """A bounded, non-sensitive remote generation error."""

    def __init__(
        self,
        category: str,
        message: str = "remote generation failed",
        *,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message)
        self.category = category
        self.retry_after_seconds = retry_after_seconds


class JSONTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> tuple[int, Mapping[str, object]]:
        """Perform one JSON request without applying retries."""
        ...


class UrllibJSONTransport:
    """Small standard-library transport with bounded response reads."""

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> tuple[int, Mapping[str, object]]:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                **headers,
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                status = int(response.status)
        except HTTPError as exc:
            raise RemoteLLMError(
                _http_error_category(exc.code),
                retry_after_seconds=_retry_after_seconds(exc.headers),
            ) from exc
        except TimeoutError as exc:
            raise RemoteLLMError("timeout") from exc
        except URLError as exc:
            raise RemoteLLMError("transient_provider") from exc
        except OSError as exc:
            raise RemoteLLMError("transient_provider") from exc

        if len(raw) > MAX_RESPONSE_BYTES:
            raise RemoteLLMError("malformed_response")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteLLMError("malformed_response") from exc
        if not isinstance(decoded, dict):
            raise RemoteLLMError("malformed_response")
        return status, decoded


def _http_error_category(status_code: int) -> str:
    if status_code in {401}:
        return "authentication"
    if status_code in {403}:
        return "authorization"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code <= 599:
        return "transient_provider"
    return "permanent_provider"


def _retry_after_seconds(headers: object) -> float | None:
    if headers is None or not hasattr(headers, "get"):
        return None
    raw_value = headers.get("Retry-After")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


_RESERVED_GENERATION_PAYLOAD_KEYS = frozenset({"model", "messages"})


def merge_provider_request_parameters(
    base: Mapping[str, object],
    config: RealProviderConfig,
    *,
    reserved_keys: frozenset[str] = _RESERVED_GENERATION_PAYLOAD_KEYS,
) -> dict[str, object]:
    """Attach allow-listed request parameters without overriding core fields."""
    merged = dict(base)
    for key, value in config.request_parameters:
        normalized = key.strip().lower()
        if normalized in reserved_keys:
            raise ValueError("request parameters must not override reserved fields")
        merged[key] = value
    return merged


def _usage_count(
    usage: object,
    key: str,
    *,
    fallback_text: str,
) -> tuple[int, str]:
    if isinstance(usage, Mapping):
        if key in usage:
            value = usage[key]
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value, "provider_reported"
            raise RemoteLLMError("malformed_response")
    return len(fallback_text.split()), "estimated"


class OpenAICompatibleLLMClient:
    """Single-attempt client for providers exposing chat-completions shape."""

    def __init__(
        self,
        config: RealProviderConfig,
        *,
        transport: JSONTransport | None = None,
    ) -> None:
        if not config.credential_configured:
            raise ValueError("provider credential is required for remote generation")
        self.config = config
        self._transport = transport or UrllibJSONTransport()

    def generate(self, query: str) -> LLMResult:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("generation query must not be empty")
        if len(query.encode("utf-8")) > MAX_QUERY_BYTES:
            raise ValueError("generation query exceeds size limit")

        started_at = perf_counter()
        result, retry_count = run_with_bounded_retries(
            lambda: self._generate_once(query),
            retry_limit=self.config.retry_limit,
            min_backoff_seconds=self.config.min_backoff_seconds,
            max_backoff_seconds=self.config.max_backoff_seconds,
            max_elapsed_seconds=self.config.max_retry_elapsed_seconds,
        )
        return replace(
            result,
            latency_ms=int((perf_counter() - started_at) * 1000),
            attempts=retry_count + 1,
            retry_count=retry_count,
        )

    def _generate_once(self, query: str) -> LLMResult:
        started_at = perf_counter()
        try:
            status, response = self._transport.post(
                self._completion_url(),
                headers={"Authorization": f"Bearer {self.config.credential}"},
                payload=merge_provider_request_parameters(
                    {
                        "model": self.config.generation_model,
                        "messages": [{"role": "user", "content": query}],
                    },
                    self.config,
                ),
                timeout_seconds=self.config.generation_timeout_seconds,
            )
        except RemoteLLMError:
            raise
        except Exception as exc:
            raise RemoteLLMError("transient_provider") from exc

        if status < 200 or status >= 300:
            raise RemoteLLMError(_http_error_category(status))
        text = self._parse_text(response)
        usage = response.get("usage")
        input_tokens, input_source = _usage_count(
            usage,
            "prompt_tokens",
            fallback_text=query,
        )
        output_tokens, output_source = _usage_count(
            usage,
            "completion_tokens",
            fallback_text=text,
        )
        usage_source = (
            "provider_reported"
            if input_source == output_source == "provider_reported"
            else "estimated"
        )
        latency_ms = int((perf_counter() - started_at) * 1000)
        return LLMResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            provider_name=self.config.provider,
            model_name=self.config.generation_model,
            usage_source=usage_source,
        )

    def _completion_url(self) -> str:
        return f"{self.config.endpoint.rstrip('/')}/chat/completions"

    @staticmethod
    def _parse_text(response: Mapping[str, object]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RemoteLLMError("malformed_response")
        first = choices[0]
        if not isinstance(first, Mapping):
            raise RemoteLLMError("malformed_response")
        message = first.get("message")
        if not isinstance(message, Mapping):
            raise RemoteLLMError("malformed_response")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise RemoteLLMError("malformed_response")
        return text
