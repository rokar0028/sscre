# Phase 2 → Phase 3 transition plan

**Review date:** 2026-10-09  
**Audience:** you + Cursor agent mode  
**Primary output:** [`docs/phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md) (authoring complete 2026-10-09; Phase 3 **code** gated on explicit OK)

---

## Snapshot (where SSCRE stands)

| Area | Score / status | Notes |
| --- | --- | --- |
| Phase 1 | **25/25** | Milestones 1–10 implemented per plans. |
| Phase 2 | **~40 / 55** | Workstreams **1–6** complete with evidence; **7–9** and several definition-of-done items open. |
| Phase 3 | **implementation-complete** | Feature 1 passed; Feature 2 and Strategy D were deferred by their pre-registered gates. |
| Phase 4 | **validation-complete with documented deferrals** | Pareto follow-up, bounded scale profiling, release audit, and artifact manifest complete; credentialed provider run unavailable. |
| **In-scope total** | **historical pre-Phase 3 snapshot** | The earlier ~70 / 100 score is retained only as the planning baseline. |

**Strategic decision (confirmed):** Do **not** finish every remaining Phase 2 item. Close **at most 2–3** high-leverage gaps, then start Phase 3 (hypothesis-driven features that produce publishable numbers).

**North star:** Early-stage startup roles (₹20–40 LPA) → need a **paper with measured** hit rate, false-reuse rate, cost/latency trade-offs, and honest limitations—not a longer checklist.

**Related:** Public repo timing and export rules live in
[`SSCRE_PUBLIC_READINESS.md`](./SSCRE_PUBLIC_READINESS.md). Green CI and
reproducible benchmarks help both paper artifact and future public export.

## Resource decision: APIs, LLMs, and GPUs

This section records when external compute becomes necessary for the research
paper. It prevents an API key or rented GPU from being introduced merely
because the project is entering a later phase.

| Need | Phase 2 | Phase 3 | After Phase 3 / optional v2 |
| --- | --- | --- | --- |
| Development and reproducible tests | Local CPU + deterministic fake providers | Local CPU + synthetic replay | Keep for regression tests |
| Real provider cost, token, and network-latency claims | Not required; `P2-PROV` is deferred | Not required; live-provider evidence remains explicitly deferred | Use a small, separately labelled API run before making production-provider claims |
| LLM API for a demo | Optional, only for a live demonstration | Optional, not part of the paper result | Use a low-volume hosted API if the demo needs generated answers |
| Additional LLM / cross-encoder validator | Not required | Only if Strategy C’s final held-out FPR exceeds `0.0`; this trigger did not fire | Revisit only under a written protocol reset |
| Scaling or high-volume load testing | Not required | Deferred; no capacity claim is supported | Run after the workload and target scale are defined |
| Rented GPU | Not required | Not required | Only for self-hosting, high-volume load tests, local cross-encoder inference, or quantization experiments; profile first |

**Paper rule:** Phase 3 results may be written using the current synthetic
replay artifacts. If real API evidence is later added, it must be a separate,
clearly labelled experiment with provider/model version, configuration, token
usage, cost, latency, rate-limit behavior, and credentials excluded from
artifacts. Do not mix synthetic and live-provider numbers.

**Recommended next decision:** after Phase 3, run a small real-provider API
validation only if the paper needs real-world cost/latency claims. Rent a GPU
only if that experiment or a later scaling experiment shows that API usage or
local CPU inference is the bottleneck.

---

## Non-negotiable rules (agents and humans)

- [x] Read [`SSCRE_PLAN.md`](../SSCRE_PLAN.md), [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md), and relevant `WORKSTREAM_*_EVIDENCE.md` before changing code.
- [x] **No Phase 3 code** until each feature has a written **hypothesis** and **pass/fail criterion** in `PHASE3_PLAN.md` (per master plan).
- [x] **No invented numbers.** Every table/plot traces to a recorded command, config, dataset version (`reviewed-query-pairs-2.0`), and seed.
- [x] **Held-out split (`benchmarks/held_out_test.jsonl`, 215 pairs):** development-only tuning; the additional Phase 4 reference replay was explicitly reset and separately labelled.
- [x] Work on a **feature branch**; do not commit to `main` or **push** without explicit approval.
- [x] Prefer vertical slices over new infrastructure (YAGNI); experiment tracking only if manual artifacts are insufficient.

---

## Phase 0 — Decisions required from you (gate)

**Implementation plan (steps + decision record):**
[`PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md`](./PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md)

**Phase 0 complete (2026-10-09).** Full record:
[`PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md`](./PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md) § Decision record.

- [x] Confirm **2–3 Phase 2 carryover items** from Phase 1 below (or replace with your own list).
- [x] Confirm **Phase 3 feature order** (default recommendation: adaptive thresholds → pattern-aware eviction → Strategy D only if C misses safety target).
- [x] Confirm whether **live provider measurements** stay deferred through Phase 3 (synthetic + explicit limitation) or become a Phase 2 carryover.
- [x] Confirm whether **human correctness labels** are in scope before the paper or explicitly out of scope with limitation text.
- [x] Approve creation of **`docs/phase-3/PHASE3_PLAN.md`** as the single Phase 3 source of truth (and link it from [`phase-3/README.md`](../phase-3/README.md)).

---

## Phase 1 — Close 2–3 Phase 2 gaps (triage)

**Implementation plan (steps + completion record):**
[`PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md`](./PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md)

Confirmed carryovers: **P2-CI** → **P2-GALLERY** → **P2-OPS (lite)** (see § 1.2).

### 1.1 Inventory (remaining work from Phase 2 plans)

Status key: **done** | **partial** | **open** | **deferred**

| ID | Item | Source | Status | Paper needs? | Phase 3 needs? | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| P2-CI | Green CI on Ubuntu (pytest + compose config) | `.github/workflows/ci.yml`, agent note on sha256 / migration checksum / CRLF | **partial** | High (artifact credibility) | Low | **M** |
| P2-LABEL | Human factual-correctness labels + adjudication | PHASE_2 step 4; Milestone 11 | **open** | Medium–High (quality claims) | Low | **L** |
| P2-PROV | Live real-provider observation run | WS4 deferral; WS5 limitation already documented | **deferred** | Medium (cost/latency realism) | Low | **M–L** |
| P2-FIELDS | Independent compatibility / correctness / preference on every pair | Phase 2 definition of done | **partial** | Medium | Low | **M** |
| P2-GALLERY | Failure gallery + category aggregates | WS7 | **open** | **High** (figures, discussion) | Medium (failure clustering) | **M** |
| P2-OPS | PostgreSQL restart, concurrency, load limits | WS8 | **partial** | Low–Medium (honest ops section) | Medium (1K–100K still Phase 3+) | **M–L** |
| P2-DASH | Dashboard reading artifacts | WS9 gate | **open** | Low | Low | **M** |
| P2-DUAL | Dual-model experiment | WS9 gate | **open** | Low | Low | **L** |

Agent task (when asked):

- [ ] Refresh this table from the latest checkboxes in [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md) and [`MILESTONE_11_REMAINING_GAPS_IMPLEMENTATION_PLAN.md`](../phase-2/MILESTONE_11_REMAINING_GAPS_IMPLEMENTATION_PLAN.md).
- [ ] Re-score **Paper needs?** / **Phase 3 needs?** / **Effort** after refresh.
- [ ] Propose exactly **2–3** IDs to finish; mark others **deferred** with one-line rationale each.

### 1.2 Confirmed carryovers (Phase 0, 2026-10-09)

| Priority | ID | One-line reason |
| --- | --- | --- |
| 1 | **P2-CI** | Reproducible checkout + stable checksums underpin paper, CI badge, and public export smoke tests. |
| 2 | **P2-GALLERY** | Paper discussion and failure-category metrics; inputs Phase 3 “cluster recurring failures.” |
| 3 | **P2-OPS (lite)** | Document unsupported multi-process + one PostgreSQL restart smoke test; no load/concurrency claims. |

**Deferred (2026-10-09):** P2-LABEL, P2-PROV, P2-FIELDS, P2-DASH, P2-DUAL;
full WS8 load/concurrency (superseded in part on 2026-10-11).

**Update (2026-10-11):** bounded WS8 package recorded in
[`WORKSTREAM_8_EVIDENCE.md`](../phase-2/WORKSTREAM_8_EVIDENCE.md). P2-OPS is
**partial**: simulated failure-closed, measured multi-process duplicate
generation, contention, and a 32-request PostgreSQL load (`not_reached`).
Live container restart, cross-process generation locks, and 1K–100K / capacity
claims remain unsupported. Phase 1 lite stays
[`WORKSTREAM_8_OPS_LITE_EVIDENCE.md`](../phase-2/WORKSTREAM_8_OPS_LITE_EVIDENCE.md).

### 1.3 P2-CI investigation checklist

Failing signals on **GitHub Actions** (e.g. run `37826835133`, 2026-10-08): 15
failures — mostly `source_dataset sha256 mismatch`; one failure in
`tests/test_migrate.py::test_migration_checksum_is_sha256_of_file_contents`.

**Independent review (2026-10-09):**

| Check | Local | `origin/main` (CI) |
| --- | --- | --- |
| `python -m pytest -q` | **650 passed**, 14 skipped | **15 failed** (635 passed) |
| `python -m sscre.benchmark_validate --phase2 --production` | **passed** | fails via same sha256 gate |
| `split_manifest.json` vs `reviewed_query_pairs.jsonl` | **match** (`8dbd3c50…`) | manifest still **`84d8c6fd…`** on remote |
| Unpushed fix | commit **`edd2dea`** on local `main` (manifest + `.gitattributes` for `*.jsonl` LF) | not on GitHub yet (`main` ahead 1) |

**Root causes (confirmed):**

1. **Benchmark:** Remote manifest SHA-256 stale vs 615-pair JSONL. Local
   `edd2dea` refreshes manifest; **push required** for CI.
2. **Migration unit test:** Expected hash is for `SELECT 1;\r\n`; Linux writes
   `SELECT 1;\n` → different SHA-256. Fix `tests/test_migrate.py` (assert LF
   bytes / `newline="\n"`), not production migrations. Optional hardening:
   `migrations/*.sql text eol=lf` in `.gitattributes`.

**Tasks:**

- [x] Reproduce locally: `python -m pip install ".[dev]" ; python -m pytest -q`
  (2026-10-09: 650 passed).
- [x] `python -m sscre.benchmark_validate --phase2 --production` (2026-10-09:
  passed).
- [ ] Push `edd2dea` (or equivalent) so GitHub manifest matches JSONL on Ubuntu.
- [x] Fix LF migration checksum test; re-run pytest on Windows; confirm green CI
  on push.
- [ ] Record fix + GitHub Actions URL in verification log below.

### 1.4 Phase 1 exit criteria

- [x] You approved the 2–3 carryover IDs in writing (chat or checked Phase 0 box).
- [x] Selected items have updated plan docs with `- [ ]` / `- [x]` and evidence links ([`PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md`](./PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md), [`WORKSTREAM_8_OPS_LITE_EVIDENCE.md`](../phase-2/WORKSTREAM_8_OPS_LITE_EVIDENCE.md), gallery export in `benchmarks/README.md`).
- [x] `python -m pytest -q` passes locally on the carryover branch (2026-10-09: **653 passed**, 15 skipped on `phase1/carryovers`).
- [ ] GitHub Actions is green on the branch you intend to merge (pending push of `edd2dea` + carryover commits; last known fail run `37826835133`).

---

## Phase 2 — Author `PHASE3_PLAN.md` (planning only)

**Implementation plan (steps + completion record):**
[`PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](./PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md)

Create [`docs/phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md) with the sections below. **No implementation** in this phase.

### 2.1 Document skeleton

- [x] Title, status, last updated, link back to this transition doc.
- [x] **Goals** (3–5 bullets): what Phase 3 must prove for the paper.
- [x] **Non-goals** (explicit): multi-region, unbounded observability, dual-model by default, etc.
- [x] **Baselines frozen:** Strategies A / B / C definitions and configs (pointer to WS5 artifacts).
- [x] **Dataset policy:** development vs held-out; operating-point threshold `0.95` chosen on development only (cite WS5).

### 2.2 Feature cards (one per Phase 3 feature)

For each feature, complete **all** fields before any code:

| Feature | Hypothesis | Pass/fail criterion | Primary metric | Baselines | Effort | Order |
| --- | --- | --- | --- | --- | --- | --- |
| Adaptive per-domain thresholds | Per-domain τ ↑ C `hit_rate` vs global `0.95` without held-out FPR > `0` | Dev τ map + one held-out replay; see `PHASE3_PLAN.md` Feature 1 | `hit_rate`, `false_positive_rate`, `estimated_cost_usd`, `p95_latency_ms` | A, B, C global vs C adaptive | M | 1 |
| Pattern-aware eviction (hits + freshness class) | Pattern eviction ↑ reuse vs WS6 `conservative` at FPR ≤ `0` | Dev `entry_cap` + rule tune; one held-out replay — `PHASE3_PLAN.md` Feature 2 | `stale_exposure_rate`, `hit_rate`, `eviction_count` | C + WS6 `conservative` | L | 2 |
| Strategy D cross-encoder validator | CE lowers FPR vs C **if** final held-out FPR > `0` | Dev validator threshold; one held-out replay — `PHASE3_PLAN.md` Feature 3 | `false_positive_rate`, validator `p95_latency_ms`, cost | C vs C+D | L; **default defer** | 3 (conditional) |

Checklist per feature:

- [x] Hypothesis is falsifiable (one sentence). _(Feature 1 — adaptive thresholds.)_
- [x] Pass/fail uses **held-out** or pre-registered development protocol (state which). _(Feature 1.)_
- [x] Metric names match WS5 report fields (hit rate, false-positive / unsafe-serve, cost, p95 latency). _(Feature 1.)_
- [x] Stopping rule for Strategy D documented (when **not** to build it). _(Feature 3 — defer while C FPR ≤ `0`.)_

Optional Phase 3 items from [`SSCRE_PLAN.md`](../SSCRE_PLAN.md)—include only with the same card:

- [x] int8 embedding quantization — **deferred v2** (`PHASE3_PLAN.md` P3-OPT-Q8)
- [x] Load tests 1K→100K simulated Q/day — **deferred v2** (`P3-OPT-LOAD`)
- [x] Failure clustering from gallery exports — **deferred code**; manual paper analysis OK (`P3-OPT-CLUSTER`)
- [x] Experiment tracking — **deferred v2** (`P3-OPT-TRACK`)

### 2.3 Recommended implementation order (default)

- [x] **1.** Adaptive per-domain thresholds (largest expected Pareto shift with moderate risk).
- [x] **2.** Pattern-aware eviction (storage + freshness interaction; builds on WS6).
- [x] **3.** Strategy D **iff** documented C shortfall on pre-registered safety constraint.
- [x] Defer quantization and extreme load until main safety/reuse story is stable.

### 2.4 Phase 2 exit criteria (authoring)

- [x] [`PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](./PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md) Steps 0–6 + Step 7 review complete; user OK for code pending.
- [x] [`PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md) has Features 1–3 cards, optional deferrals, order, and paper-artifact outline.
- [x] No Phase 3 implementation code in the authoring branch (docs only).
- [x] **User OK in writing** to start Phase 3 implementation (Feature 1 first);
  execution requests were provided in chat on 2026-10-10.

---

## Phase 3 — Evaluation and paper artifacts (execution)

These are **deliverables** Phase 3 implementation must produce—not optional polish.

### 3.1 Tables and figures

- [x] **Main results table:** final comparison records per-strategy hit rate, false-reuse rate, cost, and p50/p95 latency.
- [x] **Threshold sweeps** and domain threshold curves are recorded.
- [ ] Selected-stack **Pareto curve** remains deferred to a future protocol-approved rerun.
- [x] **Freshness / eviction** slice: recorded in `phase3-held-out-eviction.json`.
- [x] **Ablations:** recorded in `phase3-ablations.json`, including deferred/failed features.

### 3.2 Statistics and protocol

- [x] Bootstrap (or documented binomial) **confidence intervals**; fixed seeds recorded.
- [x] **Single final held-out run** logged once (config hash, git commit, dataset version).
- [x] Limitations section sourced from real gaps (synthetic provider, deferred labels, OPS-lite at Phase 3 close, and WS6 freshness scope).
  2026-10-11: cite [`WORKSTREAM_8_EVIDENCE.md`](../phase-2/WORKSTREAM_8_EVIDENCE.md)
  for bounded PostgreSQL ops; do not upgrade that package into a capacity claim.

### 3.3 Reproducibility

- [x] Documented `python -m sscre ...` sequence regenerates the current paper-artifact package; commands are copied into the evidence files.
- [x] Outputs land under `artifacts/evaluation/` with `phase3-*` names.

### 3.4 Headline numbers (draft placeholders — fill after measurement)

Do **not** check until values exist in artifacts:

- [x] Held-out **hit rate** at selected operating point: Strategy C + Feature 1
  `0.002325581395348837`.
- [x] Held-out **false-reuse / false-positive rate** with 95% CI: `0.0`.
- [x] **Estimated token or cost savings** recorded in the final comparison; configured synthetic costs are `0.0`.
- [x] **p95 latency** recorded in the final comparison: `0.0 ms` under synthetic replay.

Use these in abstract and resume only after the final held-out run.

**Phase 3 execution status (2026-10-10):** implementation and final held-out package
closed. Feature 1 passed, Feature 2 failed its reuse-improvement criterion and is
deferred, Strategy D was not triggered, and the selected-stack Pareto curve remains
explicitly deferred to avoid an additional held-out run.

---

## Phase 4 — Post-Phase 3 validation status

**Status:** implementation and evidence package complete on `phase4/setup`;
credentialed live-provider validation is unavailable, and clean-checkout replay
remains deferred even though the Step 3 profiling changes are committed locally.

Plan and evidence:

- [x] `PHASE4_IMPLEMENTATION_PLAN.md` Step 0 baseline and gates.
- [x] `P4-PARETO` protocol-reset follow-up with retained adaptive point.
- [x] `P4-PROVIDER` unavailable artifact; no remote request or synthetic
  substitution.
- [x] `P4-SCALE` bounded storage and in-memory scale profile; no optimization
  trigger.
- [x] `P4-RELEASE` link, artifact, redaction, limitation, and verification
  audit.
- [x] `P4-ARTIFACTS` machine-readable manifest:
  `artifacts/evaluation/phase4-paper-artifact-manifest.json`.

See [`PHASE4_IMPLEMENTATION_PLAN.md`](./PHASE4_IMPLEMENTATION_PLAN.md) and
[`../phase-4/PHASE4_RELEASE_EVIDENCE.md`](../phase-4/PHASE4_RELEASE_EVIDENCE.md).

## Phase 4 — Agent workflow summary

When invoked in agent mode:

1. [x] Complete **Phase 1** triage table refresh + recommendation; **wait for OK** (Phase 0).
2. [x] Write **`PHASE3_PLAN.md`** (Phase 2); **wait for OK** on scope/order before Phase 3 code.
3. [x] Implement approved Phase 2 carryovers on a branch; keep diffs minimal.
4. [x] Implement Phase 3 features one card at a time; update plan checkboxes and evidence after each. Feature 2 failed its criterion and Strategy D was deferred by gate.
5. [x] Run verification from repo root and record in plan:
   - [x] `python -m pytest -q`
   - [x] Paper artifact commands from `PHASE3_PLAN.md`
   - [x] `docker compose config` (non-secret sample env)

Reply template after planning pass:

- Short summary of recommended 2–3 Phase 2 items and Phase 3 order.
- Bulleted **decisions needed** (Phase 0 checklist).

---

## Verification log

| Step | Command / action | Date | Result |
| --- | --- | --- | --- |
| Phase 1 CI | `python -m pytest -q` on branch | 2026-10-09 | 650 passed, 14 skipped (local) |
| Phase 1 CI | `benchmark_validate --phase2 --production` | 2026-10-09 | passed (local) |
| Phase 1 CI | Local pytest + validate on `phase1/carryovers` | 2026-10-09 | 650 passed; validate passed |
| Phase 1 carryovers | `python -m pytest -q` (final, all tracks) | 2026-10-09 | **653 passed**, 15 skipped |
| Phase 1 carryovers | `sscre.gallery_export` held-out comparison | 2026-10-09 | `workstream5-held-out-comparison-gallery.html` |
| Phase 1 carryovers | OPS lite smoke | 2026-10-09 | `test_postgres_connection_loss_on_lookup_fails_closed` (skipped without DB URL) |
| Phase 1 CI | Push `edd2dea` + carryover branch | | pending explicit OK |
| Phase 1 CI | GitHub Actions run URL (green) | | last known fail: `37826835133` |
| Phase 2 authoring | `PHASE3_PLAN.md` + authoring plan Steps 0–6 | 2026-10-09 | complete on `phase2/phase3-plan` |
| Phase 2 authoring | Self-review (Features 1–3 hypothesis + pass/fail) | 2026-10-09 | no TBD in in-scope cards |
| Phase 2 authoring | User OK for Phase 3 code | 2026-10-10 | implementation steps 1–6 explicitly requested in chat |
| Phase 3 | Final held-out evaluation command | 2026-10-10 | passed once; `phase3-final-held-out-comparison.json` |
| Phase 3 | Reproducibility runbook (`PHASE3_PLAN.md` § 3.3) end-to-end | 2026-10-10 | development package, gallery, pytest, benchmark validation, and compose checks passed |

---

## Learning objectives (study only — not implementation checkboxes)

- [ ] How to pre-register an operating point without held-out leakage.
- [ ] When bootstrap CIs for proportions vs latency distributions.
- [ ] Cross-encoder cost/latency trade-offs as Strategy D.
- [ ] Domain-stratified threshold selection without overfitting small domains.
