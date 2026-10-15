# Post–Phase 4 Workstream 5 — Fresh held-out construction (assisted)

## Goal

Build a **new** held-out scoring population so the pre-registered Strategy C
versus Strategy A headline gate can run once, without reusing the contaminated
215-record split and without treating assistant drafts as human review.

**Status:** `closed` — headline gate scored **pass** on fresh held-out (Step 7
synced 2026-10-15)

**Evidence:** [`POST_PHASE4_WS5_FRESH_HELD_OUT_EVIDENCE.md`](./POST_PHASE4_WS5_FRESH_HELD_OUT_EVIDENCE.md)

**Parent:** [`docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md) Workstream 5

**Card:** [`docs/phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`](../phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md)
(`P4-SEMVALID` primary pass/fail). Do not invent a different decision path.

**Operator:** The user is the only **final** labeler. The assistant drafts
candidates and labels (`review_status: draft` only).

## Authoring gate vs execution gates

**Authoring exit:** This document, the evidence stub, and parent/index links
exist. Authoring does **not** authorize extract, freeze, or headline scoring.

**Execution exit:** A frozen fresh manifest exists, human `review_status: final`
covers every scored pair, one local-embedding A/B/C run completes, and the
pre-registered scorer records `pass`, `fail`, or `deferred` (not a silent skip).

- [x] Authoring deliverable exists (this plan + evidence stub + parent pointer).
- [x] User written OK to start Step 1 extract (2026-10-15).
- [x] User written OK that the review batch is final (Step 4 freeze; 2026-10-15
      chat `next`).
- [x] User written OK to run the one held-out evaluation (Step 6; 2026-10-15
      chat `ok next`).

## Current baseline

- Existing 615 pairs (`reviewed-query-pairs-2.0`): 400 development / 215
  held-out. The 215-row [`benchmarks/held_out_test.jsonl`](../../benchmarks/held_out_test.jsonl)
  is **contaminated for headline use**
  ([`benchmarks/semantic-validity-held-out-gate.json`](../../benchmarks/semantic-validity-held-out-gate.json)).
- Relabeling or re-splitting those 215 rows as “fresh” is **forbidden**.
- Development thresholds stay frozen (`τ=0.9` fallback on development;
  [`PHASE4_STEP5_THRESHOLD_DECISION.md`](../phase-4/PHASE4_STEP5_THRESHOLD_DECISION.md)).
  Fresh held-out results must **not** retune τ.
- Licensed CacheEval pool after commercial filter: **1945** retained rows
  ([`benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json`](../../benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json)).
  About **583** already entered the 615. Unused filtered rows are the default
  source for this batch.
- Filtered JSONL
  [`benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl`](../../benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl)
  is **gitignored**; regenerate locally with
  [`benchmarks/candidates/tools/filter_cacheeval_commercial.py`](../../benchmarks/candidates/tools/filter_cacheeval_commercial.py).
- Local embeddings (`all-MiniLM-L6-v2`, 384-d) are enough. No Gemini. No
  `SSCRE_API_EXPOSURE_MODE=external`.

### Open baseline gaps

- [ ] Local `cacheeval_v1_filtered.jsonl` is not in git; Step 1 must regenerate
      it or stop as `unavailable`.
- [x] Dedicated fresh files
      `benchmarks/fresh_held_out.jsonl` and
      `benchmarks/fresh_held_out_manifest.json` frozen (Step 4, 2026-10-15).

## Roles

| Role | May do | Must not do |
| --- | --- | --- |
| Assistant | Extract unused rows, schema/IDs, draft labels, validate, freeze **after** user OK, run eval once | Mark `review_status: final`; change τ after seeing held-out scores; reuse 215-row split |
| User | Keep / change / drop every draft pair; written freeze OK; written eval OK | Skip reading pairs and still call the set human-reviewed |

## Pre-registered pass/fail (do not change)

From `experiments/semantic-validity-evaluation-config-v1.json` and the P4 card.

On the **fresh** primary population, Strategy C must:

- strictly exceed Strategy A **safe-reuse coverage**
- stay at or below **FPR cap 0.0** on labeled served reuse
- stay at or below **abstention ceiling 0.5**
- record **zero** unlabeled served-candidate reuse for the headline result

A **fail** is a valid scientific outcome (keep conservative stack). Do not
weaken safety rules to raise reuse. R1.1 already showed C is very conservative
on development; this batch may still **fail**.

## Batch design (first freeze)

Default first freeze: **80** pairs (user may say 50 or 100 before Step 1).

Draft sampling **targets** (not a scored metric):

| Kind | Approx share | Why |
| --- | --- | --- |
| Compatible / paraphrase | ~30% | Need reusable opportunities for coverage |
| Incompatible | ~50% | Need labeled negatives so FPR is defined |
| Uncertain | ~20% | Matches C abstention behavior |

All pairs: schema `1.1`, new IDs after `pair-0615`,
`source_group` from [`benchmarks/source_inventory.json`](../../benchmarks/source_inventory.json),
`annotation_source: assistant_draft` until the user finals them,
`correctness_label: null` (WS6 stays out of scope).

Held-out only: **do not** merge into `development.jsonl` or replace
`held_out_test.jsonl`. New files only.

## Step 1 — Extract unused licensed candidates

- [x] User has written OK to start extract (execution gate).
- [x] Confirm every tool path below exists before running it.
- [x] Regenerate gitignored filtered CacheEval JSONL (or record `unavailable`).
      Used existing local filtered file (`used_existing_filtered`; see evidence).
- [x] Convert with
      [`convert_cacheeval_candidates.py`](../../benchmarks/candidates/tools/convert_cacheeval_candidates.py)
      via
      [`extract_fresh_held_out_draft.py`](../../benchmarks/candidates/tools/extract_fresh_held_out_draft.py).
- [x] Drop any pair whose normalized `(query_a, query_b)` key collides with
      [`reviewed_query_pairs.jsonl`](../../benchmarks/reviewed_query_pairs.jsonl),
      [`development.jsonl`](../../benchmarks/development.jsonl), or
      [`held_out_test.jsonl`](../../benchmarks/held_out_test.jsonl).
- [x] Sample the agreed batch size with the mix targets above (80 pairs;
      24 / 40 / 16 mix).
- [x] Write draft JSONL
      `benchmarks/candidates/fresh_held_out_draft.jsonl`
      (`review_status: draft` only).

**Step 1 gate:** Stop if the filtered file cannot be rebuilt or leftover
licensed rows are too few after collision drop. Record `unavailable`; do not
pad with the old 215.

## Step 2 — Draft labels and review sheet

- [x] Map CacheEval `EQUIV` / `PARA_SAFE` / mismatch classes to
      compatible / incompatible / uncertain using the existing converter
      rules, then re-check against
      [`ANNOTATION_GUIDE_v1.md`](../../benchmarks/ANNOTATION_GUIDE_v1.md).
      (`fresh_held_out_annotation.py`; 16 anaphor/deictic rows → `uncertain`).
- [x] Write a compact review sheet
      `benchmarks/candidates/fresh_held_out_review.md`
      (id, query A, query B, draft label, keep/change/drop).
- [x] Redact: no secrets, personal data, or full provider transcripts.

**Step 2 gate:** Drafts remain `draft`. Do not freeze.

## Step 3 — Human review (user)

- [x] User marks every row keep, change (new label), or drop (2026-10-15 chat:
      **keep all** at Step 2 draft labels; no drops or relabels).
- [x] Assistant applies edits; dropped rows never enter the freeze.
- [x] Every kept row has `review_status: final`, `annotation_source: human_review`,
      and a non-null `compatibility_label`
      (`benchmarks/candidates/fresh_held_out_reviewed.jsonl`, 80 rows).
- [x] Count remaining pairs. If below **40** after drops, either pull a top-up
      (repeat Steps 1–3) or stop and keep headline **deferred** (80 ≥ 40).

**Step 3 gate:** No freeze until the user writes that the batch is final.

## Step 4 — Freeze manifest (before any score look)

- [x] User written OK to freeze.
- [x] Write `benchmarks/fresh_held_out.jsonl` (finals only, 100 rows).
- [x] Write `benchmarks/fresh_held_out_manifest.json` with SHA-256 of the
      JSONL, pair ids, source/license, dataset version
      `fresh-held-out-1.0`, commit, and `held_out_influence: none`.
- [x] Point
      [`semantic-validity-held-out-gate.json`](../../benchmarks/semantic-validity-held-out-gate.json)
      at that manifest and set status `fresh-held-out-ready` **only after**
      the freeze hashes are recorded.
- [x] Do not inspect C-versus-A metrics before this freeze (no Step 6 run at
      freeze close).

## Step 5 — Harness fail-closed on the new paths

- [x] Confirm [`src/sscre/evaluate.py`](../../src/sscre/evaluate.py)
      `--benchmark` can take `benchmarks/fresh_held_out.jsonl` without
      silently scoring `held_out_test.jsonl` (explicit path; 100 vs 215 rows).
- [x] Confirm
      [`src/sscre/semantic_validity_held_out.py`](../../src/sscre/semantic_validity_held_out.py)
      and [`src/sscre/semantic_validity_gate.py`](../../src/sscre/semantic_validity_gate.py)
      still reject the old 215-row file as headline input.
- [x] Add or extend tests so a contaminated path cannot be marked
      `fresh-held-out-ready` (`validate_fresh_held_out_gate_record`).
- [x] Keep `python -m sscre.benchmark_validate` passing on the **existing**
      615-pair artifact (do not require the fresh file inside `--phase2`
      unless the validator is explicitly extended).

## Step 6 — One local-embedding evaluation

- [x] User written OK to run (2026-10-15 chat `ok next`).
- [x] Run A/B/C **once** on the frozen fresh file with local MiniLM, `τ=0.9`,
      config
      [`experiments/semantic-validity-evaluation-config-v1.json`](../../experiments/semantic-validity-evaluation-config-v1.json).
- [x] Score the pre-registered rule without changing it (gate artifact
      `phase4-semantic-validity-gate.json` → **pass**).
- [x] Write
      `artifacts/evaluation/phase4-semantic-validity-held-out.json`
      (or keep the deferred artifact if the run is blocked).
- [x] Record `pass`, `fail`, or `deferred` in evidence. Never convert unrun
      into pass/fail (**pass** recorded).

## Step 7 — Evidence close

- [x] Update
      [`POST_PHASE4_WS5_FRESH_HELD_OUT_EVIDENCE.md`](./POST_PHASE4_WS5_FRESH_HELD_OUT_EVIDENCE.md)
      with commands, hashes, mix counts, and the gate verdict.
- [x] Sync parent Workstream 5 checkboxes only for steps that actually ran
      (2026-10-15).
- [x] Leave WS6 (factual correctness) deferred unless the user later requires
      it.

## Verification (authoring)

- [x] Linked parent, P4 card, benchmark, config, gate JSON, and tool paths
      exist in this checkout (filtered JSONL is gitignored; listed as a gap).
- [x] Extract command run 2026-10-15 (`extract_fresh_held_out_draft.py`; evidence).
- [x] Fresh JSONL frozen at Step 4 close (not applicable to authoring-only
      snapshot).

## Out of scope for this document

- External API mode, Gemini / Gate C live calls, multi-worker deploy.
- Replacing or relabeling `held_out_test.jsonl` as fresh.
- Changing Strategy C rules or `τ` after seeing held-out scores.
- Factual correctness labels (Workstream 6).
- Merging the fresh set into the 400-row development split.
- WS7 CI jobs except tests added in Step 5.

## Stopping rule

If licensed unused rows cannot be rebuilt, review does not finish, or the
user does not freeze, keep Gate D / WS5 **deferred**. That remains an honest
close.
