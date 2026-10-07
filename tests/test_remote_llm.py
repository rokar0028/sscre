import pytest

from sscre.provider_config import RealProviderConfig
from sscre.remote_llm import (
    OpenAICompatibleLLMClient,
    RemoteLLMError,
    UrllibJSONTransport,
)


class FakeTransport:
    def __init__(self, status: int = 200, response: dict | None = None) -> None:
        self.status = status
        self.response = (
            response
            if response is not None
            else {
                "choices": [{"message": {"content": "A remote answer"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 3},
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
            raise RemoteLLMError("transient_provider")
        return self.status, self.response


def _config(**overrides) -> RealProviderConfig:
    values = {
        "provider": "test-provider",
        "endpoint": "https://api.example.test/v1",
        "generation_model": "generation-test",
        "embedding_model": "embedding-test",
        "embedding_dimension": 8,
        "request_timeout_seconds": 30,
        "generation_timeout_seconds": 25,
        "embedding_timeout_seconds": 5,
        "connect_timeout_seconds": 2,
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


def test_remote_generation_parses_response_and_sends_allow_listed_payload() -> None:
    transport = FakeTransport()
    client = OpenAICompatibleLLMClient(_config(), transport=transport)

    result = client.generate("How do I test this?")

    assert result.text == "A remote answer"
    assert result.input_tokens == 4
    assert result.output_tokens == 3
    assert result.usage_source == "provider_reported"
    assert result.provider_name == "test-provider"
    assert result.model_name == "generation-test"
    assert len(transport.calls) == 1
    assert transport.calls[0]["url"] == (
        "https://api.example.test/v1/chat/completions"
    )
    assert transport.calls[0]["headers"] == {
        "Authorization": "Bearer credential-value",
    }
    assert transport.calls[0]["payload"] == {
        "model": "generation-test",
        "messages": [{"role": "user", "content": "How do I test this?"}],
    }
    assert transport.calls[0]["timeout_seconds"] == 25


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_tokens": -1, "completion_tokens": 1},
        {"prompt_tokens": 1, "completion_tokens": -3},
        {"prompt_tokens": "4", "completion_tokens": 1},
        {"prompt_tokens": True, "completion_tokens": 1},
    ],
)
def test_invalid_provider_token_counts_are_rejected(usage: dict) -> None:
    transport = FakeTransport(
        response={
            "choices": [{"message": {"content": "answer text"}}],
            "usage": usage,
        }
    )
    client = OpenAICompatibleLLMClient(_config(), transport=transport)

    with pytest.raises(RemoteLLMError) as exc_info:
        client.generate("query")

    assert exc_info.value.category == "malformed_response"


def test_urllib_timeout_maps_to_timeout_category(monkeypatch) -> None:
    def raise_timeout(*_args, **_kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr("sscre.remote_llm.urlopen", raise_timeout)
    transport = UrllibJSONTransport()

    with pytest.raises(RemoteLLMError) as exc_info:
        transport.post(
            "https://api.example.test/v1/chat/completions",
            headers={},
            payload={"model": "m", "messages": []},
            timeout_seconds=5,
        )

    assert exc_info.value.category == "timeout"


def test_request_parameters_merge_into_generation_payload() -> None:
    transport = FakeTransport()
    config = _config(request_parameters=(("temperature", "0"),))
    OpenAICompatibleLLMClient(config, transport=transport).generate("hello")

    assert transport.calls[0]["payload"]["temperature"] == "0"
    assert transport.calls[0]["payload"]["model"] == "generation-test"


def test_missing_usage_is_explicitly_estimated() -> None:
    transport = FakeTransport(
        response={"choices": [{"message": {"content": "one two three"}}]}
    )

    result = OpenAICompatibleLLMClient(_config(), transport=transport).generate(
        "one two"
    )

    assert result.input_tokens == 2
    assert result.output_tokens == 3
    assert result.usage_source == "estimated"


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": ""}}]},
    ],
)
def test_malformed_response_fails_closed(response: dict) -> None:
    client = OpenAICompatibleLLMClient(
        _config(),
        transport=FakeTransport(response=response),
    )

    with pytest.raises(RemoteLLMError, match="remote generation failed") as exc_info:
        client.generate("query")

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
    client = OpenAICompatibleLLMClient(
        _config(),
        transport=FakeTransport(status=status),
    )

    with pytest.raises(RemoteLLMError) as exc_info:
        client.generate("query")

    assert exc_info.value.category == category
    assert "credential-value" not in str(exc_info.value)


def test_credential_is_required_before_transport_call() -> None:
    with pytest.raises(ValueError, match="credential"):
        OpenAICompatibleLLMClient(_config(credential=None))


def test_retryable_provider_failure_is_retried_with_bounded_count() -> None:
    transport = FlakyTransport(failures=2)
    client = OpenAICompatibleLLMClient(
        _config(
            retry_limit=2,
            min_backoff_seconds=0,
            max_backoff_seconds=1,
        ),
        transport=transport,
    )

    result = client.generate("query")

    assert result.attempts == 3
    assert result.retry_count == 2
    assert len(transport.calls) == 3


def test_non_retryable_malformed_response_is_not_retried() -> None:
    transport = FakeTransport(response={"choices": []})
    client = OpenAICompatibleLLMClient(
        _config(retry_limit=2),
        transport=transport,
    )

    with pytest.raises(RemoteLLMError):
        client.generate("query")

    assert len(transport.calls) == 1


def test_first_attempt_success_performs_no_retry() -> None:
    transport = FakeTransport()
    client = OpenAICompatibleLLMClient(_config(retry_limit=3), transport=transport)

    result = client.generate("one two three")

    assert result.retry_count == 0
    assert result.attempts == 1
    assert len(transport.calls) == 1


def test_measured_latency_and_retry_counts_remain_bounded() -> None:
    transport = FlakyTransport(failures=1)
    client = OpenAICompatibleLLMClient(
        _config(retry_limit=1, min_backoff_seconds=0, max_backoff_seconds=0),
        transport=transport,
    )

    result = client.generate("query")

    assert result.latency_ms >= 0
    assert result.retry_count <= client.config.retry_limit
    assert result.attempts == result.retry_count + 1


def test_exception_text_does_not_serialize_query_or_response_body() -> None:
    secret_query = "secret-query-token-value"
    transport = FakeTransport(
        response={
            "choices": [{"message": {"content": ""}}],
            "provider_payload": "raw-response-body-should-not-leak",
        }
    )
    client = OpenAICompatibleLLMClient(_config(), transport=transport)

    with pytest.raises(RemoteLLMError) as exc_info:
        client.generate(secret_query)

    message = str(exc_info.value)
    assert secret_query not in message
    assert "raw-response-body-should-not-leak" not in message
    assert "credential-value" not in message


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query_is_rejected_before_transport(query: str) -> None:
    transport = FakeTransport()
    client = OpenAICompatibleLLMClient(_config(), transport=transport)

    with pytest.raises(ValueError, match="query"):
        client.generate(query)

    assert transport.calls == []
