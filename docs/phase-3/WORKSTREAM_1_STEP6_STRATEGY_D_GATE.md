# Workstream 1 Step 6 — Strategy D gate re-check

**Track ID:** `P3-WS1-GATE-D`  
**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_1_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_1_IMPLEMENTATION_PLAN.md) § Step 6

## Purpose

Re-evaluate the Feature 3 trigger after Workstream 1 card promotions (Steps 2–5)
to confirm Strategy D remains **unauthorized** without a new held-out run or
benchmark/policy change.

## Change since last gate (2026-10-10)

| Area | Changed? | Notes |
| --- | --- | --- |
| Benchmark `reviewed-query-pairs-2.0` / splits | **no** | No JSONL or manifest edits in this workstream |
| Evaluation config safety cap | **no** | `max_false_positive_rate` still **0.0** |
| Shipped stack (Feature 1 τ map + default eviction) | **no** | No cache/evaluation code in Steps 2–5 |
| Held-out replay | **no** | No new access to `benchmarks/held_out_test.jsonl` outcomes |
| Feature cards 4–8 | **yes (docs only)** | Hypothesis cards; no runtime policy change |

Steps 2–5 are **documentation-only** promotions. They do **not** constitute a
benchmark or policy change that requires a new held-out report for this re-check.

## Trigger evaluation (frozen artifact)

**Source of truth:** `artifacts/evaluation/phase3-final-held-out-comparison.json`  
(cited in [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md))

| Check | Value |
| --- | --- |
| Arm | `baselines.compatibility-cache` (Strategy C + Feature 1 adaptive map) |
| `false_positive_rate` | **0.0** |
| `false_positive_examples` count | **0** |
| Safety ceiling | `max_false_positive_rate` **0.0** (`experiments/evaluation_config.json`) |
| Trigger (`FPR > 0.0`) | **not fired** |

Verification command (2026-10-11):

```powershell
$env:PYTHONPATH='src'
python -c "import json; c=json.load(open('artifacts/evaluation/phase3-final-held-out-comparison.json',encoding='utf-8'))['baselines']['compatibility-cache']; print(c['false_positive_rate'], len(c.get('false_positive_examples',[])))"
```

Output: `0.0 0`

## Decision

- **Strategy D:** remains **deferred**; no cross-encoder implementation authorized.
- **Protocol reset:** **not required** for this re-check (no new held-out run).
- **Prior evidence** stands: [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md).

## When to re-run this gate

Re-check **required** before any Strategy D code if **any** of:

1. Benchmark version or held-out split changes.
2. Shipped τ map, eviction, TTL, or compatibility rules change and a **new**
   held-out compatibility report is produced.
3. A future held-out run reports `false_positive_rate` **>** `0.0` for the
   shipped stack.

## If the trigger fires later

1. Write a **protocol reset** (template in [`WORKSTREAM_1_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_1_IMPLEMENTATION_PLAN.md))
   before using held-out outcomes for validator tuning or comparison.
2. Follow [Feature 3](./PHASE3_PLAN.md#feature-3--strategy-d-cross-encoder-validator)
   development protocol only **after** trigger documentation.
3. Do **not** retune Features 1–2 using the same held-out run that invoked D.
4. Add validator telemetry to the serialization contract before implementation.
