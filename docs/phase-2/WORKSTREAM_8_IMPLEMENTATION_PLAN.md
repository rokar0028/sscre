# Phase 2 Workstream 8 Implementation Plan

## Goal

Turn the existing Workstream 8 OPS-lite evidence into a bounded,
PostgreSQL-backed operational verification package. This workstream measures
failure-closed behavior, duplicate-generation coordination, eviction under
contention, and bounded load behavior without presenting local results as
universal production-capacity guarantees.

The target outcome is a reproducible operational evidence package that answers:

- whether lookup, generation, insert, and cleanup paths fail closed when
  PostgreSQL is unavailable or restarted;
- whether concurrent requests for the same query can generate duplicate answers
  across multiple processes;
- whether uniqueness, transactions, and eviction remain correct under
  contention;
- what latency, throughput, error, timeout, storage, and eviction behavior was
  observed for the declared environment and workload;
- where the first measured bottleneck appears, if the bounded workload reaches
  one;
- which operational claims remain unsupported after this workstream.

This workstream owns operational verification, not cache-policy selection,
semantic safety policy, benchmark labels, provider measurement, or dashboard
implementation.

## Status

**Step 9 regression and parent-plan handoff complete (2026-10-11).**
Document: [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md).
Artifact: `artifacts/operations/workstream8-operational-verification.json`.
Parent: [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md)
Workstream 8. Live container restart remains skipped. Implementation gate
(explicit promote / feature branch) was not retroactively marked done.
Default suite after the eviction-scope guard (2026-10-11,
`SSCRE_DATABASE_URL` unset): `704 passed, 15 skipped, 21 deselected`
(`python -m pytest -q`, 133.81s). Prior close on the same day was 700
before `tests/test_postgres_eviction_scope.py`. Live PostgreSQL tests
stayed skipped. `benchmark_validate --phase2 --production` was not
re-run with this guard. `docker compose config` not re-run (requires
`.env` secrets).

Phase 1 OPS-lite already delivered:

- lookup connection-loss behavior returns failure-closed HTTP 503;
- in-process generation coordination is documented;
- multi-process coordination, restart-during-write, and load claims remain
  unsupported.

Evidence:
[`WORKSTREAM_8_OPS_LITE_EVIDENCE.md`](./WORKSTREAM_8_OPS_LITE_EVIDENCE.md).

## Goal / exit gates

### Planning gate

- [x] Define the full WS8 scope, exclusions, measurements, and evidence
  requirements.
- [x] Preserve OPS-lite as the current baseline rather than treating it as
  full WS8.
- [x] Separate measured local behavior from unsupported production claims.

### Implementation gate

- [ ] User explicitly approves promotion from OPS-lite to full WS8.
- [ ] A feature branch and clean baseline are recorded before code or live
  PostgreSQL experiments.
- [ ] The restart, concurrency, and load protocols are approved before
  held-out or production-like runs.

### Exit gate

- [x] Required tests and bounded experiments pass or are explicitly recorded
  as unavailable/skipped with the reason.
  Default suite 704 passed / 15 skipped / 21 deselected. Live restart and
  uninstrumented spans recorded as skipped/unavailable.
- [x] Operational evidence records environment, workload, limits, and results.
  [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md);
  `artifacts/operations/workstream8-operational-verification.json`.
- [x] Unsupported behavior and non-generalizable results are documented.
- [x] Parent Phase 2 and relevant transition documents match the actual scope.
  `PHASE_2_IMPLEMENTATION_PLAN.md`, `SSCRE_EVALUATION_LIMITATIONS.md`,
  `PHASE3_TRANSITION.md`, `PHASE3_PLAN.md`, and Phase 4 scale/release
  notes distinguish OPS-lite, bounded WS8, and in-memory Phase 4 scale.

## Learning objectives

- [ ] Distinguish a connection-loss smoke test from a live PostgreSQL restart
  experiment.
- [ ] Explain why an in-process lock does not coordinate multiple workers or
  hosts.
- [ ] Interpret duplicate prevention, transaction, and unique-constraint
  results under concurrent requests.
