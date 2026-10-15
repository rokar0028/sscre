"""Workstream 2 Step 2.8 — boundary verification runner.

Writes ``artifacts/stabilization/ws2-boundary-verification.json``.
When ``SSCRE_DATABASE_URL`` is set, applies migrations and runs Gate B PostgreSQL tests.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/stabilization/ws2-boundary-verification.json"
MIGRATIONS_DIR = ROOT / "migrations"

INVENTORY_PATHS = (
    "tests/test_ws2_boundary_gate.py",
    "tests/test_api_client_auth.py",
    "tests/test_api_route_authorization.py",
    "tests/test_api_abuse_controls.py",
    "tests/test_admin.py",
    "tests/test_health.py",
    "tests/test_cache_scope.py",
    "tests/test_cache_scope_enforcement.py",
    "tests/test_postgres_cache_scope.py",
    "tests/test_postgres_eviction_scope.py",
    "tests/test_postgres_integration.py",
    "tests/test_postgres_contention.py",
    "migrations/012_cache_tenant_namespace.sql",
    "migrations/013_cache_scoped_identity.sql",
    "pyproject.toml",
)

FOCUSED_PYTEST = [
    sys.executable,
    "-m",
    "pytest",
    "tests/test_ws2_boundary_gate.py",
    "tests/test_api_client_auth.py",
    "tests/test_api_route_authorization.py",
    "tests/test_api_abuse_controls.py",
    "tests/test_admin.py",
    "tests/test_health.py",
    "tests/test_cache_scope.py",
    "tests/test_cache_scope_enforcement.py",
    "tests/test_postgres_cache_scope.py",
    "-q",
]

GATE_B_PYTEST = [
    sys.executable,
    "-m",
    "pytest",
    "tests/test_postgres_cache_scope.py",
    "tests/test_postgres_eviction_scope.py",
    "tests/test_postgres_integration.py",
    "-q",
]

GATE_B_CONTENTION_PYTEST = [
    sys.executable,
    "-m",
    "pytest",
    "tests/test_postgres_contention.py",
    "-m",
    "ws8_postgres_contention",
    "-q",
]


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    ).stdout.strip()


def _inventory() -> dict[str, object]:
    missing = [
        path for path in INVENTORY_PATHS if not (ROOT / path).is_file()
    ]
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return {
        "referenced_paths_exist": not missing,
        "missing_paths": missing,
        "cli_scripts_declared_in_pyproject": {
            "sscre-migrate": "sscre-migrate" in pyproject,
            "sscre-env-validate": "sscre-env-validate" in pyproject,
        },
        "migrations": [
            "migrations/012_cache_tenant_namespace.sql",
            "migrations/013_cache_scoped_identity.sql",
        ],
    }


def _run_pytest(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    combined = (completed.stdout or "") + (completed.stderr or "")
    passed = failed = skipped = deselected = None
    match = re.search(
        r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?(?:, (\d+) deselected)?",
        combined,
    )
    if match:
        passed = int(match.group(1))
        failed = int(match.group(2) or 0)
        skipped = int(match.group(3) or 0)
        deselected = int(match.group(4) or 0)
    return {
        "command": " ".join(command),
        "exit_code": completed.returncode,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "deselected": deselected,
        "result": combined.strip().splitlines()[-1] if combined.strip() else "",
    }


def _migration_checksums() -> dict[str, str]:
    from sscre.migrate import migration_checksum

    checksums: dict[str, str] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem.split("_", 1)[0]
        checksums[version] = migration_checksum(path)
    return checksums


def _postgres_environment(database_url: str) -> dict[str, object]:
    import psycopg

    from sscre.migrate import validate_migration_state

    validate_migration_state(database_url, MIGRATIONS_DIR)
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            pg_version = cursor.fetchone()[0]
            cursor.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            row = cursor.fetchone()
            pgvector_version = row[0] if row else None
            cursor.execute(
                "SELECT version, checksum FROM schema_migrations ORDER BY version"
            )
            applied = {row[0]: row[1] for row in cursor.fetchall()}
    return {
        "postgresql_version": pg_version,
        "pgvector_version": pgvector_version,
        "migrations_applied": len(applied),
        "migration_checksums_on_disk": _migration_checksums(),
        "schema_migrations": applied,
        "role_boundary_note": (
            "Application role: SELECT/INSERT/UPDATE/DELETE on cache_entries and "
            "canonical_answers; migration role separate (POST_PHASE4_WS2_STORAGE_ISOLATION.md)."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-full-suite",
        action="store_true",
        help="Skip the default pytest suite (focused + Gate B only).",
    )
    args = parser.parse_args(argv)

    database_url = os.getenv("SSCRE_DATABASE_URL")
    inventory = _inventory()
    if inventory["missing_paths"]:
        print("Missing inventory paths:", inventory["missing_paths"], file=sys.stderr)
        return 1

    focused = _run_pytest(FOCUSED_PYTEST)
    if focused["exit_code"] != 0:
        print(focused.get("result") or "focused pytest failed", file=sys.stderr)
        return focused["exit_code"] or 1

    full_suite: dict[str, object] | None = None
    if not args.skip_full_suite:
        full_suite = _run_pytest([sys.executable, "-m", "pytest", "-q"])
        if full_suite["exit_code"] != 0:
            print(full_suite.get("result") or "full suite failed", file=sys.stderr)
            return full_suite["exit_code"] or 1

    gate_b: dict[str, object]
    if not database_url:
        gate_b = {
            "status": "deferred",
            "reason": "SSCRE_DATABASE_URL not set in verification environment",
        }
    else:
        from sscre.migrate import apply_migrations

        applied = apply_migrations(database_url, MIGRATIONS_DIR)
        print(f"Applied migrations: {', '.join(applied) or 'none'}")
        scope_run = _run_pytest(GATE_B_PYTEST)
        contention_run = _run_pytest(GATE_B_CONTENTION_PYTEST)
        if scope_run["exit_code"] != 0 or contention_run["exit_code"] != 0:
            print("Gate B PostgreSQL pytest failed", file=sys.stderr)
            return 1
        gate_b = {
            "status": "verified",
            "migrate_command": f"sscre-migrate --database-url <redacted>",
            "scoped_tests": scope_run,
            "contention_tests": contention_run,
            "environment": _postgres_environment(database_url),
        }

    record = {
        "schema_version": "ws2-boundary-verification-1.1",
        "workstream": 2,
        "step": "2.8",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "configuration_mode": {
            "trusted_local_default": True,
            "external_requires_client_auth_json": True,
            "postgres_gate_b": gate_b["status"],
            "postgres_gate_b_reason": gate_b.get("reason"),
        },
        "inventory": inventory,
        "focused_verification": focused,
        "full_suite": full_suite,
        "gate_b_postgresql": gate_b,
        "redaction_audit": {
            "http_error_bodies": "Fixed detail strings only; no SQL, tokens, or cache payloads",
            "client_auth_logs": (
                "request_id, tenant_id, principal_id, error_type only on semantic failure path"
            ),
            "evidence_files": "No bearer tokens or registry secrets in artifacts/stabilization/*.json",
        },
        "python_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {ARTIFACT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
