# Phase 3 Feature 1 evidence — adaptive per-domain thresholds

**Date:** 2026-10-10  
**Branch:** `phase3/implementation`  
**Base commit:** `8c65926227fbdc923a23994c183ac33ba378694f`  
**Working tree:** dirty while implementation is in progress  
**Dataset:** `reviewed-query-pairs-2.0`  
**Config:** `evaluation-config-1.0`  
**Config SHA-256:** `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8`  
**Split manifest SHA-256:** `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51`

## Implementation

- Domain key: `record.metadata.domain`.
- Blank or missing domains use `unknown`.
- Strata with fewer than 10 development pairs use global `0.95`.
- Other strata select from `0.8`, `0.9`, and `0.95`, maximizing development
  `hit_rate` subject to `false_positive_rate <= 0.0`; ties select the lowest
  threshold.
- A frozen map can be supplied to later evaluations; held-out runs do not select
  or modify the map.
- Held-out JSON `phase3-adaptive-held-out.json` carries `config_version` at the
  report root; config SHA-256 is in this evidence header and in the final
  comparison artifact.

Changed code and tests:

- `src/sscre/baseline.py`
- `src/sscre/evaluate.py`
- `tests/test_adaptive_thresholds.py`

## Commands and results

Commands were run from the repository root with the working tree on `PYTHONPATH`
so the evaluation used the uncommitted implementation:

```powershell
$env:PYTHONPATH='src'
python -m sscre.evaluate --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --baseline compatibility-cache --split development --production --adaptive-threshold-map-output artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-adaptive-development.json

$env:PYTHONPATH='src'
python -m sscre.evaluate --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --baseline compatibility-cache --split held-out --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-adaptive-held-out.json

$env:PYTHONPATH='src'
python -m pytest -q tests/test_adaptive_thresholds.py

$env:PYTHONPATH='src'
python -m pytest -q
```

Results:

- Focused tests: **5 passed** (domain lookup/fallback, malformed map rejection,
  selector behavior, and compatibility safety).
- Full suite before the review-test additions: **655 passed**, **15 skipped**, one
  existing Starlette/httpx deprecation warning; current suite after those additions:
  **661 passed**, **15 skipped**.
- Held-out adaptive Strategy C: `hit_rate=0.002325581395348837`,
  `false_positive_rate=0.0`.
- Frozen WS5 global Strategy C reference at `0.95`:
  `hit_rate=0.0`, `false_positive_rate=0.0`.
- Feature 1 decision: **pass** — held-out FPR stayed at `0.0` and hit rate was
  strictly higher than the frozen global-threshold reference.

## Artifacts

- [x] `artifacts/evaluation/phase3-adaptive-threshold-map.json`
- [x] `artifacts/evaluation/phase3-adaptive-development.json`
- [x] `artifacts/evaluation/phase3-adaptive-held-out.json`

These generated artifacts remain uncommitted until the implementation slice is
reviewed and the user approves the commit.
