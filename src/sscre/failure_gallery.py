"""Failure gallery and Workstream 7 quality-analysis contract validation.

See ``docs/phase-2/FAILURE_GALLERY_CONTRACT_v1.md``.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sscre import __version__
from sscre.benchmark_splits import file_sha256
from sscre.failure_quality import (
    audit_false_positive_category_completeness,
    build_freshness_failure_companion,
    build_quality_analysis,
    enrich_failure_gallery,
    load_held_out_records_for_gallery,
)
from sscre.freshness_artifacts import STANDARD_ARTIFACT_PATHS
from sscre.serialization import validate_redacted_report_payload

FAILURE_GALLERY_SCHEMA_VERSION = "failure-gallery-1.0"
WORKSTREAM7_QUALITY_ARTIFACT_KIND = "workstream7-quality-analysis"
DEFAULT_HELD_OUT_FRESHNESS_PATH = STANDARD_ARTIFACT_PATHS["held-out"]
DEFAULT_HELD_OUT_COMPARISON_PATH = (
    "artifacts/evaluation/workstream5-held-out-comparison.json"
)
DEFAULT_QUALITY_ANALYSIS_OUTPUT_PATH = (
    "artifacts/evaluation/workstream7-quality-analysis.json"
)
DEFAULT_SPLIT_MANIFEST_PATH = Path("benchmarks/split_manifest.json")

WS5_COMPARISON_GALLERY_SECTIONS = (
    "embedding_only_false_positives",
    "embedding_only_false_positives_caught_by_strategy_c",
    "strategy_c_failures",
)

PLANNED_GALLERY_SECTIONS = frozenset({"freshness_protection_and_exposure"})

UNAVAILABLE_GALLERY_SECTIONS = frozenset(
    {
        "correctness_labeled_failures",
        "real_provider_failures",
    }
)

_EMBEDDING_GALLERY_SECTIONS = frozenset(
    {
        "embedding_only_false_positives",
        "embedding_only_false_positives_caught_by_strategy_c",
    }
)

_EMBEDDING_EXAMPLE_REQUIRED_KEYS = frozenset({"id", "direction", "similarity"})
_STRATEGY_C_EXAMPLE_REQUIRED_KEYS = frozenset(
    {
        "id",
        "direction",
        "similarity",
        "reason",
        "predicted_decision",
        "expected_reusable",
        "expected_compatibility",
        "failure_category",
    }
)

_FORBIDDEN_EXAMPLE_KEYS = frozenset(
    {
        "answer",
        "authorization",
        "api_key",
        "normalized_query",
        "password",
        "prompt",
        "provider_secret",
        "query",
        "query_a",
        "query_b",
        "query_text",
        "secret",
        "token",
    }
)

_VALID_DIRECTIONS = frozenset({"a_to_b", "b_to_a"})
_SAFETY_DECISIONS = frozenset({"SAFE", "UNSAFE", "UNCERTAIN"})


def _reject_forbidden_example_keys(example: Mapping[str, object], *, context: str) -> None:
    leaked = _FORBIDDEN_EXAMPLE_KEYS.intersection(example)
    if leaked:
        names = ", ".join(sorted(str(key) for key in leaked))
        raise ValueError(f"{context} contains forbidden field(s): {names}")


def _validate_embedding_example(
    example: object,
    *,
    section: str,
    index: int,
) -> None:
    context = f"failure_gallery.{section}[{index}]"
    if not isinstance(example, dict):
        raise ValueError(f"{context} must be an object")
    missing = _EMBEDDING_EXAMPLE_REQUIRED_KEYS.difference(example)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"{context} missing required field(s): {names}")
    direction = example.get("direction")
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(f"{context}.direction must be a_to_b or b_to_a")
    if example.get("category_source") is not None:
        if "mitigation" not in example:
            raise ValueError(f"{context} missing mitigation after enrichment")
        if not example.get("failure_category") and not example.get(
            "category_unavailable"
        ):
            raise ValueError(
                f"{context} requires failure_category or category_unavailable"
            )


def _validate_strategy_c_example(
    example: object,
    *,
    index: int,
) -> None:
    section = "strategy_c_failures"
    context = f"failure_gallery.{section}[{index}]"
    if not isinstance(example, dict):
        raise ValueError(f"{context} must be an object")
    missing = _STRATEGY_C_EXAMPLE_REQUIRED_KEYS.difference(example)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"{context} missing required field(s): {names}")
    direction = example.get("direction")
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(f"{context}.direction must be a_to_b or b_to_a")
    decision = example.get("predicted_decision")
    if decision not in _SAFETY_DECISIONS:
        raise ValueError(f"{context}.predicted_decision must be SAFE, UNSAFE, or UNCERTAIN")
    traces = example.get("candidate_traces")
    if traces is not None and not isinstance(traces, list):
        raise ValueError(f"{context}.candidate_traces must be a list or omitted")
    if example.get("category_source") is not None and "mitigation" not in example:
        raise ValueError(f"{context} missing mitigation after enrichment")


def validate_failure_gallery_redacted(gallery: object) -> None:
    """Validate gallery shape and operational redaction rules."""
    validate_failure_gallery(gallery)
    validate_redacted_report_payload({"failure_gallery": gallery})


def validate_failure_gallery(gallery: object) -> None:
    """Validate a comparison or consolidated ``failure_gallery`` block."""
    if not isinstance(gallery, dict):
        raise ValueError("failure_gallery must be an object")
    unknown = set(gallery).difference(
        set(WS5_COMPARISON_GALLERY_SECTIONS)
        .union(PLANNED_GALLERY_SECTIONS)
        .union(UNAVAILABLE_GALLERY_SECTIONS)
    )
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"failure_gallery has unknown section(s): {names}")
    for section in WS5_COMPARISON_GALLERY_SECTIONS:
        if section not in gallery:
            raise ValueError(f"failure_gallery missing required section: {section}")
        examples = gallery[section]
        if not isinstance(examples, list):
            raise ValueError(f"failure_gallery.{section} must be a list")
        for index, example in enumerate(examples):
            if section in _EMBEDDING_GALLERY_SECTIONS:
                _validate_embedding_example(example, section=section, index=index)
            else:
                _validate_strategy_c_example(example, index=index)


def validate_quality_analysis(block: object) -> None:
    if not isinstance(block, dict):
        raise ValueError("quality_analysis must be an object")
    by_category = block.get("by_failure_category")
    if by_category is None:
        raise ValueError("quality_analysis.by_failure_category is required")
    if not isinstance(by_category, dict):
        raise ValueError("quality_analysis.by_failure_category must be an object")
    for category, summary in by_category.items():
        if not isinstance(category, str) or not category:
            raise ValueError("quality_analysis.by_failure_category keys must be strings")
        if not isinstance(summary, dict):
            raise ValueError(
                f"quality_analysis.by_failure_category[{category!r}] must be an object"
            )
        if "sample_count" not in summary:
            raise ValueError(
                f"quality_analysis.by_failure_category[{category!r}] "
                "missing sample_count"
            )
    by_freshness = block.get("by_freshness_class")
    if by_freshness is not None and not isinstance(by_freshness, dict):
        raise ValueError("quality_analysis.by_freshness_class must be an object")


def validate_freshness_failure_companion(block: object) -> None:
    if not isinstance(block, dict):
        raise ValueError("freshness_failure_companion must be an object")
    for key in ("source_artifact_path", "measurement_environment", "dataset_version"):
        if key not in block:
            raise ValueError(f"freshness_failure_companion missing {key}")
    path = block.get("source_artifact_path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("freshness_failure_companion.source_artifact_path must be a string")
    unavailable = block.get("unavailable")
    if unavailable is True:
        reason = block.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "freshness_failure_companion.reason is required when unavailable is true"
            )
        return
    for key in ("stale_exposure_accounting", "protection_counts"):
        if key not in block:
            raise ValueError(f"freshness_failure_companion missing {key}")
        if not isinstance(block[key], dict):
            raise ValueError(f"freshness_failure_companion.{key} must be an object")


def validate_input_artifacts(block: object) -> None:
    if not isinstance(block, dict):
        raise ValueError("input_artifacts must be an object")
    comparison = block.get("comparison")
    if not isinstance(comparison, dict):
        raise ValueError("input_artifacts.comparison must be an object")
    for key in ("path", "schema_version", "split_manifest_sha256", "dataset_version"):
        if key not in comparison:
            raise ValueError(f"input_artifacts.comparison missing {key}")
    freshness = block.get("freshness")
    if freshness is not None and not isinstance(freshness, dict):
        raise ValueError("input_artifacts.freshness must be an object or omitted")


def validate_selected_sample(block: object) -> None:
    if not isinstance(block, dict):
        raise ValueError("selected_sample must be an object")
    for key in (
        "evaluation_split",
        "dataset_version",
        "directed_request_count",
        "compatibility_threshold",
        "measurement_environment",
    ):
        if key not in block:
            raise ValueError(f"selected_sample missing {key}")
    split = block.get("evaluation_split")
    if split != "held-out":
        raise ValueError("selected_sample.evaluation_split must be held-out for WS7 freeze")
    environment = block.get("measurement_environment")
    if not isinstance(environment, str) or not environment:
        raise ValueError("selected_sample.measurement_environment must be a non-empty string")


def validate_consolidated_quality_analysis(payload: Mapping[str, object]) -> None:
    """Validate the Workstream 7 consolidated quality-analysis artifact envelope."""
    schema_version = payload.get("failure_gallery_schema_version")
    if schema_version != FAILURE_GALLERY_SCHEMA_VERSION:
        raise ValueError(
            f"failure_gallery_schema_version must be {FAILURE_GALLERY_SCHEMA_VERSION!r}"
        )
    validate_selected_sample(payload.get("selected_sample"))
    validate_input_artifacts(payload.get("input_artifacts"))
    gallery = payload.get("failure_gallery")
    if gallery is None:
        raise ValueError("consolidated artifact missing failure_gallery")
    validate_failure_gallery(gallery)
    validate_quality_analysis(payload.get("quality_analysis"))
    validate_freshness_failure_companion(payload.get("freshness_failure_companion"))
    limitations = payload.get("limitations")
    if limitations is not None and not isinstance(limitations, list):
        raise ValueError("limitations must be a list when present")
    unavailable_sections = payload.get("unavailable_sections")
    if unavailable_sections is not None:
        if not isinstance(unavailable_sections, list):
            raise ValueError("unavailable_sections must be a list")
        for entry in unavailable_sections:
            if entry not in UNAVAILABLE_GALLERY_SECTIONS:
                raise ValueError(f"unknown unavailable_sections entry: {entry!r}")


def attach_failure_gallery_schema(payload: Mapping[str, object]) -> dict[str, object]:
    result = dict(payload)
    gallery = result.get("failure_gallery")
    if gallery is not None:
        validate_failure_gallery(gallery)
        result["failure_gallery_schema_version"] = FAILURE_GALLERY_SCHEMA_VERSION
    if "quality_analysis" in result and "input_artifacts" in result:
        validate_consolidated_quality_analysis(result)
    return result


def load_comparison_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"comparison report must be a JSON object: {path}")
    if payload.get("baseline") != "comparison":
        raise ValueError(f"expected baseline comparison report: {path}")
    if payload.get("evaluation_split") != "held-out":
        raise ValueError(
            f"Workstream 7 packaging requires held-out comparison: {path}"
        )
    gallery = payload.get("failure_gallery")
    if not isinstance(gallery, dict):
        raise ValueError(f"comparison report missing failure_gallery: {path}")
    validate_failure_gallery(gallery)
    if "statistics" not in payload:
        raise ValueError(f"comparison report missing statistics: {path}")
    return payload


def _benchmark_manifest_sha256(report: Mapping[str, object]) -> str | None:
    artifact = report.get("benchmark_artifact")
    if isinstance(artifact, dict):
        manifest_sha = artifact.get("split_manifest_sha256")
        if isinstance(manifest_sha, str) and manifest_sha:
            return manifest_sha
    return None


def _dataset_version(report: Mapping[str, object]) -> str:
    artifact = report.get("benchmark_artifact")
    if isinstance(artifact, dict):
        dataset_version = artifact.get("dataset_version")
        if isinstance(dataset_version, str) and dataset_version:
            return dataset_version
    baselines = report.get("baselines")
    if isinstance(baselines, dict):
        for baseline in baselines.values():
            if isinstance(baseline, dict):
                dataset_version = baseline.get("dataset_version")
                if isinstance(dataset_version, str) and dataset_version:
                    return dataset_version
    raise ValueError("comparison report missing dataset_version")


def _directed_request_count(report: Mapping[str, object]) -> int:
    baselines = report.get("baselines")
    if isinstance(baselines, dict):
        compatibility = baselines.get("compatibility-cache")
        if isinstance(compatibility, dict):
            request_count = compatibility.get("request_count")
            if isinstance(request_count, int) and request_count > 0:
                return request_count
    raise ValueError("comparison report missing compatibility-cache request_count")


def _compatibility_threshold(report: Mapping[str, object]) -> float:
    selection = report.get("threshold_selection")
    if isinstance(selection, dict):
        threshold = selection.get("selected_threshold")
        if isinstance(threshold, (int, float)):
            return float(threshold)
    raise ValueError("comparison report missing threshold_selection.selected_threshold")


def _gallery_for_consolidated_package(
    gallery: Mapping[str, object],
) -> tuple[dict[str, list[dict[str, object]]], bool]:
    copied = _copy_failure_gallery(gallery)
    if not audit_false_positive_category_completeness(copied):
        return copied, False
    records = load_held_out_records_for_gallery()
    return enrich_failure_gallery(copied, records), True


def _copy_failure_gallery(gallery: Mapping[str, object]) -> dict[str, list[dict[str, object]]]:
    copied: dict[str, list[dict[str, object]]] = {}
    for section in WS5_COMPARISON_GALLERY_SECTIONS:
        examples = gallery.get(section)
        if not isinstance(examples, list):
            raise ValueError(f"failure_gallery.{section} must be a list")
        copied[section] = [
            dict(example) if isinstance(example, dict) else example  # type: ignore[misc]
            for example in examples
        ]
    return copied


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


def _input_artifact_descriptor(
    report: Mapping[str, object] | None,
    *,
    path: str,
    present: bool,
) -> dict[str, object]:
    descriptor: dict[str, object] = {"path": path, "present": present}
    if report is None:
        return descriptor
    descriptor["schema_version"] = report.get("schema_version")
    statistics = report.get("statistics")
    if isinstance(statistics, dict):
        descriptor["statistics_schema_version"] = statistics.get(
            "statistics_schema_version"
        )
    descriptor["freshness_evaluation_schema_version"] = report.get(
        "freshness_evaluation_schema_version"
    )
    descriptor["dataset_version"] = _dataset_version(report)
    manifest_sha = _benchmark_manifest_sha256(report)
    if manifest_sha is not None:
        descriptor["split_manifest_sha256"] = manifest_sha
    return descriptor


def _default_regeneration_commands(
    *,
    comparison_path: str,
    freshness_path: str,
    output_path: str,
) -> list[str]:
    return [
        (
            "python -m sscre.evaluate "
            '--benchmark benchmarks/held_out_test.jsonl '
            '--config experiments/evaluation_config.json '
            "--baseline all --split held-out --production "
            f'--output "{comparison_path}"'
        ),
        (
            "python -m sscre.freshness_evaluate "
            '--benchmark benchmarks/held_out_test.jsonl '
            '--config experiments/evaluation_config.json '
            f'--split held-out --production --output "{freshness_path}"'
        ),
        (
            "python -m sscre.failure_gallery_export "
            f'--comparison "{comparison_path}" '
            f'--freshness-companion "{freshness_path}" '
            f'--output "{output_path}"'
        ),
    ]


def package_consolidated_quality_analysis(
    *,
    comparison_path: Path | str,
    freshness_companion_path: Path | str | None = None,
    output_path: Path | str = DEFAULT_QUALITY_ANALYSIS_OUTPUT_PATH,
    allow_manifest_mismatch: bool = False,
    execution_timestamp: str | None = None,
) -> dict[str, object]:
    """Assemble the Workstream 7 consolidated quality-analysis JSON artifact."""
    comparison_file = Path(comparison_path)
    comparison = load_comparison_report(comparison_file)
    freshness_file = Path(
        freshness_companion_path or DEFAULT_HELD_OUT_FRESHNESS_PATH
    )
    freshness_report: dict[str, Any] | None = None
    if freshness_file.is_file():
        loaded = json.loads(freshness_file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            freshness_report = loaded

    comparison_manifest = _benchmark_manifest_sha256(comparison)
    freshness_manifest = (
        _benchmark_manifest_sha256(freshness_report)
        if freshness_report is not None
        else None
    )
    limitations: list[str] = [
        "synthetic_replay: compatibility and freshness metrics are replay-only"
    ]
    manifest_mismatch = (
        comparison_manifest is not None
        and freshness_manifest is not None
        and comparison_manifest != freshness_manifest
    )
    if freshness_report is not None:
        comparison_dataset = _dataset_version(comparison)
        freshness_dataset = _dataset_version(freshness_report)
        if comparison_dataset != freshness_dataset:
            message = (
                "dataset_version mismatch between comparison and freshness inputs"
            )
            if not allow_manifest_mismatch:
                raise ValueError(message)
            limitations.append(message)
            limitations.append(f"comparison_dataset_version={comparison_dataset}")
            limitations.append(f"freshness_dataset_version={freshness_dataset}")

    if manifest_mismatch:
        message = (
            "split_manifest_sha256 mismatch between comparison and freshness inputs"
        )
        if not allow_manifest_mismatch:
            raise ValueError(message)
        limitations.append(message)
        limitations.append(
            f"comparison_manifest_sha256={comparison_manifest}"
        )
        limitations.append(f"freshness_manifest_sha256={freshness_manifest}")

    companion = build_freshness_failure_companion(
        freshness_file if freshness_file.is_file() else freshness_file,
        validate_artifact=freshness_report is not None,
    )
    if manifest_mismatch:
        companion["manifest_mismatch"] = True

    current_manifest_sha: str | None = None
    if DEFAULT_SPLIT_MANIFEST_PATH.is_file():
        current_manifest_sha = file_sha256(DEFAULT_SPLIT_MANIFEST_PATH)
    comparison_stale_vs_repo = (
        comparison_manifest is not None
        and current_manifest_sha is not None
        and comparison_manifest != current_manifest_sha
    )
    if comparison_stale_vs_repo:
        limitations.append(
            "comparison_split_manifest_sha256 differs from benchmarks/split_manifest.json"
        )
        limitations.append(f"repo_split_manifest_sha256={current_manifest_sha}")
        limitations.append(
            f"comparison_split_manifest_sha256={comparison_manifest}"
        )

    measurement_environment = comparison.get("measurement_environment")
    if not isinstance(measurement_environment, str) or not measurement_environment:
        measurement_environment = "synthetic_replay"

    package_timestamp = execution_timestamp or datetime.now(timezone.utc).isoformat()
    comparison_path_posix = comparison_file.as_posix()
    freshness_path_posix = freshness_file.as_posix()
    output_path_posix = Path(output_path).as_posix()

    payload: dict[str, object] = {
        "artifact_kind": WORKSTREAM7_QUALITY_ARTIFACT_KIND,
        "dataset_version": _dataset_version(comparison),
        "evaluation_split": comparison.get("evaluation_split"),
        "split_manifest_sha256": comparison_manifest,
        "measurement_environment": measurement_environment,
        "execution_timestamp": package_timestamp,
        "source_comparison_execution_timestamp": comparison.get(
            "execution_timestamp"
        ),
        "software_version": comparison.get("software_version") or __version__,
        "git_commit": comparison.get("git_commit") or _git_commit(),
        "git_worktree_dirty": comparison.get("git_worktree_dirty"),
        "selected_sample": {
            "evaluation_split": "held-out",
            "dataset_version": _dataset_version(comparison),
            "directed_request_count": _directed_request_count(comparison),
            "compatibility_threshold": _compatibility_threshold(comparison),
            "measurement_environment": measurement_environment,
        },
        "input_artifacts": {
            "comparison": _input_artifact_descriptor(
                comparison,
                path=comparison_path_posix,
                present=True,
            ),
            "freshness": _input_artifact_descriptor(
                freshness_report,
                path=freshness_path_posix,
                present=freshness_report is not None,
            ),
        },
        "quality_analysis": build_quality_analysis(comparison),
        "freshness_failure_companion": companion,
        "limitations": limitations,
        "unavailable_sections": sorted(UNAVAILABLE_GALLERY_SECTIONS),
        "regeneration_commands": _default_regeneration_commands(
            comparison_path=comparison_path_posix,
            freshness_path=freshness_path_posix,
            output_path=output_path_posix,
        ),
    }
    gallery, enriched_at_pack = _gallery_for_consolidated_package(
        comparison["failure_gallery"]
    )
    payload["failure_gallery"] = gallery
    if enriched_at_pack:
        limitations.append(
            "failure_gallery enriched at pack time from benchmarks/held_out_test.jsonl"
        )
        payload["limitations"] = limitations
    missing_categories = audit_false_positive_category_completeness(gallery)
    if missing_categories:
        limitations.append(
            "embedding_false_positive_category_gaps: "
            + ",".join(missing_categories[:20])
            + ("..." if len(missing_categories) > 20 else "")
        )
    else:
        payload["false_positive_category_complete"] = True
    payload["limitations"] = limitations
    validate_redacted_report_payload(payload)
    return attach_failure_gallery_schema(payload)


def write_consolidated_quality_analysis(
    output_path: Path | str,
    payload: Mapping[str, object],
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
