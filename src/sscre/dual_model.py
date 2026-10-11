"""Validate and optionally run the Workstream 9 dual-model experiment.

The runner is opt-in, absent from the default request path, and does not
call providers unless the definition is enabled, approved, and explicitly
invoked.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic
from typing import Mapping

from sscre.benchmark import load_benchmark_jsonl
from sscre.benchmark_splits import file_sha256, load_split_manifest
from sscre.llm import LLMClient, LLMResult, validate_llm_result
from sscre.pricing import PricingSchedule, estimate_request_cost
from sscre.provider_config import RealProviderConfig
from sscre.remote_llm import OpenAICompatibleLLMClient
from sscre.serialization import validate_redacted_report_payload

DUAL_MODEL_EXPERIMENT_SCHEMA_VERSION = "workstream9-dual-model-experiment-1.0"
DUAL_MODEL_EXPERIMENT_ID = "workstream9-dual-model-v1"
DUAL_MODEL_ARTIFACT_KIND = "workstream9-dual-model-experiment"
DEFAULT_EXPERIMENT_PATH = Path("experiments/workstream9_dual_model_v1.json")
DEFAULT_RESULT_PATH = Path("artifacts/evaluation/workstream9-dual-model-v1.json")
DUAL_MODEL_RESULT_SCHEMA_VERSION = "workstream9-dual-model-result-1.0"
DUAL_MODEL_RESULT_KIND = "workstream9-dual-model-result"
PENDING_IDENTIFIER = "pending_approval"
MAX_DEFINITION_STRING_BYTES = 1024
_PREFERENCE_SUMMARY_KEYS = (
    "assigned_denominator",
    "decided_denominator",
    "assigned",
    "decided",
    "prefer_a",
    "prefer_b",
    "tie",
    "abstain",
    "disagreements",
    "missing_reviews",
)
_BUDGET_USAGE_KEYS = (
    "requests",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "elapsed_seconds",
    "cost_source",
)
_MODEL_OBSERVATION_KEYS = (
    "status",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "retry_count",
    "output_bytes",
    "cost_usd",
    "usage_source",
)
_MODEL_OBSERVATION_STATUSES = frozenset(
    {
        "ok",
        "timeout",
        "transient",
        "permanent",
        "validation",
        "budget_exhausted",
    }
)
_ERROR_STATUS = {
    "timeout": "timeout",
    "authentication": "permanent",
    "authorization": "permanent",
    "permanent_provider": "permanent",
    "transient_provider": "transient",
    "rate_limited": "transient",
    "malformed_response": "validation",
    "validation": "validation",
}
_REQUIRED_TOP_LEVEL = (
    "dual_model_experiment_schema_version",
    "experiment_id",
    "hypothesis",
    "competing_interpretation",
    "models",
    "generation",
    "sample",
    "preference_review",
    "correctness_unavailable",
    "budget",
    "decision",
    "provider_failures",
    "safety",
    "approval",
    "enabled",
)


class DualModelExperimentError(ValueError):
    """Raised when a dual-model experiment definition is invalid."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DualModelExperimentError(f"{name} must be an object")
    return value


