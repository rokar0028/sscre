# Phase 3 Workstream 5 Implementation Plan

## Goal

Execute [Feature 6 — Float32 embedding storage baseline](./PHASE3_PLAN.md#feature-6--float32-embedding-storage-baseline)
and, only if authorized, [Feature 7 — int8 embedding quantization](./PHASE3_PLAN.md#feature-7--int8-embedding-quantization-conditional).

**Status:** `ready` — cards promoted 2026-10-11 (Workstream 1 Step 4).  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md) § Workstream 5.  
**IDs:** `P3-FEAT-EMBED-BASE`, `P3-FEAT-Q8` (conditional).

## Learning objectives

- [ ] Account cache bytes consistently with `_entry_size` semantics.
- [ ] Gate optional optimizations on measured dominance, not assumptions.
- [ ] Report fake-embedding limitations on storage-only claims.

## Prerequisites

- [x] Features 6–7 cards in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- [ ] User confirms pre-registered thresholds before Feature 7 code (dominance
      **0.20**, reduction **3.5×**, safety/reuse rules in card).
- [ ] Pre-code checklist for code work (Feature 6 harness changes).

## Feature 6 — Implementation steps

### Step 1 — Harness

- [ ] Add or extend tooling to emit byte breakdown fields on a development-scale
      workload (not the 4-item Phase 4 storage workload).
- [ ] Reuse `InMemoryExactCache._entry_size` logic or shared helper — single
      formula.

### Step 2 — Run baseline

- [ ] Replay `benchmarks/development.jsonl` (document directed-request construction).
- [ ] Write `artifacts/evaluation/phase3-embedding-storage-baseline.json`.
- [ ] Record command, commit, config hash, dataset version in
      [`PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md).

### Step 3 — Dominance gate

- [ ] Compute `embedding_share`; record **quantize authorized: yes/no**.
- [ ] If **no**, close Workstream 5 without Feature 7 code.

## Feature 7 — Implementation steps (if authorized)

### Step 4 — int8 path

- [ ] Implement symmetric per-vector int8 quantize/dequantize at embedding
      boundary (in-memory replay first).
- [ ] Tests: round-trip bounds, dimension mismatch, failure-closed on corrupt input.

### Step 5 — Development compare

- [ ] Run float32 vs int8 on same development workload as Feature 6.
- [ ] Write `artifacts/evaluation/phase3-quantization-development.json`.
- [ ] Evaluate pass/fail per Feature 7 card.

### Step 6 — Close

- [ ] Update evidence with pass/fail and limitations (fake embeddings).
- [ ] No held-out run for quantization tuning.

## Verification

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_storage_evaluation.py tests/test_cache_eviction.py
```

Add tests for quantization when Step 4 lands. Full suite after substantive code:

```powershell
python -m pytest -q
```

## Out of scope

- PostgreSQL `halfvec` / schema migration (document as follow-up)
- Held-out threshold or quantization tuning
- Phase 4 32-request scale profile as substitute for Feature 6
