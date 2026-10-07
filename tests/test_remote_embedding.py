import math

import pytest

from sscre.provider_config import RealProviderConfig
from sscre.remote_embedding import (
    OpenAICompatibleEmbeddingClient,
    RemoteEmbeddingError,
)


class FakeTransport:
    def __init__(self, status: int = 200, response: dict | None = None) -> None:
        self.status = status
        self.response = (
            response
            if response is not None
            else {
                "model": "embedding-test",
                "data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}],
                "usage": {"prompt_tokens": 4},
            }
        )
        self.calls: list[dict] = []

    def post(self, url, *, headers, payload, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.status, self.response


class FlakyTransport(FakeTransport):
    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures

    def post(self, url, *, headers, payload, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.failures:
            self.failures -= 1
            raise RemoteEmbeddingError("rate_limited", retry_after_seconds=0)
        return self.status, self.response


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


def test_remote_embedding_parses_vector_and_usage() -> None:
    transport = FakeTransport()
    client = OpenAICompatibleEmbeddingClient(_config(), transport=transport)

    result = client.embed("How do I test this?")

    assert result.vector == (0.1, 0.2, 0.3, 0.4)
    assert result.model_name == "embedding-test"
    assert result.provider_name == "test-provider"
    assert result.input_tokens == 4
    assert result.usage_source == "provider_reported"
    assert transport.calls[0]["url"] == (
        "https://api.example.test/v1/embeddings"
    )
    assert transport.calls[0]["headers"] == {
        "Authorization": "Bearer credential-value",
    }
    assert transport.calls[0]["payload"] == {
        "model": "embedding-test",
        "input": "How do I test this?",
    }
    assert transport.calls[0]["timeout_seconds"] == 5


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": -1},
        {"prompt_tokens": "4"},
        {"prompt_tokens": True},
    ],
)
def test_invalid_embedding_token_counts_are_rejected(usage: dict) -> None:
    transport = FakeTransport(
        response={
            "model": "embedding-test",
            "data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}],
            "usage": usage,
        }
    )
    client = OpenAICompatibleEmbeddingClient(_config(), transport=transport)

    with pytest.raises(RemoteEmbeddingError) as exc_info:
        client.embed("query")

    assert exc_info.value.category == "malformed_response"


def test_missing_usage_is_explicitly_estimated() -> None:
    transport = FakeTransport(
        response={
            "model": "embedding-test",
            "data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}],
        }
    )

    result = OpenAICompatibleEmbeddingClient(
        _config(),
        transport=transport,
    ).embed("one two")

    assert result.input_tokens == 2
    assert result.usage_source == "estimated"


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"data": []},
        {"data": [{"embedding": []}]},
        {"data": [{"embedding": [0.1, 0.2]}]},
        {"data": [{"embedding": [0.1, math.nan, 0.3, 0.4]}]},
        {
            "model": "different-model",
            "data": [{"embedding": [0.1, 0.2, 0.3, 0.4]}],
        },
    ],
)
def test_invalid_embedding_response_fails_closed(response: dict) -> None:
    client = OpenAICompatibleEmbeddingClient(
        _config(),
        transport=FakeTransport(response=response),
    )

    with pytest.raises(RemoteEmbeddingError) as exc_info:
        client.embed("query")

    assert exc_info.value.category == "malformed_response"


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (401, "authentication"),
        (403, "authorization"),
        (429, "rate_limited"),
        (500, "transient_provider"),
        (400, "permanent_provider"),
    ],
)
def test_http_statuses_use_bounded_error_categories(status: int, category: str) -> None:
    client = OpenAICompatibleEmbeddingClient(
        _config(),
        transport=FakeTransport(status=status),
    )

    with pytest.raises(RemoteEmbeddingError) as exc_info:
        client.embed("query")

    assert exc_info.value.category == category
    assert "credential-value" not in str(exc_info.value)


def test_empty_text_is_rejected_before_transport() -> None:
    transport = FakeTransport()
    client = OpenAICompatibleEmbeddingClient(_config(), transport=transport)

    with pytest.raises(ValueError, match="must not be empty"):
        client.embed(" ")

    assert transport.calls == []


def test_retryable_embedding_failure_is_retried_with_bounded_count() -> None:
    transport = FlakyTransport(failures=1)
    client = OpenAICompatibleEmbeddingClient(
        _config(
            retry_limit=1,
            min_backoff_seconds=0,
            max_backoff_seconds=1,
        ),
        transport=transport,
    )

    result = client.embed("query")

    assert result.attempts == 2
    assert result.retry_count == 1
    assert len(transport.calls) == 2
