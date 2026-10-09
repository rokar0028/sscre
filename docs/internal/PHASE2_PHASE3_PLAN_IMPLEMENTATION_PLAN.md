# Phase 2 — Phase 3 plan authoring implementation plan

**Status:** **closed (authoring)** — 2026-10-09; Phase 3 **code** blocked until user OK (Step 7.5)  
**Owner:** Kartik  
**Parent:** [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § Phase 2  
**Scope source:** [`PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md`](./PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md) (P0-P3-ORDER, P0-PROVIDER, P0-LABELS, P0-PHASE3-DOC); [`SSCRE_PLAN.md`](../SSCRE_PLAN.md) § Phase 3  
**Time box:** 1–2 focused sessions (order: inventory → skeleton → feature cards → paper outline → handoff)

## Goal

Author [`docs/phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md) as the **single Phase 3
source of truth: one falsifiable hypothesis and one pass/fail criterion per feature
**before** any Phase 3 implementation. Freeze baseline pointers (Strategies A / B / C,
development operating point, held-out protocol) so execution does not re-litigate
Phase 2 evidence.

**Exit (authoring):** `PHASE3_PLAN.md` exists with skeleton, feature cards, implementation
order, paper-artifact outline, and limitations aligned to Phase 0 decisions; transition doc
§ 2.1–2.4 checked (except user-OK box); [`docs/phase-3/README.md`](../phase-3/README.md)
links the plan; **Completion record** and **Verification log** filled.

**Exit (Phase 3 code — separate gate):** explicit user OK to start implementation
([`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 2.4).

---

## Learning objectives

Study topics only — not required to check for authoring close (same rule as
[`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) learning section).

- [ ] Pre-register held-out use: development tuning vs one final held-out report.
- [ ] Write a falsifiable hypothesis and pass/fail criterion for adaptive thresholds.
- [ ] State a stopping rule for Strategy D when Strategy C already meets the safety target.
- [ ] Map WS5 report JSON fields to paper table columns without inventing numbers.

---

## Prerequisites (read-only)

- [x] Phase 0 complete — see [`PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md`](./PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md) decision record (2026-10-09).
- [x] Phase 1 carryovers delivered or accepted with documented gaps — see [`PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md`](./PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md) (P2-CI GitHub green may still be push-gated).
- [x] Skim [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) non-negotiable rules (held-out, no invented numbers, no push without OK).
- [x] Skim [`WORKSTREAM_5_EVIDENCE.md`](../phase-2/WORKSTREAM_5_EVIDENCE.md) (frozen baselines, threshold `0.95`, artifact paths).
- [x] Skim [`WORKSTREAM_6_EVIDENCE.md`](../phase-2/WORKSTREAM_6_EVIDENCE.md) (freshness / eviction context for feature card 2).
- [x] Skim gallery export notes in [`benchmarks/README.md`](../../benchmarks/README.md) (failure clustering optional item).
- [x] Confirm workflow: feature branch for doc edits; no commit to `main` or `git push` without explicit OK.

**No Phase 3 code in this phase** — markdown planning only.

---

## Step 0 — Branch and baseline inventory

**Track ID:** `P2-SETUP`

- [x] Create feature branch from current `main` (e.g. `phase2/phase3-plan`).
- [x] Record branch name and base commit in **Completion record → Branch**.
- [x] Copy into a working note (or `PHASE3_PLAN.md` draft appendix) the frozen references below — do not paraphrase metric values without citing artifact paths.

### 0.1 Frozen evaluation inputs (WS5)

| Item | Pointer |
| --- | --- |
| Dataset version | `reviewed-query-pairs-2.0` |
| Splits | 400 development / 215 held-out / 615 source |
| Config | `experiments/evaluation_config.json` (`evaluation-config-1.0`) |
| Development sweep | `artifacts/evaluation/workstream5-development-sweep.json` |
| Held-out comparison | `artifacts/evaluation/workstream5-held-out-comparison.json` |
| Held-out Pareto | `artifacts/evaluation/workstream5-held-out-pareto.json` |
| Operating point | Similarity threshold **`0.95`** chosen on **development only** (WS5 evidence) |
| Provider framing | `synthetic_replay` — live provider deferred per P0-PROVIDER |

### 0.2 Strategy definitions (for “Baselines frozen” section)

- [x] Document in `PHASE3_PLAN.md` what **Strategy A** (no-cache), **B** (embedding-only), and **C** (compatibility-aware) mean in this repo — cite WS5 `baseline` keys and [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md) WS1–5 narrative.
- [x] Record pre-Phase-3 held-out safety snapshot **from artifacts only** (e.g. Strategy C FPR at `0.95` — cite `workstream5-held-out-comparison.json` / Pareto `selected_constraint`, not memory).

### 0.3 Phase 0 constraints to embed as non-goals / limitations

- [x] **P0-PROVIDER:** No live-provider tables unless promoted later in writing.
- [x] **P0-LABELS:** Human factual-correctness labels out of scope; compatibility + sparse correctness fields per label contract.
- [x] **Deferred Phase 2:** P2-DASH, P2-DUAL, full WS8 load/concurrency — not Phase 3 v1 unless a new decision record says otherwise.

- [x] Log read-only confirmation in **Verification log** (§ P2-SETUP).

---

## Step 1 — Document skeleton (`PHASE3_PLAN.md`)

**Track ID:** `P3-DOC-SKELETON`  
**References:** [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 2.1

Create `docs/phase-3/PHASE3_PLAN.md` with (empty tables OK until Step 2):

- [x] Title, **Status** (`planning-complete` until user OK for code), **Last updated**, link back to [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md).
- [x] **Goals** (3–5 bullets): what Phase 3 must prove for the paper (measured hit rate, false-reuse / unsafe-serve, cost/latency trade-offs, honest limitations).
- [x] **Non-goals** (explicit): e.g. multi-region, unbounded observability, dual-model by default, dashboard-first UX, full 615-pair human correctness study.
- [x] **Baselines frozen:** Strategies A / B / C + config hash / artifact paths (from Step 0).
- [x] **Dataset policy:** development vs held-out; threshold selection on development only; **one** final held-out report for the paper unless protocol reset in writing.
- [x] **Working agreements:** feature branch, no push without OK, no invented numbers (mirror transition doc).

### 1.1 Index and links

- [x] Update [`docs/phase-3/README.md`](../phase-3/README.md) to link `PHASE3_PLAN.md` as the Phase 3 source of truth (replace “when planning is approved” placeholder text).
- [x] Optional: one-line link from [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md) header or “Phase 3 handoff” note — only if a natural anchor exists; avoid drive-by edits.

### 1.2 Record

- [x] Fill **Completion record → P3-DOC-SKELETON** (partial — user OK for Phase 3 code still pending).

---

## Step 2 — Feature card 1: Adaptive per-domain thresholds

**Track ID:** `P3-FEAT-ADAPT`  
**Order:** 1 (per P0-P3-ORDER)

Complete **all** fields in `PHASE3_PLAN.md` before any implementation:

- [x] **Hypothesis** — one falsifiable sentence (e.g. domain-stratified thresholds improve reuse at equal or lower false-reuse vs global `0.95`).
- [x] **Pass/fail criterion** — state **development** tuning protocol vs **held-out** evaluation; pre-register max false-reuse / unsafe-serve constraint (align with WS5 `max_false_positive_rate` semantics).
- [x] **Primary metric(s)** — hit rate, false-positive / unsafe-serve rate, cost, p50/p95 latency — names must match WS5 report / `evaluation_statistics` fields.
- [x] **Baselines** — A, B, C at frozen global threshold vs adaptive policy.
- [x] **Effort** — S / M / L with rough session estimate.
- [x] **Domain definition** — cite benchmark metadata field(s) used for strata (verify in `benchmarks/` or label contract; no invented domains).

Checklist:

- [x] Hypothesis is falsifiable (one sentence).
- [x] Pass/fail does **not** tune on held-out labels.
- [x] Stopping rule if adaptive policy ties or loses to global `0.95` on held-out safety.

---

## Step 3 — Feature card 2: Pattern-aware eviction

**Track ID:** `P3-FEAT-EVICT`  
**Order:** 2 (per P0-P3-ORDER)  
**References:** WS6 evidence; storage / freshness classes in evaluation reports

- [x] **Hypothesis** — e.g. eviction using hit frequency + freshness class reduces stale exposure without unacceptable hit-rate loss vs WS6 conservative baseline.
- [x] **Pass/fail criterion** — development protocol for policy knobs; held-out or pre-registered replay for stale-exposure vs reuse metrics (extend WS6 fields if policy changes).
- [x] **Primary metric(s)** — stale exposure, reuse / hit rate, storage or eviction counts (cite existing JSON paths or planned extensions).
- [x] **Baselines** — Strategy **C** + documented WS6 storage/freshness baseline — not a new ad hoc baseline.
- [x] **Effort** — S / M / L.

Checklist:

- [x] Builds on WS6 workloads (stable; note semi/dynamic held-out gaps from WS6 limitations).
- [x] No claim of multi-process or extreme load unless full WS8 is promoted.

---

## Step 4 — Feature card 3: Strategy D (conditional cross-encoder)

**Track ID:** `P3-FEAT-D`  
**Order:** 3 **only if** documented C shortfall (per P0-P3-ORDER)

- [x] **Precondition:** Document current Strategy C held-out safety outcome from Step 0 artifacts and the **safety target** that would trigger D (numeric threshold, not narrative).
- [x] **Hypothesis** — cross-encoder validator reduces false-reuse at acceptable latency/cost vs C alone.
- [x] **Pass/fail criterion** — held-out or pre-registered dev subset; false-reuse vs p95 validator latency trade-off.
- [x] **Primary metric(s)** — false-reuse / unsafe-serve, validator latency, token/cost delta.
- [x] **Baselines** — Strategy C at frozen operating point.
- [x] **Effort** — typically **L**; mark **conditional**.

Checklist:

- [x] **Stopping rule when not to build D** — e.g. if C already satisfies pre-written held-out safety constraint at `0.95`, D remains **deferred** with one-line rationale in the plan.
- [x] Pass/fail uses same held-out protocol as other features (single final held-out run).

---

## Step 5 — Optional feature cards (include only with full cards)

**Track ID:** `P3-FEAT-OPT`  
**References:** [`SSCRE_PLAN.md`](../SSCRE_PLAN.md) § Phase 3; transition § 2.2 optional list

For each optional item you include, complete the same card fields as Steps 2–4; otherwise list under **Deferred (Phase 3 v2)** with one-line rationale.

| Item | Default |
| --- | --- |
| int8 embedding quantization | Defer until float32 storage measured |
| Load tests 1K→100K simulated Q/day | Defer until safety/reuse story stable |
| Failure clustering from gallery exports | Optional if gallery HTML/JSON exists (Phase 1) |
| Experiment tracking | Only if manual JSON artifacts insufficient |

- [x] Decision: which optionals are **in** vs **deferred** recorded in `PHASE3_PLAN.md`.
- [x] Default recommendation checked in plan: defer quantization and extreme load until main safety/reuse story is stable (transition § 2.3).

---

## Step 6 — Implementation order and Phase 3 execution outline

**Track ID:** `P3-ORDER-EXEC`  
**References:** transition § 2.3, § 3 (execution deliverables — **planned**, not built in Phase 2)

### 6.1 Recommended order (confirm in plan)

- [x] **1.** Adaptive per-domain thresholds  
- [x] **2.** Pattern-aware eviction  
- [x] **3.** Strategy D **iff** documented C shortfall  
- [x] Defer quantization and extreme load until core story stable  

### 6.2 Paper artifacts section (outline only in `PHASE3_PLAN.md`)

Copy checklist from transition § 3; each item is a **planned deliverable** with placeholder commands — no headline numbers checked until artifacts exist.

- [x] **Tables and figures:** main results; threshold sweeps / Pareto by domain; freshness/eviction slice; ablations per Phase 3 feature.
- [x] **Statistics:** bootstrap (or documented binomial) CIs; fixed seeds; **single final held-out run** metadata (config hash, commit, dataset version).
- [x] **Limitations:** synthetic provider, deferred labels, OPS lite / WS8 gaps — cite real evidence paths.
- [x] **Reproducibility:** one documented entry point (e.g. `make paper-results` or `python -m sscre ...` sequence) — commands TBD in plan, filled when implemented.
- [x] **Headline numbers:** abstract/resume placeholders **unchecked** until final held-out run (transition § 3.4).

---

## Step 7 — Review, approval gate, close Phase 2

**Track ID:** `P2-CLOSE`

- [x] Self-review: every Phase 3 feature has hypothesis + pass/fail before any `- [ ]` implementation checkbox in the same doc (Features 1–3; paper §3.4 remains execution-gated).
- [x] Cross-check non-goals against P0-PROVIDER, P0-LABELS, and Phase 1 deferrals (`PHASE3_PLAN.md` Non-goals + Limitations).
- [x] Update [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 2.1–2.4 checkboxes to match `PHASE3_PLAN.md`.
- [x] Append **Verification log** rows (doc paths, no pytest required for planning-only phase unless docs CI exists).
- [ ] **User OK (Step 7 gate):** explicit approval of scope, order, and Strategy D
  precondition before Phase 3 code ([`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 2.4).
  _Authoring does not require this checkbox; Phase 3 implementation does._

**Next authorized work (after user OK):** implement Phase 3 features **one card at a time**
on a feature branch; update plan checkboxes and evidence after each slice.

---

## Acceptance criteria

- [x] [`docs/phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md) exists with skeleton (§ 2.1), completed cards for order 1–2 and conditional card 3, optional/deferred list, implementation order, and paper-artifact outline.
- [x] Each in-scope feature has falsifiable hypothesis + pass/fail + metrics aligned to WS5/WS6 report fields.
- [x] Strategy D stopping rule documented; default path defers D if C meets pre-written safety target.
- [x] Dataset / held-out policy matches transition non-negotiables (no held-out tuning; one final held-out report).
- [x] Limitations reflect P0-PROVIDER and P0-LABELS without overstating ops or label coverage.
- [x] [`docs/phase-3/README.md`](../phase-3/README.md) links `PHASE3_PLAN.md`.
- [x] [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 2.1–2.4 aligned; Phase 2 verification log rows filled.
- [x] **No Phase 3 implementation** commits masquerading as planning (docs-only on `phase2/phase3-plan` at close).
- [x] Completion record below has no TBDs except user approval date / branch merge details.

---

## Completion record (fill in)

_Date completed:_ 2026-10-09

**Closure note:** Authoring workstream **complete**. Phase 3 **code** remains blocked until
Step 7 user OK and (separately) commit/merge of doc changes if desired.

### Branch

**Name:** `phase2/phase3-plan` (created from `phase1/carryovers` tip, 2026-10-09)  
**Base commit:** `17e117f4eb2492c36bafe2b3f52a06777cefd042`  
**Doc tip (uncommitted at close):** working tree on `phase2/phase3-plan` — commit when ready  
**Merge / PR:**

### P3-DOC-SKELETON

**`PHASE3_PLAN.md` path:** `docs/phase-3/PHASE3_PLAN.md` (2026-10-09)  
**README updated:** `docs/phase-3/README.md`  
**User approval date (Phase 3 code OK):** pending

### Feature cards

| Feature | Hypothesis recorded | Pass/fail recorded | In v1 scope |
| --- | --- | --- | --- |
| Adaptive thresholds | yes | yes (dev tune / held-out eval) | yes |
| Pattern-aware eviction | yes | yes | yes |
| Strategy D (conditional) | yes (if triggered) | yes | default **defer** (C FPR `0.0`) |
| Optionals (list IDs) | n/a (all deferred v1) | n/a | P3-OPT-Q8, LOAD, CLUSTER (manual OK), TRACK — see plan § Optional |

### P2-CLOSE

**Transition § 2 updated:** yes — § 2.1–2.4 + verification log (2026-10-09)  
**Self-review:** Features 1–3 complete; optionals deferred (P3-OPT-*); paper §3.4 execution checkboxes intentionally open  
**Deferred items one-liners:** P2-DASH/DUAL; full WS8; P2-PROV/P2-LABELS; P3-OPT-Q8/LOAD/TRACK; P3-OPT-CLUSTER manual-only; Strategy D default defer (C FPR `0.0`)

---

## Verification log

| Step | Command / action | Date | Result |
| --- | --- | --- | --- |
| P2-SETUP | Read WS5 / WS6 evidence + config paths | 2026-10-09 | ok |
| P2-SETUP | Branch `phase2/phase3-plan` @ `17e117f` | 2026-10-09 | ok |
| P2-SETUP | `benchmark_validate --phase2 --production` | 2026-10-09 | passed (`split_manifest_sha256=68912e3b…`) |
| P2-SETUP | Config + held-out JSON snapshot in `PHASE3_PLAN.md` appendix | 2026-10-09 | ok |
| P3-DOC-SKELETON | `PHASE3_PLAN.md` skeleton on branch | 2026-10-09 | `docs/phase-3/PHASE3_PLAN.md` |
| P3-DOC-SKELETON | `docs/phase-3/README.md` link | 2026-10-09 | index table updated |
| P3-FEAT-ADAPT | Feature card complete in plan | 2026-10-09 | `PHASE3_PLAN.md` § Feature 1 |
| P3-FEAT-EVICT | Feature card complete in plan | 2026-10-09 | `PHASE3_PLAN.md` § Feature 2 |
| P3-FEAT-D | Conditional card + stopping rule | 2026-10-09 | `PHASE3_PLAN.md` § Feature 3; **deferred** |
| P3-FEAT-OPT | Optional/deferred list | 2026-10-09 | `PHASE3_PLAN.md` § Optional features — v1 |
| P3-ORDER-EXEC | Order + paper outline in plan | 2026-10-09 | `PHASE3_PLAN.md` § order + § Paper artifacts |
| P2-CLOSE | Self-review + non-goals cross-check | 2026-10-09 | ok |
| P2-CLOSE | User OK for Phase 3 implementation | | pending |
| P2-CLOSE | `PHASE3_TRANSITION.md` § 2.1–2.4 | 2026-10-09 | aligned |

---

## Verification

### Authoring close (Phase 2 planning — this plan)

- [x] `PHASE3_PLAN.md` readable end-to-end; no TBD in hypothesis/pass/fail for in-scope features.
- [x] Completion record complete.
- [x] Parent transition doc § Phase 2 matches evidence.

### Phase 3 code gate (not part of authoring close)

- [ ] User explicitly approved plan before any Phase 3 code work is treated as authorized
  (record date in **Completion record → User approval date** and check Step 7 user OK).
