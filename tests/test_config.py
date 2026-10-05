from sscre.config import Settings


def test_database_url_is_read_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "SSCRE_DATABASE_URL",
        "postgresql://sscre:secret@localhost:5432/sscre",
    )

    settings = Settings.from_environment()

    assert settings.database_url == (
        "postgresql://sscre:secret@localhost:5432/sscre"
    )
