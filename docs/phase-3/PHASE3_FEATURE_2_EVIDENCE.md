# Phase 3 Feature 2 evidence — pattern-aware eviction

**Date:** 2026-10-10  
**Branch:** `phase3/implementation`  
**Dataset:** `reviewed-query-pairs-2.0`  
**Config:** `evaluation-config-1.0`  
**Config SHA-256:** `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8`
**Split manifest SHA-256:** `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51`
**Git commit (held-out artifact):** `8c65926227fbdc923a23994c183ac33ba378694f`
(`git_worktree_dirty` **true** in `phase3-held-out-eviction.json` header)

## Implementation

- Added optional `lru`/`pattern` eviction strategies to `InMemoryExactCache`.
- Pattern ordering uses hit count and reviewed freshness class; lower-hit entries
  are evicted first, with dynamic and semi-dynamic entries prioritized before
  stable entries.
- Added capped compatibility replay using the Feature 1 frozen threshold map.
- Kept WS6 `conservative` TTLs unchanged.
- Added `sscre.phase3_eviction` for development cap selection and held-out replay.

Changed code and tests:

- `src/sscre/cache.py`
- `src/sscre/baseline.py`
- `src/sscre/phase3_eviction.py`
- `tests/test_cache_eviction.py`

## Commands and results

Commands used the working tree through `PYTHONPATH`:

```powershell
$env:PYTHONPATH='src'
python -m sscre.phase3_eviction --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --split development --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-development-eviction.json --policy-output artifacts/evaluation/phase3-pattern-eviction-policy.json

$env:PYTHONPATH='src'
python -m sscre.phase3_eviction --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --split held-out --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --selected-policy artifacts/evaluation/phase3-pattern-eviction-policy.json --output artifacts/evaluation/phase3-held-out-eviction.json

$env:PYTHONPATH='src'
python -m pytest -q tests/test_cache_eviction.py tests/test_adaptive_thresholds.py

$env:PYTHONPATH='src'
python -m pytest -q
```

Development selection:

- Selected the smallest cap with reference eviction: `entry_cap=1`.
- Reference evictions: `777`.
- Candidate constraints: satisfied (`stale_exposure_rate=0.0`,
  `false_positive_rate=0.0`, `dynamic_reuse_served_rate=0.0`).

Held-out decision:

- Default-eviction reference hit rate: `0.002325581395348837`.
- Pattern-eviction hit rate: `0.002325581395348837`.
- Both safe-reuse coverage: `0.011764705882352941`.
- Candidate FPR: `0.0`.
- Candidate stale exposure: `0.0`.
- **Result: fail/defer.** Pattern eviction did not strictly improve reuse or
  safe-reuse coverage, so it is not included in the shipped Phase 3 stack.
- Full suite after implementation: **661 passed**, **15 skipped**, one existing
  Starlette/httpx deprecation warning.

## Artifacts

- [x] `artifacts/evaluation/phase3-pattern-eviction-policy.json`
- [x] `artifacts/evaluation/phase3-development-eviction.json`
- [x] `artifacts/evaluation/phase3-held-out-eviction.json`

No held-out retuning was performed. The Feature 1 adaptive threshold map remains
eligible; the stack uses default/WS6 conservative eviction.
