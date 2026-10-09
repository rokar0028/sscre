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
| Phase 3 | **0 / 20** (planned) | No implementation; scope lives in [`SSCRE_PLAN.md`](../SSCRE_PLAN.md) § Phase 3. |
| **In-scope total** | **~70 / 100** | |

**Strategic decision (confirmed):** Do **not** finish every remaining Phase 2 item. Close **at most 2–3** high-leverage gaps, then start Phase 3 (hypothesis-driven features that produce publishable numbers).

**North star:** Early-stage startup roles (₹20–40 LPA) → need a **paper with measured** hit rate, false-reuse rate, cost/latency trade-offs, and honest limitations—not a longer checklist.

**Related:** Public repo timing and export rules live in
[`SSCRE_PUBLIC_READINESS.md`](./SSCRE_PUBLIC_READINESS.md). Green CI and
reproducible benchmarks help both paper artifact and future public export.

---

## Non-negotiable rules (agents and humans)

- [ ] Read [`SSCRE_PLAN.md`](../SSCRE_PLAN.md), [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md), and relevant `WORKSTREAM_*_EVIDENCE.md` before changing code.
- [ ] **No Phase 3 code** until each feature has a written **hypothesis** and **pass/fail criterion** in `PHASE3_PLAN.md` (per master plan).
- [ ] **No invented numbers.** Every table/plot traces to a recorded command, config, dataset version (`reviewed-query-pairs-2.0`), and seed.
- [ ] **Held-out split (`benchmarks/held_out_test.jsonl`, 215 pairs):** development-only tuning; **one** final held-out report for the paper unless you explicitly reset the protocol in writing.
- [ ] Work on a **feature branch**; do not commit to `main` or **push** without explicit approval.
- [ ] Prefer vertical slices over new infrastructure (YAGNI); experiment tracking only if manual artifacts are insufficient.

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
| P2-OPS | PostgreSQL restart, concurrency, load limits | WS8 | **open** | Low–Medium (honest ops section) | Medium (load Phase 3) | **M–L** |
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

**Deferred:** P2-LABEL, P2-PROV, P2-FIELDS, P2-DASH, P2-DUAL; full WS8 load/concurrency.

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
- [ ] **User OK in writing** to start Phase 3 implementation (Feature 1 first).

---

## Phase 3 — Evaluation and paper artifacts (execution)

These are **deliverables** Phase 3 implementation must produce—not optional polish.

### 3.1 Tables and figures

- [ ] **Main results table:** per strategy — hit rate, false-reuse (unsafe-serve) rate, estimated cost savings, p50/p95 latency (held-out + development clearly labeled).
- [ ] **Threshold sweeps** and **Pareto curves** (coverage vs false-positive rate), overall and **by domain** where adaptive thresholds apply.
- [ ] **Freshness / eviction** slice: stale exposure vs reuse (extend WS6 metrics if policy changes).
- [ ] **Ablations:** each Phase 3 feature alone vs full stack vs C baseline.

### 3.2 Statistics and protocol

- [ ] Bootstrap (or documented binomial) **confidence intervals**; fixed seeds recorded.
- [ ] **Single final held-out run** logged once (config hash, git commit, dataset version).
- [ ] Limitations section sourced from real gaps (e.g. synthetic provider, deferred live provider, label sparsity).

### 3.3 Reproducibility

- [ ] One entry point regenerates all paper artifacts (e.g. `make paper-results` or documented `python -m sscre ...` sequence)—commands copied into `PHASE3_PLAN.md` and evidence file.
- [ ] Outputs land under `artifacts/evaluation/` (or agreed path) with names tied to plan version.

### 3.4 Headline numbers (draft placeholders — fill after measurement)

Do **not** check until values exist in artifacts:

- [ ] Held-out **hit rate** at selected operating point (Strategy C or best Phase 3 stack).
- [ ] Held-out **false-reuse / false-positive rate** with 95% CI.
- [ ] **Estimated token or cost savings** vs no-cache at same quality constraint.
- [ ] **p95 latency** delta cache-hit vs miss (synthetic provider unless P2-PROV done).

Use these in abstract and resume only after the final held-out run.

---

## Phase 4 — Agent workflow summary

When invoked in agent mode:

1. [x] Complete **Phase 1** triage table refresh + recommendation; **wait for OK** (Phase 0).
2. [x] Write **`PHASE3_PLAN.md`** (Phase 2); **wait for OK** on scope/order before Phase 3 code.
3. [x] Implement approved Phase 2 carryovers on a branch; keep diffs minimal.
4. [ ] Implement Phase 3 features **one card at a time**; update plan checkboxes and evidence after each.
5. [ ] Run verification from repo root and record in plan:
   - [ ] `python -m pytest -q`
   - [ ] Paper artifact command(s) from `PHASE3_PLAN.md`
   - [ ] `docker compose config` (non-secret sample env)

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
| Phase 2 authoring | User OK for Phase 3 code | | pending |
| Phase 3 | Final held-out evaluation command | | |
| Phase 3 | Reproducibility runbook (`PHASE3_PLAN.md` § 3.3) end-to-end | | |

---

## Learning objectives (study only — not implementation checkboxes)

- [ ] How to pre-register an operating point without held-out leakage.
- [ ] When bootstrap CIs for proportions vs latency distributions.
- [ ] Cross-encoder cost/latency trade-offs as Strategy D.
- [ ] Domain-stratified threshold selection without overfitting small domains.
