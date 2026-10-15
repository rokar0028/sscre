# Phase 4 Step 6 — Held-out evaluation implementation plan

## Goal

Produce the only authorized P4-SEMVALID headline held-out A/B/C artifact, or record
an explicit deferred/unavailable evidence package when no fresh population exists.

**Status:** `closed (Step 6 deferred)` — 2026-10-12.  
**Parent:** parent § 10 Step 6.  
**Card:** `P4-SEMVALID`.

## Prerequisites

- [x] Step 3 held-out gate frozen (`held-out-deferred`).
- [x] Step 5 development threshold artifact exists.

## Implementation

- [x] Fail closed: `validate_p4_held_out_headline_run` blocks P4 held-out evaluate on
      contaminated `held_out_test.jsonl` and when gate status is not
      `fresh-held-out-ready` ([`semantic_validity_held_out.py`](../../src/sscre/semantic_validity_held_out.py)).
- [x] Record deferred evidence:
      [`artifacts/evaluation/phase4-semantic-validity-held-out-deferred.json`](../../artifacts/evaluation/phase4-semantic-validity-held-out-deferred.json).
- [x] CLI: `python -m sscre.semantic_validity_held_out` (config `record_held_out_deferred`).
- [x] Gate record updated with `step_6_headline_evaluation` block.

## Verification

```powershell
$env:PYTHONPATH = "src"
python -m sscre.semantic_validity_held_out
python -m pytest -q tests/test_semantic_validity_held_out.py tests/test_evaluation_protocol.py
```

## Acceptance (deferred path)

- [x] No headline held-out replay executed on the contaminated 215-record split.
- [x] Deferred artifact documents gate status, reason, and authorized command when ready.
- [x] Evaluate CLI rejects P4 held-out on `benchmarks/held_out_test.jsonl`,
      `benchmarks/development.jsonl`, and any path while gate is deferred.
- [ ] Fresh held-out A/B/C artifact (`phase4-semantic-validity-held-out.json`) —
      blocked until gate `fresh-held-out-ready` and new benchmark path exist.

## Out of scope for this document

- Step 7 gate scoring (requires a completed held-out replay artifact).
- Constructing a fresh held-out population (data acquisition / labeling).
