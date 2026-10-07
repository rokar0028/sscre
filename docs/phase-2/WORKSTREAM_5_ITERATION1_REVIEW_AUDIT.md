# Workstream 5 iteration 1 — review and audit

## Audit status

**Completed:** 2026-10-07
**Scope:** Steps 1–5 implementation (audit through statistics attachment), tests,
contracts, and gap analysis versus Phase 2 §5 and
[`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md).
**Verdict:** **Steps 1–5 are implemented and tested** on the 32-pair working
benchmark. **Steps 6–12 remain open.** Do not treat Workstream 5 or Phase 2
statistical acceptance as closed.

This is a code and plan review, not a held-out freeze or Phase 2 sign-off.

## Verification run (2026-10-07)

| Check | Result |
|---|---|
| `python -m pytest -q` | **583 passed**, 14 skipped, 1 deprecation warning |
| `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2` | **Fail (expected):** 32 records, requires ≥500 |
| Held-out smoke: `sscre.evaluate --baseline all --split held-out` | **Pass:** writes `statistics`, `operating_point.selected_threshold` present |

## Steps 1–5 — evidence summary

| Step | Deliverable | Status |
|---|---|---|
| 1 | [`WORKSTREAM_5_STEP1_AUDIT.md`](./WORKSTREAM_5_STEP1_AUDIT.md) | Complete |
| 2 | `evaluation_statistics.py`, [`EVALUATION_STATISTICS_CONTRACT_v1.md`](./EVALUATION_STATISTICS_CONTRACT_v1.md), config keys | Complete |
| 3 | `request_samples` on all baseline reports | Complete |
| 4 | Wilson / Clopper–Pearson, `BootstrapResampler`, `summarize_request_sample_statistics()` | Complete |
| 5 | CLI + save path statistics; `--no-statistics` | Complete |

### Primary modules

| Module | Role |
|---|---|
| `src/sscre/evaluation_statistics.py` | Intervals, samples, summarize, enrich, comparison statistics |
| `src/sscre/baseline.py` | Sample collection; save path enrichment |
| `src/sscre/evaluate.py` | Comparison + single-baseline attachment |
| `src/sscre/serialization.py` | Schema attachment; statistics preserved under redaction |
| `experiments/evaluation_config.json` | `confidence_level`, `bootstrap_*`, `minimum_n_*` |

### Test coverage (WS5-specific)

| File | Focus |
|---|---|
| `tests/test_evaluation_statistics.py` | Interval math, summarize, schema |
| `tests/test_baseline_request_samples.py` | Sample count, ordering, redaction |
| `tests/test_evaluate_statistics_attachment.py` | CLI attachment, `--baseline all`, `--no-statistics` |
| `tests/test_workstream3_replay.py` | Statistics on evaluate CLI; held-out threshold isolation |
| `tests/test_benchmark.py` | Baseline metrics; held-out comparison (pre-existing) |

## What works well

- **Development-only threshold selection** unchanged; held-out tests still assert
  `threshold_selection_split == "development"`.
- **Synthetic labeling:** `measurement_environment: synthetic_replay` on reports;
  no merging of WS4 real-provider values into baseline JSON.
- **Interval policy is explicit:** Wilson (default) or Clopper–Pearson; bootstrap
  mean and quantiles with shared `BootstrapResampler` per comparison run.
- **Redaction:** statistics blocks are numeric; `validate_redacted_report_payload`
  runs on `statistics` and `request_samples`; query text stays out of samples.
- **Backward compatibility:** `--no-statistics` omits CIs; direct
  `run_*_baseline()` without save still works without statistics block.
- **Determinism:** fixed `bootstrap_seed` + iteration count documented in config
  and echoed in each `statistics` summary.

## Gaps and risks (ordered by impact)

### Blockers for Phase 2 / WS5 acceptance

1. **Benchmark scale:** `--phase2` fails at 32 pairs. All CIs are statistically
   valid but **not defensible for final Phase 2 claims** until scale-up.
2. **No frozen held-out artifact** in repo (Step 9): no checked-in
   `workstream5-held-out-comparison.json` with commit hash and interim label.
3. **No `WORKSTREAM_5_EVIDENCE.md`:** Step 12 completion record missing.
4. **Pareto artifacts (Step 8):** not implemented; parent Phase 2 DoD still open.
5. **Stratified statistics (Step 6):** `failure_category` / `freshness_class` are
   on each `request_samples` row but **not aggregated** into `statistics`.
6. **`constraint_satisfied`:** `statistics.operating_point` records threshold and
   `max_false_positive_rate` but does **not** evaluate or store whether held-out
   FPR satisfied the cap (plan Step 10).
7. **Correctness / preference in statistics:** Phase 2 §5.2 correctness of reused
   vs generated answers is **not** in the statistics layer (only in compatibility
   `label_sections` point counts).

### Medium

8. **Payload size:** Saved reports include full `request_samples` arrays **and**
   derived `statistics`. Regeneration is possible from samples, but JSON grows
   with benchmark scale (bounded at 2000 samples).
9. **Zero default costs** in `evaluation_config.json` make `estimated_cost_usd_*`
   bootstrap intervals **structurally present but not meaningful** until pricing
   is non-zero or labeled placeholder in evidence.
10. **Plan document drift:** “Open baseline gaps” and canonical table still mention
    absent CIs (fixed in this review’s plan sync).
11. **Step 12 checklist** partially done in code/tests but not reflected in plan
    checkboxes or evidence file.

### Low

12. **Clopper–Pearson:** Beta CDF via trapezoid integration (256 steps)—adequate
    for current tests; document if used on large `n` near 2048 cap.
13. **Legacy key guard:** tests still forbid stray top-level `confidence_interval`;
    intervals live under `statistics.proportions.*` — intentional.

## Phase 2 §5 requirement matrix (post Steps 1–5)

| Requirement | Status |
|---|---|
| Four baselines on same workload | **CLI yes**; frozen held-out artifact **no** |
| Proportion CIs (hit rate, FPR, coverage, decisions) | **Yes** in `statistics` when samples exist |
| Distribution CIs (latency, cost, tokens) | **Yes** (bootstrap) |
| Seed / method / `n` metadata | **Yes** in statistics block |
| By failure category / freshness class | **No** (Step 6) |
| Pareto trade-offs | **No** (Step 8) |
| Storage footprint in Pareto | **No** (Step 7) |
| Operating point + constraint check on held-out | **Partial** (threshold only) |
| Real-provider labeled rows in eval JSON | **No** (optional Step 11; WS4 deferred) |

## Recommendations (next work)

1. **Step 6** — `statistics.strata.by_failure_category` /
   `by_freshness_class` with per-stratum `n` and sparse-stratum rules.
2. **Step 8–9** — Pareto builder + run held-out `--baseline all --production`,
   write **interim** artifact under `artifacts/evaluation/`, link in
   `WORKSTREAM_5_EVIDENCE.md`.
3. **Step 10** — Document operating point in `benchmarks/README.md`; add
   `constraint_satisfied` (and behavior when no threshold meets FPR cap).
4. **Step 12** — Create [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md)
   (interim); sync parent [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md)
   WS5 link when evidence exists.
5. **Plan hygiene** — Mark Steps 6–12 and acceptance criteria honestly; keep
   learning objectives unchecked.

## Security and contract compliance

- No query/answer text in `request_samples` or `statistics` (reviewed in tests).
- WS1 decision semantics unchanged; statistics are observational only.
- Held-out labels not used in `_select_development_threshold` (unchanged code path).

## Audit conclusion

Workstream 5 **iteration 1 core pipeline (samples → intervals → report JSON) is
sound for development and interim held-out runs** on synthetic replay. **Close
the workstream only after** stratified metrics, Pareto, held-out freeze evidence,
operating-point constraint reporting, and explicit interim-vs-final labeling
against the 500-pair gate.
