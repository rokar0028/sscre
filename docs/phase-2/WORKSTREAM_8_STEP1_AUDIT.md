# Workstream 8 — Step 1 audit and protocol baseline

**Completed:** 2026-10-10  
**Scope:** inventory repository behavior, PostgreSQL integration tests, Docker/PostgreSQL
configuration, load-test support, Phase 4 in-memory measurements, and OPS-lite evidence;
define frozen restart, concurrency, eviction, and load protocols before code or live
experiments.  
**Parent plan:** [WORKSTREAM_8_IMPLEMENTATION_PLAN.md](./WORKSTREAM_8_IMPLEMENTATION_PLAN.md)

This audit records the operational baseline and protocol definitions only. It does not
run container restarts, multi-process races, PostgreSQL load verification, or package
final evidence (Step 8).

## Measurement environment snapshot

Recorded at audit time from the repository working tree.

| Field | Value |
|---|---|
| Git commit | `4997e6670bc6a2609cb9351bdf3bae882d61c01c` |
| Branch | `phase4/setup` (tracks `origin/phase4/setup`) |
| Working tree | Modified `docs/phase-2/README.md`; untracked `WORKSTREAM_8_IMPLEMENTATION_PLAN.md` and this audit |
| Python | 3.14.5 |
| Package | `sscre` 0.1.0 (editable/install from repo) |
| fastapi | 0.142.2 |
| psycopg | 3.3.6 |
| pytest | 9.1.1 |
| uvicorn | 0.54.0 |
| Declared PostgreSQL image | `pgvector/pgvector:pg16` (`docker-compose.yml`) |
| `SSCRE_DATABASE_URL` during audit | **unset** — PostgreSQL integration tests not executed against live DB |
| Full unit suite (2026-10-10) | `python -m pytest -q` → **685 passed, 15 skipped**, ~170s |
| Postgres integration collect-only | `python -m pytest -q tests/test_postgres_integration.py --collect-only` → **14 tests** collected |
| `docker compose config` | **Not validated** — requires `.env` with `POSTGRES_PASSWORD` and `SSCRE_ADMIN_TOKEN` |

Re-run baseline capture before held-out or destructive runs if commit, branch, or
dependency versions change.

## OPS-lite evidence (what exists)

Source: [WORKSTREAM_8_OPS_LITE_EVIDENCE.md](./WORKSTREAM_8_OPS_LITE_EVIDENCE.md).

| Claim | Evidence |
|---|---|
| Single-process generation coordination | In-process `threading.Lock` in `src/sscre/app.py` (`generation_lock`) |
| Multi-process / cross-host coordination | **Explicitly unsupported** in lite docs |
| PostgreSQL lookup connection loss → failure-closed | `test_postgres_connection_loss_on_lookup_fails_closed` |
| In-memory lookup failure → 503 + request ID | `tests/test_exact_cache.py::test_cache_repository_failure_returns_503_with_request_id` |

### What OPS-lite does **not** prove

- Live PostgreSQL **process or container restart** during generation, insert, or cleanup.
- Recovery behavior after a real restart (only simulated connection loss on lookup).
- Same-query concurrent requests across **multiple application processes** or Uvicorn workers.
- Whether duplicate **generation** was prevented vs duplicate **insert** rejected (`UNIQUE`).
- Eviction, entry caps, or cleanup under **concurrent** PostgreSQL writers.
- Bounded **PostgreSQL-backed** load: latency percentiles, throughput, storage growth, or evictions.
- Production capacity, SLA, multi-region, or managed-PostgreSQL claims.

## Code and test inventory

### PostgreSQL repository and API

| Component | Location | Role for WS8 |
|---|---|---|
| Exact + vector PostgreSQL cache | `src/sscre/postgres_cache.py` | Persistence, uniqueness, eviction, cleanup |
| Request path + in-process lock | `src/sscre/app.py` | Generation guard, failure-closed responses |
| Migrations | `migrations/` + `sscre-migrate` | Schema for integration experiments |
| Docker stack | `docker-compose.yml` | `postgres` (pg16 + pgvector), `migrate`, `api` |

### `tests/test_postgres_integration.py` (requires `SSCRE_DATABASE_URL`)

