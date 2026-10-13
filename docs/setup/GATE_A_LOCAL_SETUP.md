# Gate A — local dependency and import setup

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md) Workstream 1 Step 1.3  
**Modes:** [`LOCAL_ENVIRONMENT_MODES.md`](./LOCAL_ENVIRONMENT_MODES.md)  
**Evidence:** [`POST_PHASE4_WS1_EVIDENCE.md`](./POST_PHASE4_WS1_EVIDENCE.md)  
**Verification record:** [`../../artifacts/stabilization/gate-a-package-verification.json`](../../artifacts/stabilization/gate-a-package-verification.json)

Gate A needs no `.env`, PostgreSQL, or provider credentials. Use a virtual
environment inside this repository checkout so installs do not depend on a
global Python, ignored `build/`, or `src/sscre.egg-info/` from an old install.

## Supported Python

From [`pyproject.toml`](../../pyproject.toml): **`requires-python >= 3.11`**.

CI uses Python 3.12 ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)).
Local development on 3.11–3.14 is expected to work when dependencies resolve.

## One-time setup (Windows PowerShell)

Run from the repository root (`git rev-parse --show-toplevel`):

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install ".[dev]"
```

This installs the `sscre` package from the **current checkout** (editable-style
via setuptools) plus `pytest` and `httpx`. It does not install
`sentence-transformers` unless you add the optional extra below.

## Optional — local embeddings (not required for unit tests)

```powershell
python -m pip install ".[local-embeddings]"
```

Use only for opt-in `local_embedding` tests or real local embedding workflows.
Gate A `pytest -q` does not require this extra.

## Import smoke (no network)

After `".[dev]"` install, verify imports and console script registration:

```powershell
python scripts/gate_a_import_smoke.py
```

The script:

- imports core `sscre.*` modules (including `app` and `evaluate`);
- checks all declared `[project.scripts]` console entry points are registered;
- calls `Settings.from_environment()` without requiring `SSCRE_DATABASE_URL`;
- reports whether `sentence_transformers` is installed (optional).

Exit code `0` means success. It does not start Uvicorn, connect to PostgreSQL,
or call a provider.

## Default verification command

```powershell
python -m pytest -q
```

`pyproject.toml` sets `pythonpath = ["src"]` for pytest; after `pip install
".[dev]"`, tests use the installed package consistent with CI.

## Without activating `.venv`

If you prefer not to activate the venv, call the venv interpreter explicitly:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[dev]"
.\.venv\Scripts\python.exe scripts/gate_a_import_smoke.py
.\.venv\Scripts\python.exe -m pytest -q
```

## Environment validation (Step 1.4)

Validate the **current process environment** (not the contents of a `.env` file):

```powershell
# Gate A unit-test profile (no Postgres/admin required)
# Clear leftover Compose vars first if you ran development-compose checks above:
# Remove-Item Env:POSTGRES_PASSWORD,Env:SSCRE_ADMIN_TOKEN -ErrorAction SilentlyContinue
python -m sscre.env_validate --mode unit-test

# CI / Compose sample (same non-secret values as `.github/workflows/ci.yml`)
$env:POSTGRES_PASSWORD = 'ci-local-password'
$env:SSCRE_ADMIN_TOKEN = 'ci-local-admin-token-123456'
$env:SSCRE_SEMANTIC_STRATEGY = 'C'
python -m sscre.env_validate --mode development-compose --json
```

Exit code `0` means pass. Output is redacted (tokens are never printed; only
`*_configured` booleans). Explicit Strategy **B** emits an embedding-only
warning; Compose and `.env.example` default to **C** (Step 1.5).

Provider rules: [`PROVIDER_BOUNDARY.md`](./PROVIDER_BOUNDARY.md).

## Local embedding provenance (Step 1.6)

Identity, weight cache state, and fake-embedding scope:
[`LOCAL_EMBEDDING_PROVENANCE.md`](./LOCAL_EMBEDDING_PROVENANCE.md).

```powershell
python scripts/ws1_local_embedding_provenance.py
# optional: python scripts/ws1_local_embedding_provenance.py --smoke-load
```

Production profile checks (require explicit env):

```powershell
$env:SSCRE_RUNTIME_PROFILE = 'production'
# plus SSCRE_DATABASE_URL, SSCRE_ADMIN_TOKEN, SSCRE_ADMIN_TOKEN_EXPIRES_AT
python -m sscre.env_validate --mode production
```

## What this step does not do

- Does not create or read `.env` (see [`LOCAL_ENVIRONMENT_MODES.md`](./LOCAL_ENVIRONMENT_MODES.md)).
- Does not start Docker or PostgreSQL (see [`POSTGRESQL_LOCAL_SETUP.md`](./POSTGRESQL_LOCAL_SETUP.md)).
