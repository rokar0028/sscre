# SSCRE local environment modes (Gate A entry point)

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md) Workstream 1  
**Contract:** [`POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md`](./POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md)  
**Evidence:** [`POST_PHASE4_WS1_EVIDENCE.md`](./POST_PHASE4_WS1_EVIDENCE.md)

Use this document to choose an operating mode before running commands.
Database container lifecycle, migration CLI details, and pgvector checks live in
[`POSTGRESQL_LOCAL_SETUP.md`](./POSTGRESQL_LOCAL_SETUP.md) — link there instead
of duplicating those steps here.

## Decision tree

```text
Need external credentials or live provider?
  yes → Production/provider mode (Gate C) — stop if not explicitly authorized
  no  → Need PostgreSQL integration or WS8 harness markers?
          yes → PostgreSQL verification mode (Gate B)
          no  → Need full API + Postgres via Compose?
                  yes → Development Compose mode (Gate A + local DB)
                  no  → Unit-test mode (Gate A default)
```

## Stabilization gates (reminder)

| Gate | Mode(s) | Credentials |
| --- | --- | --- |
| A | Unit-test, development Compose (no live provider) | None required for default pytest |
| B | PostgreSQL verification | Local `.env` / Docker; record version, migrations, skips |
| C | Production/provider | Approved provider, quota, pricing; redacted artifacts |
| D | Semantic headline eval | Fresh held-out population (deferred in baseline) |

## Mode 1 — Unit-test (Gate A)

**Purpose:** Fast feedback on application logic with fake providers and
in-memory storage.

| Aspect | Expectation |
| --- | --- |
| Repository | In-memory (no `SSCRE_DATABASE_URL` unless a test sets it) |
| Providers | Deterministic fake embeddings/generation in tests |
| `.env` | Not required; do not commit secrets for this mode |
| PostgreSQL | Not used by default suite |
| Credentials | None |

**Setup and import smoke:** see [`GATE_A_LOCAL_SETUP.md`](./GATE_A_LOCAL_SETUP.md).

**Default test command** (after `".[dev]"` install):

```powershell
python -m pytest -q
```

**Pytest behavior:** `addopts` deselects `ws8_postgres_failure_recovery`,
`ws8_postgres_multiprocess`, `ws8_postgres_contention`, and `ws8_postgres_load`.
Opt-in markers: `local_embedding`, `real_provider` (see `pyproject.toml`).

**Evidence rule:** Results from this mode are **locally verified** only. They
are not PostgreSQL verified, provider verified, or production evidence.

## Mode 2 — Development Compose (Gate A + local database)

**Purpose:** Run the API against PostgreSQL/pgvector with migrations applied via
Compose services.

| Aspect | Expectation |
| --- | --- |
| Configuration | Copy [`.env.example`](../../.env.example) → `.env`; replace placeholders locally |
| Stack | `docker compose` — `postgres`, `migrate`, `api` ([`docker-compose.yml`](../../docker-compose.yml)) |
| Image | `pgvector/pgvector:pg16` |
| Strategy safety | Default **C** in `docker-compose.yml` and `.env.example`; set **B** only for embedding-only experiments |
| Admin | `SSCRE_ADMIN_TOKEN` required for Compose (`:?` interpolation) |
| Provider | Not required; do not enable `SSCRE_REAL_PROVIDER` without Gate C |

**Minimal sequence** (details: [`POSTGRESQL_LOCAL_SETUP.md`](./POSTGRESQL_LOCAL_SETUP.md)):

```powershell
Copy-Item .env.example .env
# Edit .env: passwords and admin token (strategy defaults to C)
docker compose up -d postgres
# After postgres is healthy: migrate + api per POSTGRESQL_LOCAL_SETUP.md
```

**Compose config check** (CI sample — no real `.env` required):

```powershell
$env:POSTGRES_PASSWORD = 'ci-local-password'
$env:SSCRE_ADMIN_TOKEN = 'ci-local-admin-token-123456'
docker compose config -q
```

**Evidence rule:** Compose bring-up proves **development** configuration only.
It is not external deployment readiness (Workstream 2) or production capacity.

## Mode 3 — PostgreSQL verification (Gate B)

**Purpose:** Exercise the real PostgreSQL/pgvector path, migrations, and opt-in
integration markers.

| Aspect | Expectation |
| --- | --- |
| Database | Migrated instance; `SSCRE_DATABASE_URL` set (from `.env` or shell) |
| Migrations | `sscre-migrate` checksum validation — see PostgreSQL setup doc |
| Health | API `/health` and `/ready` when running the stack; harness-specific checks for WS8 |
| Tests | Explicit marker selection; default `pytest -q` **does not** run these |