| Test | WS8 relevance |
|---|---|
| `test_insert_and_exact_lookup` | Baseline read/write |
| `test_embedding_round_trip` | Vector metadata persistence |
| `test_top_k_embedding_search_returns_ranked_candidates` | Semantic retrieval on PostgreSQL |
| `test_duplicate_hash_is_rejected` | Uniqueness / duplicate insert |
| `test_generation_failure_does_not_persist_an_entry` | Generation path without partial persist |
| `test_postgres_search_returns_expired_candidates` | Expired rows not served via search path |
| `test_cleanup_expired_removes_entry_and_updates_counter` | Cleanup behavior (single-threaded) |
| `test_postgres_connection_loss_on_lookup_fails_closed` | **OPS-lite** simulated drop on lookup |
| `test_insert_and_evict_enforces_postgres_entry_cap` | Entry cap + eviction (sequential) |

Fixtures: `cache_entry`, `repository` (insert + teardown delete by `query_hash`).

**Audit result:** module is wired for skip-when-unset and collects 14 tests; live run
**skipped** in this environment pending `SSCRE_DATABASE_URL`.

### In-process concurrency (not PostgreSQL)

`tests/test_workstream3_concurrency.py` — seven tests, **InMemoryExactCache** only:

- Concurrent same-query coordination (Strategy C).
- Duplicate-write races (compatible, incompatible, expired).
- Expired entries never served under concurrency.

These support request-path invariants but are **not** PostgreSQL operational evidence.

### Load and storage tooling

| Tool | Storage backend | Notes |
|---|---|---|
| `sscre-load-test` / `python -m sscre.load_test` | **In-memory** (`InMemoryExactCache` or `DisabledCache`) | p50/p95/p99, errors, synthetic provider; `storage` block is in-memory stats |
| `python -m sscre.storage_evaluation` | Config-driven (Phase 4 profile) | Not PostgreSQL capacity evidence |
| `experiments/milestone10_load_v1.json` | Used by Phase 4 | 8 warmup, 32 requests, concurrency 4, small caps |

Phase 4 reference: `docs/phase-4/PHASE4_SCALE_EVIDENCE.md`, artifact
`artifacts/evaluation/phase4-scale-profile.json` — **must not** be cited as WS8
PostgreSQL load evidence.

## Frozen protocol definitions (pre-run)

Protocol IDs are stable labels for Step 8 evidence. Parameters may be tightened in
Steps 2–6; changing IDs requires a new audit note.

### Protocol `ws8-failure-recovery-v1` (Step 2–3)

**Purpose:** Failure-closed behavior and recovery when PostgreSQL is unavailable or
restored.

| Scenario ID | Event type | Injection point | Success criteria (high level) |
|---|---|---|---|
| `FR-lookup-drop` | Simulated connection loss | Repository lookup | No cache hit; HTTP 503; request ID present (**OPS-lite baseline**) |
| `FR-lookup-simulated-failure` | Simulated repository failure (not live restart) | During `/v1/query` lookup | Same HTTP behavior as drop; `event_class` labeled separately in evidence |
| `FR-gen-persist` | Drop or restart | After generation, before/during insert | No incomplete or unsafe entry served or readable |
| `FR-insert` | Drop or restart | During `insert` / `insert_and_evict` | Failure-closed response; no partial unsafe serve |
| `FR-cleanup` | Drop or restart | During `cleanup_expired` | Failure-closed or explicit cleanup failure; no stale serve |
| `FR-recovery` | Restore connectivity | After any of above | Subsequent healthy request passes validation; expired/unsafe still blocked |

**Environment:** isolated database (dedicated compose project or disposable DB URL); opt-in
pytest marker or CLI — not default `pytest -q`.

**Instrumentation:** record `event_class` ∈
`{simulated_drop, process_restart, container_restart, simulated_repository_failure}`.

### Protocol `ws8-multiprocess-dup-v1` (Step 4)

**Purpose:** Measure duplicate **generation** vs duplicate **insert** for one query identity.

| Parameter | Initial value |
|---|---|
| Application processes | 2 (expand to 4 only if 2-run variance is documented) |
| PostgreSQL | Single shared database |
| Query | One fixed normalized miss per run (UUID suffix per run) |
| Provider | `CountingMockLLMClient` or instrumented mock in each process |
| Barrier | All processes ready before simultaneous `/v1/query` POST |
| Repeats | 3 runs minimum; record min/max generation and insert counts |

**Reports:** `provider_generations`, `insert_success`, `insert_conflict`, `insert_error`,
final row count for query hash, HTTP outcomes (no partial/unsafe serve).

### Protocol `ws8-contention-v1` (Step 5)