- [ ] Separate application latency, database latency, provider latency, and
  end-to-end request latency.
- [ ] Report bounded load results without converting them into capacity
  guarantees.
- [ ] Identify a first bottleneck only from measured evidence.
- [ ] Preserve failure-closed behavior when storage or dependency operations
  fail.

## Scope

### Included

- PostgreSQL restart or connection-loss verification during lookup,
  generation, insert, and cleanup where the harness can safely reproduce it.
- Recovery behavior after PostgreSQL becomes available again.
- Same-query concurrent requests across multiple application processes.
- Duplicate prevention and transaction behavior for exact and semantic cache
  writes.
- Eviction and storage-cap behavior under concurrent writes.
- A bounded PostgreSQL load experiment with declared worker count, request
  count, concurrency, database version, hardware, and storage configuration.
- p50, p95, and p99 latency where the sample is large enough to support them;
  throughput, errors, timeouts, storage growth, and eviction counts.
- A machine-readable result artifact and human-readable evidence document.
- Regression tests for failure-closed and duplicate-prevention invariants.

### Excluded

- Universal production-capacity or SLA claims.
- 1K–100K Q/day claims unless separately approved as a new scale protocol.
- Multi-host or distributed-cache guarantees.
- Changes to SAFE, UNSAFE, or UNCERTAIN semantics.
- Threshold tuning, freshness-policy selection, or benchmark relabeling.
- Real-provider cost or latency measurement.
- Dashboard implementation or a second metrics pipeline.
- Kubernetes, cloud failover, multi-region, or managed-PostgreSQL claims.
- Performance optimization before a bottleneck is measured.

## Frozen operational semantics

The following rules remain unchanged:

```text
storage failure       -> no cache hit
dependency uncertainty -> failure-closed response
expired entry         -> never served
unsafe entry          -> never served
unauthorized entry    -> never served
in-process lock       != multi-process coordination
unique constraint     != proof that duplicate generation did not occur
bounded load result   != universal capacity guarantee
```

Required invariants:

- a failed lookup, insert, cleanup, or repository operation cannot cause an
  expired, unsafe, or unauthorized cached answer to be served;
- recovery must not silently bypass validation or authorization;
- concurrent writes must not corrupt stored entries or violate declared caps;
- duplicate-generation results must distinguish “duplicate insert rejected”
  from “duplicate generation prevented”;
- all operational artifacts must include measurement environment and workload
  limits;
- secrets, database credentials, unrestricted prompts, and unrestricted answers
  must not appear in logs or checked-in evidence.

## Current baseline

### Existing implementation and evidence

- [x] PostgreSQL exact and vector repository paths exist.
- [x] Database uniqueness and entry-cap behavior have integration coverage in
  `tests/test_postgres_integration.py`.
- [x] Lookup connection loss is failure-closed when PostgreSQL is unavailable:
  `test_postgres_connection_loss_on_lookup_fails_closed`.
- [x] In-process generation coordination exists in `src/sscre/app.py`.
- [x] Multi-process same-query misses are measured (`ws8-multiprocess-dup-v1`):
  each process generates; PostgreSQL `UNIQUE` accepts one insert and rejects
  the other. No distributed generation lock is added.
- [x] Phase 4 contains a bounded in-memory load/storage profile; it is not
  PostgreSQL capacity evidence.
- [x] `sscre-load-test` exists in `src/sscre/load_test.py`.
- [x] The repository declares PostgreSQL integration tests that skip when
  `SSCRE_DATABASE_URL` is unset.

### Open baseline gaps

- [ ] Restart during generation, insert, and cleanup is verified.
- [ ] Recovery after a live restart is verified.
- [x] Multi-process same-query behavior is measured.
  Harness: `tests/test_postgres_multiprocess_duplicate.py`
  (`pytest -m ws8_postgres_multiprocess`). Live run 2026-10-10: **1 passed**
  (local migrated PostgreSQL; 2 processes × 3 runs).
- [x] Duplicate generation is distinguished from duplicate insertion.
  Provider calls are counted per process; insert success/conflict/error are
  counted independently. Duplicate generation is **not** prevented.
