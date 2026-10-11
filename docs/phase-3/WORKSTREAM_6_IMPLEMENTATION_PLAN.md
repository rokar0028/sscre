# Phase 3 Workstream 6 Implementation Plan

## Goal

Execute [Feature 8 — Simulated load ladder](./PHASE3_PLAN.md#feature-8--simulated-load-ladder-1k100k-qday):
1K → 10K → 100K simulated Q/day with pre-registered budgets and bottleneck
identification.

**Status:** `ready` — card promoted 2026-10-11 (Workstream 1 Step 5).  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md) § Workstream 6.  
**ID:** `P3-FEAT-LOAD`.

**Not** Phase 2 freshness experiments ([`../phase-2/WORKSTREAM_6_IMPLEMENTATION_PLAN.md`](../phase-2/WORKSTREAM_6_IMPLEMENTATION_PLAN.md)).

## Learning objectives

- [ ] Map simulated Q/day to bounded local request counts.
- [ ] Separate fixture failures from protocol failures in error rates.
- [ ] Stop at first reproducible bottleneck without optimizing.

## Prerequisites

- [x] Feature 8 card in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) with budgets.
- [ ] User OK for load runs if PostgreSQL or long runs are requested.
- [ ] Pre-code checklist before harness changes.

## Implementation steps

### Step 1 — Workload config

- [ ] Add `experiments/phase3_load_ladder_v1.json` (or documented equivalent)
      with L1/L2/L3 request counts, concurrency, repeat ratio, cache caps.
- [ ] Document query sampling from `benchmarks/development.jsonl`.

### Step 2 — Harness

- [ ] Extend `src/sscre/load_test.py` for ladder steps and component p95 shares.
- [ ] Exclude labeled failure fixtures from `non_fixture_error_rate`.
- [ ] Tests in `tests/test_load_test.py` (or new file) for ladder metadata shape.

### Step 3 — In-memory ladder

- [ ] Run L1, L2, L3; write `artifacts/operations/phase3-load-ladder-memory.json`.
- [ ] Verify `total_bytes` ≤ `max_cache_bytes` each step.

### Step 4 — PostgreSQL ladder

- [ ] Run same logical workload when `SSCRE_DATABASE_URL` is set.
- [ ] Else write postgres artifact with `status: unavailable` and reason.

### Step 5 — Bottleneck

- [ ] Apply budget table from Feature 8 card.
- [ ] Repeat failing step once for reproducibility.
- [ ] Record `first_bottleneck` or `not_reached`.

### Step 6 — Evidence

- [ ] Complete [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) with
      commands, commit, environment, budgets.

## Verification

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_load_test.py
python -m pytest -q
```

Record skip/unavailable notes for PostgreSQL.

## Out of scope

- Production capacity or SLA claims
- Held-out evaluation
- Infrastructure changes after bottleneck observation
