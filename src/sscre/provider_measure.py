"""Create a redacted real-provider measurement or unavailable record.

Live provider execution remains opt-in. When live mode is disabled, this
command creates an auditable unavailable artifact rather than silently
substituting deterministic fake-provider measurements.
"""

import argparse
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from sscre.benchmark import load_benchmark_jsonl
from sscre.embedding import EmbeddingResult
from sscre.llm import LLMResult
from sscre.pricing import (
    PricingSchedule,
    estimate_request_cost,
    load_pricing_schedule_from_json,
)
from sscre.provider_config import RealProviderConfig
from sscre.remote_embedding import OpenAICompatibleEmbeddingClient
from sscre.remote_llm import OpenAICompatibleLLMClient
from sscre.serialization import validate_redacted_report_payload


MEASUREMENT_SCHEMA_VERSION = "real-provider-measurement-1.0"
OPENAI_COMPATIBLE_API_VERSION = "openai-compatible-http-v1"
_FAILURE_CATEGORIES = (
    "authentication",
    "authorization",
    "malformed_response",
    "permanent_provider",
    "rate_limited",
    "timeout",
    "transient_provider",
    "validation",
)


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def _runtime_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": sys.version.split()[0]}
    for distribution in ("sscre", "fastapi", "pytest"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    versions["provider_sdk"] = None
    versions["provider_api"] = OPENAI_COMPATIBLE_API_VERSION
    return versions


def _empty_failure_counts() -> dict[str, int]:
    return {category: 0 for category in _FAILURE_CATEGORIES}


def _failure_count_payload(counts: dict[str, int]) -> list[dict[str, int | str]]:
    # Use list entries, not a dict keyed by category names. Keys such as
    # "authorization" or "token" violate validate_redacted_report_payload.
    return [
        {"category": category, "count": counts[category]}
        for category in _FAILURE_CATEGORIES
    ]


def _category_for_error(exc: BaseException) -> str:
    category = getattr(exc, "category", None)
    if isinstance(category, str) and category in _empty_failure_counts():
        return category
    return "transient_provider"


def _load_evaluation_config(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    return config


def build_unavailable_measurement(
    *,
    benchmark_path: Path,
    config_path: Path,
    reason: str,
) -> dict[str, Any]:
    config = _load_evaluation_config(config_path)
    records = load_benchmark_jsonl(benchmark_path)
    dataset_version = config.get("dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise ValueError("configuration requires dataset_version")
    return {
        "schema_version": MEASUREMENT_SCHEMA_VERSION,
        "status": "unavailable",
        "measurement_environment": "real_provider",
        "provider_available": False,
        "unavailable_reason": reason,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "runtime_versions": _runtime_versions(),
        "benchmark": {
            "path": str(benchmark_path).replace("\\", "/"),
            "dataset_version": dataset_version,
            "split": "development",
            "record_count": len(records),
        },
        "configuration": {
            "path": str(config_path).replace("\\", "/"),
            "config_version": config.get("config_version"),
            "pricing_schedule_id": config.get("pricing_schedule_id"),
        },
        "provider": None,
        "requests": {
            "count": 0,
            "generation": 0,
            "embedding": 0,
            "retries": 0,
        },
        "failures": _failure_count_payload(_empty_failure_counts()),
        "tokens": {
            "generation_input": None,
            "generation_output": None,
            "embedding_input": None,
            "usage_sources": {},
        },
        "latency_ms": {
            "generation": None,
            "embedding": None,
            "wrapper": None,
            "total": None,
        },
        "cost_usd": {
            "generation": None,
            "embedding": None,
            "retry": None,
            "wrapper": None,
            "total_estimated": None,
            "source": "unavailable",
        },
        "redaction": {
            "raw_prompts": False,
            "raw_answers": False,
            "credentials": False,
            "provider_payloads": False,
        },
        "limitations": [
            "No credentialed real-provider request was made.",
            "Synthetic measurements were not substituted.",
            "Quality, latency, token, and cost conclusions remain unavailable.",
        ],
    }


def build_live_measurement(
    *,
    benchmark_path: Path,
    config_path: Path,
    provider_config: RealProviderConfig,
    pricing_schedule: PricingSchedule | None = None,
    generate: Callable[[str], LLMResult] | None = None,
    embed: Callable[[str], EmbeddingResult] | None = None,
) -> dict[str, Any]:
    """Run one embedding and one generation call per benchmark record."""
    if provider_config.split != "development":
        raise ValueError("live measurement requires the development split")
    evaluation_config = _load_evaluation_config(config_path)
    dataset_version = evaluation_config.get("dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise ValueError("configuration requires dataset_version")
    if provider_config.dataset_version != dataset_version:
        raise ValueError("provider dataset_version must match evaluation config")

    llm_client = OpenAICompatibleLLMClient(provider_config) if generate is None else None
    embedding_client = (
        OpenAICompatibleEmbeddingClient(provider_config) if embed is None else None
    )
    generate_fn = generate or (lambda query: llm_client.generate(query))  # type: ignore[union-attr]
    embed_fn = embed or (lambda text: embedding_client.embed(text))  # type: ignore[union-attr]

    records = load_benchmark_jsonl(benchmark_path)
    failures = _empty_failure_counts()
    usage_sources: Counter[str] = Counter()
    generation_latencies: list[int] = []
    embedding_latencies: list[int] = []
    total_latencies: list[int] = []
    generation_input_tokens = 0
    generation_output_tokens = 0
    embedding_input_tokens = 0
    generation_calls = 0
    embedding_calls = 0
    generation_attempts = 0
    embedding_attempts = 0
    retry_total = 0
    cost_generation = 0.0
    cost_embedding = 0.0
    cost_wrapper = 0.0
    cost_retry_unavailable = False
    cost_total: float | None = 0.0

    for record in records:
        query = record.query_a
        record_started = datetime.now(timezone.utc)
        try:
            embedding_attempts += 1
            embedding_result = embed_fn(query)
            embedding_calls += 1
            embedding_latencies.append(embedding_result.latency_ms)
            embedding_input_tokens += embedding_result.input_tokens
            usage_sources[embedding_result.usage_source] += 1
            retry_total += embedding_result.retry_count

            generation_attempts += 1
            generation_result = generate_fn(query)
            generation_calls += 1
            generation_latencies.append(generation_result.latency_ms)
            generation_input_tokens += generation_result.input_tokens
            generation_output_tokens += generation_result.output_tokens
            usage_sources[generation_result.usage_source] += 1
            retry_total += generation_result.retry_count

            total_latencies.append(
                embedding_result.latency_ms + generation_result.latency_ms
            )
            if pricing_schedule is not None:
                breakdown = estimate_request_cost(
                    pricing_schedule,
                    generation_input_tokens=generation_result.input_tokens,
                    generation_output_tokens=generation_result.output_tokens,
                    embedding_input_tokens=embedding_result.input_tokens,
                    generation_retry_count=generation_result.retry_count,
                    embedding_retry_count=embedding_result.retry_count,
                    cache_lookup=False,
                    preprocessing=False,
                )
                if breakdown.generation_cost_usd is not None:
                    cost_generation += breakdown.generation_cost_usd
                if breakdown.embedding_cost_usd is not None:
                    cost_embedding += breakdown.embedding_cost_usd
                if breakdown.wrapper_cost_usd is not None:
                    cost_wrapper += breakdown.wrapper_cost_usd
                if breakdown.retry_cost_usd is None and (
                    generation_result.retry_count > 0
                    or embedding_result.retry_count > 0
                ):
                    cost_retry_unavailable = True
                    cost_total = None
                elif cost_total is not None and breakdown.total_estimated_cost_usd is not None:
                    cost_total += breakdown.total_estimated_cost_usd
        except Exception as exc:
            failures[_category_for_error(exc)] += 1
        finally:
            _ = record_started

    def _average(values: list[int]) -> int | None:
        return int(sum(values) / len(values)) if values else None

    cost_source = (
        pricing_schedule.source if pricing_schedule is not None else "unavailable"
    )
    return {
        "schema_version": MEASUREMENT_SCHEMA_VERSION,
        "status": "completed",
        "measurement_environment": "real_provider",
        "provider_available": True,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "runtime_versions": _runtime_versions(),
        "benchmark": {
            "path": str(benchmark_path).replace("\\", "/"),
            "dataset_version": dataset_version,
            "split": provider_config.split,
            "record_count": len(records),
        },
        "configuration": {
            "path": str(config_path).replace("\\", "/"),
            "config_version": evaluation_config.get("config_version"),
            "pricing_schedule_id": provider_config.pricing_schedule_id,
            "provider_config_version": provider_config.config_version,
        },
        "provider": {
            **provider_config.redacted(),
            "api_contract_version": OPENAI_COMPATIBLE_API_VERSION,
        },
        "requests": {
            "count": len(records),
            "attempted": generation_attempts + embedding_attempts,
            "successful": generation_calls + embedding_calls,
            "failed": (
                generation_attempts
                + embedding_attempts
                - generation_calls
                - embedding_calls
            ),
            "generation": generation_calls,
            "embedding": embedding_calls,
            "retries": retry_total,
        },
        "failures": _failure_count_payload(failures),
        "tokens": {
            "generation_input": generation_input_tokens,
            "generation_output": generation_output_tokens,
            "embedding_input": embedding_input_tokens,
            "usage_sources": dict(usage_sources),
        },
        "latency_ms": {
            "generation": _average(generation_latencies),
            "embedding": _average(embedding_latencies),
            "wrapper": 0,
            "total": _average(total_latencies),
        },
        "cost_usd": {
            "generation": round(cost_generation, 6) if pricing_schedule else None,
            "embedding": round(cost_embedding, 6) if pricing_schedule else None,
            "retry": None if cost_retry_unavailable else 0.0,
            "wrapper": round(cost_wrapper, 6) if pricing_schedule else None,
            "total_estimated": (
                round(cost_total, 6)
                if pricing_schedule is not None and cost_total is not None
                else None
            ),
            "source": cost_source,
        },
        "redaction": {
            "raw_prompts": False,
            "raw_answers": False,
            "credentials": False,
            "provider_payloads": False,
        },
        "limitations": [
            "Benchmark queries and generated answers are not stored in this artifact.",
            "Provider answer text may be nondeterministic across repeated runs.",
            "Connect and read timeouts share one urllib transport timeout budget.",
        ],
    }


def _resolve_pricing_schedule(
    provider_config: RealProviderConfig,
) -> PricingSchedule | None:
    pricing_path = os.getenv("SSCRE_PROVIDER_PRICING_JSON")
    if not pricing_path:
        return None
    return load_pricing_schedule_from_json(
        Path(pricing_path),
        schedule_id=provider_config.pricing_schedule_id,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write a redacted real-provider measurement status artifact"
    )
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    live_enabled = os.environ.get("SSCRE_REAL_PROVIDER_LIVE", "").lower() == "true"
    provider_config = RealProviderConfig.from_environment()
    if live_enabled:
        if provider_config is None:
            raise SystemExit(
                "SSCRE_REAL_PROVIDER=true and valid provider configuration are "
                "required when SSCRE_REAL_PROVIDER_LIVE=true"
            )
        if not provider_config.credential_configured:
            raise SystemExit("SSCRE_PROVIDER_CREDENTIAL is required for live measurement")
        payload = build_live_measurement(
            benchmark_path=args.benchmark,
            config_path=args.config,
            provider_config=provider_config,
            pricing_schedule=_resolve_pricing_schedule(provider_config),
        )
    else:
        payload = build_unavailable_measurement(
            benchmark_path=args.benchmark,
            config_path=args.config,
            reason="live_opt_in_missing",
        )

    validate_redacted_report_payload(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
