"""Shared Workstream 2 test settings that satisfy external-mode validation."""

from sscre.config import Settings


def external_test_settings(**overrides: object) -> Settings:
    """Build Settings for external API tests.

    External mode requires positive rate-limit and provider-budget values.
    Use overrides for abuse-control tests (low limits, small body cap, etc.).
    When semantic retrieval stays enabled, keep ``tenant_provider_budget_per_minute``
    high enough for both embedding and generation on a cache miss (at least 2).
    """
    base: dict[str, object] = {
        "api_exposure_mode": "external",
        "client_auth_json": "registry-placeholder.json",
        "rate_limit_requests_per_minute": 1000,
        "tenant_provider_budget_per_minute": 1000,
    }
    base.update(overrides)
    return Settings(**base)
