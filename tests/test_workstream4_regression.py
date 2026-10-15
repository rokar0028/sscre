"""Workstream 4 regression guards for fake providers and synthetic evidence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sscre.app import create_app
from sscre.cache import InMemoryExactCache
from sscre.config import Settings
from sscre.embedding import FakeEmbeddingClient
from sscre.llm import MockLLMClient
from sscre.provider_config import RealProviderConfig
from sscre.provider_measure import MEASUREMENT_SCHEMA_VERSION
from sscre.serialization import serialize_safety_result_for_boundary
from sscre.safety import CandidateTrace, resolve_candidate_traces


ROOT = Path(__file__).resolve().parents[1]
DEVELOPMENT_ARTIFACT = ROOT / "artifacts" / "evaluation" / "workstream3-development.json"
EVALUATION_CONFIG = ROOT / "experiments" / "evaluation_config.json"
DEVELOPMENT_BENCHMARK = ROOT / "benchmarks" / "development.jsonl"


def test_fake_provider_query_remains_deterministic_for_same_input() -> None:
    client = TestClient(create_app(semantic_enabled=False))
    query = {"query": "deterministic fake provider regression"}

    first = client.post("/v1/query", json=query).json()
    second = client.post("/v1/query", json=query).json()

    assert first["source"] == second["source"] == "generated"
    assert first["answer"] == second["answer"]
    assert first["metrics"]["provider_name"] == "synthetic"
    assert first["metrics"]["generation_model"] == "mock"


def test_workstream1_decision_vocabulary_regression() -> None:
    for decision in ("SAFE", "UNSAFE", "UNCERTAIN"):
        payload = serialize_safety_result_for_boundary(
            resolve_candidate_traces(
                (CandidateTrace("hash-1", 0.9, decision, "similarity_below_threshold"),)
            )
        )
        assert payload["decision"] == decision


def test_workstream3_embedding_failure_still_fails_closed_without_cache() -> None:
    cache = InMemoryExactCache()
    client = TestClient(
        create_app(
            repository=cache,
            embedding_client=FakeEmbeddingClient(should_fail=True),
            semantic_strategy="C",
        )
    )
    body = client.post("/v1/query", json={"query": "embedding failure regression"}).json()

    assert body["source"] == "generated"
    assert body["reason"] == "embedding_unavailable"
    assert cache.storage_stats().entries == 0


def test_default_request_path_does_not_open_remote_urls(monkeypatch) -> None:
    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("default regression path must not perform network I/O")

    monkeypatch.setattr("sscre.remote_llm.urlopen", fail_urlopen)

    response = TestClient(create_app()).post(
        "/v1/query",
        json={"query": "no remote transport on default path"},
    )

    assert response.status_code == 200


def test_real_provider_mode_stays_disabled_without_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("SSCRE_REAL_PROVIDER", raising=False)
    monkeypatch.delenv("SSCRE_PROVIDER", raising=False)

    assert RealProviderConfig.from_environment() is None
    client = TestClient(create_app())
    assert client.post("/v1/query", json={"query": "still synthetic"}).json()["metrics"][
        "provider_name"
    ] == "synthetic"


def test_production_profile_still_requires_explicit_provider_clients() -> None:
    with pytest.raises(ValueError, match="provider clients"):
        create_app(
            repository=InMemoryExactCache(),
            settings=Settings(
                runtime_profile="production",
                database_url="postgresql://localhost/sscre",
                admin_token="a-production-token",
                admin_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                api_exposure_mode="external",
                client_auth_json="registry-placeholder.json",
                rate_limit_requests_per_minute=100,
                tenant_provider_budget_per_minute=100,
            ),
        )


def test_production_profile_rejects_injected_fake_generation_client() -> None:
    production = Settings(
        runtime_profile="production",
        database_url="postgresql://localhost/sscre",
        admin_token="a-production-token",
        admin_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        api_exposure_mode="external",
        client_auth_json=str(ROOT / "experiments/client_auth_registry_sample.json"),
        rate_limit_requests_per_minute=100,
        tenant_provider_budget_per_minute=100,
        semantic_enabled=False,
    )
    with pytest.raises(ValueError, match="fake providers are unavailable"):
        create_app(
            llm_client=MockLLMClient(),
            repository=InMemoryExactCache(),
            settings=production,
        )


@pytest.mark.skipif(not DEVELOPMENT_ARTIFACT.is_file(), reason="development artifact missing")
def test_saved_development_evaluation_report_remains_synthetic() -> None:
    payload = json.loads(DEVELOPMENT_ARTIFACT.read_text(encoding="utf-8"))
    encoded = json.dumps(payload)

    assert payload["baseline"] == "compatibility-cache"
    assert payload["estimated_cost_usd"] == 0.0
    assert '"measurement_environment": "real_provider"' not in encoded
    assert MEASUREMENT_SCHEMA_VERSION not in encoded


def test_evaluate_cli_report_remains_synthetic_not_real_provider(tmp_path: Path) -> None:
    from sscre.evaluate import main

    output = tmp_path / "regression-development.json"
    assert main(
        [
            "--benchmark",
            str(DEVELOPMENT_BENCHMARK),
            "--config",
            str(EVALUATION_CONFIG),
            "--baseline",
            "compatibility-cache",
            "--split",
            "development",
            "--output",
            str(output),
        ]
    ) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    encoded = json.dumps(payload)

    assert payload["estimated_cost_usd"] == 0.0
    assert '"measurement_environment": "real_provider"' not in encoded
    assert MEASUREMENT_SCHEMA_VERSION not in encoded
