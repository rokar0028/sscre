"""Record WS1 local embedding provenance (redacted, no .env read).

Default: probe optional packages and HF hub cache only (no model download).

    python scripts/ws1_local_embedding_provenance.py

Opt-in smoke load (may download weights on first run):

    python scripts/ws1_local_embedding_provenance.py --smoke-load
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sscre.local_embedding import (
    DEFAULT_LOCAL_MODEL_ID,
    build_ws1_local_embedding_provenance_record,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write redacted WS1 local embedding provenance JSON.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/stabilization/local-embedding-provenance.json",
        help="Destination path for the provenance record.",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_LOCAL_MODEL_ID,
        help="Registered sentence-transformers model id.",
    )
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--smoke-load",
        action="store_true",
        help="Load the model and run the Phase 4 smoke embed (may download weights).",
    )
    args = parser.parse_args(argv)

    payload = build_ws1_local_embedding_provenance_record(
        model_id=args.model_id,
        device=args.device,
        run_smoke_load=args.smoke_load,
    )
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"status={payload.get('status')} "
        f"weights={payload.get('weights', {}).get('state')} "
        f"output={destination.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
