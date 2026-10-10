"""Failure gallery and Workstream 7 quality-analysis contract validation.

See ``docs/phase-2/FAILURE_GALLERY_CONTRACT_v1.md``.
"""

from __future__ import annotations

from collections.abc import Mapping

FAILURE_GALLERY_SCHEMA_VERSION = "failure-gallery-1.0"

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
    _reject_forbidden_example_keys(example, context=context)
    missing = _EMBEDDING_EXAMPLE_REQUIRED_KEYS.difference(example)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"{context} missing required field(s): {names}")
    direction = example.get("direction")
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(f"{context}.direction must be a_to_b or b_to_a")


def _validate_strategy_c_example(
    example: object,
    *,
    index: int,
) -> None:
    section = "strategy_c_failures"
    context = f"failure_gallery.{section}[{index}]"
    if not isinstance(example, dict):
        raise ValueError(f"{context} must be an object")
    _reject_forbidden_example_keys(example, context=context)
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
