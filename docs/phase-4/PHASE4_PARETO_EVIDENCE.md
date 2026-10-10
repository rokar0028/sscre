# Phase 4 Pareto follow-up evidence

**Track:** `P4-PARETO`  
**Date:** 2026-10-10  
**Status:** complete  
**Environment:** `synthetic_replay`

## Protocol

Phase 3 explicitly deferred the selected-stack Pareto curve to avoid an
additional held-out run. This is therefore recorded as a **new Phase 4
follow-up protocol**, not as a continuation of the Phase 3 final paper run.

- The frozen development threshold grid (`0.8`, `0.9`, `0.95`) was replayed
  against `benchmarks/held_out_test.jsonl` for the global Strategy C reference
  curve.
- The retained Feature 1 adaptive-threshold point was attached from the frozen
  Phase 3 final comparison; it was not retuned using Phase 4 held-out outcomes.
- The adaptive threshold map, default eviction, WS6-conservative freshness
  policy, and Strategy D deferral remained frozen.
- Phase 4 held-out results were not used to select a new threshold or policy.

## Command

```powershell
$env:PYTHONPATH='src'
python -m sscre.pareto `
  --development-sweep artifacts/evaluation/phase3-development-threshold-sweep.json `
  --held-out-benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --output artifacts/evaluation/phase4-selected-stack-pareto.json
```

The generated artifact was then enriched only with protocol, retained-stack,
and provenance metadata:

`artifacts/evaluation/phase4-selected-stack-pareto.json`

## Result

- [x] The global Strategy C reference curve contains threshold points `0.8`,
  `0.9`, and `0.95`.
- [x] Every reference point satisfies the configured
  `max_false_positive_rate <= 0.0` constraint.
- [x] The retained adaptive stack point is recorded from
  `phase3-final-held-out-comparison.json`.
- [x] No Phase 4 held-out retuning occurred.
- [x] The artifact records the protocol reset, source paths, commit, dirty
  worktree state, config hash, split-manifest hash, and seed.

Retained adaptive stack point:

- `hit_rate`: `0.002325581395348837`
- `safe_reuse_coverage`: `0.011764705882352941`
- `false_positive_rate`: `0.0`
- `estimated_cost_usd`: `0.0` under synthetic replay
- `p95_latency_ms`: `0.0` under synthetic replay
- `tokens_saved`: `17`

These synthetic cost and latency values must not be presented as live-provider
measurements.

## Provenance

| Field | Value |
| --- | --- |
| Git commit | `8c65926227fbdc923a23994c183ac33ba378694f` |
| Config SHA-256 | `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8` |
| Dataset | `reviewed-query-pairs-2.0` |
| Split manifest SHA-256 | `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51` |
| Seed | `42` |
| Worktree | dirty; pre-existing Phase 3 changes retained |

## Limitation

The global curve is a threshold reference curve, while the retained adaptive
stack is represented by its frozen final point. The artifact does not claim a
new adaptive-threshold curve because the adaptive map is a single frozen policy,
not a newly tuned Phase 4 grid.
