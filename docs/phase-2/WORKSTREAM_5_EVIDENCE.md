# Workstream 5 Evidence

## Step 9 held-out evaluation package

**Run date:** 2026-10-07  
**Status:** interim  
**Reason for interim status:** the checked-in benchmark contains 32 reviewed
pairs, below the Phase 2 `--phase2` scale gate of 500 pairs.

### Frozen inputs and outputs

- [x] Configuration: `experiments/evaluation_config.json`
  (`evaluation-config-1.0`)
- [x] Development threshold sweep:
  `artifacts/evaluation/workstream5-development-sweep.json`
- [x] Held-out comparison:
  `artifacts/evaluation/workstream5-held-out-comparison.json`
- [x] Held-out Pareto artifact:
  `artifacts/evaluation/workstream5-held-out-pareto.json`
- [x] Dataset: `reviewed-query-pairs-1.1`
- [x] Split: `held-out`
- [x] Statistical schema: `evaluation-statistics-1.0`
- [x] Pareto schema: `evaluation-pareto-1.0`

### Development-only operating point

- [x] Selected threshold: `0.95`
- [x] Selection rule: maximize safe reuse coverage subject to the
  development false-positive rate being at most `0.0`.
- [x] Held-out evaluation reused the development selection and did not retune
  the threshold from held-out labels.

### Reproducibility metadata

- [x] Python: `3.14.5`
- [x] Git commit at artifact generation:
  `abbfdd93d9a4545d050c568273c673f8d2694702`
- [x] Git worktree dirty at artifact generation: `true`
- [x] Confidence level: `0.95`
- [x] Bootstrap seed: `42`
- [x] Bootstrap iterations: `1000`
- [x] Held-out directed-request count: `22`
- [x] Measurement environment: `synthetic_replay`

### Commands and results

- [x] `python -m sscre.evaluate --benchmark benchmarks/development.jsonl
  --config experiments/evaluation_config.json --baseline embedding-cache
  --split development --output artifacts/evaluation/workstream5-development-sweep.json`
  → passed.
- [x] `python -m sscre.evaluate --benchmark benchmarks/held_out_test.jsonl
  --config experiments/evaluation_config.json --baseline all --split held-out
  --production --output artifacts/evaluation/workstream5-held-out-comparison.json`
  → passed.
- [x] `python -m sscre.pareto --development-sweep
  artifacts/evaluation/workstream5-development-sweep.json
  --held-out-benchmark benchmarks/held_out_test.jsonl
  --config experiments/evaluation_config.json
  --output artifacts/evaluation/workstream5-held-out-pareto.json`
  → passed.
- [x] `python -m pytest -q` → 589 passed, 14 skipped, 1 warning.
- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2`
  → expected failure: 32 records, requires at least 500.

## Step 11 provider-labeled comparison

- [x] Provider comparison reference:
  `artifacts/evaluation/workstream4-provider-comparison.json`.
- [x] Unavailable real-provider reference:
  `artifacts/evaluation/workstream4-real-provider-unavailable.json`.
- [x] Synthetic rows remain labeled separately from `real_provider` rows; no
  combined averages or synthetic values are copied into real-provider fields.
- [x] No credentialed real-provider run is available in this iteration.
  Therefore live-path latency, token, and cost confidence intervals remain
  unavailable; synthetic replay intervals must not be presented as live-provider
  measurements.
- [x] Parallel real-provider CI blocks remain deferred until a completed,
  schema-compatible real-provider artifact exists.
- [x] `python -m pytest -q tests/test_provider_compare.py
  tests/test_provider_measure.py tests/test_provider_accounting_boundary.py`
  → 20 passed, 1 warning.

### Limitations

- [x] Confidence intervals and frontier claims are interim because the
  benchmark is below the Phase 2 scale target.
- [x] Replay uses synthetic fake providers; no real-provider cost or latency
  claims are made.
- [x] The Pareto artifact has no storage row because no held-out-aligned
  storage report was supplied; the reuse/storage frontier is therefore
  unavailable until the companion storage simulation is rerun with matching
  dataset and configuration metadata.

## Step 10 operating-point policy

- [x] Policy documentation: `benchmarks/README.md`, **Operating point**.
- [x] Development sweep reports `constraint_satisfied`.
- [x] When no development threshold meets the cap, the least-unsafe threshold
  is retained for diagnostic replay and the constraint flag is `false`; it is
  not treated as an approved operating point.
- [x] Held-out labels remain reporting-only; threshold selection continues to
  use `_select_development_threshold()` on the development split.
- [x] `python -m pytest -q tests/test_benchmark.py
  tests/test_workstream3_replay.py` → 57 passed.

## Step 12 completion and handoff

- [x] Statistics schema and implementation paths recorded:
  `evaluation-statistics-1.0`,
  `src/sscre/evaluation_statistics.py`,
  `src/sscre/baseline.py`, and `src/sscre/evaluate.py`.
- [x] Evaluation config version and statistical keys recorded:
  `evaluation-config-1.0`, confidence level, bootstrap seed/iterations,
  interval method, and minimum sample settings.
- [x] Dataset, split, pair/request counts, threshold rule, constraint result,
  Pareto path, provider comparison, and known limitations recorded above.
- [x] Serialization/redaction and provider boundary tests passed; full suite
  result is recorded above.
- [x] `python -m pytest -q tests/test_serialization_boundary.py
  tests/test_evaluation_statistics.py
  tests/test_evaluate_statistics_attachment.py` → 30 passed.
- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks`
  → passed; development 21, held-out 11, source 32, cross-split overlaps 0.
- [x] Parent plan linked to this interim evidence:
  `docs/phase-2/PHASE_2_IMPLEMENTATION_PLAN.md`.
- [x] Final acceptance remains open for the 500-pair scale gate, a
  held-out-aligned storage companion, and credentialed real-provider
  measurements.

## Review remediation

- [x] Added the false-positives-versus-tokens-saved Pareto plane alongside
  cost-versus-safety.
- [x] Comparison-level statistics now record observed held-out FPR and
  `constraint_satisfied`.
- [x] Correctness and preference label metrics are attached separately by
  answer path and preserve `not_collected`.
- [x] Storage point validation now enforces provenance, finite values, integer
  footprint fields, and pricing alignment.
- [x] Pareto CLI input failures now produce controlled command errors.
- [x] Targeted remediation tests: 24 passed; full suite: 589 passed,
  14 skipped.
