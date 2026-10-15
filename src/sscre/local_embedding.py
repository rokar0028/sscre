"""Local sentence-transformers embedding provider (Phase 4 semantic validity)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import BoundedSemaphore
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from sscre.dependency_runtime import DependencyTimeoutError, run_with_timeout
from sscre.embedding import (
    EmbeddingConfig,
    EmbeddingProviderError,
    EmbeddingResult,
    EmbeddingValidationError,
    validate_embedding_result,
    validate_embedding_text,
)

LOCAL_EMBEDDING_SCHEMA_VERSION = "phase4-local-embedding-smoke-1.0"
WS1_LOCAL_EMBEDDING_PROVENANCE_SCHEMA_VERSION = "ws1-local-embedding-provenance-1.0"
DEFAULT_LOCAL_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_LOCAL_MODEL_DIMENSION = 384
DEFAULT_NORMALIZE_EMBEDDINGS = True

Encoder = Callable[[str], Sequence[float]]

_LOCAL_MODEL_SPECS: dict[str, dict[str, object]] = {
    DEFAULT_LOCAL_MODEL_ID: {
        "dimension": DEFAULT_LOCAL_MODEL_DIMENSION,
        "license": "Apache-2.0",
        "provider_type": "local_sentence_transformer",
        "normalization": "l2_unit_vectors_when_normalize_embeddings_true",
        "dtype": "float32",
    },
}


class LocalEmbeddingError(EmbeddingProviderError):
    """Bounded local embedding failure."""

    def __init__(self, category: str, message: str = "local embedding failed") -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class LocalEmbeddingProbeResult:
    status: Literal["available", "unavailable"]
    model_id: str
    expected_dimension: int
    package_installed: bool
    reason: str | None = None
    device: str | None = None
    provider_type: str | None = None
    license: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "model_id": self.model_id,
            "expected_dimension": self.expected_dimension,
            "package_installed": self.package_installed,
            "reason": self.reason,
            "device": self.device,
            "provider_type": self.provider_type,
            "license": self.license,
        }


def local_model_dimension(model_id: str) -> int:
    spec = _LOCAL_MODEL_SPECS.get(model_id)
    if spec is None:
        raise ValueError(f"unsupported local embedding model_id {model_id!r}")
    dimension = spec.get("dimension")
    if not isinstance(dimension, int) or dimension <= 0:
        raise ValueError(f"invalid dimension registry for {model_id!r}")
    return dimension


def sentence_transformers_installed() -> bool:
    return importlib.util.find_spec("sentence_transformers") is not None


def hub_model_cache_directory_name(model_id: str) -> str:
    return "models--" + model_id.replace("/", "--")


def huggingface_hub_cache_root() -> Path | None:
    """Resolve the Hugging Face hub cache directory without importing hub libraries."""
    explicit = os.environ.get("HF_HUB_CACHE")
    if explicit:
        return Path(explicit).expanduser()
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home).expanduser() / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def local_model_weights_cached(model_id: str) -> bool:
    """True when at least one snapshot exists for the model in the local HF hub cache."""
    cache_root = huggingface_hub_cache_root()
    snapshots = (
        cache_root
        / hub_model_cache_directory_name(model_id)
        / "snapshots"
    )
    if not snapshots.is_dir():
        return False
    return any(child.is_dir() for child in snapshots.iterdir())


def optional_distribution_version(distribution_name: str) -> str | None:
    try:
        return importlib.metadata.version(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def probe_local_embedding_environment(
    *,
    model_id: str = DEFAULT_LOCAL_MODEL_ID,
    device: str = "cpu",
) -> LocalEmbeddingProbeResult:
    """Inspect whether the approved local model can load without downloading weights."""
    try:
        expected_dimension = local_model_dimension(model_id)
    except ValueError as exc:
        return LocalEmbeddingProbeResult(
            status="unavailable",
            model_id=model_id,
            expected_dimension=0,
            package_installed=sentence_transformers_installed(),
            reason=str(exc),
        )

    if not sentence_transformers_installed():
        return LocalEmbeddingProbeResult(
            status="unavailable",
            model_id=model_id,
            expected_dimension=expected_dimension,
            package_installed=False,
            reason="sentence_transformers package is not installed",
        )

    spec = _LOCAL_MODEL_SPECS[model_id]
    return LocalEmbeddingProbeResult(
        status="available",
        model_id=model_id,
        expected_dimension=expected_dimension,
        package_installed=True,
        device=device,
        provider_type=str(spec["provider_type"]),
        license=str(spec["license"]),
    )


def _build_sentence_transformer_encoder(
    model_id: str,
    *,
    device: str,
    normalize_embeddings: bool,
) -> Encoder:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_id, device=device)

    def encode(text: str) -> Sequence[float]:
        vector = model.encode(
            text,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vector.tolist()

    return encode


class LocalSentenceTransformerEmbeddingClient:
    """Fixed-dimension local embeddings via sentence-transformers."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_LOCAL_MODEL_ID,
        dimension: int | None = None,
        device: str = "cpu",
        normalize_embeddings: bool = DEFAULT_NORMALIZE_EMBEDDINGS,
        timeout_seconds: float = 30.0,
        encoder: Encoder | None = None,
        batch_behavior: str = "single_query_per_embed_call",
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        expected_dimension = local_model_dimension(model_id)
        resolved_dimension = dimension if dimension is not None else expected_dimension
        if resolved_dimension != expected_dimension:
            raise ValueError(
                "dimension must match the registered local model dimension"
            )
        self._model_id = model_id
        self._device = device
        self._normalize_embeddings = normalize_embeddings
        self._timeout_seconds = timeout_seconds
        self._batch_behavior = batch_behavior
        self._encoder = encoder or _build_sentence_transformer_encoder(
            model_id,
            device=device,
            normalize_embeddings=normalize_embeddings,
        )
        self._config = EmbeddingConfig(
            model_name=model_id,
            dimension=resolved_dimension,
        )
        if executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="sscre-local-embedding",
            )
            self._owns_executor = True
        else:
            self._executor = executor
            self._owns_executor = False
        self._dependency_slots = BoundedSemaphore(1)

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

    @property
    def config(self) -> EmbeddingConfig:
        return self._config

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def device(self) -> str:
        return self._device

    @property
    def normalize_embeddings(self) -> bool:
        return self._normalize_embeddings

    @property
    def batch_behavior(self) -> str:
        return self._batch_behavior

    def embed(self, text: str) -> EmbeddingResult:
        text = validate_embedding_text(text)
        started_at = perf_counter()
        try:
            raw_vector = run_with_timeout(
                self._executor,
                lambda: self._encoder(text),
                self._timeout_seconds,
                "local_embedding",
                self._dependency_slots,
            )
        except DependencyTimeoutError as exc:
            if exc.category in {"capacity_exhausted", "dependency_timeout"}:
                raise LocalEmbeddingError("timeout") from exc
            raise LocalEmbeddingError("provider_failure") from exc
        except LocalEmbeddingError:
            raise
        except Exception as exc:
            raise LocalEmbeddingError("provider_failure") from exc

        vector = _coerce_vector(raw_vector, self._config.dimension)
        result = EmbeddingResult(
            vector=vector,
            model_name=self._config.model_name,
            input_tokens=len(text.split()),
            latency_ms=int((perf_counter() - started_at) * 1000),
            provider_name="local_sentence_transformer",
            usage_source="estimated",
        )
        validate_embedding_result(result, self._config)
        return result


