"""CLI for Workstream 6 freshness-policy replay."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from sscre import __version__
from sscre.benchmark import load_benchmark_jsonl
from sscre.evaluate import (
    _git_commit,
    _git_worktree_dirty,
    _load_config,
    _select_development_threshold,
    _validate_split,
)
from sscre.freshness_policy_selection import resolve_selected_policy_argument
from sscre.freshness_artifacts import (
    attach_freshness_artifact_metadata,
    resolve_invalidation_output_path,
    validate_freshness_artifact_package,
    write_invalidation_sidecar,
)
from sscre.freshness_replay import (
    build_freshness_replay_report,
    write_freshness_replay_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Workstream 6 freshness-policy replay.",
    )
    parser.add_argument("--benchmark", required=True, help="Benchmark JSONL path.")
    parser.add_argument("--config", required=True, help="Evaluation JSON path.")
    parser.add_argument(
        "--split",
        choices=("development", "held-out"),
        default="development",
        help="Benchmark split to replay.",
    )
    parser.add_argument("--output", required=True, help="Output report JSON path.")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Require final review status on every source record.",
    )
    parser.add_argument(
        "--selected-policy",
        help=(
            "Policy name or development artifact JSON path for held-out replay "
            "(required when split is held-out)."
        ),
    )
    parser.add_argument(
        "--invalidation-output",
        help=(
            "Optional path for the invalidation sidecar JSON "
            "(defaults next to standard development artifact output)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
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
        manifest = _validate_split(
            benchmark_path,
            args.split,
            config["dataset_version"],
            records,
            production=args.production,
        )
        selection = _select_development_threshold(benchmark_path, config)
        if args.split == "held-out" and not args.selected_policy:
            raise ValueError(
                "--selected-policy is required for held-out freshness replay"
            )
        selected_policy_name: str | None = None
        frozen_selection: dict[str, object] | None = None
        if args.selected_policy:
            selected_policy_name, frozen = resolve_selected_policy_argument(
                args.selected_policy
            )
            frozen_selection = frozen
        git_commit = _git_commit()
        git_dirty = _git_worktree_dirty()
        manifest_path = benchmark_path.parent / "split_manifest.json"
        from sscre.benchmark_splits import build_benchmark_report_metadata

        report = build_freshness_replay_report(
            records,
            config=config,
            split=args.split,
            selected_threshold=selection.selected_threshold,
            threshold_selection_rule=selection.selection_rule,
            selected_policy_name=selected_policy_name,
            frozen_development_selection=frozen_selection,
            git_commit=git_commit,
            git_worktree_dirty=git_dirty,
        )
        config_path = Path(args.config)
        report.update(
            {
                "execution_timestamp": datetime.now(timezone.utc).isoformat(),
                "software_version": __version__,
                "git_commit": git_commit,
                "git_worktree_dirty": git_dirty,
                "benchmark_artifact": build_benchmark_report_metadata(
                    manifest,
                    split=args.split,
                    records=records,
                    manifest_path=manifest_path,
                ),
            }
        )
        output_path = Path(args.output)
        report = attach_freshness_artifact_metadata(
            report,
            config_path=config_path,
            benchmark_path=benchmark_path,
            split=args.split,
            production=require_final_review,
            selected_policy_arg=args.selected_policy,
        )
        validate_freshness_artifact_package(report)
        write_freshness_replay_report(output_path, report)

        invalidation_path: Path | None = None
        if args.invalidation_output:
            invalidation_path = Path(args.invalidation_output)
        elif args.split == "development":
            invalidation_path = resolve_invalidation_output_path(output_path)
        if invalidation_path is not None:
            write_invalidation_sidecar(
                report,
                invalidation_path,
                source_artifact_path=output_path,
            )
    except ValueError as exc:
        parser.error(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
