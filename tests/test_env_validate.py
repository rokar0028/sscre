import json
from pathlib import Path

import pytest

from sscre.env_validate import (
    APPLICATION_DEFAULT_SEMANTIC_STRATEGY,
    validate_environment,
    validate_timeout_relationship,
)
from sscre.config import Settings


def test_unit_test_mode_passes_with_minimal_environment(monkeypatch) -> None:
    monkeypatch.delenv("SSCRE_DATABASE_URL", raising=False)
    monkeypatch.delenv("SSCRE_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("SSCRE_RUNTIME_PROFILE", raising=False)

    report = validate_environment("unit-test")

    assert report["status"] == "pass"
    assert report["errors"] == []
    assert report["settings"]["semantic_strategy"] == APPLICATION_DEFAULT_SEMANTIC_STRATEGY
    assert report["warnings"] == []


def test_unit_test_mode_warns_when_compose_vars_left_in_shell(monkeypatch) -> None:
    monkeypatch.delenv("SSCRE_DATABASE_URL", raising=False)
    monkeypatch.setenv("SSCRE_ADMIN_TOKEN", "ci-local-admin-token-123456")
    monkeypatch.setenv("POSTGRES_PASSWORD", "ci-local-password")

    report = validate_environment("unit-test")

    assert report["status"] == "pass"
    assert any("unit-test mode does not require" in w for w in report["warnings"])


def test_development_compose_requires_password_and_admin_token(monkeypatch) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("SSCRE_ADMIN_TOKEN", raising=False)

    report = validate_environment("development-compose")

    assert report["status"] == "fail"
    assert any("POSTGRES_PASSWORD" in error for error in report["errors"])
    assert any("SSCRE_ADMIN_TOKEN" in error for error in report["errors"])


def test_development_compose_ci_sample_passes(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "ci-local-password")
    monkeypatch.setenv("SSCRE_ADMIN_TOKEN", "ci-local-admin-token-123456")
    monkeypatch.setenv("SSCRE_SEMANTIC_STRATEGY", "C")

    report = validate_environment("development-compose")

    assert report["status"] == "pass"
    assert report["errors"] == []


def test_production_requires_database_admin_and_expiry(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_RUNTIME_PROFILE", "production")
    monkeypatch.delenv("SSCRE_DATABASE_URL", raising=False)
    monkeypatch.delenv("SSCRE_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("SSCRE_ADMIN_TOKEN_EXPIRES_AT", raising=False)

    report = validate_environment("production")

    assert report["status"] == "fail"
    assert len(report["errors"]) >= 3


def test_production_valid_sample_passes(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("SSCRE_DATABASE_URL", "postgresql://sscre:secret@localhost:5432/sscre")
    monkeypatch.setenv("SSCRE_ADMIN_TOKEN", "ci-local-admin-token-123456")
    monkeypatch.setenv(
        "SSCRE_ADMIN_TOKEN_EXPIRES_AT", "2030-01-01T00:00:00+00:00"
    )
    monkeypatch.setenv("SSCRE_API_EXPOSURE_MODE", "external")
    monkeypatch.setenv(
        "SSCRE_CLIENT_AUTH_JSON", "experiments/client_auth_registry_sample.json"
    )
    monkeypatch.setenv("SSCRE_RATE_LIMIT_REQUESTS_PER_MINUTE", "120")
    monkeypatch.setenv("SSCRE_TENANT_PROVIDER_BUDGET_PER_MINUTE", "60")
    monkeypatch.setenv("SSCRE_SEMANTIC_STRATEGY", "C")

    report = validate_environment("production")

    assert report["status"] == "pass"


def test_invalid_boolean_fails(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_SEMANTIC_ENABLED", "sometimes")

    report = validate_environment("unit-test")

    assert report["status"] == "fail"
    assert any("SSCRE_SEMANTIC_ENABLED" in error for error in report["errors"])


def test_malformed_admin_token_expiry_fails(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_RUNTIME_PROFILE", "production")
    monkeypatch.setenv("SSCRE_DATABASE_URL", "postgresql://localhost/sscre")
    monkeypatch.setenv("SSCRE_ADMIN_TOKEN", "ci-local-admin-token-123456")
    monkeypatch.setenv("SSCRE_ADMIN_TOKEN_EXPIRES_AT", "not-a-timestamp")

    report = validate_environment("production")

    assert report["status"] == "fail"


def test_timeout_relationship_rejects_dependency_exceeding_request() -> None:
    settings = Settings(
        request_timeout_seconds=10,
        embedding_timeout_seconds=11,
    )

    errors = validate_timeout_relationship(settings)

    assert errors


def test_strategy_b_emits_embedding_only_warning(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_SEMANTIC_STRATEGY", "B")

    report = validate_environment("unit-test")

    assert report["status"] == "pass"
    assert any("Strategy B" in warning for warning in report["warnings"])


def test_compose_and_env_example_default_strategy_c() -> None:
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(
        encoding="utf-8"
    )
    assert "SSCRE_SEMANTIC_STRATEGY: ${SSCRE_SEMANTIC_STRATEGY:-C}" in compose
    assert "SSCRE_SEMANTIC_STRATEGY=C" in example


def test_compose_and_env_example_default_trusted_local_exposure() -> None:
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(
        encoding="utf-8"
    )
    assert (
        "SSCRE_API_EXPOSURE_MODE: ${SSCRE_API_EXPOSURE_MODE:-trusted_local}"
        in compose
    )
    assert "SSCRE_CLIENT_AUTH_JSON: /app/client_auth_registry.json" in compose
    assert "SSCRE_API_EXPOSURE_MODE=trusted_local" in example
    assert (
        "SSCRE_CLIENT_AUTH_JSON=experiments/client_auth_registry_sample.json"
        in example
    )


def test_report_json_does_not_echo_admin_token(monkeypatch) -> None:
    secret = "super-secret-admin-token-value-12345"
    monkeypatch.setenv("SSCRE_ADMIN_TOKEN", secret)

    report = validate_environment("unit-test")
    encoded = json.dumps(report)

    assert secret not in encoded
    assert report["settings"]["admin_token_configured"] is True
