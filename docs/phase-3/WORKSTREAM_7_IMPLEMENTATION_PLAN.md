# Phase 3 Workstream 7 Implementation Plan

## Goal

Execute [Feature 4 — Failure clustering (manual synthesis)](./PHASE3_PLAN.md#feature-4--failure-clustering-manual-synthesis):
produce `PHASE3_FAILURE_CLUSTERS.md` from frozen evaluation JSON with no new
held-out replay.

**Status:** `ready` — card promoted 2026-10-11 (Workstream 1 Step 2).  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md) § Workstream 7.  
**Card:** `P3-FEAT-CLUSTER`.

## Learning objectives

- [ ] Derive cluster counts from report JSON without hand-waving totals.
- [ ] Separate Strategy B false positives from Strategy C safety discussion.
- [ ] Decide when a follow-up script is justified vs manual tables.

## Prerequisites

- [x] Feature 4 card complete in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- [x] Final held-out comparison exists:
      `artifacts/evaluation/phase3-final-held-out-comparison.json`.
- [ ] Pre-code checklist recorded in [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md).

## Implementation steps

### Step 1 — Extract primary sample

- [ ] Load `baselines.embedding-cache.false_positive_examples` from the final
      held-out comparison.
- [ ] Record `false_positive_rate`, example count, and report `git_commit` /
      config metadata from the JSON header.

### Step 2 — Build cluster keys

- [ ] Apply the deterministic key from Feature 4 (category, domain,
      freshness, rule/reason; missing → `unknown`).
- [ ] Label clusters with **≥ 2** examples; mark others `singleton`.

### Step 3 — Cross-check counts

- [ ] Sum of cluster counts equals Strategy B false-positive example count.
- [ ] Optionally cross-check category totals against
      `workstream7-quality-analysis.json` and attached `statistics` strata.

### Step 4 — Write evidence

- [ ] Publish [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md)
      (table: cluster key, count, mitigation, example pair IDs only).
- [ ] Note Strategy C FPR and empty or non-empty C false-positive list.
- [ ] Apply redaction: no unapproved raw query text.

### Step 5 — Close

- [ ] Mark Feature 4 pass/fail in evidence from card criteria.
- [ ] If pass: **do not** add clustering code (stopping rule).
- [ ] Update [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) if needed.

## Verification

No pytest required for manual doc-only pass. Optional sanity command:

```powershell
$env:PYTHONPATH='src'
python -c "import json; p='artifacts/evaluation/phase3-final-held-out-comparison.json'; d=json.load(open(p,encoding='utf-8')); b=d['baselines']['embedding-cache']; print(len(b.get('false_positive_examples',[])), b.get('false_positive_rate'))"
```

Record output in `PHASE3_FAILURE_CLUSTERS.md`.

## Out of scope

- Phase 2 WS7 consolidated artifact regeneration (already exists)
- New evaluate runs on held-out
- Automated ML clustering
