"""Gate A import smoke — no PostgreSQL, provider, or .env required.

Run from repository root after ``python -m pip install ".[dev]"``:

    python scripts/gate_a_import_smoke.py

Uses only the installed package and stdlib; does not read ``.env``.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import sys
from datetime import datetime, timezone

CORE_MODULES = (
    "sscre.config",
    "sscre.app",
    "sscre.baseline",
    "sscre.evaluate",
    "sscre.benchmark_validate",
    "sscre.migrate",
    "sscre.provider_config",
)

EXPECTED_CONSOLE_SCRIPTS = (
    "sscre-evaluate",
    "sscre-storage-evaluate",
    "sscre-migrate",
    "sscre-load-test",
    "sscre-gallery-export",
    "sscre-failure-gallery-export",
    "sscre-dashboard-export",
    "sscre-dual-model",
    "sscre-env-validate",
)


def _console_script_targets() -> dict[str, str]:
    scripts: dict[str, str] = {}
    for entry in importlib.metadata.entry_points(group="console_scripts"):
        if entry.name in EXPECTED_CONSOLE_SCRIPTS:
            scripts[entry.name] = entry.value
    return scripts


def _optional_local_embeddings() -> dict[str, object]:
    try:
        importlib.import_module("sentence_transformers")
    except ImportError:
        return {"available": False, "reason": "sentence-transformers not installed"}
    return {"available": True, "note": "optional [local-embeddings] extra"}


def main() -> int:
    report: dict[str, object] = {
        "schema_version": "gate-a-import-smoke-1.0",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "modules": {},
        "console_scripts": {},
        "local_embeddings": {},
        "settings_smoke": {},
    }

    for name in CORE_MODULES:
        importlib.import_module(name)
        report["modules"][name] = "ok"

    scripts = _console_script_targets()
    missing = [n for n in EXPECTED_CONSOLE_SCRIPTS if n not in scripts]
    if missing:
        print(
            json.dumps(
                {
                    **report,
                    "error": "missing_console_scripts",
                    "missing": missing,
                },
                indent=2,
            )
        )
        return 1

    report["console_scripts"] = scripts

    settings = importlib.import_module("sscre.config").Settings.from_environment()
    report["settings_smoke"] = {
        "runtime_profile": settings.runtime_profile,
        "semantic_strategy": settings.semantic_strategy,
        "database_url_configured": settings.database_url is not None,
    }

    report["local_embeddings"] = _optional_local_embeddings()

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
