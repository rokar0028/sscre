"""Load and export bounded evaluation artifacts for the Workstream 9 dashboard.

This module does not replay evaluation or calculate metrics.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

from sscre.failure_gallery import (
    validate_consolidated_quality_analysis,
    validate_failure_gallery,
)
from sscre.freshness_artifacts import validate_freshness_artifact_package
from sscre.freshness_invalidation import validate_invalidation_artifact
from sscre.serialization import validate_redacted_report_payload

DASHBOARD_SCHEMA_VERSION = "workstream9-dashboard-1.0"
DASHBOARD_ARTIFACT_KIND = "workstream9-dashboard"
THRESHOLD_SELECTION_SPLIT = "development"
SECTION_NAMES = (
    "operating_point",
    "baseline_comparison",
    "confidence_intervals",
    "pareto",
    "failure_categories",
    "freshness",
    "operations",
    "provider_measurements",
    "limitations",
)
SECTION_STATUSES = frozenset(
    {"available", "unavailable", "not_comparable", "metadata_mismatch"}
)
MAX_VIEW_MANIFEST_BYTES = 250_000
MAX_DISPLAY_STRING_BYTES = 512
MAX_DISPLAY_MAPPING_ITEMS = 100
MAX_DISPLAY_LIST_ITEMS = 100
_MISSING = object()

DEFAULT_SOURCE_PATHS = {
    "comparison": Path("artifacts/evaluation/workstream5-held-out-comparison.json"),
    "pareto": Path("artifacts/evaluation/workstream5-held-out-pareto.json"),
    "freshness_development": Path(
        "artifacts/evaluation/workstream6-development-freshness.json"
    ),
    "freshness_held_out": Path(
        "artifacts/evaluation/workstream6-held-out-freshness.json"
    ),
    "invalidation": Path("artifacts/evaluation/workstream6-invalidation.json"),
    "quality": Path("artifacts/evaluation/workstream7-quality-analysis.json"),
    "operations": Path(
        "artifacts/operations/workstream8-operational-verification.json"
    ),
    "provider_comparison": Path(
        "artifacts/evaluation/workstream4-provider-comparison.json"
    ),
    "provider_unavailable": Path(
        "artifacts/evaluation/workstream4-real-provider-unavailable.json"
    ),
}
DEFAULT_JSON_OUTPUT = Path("artifacts/evaluation/workstream9-dashboard.json")
DEFAULT_HTML_OUTPUT = Path("artifacts/evaluation/workstream9-dashboard.html")

_REQUIRED_SOURCES = frozenset(
    {"comparison", "freshness_held_out", "quality", "operations"}
)
_FORBIDDEN_DISPLAY_KEYS = frozenset(
    {
        "answer",
        "answer_text",
        "failure_examples",
        "false_positive_examples",
        "observed_pair_records",
        "prompt",
        "query",
        "query_a",
        "query_b",
        "query_text",
        "request_samples",
    }
)
_BASELINE_METRIC_KEYS = (
    "request_count",
    "cache_hits",
    "cache_misses",
    "generated_requests",
    "errors",
    "timeouts",
    "average_latency_ms",
    "p50_latency_ms",
    "p95_latency_ms",
    "p99_latency_ms",
    "estimated_cost_usd",
    "input_tokens",
    "output_tokens",
    "embedding_tokens",
    "tokens_saved",
    "safe_reuse_coverage",
    "false_positive_rate",
    "hit_rate",
    "precision",
    "recall",
)
_OPERATIONS_ENVIRONMENT_KEYS = (
    "os",
    "machine",
    "processor",
    "python",
    "python_implementation",
    "postgresql_version",
    "database_mode",
    "cpu_count",
    "process_count",
    "worker_count",
    "measured_at",
)
_INTERVAL_STATISTICS_KEYS = (
    "bootstrap_iterations",
    "confidence_level",
    "distributions",
    "interval_methods",
    "minimum_n_bootstrap",
    "minimum_n_proportion",
    "proportions",
    "random_seed",
    "sample_count",
    "sample_unit",
    "statistics_schema_version",
)


class DashboardInputError(ValueError):
    """Raised when a dashboard source cannot satisfy its input contract."""


@dataclass(frozen=True)
class _LoadedSource:
    name: str
    path: Path
    required: bool
    payload: dict[str, Any] | None
    descriptor: dict[str, object]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _bounded_scalar(value: object) -> object:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DashboardInputError("dashboard display values must be finite")
        return value
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_DISPLAY_STRING_BYTES:
            raise DashboardInputError("dashboard display string exceeds its bound")
        return value
    raise DashboardInputError(
        f"unsupported dashboard display scalar type: {type(value).__name__}"
    )


def _bounded_tree(value: object, *, depth: int = 0) -> object:
    """Copy a bounded numeric/categorical tree without raw request content."""
    if depth > 12:
        raise DashboardInputError("dashboard display nesting exceeds its bound")
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_DISPLAY_MAPPING_ITEMS:
                raise DashboardInputError("dashboard display mapping exceeds its bound")
            key_text = str(key)
            if key_text.lower() in _FORBIDDEN_DISPLAY_KEYS:
                raise DashboardInputError(
                    f"dashboard display contains forbidden field {key_text!r}"
                )
            result[key_text] = _bounded_tree(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        if len(value) > MAX_DISPLAY_LIST_ITEMS:
            raise DashboardInputError("dashboard display list exceeds its bound")
        return [_bounded_tree(item, depth=depth + 1) for item in value]
    return _bounded_scalar(value)


def _path_for(path: Path, repo_root: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _metadata(payload: Mapping[str, object]) -> dict[str, object]:
    benchmark = payload.get("benchmark_artifact")
    if not isinstance(benchmark, Mapping):
        benchmark = payload.get("benchmark")
    if not isinstance(benchmark, Mapping):
        benchmark = {}

    freshness_metadata = payload.get("freshness_artifact_metadata")
    if not isinstance(freshness_metadata, Mapping):
        freshness_metadata = {}

    schema_versions: dict[str, object] = {}
    for key in (
        "schema_version",
        "statistics_schema_version",
        "pareto_schema_version",
        "freshness_evaluation_schema_version",
        "failure_gallery_schema_version",
        "definition_version",
    ):
        value = payload.get(key)
        if value is not None:
            schema_versions[key] = _bounded_scalar(value)
    for key in (
        "freshness_evaluation_schema_version",
        "statistics_schema_version",
        "artifact_package_version",
    ):
        value = freshness_metadata.get(key)
        if value is not None:
            schema_versions[key] = _bounded_scalar(value)

    dataset_version = payload.get("dataset_version") or benchmark.get("dataset_version")
    evaluation_split = (
        payload.get("evaluation_split")
        or payload.get("split")
        or benchmark.get("evaluation_split")
        or benchmark.get("split")
    )
    manifest = payload.get("split_manifest_sha256") or benchmark.get(
        "split_manifest_sha256"
    )
    environment = payload.get("measurement_environment")
    timestamp = payload.get("execution_timestamp") or payload.get("measured_at")
    descriptor: dict[str, object] = {
        "artifact_kind": payload.get("artifact_kind")
        or payload.get("kind")
        or payload.get("artifact_type"),
        "schema_versions": schema_versions,
        "dataset_version": dataset_version,
        "evaluation_split": evaluation_split,
        "split_manifest_sha256": manifest,
        "measurement_environment": environment,
        "timestamp": timestamp,
    }
    status = payload.get("status")
    if status is not None:
        descriptor["artifact_status"] = _bounded_scalar(status)
    return {
        key: _bounded_tree(value)
        for key, value in descriptor.items()
        if value is not None
    }


def _descriptor(source: _LoadedSource) -> dict[str, object]:
    result = dict(source.descriptor)
    result.update(
        {
            "path": source.path.as_posix(),
            "present": source.payload is not None,
        }
    )
    return result


def _load_json_source(
    name: str,
    path: Path,
    *,
    required: bool,
) -> _LoadedSource:
    if not path.is_file():
        if required:
            raise DashboardInputError(f"required dashboard source is missing: {path}")
        return _LoadedSource(
            name=name,
            path=path,
            required=required,
            payload=None,
            descriptor={
                "status": "unavailable",
                "reason": "source_file_missing",
            },
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DashboardInputError(f"cannot load dashboard source {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise DashboardInputError(f"dashboard source must be a JSON object: {path}")
    try:
        validate_redacted_report_payload(raw)
        descriptor = _metadata(raw)
    except (TypeError, ValueError) as exc:
        raise DashboardInputError(f"invalid dashboard source {path}: {exc}") from exc
    return _LoadedSource(
        name=name,
        path=path,
        required=required,
        payload=raw,
        descriptor=descriptor,
    )


def _validate_source_contract(source: _LoadedSource) -> None:
    payload = source.payload
    if payload is None:
        return
    try:
        if source.name == "comparison":
            if payload.get("baseline") != "comparison":
                raise ValueError("baseline must be comparison")
            if payload.get("evaluation_split") != "held-out":
                raise ValueError("evaluation_split must be held-out")
            benchmark = payload.get("benchmark_artifact")
            if not isinstance(benchmark, Mapping):
                raise ValueError("benchmark_artifact is required")
            if not isinstance(payload.get("statistics"), Mapping):
                raise ValueError("statistics is required")
            validate_failure_gallery(payload.get("failure_gallery"))
        elif source.name == "pareto":
            if payload.get("pareto_schema_version") != "evaluation-pareto-1.0":
                raise ValueError("pareto_schema_version is unsupported")
            if payload.get("evaluation_split") != "held-out":
                raise ValueError("evaluation_split must be held-out")
            if not isinstance(payload.get("points"), list):
                raise ValueError("points must be a list")
        elif source.name in {"freshness_development", "freshness_held_out"}:
            validate_freshness_artifact_package(payload)
            expected = (
                "development" if source.name == "freshness_development" else "held-out"
            )
            if payload.get("evaluation_split") != expected:
                raise ValueError(f"evaluation_split must be {expected}")
        elif source.name == "invalidation":
            if payload.get("artifact_type") != "workstream6_invalidation":
                raise ValueError("artifact_type is unsupported")
            invalidation = payload.get("invalidation")
            if not isinstance(invalidation, Mapping):
                raise ValueError("invalidation block is required")
            validate_invalidation_artifact(invalidation)
        elif source.name == "quality":
            validate_consolidated_quality_analysis(payload)
        elif source.name == "operations":
            if payload.get("kind") != "workstream8-operational-verification":
                raise ValueError("kind is unsupported")
            if payload.get("schema_version") != "ws8-ops-1.0":
                raise ValueError("schema_version is unsupported")
        elif source.name == "provider_comparison":
            if payload.get("schema_version") != "provider-measurement-comparison-1.0":
                raise ValueError("schema_version is unsupported")
        elif source.name == "provider_unavailable":
            if payload.get("schema_version") != "real-provider-measurement-1.0":
                raise ValueError("schema_version is unsupported")
            if payload.get("status") != "unavailable":
                raise ValueError("status must be unavailable")
    except (TypeError, ValueError) as exc:
        raise DashboardInputError(
            f"dashboard source {source.name} failed contract validation: {exc}"
        ) from exc


def _load_sources(
    paths: Mapping[str, Path],
    *,
    repo_root: Path,
) -> dict[str, _LoadedSource]:
    sources: dict[str, _LoadedSource] = {}
    for name, path in paths.items():
        source = _load_json_source(
            name,
            _path_for(path, repo_root),
            required=name in _REQUIRED_SOURCES,
        )
        _validate_source_contract(source)
        sources[name] = source
    return sources


def _identity(source: _LoadedSource) -> dict[str, object]:
    return {
        key: source.descriptor.get(key)
        for key in ("dataset_version", "evaluation_split", "split_manifest_sha256")
    }


def _metadata_mismatch(
    source: _LoadedSource,
    primary: Mapping[str, object],
) -> str | None:
    current = _identity(source)
    for key in ("dataset_version", "evaluation_split", "split_manifest_sha256"):
        expected = primary.get(key)
        actual = current.get(key)
        if expected is not None and actual is not None and expected != actual:
            return f"{key} mismatch: expected {expected!r}, got {actual!r}"
    return None


def _section(
    *,
    status: str,
    source_names: list[str],
    sources: Mapping[str, _LoadedSource],
    data: Mapping[str, object] | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    if status not in SECTION_STATUSES:
        raise DashboardInputError(f"unsupported dashboard section status: {status}")
    result: dict[str, object] = {
        "status": status,
        "source_artifacts": [
            _descriptor(sources[name]) for name in source_names if name in sources
        ],
    }
    if data is not None:
        result["data"] = _bounded_tree(data)
    if status != "available":
        if not reason:
            raise DashboardInputError(
                f"dashboard section {source_names!r} needs a reason for {status}"
            )
        result["reason"] = reason
    return result


def _interval_statistics(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {
        key: value[key]
        for key in _INTERVAL_STATISTICS_KEYS
        if key in value
    }


def _unavailable_section(
    name: str,
    sources: Mapping[str, _LoadedSource],
    *,
    reason: str,
) -> dict[str, object]:
    source = sources[name]
    return _section(
        status="unavailable",
        source_names=[name],
        sources=sources,
        reason=reason,
    )


def _comparison_sections(
    comparison: _LoadedSource,
    sources: Mapping[str, _LoadedSource],
    primary: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    assert comparison.payload is not None
    payload = comparison.payload
    selection = payload.get("threshold_selection")
    if not isinstance(selection, Mapping):
        raise DashboardInputError("comparison threshold_selection is required")
    operating_point = {
        key: selection[key]
        for key in ("selected_threshold", "selection_rule", "constraint_satisfied")
        if key in selection
    }
    statistics = payload.get("statistics")
    if isinstance(statistics, Mapping):
        point = statistics.get("operating_point")
        if isinstance(point, Mapping):
            operating_point["statistics"] = dict(point)
    development = sources["freshness_development"]
    if development.payload is None:
        operating_point["development_provenance"] = {
            "status": "unavailable",
            "reason": "source_file_missing",
        }
    else:
        development_mismatch = _metadata_mismatch(development, primary)
        operating_point["development_provenance"] = {
            "status": "available",
            "alignment": (
                "provenance_only_manifest_mismatch"
                if development_mismatch
                else "aligned"
            ),
            "source": _descriptor(development),
        }
    operating_point["selection_split"] = THRESHOLD_SELECTION_SPLIT

    baselines = payload.get("baselines")
    baseline_data: dict[str, object] = {}
    if isinstance(baselines, Mapping):
        for baseline_name, baseline in baselines.items():
            if not isinstance(baseline, Mapping):
                continue
            baseline_data[str(baseline_name)] = {
                key: baseline[key]
                for key in _BASELINE_METRIC_KEYS
                if key in baseline
            }
    confidence_data: dict[str, object] = {}
    if isinstance(statistics, Mapping):
        overall = statistics.get("overall")
        if overall is not None:
            confidence_data["overall"] = _interval_statistics(overall)
        by_baseline = statistics.get("by_baseline")
        if isinstance(by_baseline, Mapping):
            confidence_data["by_baseline"] = {
                str(name): _interval_statistics(value)
                for name, value in by_baseline.items()
            }
        for key in ("sample_unit", "measurement_environment"):
            if key in statistics:
                confidence_data[key] = statistics[key]

    return {
        "operating_point": _section(
            status="available",
            source_names=["comparison", "freshness_development"],
            sources=sources,
            data=operating_point,
        ),
        "baseline_comparison": _section(
            status="available",
            source_names=["comparison"],
            sources=sources,
            data={"baselines": baseline_data},
        ),
        "confidence_intervals": _section(
            status="available",
            source_names=["comparison"],
            sources=sources,
            data=confidence_data,
        ),
    }


def _pareto_section(
    source: _LoadedSource,
    sources: Mapping[str, _LoadedSource],
    primary: Mapping[str, object],
) -> dict[str, object]:
    if source.payload is None:
        return _unavailable_section("pareto", sources, reason="source_file_missing")
    mismatch = _metadata_mismatch(source, primary)
    if mismatch:
        return _section(
            status="metadata_mismatch",
            source_names=["pareto"],
            sources=sources,
            reason=mismatch,
        )
    payload = source.payload
    points = payload.get("points")
    assert isinstance(points, list)
    projected_points: list[dict[str, object]] = []
    for point in points:
        if not isinstance(point, Mapping):
            continue
        projected: dict[str, object] = {
            key: point[key] for key in ("threshold", "selected") if key in point
        }
        for key in ("metrics", "constraint", "storage"):
            value = point.get(key)
            if isinstance(value, Mapping):
                projected[key] = dict(value)
        projected_points.append(projected)
    data: dict[str, object] = {
        "selected_threshold": payload.get("selected_threshold"),
        "selected_constraint": payload.get("selected_constraint"),
        "dominance": payload.get("dominance"),
        "points": projected_points,
        "storage_measurement_environment": payload.get(
            "storage_measurement_environment"
        ),
    }
    if not source.descriptor.get("split_manifest_sha256"):
        data["manifest_status"] = "not_recorded"
    if payload.get("storage_measurement_environment") == "unavailable":
        data["storage_status"] = "unavailable"
        data["storage_reason"] = "held_out_aligned_storage_artifact_unavailable"
    return _section(
        status="available",
        source_names=["pareto"],
        sources=sources,
        data=data,
    )


def _freshness_section(
    sources: Mapping[str, _LoadedSource],
    primary: Mapping[str, object],
) -> dict[str, object]:
    held_out = sources["freshness_held_out"]
    assert held_out.payload is not None
    mismatch = _metadata_mismatch(held_out, primary)
    if mismatch:
        return _section(
            status="metadata_mismatch",
            source_names=["freshness_held_out"],
            sources=sources,
            reason=mismatch,
        )
    experiment = held_out.payload.get("freshness_experiment")
    if not isinstance(experiment, Mapping):
        raise DashboardInputError("held-out freshness_experiment is required")
    data: dict[str, object] = {}
    for key in (
        "selected_policy",
        "selected_policy_name",
        "held_out_freshness_scope",
        "stale_exposure_accounting",
        "metrics_overall",
        "storage_overall",
        "invalidation",
    ):
        if key in experiment:
            data[key] = experiment[key]

    development = sources["freshness_development"]
    if development.payload is None:
        data["development_selection"] = {
            "status": "unavailable",
            "reason": "source_file_missing",
        }
    else:
        development_mismatch = _metadata_mismatch(development, primary)
        data["development_selection"] = {
            "status": "available",
            "alignment": (
                "provenance_only_manifest_mismatch"
                if development_mismatch
                else "aligned"
            ),
            "reason": development_mismatch,
            "source": _descriptor(development),
        }

    invalidation = sources["invalidation"]
    if invalidation.payload is None:
        data["invalidation_artifact"] = {
            "status": "unavailable",
            "reason": "source_file_missing",
        }
    else:
        data["invalidation_artifact"] = invalidation.payload.get("invalidation")
    return _section(
        status="available",
        source_names=["freshness_held_out", "freshness_development", "invalidation"],
        sources=sources,
        data=data,
    )


def _quality_section(
    source: _LoadedSource,
    sources: Mapping[str, _LoadedSource],
    primary: Mapping[str, object],
) -> dict[str, object]:
    assert source.payload is not None
    mismatch = _metadata_mismatch(source, primary)
    if mismatch:
        return _section(
            status="metadata_mismatch",
            source_names=["quality"],
            sources=sources,
            reason=mismatch,
        )
    quality = source.payload.get("quality_analysis")
    if not isinstance(quality, Mapping):
        raise DashboardInputError("quality_analysis is required")
    data = {
        key: quality[key]
        for key in (
            "by_failure_category",
            "by_freshness_class",
            "sample_unit",
            "source_baseline",
            "statistics_schema_version",
        )
        if key in quality
    }
    return _section(
        status="available",
        source_names=["quality"],
        sources=sources,
        data=data,
    )


def _operations_section(
    source: _LoadedSource,
    sources: Mapping[str, _LoadedSource],
) -> dict[str, object]:
    assert source.payload is not None
    environment = source.payload.get("environment")
    protocols = source.payload.get("protocols")
    data: dict[str, object] = {
        "protocol_id": source.payload.get("protocol_id"),
        "limitation": source.payload.get("limitation"),
        "unsupported_claims": source.payload.get("unsupported_claims", []),
    }
    if isinstance(environment, Mapping):
        data["environment"] = {
            key: environment[key]
            for key in _OPERATIONS_ENVIRONMENT_KEYS
            if key in environment
        }
    if isinstance(protocols, Mapping):
        data["protocols"] = dict(protocols)
    return _section(
        status="available",
        source_names=["operations"],
        sources=sources,
        data=data,
    )


def _provider_section(
    sources: Mapping[str, _LoadedSource],
) -> dict[str, object]:
    comparison = sources["provider_comparison"]
    unavailable = sources["provider_unavailable"]
    if comparison.payload is None and unavailable.payload is None:
        return _section(
            status="unavailable",
            source_names=["provider_comparison", "provider_unavailable"],
            sources=sources,
            reason="provider_sources_missing",
        )
    return _section(
        status="not_comparable",
        source_names=["provider_comparison", "provider_unavailable"],
        sources=sources,
        data={
            "comparison_status": (
                "dataset_or_split_not_aligned"
                if comparison.payload is not None
                else "unavailable"
            ),
            "real_provider_status": (
                unavailable.payload.get("status")
                if unavailable.payload is not None
                else "unavailable"
            ),
            "rows": {
                "synthetic": {
                    "status": (
                        "not_comparable"
                        if comparison.payload is not None
                        else "unavailable"
                    ),
                    "source": _descriptor(comparison),
                },
                "real_provider": {
                    "status": (
                        "unavailable"
                        if unavailable.payload is None
                        else "unavailable"
                    ),
                    "source": _descriptor(unavailable),
                },
            },
        },
        reason=(
            "available provider artifacts use reviewed-query-pairs-1.1 "
            "development scope and cannot be merged with the Phase 2 held-out package"
        ),
    )


def _limitations_section(
    sources: Mapping[str, _LoadedSource],
) -> dict[str, object]:
    limitations: list[object] = []
    unavailable_sections: list[str] = []
    for name, source in sources.items():
        if source.payload is None:
            unavailable_sections.append(name)
            continue
        source_limitations = source.payload.get("limitations")
        if isinstance(source_limitations, list):
            limitations.extend(source_limitations[:20])
        unsupported = source.payload.get("unsupported_claims")
        if isinstance(unsupported, list):
            limitations.extend(unsupported[:20])
        unavailable = source.payload.get("unavailable_sections")
        if isinstance(unavailable, list):
            limitations.extend(unavailable[:20])
    return _section(
        status="available",
        source_names=list(sources),
        sources=sources,
        data={
            "limitations": limitations,
            "unavailable_source_names": unavailable_sections,
        },
    )


def validate_dashboard_view_manifest(payload: Mapping[str, object]) -> None:
    """Validate the bounded WS9 view-manifest envelope."""
    if payload.get("dashboard_schema_version") != DASHBOARD_SCHEMA_VERSION:
        raise DashboardInputError(
            f"dashboard_schema_version must be {DASHBOARD_SCHEMA_VERSION!r}"
        )
    if payload.get("artifact_kind") != DASHBOARD_ARTIFACT_KIND:
        raise DashboardInputError("artifact_kind must identify the WS9 dashboard")
    inputs = payload.get("input_artifacts")
    if not isinstance(inputs, Mapping):
        raise DashboardInputError("input_artifacts must be an object")
    sections = payload.get("sections")
    if not isinstance(sections, Mapping):
        raise DashboardInputError("sections must be an object")
    if set(sections) != set(SECTION_NAMES):
        raise DashboardInputError("dashboard sections do not match the frozen schema")
    for name in SECTION_NAMES:
        section = sections[name]
        if not isinstance(section, Mapping):
            raise DashboardInputError(f"section {name!r} must be an object")
        status = section.get("status")
        if status not in SECTION_STATUSES:
            raise DashboardInputError(f"section {name!r} has invalid status")
        sources = section.get("source_artifacts")
        if not isinstance(sources, list) or not sources:
            raise DashboardInputError(
                f"section {name!r} must identify source artifacts"
            )
        if status != "available" and not isinstance(section.get("reason"), str):
            raise DashboardInputError(
                f"section {name!r} needs a reason for {status}"
            )
    try:
        validate_redacted_report_payload(payload)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise DashboardInputError(f"invalid dashboard view manifest: {exc}") from exc
    if len(encoded.encode("utf-8")) > MAX_VIEW_MANIFEST_BYTES:
        raise DashboardInputError("dashboard view manifest exceeds its size bound")


def _git_metadata(repo_root: Path) -> dict[str, object]:
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return {"git_commit": None, "git_worktree_dirty": None}
    commit = commit_result.stdout.strip()
    return {
        "git_commit": commit if commit_result.returncode == 0 and commit else None,
        "git_worktree_dirty": bool(
            status_result.returncode == 0 and status_result.stdout.strip()
        ),
    }


def _add_generation_metadata(
    manifest: Mapping[str, object],
    *,
    repo_root: Path,
    allow_metadata_mismatch: bool,
) -> dict[str, object]:
    result = dict(manifest)
    result["generation"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **_git_metadata(repo_root),
    }
    result["export_policy"] = {
        "metadata_mismatch_override": allow_metadata_mismatch,
        "metric_source": "upstream_artifacts",
    }
    return result


def _metadata_mismatch_sections(manifest: Mapping[str, object]) -> list[str]:
    sections = manifest.get("sections")
    if not isinstance(sections, Mapping):
        return []
    return [
        name
        for name, section in sections.items()
        if isinstance(section, Mapping)
        and section.get("status") == "metadata_mismatch"
    ]


def render_dashboard_html(payload: Mapping[str, object]) -> str:
    """Render a bounded, source-referenced HTML view of a dashboard package."""
    validate_dashboard_view_manifest(payload)
    title = "SSCRE Workstream 9 dashboard"
    generation = payload.get("generation")
    generation_text = (
        json.dumps(generation, sort_keys=True, ensure_ascii=False)
        if isinstance(generation, Mapping)
        else "not recorded"
    )
    section_html: list[str] = []
    sections = payload["sections"]
    assert isinstance(sections, Mapping)
    for name in SECTION_NAMES:
        section = sections[name]
        assert isinstance(section, Mapping)
        status = html.escape(str(section.get("status", "unknown")))
        source_items: list[str] = []
        source_artifacts = section.get("source_artifacts")
        if isinstance(source_artifacts, list):
            for source in source_artifacts:
                if isinstance(source, Mapping):
                    metadata = ", ".join(
                        f"{key}={source[key]}"
                        for key in (
                            "measurement_environment",
                            "dataset_version",
                            "evaluation_split",
                        )
                        if source.get(key) is not None
                    )
                    label = str(source.get("path", "unknown"))
                    if metadata:
                        label += f" ({metadata})"
                    source_items.append(
                        "<li>"
                        + html.escape(label)
                        + "</li>"
                    )
        reason = section.get("reason")
        reason_html = (
            f"<p><strong>Reason:</strong> {html.escape(str(reason))}</p>"
            if reason
            else ""
        )
        data = section.get("data")
        data_html = ""
        if data is not None:
            data_json = json.dumps(
                data,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            data_html = f"<pre>{html.escape(data_json)}</pre>"
        anchor = html.escape(name.replace("_", "-"))
        heading = html.escape(name.replace("_", " ").title())
        section_html.append(
            f'<section id="{anchor}">'
            f"<h2>{heading}</h2>"
            f"<p><strong>Status:</strong> {status}</p>"
            "<p><strong>Sources:</strong></p>"
            f"<ul>{''.join(source_items)}</ul>"
            f"{reason_html}{data_html}</section>"
        )
    body = "\n".join(
        [
            f"<h1>{html.escape(title)}</h1>",
            f"<p><strong>Schema:</strong> "
            f"{html.escape(str(payload['dashboard_schema_version']))}</p>",
            f"<p><strong>Generation:</strong> "
            f"{html.escape(generation_text)}</p>",
            "<nav aria-label=\"Dashboard sections\"><ul>"
            + "".join(
                f'<li><a href="#{html.escape(name.replace("_", "-"))}">'
                f"{html.escape(name.replace('_', ' ').title())}</a></li>"
                for name in SECTION_NAMES
            )
            + "</ul></nav>",
            "<main>",
            *section_html,
            "</main>",
        ]
    )
    return (
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;line-height:1.45;margin:2rem;"
        "max-width:70rem}section{border-top:1px solid #ccc;padding:1rem 0}"
        "pre{background:#f6f6f6;overflow:auto;padding:1rem;white-space:pre-wrap;"
        "word-break:break-word}a{margin-right:.75rem}"
        "</style></head><body>"
        f"{body}</body></html>\n"
    )


def export_dashboard(
    *,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    html_output: Path = DEFAULT_HTML_OUTPUT,
    allow_metadata_mismatch: bool = False,
    repo_root: Path | None = None,
    **source_paths: Path | None,
) -> dict[str, object]:
    """Build and write the JSON and static HTML dashboard artifacts."""
    root = repo_root or _repo_root()
    manifest = build_dashboard_view_manifest(
        repo_root=root,
        **source_paths,
    )
    mismatches = _metadata_mismatch_sections(manifest)
    if mismatches and not allow_metadata_mismatch:
        names = ", ".join(mismatches)
        raise DashboardInputError(
            "metadata mismatch requires --allow-metadata-mismatch for diagnostic "
            f"export: {names}"
        )
    exported = _add_generation_metadata(
        manifest,
        repo_root=root,
        allow_metadata_mismatch=allow_metadata_mismatch,
    )
    validate_dashboard_view_manifest(exported)
    json_path = _path_for(json_output, root)
    html_path = _path_for(html_output, root)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(exported, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    html_path.write_text(render_dashboard_html(exported), encoding="utf-8")
    return exported


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in DEFAULT_SOURCE_PATHS.items():
        parser.add_argument(f"--{name.replace('_', '-')}", type=Path, default=default)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML_OUTPUT)
    parser.add_argument(
        "--allow-metadata-mismatch",
        action="store_true",
        help="Write a diagnostic package while recording metadata mismatches.",
    )
    args = parser.parse_args(argv)
    source_paths = {
        f"{name}_path": getattr(args, name) for name in DEFAULT_SOURCE_PATHS
    }
    try:
        export_dashboard(
            json_output=args.json_output,
            html_output=args.html_output,
            allow_metadata_mismatch=args.allow_metadata_mismatch,
            **source_paths,
        )
    except (DashboardInputError, OSError, ValueError) as exc:
        print(f"dashboard export failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.json_output.as_posix()}")
    print(f"wrote {args.html_output.as_posix()}")
    return 0


def build_dashboard_view_manifest(
    *,
    comparison_path: Path | None = None,
    pareto_path: Path | None = None,
    freshness_development_path: Path | None = None,
    freshness_held_out_path: Path | None = None,
    invalidation_path: Path | None = None,
    quality_path: Path | None = None,
    operations_path: Path | None = None,
    provider_comparison_path: Path | None = None,
    provider_unavailable_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, object]:
    """Load aligned artifacts and return a bounded, read-only view manifest."""
    root = repo_root or _repo_root()
    overrides = {
        "comparison": comparison_path,
        "pareto": pareto_path,
        "freshness_development": freshness_development_path,
        "freshness_held_out": freshness_held_out_path,
        "invalidation": invalidation_path,
        "quality": quality_path,
        "operations": operations_path,
        "provider_comparison": provider_comparison_path,
        "provider_unavailable": provider_unavailable_path,
    }
    paths = {
        name: value if value is not None else default
        for name, default in DEFAULT_SOURCE_PATHS.items()
        for value in [overrides[name]]
    }
    sources = _load_sources(paths, repo_root=root)
    comparison = sources["comparison"]
    assert comparison.payload is not None
    primary = _identity(comparison)
    if primary.get("dataset_version") != "reviewed-query-pairs-2.0":
        raise DashboardInputError("comparison dataset_version is not Phase 2.0")
    if primary.get("evaluation_split") != "held-out":
        raise DashboardInputError("comparison evaluation_split must be held-out")
    if not primary.get("split_manifest_sha256"):
        raise DashboardInputError("comparison manifest identity is required")

    comparison_sections = _comparison_sections(comparison, sources, primary)
    sections: dict[str, dict[str, object]] = {
        **comparison_sections,
        "pareto": _pareto_section(sources["pareto"], sources, primary),
        "failure_categories": _quality_section(
            sources["quality"], sources, primary
        ),
        "freshness": _freshness_section(sources, primary),
        "operations": _operations_section(sources["operations"], sources),
        "provider_measurements": _provider_section(sources),
    }
    sections["limitations"] = _limitations_section(sources)
    manifest: dict[str, object] = {
        "dashboard_schema_version": DASHBOARD_SCHEMA_VERSION,
        "artifact_kind": DASHBOARD_ARTIFACT_KIND,
        "input_artifacts": {
            name: _descriptor(source) for name, source in sources.items()
        },
        "primary_evaluation_identity": primary,
        "sections": sections,
    }
    validate_dashboard_view_manifest(manifest)
    return manifest


__all__ = [
    "DASHBOARD_ARTIFACT_KIND",
    "DASHBOARD_SCHEMA_VERSION",
    "DEFAULT_SOURCE_PATHS",
    "DEFAULT_HTML_OUTPUT",
    "DEFAULT_JSON_OUTPUT",
    "DashboardInputError",
    "SECTION_NAMES",
    "build_dashboard_view_manifest",
    "export_dashboard",
    "main",
    "render_dashboard_html",
    "validate_dashboard_view_manifest",
]


if __name__ == "__main__":
    raise SystemExit(main())
