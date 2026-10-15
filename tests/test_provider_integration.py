import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import CacheEntry, InMemoryExactCache
from sscre.config import Settings
from sscre.embedding import (
    EmbeddingConfig,
    EmbeddingProviderError,
    EmbeddingResult,
    FakeEmbeddingClient,
)
from sscre.llm import LLMResult, MockLLMClient
from sscre.provider_config import RealProviderConfig
from sscre.remote_embedding import OpenAICompatibleEmbeddingClient
from sscre.remote_llm import OpenAICompatibleLLMClient
from sscre.safety import QueryMetadata


def _enable_provider(monkeypatch) -> None:
    values = {
        "SSCRE_REAL_PROVIDER": "true",
        "SSCRE_PROVIDER": "test-provider",
        "SSCRE_PROVIDER_ENDPOINT": "https://api.example.test/v1",
        "SSCRE_PROVIDER_GENERATION_MODEL": "generation-test",
        "SSCRE_PROVIDER_EMBEDDING_MODEL": "embedding-test",
        "SSCRE_PROVIDER_EMBEDDING_DIMENSION": "8",
        "SSCRE_PROVIDER_REQUEST_TIMEOUT_SECONDS": "30",
        "SSCRE_PROVIDER_GENERATION_TIMEOUT_SECONDS": "25",
        "SSCRE_PROVIDER_EMBEDDING_TIMEOUT_SECONDS": "5",
        "SSCRE_PROVIDER_RETRY_LIMIT": "0",
        "SSCRE_PROVIDER_MIN_BACKOFF_SECONDS": "0",
        "SSCRE_PROVIDER_MAX_BACKOFF_SECONDS": "1",
        "SSCRE_PROVIDER_MAX_RETRY_ELAPSED_SECONDS": "5",
        "SSCRE_PROVIDER_EXPERIMENT_ID": "workstream4-step6",
        "SSCRE_PROVIDER_DATASET_VERSION": "dataset",
        "SSCRE_PROVIDER_SPLIT": "development",
        "SSCRE_PROVIDER_PRICING_SCHEDULE_ID": "prices",
        "SSCRE_PROVIDER_CREDENTIAL": "credential-value",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


class ConfiguredGenerationClient:
    def __init__(self, config) -> None:
        self.config = config


class ConfiguredEmbeddingClient:
    def __init__(self, config) -> None:
        self.config = config


class CountingProviderLLMClient:
    def __init__(
        self,
        *,
        provider_name: str = "test-provider",
        model_name: str = "generation-test",
        should_fail: bool = False,
    ) -> None:
        self.calls = 0
        self.provider_name = provider_name
        self.model_name = model_name
        self.should_fail = should_fail

    def generate(self, query: str) -> LLMResult:
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("configured provider generation failed")
        return LLMResult(
            text=f"provider answer for {query}",
            input_tokens=4,
            output_tokens=6,
            latency_ms=12,
            provider_name=self.provider_name,
            model_name=self.model_name,
            usage_source="provider_reported",
            attempts=1,
            retry_count=0,
        )


class CountingProviderEmbeddingClient:
    def __init__(
        self,
        *,
        dimension: int = 8,
        model_name: str = "embedding-test",
        provider_name: str = "test-provider",
        vectors: dict[str, tuple[float, ...]] | None = None,
        should_fail: bool = False,
    ) -> None:
        self.calls = 0
        self.should_fail = should_fail
        self._vectors = vectors or {}
        self._config = EmbeddingConfig(model_name=model_name, dimension=dimension)
        self.provider_name = provider_name

    @property
    def config(self) -> EmbeddingConfig:
        return self._config

    def embed(self, text: str) -> EmbeddingResult:
        self.calls += 1
        if self.should_fail:
            raise EmbeddingProviderError("embedding provider unavailable")
        vector = self._vectors.get(text)
        if vector is None:
            vector = tuple(0.125 for _ in range(self._config.dimension))
        return EmbeddingResult(
            vector=vector,
            model_name=self._config.model_name,
            input_tokens=3,
            latency_ms=8,
            provider_name=self.provider_name,
            usage_source="provider_reported",
            attempts=1,
            retry_count=0,
        )


class SlowProviderLLMClient(CountingProviderLLMClient):
    def generate(self, query: str) -> LLMResult:
        time.sleep(1.1)
        return super().generate(query)


def _provider_test_client(
    monkeypatch,
    *,
    llm_client: CountingProviderLLMClient | None = None,
    embedding_client: CountingProviderEmbeddingClient | None = None,
    **create_app_kwargs,
) -> tuple[TestClient, CountingProviderLLMClient, CountingProviderEmbeddingClient]:
    _enable_provider(monkeypatch)
    llm = llm_client or CountingProviderLLMClient()
    embedding = embedding_client or CountingProviderEmbeddingClient()
    client = TestClient(
        create_app(
            llm_client=llm,
            embedding_client=embedding,
            **create_app_kwargs,
        )
    )
    return client, llm, embedding


def _python_search_meta() -> QueryMetadata:
    return QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", "python"),
        constraints=(("language", "python"),),
        output_format="code",
    )


