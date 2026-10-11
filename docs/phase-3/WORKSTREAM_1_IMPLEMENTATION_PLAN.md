# Phase 3 Workstream 1 Implementation Plan

## Goal

Keep Phase 3 **hypothesis-driven**: every feature has a written, falsifiable
card in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) before code, and every evaluation
run respects development vs held-out discipline, protocol-reset rules, and
resource gates from the transition doc.

Workstream 1 is mostly **documentation and process**. It does not implement
cache, evaluation, or load-test code. It defines the registry, templates, and
checklists that Workstreams 2–9 (and any new Phase 3 slice) must satisfy.

```text
feature idea
    ↓
complete feature card in PHASE3_PLAN.md (hypothesis + pass/fail + artifacts)
    ↓
user OK for that slice (when required)
    ↓
development tuning only
    ↓
freeze config / policy artifacts
    ↓
one held-out replay (or documented deferral / N/A)
    ↓
evidence markdown + artifacts under artifacts/
```

**Status:** **closed (registry)** — 2026-10-11 (Steps 0–7). v1 Features 1–3
unchanged. Features 4–8 cards promoted; WS5–8 **execution** is separate. Reopen
only for new Phase 3 feature cards.

**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 1.

## Scope

### Included

- Feature card schema and required fields
- Registry of implemented, deferred, and open Phase 3 features
- Pre-code gate checklist (held-out, provider, GPU, fail-closed)
- Protocol-reset record template (post–final held-out runs)
- Promotion workflow for optional rows → full feature cards
- Evidence index for v1 gate closure

### Excluded

- Implementing adaptive thresholds, eviction, Strategy D, quantization, load
  tests, clustering code, or experiment trackers (other workstreams)
- Changing Strategies A / B / C definitions or WS5 baseline keys
- Retuning Features 1–2 on held-out data
- Commits or pushes without explicit user OK

## Learning objectives

- [ ] Write a falsifiable hypothesis and a pre-registered pass/fail criterion.
- [ ] Separate development tuning from a single final held-out report.
- [ ] Document a protocol reset without reusing held-out outcomes for tuning.
- [ ] Decide when an optional deferral row must become a full card before code.

## Source of truth

| Document | Role |
| --- | --- |
| [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) | Canonical feature cards and optional deferral table |
| [`../internal/PHASE3_TRANSITION.md`](../internal/PHASE3_TRANSITION.md) | Non-negotiable rules (held-out, numbers, branch/push) |
| [`../internal/PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md`](../internal/PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md) | P0-P3-ORDER, P0-PROVIDER, P0-LABELS |
| [`../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md) | v1 authoring steps and completion record |
| [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md) | Example protocol reset for a superseded held-out package |

Frozen evaluation inputs (do not redefine in new cards):

| Item | Value / path |
| --- | --- |
| Dataset | `reviewed-query-pairs-2.0` |
| Splits | 400 development / 215 held-out / 615 source |
| Development split file | `benchmarks/development.jsonl` |
| Held-out split file | `benchmarks/held_out_test.jsonl` |
| Config | `experiments/evaluation_config.json` (`evaluation-config-1.0`) |
| Safety cap | `max_false_positive_rate` **`0.0`** |
| Global Strategy C τ (reference) | **`0.95`** (development-selected, WS5) |
| Shipped stack (paper) | Feature 1 adaptive map + default/WS6 conservative eviction |
| Default measurement | `synthetic_replay` |

## Current baseline

### v1 registry (closed)

| ID | Feature | Card location | Implementation | Gate outcome |
| --- | --- | --- | --- | --- |
| `P3-FEAT-ADAPT` | Adaptive per-domain thresholds | `PHASE3_PLAN.md` Feature 1 | Done | **Pass** — [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md) |
| `P3-FEAT-EVICT` | Pattern-aware eviction | Feature 2 | Done | **Fail/defer** — [`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md) |
| `P3-FEAT-D` | Strategy D cross-encoder | Feature 3 | Not built | **Deferred** — trigger FPR `> 0.0` not met — [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) |

### Optional rows (defer table only — not full cards yet)

| ID | Item | v1 decision | Parent workstream |
| --- | --- | --- | --- |
| `P3-OPT-Q8` | int8 embedding quantization | Defer until float32 baseline | WS5 |
| `P3-OPT-LOAD` | Load 1K→100K simulated Q/day | Defer until card + approval | WS6 |
| `P3-OPT-CLUSTER` | Failure clustering | Manual OK; code deferred | WS7 |
| `P3-OPT-TRACK` | Experiment tracking | Defer until audit fails | WS8 |