**Purpose:** Uniqueness, transactions, eviction, and cleanup under bounded concurrent
PostgreSQL access.

| Workload | Concurrency | Focus |
|---|---|---|
| `CT-dup-key` | 8 threads | Same `query_hash` insert → deterministic duplicate handling |
| `CT-mixed-rw` | 8 threads | Interleaved lookup + insert on distinct keys |
| `CT-evict-cap` | 8 threads | `insert_and_evict` with `max_entries` / `max_bytes` at or below Phase 4 scale |
| `CT-cleanup-race` | 4 threads | Cleanup vs insert on overlapping/expired keys |

**Reports:** eviction counters, `storage_stats`, DB errors vs validation errors, no
corruption of stored answers.

### Protocol `ws8-pg-load-v1` (Step 6)

**Purpose:** Bounded PostgreSQL-backed load with declared limits (not production capacity).

| Parameter | Initial value | Notes |
|---|---|---|
| Workload file | Adapt from `experiments/milestone10_load_v1.json` | New filename e.g. `experiments/workstream8_pg_load_v1.json` |
| Warmup / requests | 8 / 32 (match Phase 4 profile) | Increase only with explicit plan amendment |
| Concurrency | 4 | Thread pool against one API + PostgreSQL |
| Cache caps | `max_cache_entries=8`, `max_cache_bytes=10000` (configurable) | Record actual settings in artifact |
| Modes | At minimum `exact_cache` with PostgreSQL repository | Optional comparison to in-memory only if labeled separate |
| Repeats | 2 cold + 2 warm passes | Stop early if error rate > 10% or p99 > 5× p50 |

**Required artifact fields:** hardware/OS, Python, PostgreSQL version, process count,
worker count, p50/p95/p99, throughput, errors, timeouts, storage growth, evictions,
`protocol_id`, `git_commit`, timestamps.

**Gap:** `load_test.py` currently hardcodes in-memory repository — Step 6 adds minimum
PostgreSQL adapter or alternate runner.

## Stop conditions (destructive / unstable / non-diagnostic)

Stop the run and record `stopped_reason` when any of the following occur:

1. **Data safety:** test targets a non-isolated database URL or shared developer data
   without explicit opt-in.
2. **Unbounded failure:** same scenario fails **3 consecutive** attempts with different
   infrastructure cause (flaky network, disk full).
3. **Non-diagnostic load:** error rate > **10%** or timeout rate > **5%** before
   completing warmup — fix harness before scaling request count.
4. **Restart loop:** PostgreSQL fails to reach `healthy` within **5 minutes** after
   restart — do not retry more than **2** restart cycles per session.
5. **Resource exhaustion:** host memory or disk triggers OOM / full volume during load —
   stop and reduce concurrency or workload.
6. **Sensitive leakage:** artifact or log contains credentials, full prompts, or
   unrestricted answers — discard output and fix redaction before re-run.
7. **Ambiguous event:** cannot classify failure as drop vs restart vs simulated repository
   — do not merge results across classes.

## Gaps for Steps 2+

- [x] Opt-in PostgreSQL failure/recovery harness (Step 2).
  `src/sscre/postgres_failure_harness.py`,
  `tests/test_postgres_failure_recovery.py`.
- [x] Live integration run with `SSCRE_DATABASE_URL` recorded in evidence.
  Multiprocess, contention, and pg-load passed against local migrated
  PostgreSQL (2026-10-10). Live container restart still skipped.
- [x] Multi-process runner and provider generation counters (Step 4).
  `tests/test_postgres_multiprocess_duplicate.py`; marker
  `ws8_postgres_multiprocess`.
- [x] PostgreSQL concurrent contention tests (Step 5).
  `tests/test_postgres_contention.py`; marker `ws8_postgres_contention`.
  Live 6 passed (2026-10-10).
- [x] PostgreSQL-backed load-test path (Step 6).
  `repository=postgres` in `src/sscre/load_test.py`;
  `experiments/workstream8_pg_load_v1.json`;
  `artifacts/operations/workstream8-pg-load-v1.json`.
- [x] `WORKSTREAM_8_EVIDENCE.md` and `artifacts/operations/workstream8-operational-verification.json` (Step 8).
- [ ] Implementation gate: explicit user approval for promotion beyond OPS-lite before
  production-like or held-out runs (parent plan).

## Handoff

Step 2 should implement `ws8-failure-recovery-v1` with opt-in controls and event
classification, preserving existing OPS-lite lookup smoke as `FR-lookup-drop` baseline.
