# Phase 3 Step 5 evidence — final held-out package

**Date:** 2026-10-10  
**Branch:** `phase3/implementation`  
**Final stack:** Strategies A/B/C with Feature 1 adaptive thresholds; default/WS6
conservative eviction; Strategy D deferred  
**Held-out run:** `2026-10-10T14:10:29.559417+00:00`
**Git commit:** `01166574615b3f43faf2adf6848a130df0c9a98e`
**Git worktree:** dirty; source fixes remain uncommitted
**Config:** `evaluation-config-1.0`  
**Config SHA-256:** `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8`  
**Adaptive map SHA-256:** `cf665370c369605c0089bd1e8391b03a62799e58281b431539b4fa689bd3de16`
**Dataset:** `reviewed-query-pairs-2.0`  
**Split manifest SHA-256:** `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51`

## Protocol reset

The initial held-out package was superseded after review found three
reproducibility defects: missing config/map hashes, absence of the configured
conservative freshness policy in the final CLI path, and replay entries not
carrying the reviewed freshness class. This rerun was a written protocol reset:
the development-selected threshold map, dataset split, safety criterion, seed,
and Strategy D gate were unchanged; no held-out tuning was performed.

## Final command

```powershell
$env:PYTHONPATH='src'
python -m sscre.evaluate --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --baseline all --split held-out --production --freshness-policy conservative --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-final-held-out-comparison.json
```

The command completed successfully and was run once for the final paper stack.

## Final point estimates

| Arm | Hit rate | False-positive rate | p50 latency | p95 latency |
| --- | ---: | ---: | ---: | ---: |
| Strategy A — no cache | 0.0 | n/a | n/a | n/a |
| Strategy B — embedding cache | 0.06279069767441861 | 0.48148148148148145 | 0.0 ms | 0.0 ms |
| Strategy C + Feature 1 | 0.002325581395348837 | 0.0 | 0.0 ms | 0.0 ms |

Estimated costs are `0.0` under the configured zero-cost synthetic replay model;
they must not be presented as live-provider costs.

## Artifacts

- [x] `artifacts/evaluation/phase3-final-held-out-comparison.json`
- [x] `artifacts/evaluation/phase3-final-held-out-comparison-gallery.html`
- [x] `python -m sscre.benchmark_validate --phase2 --production` passed.
- [x] `docker compose config` passed with CI sample environment.
- [x] Full suite after review fixes: **661 passed**,
  **15 skipped**, one existing warning.

The final report records bootstrap configuration from the evaluation config:
seed `42`, 1000 iterations, confidence level `0.95`.
