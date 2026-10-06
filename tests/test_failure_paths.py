from concurrent.futures import ThreadPoolExecutor
import threading
import time

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import InMemoryExactCache
from sscre.embedding import EmbeddingConfig
from sscre.llm import LLMResult


class MalformedEmbeddingClient:
    config = EmbeddingConfig(model_name="malformed", dimension=2)

    def embed(self, text: str) -> object:
        return object()


def test_malformed_embedding_generates_without_creating_a_cache_hit() -> None:
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=MalformedEmbeddingClient(),
        )
    )

    response = client.post(
        "/v1/query",
        json={"query": "embedding provider returned malformed data"},
    )

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert response.json()["reason"] == "embedding_unavailable"
    assert cache.storage_stats().entries == 0


def test_concurrent_same_query_generates_once_and_reuses_safely() -> None:
    class CountingSlowLLM:
        def __init__(self) -> None:
            self.calls = 0
            self._lock = threading.Lock()

        def generate(self, query: str) -> LLMResult:
            with self._lock:
                self.calls += 1
            time.sleep(0.05)
            return LLMResult(
                text=f"answer for {query}",
                input_tokens=1,
                output_tokens=3,
                latency_ms=50,
            )

    model = CountingSlowLLM()
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            llm_client=model,
            repository=cache,
            semantic_enabled=False,
        )
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post(
                    "/v1/query",
                    json={"query": "concurrent integration query"},
                ),
                range(2),
            )
        )

    assert all(response.status_code == 200 for response in responses)
    assert model.calls == 1
    assert sorted(response.json()["source"] for response in responses) == [
        "cache",
        "generated",
    ]
    assert cache.storage_stats().entries == 1