### Open gate

- [x] Full feature cards exist for Workstreams 5–8 before their implementation
  starts (Features 4–8 in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md), 2026-10-11).

## Feature card template

Add or extend a section in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) using this
shape. Every field must be filled; no `TBD` in in-scope cards.

```markdown
### Feature N — <title>

**Order:** <n> · **Implementation ID:** `P3-...`

#### Hypothesis

One falsifiable sentence.

#### Scope (in / out)

Bullets stating what changes and what stays frozen (τ, TTL, baselines).

#### Development protocol (tuning allowed)

Numbered steps on `benchmarks/development.jsonl` only.
Name frozen output artifacts under `artifacts/evaluation/`.

#### Held-out protocol (evaluation only)

Single replay rules; reference comparison arm(s).

#### Pass / fail (pre-registered)

Pass iff … ; fail/stopping rule … ; no held-out retuning.

#### Primary metrics

Table mapping concerns → WS5 / freshness JSON field names.

#### Baselines

Arms and `--baseline` keys where applicable.

#### Effort

S / M / L estimate.

#### Evidence (paths to create at implementation time)

List `docs/phase-3/…` and `artifacts/…` targets.
```

Update the summary table at the top of **Feature cards** in `PHASE3_PLAN.md`
when a row is promoted from optional to in-scope.

## Non-negotiable gates (all workstreams)

These are copied from the parent plan so agents do not hunt across files.

1. **Card before code** — hypothesis, pass/fail, stopping rule, artifact names
   in `PHASE3_PLAN.md`.
2. **Development-only tuning** — `benchmarks/development.jsonl`; held-out labels
   and outcomes are not used to select thresholds, caps, or validator settings.
3. **Held-out discipline** — one final held-out report per paper stack unless a
   **protocol reset** is written first (see template below).
4. **No invented numbers** — tables and plans cite artifact paths and commands.
5. **Provider boundary** — synthetic and live-provider results in separate
   artifacts and tables (`P0-PROVIDER`).
6. **Labels** — compatibility-focused safety claims; sparse correctness
   (`P0-LABELS`) documented in limitations.
7. **Infrastructure** — no GPU rental or new heavy dependencies unless an
   approved profiling result requires them.
8. **Fail-closed** — `UNCERTAIN` and dependency failures never become cache
   hits; expired or dynamic candidates are not served.
9. **Branch / push** — feature branch; no `main` commit or `git push` without
   explicit user OK.

## Protocol reset template

Use when any held-out run after [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md)
is authorized (for example Phase 4 Pareto follow-up). Paste into the relevant
evidence file and link from `PHASE3_PLAN.md` if the protocol changes globally.

```markdown
## Protocol reset

**Date:** YYYY-MM-DD  
**Reason:** (e.g. diagnostic Pareto, reproducibility fix, new feature held-out)  
**What is unchanged:** dataset version, split manifest, safety cap, seeds,  
  development-selected policies (τ map, TTL, eviction).  
**What is new:** (e.g. additional held-out replay label, CLI flag fix)  
**Tuning forbidden:** held-out labels/outcomes were not used to change …  
**Artifacts superseded:** (paths)  
**New artifacts:** (paths)  
**Git commit / config SHA-256:** (record after run)
```

Example: [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md) § Protocol reset.

## Pre-code gate checklist

Complete before the first line of implementation for a new card. Record the
date and approver in the workstream evidence file.

- [ ] Feature card merged in `PHASE3_PLAN.md` (all template sections complete).
- [ ] Implementation ID matches parent workstream in
      [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md).
- [ ] Frozen baselines and config paths cited; Strategies A/B/C not redefined.
- [ ] Development and held-out protocols explicitly separated.
- [ ] Pass/fail and stopping rules are numeric or boolean where possible
      (e.g. FPR `≤ 0.0`, not “better”).
- [ ] Artifact filenames listed and prefixed consistently (`phase3-…`).
- [ ] User OK obtained for this slice when the transition doc or chat requires it.
- [ ] No scope creep from P2-DASH, P2-DUAL, live provider, or capacity claims
      unless a new decision record promotes them.

## Implementation steps

### Step 0 — Confirm v1 registry (read-only)

**Track ID:** `P3-WS1-INVENTORY`

- [x] Verify Features 1–3 cards in `PHASE3_PLAN.md` have hypothesis and pass/fail.
- [x] Verify Strategy D trigger and stopping rules in Feature 3.
- [x] Verify optional deferral table (`P3-OPT-*`) matches Phase 0 order and
      [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md).
