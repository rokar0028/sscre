"""Workstream 4 retry and provider failure test plan."""

import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import InMemoryExactCache
from sscre.embedding import EmbeddingConfig, EmbeddingResult
from sscre.llm import MockLLMClient
from sscre.provider_config import RealProviderConfig
from sscre.remote_embedding import OpenAICompatibleEmbeddingClient, RemoteEmbeddingError
from sscre.remote_llm import OpenAICompatibleLLMClient, RemoteLLMError


class FakeTransport:
    def __init__(self, status: int = 200, response: dict | None = None) -> None:
        self.status = status
        self.response = response or {
            "choices": [{"message": {"content": "remote answer"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        }
        self.calls: list[dict] = []

    def post(self, url, *, headers, payload, timeout_seconds):
        self.calls.append({"url": url, "timeout_seconds": timeout_seconds})
        return self.status, self.response


class FlakyTransport(FakeTransport):
    def __init__(self, failures: int, *, category: str = "transient_provider") -> None:
        super().__init__()
        self.failures = failures
        self.category = category

    def post(self, url, *, headers, payload, timeout_seconds):
        self.calls.append({"url": url})
        if self.failures:
            self.failures -= 1
            raise RemoteLLMError(self.category)
        return self.status, self.response


class RateLimitOnceTransport(FakeTransport):
    def post(self, url, *, headers, payload, timeout_seconds):
        self.calls.append({"url": url})
        if len(self.calls) == 1:
            raise RemoteLLMError("rate_limited", retry_after_seconds=10)
        return self.status, self.response


class AlwaysFailTransport(FakeTransport):
    def __init__(
        self,
        *,
        category: str = "transient_provider",
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__()
        self.category = category
        self.retry_after_seconds = retry_after_seconds

    def post(self, url, *, headers, payload, timeout_seconds):
        self.calls.append({"url": url})
        raise RemoteLLMError(
            self.category,
            retry_after_seconds=self.retry_after_seconds,
        )


def _config(**overrides) -> RealProviderConfig:
    values = {
        "provider": "test-provider",
        "endpoint": "https://api.example.test/v1",
        "generation_model": "generation-test",
        "embedding_model": "embedding-test",
        "embedding_dimension": 4,
        "request_timeout_seconds": 30,
        "generation_timeout_seconds": 25,
        "embedding_timeout_seconds": 5,
        "retry_limit": 0,
        "min_backoff_seconds": 0,
        "max_backoff_seconds": 1,
        "max_retry_elapsed_seconds": 5,
        "experiment_id": "experiment",
        "dataset_version": "dataset",
        "split": "development",
        "pricing_schedule_id": "prices",
        "credential": "credential-value",
    }
    values.update(overrides)
    return RealProviderConfig(**values)


def test_first_attempt_success_performs_no_retry() -> None:
    transport = FakeTransport()
    client = OpenAICompatibleLLMClient(_config(retry_limit=3), transport=transport)

    result = client.generate("query")

    assert result.retry_count == 0
    assert len(transport.calls) == 1


def test_retryable_transient_error_retries_within_configured_budget() -> None:
    transport = FlakyTransport(failures=1)
    client = OpenAICompatibleLLMClient(
        _config(retry_limit=2, min_backoff_seconds=0, max_backoff_seconds=0),
        transport=transport,
    )

    result = client.generate("query")

    assert result.text == "remote answer"
    assert result.retry_count == 1
    assert len(transport.calls) == 2


def test_rate_limit_response_records_bounded_rate_limit_event() -> None:
    transport = FakeTransport(status=429)
    with pytest.raises(RemoteLLMError) as exc_info:
        OpenAICompatibleLLMClient(_config(), transport=transport).generate("query")

    assert exc_info.value.category == "rate_limited"
    assert len(transport.calls) == 1


def test_rate_limit_response_retries_within_configured_budget() -> None:
    transport = RateLimitOnceTransport()
    client = OpenAICompatibleLLMClient(
        _config(
            request_timeout_seconds=60,
            retry_limit=1,
            min_backoff_seconds=0,
            max_backoff_seconds=2,
            max_retry_elapsed_seconds=30,
        ),
        transport=transport,
    )

    result = client.generate("query")

    assert result.retry_count == 1
    assert len(transport.calls) == 2


@pytest.mark.parametrize("status", [400])
def test_permanent_provider_error_does_not_retry(status: int) -> None:
    transport = FakeTransport(status=status)
    client = OpenAICompatibleLLMClient(_config(retry_limit=3), transport=transport)

    with pytest.raises(RemoteLLMError) as exc_info:
        client.generate("query")

    assert exc_info.value.category == "permanent_provider"
    assert len(transport.calls) == 1


@pytest.mark.parametrize("status", [401, 403])
def test_authentication_and_authorization_errors_do_not_retry(status: int) -> None:
    transport = FakeTransport(status=status)
    client = OpenAICompatibleLLMClient(_config(retry_limit=3), transport=transport)

    with pytest.raises(RemoteLLMError):
        client.generate("query")

    assert len(transport.calls) == 1


def test_malformed_provider_response_does_not_retry() -> None:
    transport = FakeTransport(response={"choices": []})
    client = OpenAICompatibleLLMClient(_config(retry_limit=3), transport=transport)

    with pytest.raises(RemoteLLMError) as exc_info:
        client.generate("query")

    assert exc_info.value.category == "malformed_response"
    assert len(transport.calls) == 1


def test_retry_after_cannot_exceed_remaining_request_budget() -> None:
    transport = AlwaysFailTransport(
        category="rate_limited",
        retry_after_seconds=10,
    )
    client = OpenAICompatibleLLMClient(
        _config(
            retry_limit=3,
            min_backoff_seconds=0,
            max_backoff_seconds=0.01,
            max_retry_elapsed_seconds=0.01,
        ),
        transport=transport,
    )

    with pytest.raises(RemoteLLMError) as exc_info:
        client.generate("query")

    assert exc_info.value.category == "rate_limited"
    assert len(transport.calls) == 1


def test_retry_exhaustion_returns_controlled_non_reusable_failure() -> None:
    transport = AlwaysFailTransport()
    client = OpenAICompatibleLLMClient(
        _config(retry_limit=2, min_backoff_seconds=0, max_backoff_seconds=0),
        transport=transport,
    )

    with pytest.raises(RemoteLLMError) as exc_info:
        client.generate("query")

    assert exc_info.value.category == "transient_provider"
    assert len(transport.calls) == 3


@pytest.mark.parametrize(
    ("client_factory", "method", "text"),
    [
        (OpenAICompatibleLLMClient, "generate", "query"),
        (OpenAICompatibleEmbeddingClient, "embed", "text"),
    ],
)
def test_timeout_does_not_return_partial_provider_result(
    client_factory,
    method: str,
    text: str,
) -> None:
    transport = AlwaysFailTransport(category="timeout")
    client = client_factory(_config(), transport=transport)

    with pytest.raises((RemoteLLMError, RemoteEmbeddingError)) as exc_info:
        getattr(client, method)(text)

    assert exc_info.value.category == "timeout"
    assert len(transport.calls) == 1


def test_retries_during_generation_do_not_cache_before_success() -> None:
    from sscre.cache import InMemoryExactCache
    from tests.test_provider_integration import CountingProviderEmbeddingClient

    transport = FlakyTransport(failures=1)
    llm = OpenAICompatibleLLMClient(
        _config(retry_limit=2, min_backoff_seconds=0, max_backoff_seconds=0),
        transport=transport,
    )
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            llm_client=llm,
            embedding_client=CountingProviderEmbeddingClient(),
            repository=cache,
            semantic_strategy="C",
        )
    )

    response = client.post(
        "/v1/query",
        json={"query": "retry before cache insert unique phrase"},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert len(transport.calls) == 2
    assert cache.storage_stats().entries == 1


def test_provider_generation_failure_does_not_produce_cache_hit() -> None:
    cache = InMemoryExactCache()
    model = MockLLMClient(should_fail=True)
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            semantic_enabled=False,
        )
    )

    first = client.post("/v1/query", json={"query": "provider generation failure"})

    assert first.status_code == 502
    assert first.json()["detail"] == "response generation failed"
    assert cache.storage_stats().entries == 0

    model.should_fail = False
    second = client.post("/v1/query", json={"query": "provider generation failure"})

    assert second.status_code == 200
    assert second.json()["source"] == "generated"


class RemoteEmbeddingFailureClient:
    config = EmbeddingConfig(model_name="embedding-test", dimension=4)

    def embed(self, text: str) -> EmbeddingResult:
        raise RemoteEmbeddingError("malformed_response")


def test_provider_embedding_failure_does_not_insert_unvalidated_cache_entry() -> None:
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=RemoteEmbeddingFailureClient(),
            semantic_strategy="C",
        )
    )

    response = client.post("/v1/query", json={"query": "embedding provider failure"})

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert response.json()["reason"] == "embedding_unavailable"
    assert cache.storage_stats().entries == 0
