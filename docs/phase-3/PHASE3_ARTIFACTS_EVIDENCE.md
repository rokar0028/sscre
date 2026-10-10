# Phase 3 Step 4 evidence — paper artifact package

**Date:** 2026-10-10  
**Branch:** `phase3/implementation`  
**Status:** preview package complete; final held-out package remains Step 5

## Generated artifacts

Development and preview outputs under `artifacts/evaluation/`:

- `phase3-development-comparison.json`
- `phase3-development-threshold-sweep.json`
- `phase3-domain-threshold-curves.json`
- `phase3-pareto-reference.json`
- `phase3-results-preview.json`
- `phase3-ablations.json`
- `phase3-paper-artifact-manifest.json`
- `phase3-adaptive-held-out-gallery.html`

Feature evidence remains separate:

- `phase3-adaptive-threshold-map.json`
- `phase3-held-out-eviction.json`
- `phase3-pattern-eviction-policy.json`

## Reproduction commands

```powershell
$env:PYTHONPATH='src'
python -m sscre.evaluate --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --baseline all --split development --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-development-comparison.json

$env:PYTHONPATH='src'
python -m sscre.evaluate --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --baseline embedding-cache --split development --production --output artifacts/evaluation/phase3-development-threshold-sweep.json

$env:PYTHONPATH='src'
python -m sscre.gallery_export artifacts/evaluation/phase3-adaptive-held-out.json -o artifacts/evaluation/phase3-adaptive-held-out-gallery.html

$env:PYTHONPATH='src'
python -m sscre.phase3_artifacts --output-dir artifacts/evaluation --development-comparison artifacts/evaluation/phase3-development-comparison.json --threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --adaptive-held-out artifacts/evaluation/phase3-adaptive-held-out.json --eviction-held-out artifacts/evaluation/phase3-held-out-eviction.json --frozen-held-out-comparison artifacts/evaluation/workstream5-held-out-comparison.json --frozen-held-out-pareto artifacts/evaluation/workstream5-held-out-pareto.json
```

## Protocol boundary

- The package uses recorded Feature 1 and Feature 2 held-out artifacts; it does
  not rerun held-out evaluation.
- `phase3-pareto-reference.json` is explicitly the frozen WS5 reference. A
  selected-stack Pareto curve and final results table are deferred to Step 5's
  single final held-out run.
- Headline numbers remain unchecked until the final package is frozen.
- Statistics metadata remains seed `42`, 1000 bootstrap iterations, confidence
  level `0.95`.

## Verification

- [x] Artifact assembly command completed successfully.
- [x] `python -m pytest -q`: **659 passed**, 15 skipped, one existing warning.
- [x] No new held-out evaluation was run for this packaging step.
