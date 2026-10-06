from sscre.config import Settings
import pytest


def test_database_url_is_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "SSCRE_DATABASE_URL",
        "postgresql://sscre:secret@localhost:5432/sscre",
    )

    settings = Settings.from_environment()

    assert settings.database_url == (
        "postgresql://sscre:secret@localhost:5432/sscre"
    )


def test_semantic_cache_settings_are_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_SEMANTIC_ENABLED", "false")
    monkeypatch.setenv("SSCRE_SEMANTIC_STRATEGY", "C")
    monkeypatch.setenv("SSCRE_SEMANTIC_TOP_K", "7")
    monkeypatch.setenv("SSCRE_SEMANTIC_SIMILARITY_THRESHOLD", "0.88")

    settings = Settings.from_environment()

    assert settings.semantic_enabled is False
    assert settings.semantic_strategy == "C"
    assert settings.semantic_top_k == 7
    assert settings.semantic_similarity_threshold == 0.88


def test_invalid_dynamic_cache_boolean_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_CACHE_ALLOW_DYNAMIC_ENTRIES", "sometimes")

    with pytest.raises(ValueError, match="true or false"):
        Settings.from_environment()


def test_dependency_timeouts_are_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_TIMEOUT_REQUEST_SECONDS", "40")
    monkeypatch.setenv("SSCRE_TIMEOUT_GENERATION_SECONDS", "12")

    settings = Settings.from_environment()

    assert settings.request_timeout_seconds == 40
    assert settings.generation_timeout_seconds == 12


def test_admin_token_is_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_ADMIN_TOKEN", "configured-token")

    settings = Settings.from_environment()

    assert settings.admin_token == "configured-token"


def test_runtime_profile_and_log_level_are_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("SSCRE_RUNTIME_PROFILE", "test")
    monkeypatch.setenv("SSCRE_LOG_LEVEL", "warning")

    settings = Settings.from_environment()

    assert settings.runtime_profile == "test"
    assert settings.log_level == "WARNING"


def test_production_requires_database_and_admin_secret() -> None:
    with pytest.raises(ValueError, match="database_url"):
        Settings(runtime_profile="production")

    with pytest.raises(ValueError, match="admin_token"):
        Settings(
            runtime_profile="production",
            database_url="postgresql://localhost/sscre",
        )

    with pytest.raises(ValueError, match="16 characters"):
        Settings(
            runtime_profile="production",
            database_url="postgresql://localhost/sscre",
            admin_token="too-short",
        )


def test_dependency_timeouts_must_be_positive() -> None:
    with pytest.raises(ValueError, match="repository_timeout_seconds"):
        Settings(repository_timeout_seconds=0)
