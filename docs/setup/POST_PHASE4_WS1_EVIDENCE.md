# Post–Phase 4 stabilization — Workstream 1 evidence

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Status:** `closed (Gate A — Step 1.7)`

## Step 1.1 — Environment contract inventory

**Date:** 2026-10-13  
**HEAD:** `cbe5e0d1df7534ed28a2df025c55b351fabec239` (`main`)

### Deliverables

- [x] Environment contract matrix:
      [`POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md`](./POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md)
- [x] Machine-readable contract:
      [`../../artifacts/stabilization/ws1-environment-contract.json`](../../artifacts/stabilization/ws1-environment-contract.json)

### Git / secrets checks

| Check | Result |
| --- | --- |
| `git check-ignore -v .env` | ignored via `.gitignore:8:.env` |
| `git ls-files --error-unmatch .env` | not tracked (expected error) |
| `git ls-files .env.example` | tracked |
| `.env.example` content review | placeholders only; no provider credential keys |

### Contract reconciliation notes

- Classified **52** named environment variables across config, Compose,
  provider, migrate, and harness code paths.
- **6** unresolved mismatches recorded as MIS-001–MIS-006; no defaults or
  Compose files were edited in Step 1.1.
- Compose `api` service forwards all `Settings` cache/timeout/semantic keys;
  gaps: `SSCRE_ADMIN_READ_TOKEN`, `SSCRE_ADMIN_TOKEN_EXPIRES_AT`,
  `SSCRE_ADMIN_READ_TOKEN_EXPIRES_AT`.

### Verification (Step 1.1)

- [x] Matrix built from `docker-compose.yml`, `config.py`, `.env.example`,
      `pyproject.toml` (Python range only), and setup docs.
- [x] Variables classified per WS1 vocabulary.
- [x] Compose forwarding gaps identified.
- [x] Compose-only / doc gaps identified (ports, `SSCRE_MIGRATIONS_DIR`).
- [x] `.env.example` and `.env` hygiene confirmed.
- [x] Mismatches recorded before any default edits.

## Step 1.2 — Four operating modes

**Date:** 2026-10-13

### Deliverable

- [x] Setup entry point with decision tree and mode-specific commands:
      [`LOCAL_ENVIRONMENT_MODES.md`](./LOCAL_ENVIRONMENT_MODES.md)

### Verification (Step 1.2)

- [x] Documented unit-test mode (in-memory, fake providers, default `pytest -q`).
- [x] Documented development Compose mode (`.env`, pgvector/pg16, Strategy C
      safety expectation and MIS-001 override note).
- [x] Documented PostgreSQL verification mode (migrations, markers, Gate B
      recording requirements).
- [x] Documented production/provider mode (production profile, provider
      boundary, Gate C fail-closed).
- [x] Command → mode map and evidence prohibitions for fake/synthetic/unavailable.
- [x] Linked [`POSTGRESQL_LOCAL_SETUP.md`](./POSTGRESQL_LOCAL_SETUP.md) without
      duplicating database lifecycle steps.
- [x] Updated [`docs/README.md`](../README.md) setup table.

## Step 1.3 — Dependency and import setup

**Date:** 2026-10-13

### Deliverables

- [x] Gate A setup sequence:
      [`GATE_A_LOCAL_SETUP.md`](./GATE_A_LOCAL_SETUP.md)
- [x] Import smoke script:
      [`../../scripts/gate_a_import_smoke.py`](../../scripts/gate_a_import_smoke.py)

### Verification run

| Step | Result |
| --- | --- |
| `python -m pip install ".[dev]"` | completed (repo checkout install) |
| `python scripts/gate_a_import_smoke.py` | exit `0` |
| Log | [`../../artifacts/stabilization/gate-a-import-smoke.log`](../../artifacts/stabilization/gate-a-import-smoke.log) |

Smoke summary (2026-10-13T08:24:54Z): Python 3.14.5; 7 core modules `ok`; 8/8
console scripts registered; `Settings.from_environment()` without
`SSCRE_DATABASE_URL`; `local_embeddings.available` varied by host (optional
extra not required for Gate A; Step 1.7 records `unavailable` until
`.[local-embeddings]` is installed).

