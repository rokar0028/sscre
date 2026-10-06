from pathlib import Path

import pytest

from sscre.migrate import _migration_files, migration_checksum


def test_migration_checksum_is_sha256_of_file_contents(tmp_path: Path) -> None:
    migration = tmp_path / "001_example.sql"
    migration.write_text("SELECT 1;\n", encoding="utf-8")

    assert migration_checksum(migration) == (
        "d3cd5042f97738960d802ad6b3a548df"
        "a18152215118ba18f04493bc6944b0e4"
    )


def test_migration_filenames_require_unique_three_digit_versions(
    tmp_path: Path,
) -> None:
    (tmp_path / "001_first.sql").write_text("", encoding="utf-8")
    (tmp_path / "001_second.sql").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        _migration_files(tmp_path)


def test_migration_filenames_reject_unversioned_sql(tmp_path: Path) -> None:
    (tmp_path / "README.sql").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="NNN_name.sql"):
        _migration_files(tmp_path)
