# Post–Phase 4 Workstream 4 — PostgreSQL correctness and vector-search readiness

## Goal

Verify the actual PostgreSQL/pgvector storage path at a bounded, declared
scale before making external deployment, vector-search, or capacity claims.
The workstream must distinguish application correctness, migration/privilege
behavior, query-plan observations, and load evidence. A passing local database
run is not a universal production guarantee.

**Status:** `closed (bounded local verification — commit bundle pending)` —
Steps 1–9 recorded in evidence (2026-10-15). The vector probe does not include
a true cold-cache run, and the bounded load stopped under its registered rule.

**Parent:** [`../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)
Workstream 4.

**Evidence:** [`POST_PHASE4_WS4_POSTGRESQL_READINESS_EVIDENCE.md`](./POST_PHASE4_WS4_POSTGRESQL_READINESS_EVIDENCE.md)
(Step 1 historical snapshot; close-out in Step 9).

**Card:** Parent stabilization Workstream 4 acceptance criteria; no separate
post-Phase 4 feature card exists.

## Goal / exit gates

### Gate A — migrated database and privilege boundary

Run against a fresh, versioned `pgvector/pgvector:pg16` database. Record
PostgreSQL and pgvector versions, every migration checksum, database roles,
worker count, hardware/runtime, and the exact workload. Establish whether the
application role can start and serve requests without migration privileges.

### Gate B — correctness and safety

Pass the existing PostgreSQL integration, vector, failure-closed, scoped-cache,
eviction, cleanup, uniqueness, and transaction tests. Add only focused
regressions for an acceptance gap. Verify that tampered canonical rows,
expired/disallowed candidates, and cross-scope candidates cannot produce an
unsafe served result.

### Gate C — bounded vector and storage behavior

Capture `EXPLAIN (ANALYZE, BUFFERS)` for the declared vector query at declared
dimensions, cache sizes, and candidate counts. Decide whether an HNSW or
IVFFlat index is justified. No index migration is authorized without measured
dimension, workload, operator choice, build cost, and query-plan evidence.

### Exit

Workstream 4 may be marked closed only when all required tests pass or have
explicit unavailable evidence, least-privilege startup is classified, vector
plans and storage behavior are recorded, and the evidence states exactly which
deployment claims remain out of scope.

## Learning objectives

- [ ] Explain why migration correctness and application-role startup are
      separate properties.
- [ ] Verify canonical-answer integrity and failure-closed behavior on the real
      PostgreSQL repository.
- [ ] Interpret vector query plans without turning one bounded workload into a
      capacity claim.
- [ ] Decide whether an approximate vector index is justified by measured
      workload evidence.
- [ ] Distinguish in-process, multi-process, and multi-host concurrency results.

## Prerequisites and audit corpus

### Feature minimum inputs

- [x] Inspect [`../../docker-compose.yml`](../../docker-compose.yml) and confirm
      the declared `pgvector/pgvector:pg16` service, healthcheck, migration
      service, and API dependency.
- [x] Inspect [`POSTGRESQL_LOCAL_SETUP.md`](POSTGRESQL_LOCAL_SETUP.md) and
      confirm the documented startup, migration, extension, and teardown
      commands.
- [x] Inventory all 14 SQL migrations under `../../migrations/`, including
      `002_enable_pgvector.sql`, `003_store_cache_embeddings.sql`,
      `006_store_canonical_answers.sql`, `008_store_cache_sizes.sql`,
      `011_validate_sha256_hashes.sql`, `012_cache_tenant_namespace.sql`, and
      `013_cache_scoped_identity.sql`.
- [x] Inspect `src/sscre/postgres_cache.py`,
      `src/sscre/migrate.py`, `src/sscre/config.py`, and
      `src/sscre/postgres_failure_harness.py` before changing code or schema.
- [x] Confirm the existing PostgreSQL test files and marker families:
      `tests/test_postgres_integration.py`,
      `tests/test_postgres_vector.py`,
      `tests/test_postgres_cache_scope.py`,
      `tests/test_postgres_failure_closed.py`,
      `tests/test_postgres_failure_recovery.py`,
      `tests/test_postgres_multiprocess_duplicate.py`,
      `tests/test_postgres_contention.py`,
      `tests/test_postgres_eviction_scope.py`, and
      `tests/test_postgres_pg_load.py`.

### Broader stabilization scope

- [x] Include the parent requirements for all integration, failure-recovery,
      contention, multiprocess, and load markers (mapped in evidence Step 1).
- [x] Include startup with a least-privilege application role and separate
      migration role (Step 3 evidence).
- [x] Include canonical-answer integrity, expired/disallowed filtering,
      uniqueness, caps, eviction, cleanup, transaction behavior, vector plans,
      and index decision evidence (filtering / scope: Step 5 evidence; remainder
      Steps 6–8).
- [x] Include the declared measurement metadata: PostgreSQL version, pgvector
      version, migration checksums, Python/package versions, hardware,
      process/worker count, cache settings, vector dimension, candidate count,
      and workload duration (checksums + frozen workload IDs in Step 1 evidence;
      live PG/pgvector versions deferred to Step 2+).
- [x] Record current `HEAD`, `git status --short`, Docker/Compose versions, and
      whether the database service is available before implementation (see
      evidence Step 1 environment table).

**Baseline rule:** If Docker, PostgreSQL, pgvector, or a required role
permission is unavailable, record `unavailable` with the exact reason. Do not
replace PostgreSQL evidence with in-memory or fake-provider results.

## Implementation steps

### Step 1 — Audit the storage contract and freeze the workload

- [x] Document the schema objects, constraints, indexes, migration order, and
      checksum validation behavior.
- [x] Map each parent acceptance criterion to an existing test, SQL probe,
      query-plan capture, bounded load run, or explicit evidence row.
- [x] Record repository methods that perform exact lookup, vector search,
      canonical-answer reads/writes, cleanup, eviction, and duplicate handling.
- [x] Record the current vector representation, configured dimension,
      similarity operator, `top_k`, expiration policy, scope predicates, and
      storage-cap settings.
- [x] Freeze a small deterministic workload for correctness and a separate
      bounded workload for vector plans/load. Do not use held-out semantic
      labels or change the WS5 protocol.
- [x] Write the pre-edit audit into the evidence file as a historical snapshot
      ([`POST_PHASE4_WS4_POSTGRESQL_READINESS_EVIDENCE.md`](./POST_PHASE4_WS4_POSTGRESQL_READINESS_EVIDENCE.md)
      § Step 1, 2026-10-15).

**Stopping rule:** Do not change migrations, indexes, query semantics, or
repository behavior until the pre-edit schema and workload identity are
recorded.

### Step 2 — Build and migrate a clean pgvector database

- [x] Start the documented `postgres` service from a clean named volume.
- [x] Wait for the Compose healthcheck, then verify
      `SELECT extname FROM pg_extension WHERE extname = 'vector'` (0 rows
      pre-migrate; **0.8.7** present post-migrate — see evidence Step 2).
- [x] Run `sscre-migrate --database-url ...` using the documented migration
      path and capture its exit status and checksum output (exit **0**, all
      `000`–`013` applied).
- [x] Query `schema_migrations` and record applied migration names/checksums.
- [x] Verify required tables, columns, constraints, indexes, vector operator
      availability, and canonical-answer foreign-key behavior.
- [x] Run the migration validator again in read-only mode through
      `PostgresExactCacheRepository` initialization or `check_ready`.
- [x] Keep the database URL, password, and any connection string out of
      evidence, logs, screenshots, and committed artifacts.

### Step 3 — Establish the least-privilege startup boundary

- [x] Create separate local-only roles for migration and application use, with
      credentials supplied out of band (`sscre_migrate`, `sscre_app`; see
      [`scripts/ws4_step3_privilege_probe.py`](../../scripts/ws4_step3_privilege_probe.py)).
- [x] Apply migrations as the migration role (fresh `sscre_migrate_probe` DB;
      idempotent re-run on `sscre`).
- [x] Grant the application role only the database/schema/table/sequence
      privileges needed by the runtime path; do not grant `CREATE` or migration
      ownership unless the audit proves it is required. Record that tenant and
      namespace isolation remains an application/repository responsibility, not
      a PostgreSQL role or row-level-security boundary.
- [x] Start the API/repository with the application role after migrations are
      complete and verify readiness, exact lookup, insert, update counters,
      vector lookup, cleanup, and eviction.
- [x] Attempt startup with an intentionally stale or missing migration state
      and confirm the application fails closed with a controlled error.
- [x] If runtime DDL or extension privileges are required, either remove that
      requirement with a focused code/migration change or document the precise
      privilege boundary and deployment procedure (app init `read_only=True`;
      superuser extension bootstrap documented).
- [x] Revoke migration privileges from the application role and repeat the
      startup/readiness check.

### Step 4 — Verify canonical-answer integrity and tamper behavior

- [x] Insert entries sharing a canonical answer and verify deduplication,
      reference counts, storage statistics, and lifecycle cleanup.
- [x] Verify reads use the canonical answer referenced by
      `canonical_answer_hash`, not an untrusted stale denormalized value.
- [x] Tamper with a canonical answer or hash through a privileged test-only
      SQL operation and verify the application rejects or safely handles the
      row without serving corrupted reusable content.
- [x] Verify malformed or mismatched SHA-256 values are rejected by database
      constraints and repository validation.
- [x] Verify generation failure does not persist a cache entry and database
      failure returns the controlled error with request correlation intact.
- [x] Add a regression test only if the current tests do not cover the observed
      gap; keep tamper setup isolated and clean all test rows afterward
      (`_assert_canonical_integrity` + integration tests; evidence Step 4).

### Step 5 — Verify candidate filtering and scope safety

- [x] Insert a controlled mix of fresh, expired, disallowed, allowed, and
      cross-tenant/cross-namespace candidates.
- [x] Confirm the database query itself applies scope and any required
      eligibility predicates, or provide a measured proof that post-query
      filtering cannot hide a valid candidate at the declared `top_k`
      (`ws4-candidate-filter-v1` recall probe; evidence Step 5).
- [x] Confirm expired and disallowed candidates cannot win an exact lookup or
      the application-served semantic result, including when they have a better
      similarity score. Direct repository search may still return an ineligible
      candidate and is not itself the serving boundary.
- [x] Confirm tenant and namespace predicates are present for every scoped
      operation and that missing scope is rejected when required.
- [x] Verify candidate ordering and tie behavior at the configured dimension
      and `top_k`.
- [x] Record the candidate population, filter counts, recall probe, and
      limitation if the implementation still filters after retrieval.

### Step 6 — Run the PostgreSQL correctness and failure matrix

- [x] Run `tests/test_postgres_integration.py`,
      `tests/test_postgres_vector.py`, `tests/test_postgres_cache_scope.py`,
      and `tests/test_postgres_eviction_scope.py` against the migrated service.
- [x] Run the failure-closed and recovery tests:
      `-m ws8_postgres_failure_recovery` and the corresponding
      `tests/test_postgres_failure_closed.py`.
- [x] Run the multiprocess duplicate test with its explicit marker and record
      process count, worker count, generation count, insert conflicts, and
      surviving rows.
- [x] Run the contention marker and record duplicate conflicts, mixed read/write
      behavior, cleanup races, cap enforcement, and database errors separately.
- [x] Clean all generated query hashes and test rows after each scenario; verify
      no unrelated rows were deleted.
- [x] Treat marker skips as `skipped` or `unavailable` with reason, never as a
      passing PostgreSQL result.

### Step 7 — Measure vector query plans and decide on indexing

- [x] Choose and record declared vector dimensions, row counts, candidate
      counts, `top_k`, similarity threshold, tenant/namespace scope, and cache
      state for each plan run.
- [x] Capture the exact parameterized vector query used by
      `PostgresExactCacheRepository.search_by_embedding`.
- [x] Run `EXPLAIN (ANALYZE, BUFFERS)` for a fresh-session observation and warm
      repeats at the declared workload size; capture planning time, execution
      time, buffers, rows removed by filter, sort behavior, and whether the
      query uses the intended index. Do not label a fresh connection as a true
      cold-cache run.
- [x] Record PostgreSQL `shared_buffers` or relevant cache settings, CPU/memory,
      storage type, connection count, process/worker count, and run repetition.
- [x] Compare the measured plan with the existing scoped semantic index and
      determine whether exact/approximate indexing is justified at the declared
      DIM=2, N<=2000 workload only.
- [ ] If adding HNSW or IVFFlat, first document operator class, dimension,
      build parameters, migration lock/build cost, recall test, insert/update
      behavior, and rollback path.
- [x] If no index is added, record the measured reason and the workload boundary
      where a future decision must be revisited using deployed embedding
      dimensions, scoped cardinality, top_k, concurrency, and cache conditions.
- [x] Never infer production latency or capacity from one local plan.

### Step 8 — Verify caps, eviction, cleanup, uniqueness, and transactions

- [x] Run the bounded PostgreSQL load configuration from
      `experiments/workstream8_pg_load_v1.json` through
      `tests/test_postgres_pg_load.py` / `sscre.load_test`; record that the
      protocol stopped after its first pass under `p99_above_5x_p50`.
- [x] Verify entry and byte caps with exact, semantic, canonical-answer, and
      scoped rows; confirm fresh rows are not evicted incorrectly.
- [x] Verify eviction and cleanup delete only the declared query-hash scope and
      remove unreferenced canonical answers without deleting shared answers.
- [x] Verify expired rows are never served while cleanup races with reads and
      writes.
- [x] Verify uniqueness conflicts are classified separately from database and
      validation errors, including concurrent inserts.
- [x] Record transaction isolation/locking assumptions, rollback behavior,
      connection count, concurrency, request count, warmup, errors, and
      stopped reason.
- [x] Keep the partial load result bounded and label synthetic provider behavior
      as synthetic; do not claim provider latency or production capacity.

### Step 9 — Evidence close and handoff

- [x] Write
      `docs/setup/POST_PHASE4_WS4_POSTGRESQL_READINESS_EVIDENCE.md` with
      migration/privilege results, test matrix, SQL probes, query plans,
      bounded load artifact, environment metadata, and limitations.
- [x] Link the evidence from this plan and the parent stabilization plan.
- [x] Record every pass, skip, unavailable result, and failed/stopped scope
      with its reason and exact command.
- [x] Hash or otherwise identify migration/configuration inputs and generated
      artifacts without including secrets.
- [x] Update the parent WS4 checklist only for criteria supported by current
      evidence.
- [x] Reconcile the parent deployment-exit language so PostgreSQL verification
      is not presented as multi-worker, multi-replica, managed-cloud, or SLA
      readiness.
- [x] Run the post-change default suite and record its result:
      `913 passed, 1 skipped, 21 deselected` (the live PostgreSQL markers remain
      opt-in).
- [x] Recheck `git status --short` on all canonical paths before describing the
      workstream as closed; keep status explicit if the package is uncommitted.

## Verification commands

Confirm every referenced path, marker, and CLI option immediately before
recording a result.

```powershell
docker compose up -d postgres
docker compose ps
$env:SSCRE_DATABASE_URL = 'postgresql://<local-role>:<local-password>@localhost:5432/sscre'
python -m sscre.migrate --database-url $env:SSCRE_DATABASE_URL
docker compose exec -T postgres psql -U sscre -d sscre -c "SELECT version(); SELECT extname FROM pg_extension WHERE extname = 'vector';"
python -m pytest -q tests/test_postgres_integration.py tests/test_postgres_vector.py tests/test_postgres_cache_scope.py tests/test_postgres_eviction_scope.py
```

Conditional marker runs:

```powershell
python -m pytest -q -m ws8_postgres_failure_recovery
python -m pytest -q -m ws8_postgres_multiprocess
python -m pytest -q -m ws8_postgres_contention
python -m pytest -q -m ws8_postgres_load
```

For plan capture, use the repository's actual vector query and declared
parameters; do not substitute a generic query:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT ...;
```

Load verification uses the checked-in configuration after confirming the
command and file exist:

```powershell
python -m sscre.load_test `
  --config experiments/workstream8_pg_load_v1.json `
  --output artifacts/operations/workstream8-pg-load-v1.json
python -m sscre.ops_evidence `
  --output artifacts/operations/workstream8-operational-verification.json
```

## Acceptance criteria

- [x] All required PostgreSQL tests either pass or have explicit unavailable
      evidence.
- [x] Migrations are applied and checksummed before application startup.
- [x] Application startup and required runtime operations work with the
      least-privilege application role.
- [x] Any startup DDL or extension privilege requirement is removed or
      explicitly documented.
- [x] Canonical-answer reads, tampered-row handling, expiry, disallowed
      filtering, and scope isolation are verified.
- [x] Vector query plans are captured at the declared dimension and workload
      sizes, with fresh-session and warm-repeat states explicitly distinguished;
      a true cold-cache state is not claimed.
- [x] No HNSW/IVFFlat index is added from the bounded DIM=2, N<=2000 result;
      production-dimension indexing remains deferred until migration, recall,
      build-cost, and plan evidence exists.
- [x] Caps, eviction, cleanup, uniqueness, and transaction behavior are
      verified under bounded concurrent writes (pytest + contention; load
      protocol partial — stopped under `p99_above_5x_p50`).
- [x] PostgreSQL version, pgvector version, migration checksums, hardware,
      worker count, and workload are recorded.
- [x] No result is presented as a universal production SLA, multi-host
      guarantee, or managed-PostgreSQL capacity claim.

## Out of scope for this document

- [ ] Universal production capacity, SLA, multi-region, Kubernetes, or managed
      PostgreSQL claims.
- [ ] Multi-host distributed-cache coordination beyond the declared
      multiprocess test.
- [ ] Live commercial provider behavior, pricing, or latency.
- [ ] New semantic benchmark construction, threshold tuning, or held-out
      evaluation.
- [ ] Broad schema refactoring unrelated to a failing WS4 acceptance criterion.