### Verification (Step 1.3)

- [x] Documented Python `>=3.11` and PowerShell `.venv` sequence.
- [x] Documented `pip install ".[dev]"` and optional `".[local-embeddings]"`.
- [x] Added import smoke command (no Postgres/provider).
- [x] Setup uses current checkout install, not ignored egg-info artifacts.
- [x] Recorded install and smoke results in evidence.

## Step 1.4 — Environment validation

**Date:** 2026-10-13

### Deliverables

- [x] CLI: [`../../src/sscre/env_validate.py`](../../src/sscre/env_validate.py)
      (`python -m sscre.env_validate`, console script `sscre-env-validate`)
- [x] Tests: [`../../tests/test_env_validate.py`](../../tests/test_env_validate.py)

### Verification run

| Check | Result |
| --- | --- |
| `pytest -q tests/test_env_validate.py` | 10 passed |
| `env_validate --mode development-compose` (CI sample + `SSCRE_SEMANTIC_STRATEGY=C`) | exit `0` |
| Log | [`../../artifacts/stabilization/env-validate-development-compose.log`](../../artifacts/stabilization/env-validate-development-compose.log) |

Timeout rule: each dependency timeout must be `<= SSCRE_TIMEOUT_REQUEST_SECONDS`.
MIS-001 reported as **warning** when strategy is B, not a hard fail.

### Verification (Step 1.4)

- [x] Reuses `Settings.from_environment()` for parsing/validation.
- [x] Modes: `unit-test`, `development-compose`, `production`.
- [x] Redacted output; no `.env` file read.
- [x] Unit tests cover samples, production requirements, invalid values, timeouts, MIS-001.

## Step 1.5 — Compose default and provider boundary

**Date:** 2026-10-13

### Decision

- Development Compose and `.env.example` default **Strategy C** (aligned with
  `Settings.from_environment()` and production-readiness contract).
- Strategy **B** remains available via explicit `SSCRE_SEMANTIC_STRATEGY=B`
  (validator warning only).

### Changes

- [`../../docker-compose.yml`](../../docker-compose.yml): `${SSCRE_SEMANTIC_STRATEGY:-C}`
- [`.env.example`](../../.env.example): `SSCRE_SEMANTIC_STRATEGY=C`
- [`PROVIDER_BOUNDARY.md`](./PROVIDER_BOUNDARY.md) — Gate C OpenAI-compatible rules; no WS1 SDK/live run
- **MIS-001** resolved in contract JSON and environment contract doc

### Verification

| Check | Result |
| --- | --- |
| `docker compose config -q` (CI sample env) | exit `0` |
| `pytest -q tests/test_env_validate.py` | 11 passed (includes compose/example default test) |
| Live provider | not run (documented unavailable path only) |

## Step 1.6 — Local embedding provenance

**Date:** 2026-10-13

### Deliverables

- [x] Provenance note:
      [`LOCAL_EMBEDDING_PROVENANCE.md`](./LOCAL_EMBEDDING_PROVENANCE.md)
- [x] Redacted record helper:
      [`../../src/sscre/local_embedding.py`](../../src/sscre/local_embedding.py)
      (`build_ws1_local_embedding_provenance_record`)
- [x] Recorder script:
      [`../../scripts/ws1_local_embedding_provenance.py`](../../scripts/ws1_local_embedding_provenance.py)

### Verification run

| Step | Result |
| --- | --- |
| `pytest -q tests/test_local_embedding.py -m "not local_embedding"` | **12 passed**, 1 skipped (no optional extra) |
| `$env:PYTHONPATH='src'; python scripts/ws1_local_embedding_provenance.py` | exit `0`; JSON written |
| `--smoke-load` on same host without `.[local-embeddings]` | `status=unavailable` (no download attempted) |
| JSON | [`../../artifacts/stabilization/local-embedding-provenance.json`](../../artifacts/stabilization/local-embedding-provenance.json) |

