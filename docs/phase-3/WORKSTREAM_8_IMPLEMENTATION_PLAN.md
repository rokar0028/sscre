# Phase 3 Workstream 8 Implementation Plan

## Goal

Execute [Feature 5 — Experiment-tracking gate (manual audit)](./PHASE3_PLAN.md#feature-5--experiment-tracking-gate-manual-audit):
decide whether manual artifacts are sufficient or a tracker is required.

**Status:** **closed** (Step 5, 2026-10-12). Feature 5 audit **pass**; **`keep_manual`**.
**Evidence:** [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md).
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md) § Workstream 8.
**Card:** `P3-FEAT-TRACK`.

**Not** Phase 2 operational verification ([`../phase-2/WORKSTREAM_8_IMPLEMENTATION_PLAN.md`](../phase-2/WORKSTREAM_8_IMPLEMENTATION_PLAN.md)).

## Learning objectives

- [ ] List minimum provenance fields for a reproducible paper result.
- [ ] Distinguish manifest-fixable gaps from tracker-level gaps.
- [ ] Avoid adding infrastructure when evidence + JSON already suffice.

## Prerequisites

- [x] Feature 5 card complete in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- [x] Audit scope is read-only; no product-code or held-out replay change is
      authorized by this plan.
- [x] Confirm every referenced manifest, evidence file, and artifact path exists
      before recording verification results (2026-10-11;
      [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) § Step 1).

## Gates and stopping rules

**Gate A — corpus and protocol.** Confirm the audit inputs below and record the
provenance fields before scoring any gap. Do not repair files during the audit.

**Gate B — decision.** Score the Feature 5 pre-registered pass/fail rule
([`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 5) and record one decision label:

- **`keep_manual`** — audit **pass**: Phase 4 manifest paths resolve,
  `repro_blocked_gaps = 0`, and final held-out provenance is in evidence and/or
  JSON. **`manifest_fixable_gaps` alone do not override pass**; list optional
  doc hygiene (e.g. G1–G5) without changing the decision.
- **`manifest_fix_only`** — audit **fail** with **`repro_blocked_gaps ≥ 1`**, but
  every gap can close via manifest or evidence within one session (no tracker).
  Do not install a tracker for this case alone.
- **`tracker_required`** — recommendation only when provenance stays
  unreconstructable after that documentation check; MLflow/W&B need separate
  user approval.

Do not run evaluations, access held-out data, rewrite historical artifacts,
or change application code during the audit.

## Implementation steps

### Step 1 — Load audit corpus

Minimum corpus: Feature 5 card in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md). Extended
scope (parent Workstream 8): every Phase 3/4 **paper result**, including
Features 6–8 evidence ([`PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md),
[`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md),
[`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md)) for matrix rows R06–R09.

- [x] Read `artifacts/evaluation/phase4-paper-artifact-manifest.json`.
- [x] Read `artifacts/evaluation/phase3-paper-artifact-manifest.json`.
- [x] Read [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md) and
      comparison JSON metadata.
- [x] Read feature evidence:
      `PHASE3_FEATURE_1_EVIDENCE.md`, `PHASE3_FEATURE_2_EVIDENCE.md`,
      `PHASE3_FEATURE_3_EVIDENCE.md`, and `PHASE3_ARTIFACTS_EVIDENCE.md`.
- [x] Read extended Phase 3 paper-result evidence (parent WS8 scope):
      `PHASE3_QUANTIZATION_EVIDENCE.md`, `PHASE3_LOAD_EVIDENCE.md`,
      `PHASE3_FAILURE_CLUSTERS.md`.
- [x] Read the relevant verification logs in
      [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) and
      [`../internal/PHASE4_IMPLEMENTATION_PLAN.md`](../internal/PHASE4_IMPLEMENTATION_PLAN.md).
