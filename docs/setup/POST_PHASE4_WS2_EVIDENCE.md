# Post–Phase 4 stabilization — Workstream 2 evidence

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Status:** `verification gate passed (in-memory)` — Gate B PostgreSQL **deferred**  
**Machine-readable:** [`../../artifacts/stabilization/ws2-boundary-verification.json`](../../artifacts/stabilization/ws2-boundary-verification.json)

## Step 2.1 — Threat model and deployment contract

**Date:** 2026-10-14  
**HEAD (Step 2.1 close):** `c7c376eb87dae507ed73a086b8908683561836e0`  
**Branch:** `main`

### Deliverables

- [x] Threat model and API/auth boundary:
      [`POST_PHASE4_WS2_API_AUTH_BOUNDARY.md`](./POST_PHASE4_WS2_API_AUTH_BOUNDARY.md)
- [x] Machine-readable inventory:
      [`../../artifacts/stabilization/ws2-api-auth-boundary.json`](../../artifacts/stabilization/ws2-api-auth-boundary.json)

## Step 2.2 — Authenticated request context

**Date:** 2026-10-14

- [x] Client auth implementation and tests (`tests/test_api_client_auth.py`)

## Step 2.3 — Scoped cache identity

**Date:** 2026-10-14

- [x] `CacheScope`, versioned keys, migration 012, `tests/test_cache_scope.py`

## Step 2.4 — Storage isolation and migration evidence

**Date:** 2026-10-14

- [x] [`POST_PHASE4_WS2_STORAGE_ISOLATION.md`](./POST_PHASE4_WS2_STORAGE_ISOLATION.md)
- [x] Migration 013, `tests/test_postgres_cache_scope.py`
- [x] [`ws2-storage-isolation.json`](../../artifacts/stabilization/ws2-storage-isolation.json)

## Step 2.5 — Scoped lookup, semantic search, and canonical access

**Date:** 2026-10-14

- [x] `tests/test_cache_scope_enforcement.py`

## Step 2.6 — Route authorization and operational exposure

**Date:** 2026-10-14

- [x] `tests/test_api_route_authorization.py`

## Step 2.7 — Abuse controls

**Date:** 2026-10-14

- [x] `tests/test_api_abuse_controls.py`

## Step 2.8 — Verify the boundary in both storage modes

**Date:** 2026-10-14

### Inventory (pre-run)

- [x] Referenced test paths, migrations `012`/`013`, and CLI entries
      `sscre-migrate` / `sscre-env-validate` in `pyproject.toml` — recorded in
      [`ws2-boundary-verification.json`](../../artifacts/stabilization/ws2-boundary-verification.json)

### Focused verification (in-memory)

- [x] `python -m pytest tests/test_ws2_boundary_gate.py tests/test_api_client_auth.py tests/test_api_route_authorization.py tests/test_api_abuse_controls.py tests/test_admin.py tests/test_health.py tests/test_cache_scope.py tests/test_cache_scope_enforcement.py tests/test_postgres_cache_scope.py -q`
      — **45 passed**, **5 skipped** (PostgreSQL scope tests skipped without `SSCRE_DATABASE_URL`)

### Full suite

- [x] `python -m pytest -q` — **856 passed**, 20 skipped, 21 deselected (2026-10-14)

### Gate B PostgreSQL

- [ ] Scoped isolation on live PostgreSQL — **deferred** (`SSCRE_DATABASE_URL` not set in verification environment). Not scored as pass or fail.

When Gate B is run locally:

```powershell
sscre-migrate --database-url $env:SSCRE_DATABASE_URL
python -m pytest tests/test_postgres_cache_scope.py tests/test_postgres_eviction_scope.py -q
```

Record `pg_version`, `pgvector` version, migration checksums, and role notes in this file and refresh `ws2-boundary-verification.json`.

### Redaction audit (Step 2.8)

- [x] HTTP `detail` strings are fixed vocabulary (no SQL, tokens, answers, or cross-tenant oracles).
- [x] Semantic-failure logs use `request_id`, `tenant_id`, `principal_id`, `error_type` only.
- [x] Stabilization JSON artifacts contain no live credentials.

### Workstream 2 verdict

| Gate | Result |
| --- | --- |
| Authoring (Steps 2.1–2.7) | **Closed** with linked code and docs |
| Verification (in-memory) | **Pass** at recorded counts above |
| Verification (PostgreSQL Gate B) | **Deferred** — unavailable in CI for this run |
| External / multi-user deployment | **Not authorized** until Gate B is recorded or explicitly accepted by operator |

**Next:** Workstream 3 — timeout, concurrency, and failure-closed runtime stability.
