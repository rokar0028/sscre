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

**In progress — Step 1 (audit) complete 2026-10-08**; see
[`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md). Workstream 5 exposes
freshness-class strata and cache-control outcomes, but no policy sweep or
freshness-specific held-out package has been completed. The audit found that
the held-out split has no semi-dynamic or dynamic pairs and that WS5 held-out
artifacts predate the current split manifest; both must be resolved before
Step 2.

Current known baseline:

- `stable`, `semi_dynamic`, and `dynamic` are represented in the benchmark
  schema and query metadata.
- `CacheControlPolicy` supports independent stable and semi-dynamic TTLs,
  optional dynamic TTLs, and a dynamic-entry allow switch.
- Reads fail closed for disabled dynamic entries, missing expiration, invalid
  expiration, and expired entries.
- In-memory and PostgreSQL repositories support deletion by query hash
  internally, but no independently specified public invalidation experiment
  protocol is frozen.
- Workstream 5 reports freshness strata, but its selected operating point does
  not compare alternative TTL policies.

Open status:

- [ ] Freeze the policy matrix and freshness-specific constraints.
- [ ] Validate or extend benchmark coverage for all three freshness classes.
- [ ] Add deterministic policy-sweep replay and stale-exposure accounting.
- [ ] Evaluate explicit invalidation where supported, or record it as
  unavailable with the reason.
- [ ] Produce development and held-out freshness artifacts.
- [ ] Link completion evidence from the Phase 2 parent plan.

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
| Policy replay | `src/sscre/freshness_evaluation.py` (planned; reuse existing replay helpers where practical) |
| Statistical attachment | `src/sscre/evaluation_statistics.py` |
| Storage companion | `src/sscre/storage_evaluation.py` |
| Freshness CLI | `src/sscre/freshness_evaluate.py` (planned only if existing CLI composition is insufficient) |
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
- [ ] No freshness policy sweep artifact exists.
- [ ] No stale-exposure metric or freshness-specific operating-point record
  exists.
- [ ] No frozen invalidation experiment protocol exists.
- [ ] No Workstream 6 completion evidence exists.

### Open baseline gaps

- [ ] Held-out has 0 semi-dynamic and 0 dynamic pairs (development: 5 and 4;
  Step 1 audit). Obtain held-out coverage or declare held-out freshness
  claims stable-only/unavailable.
- [ ] 9 development semi-dynamic/dynamic pairs are too few for interval-backed
  class claims; label results diagnostic unless coverage grows.
- [ ] Regenerate or annotate WS5 held-out artifacts, which predate the current
  split manifest.
- [ ] Decide whether reviewed `freshness_class` or runtime classifier defines
  policy strata (they disagree on 31/800 development queries).
- [ ] Add versioned freshness-policy configuration and schema metadata.
- [ ] Add deterministic time control or an equivalent clock boundary for
  replay.
- [ ] Capture stale-exposure and cache-control outcome samples without raw
  query or answer text in statistical attachments.
- [ ] Define storage pairing for each TTL arm and label synthetic storage
  simulation separately.
- [ ] Record invalidation as tested, unsupported, or not applicable; do not
  infer invalidation behavior from TTL deletion.

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
- [ ] Open decision before Step 2: how to obtain held-out freshness coverage
  (see evidence § Decisions needed).

### 2. Freeze the freshness experiment schema and policy config

Define a versioned machine-readable contract before replay.

Planned touch points:
`experiments/evaluation_config.json`,
`src/sscre/serialization.py`,
`src/sscre/evaluation_statistics.py`,
`tests/test_workstream6_freshness.py`.

- [ ] Add a freshness experiment schema version, for example
  `freshness-evaluation-1.0`.
- [ ] Define policy records with stable, semi-dynamic, and dynamic TTL values.
- [ ] Define `allow_dynamic_entries` and reject inconsistent dynamic settings.
- [ ] Define stale-exposure, dynamic-reuse, and freshness-violation fields.
- [ ] Define the selected-policy record and constraint result shape.
- [ ] Preserve report redaction and existing schema attachment behavior.
- [ ] Add validation for positive TTLs, finite metrics, and consistent policy
  names.

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

- [ ] Build policies through the existing `CacheControlPolicy` and `Settings`
  boundaries rather than duplicating TTL logic.
- [ ] Add a controlled comparison time or clock injection at the smallest
  existing boundary that permits deterministic replay.
- [ ] Ensure policy construction cannot create a dynamic policy without a
  positive dynamic TTL.
- [ ] Preserve timezone-aware expiration validation.
- [ ] Test exact-boundary behavior when `now == ttl_expires_at`.
- [ ] Test that a policy arm cannot mutate the next arm's cache state.

Do not alter production failure-closed semantics just to simplify replay.
Replay-only clock injection must be clearly separated from runtime defaults.

### 4. Implement freshness-policy replay

Replay the same reviewed records under each policy arm. Reuse Workstream 5
baseline observations and accounting rules where possible.

- [ ] Apply each policy to development records without changing labels.
- [ ] Apply the frozen selected policy to held-out records only after
  development selection is recorded.
- [ ] Keep cache state isolated per policy and per split.
- [ ] Record request-level numeric observations and bounded categorical counts.
- [ ] Preserve baseline identity and measurement environment.
- [ ] Ensure no expired, disabled, missing-expiration, or invalid-expiration
  candidate is served.
- [ ] Include exact and semantic paths where the baseline supports them.
- [ ] Keep no-cache behavior as a reference row.

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

- [ ] Reuse Workstream 5 interval methods and seed policy.
- [ ] Mark sparse or unavailable intervals explicitly.
- [ ] Keep synthetic replay and real-provider rows separately labeled.
- [ ] Ensure no raw queries, answers, credentials, or unrestricted traces are
  included in the statistical attachment.

### 6. Implement and test stale-exposure accounting

Use reviewed temporal metadata and controlled replay outcomes; do not invent
freshness labels from runtime behavior.

- [ ] Define the stale-exposure numerator and denominator in the contract.
- [ ] Count served stale or disallowed dynamic answers separately from blocked
  stale candidates.
- [ ] Test a controlled stale-answer fixture under long and short TTL arms.
- [ ] Test that blocked expiration is protection, not served stale exposure.
- [ ] Test that a fresh incompatible candidate is not counted as a freshness
  violation.
- [ ] Test missing and invalid expiration as safety failures, not successful
  reuse.
- [ ] Add deterministic interval tests for stale-exposure proportions.

If the benchmark does not provide enough reviewed stale-answer labels, publish
runtime freshness-protection metrics while marking answer-level stale exposure
as unavailable rather than substituting zero.

### 7. Evaluate explicit invalidation separately from TTL expiration

The plan must not conflate deletion with expiration.

- [ ] Document the existing `delete_by_query_hash` capabilities for in-memory
  and PostgreSQL repositories.
- [ ] Decide whether an explicit invalidation test can be run through an
  existing supported repository boundary.
- [ ] If supported, run a controlled sequence: insert, verify fresh reuse,
  invalidate, verify no reuse, regenerate, and verify replacement.
- [ ] Record invalidation latency, resulting storage count/bytes, and whether
  the invalidated entry can reappear through semantic retrieval.
- [ ] If unsupported, emit an explicit unavailable record with the repository,
  missing boundary, and consequence.
- [ ] Do not add a public invalidation endpoint as incidental scope.

The invalidation artifact must identify whether the result is synthetic
repository behavior, PostgreSQL integration behavior, or unavailable.

### 8. Pair storage evaluation with policy arms

Run storage evaluation for aligned policy configurations rather than reusing a
single footprint for all TTL policies.

- [ ] Pair each policy with an aligned storage configuration and dataset
  version.
- [ ] Measure entries, bytes, expired cleanup, and eviction counts.
- [ ] Distinguish lazy read rejection from physical deletion.
- [ ] Label storage rows `synthetic_storage_simulation` unless measured in a
  supported real environment.
- [ ] Add reuse-versus-storage points for policy arms where observations are
  aligned.
- [ ] Mark the plane unavailable when a matching storage run is not possible.

### 9. Select a development policy and freeze the held-out run

Use a predeclared constraint-first procedure.

- [ ] Run every policy arm on development.
- [ ] Write the selection record before reading held-out results.
- [ ] Verify the selection record does not contain held-out labels or outcomes.
- [ ] Run the selected policy on held-out with the benchmark frozen.
- [ ] Record held-out constraint satisfaction and all policy metrics.
- [ ] Retain non-selected policy rows only as development diagnostics unless
  the experiment contract explicitly permits held-out comparison.
- [ ] Record exact commands, config hashes, git identity, and test result.

### 10. Generate the freshness evaluation artifacts

Create machine-readable artifacts suitable for Workstream 9 without creating a
second analytics pipeline.

Planned artifacts:

- `artifacts/evaluation/workstream6-development-freshness.json`;
- `artifacts/evaluation/workstream6-held-out-freshness.json`;
- `artifacts/evaluation/workstream6-invalidation.json`, when supported;
- `docs/phase-2/WORKSTREAM_6_EVIDENCE.md`.

- [ ] Include policy matrix, selected policy, and constraint results.
- [ ] Include freshness-class and cache-control outcome breakdowns.
- [ ] Include statistics schema and interval metadata.
- [ ] Include storage companion references and environment labels.
- [ ] Include unavailable fields and their consequences.
- [ ] Make regeneration deterministic from checked-in config and commands.

### 11. Regression, serialization, and safety tests

- [ ] Add focused unit tests for policy construction and boundary times.
- [ ] Add replay tests for all three freshness classes.
- [ ] Add tests proving dynamic entries are not served by default.
- [ ] Add tests proving enabled dynamic entries respect their TTL.
- [ ] Add tests proving expired entries are never served.
- [ ] Add tests proving policy arms do not leak cache state.
- [ ] Add tests for stale-exposure and invalidation accounting.
- [ ] Add serialization/redaction tests for freshness artifacts.
- [ ] Confirm existing Workstream 3 freshness tests remain green.
- [ ] Run the full suite after substantive implementation changes.

### 12. Record evidence and update parent handoff

- [ ] Record implementation paths and schema versions.
- [ ] Record benchmark and split counts by freshness class.
- [ ] Record policy matrix and selected-policy rule.
- [ ] Record development and held-out commands and artifact paths.
- [ ] Record stale-exposure definitions and interval methods.
- [ ] Record invalidation result or explicit unavailable status.
- [ ] Record storage pairing and measurement environments.
- [ ] Record full-suite result and skipped integrations.
- [ ] Record limitations, especially sparse dynamic classes and missing
  real-provider measurements.
- [ ] Link `WORKSTREAM_6_EVIDENCE.md` from
  `PHASE_2_IMPLEMENTATION_PLAN.md`.

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

- [ ] The development and held-out workloads contain stable, semi-dynamic, and
  dynamic examples, with deterministic coverage counts recorded.
- [ ] At least three declared policy classes are replayed on the same workload.
- [ ] TTL policy and invalidation behavior are reported separately.
- [ ] Dynamic queries cannot be served when dynamic reuse is disallowed.
- [ ] Expired, missing-expiration, and invalid-expiration entries cannot be
  served.
- [ ] Dynamic-short behavior, if enabled for the experiment, has a positive
  TTL and remains opt-in.
- [ ] Reports include reuse, stale-exposure, latency, cost, token, storage,
  and eviction metrics or explicit unavailable states.
- [ ] Metrics are stratified by freshness class and cache-control outcome.
- [ ] Stale exposure is defined and is not conflated with blocked expiration.
- [ ] Development policy selection is completed before held-out evaluation and
  uses no held-out labels.
- [ ] Held-out results include constraint satisfaction for the selected policy.
- [ ] Confidence intervals, sample counts, seed, and interval methods are
  attached using the Workstream 5 statistics contract.
- [ ] Storage rows are aligned to policy/configuration and labeled by
  measurement environment.
- [ ] Explicit invalidation is tested where supported or marked unavailable
  with consequences.
- [ ] Synthetic replay and real-provider measurements remain separately
  labeled.
- [ ] Serialization and redaction tests pass for freshness artifacts.
- [ ] Completion evidence is linked from the Phase 2 parent plan.

## Completion evidence

Record in [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md):

- [ ] freshness schema and policy-config versions;
- [ ] benchmark, split, manifest, and class counts;
- [ ] policy matrix with exact TTL values;
- [ ] development selection artifact and selection rule;
- [ ] held-out artifact and selected-policy constraint result;
- [ ] stale-exposure definition, counts, and interval metadata;
- [ ] invalidation artifact or an explicit unavailable record;
- [ ] storage companion artifact and environment labels;
- [ ] commands, dates, Python version, git commit, and dirty flag;
- [ ] focused and full-suite test results;
- [ ] skipped PostgreSQL/provider integrations;
- [ ] limitations and their effect on Phase 2 conclusions.

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

- [ ] Publish the freshness schema and policy-config versions.
- [ ] Publish development and held-out freshness artifact paths.
- [ ] Publish the selected policy and constraint result.
- [ ] Publish freshness-class and cache-control outcome definitions.
- [ ] Publish invalidation status and measurement environment.
- [ ] Confirm no held-out policy tuning occurred.
- [ ] Link completion evidence from
  `PHASE_2_IMPLEMENTATION_PLAN.md`.

## Execution sequence

1. [x] Audit current freshness behavior, coverage, and invalidation support.
2. [ ] Freeze the freshness report schema and policy matrix.
3. [ ] Add deterministic policy construction and replay time control.
4. [ ] Implement development policy replay.
5. [ ] Add stale-exposure and cache-control outcome metrics.
6. [ ] Add interval and stratified freshness summaries.
7. [ ] Test explicit invalidation or record it as unavailable.
8. [ ] Pair policy arms with storage evaluation.
9. [ ] Select and freeze the development policy.
10. [ ] Run the held-out selected-policy evaluation.
11. [ ] Run regression tests and generate completion artifacts.
12. [ ] Update evidence, parent status, and downstream handoffs.

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
