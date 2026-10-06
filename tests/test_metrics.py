import json
from uuid import UUID

from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.embedding import EmbeddingConfig, EmbeddingResult, FakeEmbeddingClient
from sscre.llm import MockLLMClient


def test_response_contains_request_metrics_and_cumulative_counters() -> None:
    client = TestClient(create_app())

    generated = client.post("/v1/query", json={"query": "Explain metrics"})
    cached = client.post("/v1/query", json={"query": "Explain metrics"})

    generated_metrics = generated.json()["metrics"]
    cached_metrics = cached.json()["metrics"]
    UUID(generated_metrics["request_id"])
    UUID(cached_metrics["request_id"])
    assert generated_metrics["total_latency_ms"] >= 0
    assert generated_metrics["llm_input_tokens"] > 0
    assert generated_metrics["llm_output_tokens"] > 0
    assert generated_metrics["cache_hits"] == 0
    assert generated_metrics["cache_misses"] == 1
    assert generated_metrics["semantic_misses"] == 1
    assert cached_metrics["cache_hits"] == 1
    assert cached_metrics["cache_misses"] == 1
    assert cached_metrics["exact_hits"] == 1


def test_decision_log_is_structured_and_does_not_include_answer(
    caplog,
) -> None:
    caplog.set_level("INFO", logger="sscre")
    client = TestClient(create_app())

    response = client.post("/v1/query", json={"query": "Explain logs"})

    assert response.status_code == 200
    log = json.loads(next(record.message for record in caplog.records))
    assert log["event"] == "cache_decision"
    assert log["decision"] == "UNCERTAIN"
    assert log["request_id"] == response.json()["metrics"]["request_id"]
    assert log["source"] == "generated"
    assert log["llm_input_tokens"] > 0
    assert log["llm_output_tokens"] > 0
    assert log["latency_ms"] >= 0
    assert "answer" not in log


def test_cache_hit_decision_log_is_structured(caplog) -> None:
    caplog.set_level("INFO", logger="sscre")
    client = TestClient(create_app())

    client.post("/v1/query", json={"query": "Explain hit logs"})
    response = client.post("/v1/query", json={"query": "Explain hit logs"})

    logs = [json.loads(record.message) for record in caplog.records]
    log = next(entry for entry in logs if entry["decision"] == "SAFE")
    assert log["source"] == "cache"
    assert log["request_id"] == response.json()["metrics"]["request_id"]
    assert log["llm_input_tokens"] == 0
    assert log["llm_output_tokens"] == 0
    assert log["latency_ms"] >= 0


def test_semantic_hit_reports_strategy_similarity_and_counters() -> None:
    from hashlib import sha256

    from sscre.cache import CacheEntry, InMemoryExactCache
    from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient

    cache = InMemoryExactCache(embedding_dimension=2)
    cache.insert(
        CacheEntry(
            query_hash=sha256(b"stored query").hexdigest(),
            normalized_query="stored query",
            answer="stored answer",
            embedding=(1.0, 0.0),
            embedding_model="test-embedding",
            embedding_dimension=2,
        )
    )
    embedding_client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={"paraphrased query": (1.0, 0.0)},
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=embedding_client,
            semantic_similarity_threshold=0.9,
        )
    )

    response = client.post("/v1/query", json={"query": "paraphrased query"})

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "semantic"
    assert body["similarity"] == 1.0
    assert body["metrics"]["semantic_hits"] == 1
    assert body["metrics"]["exact_hits"] == 0


def test_semantic_retrieval_rejects_a_different_embedding_model() -> None:
    from hashlib import sha256

    from sscre.cache import CacheEntry, InMemoryExactCache
    from sscre.embedding import EmbeddingConfig, FakeEmbeddingClient

    cache = InMemoryExactCache(embedding_dimension=2)
    cache.insert(
        CacheEntry(
            query_hash=sha256(b"stored query").hexdigest(),
            normalized_query="stored query",
            answer="stored answer",
            embedding=(1.0, 0.0),
            embedding_model="other-embedding",
            embedding_dimension=2,
        )
    )
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="test-embedding", dimension=2),
                vectors={"new query": (1.0, 0.0)},
            ),
            semantic_similarity_threshold=0.9,
        )
    )

    response = client.post("/v1/query", json={"query": "new query"})

    assert response.status_code == 200
    assert response.json()["source"] == "generated"


def test_semantic_disabled_does_not_embed_or_store_vectors() -> None:
    from sscre.cache import InMemoryExactCache
    from sscre.query import hash_query

    cache = InMemoryExactCache()
    embedding_client = CountingEmbeddingClient()
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=embedding_client,
            semantic_enabled=False,
        )
    )

    response = client.post("/v1/query", json={"query": "exact only"})

    assert response.status_code == 200
    assert embedding_client.calls == 0
    entry = cache.get_by_query_hash(hash_query("exact only"))
    assert entry is not None
    assert entry.embedding is None


def test_invalid_custom_embedding_result_falls_back_without_caching() -> None:
    from hashlib import sha256

    from sscre.cache import InMemoryExactCache

    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=InvalidEmbeddingClient(),
        )
    )

    response = client.post("/v1/query", json={"query": "invalid vector"})

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert cache.get_by_query_hash(
        sha256(b"invalid vector").hexdigest()
    ) is None


def test_invalid_query_is_rejected() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/query", json={"query": "   "})

    assert response.status_code == 422


def test_generation_failure_returns_502_and_is_not_cached(caplog) -> None:
    caplog.set_level("INFO", logger="sscre")
    model = MockLLMClient(should_fail=True)
    client = TestClient(create_app(model))

    failed = client.post("/v1/query", json={"query": "Will this fail?"})
    model.should_fail = False
    retry = client.post("/v1/query", json={"query": "Will this fail?"})

    assert failed.status_code == 502
    assert failed.headers["X-Request-ID"]
    assert retry.status_code == 200
    assert retry.json()["source"] == "generated"
    assert retry.json()["metrics"]["generation_failures"] == 1

    failure_log = json.loads(
        next(
            record.message
            for record in caplog.records
            if "GENERATION_FAILED" in record.message
        )
    )
    assert failure_log["source"] == "error"
    assert failure_log["llm_input_tokens"] == 0
    assert failure_log["llm_output_tokens"] == 0
    assert failure_log["latency_ms"] >= 0
    assert "answer" not in failure_log


class CountingEmbeddingClient(FakeEmbeddingClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def embed(self, text: str) -> EmbeddingResult:
        self.calls += 1
        return super().embed(text)


class InvalidEmbeddingClient:
    config = EmbeddingConfig(model_name="invalid-test", dimension=2)

    def embed(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=(1.0,),
            model_name=self.config.model_name,
            input_tokens=1,
            latency_ms=0,
        )
