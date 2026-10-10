"""Pytest hooks shared across the test suite."""

from __future__ import annotations

import os

import pytest


def _uses_postgresql_environment(request: pytest.FixtureRequest) -> bool:
    if request.node.get_closest_marker("ws8_postgres_failure_recovery"):
        return True
    path = str(request.node.fspath)
    return "test_postgres" in path


@pytest.fixture(autouse=True)
def isolate_memory_tests_from_shell_database_url(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """``create_app()`` without overrides reads ``SSCRE_DATABASE_URL`` from the shell.

    Developers often export it for Docker/WS8 runs; hide it from in-memory tests so
    the default suite stays deterministic.
    """
    if _uses_postgresql_environment(request):
        return
    monkeypatch.delenv("SSCRE_DATABASE_URL", raising=False)
