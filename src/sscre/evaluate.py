"""Command-line entry point for benchmark evaluation."""

import argparse
from dataclasses import asdict
import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sscre.baseline import (
    run_compatibility_cache_baseline,
    select_adaptive_domain_thresholds,
    run_exact_cache_baseline,
    run_embedding_cache_baseline,
    run_embedding_threshold_sweep,
    run_no_cache_baseline,
    save_exact_cache_report,
    save_embedding_sweep_report,
    save_embedding_cache_report,
    save_compatibility_cache_report,
    save_no_cache_report,
)
from sscre.benchmark import BenchmarkValidationError, load_benchmark_jsonl
from sscre.embedding import EmbeddingClient, FakeEmbeddingClient
from sscre.benchmark_annotation import validate_review_policy
from sscre.benchmark_splits import (
    build_benchmark_report_metadata,
    validate_benchmark_dataset,
)
from sscre import __version__
from sscre.evaluation_statistics import (
    apply_statistics_config_defaults,
    build_comparison_statistics,
)
from sscre.failure_quality import enrich_failure_gallery
from sscre.evaluation_protocol import (
    apply_primary_headline_population_filter,
    resolve_semantic_embedding_client,
    reuse_attribution_summary,
    validate_semantic_validity_cli_options,
)
from sscre.local_embedding import LocalSentenceTransformerEmbeddingClient
from sscre.freshness_artifacts import freshness_companion_artifact_references
from sscre.freshness_evaluation import (
    DEFAULT_REPLAY_ANCHOR_TIME,
    FreshnessReplayClock,
    apply_freshness_experiment_config_defaults,
    freshness_experiment_from_mapping,
)
from sscre.serialization import (
    attach_evaluation_report_schema,
    redact_operational_evaluation_report,
    validate_redacted_report_payload,
)

_COST_FIELDS = (
    "input_cost_per_1k_tokens",
    "output_cost_per_1k_tokens",
    "embedding_cost_per_1k_tokens",
    "cache_lookup_cost_usd",
    "preprocessing_cost_usd",
)
_SPLIT_FILENAMES = {
    "development": "development.jsonl",
    "held-out": "held_out_test.jsonl",
}
_SPLIT_MANIFEST_KEYS = {
    "development": "development",
    "held-out": "held_out_test",
}


def _load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid configuration {config_path}: {exc}") from exc

    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    dataset_version = config.get("dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise ValueError("configuration requires a non-empty dataset_version")
    config_version = config.get("config_version")
    if not isinstance(config_version, str) or not config_version.strip():
        raise ValueError("configuration requires a non-empty config_version")

    for field_name in _COST_FIELDS:
        value = config.get(field_name, 0.0)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{field_name} must be a finite non-negative number")
        config[field_name] = float(value)

    thresholds = config.get("embedding_thresholds", [0.8, 0.9, 0.95])
    if (
        not isinstance(thresholds, list)
        or not thresholds
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not -1.0 <= value <= 1.0
            for value in thresholds
        )
    ):
        raise ValueError(
            "embedding_thresholds must be a non-empty list between -1 and 1"
        )
    config["embedding_thresholds"] = [float(value) for value in thresholds]

    top_k = config.get("embedding_top_k", 5)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("embedding_top_k must be a positive integer")
    config["embedding_top_k"] = top_k

    max_false_positive_rate = config.get("max_false_positive_rate", 0.0)
    if (
        isinstance(max_false_positive_rate, bool)
        or not isinstance(max_false_positive_rate, (int, float))
        or not math.isfinite(max_false_positive_rate)
        or not 0.0 <= max_false_positive_rate <= 1.0
    ):
        raise ValueError("max_false_positive_rate must be between 0 and 1")
    config["max_false_positive_rate"] = float(max_false_positive_rate)
    apply_statistics_config_defaults(config)
    apply_freshness_experiment_config_defaults(config)
    return config


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


