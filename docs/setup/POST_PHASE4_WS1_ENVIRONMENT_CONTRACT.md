# Workstream 1 — environment contract (Step 1.1)

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Evidence:** [`POST_PHASE4_WS1_EVIDENCE.md`](./POST_PHASE4_WS1_EVIDENCE.md)  
**Modes:** [`LOCAL_ENVIRONMENT_MODES.md`](./LOCAL_ENVIRONMENT_MODES.md)  
**Machine-readable:** [`../../artifacts/stabilization/ws1-environment-contract.json`](../../artifacts/stabilization/ws1-environment-contract.json)

This document is the source-of-truth matrix for local configuration. Step 1.1
records the contract only; it does not change `docker-compose.yml`,
`.env.example`, or application defaults.

## Owners

| Source | Role |
| --- | --- |
| [`src/sscre/config.py`](../../src/sscre/config.py) | `Settings.from_environment()` parsing and validation |
| [`docker-compose.yml`](../../docker-compose.yml) | Compose interpolation and `api` / `migrate` / `postgres` env |
| [`.env.example`](../../.env.example) | Documented local placeholders (tracked) |
| [`.env`](../../.env) | Developer secrets (gitignored, not tracked) |
| [`src/sscre/provider_config.py`](../../src/sscre/provider_config.py) | Gate C real-provider boundary |
| [`src/sscre/migrate.py`](../../src/sscre/migrate.py) | `SSCRE_MIGRATIONS_DIR` for CLI migrations |

## Secrets and `.env` hygiene

- [x] `.env` is listed in [`.gitignore`](../../.gitignore) (`git check-ignore .env` → ignored).
- [x] `.env` is not tracked (`git ls-files --error-unmatch .env` → not in index).
- [x] `.env.example` is tracked and uses placeholders only (`change-this-local-password`,
      `replace-with-a-long-local-admin-token`); no provider credential keys.

## `Settings` variables (application)

Classification uses WS1 vocabulary: `required`, `optional with default`,
`development-only`, `PostgreSQL-only`, `production-only`, `provider-specific`.

| Variable | Classification | In `.env.example` | In Compose `api` | Config default if unset | Notes |
| --- | --- | --- | --- | --- | --- |
| `SSCRE_DATABASE_URL` | PostgreSQL-only | yes | yes | none | Required when `runtime_profile=production`. |
| `SSCRE_RUNTIME_PROFILE` | optional with default | yes | yes | `development` | |
| `SSCRE_LOG_LEVEL` | optional with default | yes | yes | `INFO` | |
| `SSCRE_ADMIN_TOKEN` | production-only | yes | yes (required for compose) | none | Min length 16 in production profile. |
| `SSCRE_ADMIN_READ_TOKEN` | optional with default | yes | **no** | none | MIS-002 |
| `SSCRE_ADMIN_TOKEN_EXPIRES_AT` | production-only | yes (empty) | **no** | none | Required in production profile; MIS-002, MIS-004 |
| `SSCRE_ADMIN_READ_TOKEN_EXPIRES_AT` | optional with default | yes (empty) | **no** | none | MIS-002 |
| `SSCRE_API_EXPOSURE_MODE` | optional with default | yes (`trusted_local`) | yes (default `trusted_local`) | `trusted_local` | Set `external` to require client tokens on `/v1/query`. |
| `SSCRE_CLIENT_AUTH_JSON` | optional with default | yes (sample registry path) | yes (container `/app/client_auth_registry.json`) | none | Required when mode is `external`. Compose mounts the sample file. |
| `SSCRE_RATE_LIMIT_REQUESTS_PER_MINUTE` | optional with default | yes (`120`) | yes | `0` | Enforced only in `external` mode; process-local. |
| `SSCRE_TENANT_PROVIDER_BUDGET_PER_MINUTE` | optional with default | yes (`60`) | yes | `0` | Enforced only in `external` mode; process-local. |
| `SSCRE_TENANT_MAX_CONCURRENT_QUERIES` | optional with default | yes (`8`) | yes | `32` | Enforced only in `external` mode; process-local. |
| `SSCRE_MAX_REQUEST_BODY_BYTES` | optional with default | yes | yes | `65536` | Request body cap. |
| `SSCRE_SEMANTIC_ENABLED` | optional with default | yes | yes | `true` | |
| `SSCRE_SEMANTIC_STRATEGY` | optional with default | yes (`C`) | yes (default `C`) | `C` | MIS-001 resolved WS1.5 |
| `SSCRE_SEMANTIC_TOP_K` | optional with default | yes | yes | `5` | |
| `SSCRE_SEMANTIC_SIMILARITY_THRESHOLD` | optional with default | yes | yes | `0.95` | |
| `SSCRE_CACHE_STABLE_TTL_SECONDS` | optional with default | yes | yes | 30d | |
| `SSCRE_CACHE_SEMI_DYNAMIC_TTL_SECONDS` | optional with default | yes | yes | 1d | |
| `SSCRE_CACHE_DYNAMIC_TTL_SECONDS` | optional with default | yes | yes | empty | |
| `SSCRE_CACHE_ALLOW_DYNAMIC_ENTRIES` | optional with default | yes | yes | `false` | |
| `SSCRE_CACHE_MAX_ANSWER_BYTES` | optional with default | yes | yes | 65536 | |
| `SSCRE_CACHE_MAX_METADATA_BYTES` | optional with default | yes | yes | 8192 | |
| `SSCRE_CACHE_MAX_QUERY_BYTES` | optional with default | yes | yes | 32768 | |
| `SSCRE_CACHE_MAX_ENTRIES` | optional with default | yes | yes | 10000 | |
| `SSCRE_CACHE_MAX_BYTES` | optional with default | yes | yes | 100000000 | |
| `SSCRE_TIMEOUT_REQUEST_SECONDS` | optional with default | yes | yes | 30 | |
| `SSCRE_TIMEOUT_EMBEDDING_SECONDS` | optional with default | yes | yes | 5 | |
| `SSCRE_TIMEOUT_GENERATION_SECONDS` | optional with default | yes | yes | 25 | |
| `SSCRE_TIMEOUT_REPOSITORY_SECONDS` | optional with default | yes | yes | 2 | |
| `SSCRE_TIMEOUT_HEALTH_SECONDS` | optional with default | yes | yes | 1 | |
| `SSCRE_TIMEOUT_ADMIN_SECONDS` | optional with default | yes | yes | 5 | |

