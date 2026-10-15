"""Contract tests for the local sentence-transformers embedding provider."""

from __future__ import annotations

import hashlib
import math
import threading
import time

import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import InMemoryExactCache
from sscre.local_embedding import (
    DEFAULT_LOCAL_MODEL_DIMENSION,
    DEFAULT_LOCAL_MODEL_ID,
    LocalEmbeddingError,
    LocalEmbeddingProbeResult,
    LocalSentenceTransformerEmbeddingClient,
    build_local_embedding_smoke_artifact,
    build_ws1_local_embedding_provenance_record,
    create_local_embedding_client_from_mapping,
    hub_model_cache_directory_name,
    probe_local_embedding_environment,
    sentence_transformers_installed,
)


def _dim_vector(*head: float) -> list[float]:
    vector = [0.0] * DEFAULT_LOCAL_MODEL_DIMENSION
    for index, value in enumerate(head):
        vector[index] = value
    return vector


def _client(
    *,
    encoder,
    timeout_seconds: float = 5.0,
) -> LocalSentenceTransformerEmbeddingClient:
    return LocalSentenceTransformerEmbeddingClient(
        model_id=DEFAULT_LOCAL_MODEL_ID,
        encoder=encoder,
        timeout_seconds=timeout_seconds,
    )


def test_probe_reports_unavailable_when_package_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "sscre.local_embedding.sentence_transformers_installed",
        lambda: False,
    )
    probe = probe_local_embedding_environment()
    assert probe.status == "unavailable"
    assert probe.package_installed is False


def test_probe_reports_available_when_package_present() -> None:
    if not sentence_transformers_installed():
        pytest.skip("sentence_transformers not installed")
    probe = probe_local_embedding_environment()
    assert probe.status == "available"
    assert probe.expected_dimension == DEFAULT_LOCAL_MODEL_DIMENSION


def test_local_embedding_success_and_validation() -> None:
    vector = _dim_vector()
    vector[0] = 0.1
    vector[1] = 0.2
    client = _client(encoder=lambda text: vector)

    result = client.embed("hello world")

    assert result.model_name == DEFAULT_LOCAL_MODEL_ID
    assert len(result.vector) == DEFAULT_LOCAL_MODEL_DIMENSION
    assert result.provider_name == "local_sentence_transformer"
    assert result.usage_source == "estimated"
    client.close()


@pytest.mark.parametrize(
    "vector",
    [
        [0.1, 0.2],
        _dim_vector(0.1, math.nan),
        _dim_vector(True, 0.2),
    ],
)
def test_malformed_encoder_output_fails_closed(vector: list[float]) -> None:
    client = _client(encoder=lambda text: vector)

    with pytest.raises(LocalEmbeddingError) as exc_info:
        client.embed("query")

    assert exc_info.value.category in {"dimension_mismatch", "malformed_response"}


def test_encoder_failure_surfaces_as_provider_failure() -> None:
    def fail(_: str) -> list[float]:
        raise RuntimeError("model exploded")

    client = _client(encoder=fail)

    with pytest.raises(LocalEmbeddingError) as exc_info:
        client.embed("query")

    assert exc_info.value.category == "provider_failure"


def test_embed_timeout_is_bounded() -> None:
    def slow(_: str) -> list[float]:
        time.sleep(0.2)
        return _dim_vector()

    client = _client(encoder=slow, timeout_seconds=0.05)

    with pytest.raises(LocalEmbeddingError) as exc_info:
        client.embed("query")

    assert exc_info.value.category == "timeout"
    client.close()


