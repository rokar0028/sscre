"""CLI to record a non-secret local embedding smoke artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

from sscre.local_embedding import (
    DEFAULT_LOCAL_MODEL_ID,
    write_local_embedding_smoke_artifact,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record Phase 4 local embedding smoke metadata (no query text)."
    )
    parser.add_argument(
        "--output",
        default="artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json",
        help="Smoke artifact JSON path.",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_LOCAL_MODEL_ID,
        help="Registered sentence-transformers model id.",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--config-path",
        default="experiments/semantic-validity-evaluation-config-v1.json",
    )
    args = parser.parse_args(argv)
    payload = write_local_embedding_smoke_artifact(
        Path(args.output),
        model_id=args.model_id,
        device=args.device,
        config_path=args.config_path,
    )
    print(f"status={payload['status']} model_id={payload.get('model_id', args.model_id)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