def _git_worktree_dirty() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def _validate_split(
    benchmark_path: Path,
    split: str,
    dataset_version: str,
    records: list,
    *,
    validate_full_dataset: bool = True,
    production: bool = False,
) -> dict[str, Any]:
    expected_filename = _SPLIT_FILENAMES[split]
    if benchmark_path.name != expected_filename:
        raise ValueError(
            f"--split {split!r} requires {expected_filename!r}"
        )

    manifest_path = benchmark_path.parent / "split_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid split manifest {manifest_path}: {exc}") from exc

    if manifest.get("dataset_version") != dataset_version:
        raise ValueError("split manifest and configuration dataset versions differ")

    split_metadata = manifest.get(_SPLIT_MANIFEST_KEYS[split])
    if not isinstance(split_metadata, dict):
        raise ValueError(f"split manifest has no {split!r} entry")

    manifest_path_value = split_metadata.get("path")
    if not isinstance(manifest_path_value, str):
        raise ValueError(f"split manifest has no path for {split!r}")
    manifest_root = manifest_path.parent.parent
    manifest_benchmark_path = (manifest_root / manifest_path_value).resolve()
    if manifest_benchmark_path != benchmark_path.resolve():
        raise ValueError(f"benchmark path does not match the {split!r} manifest entry")

    record_count = split_metadata.get("record_count")
    if record_count != len(records):
        raise ValueError(f"benchmark record count does not match the {split!r} manifest")

    data_dir = manifest_benchmark_path.parent
    full_path = data_dir / "reviewed_query_pairs.jsonl"
    other_split = "held-out" if split == "development" else "development"
    other_path = data_dir / _SPLIT_FILENAMES[other_split]
    load_final = production or split == "held-out"
    full_ids = {
        record.id
        for record in load_benchmark_jsonl(
            full_path,
            require_final_review=load_final,
        )
    }
    selected_ids = {record.id for record in records}
    other_ids = {
        record.id
        for record in load_benchmark_jsonl(
            other_path,
            require_final_review=load_final,
        )
    }
    if not selected_ids <= full_ids:
        raise ValueError(f"{split!r} split contains IDs outside the reviewed dataset")
    if selected_ids & other_ids:
        raise ValueError("development and held-out split IDs overlap")
    if selected_ids | other_ids != full_ids:
        raise ValueError("development and held-out splits do not cover the reviewed dataset")

    try:
        validate_review_policy(records, split=split)
        if validate_full_dataset:
            validate_benchmark_dataset(benchmark_path.parent, production=production)
    except BenchmarkValidationError as exc:
        raise ValueError(str(exc)) from exc

    return manifest


def _select_development_threshold(
    benchmark_path: Path,
    config: dict[str, Any],
    *,
    embedding_client: EmbeddingClient | None = None,
) -> Any:
    development_path = benchmark_path.parent / "development.jsonl"
    development_records = load_benchmark_jsonl(development_path)
    _validate_split(
        development_path,
        "development",
        config["dataset_version"],
        development_records,
        validate_full_dataset=False,
    )
    development_records, _ = apply_primary_headline_population_filter(
        development_records,
        config,
    )
    return run_embedding_threshold_sweep(
        development_records,
        dataset_version=config["dataset_version"],
        thresholds=config["embedding_thresholds"],
        top_k=config["embedding_top_k"],
        max_false_positive_rate=config["max_false_positive_rate"],
        embedding_client=embedding_client,
        input_cost_per_1k_tokens=config["input_cost_per_1k_tokens"],
        output_cost_per_1k_tokens=config["output_cost_per_1k_tokens"],
        embedding_cost_per_1k_tokens=config["embedding_cost_per_1k_tokens"],
        cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
        preprocessing_cost_usd=config["preprocessing_cost_usd"],
    )