**Example commands** (only when Docker/Postgres is available):

```powershell
$env:SSCRE_DATABASE_URL = '<from .env>'
python -m pytest -q tests/test_postgres_integration.py
python -m pytest -q -m ws8_postgres_failure_recovery
python -m pytest -q -m ws8_postgres_multiprocess
python -m pytest -q -m ws8_postgres_contention
python -m pytest -q -m ws8_postgres_load
```

**Recording requirement (Gate B):** When claiming PostgreSQL verification,
record PostgreSQL version, pgvector extension, migration state, workload, and
which markers were skipped with reason. Historical WS8 artifacts at HEAD are
not a substitute for a fresh run unless replay is documented.

**Evidence rule:** Passing opt-in PostgreSQL tests supports **PostgreSQL
verified** claims for the exercised scope only — not universal SLA or
multi-tenant production readiness.

## Mode 4 — Production / provider (Gate C)

**Purpose:** Production runtime profile and/or explicitly authorized real
provider measurement.

| Aspect | Expectation |
| --- | --- |
| Runtime profile | `SSCRE_RUNTIME_PROFILE=production` |
| Database | `SSCRE_DATABASE_URL` required |
| Admin | `SSCRE_ADMIN_TOKEN` (≥16 chars), `SSCRE_ADMIN_TOKEN_EXPIRES_AT` (timezone-aware ISO-8601) |
| Provider | `SSCRE_REAL_PROVIDER=true` plus full `SSCRE_PROVIDER_*` contract in [`provider_config.py`](../../src/sscre/provider_config.py) |
| Live measure | `SSCRE_REAL_PROVIDER_LIVE=true` only with credential and approval |
| Pricing | `SSCRE_PROVIDER_PRICING_JSON` / schedule id as used by measure CLI |

**Fail-closed:** Missing database, admin secret, expiry, or provider fields must
raise validation errors — do not substitute fake-provider numbers for live
measurements ([`PHASE4_PROVIDER_EVIDENCE.md`](../phase-4/PHASE4_PROVIDER_EVIDENCE.md)).

**Evidence rule:** Live cost, latency, and provider behavior require **provider
verified** artifacts. `status: unavailable` outputs are not failures of Gate A;
they document missing authorization. Free-tier providers are not assumed
unlimited or production-suitable.

## Command → mode map

| Command | Mode | Gate | Notes |
| --- | --- | --- | --- |
| `python -m pytest -q` | Unit-test | A | Default; postgres markers deselected |
| `python -m pytest -q -m ws8_postgres_*` | PostgreSQL verification | B | Opt-in |
| `python -m pytest -q -m real_provider` | Production/provider | C | Requires live opt-in env |
| `python -m pytest -q -m local_embedding` | Unit-test / eval tooling | A/C | Optional weights; not Gate C by itself |
| `python -m sscre.benchmark_validate --phase2 --production` | Unit-test / eval | A | Frozen benchmark; no live provider |
| `docker compose up` (postgres/migrate/api) | Development Compose | A | Local DB |
| `docker compose config` | Development Compose | A | Sample env like CI |
| `python -m sscre.provider_measure` with live flags | Production/provider | C | Fail-closed when unavailable |
| `uvicorn sscre.app:app --env-file .env` | Development Compose | A | See PostgreSQL setup doc |

## Evidence prohibitions (all modes)

Do **not** treat the following as provider verified, production ready, or fresh
semantic headline results:

- Fake or deterministic embeddings in tests and most evaluation artifacts
- Synthetic replay load ladders without PostgreSQL
- `provider_measure` / artifacts with `live_opt_in_missing` or `unavailable`
- Phase 3 held-out JSON with fake embeddings for new real-embedding claims
- Deferred held-out semantic gate (Workstream 5)

When a required dependency is missing, record **`unavailable`** or **`deferred`**
with the reason; do not infer pass/fail from skipped conditionals.

## Related documents

- [`POSTGRESQL_LOCAL_SETUP.md`](./POSTGRESQL_LOCAL_SETUP.md) — Postgres start/stop, migrate, pgvector, integration test snippet
- [`PROVIDER_BOUNDARY.md`](./PROVIDER_BOUNDARY.md) — Gate C provider rules (no live run in WS1)
- [`POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md`](./POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md) — variable matrix and MIS-001–MIS-006
- [`../POST_PHASE4_STABILIZATION_EVIDENCE.md`](../POST_PHASE4_STABILIZATION_EVIDENCE.md) — Workstream 0 baseline freeze
