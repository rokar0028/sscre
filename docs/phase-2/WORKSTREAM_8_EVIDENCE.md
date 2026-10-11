# Workstream 8 — operational verification evidence

**Status:** Steps 1–9 complete (2026-10-11). Parent-plan handoff recorded in
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md). Live
container restart remains skipped. Implementation-gate promotion and a
feature branch were not retroactively invented.  
**Parent:** [WORKSTREAM_8_IMPLEMENTATION_PLAN.md](./WORKSTREAM_8_IMPLEMENTATION_PLAN.md)  
**OPS-lite baseline:** [WORKSTREAM_8_OPS_LITE_EVIDENCE.md](./WORKSTREAM_8_OPS_LITE_EVIDENCE.md)  
**Step 1 audit:** [WORKSTREAM_8_STEP1_AUDIT.md](./WORKSTREAM_8_STEP1_AUDIT.md)

This record is a bounded local PostgreSQL operational package. It is **not** a
production capacity, SLA, multi-host, multi-region, or managed-PostgreSQL
guarantee.

## Implementation commit and branch

- [x] HEAD `4997e6670bc6a2609cb9351bdf3bae882d61c01c` on `phase4/setup`.
- [x] Working tree dirty when packaged (WS8 implementation and this evidence
  are uncommitted). This document describes the worktree, not that commit
  alone.
- [x] Load measurement commit in the artifact matches HEAD above.

## Protocol and workload definitions

Frozen in the Step 1 audit. Recorded here:

| Protocol | Workload | Processes / workers | Concurrency |
| --- | --- | ---: | ---: |
| `ws8-failure-recovery-v1` | FR-lookup, FR-gen-persist, FR-insert, FR-cleanup, FR-recovery | 1 / 1 | 1 |
| `ws8-multiprocess-dup-v1` | same-query miss, 3 runs | 2 / 2 | 2 |
| `ws8-contention-v1` | CT-dup-key, CT-mixed-rw, CT-cleanup-race, CT-evict-cap | 1 / 1 | 4–8 threads |
| `ws8-pg-load-v1` | 8 warmup / 32 requests, 2 cold + 2 warm | 1 / 1 | 4 |

- [x] Protocol IDs, process counts, worker counts, and concurrency are in
  `artifacts/operations/workstream8-operational-verification.json`.

## PostgreSQL version and environment

From `ws8-pg-load-v1` (`measured_at` 2026-10-10T16:31:04Z):

- [x] OS Windows-11-10.0.26200-SP0, AMD64, 8 CPUs, Python 3.14.5
- [x] PostgreSQL `16.15 (Debian 16.15-1.pgdg12+2)`, `database_mode=postgres`
- [x] Cache caps `max_entries=8`, `max_bytes=10000`
- [x] Provider data: synthetic `LoadTestLLMClient` (0 ms)

## Restart / failure scenarios and recovery

Event classes are **not** interchangeable.

| Scenario | Event class | Outcome |
| --- | --- | --- |
| FR-lookup-drop | `simulated_drop` | HTTP 503, no cache hit, request ID present |
| FR-lookup-simulated-failure | `simulated_repository_failure` | HTTP 503, labeled separately from a drop |
| FR-gen-persist | `simulated_drop` on insert-after-generate | HTTP 200 generated, row not persisted |
| FR-insert | `simulated_repository_failure` | HTTP 200 generated, row not persisted |
| FR-cleanup | `simulated_drop` | cleanup raises; expired row remains |
| FR-recovery | `simulated_drop` once, then restore | 503 then 200 cache; expired / metadata-less / incompatible candidates not served; generation failure does not persist; query validation 422 and admin Bearer 401 still enforced |
| Live container restart | `container_restart` | **Skipped** (`SSCRE_WS8_LIVE_POSTGRES_RESTART` unset) |

- [x] Simulated lookup, generation, insert, and cleanup paths fail closed or
  return generated output without persisting an incomplete entry.
- [x] Recovery does not bypass expiry, missing metadata, incompatibility,
  query validation, or admin authorization.
- [x] Live process/container restart during write is **unsupported** in this
  package.

## Duplicate generation vs duplicate insert