def _select_adaptive_thresholds(
    benchmark_path: Path,
    config: dict[str, Any],
    *,
    embedding_client: EmbeddingClient | None = None,
) -> tuple[dict[str, float], dict[str, object]]:
    development_path = benchmark_path.parent / "development.jsonl"
    development_records = load_benchmark_jsonl(development_path)
    _validate_split(
        development_path,
        "development",
        config["dataset_version"],
        development_records,
        validate_full_dataset=False,
    )
    development_records, _ = apply_primary_headline_population_filter(
        development_records,
        config,
    )
    return select_adaptive_domain_thresholds(
        development_records,
        dataset_version=config["dataset_version"],
        thresholds=config["embedding_thresholds"],
        top_k=config["embedding_top_k"],
        max_false_positive_rate=config["max_false_positive_rate"],
        embedding_client=embedding_client,
        input_cost_per_1k_tokens=config["input_cost_per_1k_tokens"],
        output_cost_per_1k_tokens=config["output_cost_per_1k_tokens"],
        embedding_cost_per_1k_tokens=config["embedding_cost_per_1k_tokens"],
        cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
        preprocessing_cost_usd=config["preprocessing_cost_usd"],
    )


def _embedding_run_options(
    config: dict[str, Any],
    embedding_client: EmbeddingClient | None,
) -> dict[str, Any]:
    return {
        "top_k": config["embedding_top_k"],
        "embedding_client": embedding_client,
        "embedding_cost_per_1k_tokens": config["embedding_cost_per_1k_tokens"],
        "cache_lookup_cost_usd": config["cache_lookup_cost_usd"],
        "preprocessing_cost_usd": config["preprocessing_cost_usd"],
    }


def _measurement_environment(
    embedding_client: EmbeddingClient | None,
) -> str:
    if isinstance(embedding_client, LocalSentenceTransformerEmbeddingClient):
        return "local_embedding_replay"
    if embedding_client is not None and not isinstance(
        embedding_client, FakeEmbeddingClient
    ):
        return "provider_replay"
    return "synthetic_replay"


def _embedding_provenance_metadata(
    embedding_client: EmbeddingClient | None,
) -> dict[str, object] | None:
    if embedding_client is None:
        return None
    block: dict[str, object] = {
        "model_name": embedding_client.config.model_name,
        "dimension": embedding_client.config.dimension,
    }
    if isinstance(embedding_client, LocalSentenceTransformerEmbeddingClient):
        block.update(
            {
                "provider_type": "local_sentence_transformer",
                "device": embedding_client.device,
                "normalize_embeddings": embedding_client.normalize_embeddings,
                "batch_behavior": embedding_client.batch_behavior,
            }
        )
    elif not isinstance(embedding_client, FakeEmbeddingClient):
        block["provider_type"] = "remote_or_custom"
    else:
        block["provider_type"] = "synthetic"
    return block


