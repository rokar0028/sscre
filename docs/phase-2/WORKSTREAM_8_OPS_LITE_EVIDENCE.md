# Workstream 8 — OPS lite evidence (Phase 1 carryover)

**Status:** complete for lite scope (2026-10-09)  
**Parent:** [`PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md`](../internal/PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md) Step 3  
**Full WS8:** deferred per Phase 0 (`P0-CARRYOVER`); see
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md) Workstream 8.

## Scope delivered (lite)

- [x] Documented **single-process** request-path coordination vs **unsupported**
  multi-process / cross-host duplicate-generation guarantees.
- [x] One PostgreSQL **connection-loss-on-lookup** smoke test (failure-closed HTTP
  503; no served cache hit when lookup fails after a persisted entry exists).

## Out of scope (explicit)

- [ ] Multi-process duplicate-generation races verified under PostgreSQL.
- [ ] Load tests (1K→100K), concurrency sweeps, eviction-under-contention.
- [ ] Live `pg_ctl`/container restart during insert/generation (future full WS8).

## Single-process vs multi-process

The API uses an in-process `threading.Lock` around generation
(`src/sscre/app.py`) so concurrent requests in **one** worker do not double-generate
the same miss. That lock does **not** coordinate across Uvicorn workers, hosts, or
processes. PostgreSQL `UNIQUE` constraints reject duplicate inserts, but cross-process
“generate twice then pick a winner” behavior is **not** verified in this iteration.

Paper and public docs must not claim multi-process safe reuse or production capacity
without full WS8 evidence.

## Restart / connection-loss smoke

**Test:** `tests/test_postgres_integration.py::test_postgres_connection_loss_on_lookup_fails_closed`

Simulates PostgreSQL unavailable during lookup (post-restart / connection drop) after
a real insert via `PostgresExactCacheRepository`. Expectation: `/v1/query` returns
**503** `cache unavailable`, not a cache hit.

Verification (requires running PostgreSQL and migrations):

```powershell
$env:SSCRE_DATABASE_URL = "<your-postgres-url>"
python -m pytest -q tests/test_postgres_integration.py::test_postgres_connection_loss_on_lookup_fails_closed
```

When `SSCRE_DATABASE_URL` is unset, the test is **skipped** (same as other Postgres
integration tests). In-memory failure-closed behavior is covered by
`tests/test_exact_cache.py::test_cache_repository_failure_returns_503_with_request_id`.

## Paper limitations (draft sentence)

Operational verification is limited to single-process coordination and a PostgreSQL
lookup failure-closed smoke test; multi-process concurrency, restart-during-write,
and load capacity are not measured in this release.
