# Post–Phase 4 Workstream 4 — PostgreSQL correctness and vector-search readiness

## Goal

Verify the actual PostgreSQL/pgvector storage path at a bounded, declared
scale before making external deployment, vector-search, or capacity claims.
The workstream must distinguish application correctness, migration/privilege
behavior, query-plan observations, and load evidence. A passing local database
run is not a universal production guarantee.

**Status:** `planning-complete` — implementation not started.

**Parent:** [`../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)
Workstream 4.

**Evidence:** To be created at
`docs/setup/POST_PHASE4_WS4_POSTGRESQL_READINESS_EVIDENCE.md` during Step 9.

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

- [ ] Inspect [`../../docker-compose.yml`](../../docker-compose.yml) and confirm
      the declared `pgvector/pgvector:pg16` service, healthcheck, migration
      service, and API dependency.
- [ ] Inspect [`POSTGRESQL_LOCAL_SETUP.md`](POSTGRESQL_LOCAL_SETUP.md) and
      confirm the documented startup, migration, extension, and teardown
      commands.
- [ ] Inventory all 14 SQL migrations under `../../migrations/`, including
      `002_enable_pgvector.sql`, `003_store_cache_embeddings.sql`,
      `006_store_canonical_answers.sql`, `008_store_cache_sizes.sql`,
      `011_validate_sha256_hashes.sql`, `012_cache_tenant_namespace.sql`, and
      `013_cache_scoped_identity.sql`.
- [ ] Inspect `src/sscre/postgres_cache.py`,
      `src/sscre/migrate.py`, `src/sscre/config.py`, and
      `src/sscre/postgres_failure_harness.py` before changing code or schema.
- [ ] Confirm the existing PostgreSQL test files and marker families:
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

- [ ] Include the parent requirements for all integration, failure-recovery,
      contention, multiprocess, and load markers.
- [ ] Include startup with a least-privilege application role and separate
      migration role.
- [ ] Include canonical-answer integrity, expired/disallowed filtering,
      uniqueness, caps, eviction, cleanup, transaction behavior, vector plans,
      and index decision evidence.
- [ ] Include the declared measurement metadata: PostgreSQL version, pgvector
      version, migration checksums, Python/package versions, hardware,
      process/worker count, cache settings, vector dimension, candidate count,
      and workload duration.
- [ ] Record current `HEAD`, `git status --short`, Docker/Compose versions, and
      whether the database service is available before implementation.

**Baseline rule:** If Docker, PostgreSQL, pgvector, or a required role
permission is unavailable, record `unavailable` with the exact reason. Do not
replace PostgreSQL evidence with in-memory or fake-provider results.

## Implementation steps

### Step 1 — Audit the storage contract and freeze the workload

- [ ] Document the schema objects, constraints, indexes, migration order, and
      checksum validation behavior.
- [ ] Map each parent acceptance criterion to an existing test, SQL probe,
      query-plan capture, bounded load run, or explicit evidence row.
- [ ] Record repository methods that perform exact lookup, vector search,
      canonical-answer reads/writes, cleanup, eviction, and duplicate handling.
- [ ] Record the current vector representation, configured dimension,
      similarity operator, `top_k`, expiration policy, scope predicates, and
      storage-cap settings.
- [ ] Freeze a small deterministic workload for correctness and a separate
      bounded workload for vector plans/load. Do not use held-out semantic
      labels or change the WS5 protocol.
- [ ] Write the pre-edit audit into the evidence file as a historical snapshot.

**Stopping rule:** Do not change migrations, indexes, query semantics, or
repository behavior until the pre-edit schema and workload identity are
recorded.

### Step 2 — Build and migrate a clean pgvector database

- [ ] Start the documented `postgres` service from a clean named volume.
- [ ] Wait for the Compose healthcheck, then verify
      `SELECT extname FROM pg_extension WHERE extname = 'vector'`.
- [ ] Run `sscre-migrate --database-url ...` using the documented migration
      path and capture its exit status and checksum output.
- [ ] Query `schema_migrations` and record applied migration names/checksums.
- [ ] Verify required tables, columns, constraints, indexes, vector operator
      availability, and canonical-answer foreign-key behavior.
- [ ] Run the migration validator again in read-only mode through
      `PostgresExactCacheRepository` initialization or `check_ready`.
- [ ] Keep the database URL, password, and any connection string out of
      evidence, logs, screenshots, and committed artifacts.

### Step 3 — Establish the least-privilege startup boundary

- [ ] Create separate local-only roles for migration and application use, with
      credentials supplied out of band.
- [ ] Apply migrations as the migration role.
- [ ] Grant the application role only the database/schema/table/sequence
      privileges needed by the runtime path; do not grant `CREATE` or migration
      ownership unless the audit proves it is required.
- [ ] Start the API/repository with the application role after migrations are
      complete and verify readiness, exact lookup, insert, update counters,
      vector lookup, cleanup, and eviction.
- [ ] Attempt startup with an intentionally stale or missing migration state
      and confirm the application fails closed with a controlled error.
- [ ] If runtime DDL or extension privileges are required, either remove that
      requirement with a focused code/migration change or document the precise
      privilege boundary and deployment procedure.
- [ ] Revoke migration privileges from the application role and repeat the
      startup/readiness check.

### Step 4 — Verify canonical-answer integrity and tamper behavior

- [ ] Insert entries sharing a canonical answer and verify deduplication,
      reference counts, storage statistics, and lifecycle cleanup.
- [ ] Verify reads use the canonical answer referenced by
      `canonical_answer_hash`, not an untrusted stale denormalized value.
- [ ] Tamper with a canonical answer or hash through a privileged test-only
      SQL operation and verify the application rejects or safely handles the
      row without serving corrupted reusable content.
- [ ] Verify malformed or mismatched SHA-256 values are rejected by database
      constraints and repository validation.
- [ ] Verify generation failure does not persist a cache entry and database
      failure returns the controlled error with request correlation intact.
- [ ] Add a regression test only if the current tests do not cover the observed
      gap; keep tamper setup isolated and clean all test rows afterward.

### Step 5 — Verify candidate filtering and scope safety

- [ ] Insert a controlled mix of fresh, expired, disallowed, allowed, and
      cross-tenant/cross-namespace candidates.
- [ ] Confirm the database query itself applies scope and any required
      eligibility predicates, or provide a measured proof that post-query
      filtering cannot hide a valid candidate at the declared `top_k`.
- [ ] Confirm expired and disallowed candidates cannot win exact or vector
      lookup, including when they have a better similarity score.
- [ ] Confirm tenant and namespace predicates are present for every scoped
      operation and that missing scope is rejected when required.
- [ ] Verify candidate ordering and tie behavior at the configured dimension
      and `top_k`.
- [ ] Record the candidate population, filter counts, recall probe, and
      limitation if the implementation still filters after retrieval.

### Step 6 — Run the PostgreSQL correctness and failure matrix

- [ ] Run `tests/test_postgres_integration.py`,
      `tests/test_postgres_vector.py`, `tests/test_postgres_cache_scope.py`,
      and `tests/test_postgres_eviction_scope.py` against the migrated service.
- [ ] Run the failure-closed and recovery tests:
      `-m ws8_postgres_failure_recovery` and the corresponding
      `tests/test_postgres_failure_closed.py`.
- [ ] Run the multiprocess duplicate test with its explicit marker and record
      process count, worker count, generation count, insert conflicts, and
      surviving rows.
- [ ] Run the contention marker and record duplicate conflicts, mixed read/write
      behavior, cleanup races, cap enforcement, and database errors separately.
- [ ] Clean all generated query hashes and test rows after each scenario; verify
      no unrelated rows were deleted.
- [ ] Treat marker skips as `skipped` or `unavailable` with reason, never as a
      passing PostgreSQL result.

### Step 7 — Measure vector query plans and decide on indexing

- [ ] Choose and record declared vector dimensions, row counts, candidate
      counts, `top_k`, similarity threshold, tenant/namespace scope, and cache
      state for each plan run.
- [ ] Capture the exact parameterized vector query used by
      `PostgresExactCacheRepository.search_by_embedding`.
- [ ] Run `EXPLAIN (ANALYZE, BUFFERS)` for cold and warm cache conditions at the
      declared workload size; capture planning time, execution time, buffers,
      rows removed by filter, sort behavior, and whether the query uses the
      intended index.
- [ ] Record PostgreSQL `shared_buffers` or relevant cache settings, CPU/memory,
      storage type, connection count, process/worker count, and run repetition.
- [ ] Compare the measured plan with the existing scoped semantic index and
      determine whether exact/approximate indexing is justified.
- [ ] If adding HNSW or IVFFlat, first document operator class, dimension,
      build parameters, migration lock/build cost, recall test, insert/update
      behavior, and rollback path.
- [ ] If no index is added, record the measured reason and the workload boundary
      where a future decision must be revisited.
- [ ] Never infer production latency or capacity from one local plan.

### Step 8 — Verify caps, eviction, cleanup, uniqueness, and transactions

- [ ] Run the bounded PostgreSQL load configuration from
      `experiments/workstream8_pg_load_v1.json` through
      `tests/test_postgres_pg_load.py` / `sscre.load_test`.
- [ ] Verify entry and byte caps with exact, semantic, canonical-answer, and
      scoped rows; confirm fresh rows are not evicted incorrectly.
- [ ] Verify eviction and cleanup delete only the declared query-hash scope and
      remove unreferenced canonical answers without deleting shared answers.
- [ ] Verify expired rows are never served while cleanup races with reads and
      writes.
- [ ] Verify uniqueness conflicts are classified separately from database and
      validation errors, including concurrent inserts.
- [ ] Record transaction isolation/locking assumptions, rollback behavior,
      connection count, concurrency, request count, warmup, errors, and
      stopped reason.
- [ ] Keep the load result bounded and label synthetic provider behavior as
      synthetic; do not claim provider latency or production capacity.

### Step 9 — Evidence close and handoff

- [ ] Write
      `docs/setup/POST_PHASE4_WS4_POSTGRESQL_READINESS_EVIDENCE.md` with
      migration/privilege results, test matrix, SQL probes, query plans,
      bounded load artifact, environment metadata, and limitations.
- [ ] Link the evidence from this plan and the parent stabilization plan.
- [ ] Record every pass, skip, unavailable result, and failed/stopped scope
      with its reason and exact command.
- [ ] Hash or otherwise identify migration/configuration inputs and generated
      artifacts without including secrets.
- [ ] Update the parent WS4 checklist only for criteria supported by current
      evidence.
- [ ] Reconcile the parent deployment-exit language so PostgreSQL verification
      is not presented as multi-worker, multi-replica, managed-cloud, or SLA
      readiness.
- [ ] Recheck `git status --short` on all canonical paths before describing the
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

- [ ] All required PostgreSQL tests either pass or have explicit unavailable
      evidence.
- [ ] Migrations are applied and checksummed before application startup.
- [ ] Application startup and required runtime operations work with the
      least-privilege application role.
- [ ] Any startup DDL or extension privilege requirement is removed or
      explicitly documented.
- [ ] Canonical-answer reads, tampered-row handling, expiry, disallowed
      filtering, and scope isolation are verified.
- [ ] Vector query plans are captured at declared dimensions, cache states, and
      workload sizes.
- [ ] Any HNSW/IVFFlat decision is supported by migration, recall, and plan
      evidence; no unmeasured index is added.
- [ ] Caps, eviction, cleanup, uniqueness, and transaction behavior are
      verified under bounded concurrent writes.
- [ ] PostgreSQL version, pgvector version, migration checksums, hardware,
      worker count, and workload are recorded.
- [ ] No result is presented as a universal production SLA, multi-host
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