def _require_str(value: object, name: str, *, allow_pending: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DualModelExperimentError(f"{name} must be a non-empty string")
    if len(value.encode("utf-8")) > MAX_DEFINITION_STRING_BYTES:
        raise DualModelExperimentError(f"{name} exceeds its string bound")
    if not allow_pending and value == PENDING_IDENTIFIER:
        raise DualModelExperimentError(f"{name} is still pending approval")
    return value


def _require_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise DualModelExperimentError(f"{name} must be a boolean")
    return value


def _require_int(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise DualModelExperimentError(f"{name} must be an integer >= {minimum}")
    return value


def _require_number(value: object, name: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
        raise DualModelExperimentError(f"{name} must be a number >= {minimum}")
    return float(value)


def _validate_models(models: Mapping[str, object], *, enabled: bool) -> None:
    _require_str(models.get("provider"), "models.provider")
    _require_str(models.get("configuration_id"), "models.configuration_id")
    origin = models.get("endpoint_origin")
    origin_status = _require_str(
        models.get("endpoint_origin_status"), "models.endpoint_origin_status"
    )
    model_a = _require_mapping(models.get("model_a"), "models.model_a")
    model_b = _require_mapping(models.get("model_b"), "models.model_b")
    allow_pending = not enabled
    identifier_a = _require_str(
        model_a.get("model_identifier"),
        "models.model_a.model_identifier",
        allow_pending=allow_pending,
    )
    identifier_b = _require_str(
        model_b.get("model_identifier"),
        "models.model_b.model_identifier",
        allow_pending=allow_pending,
    )
    _require_str(model_a.get("role"), "models.model_a.role")
    _require_str(model_b.get("role"), "models.model_b.role")
    _require_str(
        model_a.get("version_identifier"),
        "models.model_a.version_identifier",
        allow_pending=allow_pending,
    )
    _require_str(
        model_b.get("version_identifier"),
        "models.model_b.version_identifier",
        allow_pending=allow_pending,
    )
    if enabled:
        if origin_status != "recorded" or not isinstance(origin, str) or not origin:
            raise DualModelExperimentError(
                "enabled experiments must record a model endpoint origin"
            )
        if identifier_a == identifier_b:
            raise DualModelExperimentError("model A and model B must be different")
    elif origin is not None:
        raise DualModelExperimentError(
            "unapproved experiments must not store an endpoint origin"
        )


def _validate_generation(generation: Mapping[str, object]) -> None:
    for key in (
        "template_id",
        "template_version",
        "system_instruction",
        "user_message_rule",
    ):
        _require_str(generation.get(key), f"generation.{key}")
    _require_number(generation.get("temperature"), "generation.temperature")
    _require_int(generation.get("max_output_tokens"), "generation.max_output_tokens", minimum=1)
    _require_number(generation.get("timeout_seconds"), "generation.timeout_seconds", minimum=0.001)
    _require_int(generation.get("retry_limit"), "generation.retry_limit")
    _require_number(generation.get("min_backoff_seconds"), "generation.min_backoff_seconds")
    _require_number(generation.get("max_backoff_seconds"), "generation.max_backoff_seconds")
    _require_number(
        generation.get("max_retry_elapsed_seconds"),
        "generation.max_retry_elapsed_seconds",
        minimum=0.001,
    )
    _require_int(generation.get("output_byte_limit"), "generation.output_byte_limit", minimum=1)
    if float(generation["max_backoff_seconds"]) < float(generation["min_backoff_seconds"]):
        raise DualModelExperimentError("generation backoff range is invalid")


def _validate_sample(sample: Mapping[str, object]) -> None:
    if sample.get("dataset_version") != "reviewed-query-pairs-2.0":
        raise DualModelExperimentError("sample dataset_version must be Phase 2.0")
    if sample.get("evaluation_split") != "development":
        raise DualModelExperimentError("sample must use the development split")
    _require_str(sample.get("split_manifest_sha256"), "sample.split_manifest_sha256")
    _require_str(sample.get("selection_rule"), "sample.selection_rule")
    if sample.get("operating_point_change") is not False:
        raise DualModelExperimentError("sample must not change the operating point")
    pair_ids = sample.get("pair_ids")
    sample_size = _require_int(sample.get("sample_size"), "sample.sample_size", minimum=1)
    if not isinstance(pair_ids, list) or len(pair_ids) != sample_size:
        raise DualModelExperimentError("sample pair_ids must match sample_size")
    if sample_size > 20:
        raise DualModelExperimentError("sample_size exceeds the frozen bound")
    seen: set[str] = set()
    for index, pair_id in enumerate(pair_ids):
        identifier = _require_str(pair_id, f"sample.pair_ids[{index}]")
        if identifier in seen:
            raise DualModelExperimentError("sample pair_ids must be unique")
        seen.add(identifier)
    exclusions = sample.get("exclusions")
    if not isinstance(exclusions, list) or not exclusions:
        raise DualModelExperimentError("sample exclusions must be a non-empty list")


def _validate_reviews(payload: Mapping[str, object]) -> None:
    preference = _require_mapping(payload.get("preference_review"), "preference_review")
    _require_str(preference.get("question"), "preference_review.question")
    _require_str(preference.get("reviewer_instructions"), "preference_review.reviewer_instructions")
    labels = preference.get("labels")
    if not isinstance(labels, list) or set(labels) != {
        "prefer_a",
        "prefer_b",
        "tie",
        "abstain",
    }:
        raise DualModelExperimentError("preference labels are incomplete")
    _require_int(preference.get("reviewer_count"), "preference_review.reviewer_count", minimum=1)
    correctness = _require_mapping(
        payload.get("correctness_unavailable"), "correctness_unavailable"
    )
    if correctness.get("status") != "unavailable":
        raise DualModelExperimentError("correctness must remain unavailable")
    _require_str(correctness.get("reason"), "correctness_unavailable.reason")
    _require_str(
        correctness.get("missing_label_behavior"),
        "correctness_unavailable.missing_label_behavior",
    )
    if correctness.get("reviewer_count") != 0:
        raise DualModelExperimentError("unavailable correctness cannot assign reviewers")


def _validate_budget_and_decision(payload: Mapping[str, object]) -> None:
    budget = _require_mapping(payload.get("budget"), "budget")
    for key in (
        "max_requests",
        "max_input_tokens",
        "max_output_tokens",
        "max_elapsed_seconds",
        "max_reviewer_assignments",
    ):
        _require_int(budget.get(key), f"budget.{key}", minimum=1)
    _require_number(budget.get("max_cost_usd"), "budget.max_cost_usd", minimum=0.01)
    _require_number(budget.get("max_reviewer_hours"), "budget.max_reviewer_hours", minimum=0.01)
    decision = _require_mapping(payload.get("decision"), "decision")
    _require_int(
        decision.get("minimum_decided_preferences"),
        "decision.minimum_decided_preferences",
        minimum=1,
    )
    _require_str(decision.get("success_criterion"), "decision.success_criterion")
    if decision.get("confidence_method") != "unavailable":
        raise DualModelExperimentError("confidence_method must stay unavailable")
    stopping = _require_mapping(decision.get("stopping_rule"), "decision.stopping_rule")
    stop_on = stopping.get("stop_on")
    if not isinstance(stop_on, list) or "budget_exhausted" not in stop_on:
        raise DualModelExperimentError("stopping rule must include budget exhaustion")


def _validate_safety_and_approval(
    payload: Mapping[str, object],
    *,
    enabled: bool,
) -> None:
    safety = _require_mapping(payload.get("safety"), "safety")
    if safety.get("opt_in_required") is not True:
        raise DualModelExperimentError("dual-model execution must require opt-in")
    if safety.get("absent_from_default_application_path") is not True:
        raise DualModelExperimentError("dual-model execution must stay off the default path")
    approval = _require_mapping(payload.get("approval"), "approval")
    status = _require_str(approval.get("status"), "approval.status")
    model_approved = _require_bool(
        approval.get("model_pair_approved"), "approval.model_pair_approved"
    )
    budget_approved = _require_bool(
        approval.get("budget_approved"), "approval.budget_approved"
    )
    if enabled:
        if status != "approved" or not model_approved or not budget_approved:
            raise DualModelExperimentError(
                "enabled experiments require model-pair and budget approval"
            )
    elif status != "pending" or model_approved or budget_approved:
        raise DualModelExperimentError(
            "disabled experiments must keep approval pending"
        )


def validate_dual_model_experiment(payload: Mapping[str, object]) -> None:
    """Validate the frozen WS9 dual-model experiment definition."""
    for key in _REQUIRED_TOP_LEVEL:
        if key not in payload:
            raise DualModelExperimentError(f"missing field {key}")
    if payload.get("dual_model_experiment_schema_version") != (
        DUAL_MODEL_EXPERIMENT_SCHEMA_VERSION
    ):
        raise DualModelExperimentError("unsupported dual-model experiment schema")
    if payload.get("experiment_id") != DUAL_MODEL_EXPERIMENT_ID:
        raise DualModelExperimentError("experiment_id is not workstream9-dual-model-v1")
    _require_str(payload.get("hypothesis"), "hypothesis")
    _require_str(payload.get("competing_interpretation"), "competing_interpretation")
    enabled = _require_bool(payload.get("enabled"), "enabled")
    _validate_models(_require_mapping(payload.get("models"), "models"), enabled=enabled)
    _validate_generation(_require_mapping(payload.get("generation"), "generation"))
    _validate_sample(_require_mapping(payload.get("sample"), "sample"))
    _validate_reviews(payload)
    _validate_budget_and_decision(payload)
    _validate_safety_and_approval(payload, enabled=enabled)
    failures = _require_mapping(payload.get("provider_failures"), "provider_failures")
    for key in ("timeout", "refusal", "transient", "permanent", "nondeterminism"):
        _require_str(failures.get(key), f"provider_failures.{key}")
    try:
        validate_redacted_report_payload(payload)
    except (TypeError, ValueError) as exc:
        raise DualModelExperimentError(
            f"dual-model definition failed redaction: {exc}"
        ) from exc


def authorize_dual_model_execution(payload: Mapping[str, object]) -> None:
    """Reject execution unless the definition is enabled and approved."""
    validate_dual_model_experiment(payload)
    if payload.get("enabled") is not True:
        raise DualModelExperimentError(
            "dual-model execution is disabled until explicit opt-in approval"
        )


def load_dual_model_experiment(
    path: Path | None = None,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    """Load and validate the checked-in experiment definition."""
    root = repo_root or _repo_root()
    source = path if path is not None else root / DEFAULT_EXPERIMENT_PATH
    if not source.is_file():
        raise DualModelExperimentError(f"dual-model experiment is missing: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DualModelExperimentError(
            f"cannot load dual-model experiment {source}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise DualModelExperimentError("dual-model experiment must be a JSON object")
    validate_dual_model_experiment(payload)
    return payload


def _git_commit(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def _error_status(exc: BaseException) -> str:
    category = getattr(exc, "category", None)
    if isinstance(category, str) and category in _ERROR_STATUS:
        return _ERROR_STATUS[category]
    return "transient"


def _empty_model_observation(status: str) -> dict[str, object]:
    return {
        "status": status,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "retry_count": None,
        "output_bytes": None,
        "cost_usd": None,
        "usage_source": "unavailable",
    }


def _validate_preference_summary(preference: Mapping[str, object], *, name: str) -> None:
    _require_str(preference.get("status"), f"{name}.status")
    _require_str(preference.get("reason"), f"{name}.reason")
    for key in _PREFERENCE_SUMMARY_KEYS:
        _require_int(preference.get(key), f"{name}.{key}")
    assigned = int(preference["assigned"])
    decided = int(preference["decided"])
    assigned_denominator = int(preference["assigned_denominator"])
    decided_denominator = int(preference["decided_denominator"])
    prefer_a = int(preference["prefer_a"])
    prefer_b = int(preference["prefer_b"])
    tie = int(preference["tie"])
    abstain = int(preference["abstain"])
    if assigned > assigned_denominator:
        raise DualModelExperimentError(f"{name}.assigned exceeds assigned_denominator")
    if decided > decided_denominator:
        raise DualModelExperimentError(f"{name}.decided exceeds decided_denominator")
    if prefer_a + prefer_b + tie + abstain > assigned:
        raise DualModelExperimentError(f"{name} label counts exceed assigned reviews")
    if prefer_a + prefer_b + tie > decided:
        raise DualModelExperimentError(f"{name} decided counts exceed decided denominator")


def _validate_correctness_summary(correctness: Mapping[str, object]) -> None:
    status = _require_str(correctness.get("status"), "correctness.status")
    _require_str(correctness.get("reason"), "correctness.reason")
    review_scope = correctness.get("review_scope")
    if review_scope not in {"unavailable", "reviewed", "out_of_scope"}:
        raise DualModelExperimentError("correctness.review_scope is invalid")
    if status == "unavailable" and review_scope != "unavailable":
        raise DualModelExperimentError(
            "unavailable correctness must use review_scope unavailable"
        )
    if status != "unavailable" and review_scope == "unavailable":
        raise DualModelExperimentError(
            "correctness review_scope unavailable requires status unavailable"
        )
    _require_int(correctness.get("reviewer_count"), "correctness.reviewer_count")
    if status == "unavailable" and int(correctness["reviewer_count"]) != 0:
        raise DualModelExperimentError("unavailable correctness cannot assign reviewers")


def _validate_model_observation(observation: Mapping[str, object], *, name: str) -> None:
    for key in _MODEL_OBSERVATION_KEYS:
        if key not in observation:
            raise DualModelExperimentError(f"{name} missing {key}")
    status = _require_str(observation.get("status"), f"{name}.status")
    if status not in _MODEL_OBSERVATION_STATUSES:
        raise DualModelExperimentError(f"{name}.status is invalid")
    _require_str(observation.get("usage_source"), f"{name}.usage_source")


def _validate_pair_row(pair: Mapping[str, object], *, index: int) -> None:
    _require_str(pair.get("pair_id"), f"pairs[{index}].pair_id")
    _validate_model_observation(
        _require_mapping(pair.get("model_a"), f"pairs[{index}].model_a"),
        name=f"pairs[{index}].model_a",
    )
    _validate_model_observation(
        _require_mapping(pair.get("model_b"), f"pairs[{index}].model_b"),
        name=f"pairs[{index}].model_b",
    )
    pair_preference = _require_mapping(pair.get("preference"), f"pairs[{index}].preference")
    pair_correctness = _require_mapping(pair.get("correctness"), f"pairs[{index}].correctness")
    _require_str(pair_preference.get("status"), f"pairs[{index}].preference.status")
    _require_str(pair_correctness.get("status"), f"pairs[{index}].correctness.status")
    for forbidden in ("prefer_a", "prefer_b", "latency_ms", "input_tokens"):
        if forbidden in pair_preference:
            raise DualModelExperimentError(
                f"pairs[{index}].preference must not embed provider measurements"
            )


def _validate_provider_summary(summary: Mapping[str, object]) -> None:
    _require_int(summary.get("pairs_attempted"), "provider_summary.pairs_attempted")
    _require_int(
        summary.get("pairs_with_both_models_ok"),
        "provider_summary.pairs_with_both_models_ok",
    )
    failure_counts = summary.get("failure_counts_by_status")
    if not isinstance(failure_counts, Mapping):
        raise DualModelExperimentError(
            "provider_summary.failure_counts_by_status must be an object"
        )


def validate_dual_model_result(payload: Mapping[str, object]) -> None:
    """Validate a redacted dual-model result artifact."""
    if payload.get("result_schema_version") != DUAL_MODEL_RESULT_SCHEMA_VERSION:
        raise DualModelExperimentError("unsupported dual-model result schema")
    if payload.get("artifact_kind") != DUAL_MODEL_RESULT_KIND:
        raise DualModelExperimentError("artifact_kind must identify a dual-model result")
    if payload.get("experiment_id") != DUAL_MODEL_EXPERIMENT_ID:
        raise DualModelExperimentError("result experiment_id is not workstream9-dual-model-v1")
    status = _require_str(payload.get("status"), "status")
    if status not in {"completed", "stopped", "unavailable"}:
        raise DualModelExperimentError("result status is invalid")
    _require_str(payload.get("stop_reason"), "stop_reason")
    measurement_environment = _require_str(
        payload.get("measurement_environment"), "measurement_environment"
    )
    if status == "unavailable":
        if measurement_environment != "unavailable":
            raise DualModelExperimentError(
                "unavailable results must use measurement_environment unavailable"
            )
        _require_str(payload.get("unavailable_reason"), "unavailable_reason")
    elif measurement_environment == "synthetic":
        raise DualModelExperimentError(
            "synthetic measurement_environment cannot package a dual-model result"
        )
    _validate_preference_summary(_require_mapping(payload.get("preference"), "preference"), name="preference")
    _validate_correctness_summary(_require_mapping(payload.get("correctness"), "correctness"))
    if payload.get("preference_implies_correctness") is True:
        raise DualModelExperimentError("preference must not imply correctness")
    _require_mapping(payload.get("sample"), "sample")
    _require_mapping(payload.get("models"), "models")
    budget_usage = _require_mapping(payload.get("budget_usage"), "budget_usage")
    for key in _BUDGET_USAGE_KEYS:
        if key not in budget_usage:
            raise DualModelExperimentError(f"budget_usage missing {key}")
    _require_str(budget_usage.get("cost_source"), "budget_usage.cost_source")
    _validate_provider_summary(
        _require_mapping(payload.get("provider_summary"), "provider_summary")
    )
    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        raise DualModelExperimentError("pairs must be a list")
    seen_pair_ids: set[str] = set()
    for index, pair in enumerate(pairs):
        if not isinstance(pair, Mapping):
            raise DualModelExperimentError(f"pairs[{index}] must be an object")
        _validate_pair_row(pair, index=index)
        pair_id = str(pair["pair_id"])
        if pair_id in seen_pair_ids:
            raise DualModelExperimentError("pairs must not repeat pair_id values")
        seen_pair_ids.add(pair_id)
    try:
        validate_redacted_report_payload(payload)
    except (TypeError, ValueError) as exc:
        raise DualModelExperimentError(f"dual-model result failed redaction: {exc}") from exc


def _correctness_from_experiment(experiment: Mapping[str, object]) -> dict[str, object]:
    correctness = dict(
        _require_mapping(experiment.get("correctness_unavailable"), "correctness_unavailable")
    )
    correctness["review_scope"] = "unavailable"
    return correctness


def _empty_budget_usage() -> dict[str, object]:
    return {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": None,
        "elapsed_seconds": 0.0,
        "cost_source": "unavailable",
    }


def _empty_preference_summary(*, reason: str) -> dict[str, object]:
    return {
        "status": "unavailable",
        "reason": reason,
        "assigned_denominator": 0,
        "decided_denominator": 0,
        "assigned": 0,
        "decided": 0,
        "prefer_a": 0,
        "prefer_b": 0,
        "tie": 0,
        "abstain": 0,
        "disagreements": 0,
        "missing_reviews": 0,
    }


def _summarize_provider_outcomes(pairs: list[Mapping[str, object]]) -> dict[str, object]:
    failure_counts: dict[str, int] = {}
    pairs_with_both_ok = 0
    for pair in pairs:
        model_a = _require_mapping(pair.get("model_a"), "pair.model_a")
        model_b = _require_mapping(pair.get("model_b"), "pair.model_b")
        if model_a.get("status") == "ok" and model_b.get("status") == "ok":
            pairs_with_both_ok += 1
        for observation in (model_a, model_b):
            status = observation.get("status")
            if isinstance(status, str):
                failure_counts[status] = failure_counts.get(status, 0) + 1
    return {
        "pairs_attempted": len(pairs),
        "pairs_with_both_models_ok": pairs_with_both_ok,
        "failure_counts_by_status": dict(sorted(failure_counts.items())),
    }


def _summarize_preference_outcomes(
    pairs: list[Mapping[str, object]],
    *,
    preference_review: Mapping[str, object],
    review_ran: bool,
) -> dict[str, object]:
    if not review_ran:
        eligible = sum(
            1
            for pair in pairs
            if _require_mapping(pair.get("model_a"), "model_a").get("status") == "ok"
            and _require_mapping(pair.get("model_b"), "model_b").get("status") == "ok"
        )
        reviewer_count = int(preference_review["reviewer_count"])
        assigned_denominator = eligible * reviewer_count
        return {
            **_empty_preference_summary(reason="review_not_run"),
            "assigned_denominator": assigned_denominator,
            "missing_reviews": eligible * reviewer_count,
        }

    assigned_denominator = 0
    decided_denominator = 0
    assigned = 0
    decided = 0
    prefer_a = 0
    prefer_b = 0
    tie = 0
    abstain = 0
    disagreements = 0
    missing_reviews = 0
    for pair in pairs:
        pair_preference = _require_mapping(pair.get("preference"), "pair.preference")
        label = pair_preference.get("label")
        review_status = pair_preference.get("status")
        if review_status == "missing":
            missing_reviews += 1
            continue
        if review_status != "decided":
            continue
        assigned += 1
        assigned_denominator += 1
        if label == "abstain":
            abstain += 1
            continue
        decided += 1
        decided_denominator += 1
        if label == "prefer_a":
            prefer_a += 1
        elif label == "prefer_b":
            prefer_b += 1
        elif label == "tie":
            tie += 1
        if pair_preference.get("reviewer_disagreement") is True:
            disagreements += 1
    return {
        "status": "available" if decided > 0 else "unavailable",
        "reason": "review_complete" if decided > 0 else "no_decided_preferences",
        "assigned_denominator": assigned_denominator,
        "decided_denominator": decided_denominator,
        "assigned": assigned,
        "decided": decided,
        "prefer_a": prefer_a,
        "prefer_b": prefer_b,
        "tie": tie,
        "abstain": abstain,
        "disagreements": disagreements,
        "missing_reviews": missing_reviews,
    }


def _result_identity_fields(
    experiment: Mapping[str, object],
    *,
    config_path: Path | None,
    repo_root: Path,
) -> dict[str, object]:
    generation = _require_mapping(experiment.get("generation"), "generation")
    models = _require_mapping(experiment.get("models"), "models")
    sample = _require_mapping(experiment.get("sample"), "sample")
    model_a = _require_mapping(models.get("model_a"), "models.model_a")
    model_b = _require_mapping(models.get("model_b"), "models.model_b")
    return {
        "artifact_kind": DUAL_MODEL_RESULT_KIND,
        "result_schema_version": DUAL_MODEL_RESULT_SCHEMA_VERSION,
        "experiment_id": experiment["experiment_id"],
        "experiment_schema_version": experiment["dual_model_experiment_schema_version"],
        "config_path": (
            config_path.as_posix()
            if config_path is not None
            else DEFAULT_EXPERIMENT_PATH.as_posix()
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(repo_root),
        "generation": {
            "template_id": generation["template_id"],
            "template_version": generation["template_version"],
        },
        "models": {
            "provider": models["provider"],
            "endpoint_origin": models.get("endpoint_origin"),
            "configuration_id": models["configuration_id"],
            "model_a": {
                "role": model_a["role"],
                "model_identifier": model_a["model_identifier"],
                "version_identifier": model_a["version_identifier"],
            },
            "model_b": {
                "role": model_b["role"],
                "model_identifier": model_b["model_identifier"],
                "version_identifier": model_b["version_identifier"],
            },
        },
        "sample": {
            "dataset_version": sample["dataset_version"],
            "evaluation_split": sample["evaluation_split"],
            "split_manifest_sha256": sample["split_manifest_sha256"],
            "declared_pair_ids": list(sample["pair_ids"]),
        },
        "correctness": _correctness_from_experiment(experiment),
        "preference_implies_correctness": False,
    }


def resolve_dual_model_unavailable_reason(
    experiment: Mapping[str, object],
) -> str | None:
    """Return a packaging reason when live execution must not run."""
    validate_dual_model_experiment(experiment)
    if experiment.get("enabled") is not True:
        return "experiment_disabled"
    approval = _require_mapping(experiment.get("approval"), "approval")
    if (
        approval.get("status") != "approved"
        or approval.get("model_pair_approved") is not True
        or approval.get("budget_approved") is not True
    ):
        return "approval_pending"
    config = RealProviderConfig.from_environment()
    if config is None or not config.credential_configured:
        return "credentials_unavailable"
    models = _require_mapping(experiment.get("models"), "models")
    if config.provider != models.get("provider"):
        return "provider_configuration_mismatch"
    if config.endpoint_origin != models.get("endpoint_origin"):
        return "endpoint_origin_mismatch"
    return None


def build_unavailable_dual_model_result(
    experiment: Mapping[str, object],
    *,
    unavailable_reason: str,
    repo_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, object]:
    """Package an auditable unavailable result without provider substitution."""
    validate_dual_model_experiment(experiment)
    root = repo_root or _repo_root()
    sample = _require_mapping(experiment.get("sample"), "sample")
    budget = _require_mapping(experiment.get("budget"), "budget")
    preference_review = _require_mapping(experiment.get("preference_review"), "preference_review")
    declared_pair_ids = [str(pair_id) for pair_id in sample["pair_ids"]]
    identity = _result_identity_fields(experiment, config_path=config_path, repo_root=root)
    result = {
        **identity,
        "status": "unavailable",
        "unavailable_reason": unavailable_reason,
        "stop_reason": "not_executed",
        "measurement_environment": "unavailable",
        "sample": {
            **identity["sample"],
            "loaded_pair_ids": [],
            "excluded_pairs": [],
            "exclusion_policy": list(sample["exclusions"]),
            "unattempted_pair_ids": declared_pair_ids,
        },
        "pairs": [],
        "provider_summary": _summarize_provider_outcomes([]),
        "budget_usage": _empty_budget_usage(),
        "budget_limits": {
            "max_requests": budget["max_requests"],
            "max_input_tokens": budget["max_input_tokens"],
            "max_output_tokens": budget["max_output_tokens"],
            "max_cost_usd": budget["max_cost_usd"],
            "max_elapsed_seconds": budget["max_elapsed_seconds"],
            "max_reviewer_assignments": budget["max_reviewer_assignments"],
        },
        "preference": _summarize_preference_outcomes(
            [],
            preference_review=preference_review,
            review_ran=False,
        ),
        "limitations": [
            "No approved provider request was executed for this artifact.",
            "Synthetic provider measurements were not substituted.",
            "Preference review was not run and remains unavailable.",
            "Correctness remains unavailable and is not inferred from preference.",
            "This artifact does not change the default application path.",
        ],
    }
    validate_dual_model_result(result)
    return result


def package_dual_model_result(
    experiment: Mapping[str, object],
    *,
    repo_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, object]:
    """Write a unavailable artifact or raise when live execution is required."""
    reason = resolve_dual_model_unavailable_reason(experiment)
    if reason is not None:
        return build_unavailable_dual_model_result(
            experiment,
            unavailable_reason=reason,
            repo_root=repo_root,
            config_path=config_path,
        )
    raise DualModelExperimentError(
        "live dual-model execution requires --opt-in after packaging checks pass"
    )


class _ExperimentGenerationClient:
    """Apply the approved experiment generation settings at the provider boundary."""

    def __init__(
        self,
        client: LLMClient,
        *,
        generation: Mapping[str, object],
    ) -> None:
        self._client = client
        self._generation = generation

    def generate(self, query: str) -> LLMResult:
        if isinstance(self._client, OpenAICompatibleLLMClient):
            return validate_llm_result(
                self._client.generate(
                    query,
                    system_instruction=str(self._generation["system_instruction"]),
                    temperature=float(self._generation["temperature"]),
                    max_output_tokens=int(self._generation["max_output_tokens"]),
                )
            )
        return validate_llm_result(self._client.generate(query))


def build_provider_clients(experiment: Mapping[str, object]) -> dict[str, LLMClient]:
    """Build remote clients only after the experiment is authorized."""
    authorize_dual_model_execution(experiment)
    config = RealProviderConfig.from_environment()
    if config is None or not config.credential_configured:
        raise DualModelExperimentError("real-provider credentials are unavailable")
    generation = _require_mapping(experiment.get("generation"), "generation")
    config = replace(
        config,
        generation_timeout_seconds=float(generation["timeout_seconds"]),
        retry_limit=int(generation["retry_limit"]),
        min_backoff_seconds=float(generation["min_backoff_seconds"]),
        max_backoff_seconds=float(generation["max_backoff_seconds"]),
        max_retry_elapsed_seconds=float(generation["max_retry_elapsed_seconds"]),
    )
    models = _require_mapping(experiment.get("models"), "models")
    if config.provider != models.get("provider"):
        raise DualModelExperimentError("provider does not match the approved experiment")
    if config.endpoint_origin != models.get("endpoint_origin"):
        raise DualModelExperimentError("endpoint origin does not match the approved experiment")
    model_a = _require_mapping(models.get("model_a"), "models.model_a")
    model_b = _require_mapping(models.get("model_b"), "models.model_b")
    wrapped_generation = dict(generation)
    return {
        "model_a": _ExperimentGenerationClient(
            OpenAICompatibleLLMClient(
                replace(config, generation_model=str(model_a["model_identifier"]))
            ),
            generation=wrapped_generation,
        ),
        "model_b": _ExperimentGenerationClient(
            OpenAICompatibleLLMClient(
                replace(config, generation_model=str(model_b["model_identifier"]))
            ),
            generation=wrapped_generation,
        ),
    }


def _load_declared_sample(
    experiment: Mapping[str, object],
    *,
    repo_root: Path,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    sample = _require_mapping(experiment.get("sample"), "sample")
    manifest_path = repo_root / "benchmarks" / "split_manifest.json"
    declared_manifest = str(sample["split_manifest_sha256"])
    if not manifest_path.is_file():
        raise DualModelExperimentError("benchmark split manifest is missing")
    if file_sha256(manifest_path) != declared_manifest:
        raise DualModelExperimentError(
            "benchmark split manifest does not match declared sample identity"
        )
    manifest = load_split_manifest(manifest_path)
    if manifest.get("dataset_version") != sample.get("dataset_version"):
        raise DualModelExperimentError("sample dataset_version does not match manifest")
    benchmark_path = repo_root / str(sample.get("benchmark_path"))
    records = {record.id: record for record in load_benchmark_jsonl(benchmark_path)}
    queries: dict[str, str] = {}
    excluded: list[dict[str, str]] = []
    for pair_id in sample["pair_ids"]:
        identifier = str(pair_id)
        record = records.get(identifier)
        if record is None:
            excluded.append({"pair_id": identifier, "reason": "pair_not_in_benchmark"})
            continue
        if record.review_status != "final":
            excluded.append({"pair_id": identifier, "reason": "review_status_not_final"})
            continue
        if record.freshness_class != "stable":
            excluded.append({"pair_id": identifier, "reason": "freshness_class_not_stable"})
            continue
        queries[identifier] = record.query_a
    return queries, excluded


def _observe_generation(
    client: LLMClient,
    query: str,
    *,
    generation: Mapping[str, object],
    pricing_schedule: PricingSchedule | None,
) -> dict[str, object]:
    try:
        result = validate_llm_result(client.generate(query))
    except Exception as exc:
        return _empty_model_observation(_error_status(exc))
    if not isinstance(result, LLMResult):
        return _empty_model_observation("validation")
    output_bytes = len(result.text.encode("utf-8"))
    status = (
        "validation"
        if output_bytes > int(generation["output_byte_limit"])
        else "ok"
    )
    cost = estimate_request_cost(
        pricing_schedule,
        generation_input_tokens=result.input_tokens,
        generation_output_tokens=result.output_tokens,
        cache_lookup=False,
        preprocessing=False,
    )
    return {
        "status": status,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "retry_count": result.retry_count,
        "output_bytes": output_bytes,
        "cost_usd": cost.total_estimated_cost_usd,
        "usage_source": result.usage_source,
    }


def run_dual_model_experiment(
    experiment: Mapping[str, object],
    *,
    clients: Mapping[str, LLMClient],
    repo_root: Path | None = None,
    config_path: Path | None = None,
    pricing_schedule: PricingSchedule | None = None,
    measurement_environment: str = "injected_test",
) -> dict[str, object]:
    """Run the authorized experiment through injected or approved clients."""
    authorize_dual_model_execution(experiment)
    if set(clients) != {"model_a", "model_b"}:
        raise DualModelExperimentError("clients must provide model_a and model_b")
    if measurement_environment == "synthetic":
        raise DualModelExperimentError(
            "synthetic clients cannot substitute for an approved provider run"
        )
    if measurement_environment == "real_provider" and pricing_schedule is None:
        raise DualModelExperimentError(
            "real-provider execution requires a pricing schedule for cost-budget enforcement"
        )
    root = repo_root or _repo_root()
    sample = _require_mapping(experiment.get("sample"), "sample")
    budget = _require_mapping(experiment.get("budget"), "budget")
    generation = _require_mapping(experiment.get("generation"), "generation")
    models = _require_mapping(experiment.get("models"), "models")
    decision = _require_mapping(experiment.get("decision"), "decision")
    stopping = _require_mapping(decision.get("stopping_rule"), "decision.stopping_rule")
    minimum_decided_preferences = int(decision["minimum_decided_preferences"])
    queries, excluded = _load_declared_sample(experiment, repo_root=root)
    loaded_ids = [str(pair_id) for pair_id in sample["pair_ids"] if pair_id in queries]
    if not loaded_ids:
        raise DualModelExperimentError("declared sample produced no loadable pairs")
    max_requests = int(budget["max_requests"])
    max_input_tokens = int(budget["max_input_tokens"])
    max_output_tokens = int(budget["max_output_tokens"])
    max_elapsed = float(budget["max_elapsed_seconds"])
    max_cost = float(budget["max_cost_usd"])
    consecutive_limit = int(stopping["consecutive_provider_failure_pairs"])
    started = monotonic()
    usage = {
        "requests": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "elapsed_seconds": 0.0,
        "cost_source": "unavailable" if pricing_schedule is None else "measured",
    }
    pairs: list[dict[str, object]] = []
    unattempted = list(loaded_ids)
    stop_reason = "sample_complete"
    consecutive_failures = 0

    def budget_exhausted() -> bool:
        usage["elapsed_seconds"] = round(monotonic() - started, 3)
        if usage["requests"] >= max_requests:
            return True
        if usage["input_tokens"] >= max_input_tokens:
            return True
        if usage["output_tokens"] >= max_output_tokens:
            return True
        if usage["elapsed_seconds"] >= max_elapsed:
            return True
        measured_cost = usage["cost_usd"]
        if measured_cost is not None and measured_cost >= max_cost:
            return True
        return False

    for pair_id in list(unattempted):
        if budget_exhausted():
            stop_reason = "budget_exhausted"
            break
        query = queries[pair_id]
        pair_observations: dict[str, object] = {"pair_id": pair_id}
        pair_failed = False
        pair_permanent = False
        for model_name in ("model_a", "model_b"):
            if budget_exhausted():
                pair_observations[model_name] = _empty_model_observation("budget_exhausted")
                stop_reason = "budget_exhausted"
                pair_failed = True
                continue
            observation = _observe_generation(
                clients[model_name],
                query,
                generation=generation,
                pricing_schedule=pricing_schedule,
            )
            usage["requests"] += 1
            if observation["input_tokens"] is not None:
                usage["input_tokens"] += int(observation["input_tokens"])
            if observation["output_tokens"] is not None:
                usage["output_tokens"] += int(observation["output_tokens"])
            if observation["cost_usd"] is not None:
                usage["cost_usd"] = round(usage["cost_usd"] + float(observation["cost_usd"]), 6)
            pair_observations[model_name] = observation
            if observation["status"] != "ok":
                pair_failed = True
            if observation["status"] == "permanent":
                pair_permanent = True
        pair_observations["preference"] = {
            "status": "unavailable",
            "reason": "review_not_run",
        }
        pair_observations["correctness"] = {
            "status": "unavailable",
            "reason": "correctness_unavailable",
        }
        pairs.append(pair_observations)
        unattempted.remove(pair_id)
        if pair_permanent:
            stop_reason = "permanent_provider_failure"
            break
        if pair_failed:
            consecutive_failures += 1
            if consecutive_failures >= consecutive_limit:
                stop_reason = "consecutive_provider_failures"
                break
        else:
            consecutive_failures = 0
        if budget_exhausted() and unattempted:
            stop_reason = "budget_exhausted"
            break
    else:
        stop_reason = "sample_complete"

    usage["elapsed_seconds"] = round(monotonic() - started, 3)
    if pricing_schedule is None:
        usage["cost_usd"] = None
    preference_review = _require_mapping(experiment.get("preference_review"), "preference_review")
    preference_summary = _summarize_preference_outcomes(
        pairs,
        preference_review=preference_review,
        review_ran=False,
    )
    if (
        stop_reason == "sample_complete"
        and int(preference_summary["decided"]) < minimum_decided_preferences
    ):
        stop_reason = "review_shortfall"
    identity = _result_identity_fields(experiment, config_path=config_path, repo_root=root)
    result: dict[str, object] = {
        **identity,
        "status": "stopped" if stop_reason != "sample_complete" else "completed",
        "stop_reason": stop_reason,
        "measurement_environment": measurement_environment,
        "sample": {
            **identity["sample"],
            "loaded_pair_ids": loaded_ids,
            "excluded_pairs": excluded,
            "exclusion_policy": list(sample["exclusions"]),
            "unattempted_pair_ids": unattempted,
        },
        "pairs": pairs,
        "provider_summary": _summarize_provider_outcomes(pairs),
        "budget_usage": usage,
        "budget_limits": {
            "max_requests": budget["max_requests"],
            "max_input_tokens": budget["max_input_tokens"],
            "max_output_tokens": budget["max_output_tokens"],
            "max_cost_usd": budget["max_cost_usd"],
            "max_elapsed_seconds": budget["max_elapsed_seconds"],
            "max_reviewer_assignments": budget["max_reviewer_assignments"],
        },
        "preference": preference_summary,
        "limitations": [
            "Unrestricted prompts and answers are not stored.",
            "Preference review was not run by this runner.",
            "Correctness remains unavailable and is not inferred from preference.",
            "This runner does not change the default application path.",
        ],
    }
    validate_dual_model_result(result)
    return result


def write_dual_model_result(payload: Mapping[str, object], path: Path) -> None:
    validate_dual_model_result(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_EXPERIMENT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT_PATH)
    parser.add_argument(
        "--package-unavailable",
        action="store_true",
        help=(
            "Write an auditable unavailable result when execution is disabled, "
            "unapproved, or lacks credentials. Does not call providers."
        ),
    )
    parser.add_argument(
        "--opt-in",
        action="store_true",
        help="Required for live provider execution after approval and credentials.",
    )
    args = parser.parse_args(argv)
    try:
        experiment = load_dual_model_experiment(args.config)
        if args.package_unavailable:
            reason = resolve_dual_model_unavailable_reason(experiment)
            if reason is None:
                raise DualModelExperimentError(
                    "experiment is ready for live execution; use --opt-in instead"
                )
            result = build_unavailable_dual_model_result(
                experiment,
                unavailable_reason=reason,
                config_path=args.config,
            )
        elif args.opt_in:
            clients = build_provider_clients(experiment)
            result = run_dual_model_experiment(
                experiment,
                clients=clients,
                config_path=args.config,
                measurement_environment="real_provider",
            )
        else:
            print(
                "dual-model requires --package-unavailable or --opt-in",
                file=sys.stderr,
            )
            return 1
        write_dual_model_result(result, args.output)
    except (DualModelExperimentError, OSError, ValueError) as exc:
        print(f"dual-model run failed: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {args.output.as_posix()}")
    return 0


__all__ = [
    "DEFAULT_EXPERIMENT_PATH",
    "DEFAULT_RESULT_PATH",
    "DUAL_MODEL_ARTIFACT_KIND",
    "DUAL_MODEL_EXPERIMENT_ID",
    "DUAL_MODEL_EXPERIMENT_SCHEMA_VERSION",
    "DUAL_MODEL_RESULT_KIND",
    "DUAL_MODEL_RESULT_SCHEMA_VERSION",
    "DualModelExperimentError",
    "authorize_dual_model_execution",
    "build_provider_clients",
    "build_unavailable_dual_model_result",
    "load_dual_model_experiment",
    "main",
    "package_dual_model_result",
    "resolve_dual_model_unavailable_reason",
    "run_dual_model_experiment",
    "validate_dual_model_experiment",
    "validate_dual_model_result",
    "write_dual_model_result",
]


if __name__ == "__main__":
    raise SystemExit(main())