- [x] Record v1 authoring closure in
      [`../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md).

Evidence: [`WORKSTREAM_1_STEP0_INVENTORY.md`](./WORKSTREAM_1_STEP0_INVENTORY.md)
(2026-10-11).

### Step 1 — Publish this workstream plan

**Track ID:** `P3-WS1-PLAN`

- [x] Add [`WORKSTREAM_1_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_1_IMPLEMENTATION_PLAN.md).
- [x] Link from [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
      Workstream 1 section.
- [x] Add row to [`README.md`](./README.md) index.

Evidence: [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) § Step 1
(2026-10-11). Cross-link from [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Working
agreements.

### Step 2 — Promote Workstream 7 card (failure clustering)

**Track ID:** `P3-WS1-CARD-CLUSTER` · **Blocks:** WS7 code (if any)

Draft content starts in [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
Workstream 7. Promote `P3-OPT-CLUSTER` to a full **Feature card** or a named
**Phase 3 extension** section in `PHASE3_PLAN.md`:

- [x] Hypothesis: manual (or scripted) grouping of held-out failures reduces
      anecdotal discussion without new replay.
- [x] Pass/fail: every Strategy B held-out false positive assigned to a cluster
      or singleton; counts trace to JSON fields.
- [x] Stopping rule: if manual grouping is complete, **do not** add clustering
      code in v1.
- [x] Evidence target: `docs/phase-3/PHASE3_FAILURE_CLUSTERS.md` (card); execution
      in [`WORKSTREAM_7_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_7_IMPLEMENTATION_PLAN.md).

Card: [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 4 (`P3-FEAT-CLUSTER`, 2026-10-11).

### Step 3 — Promote Workstream 8 card (experiment tracking)

**Track ID:** `P3-WS1-CARD-TRACK` · **Blocks:** WS8 tooling

- [x] Hypothesis: manual artifacts are insufficient for reproducibility.
- [x] Pass/fail: audit pass if every Phase 3/4 result has command, commit,
      config hash, dataset version, split manifest, seed; else document tracker
      choice or manifest fix.
- [x] Stopping rule: **no** MLflow/W&B dependency if audit passes.
- [x] Evidence target: decision in `PHASE3_PLAN.md` Feature 5 decision table +
      [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md).

Card: [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 5 (`P3-FEAT-TRACK`, 2026-10-11).

### Step 4 — Promote Workstream 5 card (storage + quantization)

**Track ID:** `P3-WS1-CARD-Q8` · **Blocks:** WS5 code

Split into two gated sub-cards if helpful (baseline measure vs quantization test):

- [x] **5a Baseline** — measure float32 embedding bytes on development scale;
      stopping rule if embeddings are not a dominant byte share.
- [x] **5b Quantization** — only if 5a justifies; pass/fail from parent plan
      (≥ 3.5× byte reduction, FPR `0.0`, hit rate not lower on development).
- [x] Confirm fake-embedding limitation text in the card.
- [x] Evidence targets: `PHASE3_QUANTIZATION_EVIDENCE.md`, artifacts
      `phase3-embedding-storage-baseline.json`, `phase3-quantization-development.json`.

Cards: [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Features 6–7 (`P3-FEAT-EMBED-BASE`,
`P3-FEAT-Q8`, 2026-10-11). Confirm thresholds in card before Feature 7 **code**.

### Step 5 — Promote Workstream 6 card (load ladder)

**Track ID:** `P3-WS1-CARD-LOAD` · **Blocks:** WS6 code

- [x] Hypothesis and ladder steps (1K / 10K / 100K simulated Q/day) documented.
- [x] Pre-register p95 and error **budgets per step** (in-memory p95 ≤ 500 ms,
      PostgreSQL p95 ≤ 3000 ms, non-fixture error/timeout ≤ 1%).
- [x] Stopping rule: first reproducible bottleneck or `not_reached` at 100K/day.
- [x] Explicitly **not** a production SLA; separate from WS8 and Phase 4 32-request profiles.
- [x] Evidence target: `PHASE3_LOAD_EVIDENCE.md`, artifacts under
      `artifacts/operations/phase3-load-ladder-*.json`.

Card: [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 8 (`P3-FEAT-LOAD`, 2026-10-11).
Change budgets only via written protocol update before runs.

### Step 6 — Strategy D re-check gate (conditional)

**Track ID:** `P3-WS1-GATE-D`

Not a new card unless the trigger fires again.

- [x] Document trigger: final stack held-out FPR **`> 0.0`** (Feature 3).
- [x] After Workstream 1 card promotions (2026-10-11), re-evaluated trigger from
      the **frozen** final held-out artifact — no benchmark/policy change; FPR still
      **`0.0`**; D not authorized.
- [x] Future rule documented: re-check required after benchmark or shipped-policy
      change and before D code; protocol reset if a **new** held-out run invokes D.

Evidence: [`WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md`](./WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md).

### Step 7 — Close Workstream 1 (registry)

**Track ID:** `P3-WS1-CLOSE`

- [x] All open cards (Steps 2–5) checked in `PHASE3_PLAN.md` (Features 4–8).
- [x] Parent plan Workstream 1 acceptance:
      “Cards exist for Workstreams 5–8” marked complete.
- [x] Record completion in
      [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) (v1 closure +
      card promotion dates).
- [x] No code changes required for Step 7 unless a optional validator script is
      added later (YAGNI: defer).

Evidence: [`WORKSTREAM_1_STEP7_CLOSE.md`](./WORKSTREAM_1_STEP7_CLOSE.md) (2026-10-11).

## Execution sequence

1. [x] Step 0 — v1 inventory verified.
2. [x] Step 1 — this plan and index links.
3. [x] Step 2 — cluster card (`P3-OPT-CLUSTER` → Feature 4).
4. [x] Step 3 — tracking audit card (`P3-OPT-TRACK` → Feature 5).
5. [x] Step 4 — storage/quantization card(s) (`P3-OPT-Q8` → Features 6–7).
6. [x] Step 5 — load ladder card (`P3-OPT-LOAD` → Feature 8).
7. [x] Step 6 — Strategy D gate re-check (2026-10-11; trigger not fired).
8. [x] Step 7 — registry close and evidence file.

Workstreams 5–8 implementation plans should reference the promoted card section
by anchor and Implementation ID.

## Acceptance criteria

### v1 (Features 1–3)

- [x] Every in-scope v1 feature has a complete card in `PHASE3_PLAN.md`.
- [x] Strategy D stopping rule and default defer path documented.
- [x] Phase 3 code ran only after user OK (2026-10-10) per transition § 2.4.
- [x] Authoring evidence in
      [`../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md).

### Reopen (Workstreams 5–8) — closed 2026-10-11

- [x] Four promoted cards (or equivalent named sections) exist with no `TBD`
      in Features 4–8 card bodies (see Step 7 TBD note).
- [x] Pre-code checklist template + per-WS pending table in evidence (before code).
- [x] Protocol reset template available for any new held-out run.
- [x] [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) lists card IDs,
      approval dates, and links to child workstream plans.

## Verification commands

Workstream 1 is documentation-only; verify repo state before marking Step 7:

```powershell
python -m sscre.benchmark_validate --phase2 --production
```

Optional manual review (no automated gate unless a script is added later):

- Search `PHASE3_PLAN.md` for `TBD` in sections tied to open workstreams.
- Confirm each promoted card lists artifact paths under `artifacts/`.

Record results in [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md).

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Code starts without a card | Pre-code checklist; parent plan blocks WS5–8 until cards exist |
| Held-out leakage | Development-only tuning spelled out in each card; protocol reset for extra runs |
| Optional row never promoted | Steps 2–5 map `P3-OPT-*` to concrete cards |
| Strategy D built without trigger | Feature 3 precondition + Step 6 re-check |
| Synthetic vs live mixed | P0-PROVIDER gate in every card limitations |
| Invented metrics in cards | Require JSON field names from WS5/freshness contracts |

## Out of scope

- Implementing Features 1–3 (historical; see feature evidence files)
- Phase 4 tracks (separate plan)
- Editing `SSCRE_PLAN.md` checkboxes (Workstream 9)

## Handoff

| Consumer | Uses from WS1 |
| --- | --- |
| Workstream 5 | Promoted `P3-OPT-Q8` card, baseline-before-quantization gate |
| Workstream 6 | Promoted `P3-OPT-LOAD` card with budgets |
| Workstream 7 | Promoted cluster card; manual-first stopping rule |
| Workstream 8 | Tracking audit card |
| Workstream 9 | Registry complete before master-plan checkbox sync |

When Steps 2–5 are complete, create or update child plans:
`WORKSTREAM_5_IMPLEMENTATION_PLAN.md` (etc.) following the Phase 2 naming pattern.