def test_real_provider_mode_constructs_configured_clients(
    monkeypatch,
) -> None:
    _enable_provider(monkeypatch)
    import sscre.app as app_module

    generations: list[object] = []
    embeddings: list[object] = []

    def build_generation(config):
        client = ConfiguredGenerationClient(config)
        generations.append(client)
        return client

    def build_embedding(config):
        client = ConfiguredEmbeddingClient(config)
        embeddings.append(client)
        return client

    monkeypatch.setattr(app_module, "OpenAICompatibleLLMClient", build_generation)
    monkeypatch.setattr(
        app_module,
        "OpenAICompatibleEmbeddingClient",
        build_embedding,
    )

    create_app(settings=Settings(semantic_enabled=True))

    assert len(generations) == 1
    assert len(embeddings) == 1
    assert generations[0].config.provider == "test-provider"
    assert embeddings[0].config.embedding_model == "embedding-test"


def test_real_provider_mode_rejects_fake_generation_client(monkeypatch) -> None:
    _enable_provider(monkeypatch)

    with pytest.raises(ValueError, match="fake generation"):
        create_app(
            llm_client=MockLLMClient(),
            settings=Settings(semantic_enabled=False),
        )


def test_real_provider_mode_rejects_fake_embedding_client(monkeypatch) -> None:
    _enable_provider(monkeypatch)

    with pytest.raises(ValueError, match="fake embedding"):
        create_app(
            llm_client=ConfiguredGenerationClient(None),
            embedding_client=FakeEmbeddingClient(),
            settings=Settings(semantic_enabled=True),
        )


def test_real_provider_mode_fails_closed_when_configuration_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SSCRE_REAL_PROVIDER", "true")
    monkeypatch.delenv("SSCRE_PROVIDER", raising=False)

    with pytest.raises(ValueError, match="SSCRE_PROVIDER is required"):
        create_app(settings=Settings(semantic_enabled=False))


@pytest.mark.real_provider
def test_opt_in_real_provider_smoke_is_bounded_and_development_only() -> None:
    if os.getenv("SSCRE_REAL_PROVIDER_LIVE", "").lower() != "true":
        pytest.skip("set SSCRE_REAL_PROVIDER_LIVE=true to enable live provider tests")
    config = RealProviderConfig.from_environment()
    if config is None:
        pytest.fail(
            "SSCRE_REAL_PROVIDER=true and provider configuration are required "
            "when live provider testing is explicitly enabled"
        )
    if config.split != "development":
        pytest.fail("live provider smoke tests require the development split")
    if not config.credential_configured:
        pytest.fail("provider credential is required for live provider testing")

    # This test intentionally performs exactly two remote calls: one generation
    # and one embedding request. Broader workload and spend accounting belong
    # to the redacted measurement run in Workstream 4 step 10.
    generation = OpenAICompatibleLLMClient(config).generate(
        "Return one short sentence confirming the provider smoke test."
    )
    embedding = OpenAICompatibleEmbeddingClient(config).embed(
        "provider smoke test"
    )
    assert generation.text.strip()
    assert embedding.vector


def test_create_app_loads_pricing_schedule_from_env(monkeypatch, tmp_path) -> None:
    _enable_provider(monkeypatch)
    pricing_path = tmp_path / "pricing.json"
    pricing_path.write_text(
        '{"schedule_id":"prices","currency":"USD","effective_date":"2026-10-07",'
        '"source":"provider_list_estimate","generation_input_per_1k":0.01,'
        '"generation_output_per_1k":0.02,"embedding_input_per_1k":0.001}',
        encoding="utf-8",
    )
    monkeypatch.setenv("SSCRE_PROVIDER_PRICING_JSON", str(pricing_path))
    monkeypatch.setenv("SSCRE_PROVIDER_PRICING_SCHEDULE_ID", "prices")

    llm = CountingProviderLLMClient()
    embedding = CountingProviderEmbeddingClient()
    client = TestClient(
        create_app(
            llm_client=llm,
            embedding_client=embedding,
            semantic_enabled=True,
            semantic_strategy="C",
        )
    )
    response = client.post("/v1/query", json={"query": "pricing schedule wiring"})

    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics["pricing_schedule_id"] == "prices"
    assert metrics["cost_source"] == "provider_list_estimate"


