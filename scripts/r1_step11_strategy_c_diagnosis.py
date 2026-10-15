"""Research track R1 Step 1.1 — export Strategy C diagnosis (development split only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG = ROOT / "experiments/semantic-validity-evaluation-config-v1.json"
DEFAULT_BENCHMARK = ROOT / "benchmarks/development.jsonl"
DEFAULT_SOURCE_REPORT = (
    ROOT / "artifacts/evaluation/phase4-semantic-validity-development.json"
)
DEFAULT_OUTPUT = ROOT / "artifacts/stabilization/r1-step11-strategy-c-diagnosis.json"


def _load_config(path: Path) -> dict[str, object]:
    from sscre.evaluate import _load_config as load_eval_config

    return load_eval_config(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument(
        "--from-report",
        type=Path,
        default=None,
        help=(
            "Aggregate from an existing evaluation JSON (default: phase4 development "
            "comparison artifact when not using --replay)."
        ),
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Re-run compatibility-cache replay instead of aggregating a saved report.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    config = _load_config(args.config)
    if args.replay:
        from sscre.strategy_c_diagnosis import run_replay_diagnosis, write_diagnosis_record

        record = run_replay_diagnosis(
            config_path=args.config,
            benchmark_path=args.benchmark,
            config=config,
        )
    else:
        from sscre.strategy_c_diagnosis import (
            diagnose_from_evaluation_report,
            write_diagnosis_record,
        )

        report_path = args.from_report or DEFAULT_SOURCE_REPORT
        if not report_path.is_file():
            print(f"missing evaluation report: {report_path}", file=sys.stderr)
            return 1
        from sscre.benchmark import load_benchmark_jsonl
        from sscre.evaluation_protocol import apply_primary_headline_population_filter

        benchmark_records = load_benchmark_jsonl(args.benchmark)
        benchmark_records, _ = apply_primary_headline_population_filter(
            benchmark_records,
            config,
        )
        record = diagnose_from_evaluation_report(
            report_path,
            config_path=args.config,
            benchmark_path=args.benchmark,
            config=config,
            population_record_count=len(benchmark_records),
        )

    write_diagnosis_record(record, args.output)
    print(f"Wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
