"""Validate SSCRE environment configuration without printing secrets."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from sscre.config import Settings

SCHEMA_VERSION = "sscre-env-validate-1.0"
COMPOSE_DEFAULT_SEMANTIC_STRATEGY = "C"
APPLICATION_DEFAULT_SEMANTIC_STRATEGY = "C"

MODES = frozenset({"unit-test", "development-compose", "production"})

DEPENDENCY_TIMEOUT_FIELDS = (
    ("embedding_timeout_seconds", "SSCRE_TIMEOUT_EMBEDDING_SECONDS"),
    ("generation_timeout_seconds", "SSCRE_TIMEOUT_GENERATION_SECONDS"),
    ("repository_timeout_seconds", "SSCRE_TIMEOUT_REPOSITORY_SECONDS"),
    ("health_timeout_seconds", "SSCRE_TIMEOUT_HEALTH_SECONDS"),
    ("admin_timeout_seconds", "SSCRE_TIMEOUT_ADMIN_SECONDS"),
)


def _non_empty_env(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _redacted_settings_summary(settings: Settings) -> dict[str, Any]:
    return {
        "runtime_profile": settings.runtime_profile,
        "log_level": settings.log_level,
        "semantic_enabled": settings.semantic_enabled,
        "semantic_strategy": settings.semantic_strategy,
        "semantic_top_k": settings.semantic_top_k,
        "semantic_similarity_threshold": settings.semantic_similarity_threshold,
        "database_url_configured": settings.database_url is not None,
        "admin_token_configured": settings.admin_token is not None,
        "admin_read_token_configured": settings.admin_read_token is not None,
        "admin_token_expires_at_configured": settings.admin_token_expires_at
        is not None,
        "request_timeout_seconds": settings.request_timeout_seconds,
        "embedding_timeout_seconds": settings.embedding_timeout_seconds,
        "generation_timeout_seconds": settings.generation_timeout_seconds,
        "repository_timeout_seconds": settings.repository_timeout_seconds,
    }


def validate_timeout_relationship(settings: Settings) -> list[str]:
    errors: list[str] = []
    for field_name, env_name in DEPENDENCY_TIMEOUT_FIELDS:
        value = getattr(settings, field_name)
        if value > settings.request_timeout_seconds:
            errors.append(
                f"{env_name} ({value}s) exceeds "
                f"SSCRE_TIMEOUT_REQUEST_SECONDS ({settings.request_timeout_seconds}s)"
            )
    return errors


def validate_mode_requirements(mode: str) -> list[str]:
    errors: list[str] = []
    if mode == "unit-test":
        return errors
    if mode == "development-compose":
        for name in ("POSTGRES_PASSWORD", "SSCRE_ADMIN_TOKEN"):
            if not _non_empty_env(name):
                errors.append(f"{name} is required for development-compose validation")
        return errors
    if mode == "production":
        if os.getenv("SSCRE_RUNTIME_PROFILE", "").strip().lower() != "production":
            errors.append("SSCRE_RUNTIME_PROFILE must be production for this mode")
        for name in (
            "SSCRE_DATABASE_URL",
            "SSCRE_ADMIN_TOKEN",
            "SSCRE_ADMIN_TOKEN_EXPIRES_AT",
        ):
            if not _non_empty_env(name):
                errors.append(f"{name} is required for production validation")
    return errors


def unit_test_mode_warnings() -> list[str]:
    """Warn when a prior shell session left Compose/production vars set."""
    markers = (
        "POSTGRES_PASSWORD",
        "SSCRE_ADMIN_TOKEN",
        "SSCRE_DATABASE_URL",
    )
    present = [name for name in markers if _non_empty_env(name)]
    if not present:
        return []
    joined = ", ".join(present)
    return [
        "unit-test mode does not require these variables; process environment "
        f"still sets {joined}, which can make the Settings summary look configured "
        "— clear them for a minimal Gate A profile check"
    ]


def compose_strategy_warnings() -> list[str]:
    warnings: list[str] = []
    strategy = os.getenv(
        "SSCRE_SEMANTIC_STRATEGY", APPLICATION_DEFAULT_SEMANTIC_STRATEGY
    ).strip().upper()
    if strategy == "B":
        warnings.append(
            "SSCRE_SEMANTIC_STRATEGY=B selects embedding-only Strategy B; "
            "Strategy C is the compatibility-aware safety path for development Compose"
        )
    return warnings


def validate_environment(mode: str) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "status": "pass",
        "errors": [],
        "warnings": [],
        "settings": {},
    }

    report["errors"].extend(validate_mode_requirements(mode))

    try:
        settings = Settings.from_environment()
    except ValueError as exc:
        report["errors"].append(str(exc))
        report["status"] = "fail"
        return report

    report["settings"] = _redacted_settings_summary(settings)
    report["errors"].extend(validate_timeout_relationship(settings))

    if mode == "production" and settings.runtime_profile != "production":
        report["errors"].append(
            "Settings.runtime_profile is not production after parsing environment"
        )

    report["warnings"].extend(compose_strategy_warnings())
    if mode == "unit-test":
        report["warnings"].extend(unit_test_mode_warnings())

    if report["errors"]:
        report["status"] = "fail"
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate SSCRE environment variables for a supported operating mode. "
            "Does not read or print .env file contents."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=sorted(MODES),
        default="unit-test",
        help="Validation profile (default: unit-test).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON report (default: human summary).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = validate_environment(args.mode)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"mode={report['mode']}")
        print(f"status={report['status']}")
        for warning in report["warnings"]:
            print(f"warning={warning}")
        for error in report["errors"]:
            print(f"error={error}")
        if report["settings"]:
            print(
                "settings="
                + json.dumps(report["settings"], sort_keys=True)
            )

    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
