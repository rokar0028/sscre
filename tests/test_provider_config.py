import json

import pytest

from sscre.provider_config import (
    PROVIDER_CONFIG_VERSION,
    RealProviderConfig,
)


def _enable_provider(monkeypatch, **overrides) -> None:
    values = {
        "SSCRE_REAL_PROVIDER": "true",
        "SSCRE_PROVIDER": "test-provider",
        "SSCRE_PROVIDER_ENDPOINT": "https://api.example.test/v1/private",
        "SSCRE_PROVIDER_GENERATION_MODEL": "generation-test",
        "SSCRE_PROVIDER_EMBEDDING_MODEL": "embedding-test",
        "SSCRE_PROVIDER_EMBEDDING_DIMENSION": "8",
        "SSCRE_PROVIDER_REQUEST_TIMEOUT_SECONDS": "30",
        "SSCRE_PROVIDER_GENERATION_TIMEOUT_SECONDS": "25",
        "SSCRE_PROVIDER_EMBEDDING_TIMEOUT_SECONDS": "5",
        "SSCRE_PROVIDER_CONNECT_TIMEOUT_SECONDS": "2",
        "SSCRE_PROVIDER_RETRY_LIMIT": "2",
        "SSCRE_PROVIDER_MIN_BACKOFF_SECONDS": "0.1",
        "SSCRE_PROVIDER_MAX_BACKOFF_SECONDS": "2",
        "SSCRE_PROVIDER_MAX_RETRY_ELAPSED_SECONDS": "5",
        "SSCRE_PROVIDER_EXPERIMENT_ID": "workstream4-step2",
        "SSCRE_PROVIDER_DATASET_VERSION": "reviewed-query-pairs-1.1",
        "SSCRE_PROVIDER_SPLIT": "development",
        "SSCRE_PROVIDER_PRICING_SCHEDULE_ID": "provider-prices-2026-10",
        "SSCRE_PROVIDER_ALLOWED_HOSTS": "api.example.test",
        "SSCRE_PROVIDER_CREDENTIAL": "credential-value",
    }
    values.update(overrides)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_real_provider_mode_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SSCRE_REAL_PROVIDER", raising=False)

    assert RealProviderConfig.from_environment() is None


def test_enabled_config_requires_all_required_fields(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_REAL_PROVIDER", "true")

    with pytest.raises(ValueError, match="SSCRE_PROVIDER is required"):
        RealProviderConfig.from_environment()


def test_environment_config_is_validated_and_redacted(monkeypatch) -> None:
    _enable_provider(monkeypatch)

    config = RealProviderConfig.from_environment()

    assert config is not None
    assert config.config_version == PROVIDER_CONFIG_VERSION
    assert config.endpoint_origin == "https://api.example.test"
    assert config.credential_configured is True
    assert config.redacted()["endpoint_origin"] == "https://api.example.test"
    assert config.redacted()["credential_configured"] is True
    encoded = json.dumps(config.redacted(), sort_keys=True)
    assert "credential-value" not in encoded
    assert "api_key" not in encoded
    assert "https://api.example.test/v1/private" not in encoded


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("SSCRE_PROVIDER_REQUEST_TIMEOUT_SECONDS", "0", "must be at least"),
        ("SSCRE_PROVIDER_EMBEDDING_DIMENSION", "0", "must be at least"),
        ("SSCRE_PROVIDER_RETRY_LIMIT", "-1", "must be at least"),
        ("SSCRE_PROVIDER_MAX_BACKOFF_SECONDS", "9", "maximum backoff"),
        ("SSCRE_PROVIDER_MAX_RETRY_ELAPSED_SECONDS", "31", "retry budget"),
        ("SSCRE_PROVIDER_MAX_RETRY_ELAPSED_SECONDS", "nan", "must be at least"),
        ("SSCRE_PROVIDER_MAX_RETRY_ELAPSED_SECONDS", "inf", "must be at least"),
    ],
)
def test_invalid_numeric_configuration_is_rejected(
    monkeypatch,
    field: str,
    value: str,
    message: str,
) -> None:
    _enable_provider(monkeypatch, **{field: value})

    with pytest.raises(ValueError, match=message):
        RealProviderConfig.from_environment()


