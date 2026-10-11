# Phase 3 Workstream 8 Implementation Plan

## Goal

Execute [Feature 5 — Experiment-tracking gate (manual audit)](./PHASE3_PLAN.md#feature-5--experiment-tracking-gate-manual-audit):
decide whether manual artifacts are sufficient or a tracker is required.

**Status:** `ready` — card promoted 2026-10-11 (Workstream 1 Step 3).  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md) § Workstream 8.  
**Card:** `P3-FEAT-TRACK`.

**Not** Phase 2 operational verification ([`../phase-2/WORKSTREAM_8_IMPLEMENTATION_PLAN.md`](../phase-2/WORKSTREAM_8_IMPLEMENTATION_PLAN.md)).

## Learning objectives

- [ ] List minimum provenance fields for a reproducible paper result.
- [ ] Distinguish manifest-fixable gaps from tracker-level gaps.
- [ ] Avoid adding infrastructure when evidence + JSON already suffice.

## Prerequisites

- [x] Feature 5 card complete in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- [ ] Pre-code checklist N/A (read-only audit; no product code).

## Implementation steps

### Step 1 — Load audit corpus

- [ ] Read `artifacts/evaluation/phase4-paper-artifact-manifest.json`.
- [ ] Read Phase 3 final evidence and comparison JSON metadata.
- [ ] List each `tracks.*.artifacts[].path` and preview manifest `sources.*`.

### Step 2 — Provenance matrix

For each result row, mark present / missing:

| Field | Required |
| --- | --- |
| Command or generator | yes |
| Git commit (or dirty note) | yes |
| Config path + SHA-256 | yes |
| Dataset version | yes |
| Split manifest SHA-256 | yes |
| Seed / statistics block | yes when CIs reported |
| File exists on disk | yes |

### Step 3 — Classify gaps

- [ ] Count `manifest_fixable_gaps` and `repro_blocked_gaps` per Feature 5.
- [ ] Note known deferrals (clean-checkout replay, preview manifest stale status).

### Step 4 — Record decision

- [ ] Write [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md) with counts and decision.
- [ ] Fill **Feature 5 decision** table in `PHASE3_PLAN.md`.
- [ ] If `keep_manual`: confirm no tracker dependency added.

### Step 5 — Close

- [ ] Update [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) promotion row.
- [ ] If `manifest_fix_only`: open a doc-only fix task (no tracker).

## Verification

Optional path resolution (PowerShell, repo root):

```powershell
python -c "import json, pathlib; m=json.load(open('artifacts/evaluation/phase4-paper-artifact-manifest.json',encoding='utf-8')); paths=[]; 
for t in m.get('tracks',{}).values():
  for a in t.get('artifacts',[]):
    paths.append(a['path'].replace('\\\\','/'))
missing=[p for p in paths if not pathlib.Path(p).exists()]
print('listed',len(paths),'missing',len(missing))
for p in missing: print('MISSING',p)"
```

Record counts in evidence; do not treat preview manifest alone as fail if Phase 4
manifest covers final artifacts.

## Out of scope

- MLflow / W&B / similar installs
- Phase 2 PostgreSQL load verification
- Re-running held-out evaluations