- [x] List each `tracks.*.artifacts[].path` and each preview-manifest
      `sources.*` path; normalize `\` to `/` for repo-root resolution.
      [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) § Step 1
      (2026-10-11): Phase 4 **4/4** paths exist; preview **6/6** sources exist.

### Step 2 — Provenance matrix

Create one row per paper result, not merely one row per manifest track. Mark
each field `present`, `missing`, or `deferred-with-reason`:

| Field | Required |
| --- | --- |
| Command or generator | yes |
| Git commit (or dirty note) | yes |
| Config path + SHA-256 | yes |
| Dataset version | yes |
| Split proof | yes (see note below) |
| Seed / statistics block | yes when CIs reported |
| File exists on disk | yes |

Split proof: use `split_manifest_sha256` for held-out evaluate runs; otherwise
Feature 5 equivalents (`development_sha256`, `workload_sha256`, or benchmark
block for non–held-out workloads).

Use the Phase 4 manifest as the primary machine-readable index. Treat the
Phase 3 manifest as a historical preview and record any stale or superseded
entries rather than silently substituting them.

- [x] Matrix recorded for **14** paper results in
      [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) § Step 2
      (2026-10-12).

### Step 3 — Classify gaps

- [x] Count `artifacts_in_manifest`, `artifacts_missing_on_disk`, and
      `results_audited`. **4** / **0** / **14** (2026-10-12).
- [x] Count `manifest_fixable_gaps` and `repro_blocked_gaps` per Feature 5.
      **5** / **0**.
- [x] Classify each gap with its field, result, source, and proposed
      documentation-only remedy.
      [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) § Step 3 (G1–G5).
- [x] Note known deferrals (clean-checkout replay, preview manifest stale
      status) only when an explicit reason is recorded.
- [x] Confirm that missing uncertainty fields are not gaps for point estimates
      without confidence intervals.

### Step 4 — Record decision

- [x] Write [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) with the
      corpus, audit table, counts, gap classifications, and decision.
      § Step 4 (2026-10-12): **`keep_manual`**, audit **pass**.
- [x] Fill the **Feature 5 decision** table in `PHASE3_PLAN.md` with the audit
      date, decision, and `repro_blocked_gaps` count.
- [x] If `keep_manual`, confirm no tracker dependency was added.
- [x] If `manifest_fix_only`, record the doc-only follow-up without marking
      the audit itself as fixed. N/A — decision is `keep_manual`; G1–G5 optional
      follow-up recorded in evidence § Step 4.
- [x] If `tracker_required`, record the named gap and wait for user approval
      before any dependency or integration work. N/A.

### Step 5 — Close

- [x] Update [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) with the
      completed audit and decision (2026-10-12).
- [x] Update the parent plan's Workstream 8 status and acceptance checkboxes
      in the same pass.
- [x] If `manifest_fix_only`, open a doc-only fix task (no tracker) and leave
      the fix unchecked until verified. N/A (`keep_manual`); optional G1–G5 noted
      in evidence § Step 5 for Workstream 9.

## Verification

Required path-resolution check (PowerShell, repo root), after confirming all
referenced files and options exist:

```powershell
python -c "import json, pathlib; m=json.load(open('artifacts/evaluation/phase4-paper-artifact-manifest.json',encoding='utf-8')); paths=[a['path'].replace(chr(92),'/') for t in m.get('tracks',{}).values() for a in t.get('artifacts',[])]; missing=[p for p in paths if not pathlib.Path(p).exists()]; print('listed',len(paths),'missing',len(missing)); [print('MISSING',p) for p in missing]"
```

Manifest paths use forward slashes; normalize `\` before resolving from repo root.
Record the command and output in evidence (closed run: `listed 4 missing 0`,
[`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) § Step 5). Do not treat the preview manifest
alone as a failure if the Phase 4 manifest covers the final artifact.

The audit is a documentation/provenance review; no pytest or benchmark replay
is required. If a script is added to make counting reproducible, it must be
read-only, use only the frozen corpus, and be justified in the evidence before
it is added.

## Acceptance criteria

- [x] Audit corpus and manifest path counts are recorded.
- [x] Every in-scope paper result has a provenance-matrix row.
- [x] Every missing field is classified as `manifest_fixable` or
      `repro_blocked`, with a documented reason.
- [x] `repro_blocked_gaps` is scored against the pre-registered rule (**0**).
- [x] Decision is recorded in this plan's evidence and in `PHASE3_PLAN.md`.
- [x] No tracker dependency, evaluation replay, held-out access, or product-code
      change occurs as part of the audit.

## Out of scope

- MLflow / W&B / similar installs
- Phase 2 PostgreSQL load verification
- Re-running held-out evaluations