def _coerce_vector(
    raw_vector: Sequence[float],
    dimension: int,
) -> tuple[float, ...]:
    if len(raw_vector) != dimension:
        raise LocalEmbeddingError("dimension_mismatch")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in raw_vector
    ):
        raise LocalEmbeddingError("malformed_response")
    return tuple(float(value) for value in raw_vector)


def vector_fingerprint_sha256(vector: Sequence[float]) -> str:
    """Non-reversible fingerprint for smoke artifacts (no raw vector export)."""
    digest = hashlib.sha256(
        ",".join(f"{float(value):.8f}" for value in vector).encode("utf-8")
    ).hexdigest()
    return digest


def build_ws1_local_embedding_provenance_record(
    *,
    model_id: str = DEFAULT_LOCAL_MODEL_ID,
    device: str = "cpu",
    run_smoke_load: bool = False,
) -> dict[str, Any]:
    """Redacted WS1 provenance record (no query text, tokens, or credentials)."""
    try:
        expected_dimension = local_model_dimension(model_id)
        spec = _LOCAL_MODEL_SPECS[model_id]
    except (ValueError, KeyError):
        return {
            "schema_version": WS1_LOCAL_EMBEDDING_PROVENANCE_SCHEMA_VERSION,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git_commit(),
            "status": "unavailable",
            "reason": f"unsupported or unregistered model_id {model_id!r}",
            "fake_embedding_scope": "tests_and_historical_artifacts_only",
        }

    package_installed = sentence_transformers_installed()
    weights_cached_before = (
        local_model_weights_cached(model_id) if package_installed else False
    )
    if not package_installed:
        weights_state = "unavailable"
        replayability = "not_claimed_optional_extra_not_installed"
    elif weights_cached_before:
        weights_state = "cached_on_disk"
        replayability = "replayable_when_optional_extra_installed"
    else:
        weights_state = "not_cached_on_disk"
        replayability = "not_claimed_until_weights_cached_or_smoke_load_passes"

    record: dict[str, Any] = {
        "schema_version": WS1_LOCAL_EMBEDDING_PROVENANCE_SCHEMA_VERSION,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "status": "probe_only",
        "validated_identity": {
            "model_id": model_id,
            "short_name": model_id.split("/", 1)[-1],
            "dimension": expected_dimension,
            "license": spec["license"],
            "provider_type": spec["provider_type"],
            "dtype": spec["dtype"],
            "normalize_embeddings_default": DEFAULT_NORMALIZE_EMBEDDINGS,
            "device_declared": device,
        },
        "optional_install": {
            "extra": "local-embeddings",
            "command": 'python -m pip install ".[local-embeddings]"',
        },
        "packages": {
            "sentence_transformers": {
                "installed": package_installed,
                "version": optional_distribution_version("sentence-transformers"),
            },
            "torch": {
                "installed": importlib.util.find_spec("torch") is not None,
                "version": optional_distribution_version("torch"),
            },
        },
        "weights": {
            "state": weights_state,
            "cached_before_smoke": weights_cached_before,
            "replayability": replayability,
            "source": "huggingface_hub_local_cache",
            "weight_license": spec["license"],
        },
        "smoke_load": {"performed": False},
        "fake_embedding_scope": "tests_and_historical_artifacts_only",
        "phase4_references": {
            "gate_json": "benchmarks/semantic-validity-local-embedding-gate.json",
            "smoke_artifact": (
                "artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json"
            ),
        },
        "probe": probe_local_embedding_environment(
            model_id=model_id,
            device=device,
        ).to_dict(),
    }

    if not package_installed:
        record["status"] = "unavailable"
        record["reason"] = "sentence_transformers package is not installed"
        return record

    if not run_smoke_load:
        record["reason"] = (
            "probe and cache inspection only; smoke load not requested"
        )
        return record

    smoke = build_local_embedding_smoke_artifact(model_id=model_id, device=device)
    record["smoke_load"] = {
        "performed": True,
        "status": smoke.get("status"),
        "reason": smoke.get("reason"),
        "latency_ms": smoke.get("latency_ms"),
        "vector_fingerprint_sha256": smoke.get("vector_fingerprint_sha256"),
    }
    if smoke.get("status") == "pass":
        if weights_cached_before:
            record["weights"]["state"] = "cached_on_disk"
        else:
            record["weights"]["state"] = "downloaded_during_smoke_load"
        record["weights"]["replayability"] = (
            "replayable_when_optional_extra_installed"
        )
        record["status"] = "smoke_pass"
        record["reason"] = None
    else:
        record["status"] = "smoke_failed"
        record["reason"] = smoke.get("reason")
        if not weights_cached_before:
            record["weights"]["replayability"] = "not_claimed_smoke_did_not_pass"
    return record


