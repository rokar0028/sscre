# Phase 3 Workstream 7 Implementation Plan

## Goal

Execute [Feature 4 — Failure clustering (manual synthesis)](./PHASE3_PLAN.md#feature-4--failure-clustering-manual-synthesis):
deliver [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) from frozen
evaluation JSON with no new held-out replay.

**Status:** **closed** (Step 5, 2026-10-11). Feature 4 **pass**; no clustering code.  
**Evidence:** [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md).  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md) § Workstream 7.  
**Card:** `P3-FEAT-CLUSTER`.

## Gates

**Gate A — analysis preparation.** Confirm the frozen artifact paths and
available fields, then record the pre-code checklist in
[`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) (canonical) with a
summary row in [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md). No
replay or source code change is authorized by this plan.

**Gate B — evidence close.** Write
[`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md), reconcile every
Strategy B false-positive example to one row, and score the pre-registered
criteria. Add an export script only if the documented join and aggregation
cannot be reproduced manually; a script requires a new scope decision.

## Learning objectives

- [ ] Derive cluster counts from report JSON without hand-waving totals.
- [ ] Separate Strategy B false positives from Strategy C safety discussion.
- [ ] Decide when a follow-up script is justified vs manual tables.

## Prerequisites

- [x] Feature 4 card complete in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- [x] Final held-out comparison exists:
      `artifacts/evaluation/phase3-final-held-out-comparison.json`.
- [x] Pre-code checklist for Step 1 recorded in
      [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) and
      [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md).

## Frozen inputs and field mapping

Primary sample:

- `artifacts/evaluation/phase3-final-held-out-comparison.json`
  - `baselines.embedding-cache.false_positive_examples`
  - `baselines.embedding-cache.false_positive_rate`
  - `baselines.compatibility-cache.false_positive_examples`
    and `false_positive_rate`
  - report-level provenance fields

The Strategy B example rows may contain only `id`, `direction`, `reason`, and
`similarity`. Enrich them by joining on `(id, direction)` to
`artifacts/evaluation/workstream7-quality-analysis.json`,
`failure_gallery.embedding_only_false_positives[]`. Use its explicit
`failure_category`, `failure_category_display`, and `mitigation` fields.

If a join field is absent, use `unknown`; do not infer a category from free
text. Domain and freshness are also `unknown` unless explicitly present in a
frozen input. The quality artifact enriches and cross-checks the primary
sample; it is not a second false-positive denominator.

## Implementation steps

### Step 1 — Extract primary sample

- [x] Load `baselines.embedding-cache.false_positive_examples` without
      modifying the final held-out comparison.
- [x] Record `false_positive_rate`, example count, and report provenance.
- [x] Preserve each source example's `id` and `direction`.
      [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) § Step 1
      (2026-10-11): 13 examples, B FPR `0.48148148148148145`.

### Step 2 — Build cluster keys

- [x] Join the primary sample to the quality-analysis gallery by `(id,
      direction)` where available. 13 / 13 matched (2026-10-11).
- [x] Build the key in this order: `failure_category`,
      `metadata.domain`, `freshness_class`, and primary rule/reason code.
      Normalize missing fields to `unknown`.
- [x] Label keys with **at least 2** primary examples as recurring clusters;
      label one-example keys `singleton`. Two recurring keys (10 + 2) and one
      singleton (1).
- [x] Assign one mitigation per named cluster: `rule`, `benchmark`, or
      `none`. All three buckets map to **`rule`** with gallery rationale
      `compatibility_validator`.
      [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) § Step 2.

### Step 3 — Cross-check counts

- [x] Verify every primary example maps to exactly one cluster or singleton.
      13 / 13 (2026-10-11).
- [x] Verify cluster counts sum to Strategy B's
      `false_positive_examples` count. Sum **13**.
- [x] Cross-check category totals against
      `workstream7-quality-analysis.json`; record missing or duplicate joins.
      Gallery join 13 / 13; categories 10 / 2 / 1; aggregate stratum `n`
      fields documented as non-substitutes.
- [x] Keep Strategy C false-positive results separate from the B denominator.
      C FP count **0**.
      [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) § Step 3.

### Step 4 — Write evidence

- [x] Publish [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md)
      (table: cluster key, count, mitigation, example pair IDs only).
- [x] Note Strategy C FPR and its false-positive example count.
- [x] Record Feature 4 contrast slice: C `decision_counts`, `failure_examples`
      aggregates (`UNSAFE` / `UNCERTAIN`); not merged into B clusters.
      [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) § Step 4.
- [x] Include the exact read-only sanity command and its output.
- [x] Apply report redaction: no raw query text, answers, or credentials.
      [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) § Step 4
      (2026-10-11).

### Step 5 — Close

- [x] Score each Feature 4 criterion from recorded counts and joins.
      **pass** (2026-10-11).
- [x] If pass: **do not** add clustering code (stopping rule). No script or
      pipeline added.
- [x] Update [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) and the
      parent plan's WS7 status and acceptance boxes in the same pass.
      [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) § Step 5.

## Verification

No pytest is required for the manual, doc-only pass.

**Completed 2026-10-11** — outputs recorded in
[`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) § Step 1 (sanity),
§ Step 3 (cluster sum), § Step 4 (contrast aggregates).

Re-run from repo root after confirming artifact paths exist:

```powershell
$env:PYTHONPATH='src'
python -c "import json; p='artifacts/evaluation/phase3-final-held-out-comparison.json'; d=json.load(open(p,encoding='utf-8')); b=d['baselines']['embedding-cache']; c=d['baselines']['compatibility-cache']; print({'b_examples':len(b.get('false_positive_examples',[])),'b_fpr':b.get('false_positive_rate'),'c_examples':len(c.get('false_positive_examples',[])),'c_fpr':c.get('false_positive_rate'),'git_commit':d.get('git_commit'),'config_sha256':d.get('config_sha256')})"
```

Cluster-sum and contrast check:

```powershell
$env:PYTHONPATH='src'
python -c "import json; from collections import Counter; d=json.load(open('artifacts/evaluation/phase3-final-held-out-comparison.json',encoding='utf-8')); c=d['baselines']['compatibility-cache']; fe=c.get('failure_examples') or []; print({'primary_b_fps':len(d['baselines']['embedding-cache']['false_positive_examples']),'strategy_c_fps':len(c.get('false_positive_examples',[])),'c_decision_counts':c.get('decision_counts'),'c_failure_examples':len(fe),'c_predicted':dict(Counter(e.get('predicted_decision') for e in fe))})"
```

If a machine-readable export is needed to make grouping reproducible, first
document why the manual procedure failed; do not add it merely for convenience.

## Acceptance criteria

- [x] Every Strategy B held-out false-positive example appears exactly once in
      a cluster or singleton row.
- [x] Cluster counts are traceable to frozen JSON records; no hand-counted
      totals are used.
- [x] Strategy C safety results remain a separate comparison.
- [x] Evidence contains provenance, the sanity-command result, and redacted
      pair identifiers only.
- [x] No new held-out replay, threshold/eviction tuning, dependency, or
      product-code change was performed.

## Out of scope

- Phase 2 WS7 consolidated artifact regeneration (already exists)
- New evaluate runs on held-out
- Automated ML clustering