def test_invalid_opt_in_configuration_fails_clearly(monkeypatch) -> None:
    _enable_provider(monkeypatch)
    monkeypatch.setenv("SSCRE_PROVIDER_ENDPOINT", "not-a-valid-url")

    with pytest.raises(ValueError, match="endpoint"):
        create_app(settings=Settings(semantic_enabled=False))


def test_exact_cache_hit_avoids_embedding_and_generation_provider_calls(
    monkeypatch,
) -> None:
    query = "Write Python code for binary search"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="cached answer",
            metadata=_python_search_meta(),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client, llm, embedding = _provider_test_client(
        monkeypatch,
        repository=cache,
        semantic_strategy="C",
        semantic_enabled=True,
    )

    body = client.post("/v1/query", json={"query": query}).json()

    assert body["source"] == "cache"
    assert llm.calls == 0
    assert embedding.calls == 0
    assert body["metrics"]["llm_attempts"] == 0
    assert body["metrics"]["embedding_attempts"] == 0


def test_semantic_cache_hit_records_embedding_and_avoids_generation(
    monkeypatch,
) -> None:
    cached_query = "explain vector search"
    cache = InMemoryExactCache(embedding_dimension=8)
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(cached_query.encode()).hexdigest(),
            normalized_query=cached_query,
            answer="semantic cached answer",
            embedding=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            embedding_model="embedding-test",
            embedding_dimension=8,
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    embedding = CountingProviderEmbeddingClient(
        vectors={
            "new wording for vector search": (
                1.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            )
        }
    )
    client, llm, embedding = _provider_test_client(
        monkeypatch,
        repository=cache,
        embedding_client=embedding,
        semantic_strategy="B",
        semantic_similarity_threshold=0.9,
    )

    body = client.post(
        "/v1/query",
        json={"query": "new wording for vector search"},
    ).json()

    assert body["source"] == "cache"
    assert llm.calls == 0
    assert embedding.calls == 1
    assert body["metrics"]["embedding_latency_ms"] >= 0
    assert body["metrics"]["embedding_input_tokens"] > 0
    assert body["metrics"]["provider_name"] == "test-provider"
    assert body["metrics"]["llm_attempts"] == 0


def test_semantic_miss_records_embedding_and_generation_measurements(
    monkeypatch,
) -> None:
    client, llm, embedding = _provider_test_client(
        monkeypatch,
        semantic_strategy="C",
    )

    body = client.post("/v1/query", json={"query": "fresh provider query"}).json()

    assert body["source"] == "generated"
    assert llm.calls == 1
    assert embedding.calls >= 1
    metrics = body["metrics"]
    assert metrics["embedding_latency_ms"] >= 0
    assert metrics["llm_input_tokens"] > 0
    assert metrics["provider_name"] == "test-provider"
    assert metrics["generation_model"] == "generation-test"
    assert metrics["embedding_model"] == "embedding-test"


def test_unsafe_candidate_causes_generation_through_configured_adapter(
    monkeypatch,
) -> None:
    query = "Write Python code for binary search"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="java cached answer",
            metadata=QueryMetadata(
                intent="code",
                domain="programming",
                constraints=(("language", "java"),),
                output_format="code",
            ),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    client, llm, _embedding = _provider_test_client(
        monkeypatch,
        repository=cache,
        semantic_strategy="C",
        semantic_enabled=False,
    )

    body = client.post("/v1/query", json={"query": query}).json()

    assert body["source"] == "generated"
    assert body["decision"] == "UNSAFE"
    assert llm.calls == 1
    assert body["metrics"]["generation_model"] == "generation-test"


def test_uncertain_candidate_causes_generation_through_configured_adapter(
    monkeypatch,
) -> None:
    query = "exact query with missing metadata"
    cache = InMemoryExactCache()
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(query.encode()).hexdigest(),
            normalized_query=query,
            answer="legacy answer",
        )
    )
    client, llm, _embedding = _provider_test_client(
        monkeypatch,
        repository=cache,
        semantic_strategy="C",
        semantic_enabled=False,
    )

    body = client.post("/v1/query", json={"query": query}).json()

    assert body["source"] == "generated"
    assert body["decision"] == "UNCERTAIN"
    assert llm.calls == 1