All cache, timeout, and WS2 exposure/abuse `Settings` keys are forwarded to
the Compose `api` service. The three admin token expiry / read-token keys are
not (see MIS-002). Compose always injects `SSCRE_CLIENT_AUTH_JSON` as
`/app/client_auth_registry.json` (sample registry volume); do not pass a host
path into the container.

## Compose and Postgres (not `Settings`)

| Variable | Classification | In `.env.example` | Notes |
| --- | --- | --- | --- |
| `POSTGRES_DB` | PostgreSQL-only | yes | Postgres image only. |
| `POSTGRES_USER` | PostgreSQL-only | yes | |
| `POSTGRES_PASSWORD` | PostgreSQL-only | yes | Required for `docker compose` (`:?` interpolation). |
| `SSCRE_POSTGRES_PORT` | development-only | yes | Host port map. |
| `SSCRE_API_PORT` | development-only | yes | API host port map. |
| `SSCRE_MIGRATIONS_DIR` | PostgreSQL-only | **no** | Set in compose to `/app/migrations`; MIS-003 |

## Provider-specific (Gate C; not in `.env.example`)

When `SSCRE_REAL_PROVIDER=true`, [`provider_config.py`](../../src/sscre/provider_config.py)
requires the `SSCRE_PROVIDER_*` family, optional `SSCRE_PROVIDER_ALLOWED_HOSTS`,
and optional `SSCRE_PROVIDER_CREDENTIAL` (secret). Additional toggles:
`SSCRE_REAL_PROVIDER_LIVE`, `SSCRE_PROVIDER_PRICING_JSON` (used by
[`app.py`](../../src/sscre/app.py) and [`provider_measure.py`](../../src/sscre/provider_measure.py)).
Intentionally omitted from `.env.example` (MIS-005).

## Opt-in harness

| Variable | Classification | Notes |
| --- | --- | --- |
| `SSCRE_WS8_LIVE_POSTGRES_RESTART` | PostgreSQL-only | WS8 live restart harness; not Gate A. |

## Unresolved mismatches (do not normalize in Step 1.1)

| ID | Summary | Planned resolution |
| --- | --- | --- |
| MIS-001 | ~~Strategy C vs B defaults~~ **resolved** 2026-10-13 (Compose + `.env.example` → C) | — |
| MIS-002 | Admin read token / expiry env vars not in Compose `api` | WS1 Step 1.5 or document |
| MIS-003 | `SSCRE_MIGRATIONS_DIR` missing from `.env.example` | WS1 Step 1.2 docs |
| MIS-004 | Production expiry requirements vs compose `development` profile | WS1 Step 1.2 modes |
| MIS-005 | Provider vars absent from `.env.example` | WS1 Step 1.5 boundary |
| MIS-006 | CI compose job uses minimal env sample | WS1 Step 1.7 / WS7 |

## Coverage summary (Step 1.1)

- Every `Settings.from_environment()` key appears in `.env.example` except
  `SSCRE_MIGRATIONS_DIR` (migrate/compose concern).
- `.env.example` matches the Compose-forwarded surface for semantic, cache,
  timeout, database, and primary admin token settings.
- Provider and WS8 harness variables are documented but excluded from
  `.env.example` by design.
