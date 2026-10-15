"""Research track R1 Step 1.2 — bounded Gate C provider measurement."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG = ROOT / "experiments/semantic-validity-evaluation-config-v1.json"
DEFAULT_BENCHMARK = ROOT / "benchmarks/development.jsonl"
DEFAULT_OUTPUT = ROOT / "artifacts/stabilization/r1-step12-provider-measurement.json"
DEFAULT_APPROVAL = ROOT / "artifacts/stabilization/r1-step12-gate-c-approval.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--approval",
        type=Path,
        default=None,
        help="Gate C approval JSON (default: env SSCRE_R1_GATE_C_APPROVED or deferred).",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Bounded workload size (default: 5 development records).",
    )
    parser.add_argument(
        "--full-development",
        action="store_true",
        help="Measure all development records (explicit cost; not the default bound).",
    )
    args = parser.parse_args(argv)

    from sscre.evaluate import _load_config
    from sscre.r1_provider_run import (
        DEFAULT_MAX_RECORDS,
        run_r1_step12_measurement,
        write_r1_step12_record,
    )

    max_records = None if args.full_development else (
        args.max_records if args.max_records is not None else DEFAULT_MAX_RECORDS
    )
    approval_path = args.approval
    if approval_path is None and DEFAULT_APPROVAL.is_file():
        approval_path = DEFAULT_APPROVAL

    config = _load_config(args.config)
    record = run_r1_step12_measurement(
        benchmark_path=args.benchmark,
        config_path=args.config,
        config=config,
        max_records=max_records,
        gate_c_approval_path=approval_path,
    )
    write_r1_step12_record(record, args.output)
    status = record["provider_measurement"]["status"]
    print(f"Wrote {args.output.relative_to(ROOT)} (measurement status: {status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