def test_generation_failure_preserves_workstream3_decision_trace(
    monkeypatch,
    caplog,
) -> None:
    query = "implement Python binary search"
    cache = InMemoryExactCache(embedding_dimension=8)
    cache.insert(
        CacheEntry(
            query_hash=hashlib.sha256(b"write Java code for binary search").hexdigest(),
            normalized_query="write Java code for binary search",
            answer="Java cached answer",
            embedding=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            embedding_model="embedding-test",
            embedding_dimension=8,
            metadata=QueryMetadata(
                intent="code",
                domain="programming",
                constraints=(("language", "java"),),
                output_format="code",
            ),
            ttl_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    caplog.set_level("INFO", logger="sscre")
    client, _llm, _embedding = _provider_test_client(
        monkeypatch,
        llm_client=SlowProviderLLMClient(),
        repository=cache,
        embedding_client=CountingProviderEmbeddingClient(
            vectors={query: (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)}
        ),
        settings=Settings(generation_timeout_seconds=1),
        semantic_strategy="C",
        semantic_similarity_threshold=0.9,
    )

    response = client.post("/v1/query", json={"query": query})

    assert response.status_code == 504
    assert response.json()["detail"] == "response generation timed out"
    assert response.headers["X-Request-ID"]
    assert not any(
        "generation_failed" in record.message for record in caplog.records
    )


def test_embedding_failure_preserves_failure_closed_semantic_behavior(
    monkeypatch,
) -> None:
    client, llm, _embedding = _provider_test_client(
        monkeypatch,
        embedding_client=CountingProviderEmbeddingClient(should_fail=True),
        semantic_strategy="C",
    )

    body = client.post("/v1/query", json={"query": "embedding provider failure"}).json()

    assert body["source"] == "generated"
    assert body["reason"] == "embedding_unavailable"
    assert llm.calls == 1


def test_post_generation_duplicate_write_path_retains_strategy_c_boundary(
    monkeypatch,
) -> None:
    class SlowCountingProviderLLM(SlowProviderLLMClient):
        def __init__(self) -> None:
            super().__init__()
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
                provider_name=self.provider_name,
                model_name=self.model_name,
                usage_source="provider_reported",
            )

    query = "Write Python code for provider duplicate recheck"
    client, llm, _embedding = _provider_test_client(
        monkeypatch,
        llm_client=SlowCountingProviderLLM(),
        repository=InMemoryExactCache(),
        semantic_strategy="C",
        semantic_enabled=False,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post("/v1/query", json={"query": query}),
                range(2),
            )
        )

    bodies = [response.json() for response in responses]
    assert sorted(body["source"] for body in bodies) == ["cache", "generated"]
    cached = next(body for body in bodies if body["source"] == "cache")
    assert cached["decision"] == "SAFE"
    assert cached["candidate_traces"][0]["stage"] == "compatibility"
    assert llm.calls == 1


def test_provider_mode_does_not_change_candidate_ordering_or_freshness_decisions(
    monkeypatch,
) -> None:
    cache = InMemoryExactCache(embedding_dimension=8)
    java_query = "write Java code for binary search"
    python_query = "write Python code for binary search"
    ttl = datetime.now(timezone.utc) + timedelta(hours=1)
    meta = lambda lang: QueryMetadata(
        intent="code",
        domain="programming",
        entities=("binary search", lang),
        constraints=(("language", lang),),
        output_format="code",
    )
    vector = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    python_vector = (0.99, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    for query, answer, metadata, embedding in (
        (java_query, "java answer", meta("java"), vector),
        (python_query, "python answer", meta("python"), python_vector),
    ):
        cache.insert(
            CacheEntry(
                query_hash=hashlib.sha256(query.encode()).hexdigest(),
                normalized_query=query,
                answer=answer,
                embedding=embedding,
                embedding_model="embedding-test",
                embedding_dimension=8,
                metadata=metadata,
                ttl_expires_at=ttl,
            )
        )
    vectors = {"implement Python binary search": vector}
    fake_body = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(
                config=EmbeddingConfig(model_name="embedding-test", dimension=8),
                vectors=vectors,
            ),
            semantic_strategy="C",
            semantic_similarity_threshold=0.9,
            semantic_top_k=2,
        )
    ).post("/v1/query", json={"query": "implement Python binary search"}).json()
    provider_body = _provider_test_client(
        monkeypatch,
        repository=cache,
        embedding_client=CountingProviderEmbeddingClient(vectors=vectors),
        semantic_strategy="C",
        semantic_similarity_threshold=0.9,
        semantic_top_k=2,
    )[0].post("/v1/query", json={"query": "implement Python binary search"}).json()

    assert fake_body["decision"] == provider_body["decision"] == "SAFE"
    assert fake_body["answer"] == provider_body["answer"] == "python answer"
    assert [
        (trace["decision"], trace["candidate_order"])
        for trace in fake_body["candidate_traces"]
    ] == [
        (trace["decision"], trace["candidate_order"])
        for trace in provider_body["candidate_traces"]
    ]

