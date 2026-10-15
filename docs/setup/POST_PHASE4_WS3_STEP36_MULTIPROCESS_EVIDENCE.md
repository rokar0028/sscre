# Post–Phase 4 stabilization — Workstream 3 Step 3.6 evidence

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Status:** `closed (live verified)`  
**Machine-readable:** [`../../artifacts/stabilization/ws3-step36-multiprocess-duplicate.json`](../../artifacts/stabilization/ws3-step36-multiprocess-duplicate.json)

## Step 3.6 — Cross-process duplicate semantics

**Date:** 2026-10-14  
**HEAD:** `2d7323fa31aa5db576e2d11aa9854832a9d0b9f5`

### Opt-in harness

| Item | Value |
| --- | --- |
| Protocol | `ws8-multiprocess-dup-v1` |
| Test module | [`tests/test_postgres_multiprocess_duplicate.py`](../../tests/test_postgres_multiprocess_duplicate.py) |
| Pytest marker | `ws8_postgres_multiprocess` |
| Prerequisites | `SSCRE_DATABASE_URL`, migrated schema (`sscre-migrate` with repo `migrations/`) |

### Live verification (2026-10-14)

- [x] `docker compose up -d postgres` (pgvector/pgvector:pg16, **PostgreSQL 16.15**).
- [x] `python -m sscre.migrate --database-url $env:SSCRE_DATABASE_URL --migrations-dir migrations` → applied **012**, **013** (repo `src` on `PYTHONPATH`).
- [x] `python -m pytest tests/test_postgres_multiprocess_duplicate.py -m ws8_postgres_multiprocess -q` → **1 passed** (~5.1s).
- [x] Per-run aggregates match harness: **2** provider generations, **1** insert success, **1** insert conflict, **0** insert errors, **1** row per query hash (3 runs).
- [x] In-process WS3 concurrency tests were **not** used as cross-process evidence.

**Environment note (Windows + Docker Desktop):** `localhost` on the published Postgres port can hit `wslrelay` and fail password auth even when in-container `psql` succeeds. This run used a Docker-reachable host/port in `SSCRE_DATABASE_URL` and aligned the `sscre` role password before host-side `psycopg` connected. See [`POSTGRESQL_LOCAL_SETUP.md`](POSTGRESQL_LOCAL_SETUP.md) for compose URL conventions; do not commit `.env`.

### Per-process metrics (harness contract)

Each worker records: `status_code`, `source`, `decision`, `generations`, `insert_success`, `insert_conflict`, `insert_error`, `request_id` (correlation id only; not copied into this evidence file).

### Cross-process boundary

- [x] Uniqueness constraint prevents duplicate **rows**; both processes may still **generate** (no distributed lock).
- [x] In-process `generation_lock` does not coordinate separate processes.

### Rerun command

```powershell
cd <repo-root>
docker compose up -d postgres
$env:SSCRE_DATABASE_URL = (Get-Content .env |
  Where-Object { $_ -like 'SSCRE_DATABASE_URL=*' } |
  ForEach-Object { $_ -replace '^SSCRE_DATABASE_URL=', '' })
$env:PYTHONPATH = (Resolve-Path 'src').Path
$migrations = (Resolve-Path 'migrations').Path
python -m sscre.migrate --database-url $env:SSCRE_DATABASE_URL --migrations-dir $migrations
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m pytest tests/test_postgres_multiprocess_duplicate.py -m ws8_postgres_multiprocess -q
```
