"""Workstream 3 Step 3.3: controlled HTTP responses for timeout paths."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

try:
    from fastapi.testclient import TestClient
    from sscre.app import create_app
except ImportError:  # pragma: no cover
    pytest.skip(
        "sscre.app unavailable in this environment",
        allow_module_level=True,
    )

from sscre.cache import InMemoryExactCache
from sscre.config import Settings
from sscre.llm import LLMResult, MockLLMClient


class SlowLLM(MockLLMClient):
    def __init__(self, delay_seconds: float) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    def generate(self, query: str) -> LLMResult:
        time.sleep(self.delay_seconds)
        return super().generate(query)


class SlowLookupCache(InMemoryExactCache):
    def __init__(self, delay_seconds: float) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds

    def get_by_query_hash(self, query_hash: str):
        time.sleep(self.delay_seconds)
        return super().get_by_query_hash(query_hash)


def test_generation_dependency_timeout_returns_504() -> None:
    client = TestClient(
        create_app(
            llm_client=SlowLLM(delay_seconds=1.5),
            settings=Settings(
                generation_timeout_seconds=1,
                request_timeout_seconds=30,
                semantic_enabled=False,
            ),
        )
    )
    response = client.post("/v1/query", json={"query": "slow generation timeout baseline"})
    assert response.status_code == 504
    assert response.json()["detail"] == "response generation timed out"
    assert response.headers.get("X-Request-ID")


def test_generation_lock_contention_returns_503() -> None:
    settings = Settings(
        generation_timeout_seconds=1,
        request_timeout_seconds=10,
        repository_timeout_seconds=5,
        semantic_enabled=False,
    )
    client = TestClient(
        create_app(
            repository=SlowLookupCache(delay_seconds=2.5),
            settings=settings,
            semantic_enabled=False,
        )
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            client.post,
            "/v1/query",
            json={"query": "lock contention query A unique"},
        )
        second = pool.submit(
            client.post,
            "/v1/query",
            json={"query": "lock contention query B unique"},
        )
        response_first = first.result()
        response_second = second.result()
        statuses = sorted((response_first.status_code, response_second.status_code))

    assert 503 in statuses
    lock_timeout = next(
        response
        for response in (response_first, response_second)
        if response.status_code == 503
    )
    assert lock_timeout.json()["detail"] == "generation temporarily unavailable"
    assert lock_timeout.headers.get("X-Request-ID")