Protocol `ws8-multiprocess-dup-v1` (live 2026-10-10, local migrated
PostgreSQL): `pytest -m ws8_postgres_multiprocess` → **1 passed** (3.95s).

- [x] `provider_generations` min=max=2 across 3 runs
- [x] `insert_success` min=max=1; `insert_conflict` min=max=1; `insert_error=0`
- [x] One `cache_entries` row; TTL fresh; metadata present; both HTTP 200
- [x] Duplicate **insert** is prevented. Duplicate **generation** is not.

Limitation: the in-process `generation_lock` in `src/sscre/app.py` does not
coordinate workers or hosts. No distributed lock was added.

## Eviction and transactions under contention

Protocol `ws8-contention-v1` (live 2026-10-10):
`pytest -m ws8_postgres_contention` → **6 passed** (4.75s).

- [x] CT-dup-key (8 threads): 1 insert success, 7 duplicate conflicts, 1 row
- [x] CT-mixed-rw (8 threads): 4 lookup hits, 4 inserts, no database/validation
  errors
- [x] CT-cleanup-race (4 threads): fresh rows retained; stale rows removed
- [x] CT-evict-cap (8 threads): caps of 8 entries / 10000 bytes apply only to
  the run's query hashes. `storage_stats.entries == count(*)` and the owned
  rows that remain equal inserts minus evictions. Rows outside the run stay.
- [x] Expired, metadata-less, and incompatible candidates cannot win a
  concurrent lookup
- [x] `duplicate_conflict`, `database_error`, and `validation_error` recorded
  separately

Limitation: eviction and cleanup delete only the run's query hashes. The
2026-10-10 measurement used a relative cap window before that guard. Not a
production eviction-capacity claim.

## Latency, throughput, errors, timeouts, and storage

Protocol `ws8-pg-load-v1` (2026-10-10). Artifact
`artifacts/operations/workstream8-pg-load-v1.json`. Two independent cold/warm
pairs. `stopped_reason=null`. Error rate 3/32 (9.375%) is the declared
generation-failure mix. Timeouts 0.

| Pass | p50 ms | p95 ms | p99 ms | rps | hits | generated | errors | entries_delta | evictions_delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cold | 63.362 | 199.509 | 262.840 | 40.334 | 17 | 12 | 3 | 6 | 0 |
| warm | 57.953 | 72.355 | 73.557 | 64.284 | 23 | 6 | 3 | 0 | 0 |
| cold | 69.220 | 235.787 | 306.064 | 37.968 | 17 | 12 | 3 | 6 | 0 |
| warm | 56.916 | 81.719 | 84.315 | 69.020 | 23 | 6 | 3 | 0 | 0 |

Isolated keys stayed at 6 entries (cap 8). `bytes_delta` 1782 on each cold
pass. That run's artifact still records the absolute-cap warning. Later load
runs apply the cap only to the run's query hashes.

- [x] p50/p95/p99, throughput, errors, timeouts, storage growth, and evictions
  recorded.
- [x] Result is not a production capacity guarantee.

## First bottleneck

- [x] Verdict: `not_reached` (`result_class=observation`,
  `optimization_decision=none`).
- [x] End-to-end average 75.257 ms; wrapper/API 66.009 ms; synthetic LLM 0.0 ms.
- [x] Unavailable: `repository_database_span`, `embedding_span`,
  `real_provider_latency`.
- [x] Artifact: `artifacts/operations/workstream8-bottleneck-v1.json`.

No runtime, query, or cache-policy change.

## Skipped or unavailable

- [x] Live container restart (`SSCRE_WS8_LIVE_POSTGRES_RESTART` unset).
- [x] Default-suite PostgreSQL integration when the database URL environment
  is unset (15 skipped on 2026-10-11).
- [x] Opt-in WS8 markers deselected by default `addopts`.
- [x] Repository, embedding, and live-provider spans not instrumented.
- [x] `docker compose config` was not validated at Step 1 audit (requires
  `.env` secrets).
- [x] 1K–100K Q/day, multi-host, cloud failover, and real-provider cost are
  out of scope.

## Limitations and unsupported claims

