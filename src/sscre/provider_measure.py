"""Create a redacted real-provider measurement or unavailable record.

Live provider execution remains opt-in. Until a provider run is explicitly
enabled, this command creates an auditable unavailable artifact rather than
silently substituting deterministic fake-provider measurements.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any

from sscre.benchmark import load_benchmark_jsonl
from sscre.provider_config import RealProviderConfig


MEASUREMENT_SCHEMA_VERSION = "real-provider-measurement-1.0"


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


def build_unavailable_measurement(
    *,
    benchmark_path: Path,
    config_path: Path,
    reason: str,
) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
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
    if live_enabled and provider_config is not None:
        raise SystemExit(
            "live provider execution is not implemented by the unavailable-only "
            "measurement command; use the provider smoke test or add the "
            "credentialed runner before making a real measurement claim"
        )
    reason = (
        "live_opt_in_missing"
        if not live_enabled
        else "provider_configuration_unavailable"
    )
    payload = build_unavailable_measurement(
        benchmark_path=args.benchmark,
        config_path=args.config,
        reason=reason,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
