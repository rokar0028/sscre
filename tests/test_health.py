from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheRepositoryError, InMemoryExactCache


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_for_memory_profile() -> None:
    client = TestClient(create_app())

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "repository": "memory"}


def test_readiness_endpoint_fails_when_repository_is_unavailable() -> None:
    class UnreadyCache(InMemoryExactCache):
        def check_ready(self, timeout_seconds: int = 1) -> None:
            raise CacheRepositoryError("database unavailable")

    client = TestClient(create_app(repository=UnreadyCache()))

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "service not ready"}