def build_local_embedding_smoke_artifact(
    *,
    protocol_id: str = "P4-SEMVALID",
    config_path: str = "experiments/semantic-validity-evaluation-config-v1.json",
    model_id: str = DEFAULT_LOCAL_MODEL_ID,
    device: str = "cpu",
    sample_text: str = "semantic validity smoke probe",
) -> dict[str, Any]:
    probe = probe_local_embedding_environment(model_id=model_id, device=device)
    artifact: dict[str, Any] = {
        "schema_version": LOCAL_EMBEDDING_SCHEMA_VERSION,
        "protocol_id": protocol_id,
        "config_path": config_path,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "probe": probe.to_dict(),
        "status": "unavailable",
        "reason": probe.reason,
    }
    if probe.status != "available":
        return artifact

    try:
        client = LocalSentenceTransformerEmbeddingClient(
            model_id=model_id,
            device=device,
        )
        result = client.embed(sample_text)
    except (LocalEmbeddingError, EmbeddingValidationError) as exc:
        artifact["reason"] = str(exc)
        return artifact

    spec = _LOCAL_MODEL_SPECS[model_id]
    artifact.update(
        {
            "status": "pass",
            "reason": None,
            "provider_type": spec["provider_type"],
            "model_id": model_id,
            "dimension": client.config.dimension,
            "normalize_embeddings": client.normalize_embeddings,
            "dtype": spec["dtype"],
            "device": client.device,
            "batch_behavior": client.batch_behavior,
            "latency_ms": result.latency_ms,
            "usage_source": result.usage_source,
            "vector_fingerprint_sha256": vector_fingerprint_sha256(result.vector),
            "failure_behavior": "raises_local_embedding_error_no_cache_without_valid_vector",
        }
    )
    return artifact


