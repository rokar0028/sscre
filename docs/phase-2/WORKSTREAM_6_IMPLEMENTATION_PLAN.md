# Phase 2 Workstream 6 Implementation Plan

## Goal

Evaluate freshness policies as an explicit cache-policy experiment rather than
assuming that one TTL configuration is appropriate for every workload. The
workstream must compare stable, semi-dynamic, and dynamic query classes under
declared TTL and invalidation rules, while preserving the existing
failure-closed safety contract.

The target outcome is a reproducible freshness evaluation package that answers:

- whether the benchmark contains enough stable, semi-dynamic, and dynamic
  examples for a meaningful comparison;
- how each policy class changes safe reuse, stale-answer exposure, latency,
  estimated cost, token use, and storage;
- whether dynamic queries are blocked from reuse when policy disallows them or
  when their entries are expired;
- how explicit invalidation behaves where the current cache implementation
  supports it;
- whether the selected freshness policy satisfies predeclared safety and
  freshness constraints on the held-out split;
- which conclusions are supported by synthetic replay and which require
  real-provider measurements.

This workstream consumes the frozen contracts from Workstreams 1 and 3, the
reviewed benchmark and temporal metadata from Workstream 2, provider labels
from Workstream 4 when available, and the statistical/reporting machinery from
Workstream 5. It owns freshness-policy experiments, not a second evaluation
pipeline.

## Status