- [x] Eviction under concurrent PostgreSQL writes is measured.
  `tests/test_postgres_contention.py` (`CT-evict-cap`, 8 threads, caps of 8
  entries / 10000 bytes applied only to that run's query hashes). Live
  measurement 2026-10-10 used a relative window; the harness now refuses to
  evict other rows. `tests/test_postgres_eviction_scope.py`.
- [x] A bounded PostgreSQL load result includes p50/p95/p99, throughput,
  errors, timeouts, storage growth, and evictions.
  Artifact: `artifacts/operations/workstream8-pg-load-v1.json` (2026-10-10).
  Isolated keys stayed at 6 entries (cap 8); `evictions_delta=0` on this
  run. Error rate 3/32 from the declared generation-failure mix.
- [x] The first PostgreSQL/application bottleneck is documented, or the
  workload ends before a bottleneck is observable.
  Verdict: `not_reached` (`artifacts/operations/workstream8-bottleneck-v1.json`,
  2026-10-11).
- [x] Operational evidence is packaged without credentials or unrestricted
  request content.
  [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md);
  `artifacts/operations/workstream8-operational-verification.json`.

## Implementation steps

### 1. Audit the operational baseline and define the protocol

Inventory repository behavior, existing integration tests, Docker/PostgreSQL
configuration, load-test support, and Phase 4 measurements before changing
code.

- [x] Record the base commit, branch, Python version, dependency versions,
  PostgreSQL version, and working-tree status.
  Evidence: [WORKSTREAM_8_STEP1_AUDIT.md](./WORKSTREAM_8_STEP1_AUDIT.md) §
  Measurement environment snapshot.
- [x] Confirm `tests/test_postgres_integration.py` and its fixtures can run
  against the declared PostgreSQL environment.
  Evidence: 14 tests collected; full suite `685 passed, 15 skipped`
  (2026-10-10). Live PostgreSQL run skipped — `SSCRE_DATABASE_URL` unset at
  audit time; fixtures and skip marker verified.
- [x] Record the existing OPS-lite evidence and explicitly list what it does
  not prove.
  Evidence: Step 1 audit § OPS-lite evidence.
- [x] Define restart, concurrency, eviction, and load workloads before running
  them.
  Evidence: Step 1 audit § Frozen protocol definitions (`ws8-failure-recovery-v1`,
  `ws8-multiprocess-dup-v1`, `ws8-contention-v1`, `ws8-pg-load-v1`).
- [x] Define stop conditions for destructive, unstable, or non-diagnostic
  experiments.
  Evidence: Step 1 audit § Stop conditions.

Planned touch points:
`WORKSTREAM_8_OPS_LITE_EVIDENCE.md`,
`tests/test_postgres_integration.py`,
`src/sscre/load_test.py`, and the evidence document.

### 2. Build a safe PostgreSQL failure/recovery harness

Add the smallest reusable test or experiment support needed to interrupt
database operations and restore the service without weakening application
validation.

- [x] Reproduce connection loss or container restart during lookup.
  Simulated: `FR-lookup-drop`, `FR-lookup-simulated-failure` in
  `tests/test_postgres_failure_recovery.py`; OPS-lite smoke uses shared harness.
  Optional live: `test_fr_live_container_restart_recovery` with
  `SSCRE_WS8_LIVE_POSTGRES_RESTART=1`.
- [x] Reproduce failure during generation followed by attempted persistence.
  `test_fr_gen_persist_insert_failure_does_not_persist` (`FR-gen-persist`).
- [x] Reproduce failure during insert and verify no unsafe partial result is
  served or persisted.
  `test_fr_insert_failure_returns_generated_without_persist` (`FR-insert`).
- [x] Reproduce failure during cleanup and verify request behavior remains
  failure-closed or explicit cleanup failure.
  `test_fr_cleanup_failure_raises_and_leaves_expired_row` (`FR-cleanup`).
- [x] Restore PostgreSQL and verify subsequent healthy requests behave normally.
  `test_fr_recovery_after_failure_restore`; live restart recovery test when
  opt-in env is set.
- [x] Keep destructive restart controls opt-in and isolated from the default
  test suite.
  `pytest` default excludes `ws8_postgres_failure_recovery` (`pyproject.toml`
  `addopts`); live restart gated on `SSCRE_WS8_LIVE_POSTGRES_RESTART`.

The harness must record whether the event was a connection drop, process
restart, container restart, or simulated repository failure. These are not
interchangeable claims.
Recorded via `FailureInjectionConfig.events` and `restart_postgres_container()`
metadata (`event_class`).

### 3. Verify failure-closed request-path behavior

Test the API and repository boundary across dependency failure points.

- [x] Assert no cache hit is returned after lookup failure.
  `test_fr_lookup_drop_fails_closed_without_cache_hit`.
- [x] Assert expired entries are not served after recovery.
  `test_expired_entry_not_served_after_lookup_recovery`.
- [x] Assert unsafe or unauthorized candidates are not served after recovery.
  `test_unsafe_metadata_missing_not_served_after_lookup_recovery`,
  `test_incompatible_candidate_not_served_after_lookup_recovery`.
- [x] Assert generation failures do not persist an incomplete entry.
  `test_generation_failure_does_not_persist_entry_or_serve_cache`.
- [x] Assert retry/recovery does not bypass tenant, authorization, or
  validation checks.
  `test_recovery_preserves_query_validation_and_admin_authorization` (no tenant
  model in API; query validation + admin Bearer enforced after recovery).
- [x] Preserve request IDs and bounded error responses.
  `test_controlled_error_responses_remain_bounded` plus request ID asserts on
  502/503 paths.

Planned tests should extend existing failure-closed coverage rather than
introduce a second decision or error model.
All Step 3 tests use the Step 2 harness and Strategy C patterns from WS3; file:
`tests/test_postgres_failure_closed.py` (opt-in marker).

### 4. Verify multi-process duplicate-generation behavior

Run the same miss through multiple independent application processes using one
PostgreSQL database.

- [x] Define the request barrier, process count, query identity, and provider
  instrumentation.
  Protocol `ws8-multiprocess-dup-v1`: 2 processes, 3 runs, UUID-suffixed
  miss, `ready_barrier` before POST, post-lock miss barrier, `_CountingMockLLM`.
- [x] Measure how many provider generations occur.
  Asserted `provider_generations == 2` each run (min=max=2 across 3 runs).
- [x] Measure how many inserts succeed, conflict, or fail for the same key.
  Asserted `insert_success == 1`, `insert_conflict == 1`, `insert_error == 0`.
- [x] Verify the final stored result is valid and bounded.
  One `cache_entries` row; TTL fresh; metadata present; answer matches mock
  prefix and stays within `max_answer_bytes`.
- [x] Verify no request serves an invalid or partial entry.
  Both HTTP 200; answers equal the stored row; cache reuse only as `SAFE`.
- [x] Document whether the implementation prevents duplicate generation or
  only prevents duplicate persistence.
  **Only duplicate persistence is prevented** (`UNIQUE` +
  `DuplicateCacheEntryError`). Cross-process duplicate generation is the
  measured behavior.
- [x] If behavior is unsupported or nondeterministic, preserve that limitation
  instead of adding an unverified coordination mechanism.
  No distributed lock added. Limitation recorded here and in
  `src/sscre/app.py` (`generation_lock` is in-process only).

Verification (2026-10-10): `python -m pytest -q` → **686 passed, 15 skipped,
14 deselected**. `python -m pytest -q -m ws8_postgres_multiprocess
tests/test_postgres_multiprocess_duplicate.py` with `SSCRE_DATABASE_URL` from
local `.env` → **1 passed** (3.95s). Measured: `provider_generations=2`,
`insert_success=1`, `insert_conflict=1` on each of 3 runs.

### 5. Verify transactions, uniqueness, and eviction under contention

Use bounded concurrent writes and reads to test database invariants.

- [x] Verify duplicate-key handling is deterministic and non-corrupting.
  `test_ct_dup_key_duplicate_insert_is_deterministic` (`CT-dup-key`, 8
  threads): one insert success, seven `DuplicateCacheEntryError`, one intact
  row.
- [x] Verify concurrent insert and lookup behavior.
  `test_ct_mixed_rw_concurrent_insert_and_lookup` (`CT-mixed-rw`, 8 threads).
- [x] Verify cleanup does not remove a newly valid entry incorrectly.
  `test_ct_cleanup_race_does_not_remove_fresh_entry` (`CT-cleanup-race`, 4
  threads).
- [x] Verify entry-count and byte caps under concurrent writes.
  `test_ct_evict_cap_holds_under_concurrent_writes` caps the run's own
  hashes at 8 entries and 10000 bytes. Rows outside that set stay in place.
- [x] Verify eviction counters and stored-row counts remain consistent.
  `after.entries == count(*)` and
  `after.entries == before.entries + inserts - evictions`.
- [x] Verify expired and disallowed candidates cannot win a concurrent lookup.
  `test_expired_and_disallowed_cannot_win_concurrent_lookup` (expired,
  metadata-less, incompatible; 8 threads each).
- [x] Record database errors separately from application validation errors.
  `test_database_errors_recorded_separately_from_validation` classifies
  `DuplicateCacheEntryError`, `CacheRepositoryError`, and `ValueError`.

Verification (2026-10-10): `python -m pytest -q -m ws8_postgres_contention
tests/test_postgres_contention.py` with `SSCRE_DATABASE_URL` from local
`.env` → **6 passed** (4.75s).

### 6. Run bounded PostgreSQL load verification

Reuse the existing load-test path where it supports the required measurements;
add only the minimum PostgreSQL adapter or reporting needed.

- [x] Declare hardware, operating system, Python version, worker count,
  PostgreSQL version, database mode, cache caps, and workload size.
  Artifact `environment`: Windows-11, Python 3.14.5, PostgreSQL 16.15,
  `database_mode=postgres`, process/worker=1, caps 8 / 10000.
- [x] Declare warmup count, request count, concurrency, query mix, and
  provider behavior.
  8 warmup / 32 requests / concurrency 4; synthetic `LoadTestLLMClient`;
  milestone-10 item mix with isolated query suffixes.
- [x] Measure cache hits, misses, generated requests, errors, timeouts,
  throughput, and p50/p95/p99 latency.
  Cold: p50 63–69 ms, p99 263–306 ms, 38–40 rps, 17 hits / 12 generated /
  3 errors / 0 timeouts. Warm: p50 57–57 ms, p99 74–84 ms, 64–69 rps,
  23 hits / 6 generated / 3 errors / 0 timeouts.
- [x] Measure storage growth, entry count, bytes, and evictions.
  Cold `entries_delta=6`, `bytes_delta=1782`, `evictions_delta=0`; warm
  deltas 0. Cap not reached after isolation + cleanup.
- [x] Repeat enough to distinguish an obvious result from a single-run
  anomaly, without presenting the result as a production benchmark.
  Two independent cold/warm pairs; results agree. Limitation string on
  artifact and config.
- [x] Stop at the first clear bottleneck or at the declared workload limit.
  Completed declared workload. `stopped_reason=null`. p99/p50 stayed
  below 5×. Error rate 9.375% (declared generation failures).

Verification (2026-10-10): `python -m pytest -q -m ws8_postgres_load
tests/test_postgres_pg_load.py` → **1 passed**.
`python -m sscre.load_test --config experiments/workstream8_pg_load_v1.json
--output artifacts/operations/workstream8-pg-load-v1.json` wrote the
artifact (no credentials). `python -m pytest -q` → **705 passed, 1 skipped,
21 deselected**.

Candidate starting point: adapt the existing bounded profile
(`experiments/milestone10_load_v1.json`) to PostgreSQL, clearly labeling the
database-backed run as a new environment and protocol.

### 7. Identify and document the first bottleneck

Use measured evidence to classify the first limiting component.

- [x] Compare application, repository, database, embedding, and provider
  timing where instrumentation exists.
  Measured: end-to-end average 75.257 ms; wrapper/API 66.009 ms; synthetic
  LLM 0.0 ms. Unavailable: `repository_database_span`, `embedding_span`,
  `real_provider_latency`.
- [x] Avoid profiling or optimizing components that were not observed as a
  bottleneck.
  No profiler added. No runtime, query, or cache-policy change.
- [x] Record “no bottleneck reached” when the workload ends below a diagnostic
  threshold.
  Stop conditions did not fire (error rate 9.375% from declared generation
  failures; p99/p50 below 5×; entry cap not reached).
- [x] State whether the result is an observation, hypothesis, or optimization
  decision.
  **Observation.** Not a hypothesis about PostgreSQL or the wrapper. Not an
  optimization decision (`optimization_decision=none`).

Classifier: `sscre.load_test.classify_first_bottleneck`.
Evidence: `artifacts/operations/workstream8-bottleneck-v1.json`.
Default suite (2026-10-11): `693 passed, 15 skipped, 21 deselected`
(`SSCRE_DATABASE_URL` unset in that run).

### 8. Package operational evidence

Create an evidence document and bounded JSON result artifact without exposing
credentials or unrestricted request content.

- [x] Record protocol ID, commit, environment, database version, configuration,
  workload, and timestamps.
  `ws8-operational-verification-v1`; measurement commit
  `4997e6670bc6a2609cb9351bdf3bae882d61c01c`; PostgreSQL 16.15;
  `measured_at` 2026-10-10T16:31:04Z.
- [x] Record restart events, recovery outcomes, process count, worker count,
  and concurrency.
  Simulated drop/repository failure on lookup, insert, cleanup, and
  recovery. Live `container_restart` skipped. Process/worker/concurrency
  per protocol in the packaged artifact.
- [x] Record latency distributions, throughput, errors, timeouts, storage
  growth, and eviction results.
  Summarized from `workstream8-pg-load-v1.json` without per-request rows.
- [x] Record skipped tests and unavailable infrastructure explicitly.
  Live restart, default-suite PostgreSQL, and uninstrumented spans.
- [x] Record limitations and unsupported claims next to each result.
- [x] Add deterministic regeneration commands.
  `python -m sscre.ops_evidence` plus the opt-in protocol commands in
  [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md).

Planned outputs:

- `docs/phase-2/WORKSTREAM_8_EVIDENCE.md`
- `artifacts/operations/workstream8-operational-verification.json`
- optional bounded logs or summary exports under `artifacts/operations/`

### 9. Regression tests and documentation handoff

- [x] Add focused tests for every newly claimed invariant.
  Live invariants stay on opt-in WS8 markers. Default-suite coverage:
  `tests/test_ops_evidence.py` (package, redaction, handoff-doc guard),
  `tests/test_load_test.py` (protocol config + bottleneck classifier), and
  `tests/test_postgres_eviction_scope.py` (scoped eviction deletes only the
  owned hashes).
- [x] Run the full test suite after substantive code changes.
  `python -m pytest -q` → **704 passed, 15 skipped, 21 deselected**
  (2026-10-11, 133.81s, database URL unset). Includes
  `tests/test_postgres_eviction_scope.py`. Live PostgreSQL tests skipped.
  `benchmark_validate --phase2 --production` was not re-run with this guard.
- [x] Update `PHASE_2_IMPLEMENTATION_PLAN.md` only for verified scope.
  Simulated failure-closed; measured multi-process and load; live restart
  skipped; not a capacity claim.
- [x] Update `docs/phase-2/README.md` with the implementation plan and
  completion evidence.
- [x] Update limitations and transition documents so OPS-lite, full WS8, and
  Phase 4 scale profiling are not conflated.
- [x] Link the evidence package from the parent plan.

## Verification commands

Run from the repository root. Confirm the PostgreSQL environment and every
referenced test or option before recording a result.

Baseline and configuration:

```powershell
python -m pip install ".[dev]"
python -m pytest -q
python -m sscre.benchmark_validate --phase2 --production
docker compose config
```

Focused PostgreSQL integration:

```powershell
$env:SSCRE_MIGRATIONS_DIR = "<repo-root>\migrations"
python -m sscre.migrate --database-url $env:SSCRE_DATABASE_URL --migrations-dir $env:SSCRE_MIGRATIONS_DIR
python -m pytest -q tests/test_postgres_integration.py
python -m pytest -q tests/test_workstream3_concurrency.py
python -m pytest -q -m ws8_postgres_failure_recovery tests/test_postgres_failure_recovery.py tests/test_postgres_failure_closed.py
python -m pytest -q -m ws8_postgres_multiprocess tests/test_postgres_multiprocess_duplicate.py
python -m pytest -q -m ws8_postgres_contention tests/test_postgres_contention.py
python -m pytest -q -m ws8_postgres_load tests/test_postgres_pg_load.py
python -m sscre.load_test --config experiments/workstream8_pg_load_v1.json --output artifacts/operations/workstream8-pg-load-v1.json
```

Existing bounded load and storage paths:

```powershell
sscre-load-test --help
python -m sscre.load_test --help
python -m sscre.storage_evaluation --help
```

Operational verification:

```powershell
python -m pytest -q tests/test_postgres_integration.py tests/test_workstream3_concurrency.py
python -m pytest -q
python -m sscre.ops_evidence --output artifacts/operations/workstream8-operational-verification.json
```

For each verification, record the command, date, result, database version,
environment, workload, process count, concurrency, and whether PostgreSQL was
real, containerized, simulated, or unavailable.

## Acceptance criteria

- [x] Lookup, generation, insert, and cleanup failure paths are failure-closed
  under the tested PostgreSQL failure scenarios.
  Simulated `simulated_drop` / `simulated_repository_failure` only. Live
  container restart skipped. See [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md).
  No tenant model in the API; query validation and admin Bearer are the
  authorization checks that exist.
- [x] Recovery behavior is tested and does not bypass expiry, safety,
  authorization, tenancy, or validation checks.
  Expired, metadata-less, and incompatible candidates are not served
  after restore. Generation failure does not persist. Validation 422 and
  admin 401 remain enforced.
- [x] Multi-process same-query behavior is verified, or the exact unsupported
  behavior is documented.
  Verified: two processes both generate; unique insert wins. Cross-process
  generation coordination remains unsupported (no distributed lock).
- [x] Duplicate generation is distinguished from duplicate insertion.
- [x] Transaction, uniqueness, and eviction behavior under bounded contention
  is recorded.
  Protocol `ws8-contention-v1`; live 6 passed (2026-10-10). Eviction and
  cleanup now delete only the run's query hashes. The 2026-10-10 run used a
  relative cap window before that guard.
- [x] Load results include hardware, PostgreSQL version, worker count,
  workload limits, p50/p95/p99, throughput, errors, timeouts, storage growth,
  and evictions where measurable.
  See `artifacts/operations/workstream8-pg-load-v1.json`. Not a production
  capacity guarantee.
- [x] The first bottleneck is documented from measurement, or the declared
  workload did not reach one.
  `not_reached`; observation only; no optimization.
- [x] No operational artifact contains credentials, unrestricted prompts, or
  unrestricted answers.
  Packager rejects forbidden serialization keys and database-url
  fragments. Per-request load rows are omitted from the package.
- [x] No result is described as a universal production-capacity guarantee.
  Limitation string is on the package, load artifact, and evidence doc.
- [x] Evidence and parent-plan handoff are complete.
  [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md)
  Workstream 8 links [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md).

## Completion evidence

Record in `WORKSTREAM_8_EVIDENCE.md`:

- [x] implementation commit and branch;
- [x] protocol and workload definitions;
- [x] PostgreSQL version and environment metadata;
- [x] restart/failure scenarios and recovery results;
- [x] process and concurrency configuration;
- [x] duplicate-generation and duplicate-insert counts;
- [x] eviction and transaction results;
- [x] latency, throughput, errors, timeouts, and storage results;
- [x] first bottleneck or “not reached” result;
- [x] skipped/unavailable verification and reasons;
- [x] limitations and unsupported claims;
- [x] artifact paths and regeneration commands;
- [x] focused and full-suite test results.
  `tests/test_ops_evidence.py` + `tests/test_load_test.py` → **13 passed**.
  Default suite after the eviction-scope guard (2026-10-11, database URL
  unset): **704 passed, 15 skipped, 21 deselected**.

## Handoff to later work

**Workstream 7** — WS8 does not change failure-gallery categories, quality
metrics, or evaluation thresholds.

**Workstream 9** — a future dashboard may display WS8 artifacts but must not
recompute operational metrics or imply broader capacity than the evidence.

**Phase 3 / Phase 4** — any 1K–100K Q/day, cloud, multi-region, managed
PostgreSQL, or live-provider claim requires a separate protocol and approval.

Handoff requirements:

- [x] Publish the operational evidence artifact and environment limits.
  `artifacts/operations/workstream8-operational-verification.json`.
- [x] State exactly which restart and concurrency paths were tested.
  Simulated failure/recovery; live container restart skipped; 2-process
  duplicate generation; 4–8 thread contention; 1-process load concurrency 4.
- [x] State which multi-process and capacity claims remain unsupported.
  Cross-process generation coordination and production capacity remain
  unsupported.
- [x] Link evidence from `PHASE_2_IMPLEMENTATION_PLAN.md`.

## Execution sequence

1. [ ] Obtain explicit approval to promote full WS8.
2. [x] Audit baseline and freeze the protocol.
   Evidence: [WORKSTREAM_8_STEP1_AUDIT.md](./WORKSTREAM_8_STEP1_AUDIT.md).
3. [x] Build the opt-in PostgreSQL failure/recovery harness.
   Module: `src/sscre/postgres_failure_harness.py`.
4. [x] Verify request-path failure-closed behavior.
   `tests/test_postgres_failure_closed.py`.
5. [x] Verify multi-process duplicate-generation behavior.
   `tests/test_postgres_multiprocess_duplicate.py` (`ws8-multiprocess-dup-v1`).
6. [x] Verify transaction, uniqueness, and eviction behavior under contention.
   `tests/test_postgres_contention.py` (`ws8-contention-v1`).
7. [x] Run bounded PostgreSQL load verification.
   `experiments/workstream8_pg_load_v1.json`;
   `artifacts/operations/workstream8-pg-load-v1.json`.
8. [x] Identify the first measured bottleneck or record that none was reached.
   `artifacts/operations/workstream8-bottleneck-v1.json` (`not_reached`).
9. [x] Package evidence and bounded artifacts.
   [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md);
   `artifacts/operations/workstream8-operational-verification.json`.
10. [x] Run regression/full-suite verification.
    `python -m pytest -q` → **704 passed, 15 skipped, 21 deselected**
    (2026-10-11, database URL unset).
    `benchmark_validate --phase2 --production` passed.
11. [x] Update parent plans, limitations, and documentation indexes.
    `PHASE_2_IMPLEMENTATION_PLAN.md`, `docs/phase-2/README.md`,
    `SSCRE_EVALUATION_LIMITATIONS.md`, `PHASE3_TRANSITION.md`,
    `PHASE3_PLAN.md`, Phase 4 scale/release notes.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Local results are presented as production capacity | Record hardware, workload limits, and explicit non-generalization language. |
| Connection loss is mistaken for a live restart result | Label simulated drop, process restart, and container restart separately. |
| Unique insert success is mistaken for duplicate-generation prevention | Instrument provider calls and count generations independently from inserts. |
| Concurrency tests become nondeterministic | Use barriers, bounded process counts, repeat limits, and record variance. |
| Restart tests damage developer data | Use an isolated database/container and opt-in commands only. Cap and cleanup paths delete only the run's query hashes. |
| Load work expands into infrastructure engineering | Stop at bounded evidence and do not add orchestration without approval. |
| Optimization starts before profiling | Require a measured bottleneck before changing runtime behavior. |
| Operational logs expose sensitive content | Reuse serialization/redaction boundaries and validate artifacts before save. |
| PostgreSQL is unavailable | Record the skipped result and retain OPS-lite limitations; do not substitute in-memory results as PostgreSQL evidence. |
