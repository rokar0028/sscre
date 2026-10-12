# Phase 4 Step 5 — Development evaluation implementation plan

## Goal

Execute parent Step 5: run frozen development A/B/C with the real local embedding
provider, record threshold selection diagnostics, and emit the development
artifact without held-out leakage.

**Status:** `closed (Step 5 development)` — 2026-10-12.  
**Parent:** parent § 10 Step 5.  
**Card:** `P4-SEMVALID`.

## Prerequisites

- [x] Step 3 protocol frozen.
- [x] Step 4 local embedding provider available.

## Implementation

- [x] Wire `resolve_semantic_embedding_client` into `sscre.evaluate` for B/C replay.
- [x] Report `false_positive_rate_unavailable_reason` when no labeled reuse.
- [x] Add development artifact metadata: embedding provenance, runtime environment,
      reuse attribution summary, threshold decision block.
- [x] Reject freshness/adaptive CLI options for `P4-SEMVALID` headline runs.

## Verification

```powershell
$env:PYTHONPATH = "src"
python -m sscre.evaluate `
  --benchmark benchmarks/development.jsonl `
  --config experiments/semantic-validity-evaluation-config-v1.json `
  --baseline all `
  --split development `
  --production `
  --output artifacts/evaluation/phase4-semantic-validity-development.json
python -m pytest -q tests/test_evaluation_attribution.py tests/test_evaluation_protocol.py tests/test_evaluate_statistics_attachment.py
python -m pytest -q
```

- [x] Full suite: `python -m pytest -q` → **794 passed**, 15 skipped (2026-10-12;
      includes fail-closed embedding FPR rectification tests).

## Acceptance

- [x] Development artifact exists with `measurement_environment=local_embedding_replay`.
- [x] Threshold selected from development sweep only (`held_out_influence=none`).
- [x] B/C report `embedding_model` = `sentence-transformers/all-MiniLM-L6-v2`, dim 384.
- [x] Threshold decision documented in
      [`PHASE4_STEP5_THRESHOLD_DECISION.md`](./PHASE4_STEP5_THRESHOLD_DECISION.md).
