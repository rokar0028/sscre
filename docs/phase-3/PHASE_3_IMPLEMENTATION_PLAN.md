# SSCRE Phase 3 Implementation Plan

## Goal

Test the advanced items in the SSCRE master plan only where a written
hypothesis and pass/fail criterion justify them, and record each result —
including negative and deferred results — as reproducible evidence.

Phase 3 is a hypothesis-driven milestone. A feature ships only if it improves
a pre-registered metric without violating the safety constraint
(`max_false_positive_rate = 0.0`). Rejected or untriggered features are
reported, not hidden.

**Status:** `partially complete` — Phase 3 **v1 stack** closed (2026-10-10);
**Workstream 1 registry** closed (2026-10-11). Features 4–8 are **card-ready**
in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md); WS5–8 **execution** (artifacts, code)
and Workstream 9 master-plan sync remain open.

## Source of truth

- Scope: Phase 3 section of [`docs/SSCRE_PLAN.md`](../SSCRE_PLAN.md) § 20.
- Feature cards (hypotheses, protocols, pass/fail) for v1:
  [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- v1 execution record:
  [`../internal/PHASE3_IMPLEMENTATION_PLAN.md`](../internal/PHASE3_IMPLEMENTATION_PLAN.md).
- Transition gates and resource rules:
  [`../internal/PHASE3_TRANSITION.md`](../internal/PHASE3_TRANSITION.md).
- Post-Phase 3 validation (Pareto follow-up, bounded profiling):
  [`../internal/PHASE4_IMPLEMENTATION_PLAN.md`](../internal/PHASE4_IMPLEMENTATION_PLAN.md).

This document maps every master-plan Phase 3 item to a workstream. Feature
hypotheses and pass/fail criteria live in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
New scope requires a new card there and a Workstream 1 reopen before code.
Features 4–8 cards were promoted 2026-10-11 ([`WORKSTREAM_1_STEP7_CLOSE.md`](./WORKSTREAM_1_STEP7_CLOSE.md)).

## Learning objectives

- [ ] Pre-register a hypothesis and stopping rule before touching code.
- [ ] Tune on development data without leaking held-out outcomes.
- [ ] Explain when a cross-encoder validator is justified by a measured
  safety shortfall rather than architecture preference.
- [ ] Measure embedding storage and reason about quantization accuracy loss.
- [ ] Design a time-compressed load ladder and identify a first bottleneck.
- [ ] Group recurring failures without inventing categories.
- [ ] Decide when manual artifacts stop being enough and tracking is needed.

## Current baseline

- [x] Strategies A (`no-cache`), exact cache, B (`embedding-cache`), and C
  (`compatibility-cache`) are frozen; Strategy C global τ `0.95` was selected
  on development only ([`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Baselines frozen).
- [x] Dataset `reviewed-query-pairs-2.0`: 400 development / 215 held-out /
  615 source; split manifest SHA-256 `68912e3b…`.
- [x] Every v1 feature has a hypothesis and pass/fail criterion
  ([`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature cards).
- [x] Adaptive per-domain thresholds passed
  ([`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md)).
- [x] Pattern-aware eviction failed its reuse criterion and is deferred
  ([`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md)).
- [x] Strategy D was not triggered: retained-stack held-out FPR `0.0`
  ([`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md)).
- [x] Single final held-out package recorded
  ([`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md)): Strategy B FPR
  `0.4815`, Strategy C + Feature 1 FPR `0.0`, hit rate `0.0023`.
- [x] Selected-stack Pareto follow-up recorded under a Phase 4 protocol reset
  ([`../phase-4/PHASE4_PARETO_EVIDENCE.md`](../phase-4/PHASE4_PARETO_EVIDENCE.md)).
- [x] Bounded in-memory storage and load profile recorded (32 requests,
  concurrency 4; no bottleneck)
  ([`../phase-4/PHASE4_SCALE_EVIDENCE.md`](../phase-4/PHASE4_SCALE_EVIDENCE.md)).
- [ ] A float32 embedding-bytes baseline at benchmark scale is recorded.
- [ ] An int8 (or `halfvec`) quantization comparison exists.
- [ ] A 1K→100K simulated Q/day load ladder has been run.
- [ ] Recurring failures are clustered.
- [ ] An experiment-tracking decision is recorded with evidence.

Open baseline gaps that limit every Phase 3 claim: synthetic replay only (no
live provider), sparse human correctness labels, held-out freshness scope is
stable-only, and the Strategy C hit rate is very low, so reuse improvements
have little headroom.

## Phase 3 definition of done

Each row maps one item in `SSCRE_PLAN.md` § 20 Phase 3.

- [x] A hypothesis and pass/fail criterion exist for every implemented feature.
  - [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) Features 1–3 (authoring closed 2026-10-09).
- [x] Cross-encoder validator (D) is implemented only if C misses the target.
  - Not implemented; trigger (held-out FPR `> 0.0`) did not fire.
- [x] Validator latency and safety improvement are compared, or the comparison
  is documented as not applicable.
  - Not applicable while D is untriggered (Workstream 4).
- [ ] Embedding storage is measured before quantization (Workstream 5).
- [ ] int8 embedding quantization is tested against a float32 reference
  (Workstream 5).
- [ ] Load tests run from 1K to 100K simulated queries/day (Workstream 6).
- [ ] The first bottleneck is identified or the tested range is documented as
  bottleneck-free (Workstream 6).
- [x] Adaptive thresholds by domain are tested.
  - Feature 1 passed (Workstream 2).
- [ ] Recurring failures are clustered (Workstream 7).
- [ ] Experiment tracking is added only if manual reports are insufficient,
  with the decision recorded (Workstream 8).
- [ ] `SSCRE_PLAN.md` § 20 Phase 3 checkboxes are synced with this plan
  (Workstream 9).

## Workstream 1 — Hypothesis registry and gates

Status: **closed (registry)** — 2026-10-11 ([`WORKSTREAM_1_STEP7_CLOSE.md`](./WORKSTREAM_1_STEP7_CLOSE.md)).
Reopens for every **new** feature card only.

Implementation plan:
[`WORKSTREAM_1_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_1_IMPLEMENTATION_PLAN.md).
Evidence:
[`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md).

Rules that apply to every workstream below:

- Write the hypothesis, primary metric, pass/fail criterion, stopping rule,
  and artifact names in `PHASE3_PLAN.md` before code.
- Tune on `benchmarks/development.jsonl` only.
- Any held-out access after the Phase 3 final run requires a written protocol
  reset recording the reason, dataset version, split, seed, and config hash.
- Never mix synthetic-replay and live-provider numbers in one table.
- Do not rent a GPU or add a provider/dependency unless profiling for an
  approved experiment shows it is required.
- Preserve fail-closed behavior: `UNCERTAIN` and dependency failures never
  produce a cache hit.

Acceptance criteria:

- [x] v1 Features 1–3 cards complete (hypothesis, pass/fail, protocols). Residual
      `TBD` / `_pending_` strings are only in deferred Strategy D evidence stubs,
      the post-audit Feature 5 decision table, and superseded runbook notes — not
      in Features 4–8 card bodies ([`WORKSTREAM_1_STEP7_CLOSE.md`](./WORKSTREAM_1_STEP7_CLOSE.md)).
- [x] Strategy D stopping rule is documented.
- [x] Cards exist for Workstreams 5–8 before implementation (Features 4–8).

## Workstream 2 — Adaptive per-domain thresholds

Status: **passed** (2026-10-10). Card: [`PHASE3_PLAN.md`](./PHASE3_PLAN.md)
Feature 1. Evidence:
[`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md).

Hypothesis: development-selected τ per `metadata.domain` increases Strategy C
`hit_rate` versus global `0.95` without held-out FPR above `0.0`.

Acceptance criteria:

- [x] Threshold map keyed by domain, with `unknown` and small-stratum fallback
  to `0.95` (`src/sscre/baseline.py`, `src/sscre/evaluate.py`).
- [x] Tests cover lookup, fallback, malformed config, and safety
  (`tests/test_adaptive_thresholds.py`).
- [x] Map frozen before held-out:
  `artifacts/evaluation/phase3-adaptive-threshold-map.json`.
- [x] One held-out replay: hit rate `0.0023` vs `0.0`, FPR `0.0`
  (`artifacts/evaluation/phase3-adaptive-held-out.json`).

## Workstream 3 — Pattern-aware eviction

Status: **failed; deferred from the shipped stack** (2026-10-10). Card:
[`PHASE3_PLAN.md`](./PHASE3_PLAN.md) Feature 2. Evidence:
[`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md).

Hypothesis: evicting lower-`hit_count` entries first within each
`freshness_class` increases reuse versus WS6 `conservative` under a forced
entry cap, without stale exposure or FPR above `0.0`.

Acceptance criteria:

- [x] Eviction priority implemented and tested (`src/sscre/cache.py`,
  `src/sscre/phase3_eviction.py`, `tests/test_cache_eviction.py`).
- [x] Policy and `entry_cap=1` frozen on development
  (`artifacts/evaluation/phase3-pattern-eviction-policy.json`).
- [x] One held-out replay: reuse equal to the same-cap reference, so the pass
  criterion failed (`artifacts/evaluation/phase3-held-out-eviction.json`).
- [x] Shipped stack keeps default eviction; no held-out retuning.

## Workstream 4 — Strategy D validator gate

Status: **deferred by gate** (2026-10-10). Card:
[`PHASE3_PLAN.md`](./PHASE3_PLAN.md) Feature 3. Evidence:
[`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md).

Trigger: final Phase 3 stack held-out FPR `> 0.0`. Observed: `0.0`.

If the trigger ever fires (for example, after a benchmark expansion), the card
already defines the protocol: deterministic fake cross-encoder first,
development-only threshold tuning with hit rate no more than 5 points below
C, validator p95 ≤ `10 ms` on synthetic replay, one held-out replay after a
written protocol reset.

Acceptance criteria:

- [x] Trigger evaluated on the final stack and recorded.
- [x] No validator code, telemetry fields, or extra held-out run added.
- [ ] If the trigger fires: add validator telemetry fields to the
  serialization contract before implementation, then follow the card.

## Workstream 5 — Embedding storage baseline and quantization

Status: **ready for execution** (cards promoted 2026-10-11). Feature cards:
[`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Features 6–7 (`P3-FEAT-EMBED-BASE`,
`P3-FEAT-Q8` conditional).
Plan: [`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md).
Evidence: [`PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md).

Master-plan items: measure embedding storage before quantization; test int8 only
if dominance gate (`embedding_share` ≥ **0.20**) passes.

### 5.1 Float32 baseline (measure first)

Run the existing storage path over the full development split, not the
four-request Phase 4 workload. Record separately:

- entries, `embedding_bytes`, `answer_bytes`, `metadata_bytes`, total bytes
- bytes per entry and the embedding share of total bytes
- embedding dimension and dtype for the configured provider

Reuse `src/sscre/storage_evaluation.py` and the byte fields already defined in
`src/sscre/config.py`, `src/sscre/cache.py`, and `src/sscre/cache_controls.py`.

Stopping rule: if embeddings are a small share of total bytes, record the
baseline and defer quantization — the storage win would not matter.

### 5.2 Quantization comparison (only if 5.1 justifies it)

Proposed hypothesis (confirm before code): symmetric per-vector int8
quantization reduces embedding bytes by at least 3.5× versus float32 while
leaving Strategy C development decisions unchanged.

- Implement quantize/dequantize at the application boundary for the in-memory
  replay first; do not change the PostgreSQL schema in this slice.
- If PostgreSQL storage is later in scope, compare pgvector `halfvec`
  (float16) before any custom int8 column, because pgvector has no native int8
  vector type.
- Compare on development only: per-pair decision agreement, `hit_rate`,
  FPR, similarity-score drift (max and p95 absolute difference), and bytes.

Proposed pass/fail:

- **Pass** iff embedding bytes fall by ≥ 3.5×, development FPR stays `0.0`,
  and development `hit_rate` is not lower than the float32 reference.
- **Fail:** keep float32; report the measured drift and bytes.

Limitation to record: deterministic fake embeddings do not represent real
embedding distributions, so a pass supports a storage claim, not a general
accuracy claim, until a real-provider embedding run exists.

Acceptance criteria:

- [x] Card (hypothesis, metric, pass/fail, stopping rule) added to `PHASE3_PLAN.md`.
- [ ] Float32 development-scale baseline recorded:
  `artifacts/evaluation/phase3-embedding-storage-baseline.json`.
- [ ] Quantization comparison recorded, or deferral justified by 5.1:
  `artifacts/evaluation/phase3-quantization-development.json`.
- [ ] Unit tests cover round-trip error bounds, dimension preservation, and
  failure-closed behavior on malformed vectors.
- [ ] Evidence: `docs/phase-3/PHASE3_QUANTIZATION_EVIDENCE.md`.

## Workstream 6 — Load ladder and first bottleneck

Status: **ready for execution** (card promoted 2026-10-11). Feature card:
[`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 8 (`P3-FEAT-LOAD`).
Plan: [`WORKSTREAM_6_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_6_IMPLEMENTATION_PLAN.md).
Evidence: [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md).

Master-plan items: 1K→100K simulated Q/day ladder; first bottleneck or
`not_reached` with pre-registered budgets.

Prior evidence is bounded and must not be reused as this result: Phase 4
in-memory profile (32 requests) and WS8 PostgreSQL load (32 requests,
`not_reached`).

### 6.1 Workload

- Ladder: 1K, 10K, and 100K simulated queries per day. 100K/day averages about
  1.16 requests/second, so each step can be replayed time-compressed; record
  the compression factor and the peak concurrency used.
- Query mix drawn from development pairs with a recorded repeat ratio, so
  cache hits occur at a known rate.
- Run in-memory first, then PostgreSQL + pgvector with the same workload.
- Extend `src/sscre/load_test.py` and a new config next to
  `experiments/milestone10_load_v1.json` / `workstream8_pg_load_v1.json`;
  do not add a load-testing framework unless the existing harness cannot
  produce the ladder.

### 6.2 Measurements

Per step and per component (embed, vector search, compatibility check,
repository write, generation): p50/p95/p99 latency, throughput, error and
timeout counts, entries, bytes, evictions, and database connection usage.

### 6.3 Bottleneck rule

Pre-register before running: a component is the first bottleneck when it is
the largest contributor to p95 at the first ladder step where p95 latency or
error rate exceeds the written budget. Budgets must be recorded in the card
before the run.

Stopping rule: stop at the first reproducible bottleneck (two runs agree).
If none is reached at 100K/day, record the tested range as bottleneck-free on
that hardware and stop — do not optimize or add infrastructure.

Acceptance criteria:

- [x] Card with ladder, budgets, and stopping rule added to `PHASE3_PLAN.md`.
- [ ] In-memory ladder recorded:
  `artifacts/operations/phase3-load-ladder-memory.json`.
- [ ] PostgreSQL ladder recorded, or explicitly marked unavailable:
  `artifacts/operations/phase3-load-ladder-postgres.json`.
- [ ] First bottleneck named with component evidence, or `not_reached` with
  the tested range.
- [ ] Storage stays within the configured cap at every step (master-plan
  success criterion 7).
- [ ] Environment (OS, CPU, Python, PostgreSQL version, worker count) recorded;
  results labeled as synthetic and not a production SLA.
- [ ] Evidence: `docs/phase-3/PHASE3_LOAD_EVIDENCE.md`.

## Workstream 7 — Failure clustering

Status: **ready for execution** (card promoted 2026-10-11). Feature card:
[`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 4 (`P3-FEAT-CLUSTER`).
Plan: [`WORKSTREAM_7_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_7_IMPLEMENTATION_PLAN.md).

Inputs (no new replay needed):

- `artifacts/evaluation/phase3-final-held-out-comparison.json`
- WS7 consolidated quality analysis (`src/sscre/failure_quality.py`,
  `src/sscre/failure_gallery.py`)
- development reports, for clusters with too few held-out examples

Approach:

1. Group Strategy B false positives and Strategy C `UNSAFE`/`UNCERTAIN`
   decisions by existing failure category, rule fired, domain, and freshness
   class.
2. Name recurring patterns only when at least the documented minimum number of
   examples share them; list everything else as singletons.
3. For each cluster, record a candidate mitigation and whether it needs a new
   rule, benchmark pairs, or nothing.

Add clustering code only if manual grouping cannot be regenerated from a
documented command.

Acceptance criteria:

- [ ] Every Strategy B held-out false positive is assigned to a cluster or a
  singleton.
- [ ] Cluster counts trace to report fields, not hand-counted text.
- [ ] Output redacted with the existing report redaction path; no unapproved
  raw query text.
- [ ] Evidence: `docs/phase-3/PHASE3_FAILURE_CLUSTERS.md`.

## Workstream 8 — Experiment-tracking decision

Status: **ready for execution** (card promoted 2026-10-11). Feature card:
[`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 5 (`P3-FEAT-TRACK`).
Plan: [`WORKSTREAM_8_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_8_IMPLEMENTATION_PLAN.md).
Evidence: [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) (audit pending).

Hypothesis to test: manual artifacts are insufficient for reproducibility (audit
refutes or confirms).

Check, without adding a dependency:

- [ ] Every Phase 3 and Phase 4 result has command, commit, config hash,
  dataset version, split manifest, and seed in its artifact or evidence file.
- [ ] The Phase 3 and Phase 4 artifact manifests resolve every referenced path.
- [ ] Count results whose provenance cannot be reconstructed.

Pass/fail:

- **Keep manual** if every result is reconstructable.
- **Add tracking** only if at least one result cannot be reconstructed and a
  manifest fix is not enough; record the tool choice and why.

Acceptance criteria:

- [ ] Decision and audit counts recorded in `PHASE3_PLAN.md`.
- [ ] No tracker dependency added without a failed audit.

## Workstream 9 — Final package and plan sync

Status: **partially complete**. v1 final package closed 2026-10-10.

Acceptance criteria:

- [x] Single final held-out run with commit, config hash, dataset version,
  split-manifest hash, seed, and timestamp
  ([`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md)).
- [x] Ablations, domain threshold curves, freshness/eviction slice, and gallery
  under `artifacts/evaluation/phase3-*`
  ([`PHASE3_ARTIFACTS_EVIDENCE.md`](./PHASE3_ARTIFACTS_EVIDENCE.md)).
- [x] Selected-stack Pareto recorded as a separately labeled Phase 4 follow-up.
- [ ] Results from Workstreams 5–8 added to the artifact manifest.
- [ ] Limitations updated with quantization, load, and clustering outcomes.
- [ ] `SSCRE_PLAN.md` § 20 Phase 3 checkboxes synced with evidence links.
- [ ] `docs/phase-3/README.md` status line updated.
- [ ] Full suite, benchmark validation, and compose config pass after the
  last workstream.

## Recommended execution order

1. [x] Write v1 feature cards and gates (Workstream 1).
2. [x] Adaptive per-domain thresholds (Workstream 2).
3. [x] Pattern-aware eviction (Workstream 3).
4. [x] Evaluate the Strategy D trigger (Workstream 4).
5. [x] Final held-out package and v1 artifacts (Workstream 9, partial).
6. [ ] Failure clustering from existing artifacts (Workstream 7) — no new
   replay, cheapest remaining item, feeds the paper discussion.
7. [ ] Float32 embedding storage baseline (Workstream 5.1).
8. [ ] Quantization comparison, only if 5.1 shows embeddings dominate storage
   (Workstream 5.2).
9. [ ] Load ladder and first bottleneck (Workstream 6).
10. [ ] Experiment-tracking audit (Workstream 8).
11. [ ] Sync master plan, README, limitations, and manifest (Workstream 9).

Do not start a step until its card exists in `PHASE3_PLAN.md` and the user
approves it.

## Verification commands

Run from the repository root (PowerShell):

```powershell
python -m pip install ".[dev]"
python -m pytest -q
python -m sscre.benchmark_validate --phase2 --production
docker compose config
```

Existing Phase 3 regeneration commands are in
[`PHASE3_ARTIFACTS_EVIDENCE.md`](./PHASE3_ARTIFACTS_EVIDENCE.md) and
[`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md). Add storage, load,
and clustering commands to their evidence files as each workstream lands, and
confirm every referenced file, flag, and test path exists before recording it.

## Out of scope for this document

- Live-provider measurements (`P0-PROVIDER`; see
  [`../phase-4/PHASE4_PROVIDER_EVIDENCE.md`](../phase-4/PHASE4_PROVIDER_EVIDENCE.md))
- Full human factual-correctness labeling (`P0-LABELS`)
- Dashboard expansion and live dual-model runs (`P2-DASH`, `P2-DUAL`)
- Multi-region, multi-host, or production capacity/SLA claims
- GPU rental or self-hosted models without a profiling result that requires them
- Retuning Features 1–3 on held-out data