Validated identity: `sentence-transformers/all-MiniLM-L6-v2`, 384-dim, Apache-2.0,
CPU default. Fake `fake-embedding` (dim 8) scoped to tests and historical
artifacts only. Default recorder is probe/cache-only; replayability is
`not_claimed` when the optional extra is absent. Phase 4 smoke pass remains on
[`../../artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json`](../../artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json).

### Verification (Step 1.6)

- [x] Documented model id, dimension, license, device, and package extra.
- [x] `weights.state` distinguishes cached, not cached, downloaded during smoke, unavailable.
- [x] Replayability explicit when weights absent and smoke not run.
- [x] Machine-readable output contains no query text, tokens, or credentials.
- [x] No new model pin beyond the Phase 4 registered id.

## Step 1.7 — Gate A package verification

**Date:** 2026-10-13  
**HEAD:** `cbe5e0d1df7534ed28a2df025c55b351fabec239` (`main`)

### Deliverable

- [x] Machine-readable package record:
      [`../../artifacts/stabilization/gate-a-package-verification.json`](../../artifacts/stabilization/gate-a-package-verification.json)

### Verification paths (pre-flight)

| Path | Present |
| --- | --- |
| `scripts/gate_a_import_smoke.py` | yes |
| `src/sscre/env_validate.py` | yes |
| `tests/test_env_validate.py` | yes |
| `scripts/ws1_local_embedding_provenance.py` | yes |
| `docker-compose.yml` | yes |
| `pyproject.toml` (`ws8_postgres_*` deselected in `addopts`) | yes |

### Verification run

| Command | Result |
| --- | --- |
| `python -m pip install ".[dev]"` | exit `0` — [`gate-a-pip-install.log`](../../artifacts/stabilization/gate-a-pip-install.log) |
| `python scripts/gate_a_import_smoke.py` | exit `0` — [`gate-a-import-smoke.log`](../../artifacts/stabilization/gate-a-import-smoke.log) |
| `python -m sscre.env_validate --mode unit-test --json` | `status: pass` |
| `python -m sscre.env_validate --mode development-compose --json` | `status: pass` (CI sample env + `SSCRE_SEMANTIC_STRATEGY=C`) |
| `python -m pytest -q` | **819 passed**, 17 skipped, 21 deselected — [`gate-a-pytest.log`](../../artifacts/stabilization/gate-a-pytest.log) |
| `docker compose config -q` | exit `0` — [`docker-compose-config.log`](../../artifacts/stabilization/docker-compose-config.log) |

Dependency versions: [`gate-a-pip-list.json`](../../artifacts/stabilization/gate-a-pip-list.json).

### Conditional checks

| Check | Status | Notes |
| --- | --- | --- |
| Live provider (Gate C) | **deferred** | No WS1 authorization or credentials |
| `ws8_postgres_*` / `test_postgres_integration.py` | **deferred** | Gate B; not claimed from Gate A |
| PostgreSQL readiness | **recorded** | `major-postgres-1` healthy; PG **16.15**; pgvector **0.8.7**; **12/12** migrations in `schema_migrations` |
| Optional local embeddings | **unavailable** | `sentence-transformers` not installed; see Step 1.6 provenance JSON |

Readiness logs: `postgres-readiness-version.log`, `postgres-readiness-pgvector.log`,
`postgres-readiness-migrations.log` under `artifacts/stabilization/`.

### Redaction / secrets hygiene

| Check | Result |
| --- | --- |
| `git check-ignore -v .env` | ignored |
| `git ls-files .env` | not tracked |
| Validator JSON logs | `admin_token_configured` only; no raw token values |

### Verification (Step 1.7)

- [x] All declared Gate A commands run with logs under `artifacts/stabilization/`.
- [x] Unavailable/deferred checks documented (provider, Gate B pytest).
- [x] WS1 evidence stored under `docs/setup/` (not `docs/phase-4/`).
- [x] Plan Status, acceptance criteria, and baseline updated in the same pass.

## WS1 close-out

Gate A is **complete** for reproducible local setup without credentials. Gate B
(PostgreSQL integration markers) and Gate C (live provider) remain explicit
next gates — not authorized from this evidence package.