def _runtime_environment_metadata() -> dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def _config_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _optional_artifact_sha256(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_adaptive_threshold_map(
    path: str | Path,
    *,
    config_path: str | Path,
    config: dict[str, Any],
    threshold_map: dict[str, float],
    diagnostics: dict[str, object],
) -> None:
    payload = {
        "schema_version": "phase3-adaptive-thresholds-1.0",
        "dataset_version": config["dataset_version"],
        "config_version": config["config_version"],
        "config_sha256": _config_sha256(config_path),
        "selection_split": "development",
        "default_threshold": diagnostics["default_threshold"],
        "thresholds": diagnostics["thresholds"],
        "threshold_map": threshold_map,
        "selection": diagnostics,
    }
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_adaptive_threshold_map(
    path: str | Path,
    *,
    expected_dataset_version: str | None = None,
    expected_config_version: str | None = None,
    expected_config_sha256: str | None = None,
) -> dict[str, float]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid adaptive threshold map {path}: {exc}") from exc
    threshold_map = payload.get("threshold_map") if isinstance(payload, dict) else None
    if not isinstance(threshold_map, dict) or not threshold_map:
        raise ValueError("adaptive threshold map requires a non-empty threshold_map")
    if payload.get("selection_split") != "development":
        raise ValueError("adaptive threshold map must be selected on development")
    if (
        expected_dataset_version is not None
        and payload.get("dataset_version") != expected_dataset_version
    ):
        raise ValueError("adaptive threshold map dataset version does not match")
    if (
        expected_config_version is not None
        and payload.get("config_version") != expected_config_version
    ):
        raise ValueError("adaptive threshold map config version does not match")
    if (
        expected_config_sha256 is not None
        and payload.get("config_sha256") != expected_config_sha256
    ):
        raise ValueError("adaptive threshold map config hash does not match")
    default_threshold = payload.get("default_threshold", 0.95)
    if (
        isinstance(default_threshold, bool)
        or not isinstance(default_threshold, (int, float))
        or not math.isfinite(default_threshold)
        or not -1.0 <= default_threshold <= 1.0
    ):
        raise ValueError("adaptive threshold map default_threshold is invalid")
    validated: dict[str, float] = {}
    for domain, threshold in threshold_map.items():
        if (
            not isinstance(domain, str)
            or not domain.strip()
            or isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or not -1.0 <= threshold <= 1.0
        ):
            raise ValueError("adaptive threshold map contains an invalid entry")
        validated[domain] = float(threshold)
    validated.setdefault("__default__", float(default_threshold))
    return validated


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate an SSCRE benchmark.")
    parser.add_argument("--benchmark", required=True, help="Benchmark JSONL path.")
    parser.add_argument("--config", required=True, help="Evaluation JSON path.")
    parser.add_argument(
        "--baseline",
        required=True,
        choices=(
            "no-cache",
            "exact-cache",
            "embedding-cache",
            "compatibility-cache",
            "all",
        ),
        help="Baseline strategy to run.",
    )
    parser.add_argument(
        "--split",
        choices=tuple(_SPLIT_FILENAMES),
        default="development",
        help="Declared benchmark split; held-out evaluation must be explicit.",
    )
    parser.add_argument("--output", required=True, help="Output report JSON path.")
    parser.add_argument(
        "--adaptive-threshold-map",
        help="Frozen development-selected Strategy C domain threshold map.",
    )
    parser.add_argument(
        "--adaptive-threshold-map-output",
        help="Write a development-selected Strategy C domain threshold map.",
    )
    parser.add_argument(
        "--freshness-policy",
        help="Apply a named configured freshness policy to Strategy C replay.",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Require final review status on every source record.",
    )
    parser.add_argument(
        "--no-statistics",
        action="store_true",
        help="Omit confidence-interval statistics from evaluation reports.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run evaluation and return a process exit status."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        benchmark_path = Path(args.benchmark)
        require_final_review = args.production or args.split == "held-out"
        records = load_benchmark_jsonl(
            benchmark_path,
            require_final_review=require_final_review,
        )
        config = _load_config(args.config)
        validate_semantic_validity_cli_options(
            config,
            freshness_policy=args.freshness_policy,
            adaptive_threshold_map=args.adaptive_threshold_map,
            adaptive_threshold_map_output=args.adaptive_threshold_map_output,
        )
        embedding_client = resolve_semantic_embedding_client(config)
        freshness_replay_clock = None
        if args.freshness_policy is not None:
            experiment = freshness_experiment_from_mapping(config)
            if experiment is None:
                raise ValueError(
                    "--freshness-policy requires freshness_experiment configuration"
                )
            policy = next(
                (
                    item
                    for item in experiment.policy_matrix
                    if item.name == args.freshness_policy
                ),
                None,
            )
            if policy is None:
                raise ValueError(
                    f"unknown freshness policy {args.freshness_policy!r}"
                )
            freshness_replay_clock = FreshnessReplayClock.from_policy_spec(
                policy,
                DEFAULT_REPLAY_ANCHOR_TIME,
            )
        adaptive_threshold_map = (
            _load_adaptive_threshold_map(
                args.adaptive_threshold_map,
                expected_dataset_version=config["dataset_version"],
                expected_config_version=config["config_version"],
                expected_config_sha256=_config_sha256(args.config),
            )
            if args.adaptive_threshold_map
            else None
        )
        adaptive_threshold_map_path = args.adaptive_threshold_map
        adaptive_diagnostics: dict[str, object] | None = None
        if args.adaptive_threshold_map_output:
            if args.split != "development":
                raise ValueError(
                    "--adaptive-threshold-map-output requires --split development"
                )
            selected_map, adaptive_diagnostics = _select_adaptive_thresholds(
                benchmark_path,
                config,
                embedding_client=embedding_client,
            )
            _write_adaptive_threshold_map(
                args.adaptive_threshold_map_output,
                config_path=args.config,
                config=config,
                threshold_map=selected_map,
                diagnostics=adaptive_diagnostics,
            )
            adaptive_threshold_map = selected_map
            adaptive_threshold_map_path = args.adaptive_threshold_map_output
        attach_statistics = not args.no_statistics
        manifest = _validate_split(
            benchmark_path,
            args.split,
            config["dataset_version"],
            records,
            production=args.production,
        )
        records, primary_headline_population = (
            apply_primary_headline_population_filter(records, config)
        )
        common_options = {
            "dataset_version": config["dataset_version"],
            "input_cost_per_1k_tokens": config["input_cost_per_1k_tokens"],
            "output_cost_per_1k_tokens": config["output_cost_per_1k_tokens"],
        }
        manifest_path = benchmark_path.parent / "split_manifest.json"
        metadata = {
            "config_version": config["config_version"],
            "config_sha256": _config_sha256(args.config),
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "software_version": __version__,
            "git_commit": _git_commit(),
            "git_worktree_dirty": _git_worktree_dirty(),
            "evaluation_split": args.split,
            "benchmark_artifact": build_benchmark_report_metadata(
                manifest,
                split=args.split,
                records=records,
                manifest_path=manifest_path,
            ),
        }
        if primary_headline_population is not None:
            metadata["primary_headline_population"] = primary_headline_population
        embedding_provenance = _embedding_provenance_metadata(embedding_client)
        if embedding_provenance is not None:
            metadata["embedding_provenance"] = embedding_provenance
        metadata["runtime_environment"] = _runtime_environment_metadata()
        metadata["threshold_selection_split"] = "development"
        metadata["held_out_influence"] = "none"
        if args.freshness_policy is not None:
            metadata["freshness_policy_name"] = args.freshness_policy
        adaptive_threshold_map_sha256 = _optional_artifact_sha256(
            adaptive_threshold_map_path
        )
        if adaptive_threshold_map_sha256 is not None:
            metadata["adaptive_threshold_map_sha256"] = (
                adaptive_threshold_map_sha256
            )
        embed_options = _embedding_run_options(config, embedding_client)
        if args.baseline == "all":
            selection = _select_development_threshold(
                benchmark_path,
                config,
                embedding_client=embedding_client,
            )
            compatibility_threshold = adaptive_threshold_map or selection.selected_threshold
            no_cache_report = run_no_cache_baseline(records, **common_options)
            exact_cache_report = run_exact_cache_baseline(
                records,
                **common_options,
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            embedding_report = run_embedding_cache_baseline(
                records,
                **common_options,
                threshold=selection.selected_threshold,
                **embed_options,
            )
            compatibility_report = run_compatibility_cache_baseline(
                records,
                **common_options,
                threshold=compatibility_threshold,
                **embed_options,
                freshness_replay_clock=freshness_replay_clock,
            )
            compatibility_false_positive_keys = {
                (example["id"], example["direction"])
                for example in compatibility_report.false_positive_examples
            }
            caught_embedding_false_positives = [
                example
                for example in embedding_report.false_positive_examples
                if (example["id"], example["direction"])
                not in compatibility_false_positive_keys
            ]
            baseline_payloads = {
                "no-cache": asdict(no_cache_report),
                "exact-cache": asdict(exact_cache_report),
                "embedding-cache": asdict(embedding_report),
                "compatibility-cache": asdict(compatibility_report),
            }
            comparison_body: dict[str, Any] = {
                **metadata,
                "baseline": "comparison",
                "measurement_environment": _measurement_environment(
                    embedding_client
                ),
                "threshold_selection": asdict(selection),
                "threshold_decision": {
                    "selected_threshold": selection.selected_threshold,
                    "selection_rule": selection.selection_rule,
                    "constraint_satisfied": selection.constraint_satisfied,
                    "selection_split": "development",
                    "held_out_records_used": False,
                },
                "reuse_attribution_summary": {
                    name: reuse_attribution_summary(payload)
                    for name, payload in baseline_payloads.items()
                    if name in {"exact-cache", "embedding-cache", "compatibility-cache"}
                },
                "baselines": baseline_payloads,
                "failure_gallery": enrich_failure_gallery(
                    {
                        "embedding_only_false_positives": (
                            embedding_report.false_positive_examples
                        ),
                        "embedding_only_false_positives_caught_by_strategy_c": (
                            caught_embedding_false_positives
                        ),
                        "strategy_c_failures": (
                            compatibility_report.failure_examples
                        ),
                    },
                    records,
                ),
            }
            if attach_statistics:
                comparison_body["statistics"] = build_comparison_statistics(
                    baseline_payloads,
                    config,
                    selected_threshold=selection.selected_threshold,
                    selection_rule=selection.selection_rule,
                    max_false_positive_rate=config["max_false_positive_rate"],
                )
            freshness_refs = freshness_companion_artifact_references(config)
            if freshness_refs is not None:
                comparison_body["freshness_policy_companion_artifacts"] = (
                    freshness_refs
                )
            payload = redact_operational_evaluation_report(
                attach_evaluation_report_schema(comparison_body)
            )
            validate_redacted_report_payload(payload)
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        elif args.baseline == "no-cache":
            report = run_no_cache_baseline(records, **common_options)
            save_no_cache_report(
                report,
                args.output,
                metadata=metadata,
                evaluation_config=config,
                attach_statistics=attach_statistics,
            )
        elif args.baseline == "exact-cache":
            report = run_exact_cache_baseline(
                records,
                **common_options,
                cache_lookup_cost_usd=config["cache_lookup_cost_usd"],
                preprocessing_cost_usd=config["preprocessing_cost_usd"],
            )
            save_exact_cache_report(
                report,
                args.output,
                metadata=metadata,
                evaluation_config=config,
                attach_statistics=attach_statistics,
            )
        elif args.baseline == "compatibility-cache":
            selection = _select_development_threshold(
                benchmark_path,
                config,
                embedding_client=embedding_client,
            )
            compatibility_threshold = (
                adaptive_threshold_map or selection.selected_threshold
            )
            report = run_compatibility_cache_baseline(
                records,
                **common_options,
                threshold=compatibility_threshold,
                **embed_options,
                freshness_replay_clock=freshness_replay_clock,
            )
            metadata.update(
                {
                    "selected_threshold": compatibility_threshold,
                    "threshold_selection_split": "development",
                    "threshold_selection_rule": (
                        "frozen adaptive per-domain map"
                        if adaptive_threshold_map is not None
                        else selection.selection_rule
                    ),
                }
            )
            save_compatibility_cache_report(
                report,
                args.output,
                metadata=metadata,
                evaluation_config=config,
                attach_statistics=attach_statistics,
            )
        elif args.split == "development":
            report = run_embedding_threshold_sweep(
                records,
                **common_options,
                thresholds=config["embedding_thresholds"],
                max_false_positive_rate=config["max_false_positive_rate"],
                **embed_options,
            )
            save_embedding_sweep_report(
                report,
                args.output,
                metadata=metadata,
                evaluation_config=config,
                attach_statistics=attach_statistics,
            )
        else:
            selection = _select_development_threshold(
                benchmark_path,
                config,
                embedding_client=embedding_client,
            )
            report = run_embedding_cache_baseline(
                records,
                **common_options,
                threshold=selection.selected_threshold,
                **embed_options,
            )
            metadata.update(
                {
                    "selected_threshold": selection.selected_threshold,
                    "threshold_selection_split": "development",
                    "threshold_selection_rule": selection.selection_rule,
                }
            )
            save_embedding_cache_report(
                report,
                args.output,
                metadata=metadata,
                evaluation_config=config,
                attach_statistics=attach_statistics,
            )
    except (OSError, ValueError, TypeError) as exc:
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