def test_repeated_local_embedding_timeout_keeps_bounded_worker_threads() -> None:
    from concurrent.futures import ThreadPoolExecutor

    def slow(text: str) -> list[float]:
        if text != "stall":
            return _dim_vector(0.1)
        time.sleep(0.25)
        return _dim_vector(0.1)

    prefix = "sscre-ws3-embed-probe"
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=prefix)
    client = LocalSentenceTransformerEmbeddingClient(
        model_id=DEFAULT_LOCAL_MODEL_ID,
        encoder=slow,
        timeout_seconds=0.05,
        executor=executor,
    )

    for _ in range(4):
        with pytest.raises(LocalEmbeddingError) as exc_info:
            client.embed("stall")
        assert exc_info.value.category == "timeout"
        time.sleep(0.3)

    worker_threads = [
        thread for thread in threading.enumerate() if thread.name.startswith(prefix)
    ]
    assert len(worker_threads) <= 1

    result = client.embed("recover")
    assert len(result.vector) == DEFAULT_LOCAL_MODEL_DIMENSION
    executor.shutdown(wait=True)


def test_embedding_failure_does_not_cache_with_local_client() -> None:
    cache = InMemoryExactCache()
    client = LocalSentenceTransformerEmbeddingClient(
        model_id=DEFAULT_LOCAL_MODEL_ID,
        dimension=DEFAULT_LOCAL_MODEL_DIMENSION,
        encoder=lambda text: (_ for _ in ()).throw(RuntimeError("fail")),
        timeout_seconds=1.0,
    )
    app_client = TestClient(
        create_app(repository=cache, embedding_client=client)
    )
    query = "local provider failure must not cache"
    response = app_client.post("/v1/query", json={"query": query})

    assert response.status_code == 200
    assert response.json()["source"] == "generated"
    assert cache.get_by_query_hash(hashlib.sha256(query.encode()).hexdigest()) is None


def test_create_client_from_frozen_config_mapping(monkeypatch) -> None:
    monkeypatch.setattr(
        "sscre.local_embedding.probe_local_embedding_environment",
        lambda **kwargs: LocalEmbeddingProbeResult(
            status="available",
            model_id=DEFAULT_LOCAL_MODEL_ID,
            expected_dimension=DEFAULT_LOCAL_MODEL_DIMENSION,
            package_installed=True,
        ),
    )
    monkeypatch.setattr(
        "sscre.local_embedding._build_sentence_transformer_encoder",
        lambda *args, **kwargs: (lambda text: _dim_vector(0.5)),
    )
    monkeypatch.setattr(
        "sscre.local_embedding.sentence_transformers_installed",
        lambda: True,
    )
    client = create_local_embedding_client_from_mapping(
        {
            "enabled": True,
            "model_id": DEFAULT_LOCAL_MODEL_ID,
            "dimension": DEFAULT_LOCAL_MODEL_DIMENSION,
            "device": "cpu",
            "timeout_seconds": 5.0,
            "normalize_embeddings": True,
        }
    )
    assert client is not None
    assert client.config.dimension == DEFAULT_LOCAL_MODEL_DIMENSION


def test_hub_cache_directory_name_for_registered_model() -> None:
    assert hub_model_cache_directory_name(DEFAULT_LOCAL_MODEL_ID) == (
        "models--sentence-transformers--all-MiniLM-L6-v2"
    )


def test_ws1_provenance_record_is_redacted_without_smoke_load() -> None:
    record = build_ws1_local_embedding_provenance_record(run_smoke_load=False)
    serialized = str(record)
    assert "semantic validity smoke probe" not in serialized
    assert record["fake_embedding_scope"] == "tests_and_historical_artifacts_only"
    assert record["smoke_load"]["performed"] is False
    assert "validated_identity" in record
    assert record["validated_identity"]["dimension"] == DEFAULT_LOCAL_MODEL_DIMENSION


def test_smoke_artifact_never_includes_raw_query_text() -> None:
    artifact = build_local_embedding_smoke_artifact(
        sample_text="super secret benchmark query text"
    )
    serialized = str(artifact)
    assert "super secret benchmark query text" not in serialized


@pytest.mark.local_embedding
def test_live_smoke_artifact_passes_when_model_loads() -> None:
    if not sentence_transformers_installed():
        pytest.skip("sentence_transformers not installed")
    artifact = build_local_embedding_smoke_artifact()
    if artifact["status"] != "pass":
        pytest.skip(artifact.get("reason") or "local model unavailable")
    assert artifact["dimension"] == DEFAULT_LOCAL_MODEL_DIMENSION
