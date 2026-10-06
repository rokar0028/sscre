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
