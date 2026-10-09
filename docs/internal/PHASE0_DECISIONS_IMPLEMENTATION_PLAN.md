# Phase 0 — Decisions implementation plan

**Status:** **complete** (2026-10-09)  
**Owner:** Kartik  
**Parent:** [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § Phase 0  
**Time box:** one focused session (~45–90 minutes)

## Goal

Record **five explicit decisions** so agents and you can start Phase 1 (2–3 Phase 2
carryovers) and author [`docs/phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md)
without re-litigating scope every session.

**Exit:** All acceptance criteria checked; decisions copied into
[`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) Phase 0 checkboxes and the
**Decision record** section below.

---

## Learning objectives

- [ ] Map open Phase 2 workstream items to paper vs resume vs engineering-only value.
- [ ] Pre-register what the held-out split is allowed to be used for.
- [ ] Write limitation text when deferring live provider or human correctness labels.

---

## Prerequisites (read-only)

- [ ] Skim [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) snapshot and Phase 1 triage table.
- [ ] Skim [`WORKSTREAM_5_EVIDENCE.md`](../phase-2/WORKSTREAM_5_EVIDENCE.md) (what is already frozen).
- [ ] Skim [`SSCRE_PUBLIC_READINESS.md`](./SSCRE_PUBLIC_READINESS.md) hard gates (private repo until paper).

No code changes in Phase 0.

---

## Step 1 — Choose Phase 2 carryovers (2–3 items)

**Decision ID:** `P0-CARRYOVER`

### 1.1 Review the menu

| ID | Item | Effort | Paper value |
| --- | --- | --- | --- |
| P2-CI | Green GitHub CI (manifest SHA + migration test LF) | M | High (credibility) |
| P2-GALLERY | Failure gallery + category metrics (WS7) | M | High (discussion) |
| P2-OPS | Restart / concurrency / load (WS8) or written “unsupported” | M–L | Medium |
| P2-LABEL | Human correctness labels (615 pairs) | L | Medium–High |
| P2-PROV | Live provider measurement run | M–L | Medium |
| P2-FIELDS | Full correctness/preference fields on every pair | M | Medium |
| P2-DASH / P2-DUAL | Dashboard or dual-model | M–L | Low for first paper |

### 1.2 Default recommendation (change if you disagree)

Pick **exactly 2–3**; mark the rest **deferred** in the decision record.

- [x] **P2-CI** — push manifest/LF fix + migration unit test fix; CI green.
- [x] **P2-GALLERY** — static or CLI gallery from existing evaluation artifacts.
- [x] **Third slot (choose one):**
  - [x] **P2-OPS-lite** — document unsupported multi-process + one restart smoke test, **or**
  - [ ] **Defer P2-OPS** — one paragraph in paper limitations only.

### 1.3 Explicitly defer (unless you promote one into the 2–3)

- [x] P2-LABEL deferred → paper uses compatibility + synthetic replay; limitation stated.
- [x] P2-PROV deferred → keep WS5 “synthetic_replay” framing.
- [x] P2-DASH and P2-DUAL deferred.

### 1.4 Record

Fill **Decision record → P0-CARRYOVER** at the bottom of this file.

---

## Step 2 — Confirm Phase 3 feature order

**Decision ID:** `P0-P3-ORDER`

Read candidate features in [`SSCRE_PLAN.md`](../SSCRE_PLAN.md) § Phase 3 and
[`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 2.3.

### 2.1 Default order (check if accepting as-is)

- [x] **1.** Adaptive per-domain thresholds (vs global `0.95`).
- [x] **2.** Pattern-aware eviction (hit frequency + freshness class).
- [x] **3.** Strategy D (cross-encoder) **only if** Strategy C fails a pre-written
  held-out safety criterion in `PHASE3_PLAN.md`.

### 2.2 Optional: reorder or drop

- [x] No change to default order.
- [ ] Custom order (write 1 → 2 → 3 in decision record).
- [ ] Drop feature(s) for v1 paper (list in decision record).

### 2.3 Record

Fill **Decision record → P0-P3-ORDER**.

---

## Step 3 — Live provider measurements

**Decision ID:** `P0-PROVIDER`

WS4/WS5 already document synthetic replay and an unavailable live run.

Choose **one**:

- [x] **A — Defer through Phase 3 (recommended):** No credentialed CI or paper
  tables from a live API; limitations cite WS5 provider section.
- [ ] **B — Phase 2 carryover:** Promote **P2-PROV** into Step 1’s 2–3 slots;
  define budget cap and one fixed dev subset before any held-out work.
- [ ] **C — Paper-only appendix:** Single optional run after main results frozen;
  not a blocker for Phase 3 start.

### Record

Fill **Decision record → P0-PROVIDER** + one sentence for the paper limitations
draft.

---

## Step 4 — Human factual-correctness labels

**Decision ID:** `P0-LABELS`

Choose **one**:

- [x] **A — Out of scope before paper (recommended):** Report compatibility and
  reuse safety; state that human correctness coverage is sparse / `not_collected`
  where applicable (per label contract).
- [ ] **B — Partial scope:** Label a fixed **N** pairs (write N: ___) for a
  case-study subsection only; not a full 615-pair claim.
- [ ] **C — Full scope:** Promote **P2-LABEL** into Step 1 (replaces another
  carryover); accept **L** effort before Phase 3.

### Record

Fill **Decision record → P0-LABELS**.

---

## Step 5 — Approve Phase 3 planning artifact

**Decision ID:** `P0-PHASE3-DOC`

- [x] Approve creating [`docs/phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md)
  as the **only** Phase 3 implementation source of truth (hypothesis + pass/fail
  per feature before code).
- [x] Approve updating [`docs/phase-3/README.md`](../phase-3/README.md) to link
  `PHASE3_PLAN.md` when it exists.
- [x] Confirm **no Phase 3 implementation** until `PHASE3_PLAN.md` is written and
  you re-read Step 2 order in that doc.

### Record

Fill **Decision record → P0-PHASE3-DOC** with date.

---

## Step 6 — Working agreements (confirm once)

**Decision ID:** `P0-WORKFLOW`

- [x] Feature branch for Phase 1 / Phase 3 work; no direct commits to `main`
  without explicit OK.
- [x] No `git push` without explicit OK.
- [x] Held-out (`benchmarks/held_out_test.jsonl`): tuning forbidden; **one** final
  held-out report for the paper unless protocol reset in writing.
- [x] Public repo: follow [`SSCRE_PUBLIC_READINESS.md`](./SSCRE_PUBLIC_READINESS.md);
  stay **private** until paper submission decision.

- [x] All four bullets accepted.

---

## Step 7 — Close Phase 0 (handoff)

- [x] Copy finalized decisions into **Decision record** (below); no TBDs left.
- [x] Check all five boxes in [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § Phase 0.
- [x] Reply to agent (or note in chat): “Phase 0 complete” + paste decision record.
- [x] **Next authorized work:** Phase 1 carryovers per `P0-CARRYOVER`, then agent
  drafts `PHASE3_PLAN.md` if `P0-PHASE3-DOC` approved.

---

## Acceptance criteria

- [x] Exactly **2–3** Phase 2 carryover IDs listed; all others marked deferred.
- [x] Phase 3 feature **order** is explicit (default or custom).
- [x] **Live provider** choice A, B, or C recorded with limitation sentence.
- [x] **Human labels** choice A, B, or C recorded (and N if B).
- [x] **`PHASE3_PLAN.md` creation** approved or explicitly rejected (if rejected,
  Phase 3 code remains blocked).
- [x] Workflow agreements confirmed.
- [x] [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) Phase 0 checkboxes updated to match.

---

## Decision record (fill in)

_Date completed: 2026-10-09_

### P0-CARRYOVER

**Selected (2–3):** P2-CI, P2-GALLERY, P2-OPS (lite: unsupported multi-process doc + one PostgreSQL restart smoke test; no load/concurrency claims)

**Deferred:** P2-LABEL, P2-PROV, P2-FIELDS, P2-DASH, P2-DUAL; full P2-OPS load/concurrency scope (superseded by OPS-lite)

**Notes:** Matches [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 1.2 draft recommendation (2026-10-09). P2-CI unblocks GitHub CI (manifest SHA on `origin/main`, LF migration checksum test). P2-GALLERY feeds paper discussion and Phase 3 failure clustering. Override in chat if you want only two carryovers (drop OPS-lite and defer P2-OPS to limitations-only).

### P0-P3-ORDER

**Order:** 1. Adaptive per-domain thresholds (vs global `0.95`)  2. Pattern-aware eviction (hit frequency + freshness class)  3. Strategy D (cross-encoder) conditional

**Strategy D gate (one line):** Implement D only if Strategy C’s **held-out** unsafe-serve / false-reuse rate remains above the pre-registered safety ceiling in `PHASE3_PLAN.md` after features 1–2 (and C threshold tuning); otherwise skip D and document C as sufficient.

**Deferred for v1 (not in ordered trio):** int8 embedding quantization, 1K→100K load tests, failure clustering as its own track (feeds from P2-GALLERY), experiment tracking unless manual artifacts fail—per [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 2.3.

### P0-PROVIDER

**Choice:** A (defer through Phase 3; consistent with P2-PROV deferred in P0-CARRYOVER)

**Paper limitation sentence:** Cost, latency, and token savings are measured under **synthetic replay** only; no credentialed live-provider run was available, so synthetic confidence intervals must not be reported as live API performance (see [`WORKSTREAM_5_EVIDENCE.md`](../phase-2/WORKSTREAM_5_EVIDENCE.md) Step 11).

### P0-LABELS

**Choice:** A (out of scope before paper; consistent with P2-LABEL deferred in P0-CARRYOVER)

**If B, N =** n/a

**Paper limitation sentence:** Primary evaluation uses **compatibility** and reuse-safety metrics; human factual-correctness labels were not collected at scale—`correctness.*` remains sparse or `not_collected` per [`EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md), and SAFE compatibility does not imply factual correctness.

### P0-PHASE3-DOC

**Approved:** yes (create `PHASE3_PLAN.md` as sole Phase 3 SOT; link from `phase-3/README.md` when the file lands; no Phase 3 code until plan written and P0-P3-ORDER re-read in that doc)

**Date:** 2026-10-09

### P0-WORKFLOW

**Confirmed:** yes (2026-10-09)

---

## Verification

Phase 0 has no pytest gate. Verification is **documentation only**:

- [x] Decision record complete.
- [x] Parent transition doc Phase 0 boxes match record.
