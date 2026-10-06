import os
import pytest
import subprocess
import sys
from pathlib import Path

from sscre.embedding import (
    EmbeddingConfig,
    EmbeddingProviderError,
    EmbeddingResult,
    EmbeddingValidationError,
    FakeEmbeddingClient,
    validate_embedding_result,
    validate_embedding_text,
)


def test_embedding_result_accepts_valid_accounting_data() -> None:
    result = EmbeddingResult(
        vector=(0.1, -0.2),
        model_name="test-embedding",
        input_tokens=3,
        latency_ms=5,
    )

    assert result.vector == (0.1, -0.2)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("vector", ()),
        ("model_name", ""),
        ("input_tokens", -1),
        ("latency_ms", -1),
    ],
)
def test_embedding_result_rejects_invalid_values(field: str, value) -> None:
    values = {
        "vector": (0.1,),
        "model_name": "test-embedding",
        "input_tokens": 3,
        "latency_ms": 5,
    }
    values[field] = value

    with pytest.raises(EmbeddingValidationError):
        EmbeddingResult(**values)


def test_embedding_result_rejects_non_finite_values() -> None:
    with pytest.raises(EmbeddingValidationError):
        EmbeddingResult(
            vector=(float("nan"),),
            model_name="test-embedding",
            input_tokens=1,
            latency_ms=0,
        )


def test_embedding_text_must_not_be_empty() -> None:
    with pytest.raises(EmbeddingValidationError):
        validate_embedding_text("  ")


def test_embedding_result_must_match_configured_model_and_dimension() -> None:
    config = EmbeddingConfig(model_name="test-embedding", dimension=2)
    result = EmbeddingResult(
        vector=(0.1, 0.2),
        model_name="test-embedding",
        input_tokens=2,
        latency_ms=1,
    )

    validate_embedding_result(result, config)


@pytest.mark.parametrize(
    ("model_name", "vector"),
    [
        ("other-embedding", (0.1, 0.2)),
        ("test-embedding", (0.1,)),
    ],
)
def test_embedding_result_rejects_config_mismatch(
    model_name: str,
    vector: tuple[float, ...],
) -> None:
    config = EmbeddingConfig(model_name="test-embedding", dimension=2)
    result = EmbeddingResult(
        vector=vector,
        model_name=model_name,
        input_tokens=2,
        latency_ms=1,
    )

    with pytest.raises(EmbeddingValidationError):
        validate_embedding_result(result, config)


def test_fake_embedding_is_deterministic_for_identical_text() -> None:
    first = FakeEmbeddingClient().embed("same query")
    second = FakeEmbeddingClient().embed("same query")

    assert first.vector == second.vector
    assert first.model_name == "fake-embedding"


def test_fake_embedding_is_stable_across_processes() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = (
        "from sscre.embedding import FakeEmbeddingClient; "
        "print(FakeEmbeddingClient().embed('same query').vector)"
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(project_root / "src"),
    }

    first = subprocess.check_output(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=environment,
        text=True,
    )
    second = subprocess.check_output(
        [sys.executable, "-c", script],
        cwd=project_root,
        env=environment,
        text=True,
    )

    assert first == second


def test_fake_embedding_supports_controlled_vectors_and_accounting() -> None:
    client = FakeEmbeddingClient(
        config=EmbeddingConfig(model_name="test-embedding", dimension=2),
        vectors={
            "similar query": (1.0, 0.0),
            "different query": (0.0, 1.0),
        },
        input_tokens=7,
        latency_ms=12,
    )

    similar = client.embed("similar query")
    different = client.embed("different query")

    assert similar.vector == (1.0, 0.0)
    assert different.vector == (0.0, 1.0)
    assert similar.input_tokens == 7
    assert similar.latency_ms == 12


def test_fake_embedding_failure_is_explicit() -> None:
    client = FakeEmbeddingClient(should_fail=True)

    with pytest.raises(EmbeddingProviderError):
        client.embed("query")