Next to the results above, this package does **not** support:

- universal production capacity or SLA
- 1K–100K queries/day
- multi-host or distributed-cache coordination
- live process or container restart during write
- duplicate-generation prevention across processes
- real-provider cost or latency
- Kubernetes, cloud failover, multi-region, or managed PostgreSQL

## Artifact paths

| Output | Path |
| --- | --- |
| Consolidated package | `artifacts/operations/workstream8-operational-verification.json` |
| Load result | `artifacts/operations/workstream8-pg-load-v1.json` |
| Bottleneck sidecar | `artifacts/operations/workstream8-bottleneck-v1.json` |
| Load config | `experiments/workstream8_pg_load_v1.json` |

Packager: `python -m sscre.ops_evidence`. Kind
`workstream8-operational-verification`, schema `ws8-ops-1.0`. Per-request
rows are omitted. Forbidden serialization keys and database-url fragments are
rejected before write.

## Regeneration commands

From the repository root. Opt-in PostgreSQL commands require a migrated
database URL in the environment; do not commit that value.

```powershell
python -m pytest -q -m ws8_postgres_failure_recovery tests/test_postgres_failure_recovery.py tests/test_postgres_failure_closed.py
python -m pytest -q -m ws8_postgres_multiprocess tests/test_postgres_multiprocess_duplicate.py
python -m pytest -q -m ws8_postgres_contention tests/test_postgres_contention.py
python -m pytest -q -m ws8_postgres_load tests/test_postgres_pg_load.py
python -m sscre.load_test --config experiments/workstream8_pg_load_v1.json --output artifacts/operations/workstream8-pg-load-v1.json
python -m sscre.ops_evidence --output artifacts/operations/workstream8-operational-verification.json
python -m pytest -q
```

Re-running load overwrites the load artifact. Re-packaging refreshes load
summaries from that file. Failure-recovery, multiprocess, and contention
counts in `sscre.ops_evidence.recorded_protocol_results` change only when
those live results change.

## Focused and full-suite results

- [x] Focused packager tests (2026-10-11):

```powershell
python -m pytest -q tests/test_ops_evidence.py tests/test_load_test.py
```

**13 passed** (1.23s).

- [x] Default suite (2026-10-11, database URL unset; opt-in WS8 markers
  deselected):

```powershell
python -m pytest -q
```

**704 passed, 15 skipped, 21 deselected** (133.81s) after the eviction-scope
guard. The earlier close on this date was 700 passed before
`tests/test_postgres_eviction_scope.py`.
`benchmark_validate --phase2 --production` was not re-run with this guard.

- [x] Live PostgreSQL (2026-10-10, local migrated database): multiprocess **1
  passed**; contention **6 passed**; pg-load **1 passed**. Failure-recovery
  and failure-closed live counts were not re-run on 2026-10-11 because the
  database URL environment was unset.

## Parent-plan handoff (Step 9)

- [x] [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md)
  Workstream 8 links this file and states the measured vs skipped scope.
- [x] Limitations
  ([`../reference/SSCRE_EVALUATION_LIMITATIONS.md`](../reference/SSCRE_EVALUATION_LIMITATIONS.md))
  keep Phase 1 lite and the 2026-10-11 package as separate sections.
- [x] Phase 3 / Phase 4 notes no longer treat OPS-lite, bounded WS8, and
  in-memory Phase 4 scale as one claim.
- [x] `tests/test_ops_evidence.py::test_handoff_docs_do_not_conflate_ws8_scopes`
  guards that split.

## Code touch points

- `src/sscre/ops_evidence.py` — packager and recorded protocol results
- `src/sscre/postgres_failure_harness.py` — failure injection and optional
  live restart
- `src/sscre/load_test.py` — PostgreSQL load path and bottleneck classifier
- `src/sscre/app.py` — in-process `generation_lock` (not multi-process)
- `tests/test_postgres_failure_recovery.py`
- `tests/test_postgres_failure_closed.py`
- `tests/test_postgres_multiprocess_duplicate.py`
- `tests/test_postgres_contention.py`
- `tests/test_postgres_pg_load.py`
- `tests/test_ops_evidence.py`
