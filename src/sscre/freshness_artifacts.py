"""Workstream 6 evaluation artifact packaging (Step 10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from sscre.benchmark_splits import file_sha256
from sscre.freshness_evaluation import (
    FRESHNESS_EVALUATION_SCHEMA_VERSION,
    validate_freshness_experiment_report,
)
from sscre.freshness_invalidation import (
    INVALIDATION_EXPERIMENT_VERSION,
    validate_invalidation_artifact,
)
from sscre.serialization import validate_redacted_report_payload

FRESHNESS_ARTIFACT_PACKAGE_VERSION = "1.0"

STANDARD_ARTIFACT_PATHS = {
    "development": "artifacts/evaluation/workstream6-development-freshness.json",
    "held-out": "artifacts/evaluation/workstream6-held-out-freshness.json",
    "invalidation": "artifacts/evaluation/workstream6-invalidation.json",
}

STANDARD_DEVELOPMENT_BENCHMARK = Path("benchmarks/development.jsonl")
STANDARD_HELD_OUT_BENCHMARK = Path("benchmarks/held_out_test.jsonl")


def development_benchmark_path_for_split(benchmark_path: Path, split: str) -> Path:
    """Return the development JSONL path paired with a split benchmark file."""
    if split == "development":
        return benchmark_path
    if split == "held-out":
        if benchmark_path.name == STANDARD_DEVELOPMENT_BENCHMARK.name:
            return benchmark_path
        sibling = benchmark_path.with_name(STANDARD_DEVELOPMENT_BENCHMARK.name)
        if sibling.is_file():
            return sibling
        standard = STANDARD_DEVELOPMENT_BENCHMARK
        if standard.is_file():
            return standard
        raise ValueError(
            "held-out freshness artifacts require a development benchmark JSONL "
            f"(expected {STANDARD_DEVELOPMENT_BENCHMARK.as_posix()})"
        )
    raise ValueError(f"unsupported freshness split: {split!r}")


def build_regeneration_command(
    *,
    benchmark_path: Path,
    config_path: Path,
    split: str,
    output_path: Path,
    production: bool,
    selected_policy: str | None,
) -> str:
    parts = [
        "python -m sscre.freshness_evaluate",
        f'--benchmark "{benchmark_path.as_posix()}"',
        f'--config "{config_path.as_posix()}"',
        f'--split {split}',
        f'--output "{output_path.as_posix()}"',
    ]
    if production:
        parts.append("--production")
    if selected_policy:
        parts.append(f'--selected-policy "{selected_policy}"')
    return " ".join(parts)


def summarize_unavailable_fields(freshness_block: Mapping[str, object]) -> list[dict[str, str]]:
    summaries: list[dict[str, str]] = []
    for item in freshness_block.get("limitations", ()):
        if isinstance(item, str) and item.strip():
            summaries.append(
                {
                    "field": item,
                    "status": "unavailable",
                    "consequence": "claim omitted or marked unavailable in this artifact",
                }
            )
    held_out_scope = freshness_block.get("held_out_freshness_scope")
    if isinstance(held_out_scope, Mapping):
        for class_name in ("semi_dynamic", "dynamic"):
            if held_out_scope.get(class_name) == "unavailable":
                summaries.append(
                    {
                        "field": f"held_out_{class_name}_freshness",
                        "status": "unavailable",
                        "consequence": str(
                            held_out_scope.get("reason", "Option A scope")
                        ),
                    }
                )
    stale = freshness_block.get("stale_exposure_accounting")
    if isinstance(stale, Mapping):
        answer_level = stale.get("answer_level_stale_exposure")
        if isinstance(answer_level, Mapping):
            if answer_level.get("status") == "unavailable":
                summaries.append(
                    {
                        "field": "answer_level_stale_exposure",
                        "status": "unavailable",
                        "consequence": str(answer_level.get("reason", "")),
                    }
                )
    return summaries


def attach_freshness_artifact_metadata(
    report: Mapping[str, object],
    *,
    config_path: Path,
    benchmark_path: Path,
    split: str,
    production: bool,
    selected_policy_arg: str | None,
) -> dict[str, object]:
    result = dict(report)
    freshness = result.get("freshness_experiment")
    if not isinstance(freshness, Mapping):
        raise ValueError("report must include freshness_experiment")

    output_path = STANDARD_ARTIFACT_PATHS.get(split, f"artifacts/evaluation/ws6-{split}.json")
    regeneration_commands = [
        build_regeneration_command(
            benchmark_path=benchmark_path,
            config_path=config_path,
            split=split,
            output_path=Path(output_path),
            production=production,
            selected_policy=None,
        )
    ]
    if split == "held-out":
        development_benchmark = development_benchmark_path_for_split(
            benchmark_path,
            "held-out",
        )
        regeneration_commands = [
            build_regeneration_command(
                benchmark_path=development_benchmark,
                config_path=config_path,
                split="development",
                output_path=Path(STANDARD_ARTIFACT_PATHS["development"]),
                production=False,
                selected_policy=None,
            ),
            build_regeneration_command(
                benchmark_path=benchmark_path,
                config_path=config_path,
                split="held-out",
                output_path=Path(STANDARD_ARTIFACT_PATHS["held-out"]),
                production=True,
                selected_policy=STANDARD_ARTIFACT_PATHS["development"],
            ),
        ]

    result["freshness_artifact_metadata"] = {
        "artifact_package_version": FRESHNESS_ARTIFACT_PACKAGE_VERSION,
        "freshness_evaluation_schema_version": result.get(
            "freshness_evaluation_schema_version",
            FRESHNESS_EVALUATION_SCHEMA_VERSION,
        ),
        "statistics_schema_version": freshness.get(
            "freshness_statistics_schema_version"
        ),
        "measurement_environment": result.get(
            "measurement_environment",
            "synthetic_replay",
        ),
        "config_path": config_path.as_posix(),
        "config_sha256": file_sha256(config_path),
        "benchmark_path": benchmark_path.as_posix(),
        "regeneration_commands": regeneration_commands,
        "companion_artifact_paths": {
            "invalidation": STANDARD_ARTIFACT_PATHS["invalidation"],
        },
        "unavailable_fields_summary": summarize_unavailable_fields(freshness),
    }
    return result


def build_invalidation_sidecar_artifact(
    report: Mapping[str, object],
    *,
    source_artifact_path: Path | None = None,
) -> dict[str, object]:
    freshness = report.get("freshness_experiment")
    if not isinstance(freshness, Mapping):
        raise ValueError("report must include freshness_experiment")
    invalidation = freshness.get("invalidation")
    if not isinstance(invalidation, Mapping):
        raise ValueError("freshness_experiment must include invalidation")
    sidecar: dict[str, object] = {
        "artifact_type": "workstream6_invalidation",
        "definition_version": INVALIDATION_EXPERIMENT_VERSION,
        "dataset_version": report.get("dataset_version"),
        "config_version": report.get("config_version"),
        "measurement_environment": invalidation.get(
            "measurement_environment",
            "synthetic_replay",
        ),
        "invalidation": dict(invalidation),
    }
    if source_artifact_path is not None:
        sidecar["source_freshness_artifact"] = source_artifact_path.as_posix()
    validate_invalidation_artifact(sidecar["invalidation"])  # type: ignore[arg-type]
    return sidecar


def validate_freshness_artifact_package(report: Mapping[str, object]) -> None:
    """Verify Step 10 required sections on a finalized artifact."""
    freshness = report.get("freshness_experiment")
    if not isinstance(freshness, Mapping):
        raise ValueError("freshness_experiment is required")
    validate_freshness_experiment_report(freshness)
    validate_redacted_report_payload(freshness)

    metadata = report.get("freshness_artifact_metadata")
    if not isinstance(metadata, Mapping):
        raise ValueError("freshness_artifact_metadata is required")

    required_blocks = (
        "metrics_overall",
        "metrics_by_policy",
        "metrics_by_cache_control_outcome",
        "statistics_by_policy",
        "storage_by_policy",
        "stale_exposure_accounting",
        "invalidation",
    )
    for key in required_blocks:
        if key not in freshness:
            raise ValueError(f"freshness_experiment missing {key!r}")

    if freshness.get("evaluation_split") == "development":
        if "selected_policy" not in freshness or "policy_selection" not in freshness:
            raise ValueError("development artifact requires selection blocks")

    commands = metadata.get("regeneration_commands")
    if not isinstance(commands, list) or not commands:
        raise ValueError("regeneration_commands must be a non-empty list")
    if freshness.get("evaluation_split") == "held-out":
        _validate_held_out_regeneration_commands(commands)


def _validate_held_out_regeneration_commands(commands: list[object]) -> None:
    if len(commands) < 2:
        raise ValueError(
            "held-out artifact requires development and held-out regeneration commands"
        )
    development_command = commands[0]
    if not isinstance(development_command, str):
        raise ValueError("regeneration_commands entries must be strings")
    dev_benchmark = STANDARD_DEVELOPMENT_BENCHMARK.as_posix()
    if dev_benchmark not in development_command:
        raise ValueError(
            "first regeneration command must use the development benchmark JSONL"
        )
    if '--split development' not in development_command:
        raise ValueError(
            "first regeneration command must target the development split"
        )


def write_json_artifact(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_invalidation_sidecar(
    report: Mapping[str, object],
    path: Path,
    *,
    source_artifact_path: Path | None = None,
) -> dict[str, object]:
    sidecar = build_invalidation_sidecar_artifact(
        report,
        source_artifact_path=source_artifact_path,
    )
    write_json_artifact(path, sidecar)
    return sidecar


def freshness_companion_artifact_references(
    config: Mapping[str, object],
) -> dict[str, object] | None:
    """Non-duplicative pointers from Workstream 5 reports to WS6 artifacts."""
    if config.get("freshness_experiment") is None:
        return None
    artifacts: dict[str, MutableMapping[str, object]] = {}
    for key, path_str in STANDARD_ARTIFACT_PATHS.items():
        path = Path(path_str)
        artifacts[key] = {
            "path": path_str,
            "present": path.is_file(),
        }
    return {
        "schema_version": FRESHNESS_EVALUATION_SCHEMA_VERSION,
        "artifacts": artifacts,
        "integration": "reference_only",
        "note": (
            "Freshness policy metrics are produced by python -m sscre.freshness_evaluate; "
            "this block does not embed WS6 metrics."
        ),
    }


def resolve_invalidation_output_path(output_path: Path) -> Path | None:
    normalized = output_path.as_posix().replace("\\", "/")
    if normalized.endswith(STANDARD_ARTIFACT_PATHS["development"]):
        return output_path.parent / Path(STANDARD_ARTIFACT_PATHS["invalidation"]).name
    return None
