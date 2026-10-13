"""Phase 4 held-out headline gate checks and deferred evidence records."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

HELD_OUT_GATE_READY_STATUS = "fresh-held-out-ready"
DEFERRED_ARTIFACT_SCHEMA = "semantic-validity-held-out-deferred-1.0"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


def _git_worktree_dirty(repo_root: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def resolve_held_out_gate_path(
    config: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
) -> Path:
    reference = config.get("held_out_gate_reference")
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("P4-SEMVALID config must include held_out_gate_reference")
    root = repo_root or _repo_root()
    return root / reference


def load_held_out_gate(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"held-out gate record not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("held-out gate record must be a JSON object")
    return payload


def validate_p4_held_out_headline_run(
    config: Mapping[str, Any],
    *,
    split: str,
    benchmark_path: Path,
    gate: Mapping[str, Any] | None = None,
    gate_path: Path | None = None,
    repo_root: Path | None = None,
) -> None:
    """Fail closed when a P4 headline held-out run is not authorized."""
    if config.get("protocol_id") != "P4-SEMVALID":
        return
    if split != "held-out":
        return
    root = repo_root or _repo_root()
    development_benchmark = (root / "benchmarks" / "development.jsonl").resolve()
    if benchmark_path.resolve() == development_benchmark:
        raise ValueError(
            "P4-SEMVALID held-out evaluation cannot use benchmarks/development.jsonl; "
            "use the authorized fresh held-out benchmark when the gate is ready"
        )
    if gate is not None:
        gate_payload = dict(gate)
    else:
        resolved_gate_path = gate_path or resolve_held_out_gate_path(
            config,
            repo_root=root,
        )
        gate_payload = load_held_out_gate(resolved_gate_path)
    status = gate_payload.get("status")
    contaminated = gate_payload.get("existing_held_out_split")
    if isinstance(contaminated, Mapping):
        contaminated_path = contaminated.get("path")
        if isinstance(contaminated_path, str):
            if benchmark_path.resolve() == (root / contaminated_path).resolve():
                raise ValueError(
                    "P4-SEMVALID headline held-out replay on "
                    f"{contaminated_path!r} is forbidden "
                    f"({contaminated.get('classification', 'contaminated')}); "
                    "use a fresh held-out population when the gate is "
                    f"{HELD_OUT_GATE_READY_STATUS!r}"
                )
    if status != HELD_OUT_GATE_READY_STATUS:
        reason = gate_payload.get("reason", "held-out gate is not ready")
        raise ValueError(
            f"P4-SEMVALID headline held-out evaluation is blocked: "
            f"gate status={status!r} ({reason})"
        )
    fresh_benchmark = gate_payload.get("fresh_held_out_benchmark_path")
    if isinstance(fresh_benchmark, str) and fresh_benchmark.strip():
        expected = (root / fresh_benchmark).resolve()
        if benchmark_path.resolve() != expected:
            raise ValueError(
                "held-out benchmark path does not match the fresh held-out "
                f"gate record ({fresh_benchmark!r})"
            )


def build_held_out_deferred_payload(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    gate: Mapping[str, Any],
    gate_path: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Build a Step 6 deferred evidence record when no fresh held-out exists."""
    root = repo_root or _repo_root()
    commands = config.get("evaluation_commands")
    held_out_command = None
    if isinstance(commands, Mapping):
        value = commands.get("held_out_abc_when_authorized")
        if isinstance(value, str):
            held_out_command = value
    development_artifact = config.get("development_threshold_artifact")
    if not isinstance(development_artifact, str):
        development_artifact = (
            "artifacts/evaluation/phase4-semantic-validity-development.json"
        )
    development_artifact_path = root / development_artifact
    development_artifact_sha256: str | None = None
    development_artifact_config_sha256: str | None = None
    if development_artifact_path.is_file():
        development_artifact_sha256 = _sha256_file(development_artifact_path)
        try:
            dev_payload = json.loads(
                development_artifact_path.read_text(encoding="utf-8")
            )
            if isinstance(dev_payload, dict):
                raw_config_sha = dev_payload.get("config_sha256")
                if isinstance(raw_config_sha, str) and raw_config_sha:
                    development_artifact_config_sha256 = raw_config_sha
        except (OSError, json.JSONDecodeError):
            pass
    try:
        config_path_record = config_path.relative_to(root).as_posix()
    except ValueError:
        config_path_record = str(config_path.as_posix())
    return {
        "artifact_schema_version": DEFERRED_ARTIFACT_SCHEMA,
        "protocol_id": config.get("protocol_id", "P4-SEMVALID"),
        "config_version": config.get("config_version"),
        "config_path": config_path_record,
        "config_sha256": _sha256_file(config_path),
        "measurement_environment": "not_executed",
        "evaluation_split": "held-out",
        "status": "deferred",
        "gate_path": str(gate_path.relative_to(root).as_posix()),
        "gate_sha256": _sha256_file(gate_path),
        "gate_status": gate.get("status"),
        "gate_reason": gate.get("reason"),
        "contaminated_split": gate.get("existing_held_out_split"),
        "development_threshold_artifact": development_artifact,
        "development_threshold_artifact_sha256": development_artifact_sha256,
        "development_threshold_artifact_config_sha256": (
            development_artifact_config_sha256
        ),
        "authorized_held_out_command_when_ready": held_out_command,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(root),
        "git_worktree_dirty": _git_worktree_dirty(root),
        "next_step": gate.get("next_step_to_resolve"),
    }


def write_held_out_deferred_evidence(
    output_path: Path,
    *,
    config_path: Path,
    gate_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("protocol config must be a JSON object")
    resolved_gate_path = gate_path or resolve_held_out_gate_path(
        config,
        repo_root=root,
    )
    gate = load_held_out_gate(resolved_gate_path)
    if gate.get("status") == HELD_OUT_GATE_READY_STATUS:
        raise ValueError(
            "held-out gate is ready; run the authorized held-out evaluate "
            "command instead of writing a deferred record"
        )
    payload = build_held_out_deferred_payload(
        config=config,
        config_path=config_path,
        gate=gate,
        gate_path=resolved_gate_path,
        repo_root=root,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record P4-SEMVALID held-out deferred evidence (Step 6).",
    )
    parser.add_argument(
        "--config",
        default="experiments/semantic-validity-evaluation-config-v1.json",
        help="Frozen semantic-validity protocol config path.",
    )
    parser.add_argument(
        "--output",
        default="artifacts/evaluation/phase4-semantic-validity-held-out-deferred.json",
        help="Deferred evidence JSON output path.",
    )
    parser.add_argument(
        "--gate",
        default=None,
        help="Override held-out gate JSON path (default: config reference).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = _repo_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = root / config_path
    gate_path = Path(args.gate) if args.gate else None
    if gate_path is not None and not gate_path.is_absolute():
        gate_path = root / gate_path
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path
    write_held_out_deferred_evidence(
        output_path,
        config_path=config_path,
        gate_path=gate_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