**Mostly complete — Steps 1–12 (Option A, 2026-10-09)**; see
[`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md). Development policy
matrix replay, selection (`conservative`), held-out stable-only evaluation,
invalidation boundary test, storage pairing, and regression tests are
recorded. Held-out has no semi-dynamic or dynamic pairs; WS5 held-out artifacts
may still be stale against the current split manifest (documented limitation).

Current known baseline:

- `stable`, `semi_dynamic`, and `dynamic` are represented in the benchmark
  schema and query metadata.
- `CacheControlPolicy` supports independent stable and semi-dynamic TTLs,
  optional dynamic TTLs, and a dynamic-entry allow switch.
- Reads fail closed for disabled dynamic entries, missing expiration, invalid
  expiration, and expired entries.
- In-memory and PostgreSQL repositories support deletion by query hash
  internally; explicit invalidation is tested at the repository boundary
  (`freshness_invalidation.py`, `invalidation_scope: repository_boundary_only`).
  No public invalidation HTTP API exists.
- Workstream 5 reports freshness strata, but its selected operating point does
  not compare alternative TTL policies.

Open status:

- [x] Freeze the policy matrix and freshness-specific constraints (Step 2).
- [x] Validate or extend benchmark coverage for all three freshness classes
  (counts recorded; held-out semi/dynamic absent — Option A scope).
- [x] Add deterministic policy-sweep replay and stale-exposure accounting.
- [x] Evaluate explicit invalidation where supported, or record it as
  unavailable with the reason.
- [x] Produce development and held-out freshness artifacts.
- [x] Link completion evidence from the Phase 2 parent plan.

## Source of truth

The scope is defined by Workstream 6 in
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).
General freshness behavior is implemented by:

- `src/sscre/cache_controls.py` — TTL policy and failure-closed eligibility;
- `src/sscre/config.py` — configured TTL and dynamic-entry settings;
- `src/sscre/safety.py` — temporal metadata and decision vocabulary;
- `src/sscre/metadata.py` — query temporal classification;
- `src/sscre/app.py` — request-path cache-control evaluation and traces;
- `src/sscre/cache.py` and `src/sscre/postgres_cache.py` — entry expiry,
  deletion, and storage behavior;
- `src/sscre/baseline.py` — deterministic replay observations;
- `src/sscre/evaluate.py` and `src/sscre/evaluation_statistics.py` —
  Workstream 5 reporting and intervals;
- `src/sscre/storage_evaluation.py` — storage footprint and eviction metrics.

Frozen inputs:

- [`SAFETY_EVALUATION_CONTRACT_v1.md`](./SAFETY_EVALUATION_CONTRACT_v1.md)
  defines `SAFE`, `UNSAFE`, and `UNCERTAIN`.
- [`CANDIDATE_TRACE_CONTRACT_v1.md`](./CANDIDATE_TRACE_CONTRACT_v1.md)
  defines bounded freshness and decision evidence.
- [`SERIALIZATION_BOUNDARY_v1.md`](./SERIALIZATION_BOUNDARY_v1.md) defines
  report, log, and redaction boundaries.
- [`EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
  keeps compatibility, correctness, and preference independent.
- [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md) defines the current
  held-out dataset, statistics, and provider limitations.
- `benchmarks/reviewed_query_pairs.jsonl` and its split manifest define the
  reviewed freshness classes and immutable development/held-out IDs.

Canonical artifact locations to add or update:

| Responsibility | Current or planned module/artifact |
|---|---|
| Freshness policy primitives | `src/sscre/cache_controls.py` |
| Runtime settings | `src/sscre/config.py` |
| Query and benchmark temporal classes | `src/sscre/metadata.py`, `src/sscre/benchmark.py` |
| Request-path freshness traces | `src/sscre/app.py`, `src/sscre/cache_control_traces.py` |
| Policy replay | `src/sscre/freshness_replay.py`, `src/sscre/freshness_evaluation.py` |
| Metrics / stale exposure | `src/sscre/freshness_metrics.py`, `src/sscre/freshness_stale_exposure.py` |
| Selection / invalidation / storage | `src/sscre/freshness_policy_selection.py`, `src/sscre/freshness_invalidation.py`, `src/sscre/freshness_storage.py` |
| Statistical attachment | `src/sscre/evaluation_statistics.py` |
| Storage companion | `src/sscre/storage_evaluation.py` |
| Freshness CLI | `src/sscre/freshness_evaluate.py` |
| Artifact packaging | `src/sscre/freshness_artifacts.py` |
| Freshness artifacts | `artifacts/evaluation/workstream6-*.json` |
| Freshness tests | `tests/test_workstream6_freshness.py` and focused existing tests |
| Completion evidence | `docs/phase-2/WORKSTREAM_6_EVIDENCE.md` |

## Learning objectives

- [ ] Explain why freshness class, TTL, expiration outcome, and compatibility
  are separate dimensions.
- [ ] Distinguish stable, semi-dynamic, and dynamic workloads without using
  query wording alone as proof of freshness.
- [ ] Design a policy matrix that can be selected from development data without
  using held-out labels.
- [ ] Define stale-answer exposure and distinguish it from ordinary
  compatibility failure.
- [ ] Interpret the trade-off between reuse, freshness safety, latency, cost,
  and storage.
- [ ] Understand why a disabled dynamic entry is different from an expired
  dynamic entry.
- [ ] Explain the limits of synthetic replay for freshness and provider-cost
  conclusions.
- [ ] Preserve failure-closed behavior when expiration metadata is missing or
  malformed.

## Scope

### Included

- A declared policy matrix covering at least:
  - stable: long TTL;
  - semi-dynamic: shorter TTL;
  - dynamic: no reuse by default and, only as an explicit experiment, a
    short positive TTL with dynamic entries enabled.
- Development-only selection of an approved policy or policy family.
- Held-out replay with the selected policy frozen before held-out evaluation.
- Metrics for reuse, safe reuse, stale exposure, dynamic blocking, expired
  entries, latency, estimated cost, token use, storage, and evictions.
- Breakdowns by benchmark `freshness_class` and relevant cache-control outcome.
- Separate reporting for TTL expiration and explicit invalidation.
- Deterministic synthetic replay using the Workstream 5 benchmark and
  statistical schema.
- Optional provider-labeled rows when Workstream 4 supplies them; unavailable
  real-provider fields remain explicit.
- Tests that prove dynamic and expired entries cannot be served when policy
  disallows them.
- Completion evidence with commands, configuration, artifacts, limitations,
  and parent-plan handoff.

### Excluded

- Changing the meaning of `SAFE`, `UNSAFE`, or `UNCERTAIN`.
- Inferring freshness class from observed cache outcomes.
- Tuning freshness policy from held-out labels or held-out stale outcomes.
- New semantic models, cross-encoders, adaptive thresholds, or dual-model
  experiments.
- A second statistics or dashboard pipeline.
- Claiming real-time provider freshness without a real-provider run.
- PostgreSQL restart, multi-process, or capacity claims owned by Workstream 8.
- A public invalidation API unless a separate product requirement authorizes
  and specifies it.
- Treating longer TTL as inherently better because it increases hit rate.

## Frozen freshness semantics

Freshness and compatibility must remain separate:

```text
freshness class       != cache-control outcome
cache-control outcome != compatibility decision
expiration validity   != answer correctness
disabled dynamic      != expired dynamic
stale exposure        != every UNSAFE decision
development policy    != held-out policy selection
unavailable metric    != zero
```

The runtime order remains:

1. classify policy eligibility, including whether dynamic entries are allowed;
2. validate expiration metadata and reject expired entries;
3. run compatibility and safety evaluation on eligible candidates;
4. serve only a candidate whose final decision is `SAFE`.

Required invariants:

- `dynamic_entries_disabled`, `missing_expiration`, `invalid_expiration`, and
  `expired` cannot produce a cache hit;
- an expired but otherwise compatible answer is not served;
- a fresh but incompatible answer is not served;
- `UNCERTAIN` remains failure-closed;
- no policy sweep may rewrite benchmark labels or infer labels from outcomes;
- a generated dynamic answer is not cached when dynamic entries are disabled;
- an enabled dynamic policy must still apply its configured positive TTL.

## Policy experiment contract

### Policy matrix

Freeze policy configurations before development replay. The exact numeric
values must be recorded in the experiment config and selected for operational
meaning, not post-hoc held-out performance.

The minimum matrix is:

| Policy | Stable | Semi-dynamic | Dynamic | Purpose |
|---|---:|---:|---:|---|
| `conservative` | short positive TTL | shorter positive TTL | disabled | freshness-first control |
| `default` | current configured TTL | current configured TTL | disabled | current product baseline |
| `dynamic-short` | current configured TTL | current configured TTL | short positive TTL | explicit dynamic opt-in |
| `long-lived` | long TTL | medium TTL | disabled | reuse/storage trade-off |

Values must be expressed in seconds in JSON configuration and converted to
`CacheControlPolicy` through the existing settings boundary. A policy may be
omitted only with a documented reason, such as duplicate behavior.

The dynamic-short arm is an experiment, not a recommendation. It must report
whether dynamic reuse introduces stale exposure and must never silently become
the default runtime policy.

### Selection constraints

Select from development data only, using constraint-first logic:

1. reject policies that exceed the declared stale-exposure cap;
2. reject policies that permit disallowed dynamic reuse;
3. reject policies that violate the existing false-positive cap;
4. rank eligible policies by the documented objective, such as safe reuse
   coverage minus a freshness-risk penalty;
5. freeze the selected policy and evaluate it once on held-out.

If no policy satisfies the constraints, record
`constraint_satisfied: false`, select no approved policy, and retain diagnostic
rows without presenting the least-safe policy as a recommendation.

Candidate policy records must include:

- policy name and exact TTL values;
- dynamic-entry setting;
- selection rule and objective;
- all constraints and caps;
- development sample counts;
- selected/not-selected status;
- held-out constraint results;
- config version, dataset version, and git identity.

### Stale-answer exposure

The first implementation must define stale exposure explicitly in the evidence
and test it with controlled time. At minimum distinguish:

- a request whose eligible candidate is rejected because it is expired;
- a request that would have reused an answer under a longer TTL but is blocked
  under the tested policy;
- a reviewed stale-answer case where serving would violate the benchmark's
  expected reuse or freshness label;
- dynamic reuse when dynamic entries are enabled.

Do not call every expired entry a stale-answer correctness failure: an expired
entry is evidence of freshness protection, while stale exposure requires a
served or otherwise benchmark-observable freshness violation.

## Current baseline

### Existing implementation

- [x] `TemporalClass` supports `stable`, `semi_dynamic`, and `dynamic`.
- [x] Benchmark records carry `freshness_class` and temporal metadata.
- [x] `CacheControlPolicy` provides separate stable, semi-dynamic, and dynamic
  TTL behavior.
- [x] Dynamic entries are disabled by default and require an explicit dynamic
  TTL when enabled.
- [x] Cache-control outcomes include `fresh`, `dynamic_entries_disabled`,
  `missing_expiration`, `invalid_expiration`, and `expired`.
- [x] Request traces expose freshness class and cache-control outcome.
- [x] Expired exact and semantic candidates are rejected before reuse.
- [x] Workstream 3 tests cover fresh, expired, missing, invalid, and dynamic
  cache-control paths.
- [x] Workstream 5 statistics can stratify observations by freshness class.
- [x] Storage evaluation reports entries, bytes, and evictions.
- [x] Freshness policy sweep artifacts exist (`workstream6-*-freshness.json`).
- [x] Stale-exposure metrics and development selected-policy record exist
  (`freshness_stale_exposure.py`, `selected_policy` in artifacts).
- [x] Frozen invalidation experiment protocol (Step 7 protocol in contract +
  `freshness_invalidation.py`).
- [x] Workstream 6 completion evidence in
  [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md) (Step 12).

### Open baseline gaps

- [x] Held-out has 0 semi-dynamic and 0 dynamic pairs (Step 1); Option A declares
  held-out stable-only with semi/dynamic unavailable in config.
- [ ] 9 development semi-dynamic/dynamic pairs are too few for interval-backed
  class claims; label results diagnostic unless coverage grows.
- [ ] Regenerate or annotate WS5 held-out artifacts, which predate the current
  split manifest.
- [x] Report both reviewed and runtime strata (`freshness_class_reporting:
  both`; contract § Freshness class reporting).
- [x] Versioned freshness-policy configuration and schema metadata (Step 2).
- [x] Deterministic replay clock and compatibility-baseline wiring (Step 3).
- [x] Capture stale-exposure and cache-control outcome samples without raw
  query or answer text in statistical attachments.
- [x] Define storage pairing for each TTL arm and label synthetic storage
  simulation separately.
- [x] Record invalidation as tested, unsupported, or not applicable; do not
  infer invalidation behavior from TTL deletion (`workstream6-invalidation.json`,
  `ttl_expiration_used: false`).

## Implementation steps

### 1. Audit freshness behavior and benchmark coverage

Inventory the existing cache-control path, benchmark class counts, trace fields,
storage hooks, and tests before changing code.

- [x] Record current stable, semi-dynamic, and dynamic counts by split.
- [x] Record current TTL defaults and dynamic-entry behavior.
- [x] Record every freshness-related trace outcome and its decision mapping.
- [x] Identify reviewed stale-answer and temporal-mismatch rows.
- [x] Identify whether any current repository or API path supports explicit
  invalidation without adding a new product surface.
- [x] Confirm the Workstream 5 artifact fields that can be reused directly.
- [x] Write an audit note in `WORKSTREAM_6_EVIDENCE.md` or a linked step audit.

Step 1 evidence (2026-10-08), recorded in
[`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md):

- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2
  --production` → passed (400 / 215 / 615).
- [x] Focused freshness tests → 31 passed; eviction, storage, and statistics
  attachment tests → 14 passed.
- [x] Held-out split has **0** semi-dynamic and **0** dynamic pairs
  (development: 5 and 4).
- [x] Replay uses the runtime classifier, a hard-coded default policy, and
  wall-clock time; reviewed and runtime classes disagree on 31/800
  development and 3/430 held-out queries.
- [x] Explicit invalidation exists only as repository `delete_by_query_hash`;
  no public route and no direct test.
- [x] `workstream5-held-out-comparison.json` was generated against split
  manifest `69c90c41…`; the checked-in manifest is `c0109b36…`. WS5 held-out
  artifacts are stale against the current split.
- [x] Option A frozen: development-only experiment; held-out stable-only
  (see evidence § Scope decision).

### 2. Freeze the freshness experiment schema and policy config

Define a versioned machine-readable contract before replay.

Planned touch points:
`experiments/evaluation_config.json`,
`src/sscre/serialization.py`,
`src/sscre/evaluation_statistics.py`,
`tests/test_workstream6_freshness.py`.

- [x] Add a freshness experiment schema version, for example
  `freshness-evaluation-1.0`.
- [x] Define policy records with stable, semi-dynamic, and dynamic TTL values.
- [x] Define `allow_dynamic_entries` and reject inconsistent dynamic settings.
- [x] Define stale-exposure, dynamic-reuse, and freshness-violation fields.
- [x] Define the selected-policy record and constraint result shape.
- [x] Preserve report redaction and existing schema attachment behavior.
- [x] Add validation for positive TTLs, finite metrics, and consistent policy
  names.

Step 2 evidence (2026-10-08):

- [x] [`FRESHNESS_EVALUATION_CONTRACT_v1.md`](./FRESHNESS_EVALUATION_CONTRACT_v1.md).
- [x] `src/sscre/freshness_evaluation.py`, `experiments/evaluation_config.json`
  (`freshness_experiment`), `serialization.py`, `evaluate.py`.
- [x] Option A: `scope: development_only`, held-out semi/dynamic unavailable,
  `freshness_class_reporting: both`.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 8 passed
  (2026-10-08); regression bundle with evaluate/statistics/benchmark → 81
  passed (2026-10-08).

Required top-level metadata:

- dataset version and split;
- benchmark artifact and manifest;
- policy schema version and config version;
- measurement environment;
- policy matrix and selected policy;
- sample counts by freshness class and outcome;
- software version, git commit, dirty flag, and UTC timestamp;
- limitations and unavailable measurement fields.

### 3. Add deterministic policy construction and clock control

Make every policy arm reproducible without relying on wall-clock timing.

- [x] Build policies through the existing `CacheControlPolicy` and `Settings`
  boundaries rather than duplicating TTL logic.
- [x] Add a controlled comparison time or clock injection at the smallest
  existing boundary that permits deterministic replay.
- [x] Ensure policy construction cannot create a dynamic policy without a
  positive dynamic TTL.
- [x] Preserve timezone-aware expiration validation.
- [x] Test exact-boundary behavior when `now == ttl_expires_at`.
- [x] Test that a policy arm cannot mutate the next arm's cache state.

Step 3 evidence (2026-10-08):

- [x] `FreshnessReplayClock`, `build_replay_clocks_for_matrix`, and
  `FreshnessPolicySpec.to_settings()` in `freshness_evaluation.py`.
- [x] Compatibility baseline optional `freshness_replay_clock` uses injected
  policy/time for cache control and insert TTLs (`baseline.py`).
- [x] Contract § Deterministic replay clock updated.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 13 passed
  (2026-10-08); `tests/test_workstream3_replay.py` + `tests/test_benchmark.py`
  regression → passed with WS6 file.

Do not alter production failure-closed semantics just to simplify replay.
Replay-only clock injection must be clearly separated from runtime defaults.

### 4. Implement freshness-policy replay

Replay the same reviewed records under each policy arm. Reuse Workstream 5
baseline observations and accounting rules where possible.

- [x] Apply each policy to development records without changing labels.
- [x] Apply the frozen selected policy to held-out records only after
  development selection is recorded (`--selected-policy` required on held-out).
- [x] Keep cache state isolated per policy and per split.
- [x] Record request-level numeric observations and bounded categorical counts.
- [x] Preserve baseline identity and measurement environment.
- [x] Ensure no expired, disabled, missing-expiration, or invalid-expiration
  candidate is served (compatibility replay + existing WS3 tests).
- [x] Compatibility-cache replay path wired; exact-cache per-policy deferred to
  Step 5+ if needed for cross-baseline freshness tables.
- [x] Keep no-cache behavior as a reference row.

Step 4 evidence (2026-10-08):

- [x] `src/sscre/freshness_replay.py`, `src/sscre/freshness_evaluate.py` CLI.
- [x] `CompatibilityCacheReport.cache_control_outcome_counts` from replay traces.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 16 passed
  (2026-10-08).
- [ ] Full development artifact:
  `artifacts/evaluation/workstream6-development-freshness.json` (optional
  record after manual CLI run).

The replay must expose enough information to distinguish:

- generated because no reusable candidate existed;
- blocked by dynamic policy;
- blocked by expiration;
- rejected for malformed expiration;
- eligible but rejected by compatibility;
- safely reused.

### 5. Add freshness metrics and stratified summaries

Attach freshness metrics to the existing Workstream 5-compatible report shape.

Minimum metrics per policy and freshness class:

- request count and candidate count;
- cache hit rate and safe reuse coverage;
- served reuse count;
- expired-candidate count and rate;
- dynamic-disabled count and rate;
- missing/invalid-expiration count and rate;
- observed stale exposure count and rate;
- reviewed stale-answer violations, where labels are available;
- `SAFE`, `UNSAFE`, and `UNCERTAIN` rates;
- p50, p95, and p99 latency;
- estimated cost and token counts;
- storage entries, bytes, and evictions.

Required sections:

```text
metrics_overall
metrics_by_freshness_class
metrics_by_cache_control_outcome
metrics_by_policy
selected_policy
invalidation
limitations
```

- [x] Reuse Workstream 5 interval methods and seed policy.
- [x] Mark sparse or unavailable intervals explicitly.
- [x] Keep synthetic replay and real-provider rows separately labeled.
- [x] Ensure no raw queries, answers, credentials, or unrestricted traces are
  included in the statistical attachment.

Step 5 evidence (2026-10-08):

- [x] `src/sscre/freshness_metrics.py` — `metrics_overall`, stratified class
  sections, `metrics_by_cache_control_outcome`, `statistics_by_policy`,
  `invalidation`, storage unavailable placeholder.
- [x] `runtime_temporal_class` on compatibility replay request samples.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 18 passed
  (2026-10-08).

### 6. Implement and test stale-exposure accounting

Use reviewed temporal metadata and controlled replay outcomes; do not invent
freshness labels from runtime behavior.

- [x] Define the stale-exposure numerator and denominator in the contract.
- [x] Count served stale or disallowed dynamic answers separately from blocked
  stale candidates.
- [x] Test a controlled stale-answer fixture under long and short TTL arms.
- [x] Test that blocked expiration is protection, not served stale exposure.
- [x] Test that a fresh incompatible candidate is not counted as a freshness
  violation.
- [x] Test missing and invalid expiration as safety failures, not successful
  reuse.
- [x] Add deterministic interval tests for stale-exposure proportions.

Step 6 evidence (2026-10-08):

- [x] `src/sscre/freshness_stale_exposure.py`, contract § numerators/denominators.
- [x] `stale_exposure_accounting` blocks on freshness replay artifacts.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 24 passed
  (2026-10-08).

If the benchmark does not provide enough reviewed stale-answer labels, publish
runtime freshness-protection metrics while marking answer-level stale exposure
as unavailable rather than substituting zero.

### 7. Evaluate explicit invalidation separately from TTL expiration

The plan must not conflate deletion with expiration.

- [x] Document the existing `delete_by_query_hash` capabilities for in-memory
  and PostgreSQL repositories.
- [x] Decide whether an explicit invalidation test can be run through an
  existing supported repository boundary.
- [x] If supported, run a controlled sequence: insert, verify fresh reuse,
  invalidate, verify no reuse, regenerate, and verify replacement.
- [x] Record invalidation latency, resulting storage count/bytes, and whether
  the invalidated entry can reappear through semantic retrieval.
- [x] If unsupported, emit an explicit unavailable record with the repository,
  missing boundary, and consequence.
- [x] Do not add a public invalidation endpoint as incidental scope.

Step 7 evidence (2026-10-08):

- [x] `src/sscre/freshness_invalidation.py`; `invalidation` block on replay
  artifacts (`status: evaluated`, synthetic in-memory repository).
- [x] Contract § Repository capabilities and sequence.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 27 passed
  (2026-10-08).

The invalidation artifact must identify whether the result is synthetic
repository behavior, PostgreSQL integration behavior, or unavailable.

### 8. Pair storage evaluation with policy arms

Run storage evaluation for aligned policy configurations rather than reusing a
single footprint for all TTL policies.

- [x] Pair each policy with an aligned storage configuration and dataset
  version.
- [x] Measure entries, bytes, expired cleanup, and eviction counts.
- [x] Distinguish lazy read rejection from physical deletion.
- [x] Label storage rows `synthetic_storage_simulation` unless measured in a
  supported real environment.
- [x] Add reuse-versus-storage points for policy arms where observations are
  aligned.
- [x] Mark the plane unavailable when a matching storage run is not possible.

Step 8 evidence (2026-10-08):

- [x] `src/sscre/freshness_storage.py`; `policy_storage_snapshot` on compatibility
  replay reports; `storage_by_policy`, `reuse_vs_storage_points` on artifacts.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py
  tests/test_storage_evaluation.py` → 33 passed (2026-10-08).

### 9. Select a development policy and freeze the held-out run

Use a predeclared constraint-first procedure.

- [x] Run every policy arm on development.
- [x] Write the selection record before reading held-out results.
- [x] Verify the selection record does not contain held-out labels or outcomes.
- [x] Run the selected policy on held-out with the benchmark frozen.
- [x] Record held-out constraint satisfaction and all policy metrics.
- [x] Retain non-selected policy rows only as development diagnostics unless
  the experiment contract explicitly permits held-out comparison.
- [x] Record exact commands, config hashes, git identity, and test result.

Step 9 evidence (2026-10-08):

- [x] `src/sscre/freshness_policy_selection.py`; development `selected_policy` +
  `policy_selection`; held-out requires frozen development artifact.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 32 passed
  (2026-10-08).

### 10. Generate the freshness evaluation artifacts

Create machine-readable artifacts suitable for Workstream 9 without creating a
second analytics pipeline.

Planned artifacts:

- `artifacts/evaluation/workstream6-development-freshness.json`;
- `artifacts/evaluation/workstream6-held-out-freshness.json`;
- `artifacts/evaluation/workstream6-invalidation.json`, when supported;
- `docs/phase-2/WORKSTREAM_6_EVIDENCE.md`.

- [x] Include policy matrix, selected policy, and constraint results.
- [x] Include freshness-class and cache-control outcome breakdowns.
- [x] Include statistics schema and interval metadata.
- [x] Include storage companion references and environment labels.
- [x] Include unavailable fields and their consequences.
- [x] Make regeneration deterministic from checked-in config and commands.

Step 10 evidence (2026-10-08):

- [x] `src/sscre/freshness_artifacts.py`; CLI attaches `freshness_artifact_metadata`
  and writes invalidation sidecar for standard development output.
- [x] `artifacts/evaluation/workstream6-development-freshness.json`,
  `workstream6-held-out-freshness.json`, `workstream6-invalidation.json`.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 33 passed
  (2026-10-08).

### 11. Regression, serialization, and safety tests

- [x] Add focused unit tests for policy construction and boundary times.
- [x] Add replay tests for all three freshness classes.
- [x] Add tests proving dynamic entries are not served by default.
- [x] Add tests proving enabled dynamic entries respect their TTL.
- [x] Add tests proving expired entries are never served.
- [x] Add tests proving policy arms do not leak cache state.
- [x] Add tests for stale-exposure and invalidation accounting.
- [x] Add serialization/redaction tests for freshness artifacts.
- [x] Confirm existing Workstream 3 freshness tests remain green.
- [x] Run the full suite after substantive implementation changes.

Step 11 evidence (2026-10-08):

- [x] Extended `tests/test_workstream6_freshness.py` (policy TTL boundaries,
  three-class replay breakdown, dynamic default/TTL, expired entries, matrix arm
  isolation, artifact redaction, checked-in artifact redaction guard).
- [x] `python -m pytest -q tests/test_cache_controls.py
  tests/test_cache_ttl_integration.py tests/test_workstream3_freshness.py
  tests/test_workstream6_freshness.py` → 73 passed (2026-10-08).
- [x] `python -m pytest -q` → 648 passed, 14 skipped (2026-10-08).

### 12. Record evidence and update parent handoff

- [x] Record implementation paths and schema versions.
- [x] Record benchmark and split counts by freshness class.
- [x] Record policy matrix and selected-policy rule.
- [x] Record development and held-out commands and artifact paths.
- [x] Record stale-exposure definitions and interval methods.
- [x] Record invalidation result or explicit unavailable status.
- [x] Record storage pairing and measurement environments.
- [x] Record full-suite result and skipped integrations.
- [x] Record limitations, especially sparse dynamic classes and missing
  real-provider measurements.
- [x] Link `WORKSTREAM_6_EVIDENCE.md` from
  `PHASE_2_IMPLEMENTATION_PLAN.md`.

Step 12 evidence (2026-10-09):

- [x] Consolidated handoff in [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md)
  § Step 12; parent plan updated.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 45 passed
  (2026-10-09).

## Verification commands

Run from the repository root. Confirm every path and option exists before
recording a command as evidence.

Focused freshness and cache-control tests:

```powershell
python -m pytest -q `
  tests/test_cache_controls.py `
  tests/test_cache_ttl_integration.py `
  tests/test_workstream3_freshness.py
```

Workstream 6 tests after implementation:

```powershell
python -m pytest -q tests/test_workstream6_freshness.py
```

Workstream 5 regression and statistics:

```powershell
python -m pytest -q `
  tests/test_evaluation_statistics.py `
  tests/test_evaluate_statistics_attachment.py `
  tests/test_workstream3_replay.py
```

Full suite:

```powershell
python -m pytest -q
```

Benchmark and scale validation:

```powershell
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2
```

Planned development replay:

```powershell
python -m sscre.freshness_evaluate `
  --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json `
  --split development `
  --output artifacts/evaluation/workstream6-development-freshness.json
```

Planned held-out replay, only after policy selection:

```powershell
python -m sscre.freshness_evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --split held-out `
  --production `
  --selected-policy artifacts/evaluation/workstream6-development-freshness.json `
  --output artifacts/evaluation/workstream6-held-out-freshness.json
```

For each successful verification, record:

- command and date;
- dataset, split, manifest, config, and schema versions;
- policy name and TTL values;
- sample counts by freshness class and outcome;
- stale-exposure definition and result;
- invalidation status;
- storage environment and companion artifact;
- test count and skipped integrations;
- pass/fail result and known limitations.

Do not mark freshness claims complete when a class is absent, too sparse for
the declared claim, or represented only by an unverified synthetic assumption.

## Acceptance criteria

Aligned with Phase 2 Workstream 6:

- [x] The **source benchmark and development split** contain stable,
  semi-dynamic, and dynamic examples, with deterministic coverage counts
  recorded.
  - Held-out evaluates **stable reviewed class only** (Option A); semi/dynamic
    are absent on held-out and marked unavailable in artifacts.
- [x] At least three declared policy classes are replayed on the same workload.
  - Four policy arms on development; held-out runs frozen `conservative` only.
- [x] TTL policy and invalidation behavior are reported separately.
- [x] Dynamic queries cannot be served when dynamic reuse is disallowed.
- [x] Expired, missing-expiration, and invalid-expiration entries cannot be
  served.
- [x] Dynamic-short behavior, if enabled for the experiment, has a positive
  TTL and remains opt-in.
- [x] Reports include reuse, stale-exposure, latency, cost, token, storage,
  and eviction metrics or explicit unavailable states.
- [x] Metrics are stratified by freshness class and cache-control outcome.
- [x] Stale exposure is defined and is not conflated with blocked expiration.
- [x] Development policy selection is completed before held-out evaluation and
  uses no held-out labels.
- [x] Held-out results include constraint satisfaction for the selected policy.
- [x] Confidence intervals, sample counts, seed, and interval methods are
  attached using the Workstream 5 statistics contract.
- [x] Storage rows are aligned to policy/configuration and labeled by
  measurement environment.
- [x] Explicit invalidation is tested where supported or marked unavailable
  with consequences.
- [x] Synthetic replay and real-provider measurements remain separately
  labeled.
- [x] Serialization and redaction tests pass for freshness artifacts.
- [x] Completion evidence is linked from the Phase 2 parent plan.

## Completion evidence

Record in [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md):

- [x] freshness schema and policy-config versions;
- [x] benchmark, split, manifest, and class counts;
- [x] policy matrix with exact TTL values;
- [x] development selection artifact and selection rule;
- [x] held-out artifact and selected-policy constraint result;
- [x] stale-exposure definition, counts, and interval metadata;
- [x] invalidation artifact or an explicit unavailable record;
- [x] storage companion artifact and environment labels;
- [x] commands, dates, Python version, git commit, and dirty flag;
- [x] focused and full-suite test results;
- [x] skipped PostgreSQL/provider integrations;
- [x] limitations and their effect on Phase 2 conclusions.

Do not check an item based only on the presence of a plan or source file. Each
item requires code, test, artifact, or documented unavailability evidence.

## Handoff to later workstreams

**Workstream 5** consumes freshness-policy metrics, selected-policy constraints,
and intervals when updating the consolidated evaluation package.

**Workstream 7** consumes freshness-related failure categories and bounded
examples, especially served stale or disallowed dynamic cases.

**Workstream 8** may use selected TTL settings in restart and concurrency
tests, but owns operational behavior and capacity claims.

**Workstream 9** reads freshness artifacts for dashboard views and must not
recompute freshness metrics independently.

Handoff requirements:

- [x] Publish the freshness schema and policy-config versions.
- [x] Publish development and held-out freshness artifact paths.
- [x] Publish the selected policy and constraint result.
- [x] Publish freshness-class and cache-control outcome definitions.
- [x] Publish invalidation status and measurement environment.
- [x] Confirm no held-out policy tuning occurred.
- [x] Link completion evidence from
  `PHASE_2_IMPLEMENTATION_PLAN.md`.

## Execution sequence

1. [x] Audit current freshness behavior, coverage, and invalidation support.
2. [x] Freeze the freshness report schema and policy matrix.
3. [x] Add deterministic policy construction and replay time control.
4. [x] Implement development policy replay.
5. [x] Add stale-exposure and cache-control outcome metrics.
6. [x] Add interval and stratified freshness summaries.
7. [x] Test explicit invalidation or record it as unavailable.
8. [x] Pair policy arms with storage evaluation.
9. [x] Select and freeze the development policy.
10. [x] Generate freshness evaluation artifacts (development, held-out, invalidation).
11. [x] Run regression tests and generate completion artifacts.
12. [x] Update evidence, parent status, and downstream handoffs.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Dynamic class is sparse or absent | Publish class counts; mark class-specific intervals or claims unavailable. |
| Longer TTL inflates reuse while increasing stale exposure | Select constraint-first; report stale exposure separately from hit rate. |
| Expired candidates are mistaken for served stale answers | Count blocked expiration and served stale exposure as separate metrics. |
| Held-out labels tune policy values | Freeze policy matrix and development selection before held-out access; test artifact inputs. |
| Wall-clock timing makes replay nondeterministic | Inject a controlled comparison time at the replay boundary; test exact expiry. |
| Dynamic opt-in becomes an accidental default | Keep `allow_dynamic_entries` explicit and require positive dynamic TTL. |
| TTL deletion is mistaken for explicit invalidation | Report invalidation in a separate artifact and test sequence. |
| Storage results are reused across incompatible TTL arms | Run aligned storage companions or mark the plane unavailable. |
| Synthetic cost/latency is presented as provider evidence | Preserve `measurement_environment` and provider-unavailable fields. |
| Freshness metadata leaks raw query or answer content | Store bounded numeric/categorical summaries and run redaction tests. |
| New CLI duplicates Workstream 5 logic | Reuse existing evaluation/report/statistics helpers; add only a thin orchestration layer. |
| PostgreSQL behavior is inferred from in-memory tests | Label repository environment and defer restart/concurrency claims to Workstream 8. |
| Invalidation API scope expands the workstream | Test existing repository support only; require a separate requirement for a public endpoint. |