def write_local_embedding_smoke_artifact(
    path: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = build_local_embedding_smoke_artifact(**kwargs)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def create_local_embedding_client_from_mapping(
    mapping: Mapping[str, Any] | None,
) -> LocalSentenceTransformerEmbeddingClient | None:
    """Build a local client when config defines local_embedding_provider."""
    if mapping is None:
        return None
    if not isinstance(mapping, dict):
        raise ValueError("local_embedding_provider must be an object")
    if mapping.get("enabled") is not True:
        return None
    model_id = mapping.get("model_id", DEFAULT_LOCAL_MODEL_ID)
    if not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("local_embedding_provider.model_id must be a non-empty string")
    dimension = mapping.get("dimension")
    if dimension is not None and (
        isinstance(dimension, bool)
        or not isinstance(dimension, int)
        or dimension <= 0
    ):
        raise ValueError("local_embedding_provider.dimension must be a positive integer")
    device = mapping.get("device", "cpu")
    if not isinstance(device, str) or not device.strip():
        raise ValueError("local_embedding_provider.device must be a non-empty string")
    timeout_seconds = mapping.get("timeout_seconds", 30.0)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
    ):
        raise ValueError("local_embedding_provider.timeout_seconds must be positive")
    normalize = mapping.get("normalize_embeddings", DEFAULT_NORMALIZE_EMBEDDINGS)
    if not isinstance(normalize, bool):
        raise ValueError("local_embedding_provider.normalize_embeddings must be boolean")
    probe = probe_local_embedding_environment(model_id=model_id, device=device)
    if probe.status != "available":
        raise LocalEmbeddingError(
            "unavailable",
            probe.reason or "local embedding environment unavailable",
        )
    return LocalSentenceTransformerEmbeddingClient(
        model_id=model_id,
        dimension=dimension,
        device=device,
        normalize_embeddings=normalize,
        timeout_seconds=float(timeout_seconds),
    )