@pytest.mark.parametrize(
    "endpoint",
    [
        "ftp://api.example.test/v1",
        "https://user:password@api.example.test/v1",
        "https://api.example.test/v1?api_key=secret",
        "https://api.example.test/v1#fragment",
    ],
)
def test_endpoint_must_be_safe_http_url(monkeypatch, endpoint: str) -> None:
    _enable_provider(monkeypatch, SSCRE_PROVIDER_ENDPOINT=endpoint)

    with pytest.raises(ValueError, match="endpoint"):
        RealProviderConfig.from_environment()


def test_endpoint_host_allow_list_is_enforced(monkeypatch) -> None:
    _enable_provider(
        monkeypatch,
        SSCRE_PROVIDER_ALLOWED_HOSTS="other.example.test",
    )

    with pytest.raises(ValueError, match="allowed_hosts"):
        RealProviderConfig.from_environment()


def test_request_parameters_cannot_override_reserved_fields() -> None:
    with pytest.raises(ValueError, match="reserved fields"):
        RealProviderConfig(
            provider="provider",
            endpoint="https://api.example.test",
            generation_model="generation",
            embedding_model="embedding",
            embedding_dimension=8,
            request_timeout_seconds=30,
            generation_timeout_seconds=25,
            embedding_timeout_seconds=5,
            connect_timeout_seconds=2,
            retry_limit=0,
            min_backoff_seconds=0,
            max_backoff_seconds=1,
            max_retry_elapsed_seconds=5,
            experiment_id="experiment",
            dataset_version="dataset",
            split="development",
            pricing_schedule_id="prices",
            request_parameters=(("model", "other"),),
        )


def test_request_parameters_cannot_contain_credentials() -> None:
    with pytest.raises(ValueError, match="credentials"):
        RealProviderConfig(
            provider="provider",
            endpoint="https://api.example.test",
            generation_model="generation",
            embedding_model="embedding",
            embedding_dimension=8,
            request_timeout_seconds=30,
            generation_timeout_seconds=25,
            embedding_timeout_seconds=5,
            connect_timeout_seconds=2,
            retry_limit=0,
            min_backoff_seconds=0,
            max_backoff_seconds=1,
            max_retry_elapsed_seconds=5,
            experiment_id="experiment",
            dataset_version="dataset",
            split="development",
            pricing_schedule_id="prices",
            request_parameters=(("api_key", "secret"),),
        )


def test_timeout_relationships_are_validated() -> None:
    with pytest.raises(ValueError, match="generation timeout"):
        RealProviderConfig(
            provider="provider",
            endpoint="https://api.example.test",
            generation_model="generation",
            embedding_model="embedding",
            embedding_dimension=8,
            request_timeout_seconds=10,
            generation_timeout_seconds=11,
            embedding_timeout_seconds=5,
            connect_timeout_seconds=2,
            retry_limit=0,
            min_backoff_seconds=0,
            max_backoff_seconds=1,
            max_retry_elapsed_seconds=5,
            experiment_id="experiment",
            dataset_version="dataset",
            split="development",
            pricing_schedule_id="prices",
        )


def test_provider_timeout_and_retry_budget_must_fit_request_timeout() -> None:
    with pytest.raises(ValueError, match="timeout plus retry budget"):
        RealProviderConfig(
            provider="provider",
            endpoint="https://api.example.test",
            generation_model="generation",
            embedding_model="embedding",
            embedding_dimension=8,
            request_timeout_seconds=30,
            generation_timeout_seconds=25,
            embedding_timeout_seconds=5,
            connect_timeout_seconds=2,
            retry_limit=1,
            min_backoff_seconds=0,
            max_backoff_seconds=1,
            max_retry_elapsed_seconds=6,
            experiment_id="experiment",
            dataset_version="dataset",
            split="development",
            pricing_schedule_id="prices",
        )
