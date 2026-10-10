# Phase 4 — Post-Phase 3 validation implementation plan

**Status:** `Step 5 complete — evidence package closed; clean-checkout replay deferred`  
**Owner:** Kartik  
**Parent:** [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § Phase 4  
**Source baseline:** [`PHASE3_IMPLEMENTATION_PLAN.md`](./PHASE3_IMPLEMENTATION_PLAN.md)  
**Scope source:** [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md), [`PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md), and [`SSCRE_PLAN.md`](../SSCRE_PLAN.md) § 20  
**Expected effort:** 2–6 focused sessions, depending on the approved validation tracks

## Scope note

The current transition document does not define a Phase 4 feature set. This plan
therefore treats Phase 4 as **post-Phase 3 validation**, not as an automatic
expansion of the cache architecture. The approved execution completed the
protocol follow-up, bounded local profiling, and release/evidence audit. Live
provider execution remains unavailable and deferred.

**Exit:** every approved track has a written protocol, reproducible evidence,
updated limitations, and passing regression checks. Unapproved tracks remain
explicitly deferred.

## Learning objectives

- [ ] Distinguish a protocol-reset experiment from a continuation of the Phase 3
  single-held-out evaluation.
- [ ] Separate synthetic replay claims from live-provider cost, token, and latency
  claims.
- [ ] Identify a measured storage, throughput, or dependency bottleneck before
  selecting infrastructure.
- [ ] Report negative or inconclusive results without turning them into product
  claims.

## Non-negotiable gates

- [x] Obtain explicit written approval for the selected Phase 4 tracks and their
  pass/fail criteria before code or external-service work.
- [x] Create a feature branch from the reviewed Phase 3 baseline; do not commit to
  `main` or push without explicit approval.
- [x] Read the Phase 3 final evidence and current benchmark/evaluation contracts
  before changing evaluation or cache behavior.
- [x] Treat any new held-out evaluation as a new protocol: record the reason,
  dataset version, split, seed, config hash, and reset decision before running it.
- [x] Never combine synthetic-replay and live-provider numbers in one result table.
- [x] Do not rent a GPU or add a provider dependency until profiling shows that it
  is required by an approved experiment.
- [x] Preserve fail-closed behavior, validation, authorization, tenancy checks,
  accessibility, and data-loss protections while making operational changes.

## Phase 4 decision gate

Phase 4 has no implementation authorization until the following choices are
recorded in this plan:

- [x] Select the **protocol follow-up** track for the deferred selected-stack
  Pareto curve.
- [x] Select the **live-provider validation** track only if real cost, token,
  rate-limit, or network-latency claims are needed.
- [x] Select the **scale/storage profiling** track only if a capacity,
  storage-footprint, quantization, or bottleneck claim is needed.
- [x] Select the **release/readiness** track only if a public export or reviewer
  handoff is part of the deliverable.
- [x] Confirm the final order and whether any track is explicitly deferred.

**Recorded decision (2026-10-10):** execute `P4-PARETO`, then approve the
bounded `P4-SCALE` and `P4-RELEASE` tracks. Attempt `P4-PROVIDER` only through
the fail-closed measurement boundary; no credentialed run was available.

## Prerequisites (read-only)

- [x] Phase 3 final evidence is reviewed:
  [`PHASE3_FINAL_EVIDENCE.md`](../phase-3/PHASE3_FINAL_EVIDENCE.md).
- [x] The retained stack is confirmed as Feature 1 adaptive thresholds with
  default/WS6-conservative eviction; Feature 2 and Strategy D remain deferred.
- [x] The Phase 3 selected-stack Pareto deferral is understood as a protocol
  decision, not a missing implementation.
- [x] Existing development and held-out artifacts are inventoried under
  `artifacts/evaluation/`.
- [x] Current repository status, branch, Python version, and declared development
  dependencies are recorded before implementation.
- [x] Phase 4 work is on `phase4/setup`, created from the Phase 3 implementation
  baseline without staging or discarding pre-existing changes.
- [x] No external provider or compute budget was used. Any future provider or
  compute budget must be approved outside the repository and excluded from
  artifacts.

## Step 0 — Branch, baseline, and protocol reset

**Track ID:** `P4-SETUP`

- [x] Create a Phase 4 feature branch from the reviewed Phase 3 baseline.
- [x] Record base commit, branch, Python/dependency environment, and working-tree
  status in the completion record.
- [x] Install declared development dependencies:
  `python -m pip install ".[dev]"`.
- [x] Run and record baseline checks before changes:
  - [x] `python -m pytest -q`
  - [x] `python -m sscre.benchmark_validate --phase2 --production`
  - [x] `docker compose config` with the non-secret CI sample environment
- [x] Record the Phase 3 artifact manifest, config hash, dataset version, split
  manifest hash, and retained-stack configuration.
- [x] For every selected track, write the workload, hypothesis, primary metric,
  pass/fail criterion, stopping rule, and artifact names before running it.
- [x] If a new held-out run is selected, append a protocol-reset record before
  accessing held-out outcomes.

## Step 1 — Protocol follow-up: reference Pareto and retained adaptive point

**Track ID:** `P4-PARETO` · **Default order:** 1 · **Effort:** S–M

### Purpose

Complete the explicitly deferred reference Pareto curve and attach the retained
adaptive-stack point without silently claiming that this is a full adaptive
threshold curve or that it belongs to the original Phase 3 single-held-out
protocol.

### Protocol

- [x] Define the curve as a **new held-out follow-up protocol**, not a
  continuation of the Phase 3 single final run.
- [x] Record a written protocol reset and treat all
  resulting numbers as Phase 4 evidence.
- [x] Freeze the retained Phase 3 stack, including the adaptive threshold map,
  default eviction, conservative freshness policy, and evaluation configuration.
- [x] Do not retune thresholds, eviction rules, or Strategy D using the new
  held-out results.
- [x] Use the same safety semantics and statistics configuration unless the
  protocol explicitly records a justified change.

**Protocol reset record:** The original Phase 3 final held-out comparison was
already consumed once. This Phase 4 run is a separately labelled follow-up that
replays the frozen development threshold grid on held-out data for the global
Strategy C reference curve and attaches the already-frozen Feature 1 adaptive
stack point from the Phase 3 final comparison. No threshold, eviction, or
Strategy D tuning is performed from Phase 4 held-out outcomes.

### Pass/fail criterion

- [x] Pass only if the generated reference curve and retained adaptive point
  contain complete configuration and provenance metadata and do not violate the
  declared safety constraint.
- [x] If the curve is incomplete, unstable, or requires post-hoc tuning, publish
  it as diagnostic-only and retain the Phase 3 selected-stack result.

### Evidence

- [x] `artifacts/evaluation/phase4-selected-stack-pareto.json`
- [x] `docs/phase-4/PHASE4_PARETO_EVIDENCE.md`
- [x] A command, commit, config hash, dataset/split metadata, seed, timestamp,
  and protocol-reset decision.

## Step 2 — Optional track: live-provider validation

**Track ID:** `P4-PROVIDER` · **Order:** only if approved · **Effort:** M–L
**Status:** attempted; unavailable without credentialed provider configuration

### Hypothesis

A small, separately labelled run against the target provider produces usable
real-world token, cost, rate-limit, and network-latency measurements while
preserving the qualitative safety decision observed under synthetic replay.

### Scope and safeguards

- [ ] Name the provider, model versions, region, request limits, and observation
  window before the run.
- [ ] Use a small fixed workload; do not present it as a production capacity test.
- [ ] Keep credentials in the environment or secret manager; never write them to
  source, logs, galleries, or artifacts.
- [ ] Record retries, failures, rate limits, token usage, cost, p50/p95 latency,
  and the exact synthetic/live boundary.
- [ ] Keep provider results in separate artifacts and tables from synthetic
  replay results.
- [x] Stop if cost, rate limits, or provider instability prevents a representative
  measurement; report the limitation instead of substituting estimates.

### Pass/fail criterion

- [ ] Pass only if the run is reproducible enough to support a clearly labelled
  provider-observation claim with complete provenance.
- [ ] This track does not change the retained cache policy by itself.

### Evidence

- [x] `artifacts/evaluation/phase4-provider-validation.json` (sanitized)
- [x] `docs/phase-4/PHASE4_PROVIDER_EVIDENCE.md`
- [x] A limitation stating workload size and why the result is not a capacity
  or general-provider claim.

## Step 3 — Optional track: storage and bounded-scale profiling

**Track ID:** `P4-SCALE` · **Order:** only if approved · **Effort:** M–L
**Status:** completed with existing deterministic local tooling; no production
optimization selected

### Hypothesis

Measured storage and bounded workload profiling identifies the first practical
resource bottleneck and determines whether quantization or a targeted
optimization is justified.

### Scope

- [x] Define the workload size, concurrency model, hardware, database mode, and
  success thresholds before measurement.
- [x] Measure cache entries, embedding bytes, answer bytes, metadata bytes,
  total storage, hit/miss latency, eviction behavior, and failure modes.
- [x] Use the bounded existing synthetic load profile: 32 requests, 8 warmup
  requests, concurrency 4, in-memory storage, and four cache strategies.
- [x] If load testing is approved, use bounded steps and stop at the first
  reproducible bottleneck; do not imply 1K–100K Q/day support without that
  workload being run.
- [x] Record the float32 storage baseline before considering quantization.
- [x] Compare quality/safety and retrieval behavior before and after any
  representation change.
- [x] Do not rent a GPU or add infrastructure unless the profile demonstrates that local
  CPU or existing services are the bottleneck.

**Frozen protocol (2026-10-10):** storage uses the existing four-item
`experiments/storage_controls_development.json` workload with
`max_entries=10`, `max_bytes=100000`, and synthetic generation latency of
`100 ms`; bounded scale uses
`experiments/milestone10_load_v1.json` with 32 requests, 8 warmups,
concurrency 4, max 8 entries, and max 10000 bytes. Both runs use local CPU,
in-memory storage, deterministic fake providers, and no PostgreSQL or GPU.
No quality/safety representation change was proposed, so no quantization
comparison was run.

### Pass/fail criterion

- [x] Pass only if the bottleneck is reproducible and the proposed mitigation
  improves the pre-registered metric without violating safety or correctness.
- [x] If no bottleneck is found, document the tested range and defer
  optimization rather than adding infrastructure.

### Evidence

- [x] `artifacts/evaluation/phase4-storage-profile.json`
- [x] `artifacts/evaluation/phase4-scale-profile.json`
- [x] `docs/phase-4/PHASE4_SCALE_EVIDENCE.md`

## Step 4 — Optional track: release and handoff readiness

**Track ID:** `P4-RELEASE` · **Order:** after selected tracks · **Effort:** S–M

- [x] Audit documentation links, artifact manifests, commands, and limitations
  against the final Phase 4 evidence.
- [x] Confirm generated artifacts exclude credentials, local absolute paths where
  inappropriate, and unexplained machine-specific state.
- [x] Run the documented verification sequence from the current environment;
  clean-checkout replay remains deferred even though Step 3 changes are now
  committed locally, because the replay has not been run.
- [x] Add only the minimum release/readiness documentation needed for the
  approved handoff; do not add dashboards, tracking infrastructure, or product
  features without a measured requirement.
- [x] Record known gaps: provider scope, labels, operations, workload range, and
  any protocol-reset results.

## Step 5 — Evidence package and final verification

**Track ID:** `P4-ARTIFACTS`

- [x] Generate a machine-readable manifest for every approved track:
  `artifacts/evaluation/phase4-paper-artifact-manifest.json`.
- [x] Ensure each applicable result has a command, code commit, configuration hash, dataset
  version, split manifest, seed, timestamp, and environment details.
- [x] Update the relevant Phase 4 evidence document after each track, not only at
  close.
- [x] Update the Phase 3 transition document only after the Phase 4 scope and
  evidence are approved.
- [x] Run `python -m pytest -q` after implementation.
- [x] Run `python -m sscre.benchmark_validate --phase2 --production`.
- [x] Run `docker compose config` with the non-secret sample environment.
- [x] Review the final diff and confirm no unapproved external writes, commits, or
  pushes occurred.

## Acceptance criteria

- [x] Phase 4 scope and selected tracks are approved in writing.
- [x] Every selected track has a written hypothesis, protocol, pass/fail
  criterion, stopping rule, and evidence path.
- [x] Any held-out follow-up is clearly labelled as a new protocol or explicitly
  avoided.
- [x] Synthetic and live-provider results are not mixed.
- [x] Storage or scale claims are limited to the measured workload and hardware.
- [x] Regression tests and validation commands pass, with skips and warnings
  recorded.
- [x] Limitations and documentation match the actual evidence.
- [x] No GPU, provider dependency, dashboard, experiment tracker, or unrelated
  product scope was added without approval.
- [ ] Separate approval is requested before committing or pushing.

## Completion record

_Date started:_ 2026-10-10  
_Date completed:_  

### Approval and branch

**Approved tracks:** `P4-PARETO` complete; `P4-PROVIDER` attempted and unavailable;
`P4-SCALE` complete; `P4-RELEASE` complete with clean-checkout replay deferred
**User approval date / message:** Phase 4 Steps 0–5 implementation requested in chat on 2026-10-10
**Branch:** `phase4/setup`  
**Base commit:** `8c65926227fbdc923a23994c183ac33ba378694f`  
**Merge / PR:** [PR #1](https://github.com/rokar0028/sscre/pull/1)  
**PR sync:** PR #1 currently ends at `dc451fe`; later documentation/artifact
commits are local and require a separate push approval.

**Working tree at setup:** pre-existing Phase 3 implementation, artifact, and
documentation changes retained; nothing staged or discarded by Step 0.  
**Environment:** Python 3.14.5; pip 26.1.2; development dependencies installed  
**Phase 3 baseline artifact/config hashes:** dataset
`reviewed-query-pairs-2.0`; split manifest SHA-256
`68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51`;
evaluation config SHA-256
`5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8`;
retained stack is Feature 1 adaptive thresholds with default/WS6-conservative
eviction.  
**Protocol reset decision:** required for P4-PARETO and recorded; bounded local
profiling used existing synthetic workloads and did not access held-out data

### Track decisions

| Track | Status | Evidence | Decision |
| --- | --- | --- | --- |
| `P4-PARETO` | complete | `docs/phase-4/PHASE4_PARETO_EVIDENCE.md` | complete; diagnostic follow-up |
| `P4-PROVIDER` | unavailable | `docs/phase-4/PHASE4_PROVIDER_EVIDENCE.md` | deferred; no credentialed run |
| `P4-SCALE` | complete | `docs/phase-4/PHASE4_SCALE_EVIDENCE.md` | no optimization trigger |
| `P4-RELEASE` | complete | `docs/phase-4/PHASE4_RELEASE_EVIDENCE.md` | clean-checkout replay deferred |
| `P4-ARTIFACTS` | complete | `artifacts/evaluation/phase4-paper-artifact-manifest.json` | complete with documented deferrals |

## Verification log

| Step | Command / action | Date | Result |
| --- | --- | --- | --- |
| P4-SETUP | Scope and protocol review | 2026-10-10 | Phase 4 tracks remain approval-gated; Step 0 authorized |
| P4-SETUP | `git switch -c phase4/setup` | 2026-10-10 | created at `8c659262`; pre-existing changes retained |
| P4-SETUP | `python -m pip install ".[dev]"` | 2026-10-10 | completed |
| P4-SETUP | `python -m pytest -q` | 2026-10-10 | **659 passed**, 15 skipped, 1 warning |
| P4-SETUP | `python -m sscre.benchmark_validate --phase2 --production` | 2026-10-10 | passed; split manifest `68912e3b…` |
| P4-SETUP | `docker compose config` with sample environment | 2026-10-10 | passed with CI-style sample secrets |
| P4-PARETO | `python -m sscre.pareto ... --output artifacts/evaluation/phase4-selected-stack-pareto.json` | 2026-10-10 | passed; reference curve generated and retained adaptive point attached |
| P4-PROVIDER | `python -m sscre.provider_measure ... --output artifacts/evaluation/phase4-provider-validation.json` | 2026-10-10 | unavailable; `live_opt_in_missing`; no remote call |
| P4-SCALE | `python -m sscre.storage_evaluation ...`; `python -m sscre.load_test ...` | 2026-10-10 | complete; no optimization trigger |
| P4-RELEASE | Documentation, artifact, link, and redaction audit | 2026-10-10 | passed; current-environment verification; clean-checkout replay deferred |
| P4-ARTIFACTS | Phase 4 manifest generation and provenance validation | 2026-10-10 | passed; 4 track entries and 4 artifacts |
| P4-CLOSE | Final regression and evidence review | 2026-10-10 | passed; full suite, benchmark validation, and Compose config |

## Verification gate

- [x] Completion record is filled with no unexplained TBDs.
- [x] Evidence paths and commands agree with the recorded artifacts.
- [x] Parent transition documentation reflects the approved Phase 4 status.
- [ ] Commit/push approval is obtained separately from implementation approval.
