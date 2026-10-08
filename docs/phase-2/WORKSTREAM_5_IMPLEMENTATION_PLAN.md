# Phase 2 Workstream 5 Implementation Plan

## Goal

Complete evaluation and statistical reporting so Phase 2 conclusions can be
defended with uncertainty bounds, baseline comparisons, and explicit operating
points—not only point estimates from deterministic replay.

This workstream consumes the frozen contracts from Workstream 1, reviewed
benchmark splits from Workstream 2, tested Strategy C decisions from
Workstream 3, and provider-labeled measurement semantics from Workstream 4. It
does not change `SAFE`, `UNSAFE`, or `UNCERTAIN` meaning, tune thresholds from
held-out labels, or claim production capacity.

The target outcome is a reproducible held-out evaluation package that answers:

- how no-cache, exact-match, embedding-only, and compatibility-aware caches
  compare on the same workload and accounting rules;
- what hit rate, reuse coverage, decision rates, false-positive rate, precision,
  and correctness metrics were observed, including breakdowns by failure category
  and freshness class;
- what confidence intervals accompany proportion and distribution metrics;
- which operating point was selected from development data and whether it
  satisfies predeclared constraints on the held-out split;
- how safety, reuse, latency, cost, and storage trade off on a Pareto frontier;
- how synthetic baseline replay relates to real-provider measurements without
  conflating them.

## Status

**Workstream 5: final synthetic held-out package** on
`reviewed-query-pairs-2.0` (615 pairs; scale gate passed 2026-10-08). Steps
1–12 and acceptance criteria are complete for synthetic replay, statistics,
Pareto, and development-only operating-point reporting. Completion evidence:
[`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md). Iteration 1 review:
[`WORKSTREAM_5_ITERATION1_REVIEW_AUDIT.md`](./WORKSTREAM_5_ITERATION1_REVIEW_AUDIT.md).

**Remaining deferrals (not WS5 synthetic-package blockers):**

- [ ] Credentialed real-provider measurements (Workstream 4 deferral; Step 11).
- [ ] Held-out-aligned `storage_evaluate` companion for populated Pareto
  `reuse_vs_storage` points (`storage_measurement_environment: unavailable`
  in current held-out Pareto artifact).

Prerequisites:

- Workstream 3 decision-depth handoff:
  [`WORKSTREAM_3_EVIDENCE.md`](./WORKSTREAM_3_EVIDENCE.md).
- Workstream 4 iteration 1 closed; synthetic baselines and provider-labeled
  schema are available; live provider observation is deferred:
  [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md).

**Scale gate status:** the checked-in benchmark is the frozen
`reviewed-query-pairs-2.0` artifact with **615** reviewed pairs (400
development / 215 held-out). The scale gate and held-out freeze criteria are
complete. Real-provider measurements, answer correctness labels, and
held-out-aligned storage simulation for the reuse/storage Pareto plane remain
explicitly deferred and must not be inferred from the synthetic artifacts.

## Source of truth

The scope is defined by Workstream 5 in
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).
The broader remaining-gaps context is in
[`MILESTONE_11_REMAINING_GAPS_IMPLEMENTATION_PLAN.md`](./MILESTONE_11_REMAINING_GAPS_IMPLEMENTATION_PLAN.md).

The following artifacts are frozen inputs and must not be redefined here:

- [`SAFETY_EVALUATION_CONTRACT_v1.md`](./SAFETY_EVALUATION_CONTRACT_v1.md)
  defines `SAFE`, `UNSAFE`, and `UNCERTAIN`.
- [`CANDIDATE_TRACE_CONTRACT_v1.md`](./CANDIDATE_TRACE_CONTRACT_v1.md) defines
  bounded candidate evidence and reason fields.
- [`SERIALIZATION_BOUNDARY_v1.md`](./SERIALIZATION_BOUNDARY_v1.md) defines
  API, log, report, and redaction boundaries.
- [`EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
  keeps compatibility, correctness, and preference labels independent.
- [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md) records provider
  measurement labels, unavailable-field rules, and the synthetic-versus-real
  comparison artifact.

Canonical current implementation locations:

| Responsibility | Current module or artifact |
|---|---|
| Baseline replay and comparison reports | `src/sscre/baseline.py` |
| Evaluation CLI, split validation, threshold selection | `src/sscre/evaluate.py` |
| Reviewed labels and disagreement classes | `src/sscre/evaluation_labels.py` |
| Report schema attachment and redaction | `src/sscre/serialization.py` |
| Provider-labeled measurement comparison | `src/sscre/provider_compare.py` |
| Storage footprint and eviction evaluation | `src/sscre/storage_evaluation.py` |
| Deterministic evaluation configuration | `experiments/evaluation_config.json` |
| Benchmark splits and manifests | `benchmarks/` |
| Statistics schema, intervals, samples | `src/sscre/evaluation_statistics.py` |
| Statistics attachment tests | `tests/test_evaluate_statistics_attachment.py` |
| Baseline and held-out CLI tests | `tests/test_benchmark.py`, `tests/test_workstream3_replay.py` |

## Learning objectives

- [ ] Explain why point estimates from a small benchmark are insufficient for
  Phase 2 claims without confidence intervals and explicit sample counts.
- [ ] Separate development-only threshold selection from held-out reporting.
- [ ] Choose appropriate interval methods for proportions versus latency, cost,
  and token distributions.
- [ ] Interpret false-positive rate, precision, and reuse coverage without
  treating embedding similarity as compatibility proof.
- [ ] Compare four baselines under consistent provider and accounting assumptions.
- [ ] Label synthetic replay, storage simulation, and real-provider rows
  separately in combined artifacts.
- [ ] Select an operating point using constraints written before held-out use.
- [ ] Read a Pareto frontier as a trade-off surface, not a single “best” score.
- [ ] Document unavailable measurements instead of substituting zeros.
- [ ] Understand why benchmark scale affects interval width and claim strength.

## Scope

### Included

- Held-out (or explicitly declared final-split) rerun of all four cache
  baselines on the same benchmark workload.
- Consolidated reporting of safety, reuse, cost, latency, token, and label
  metrics required by Phase 2 §5.2.
- Stratified aggregates by reviewed failure category and freshness class where
  the benchmark provides those fields.
- Bootstrap or binomial confidence intervals for proportions; bootstrap or
  percentile intervals for latency, cost, and token distributions.
- Documented resampling seed, iteration count, and confidence level.
- Pareto frontier artifacts for safety versus reuse, false positives versus
  tokens saved, latency versus cost, and reuse versus storage footprint.
- Operating-point record tying development threshold selection to predeclared
  constraints (`max_false_positive_rate` and extensions).
- Versioned statistical-report schema attached to evaluation JSON.
- Tests that prove held-out evaluation does not re-tune thresholds from
  held-out labels.
- Tests that CIs are present where required and deterministic under a fixed seed.
- Completion evidence linking commands, configs, artifacts, and limitations.

### Excluded

- Changing the frozen safety decision vocabulary or candidate trace taxonomy.
- Using held-out compatibility or correctness labels to select thresholds,
  similarity cutoffs, or compatibility rules.
- Cross-encoders, adaptive thresholds, or dual-model fallback experiments.
- Freshness **policy** experiments beyond reporting existing freshness metadata
  (owned by Workstream 6).
- Failure gallery UI or anecdotal-only analysis (owned by Workstream 7).
- PostgreSQL restart, multi-process, or load claims (owned by Workstream 8).
- Dashboard or second analytics pipeline (owned by Workstream 9).
- Adding plotting dependencies unless a maintainer explicitly approves; prefer
  machine-readable frontier points and documented optional render commands.
- Treating unavailable real-provider fields from Workstream 4 as zero cost or
  zero latency.

## Frozen reporting semantics

Evaluation reports must preserve these separations:

```text
observed runtime decision     ≠ reviewed compatibility label
reviewed compatibility        ≠ correctness label
correctness label             ≠ preference label
development threshold sweep   ≠ held-out evaluation input
synthetic baseline replay       ≠ real-provider measurement
point estimate                ≠ interval (both may be published)
unavailable metric            ≠ zero
```

Held-out evaluation must use a threshold **selected only from development
data**. The held-out split is for reporting and constraint checking only.

Operating-point selection must be **constraint-first**:

```text
filter candidates that violate max_false_positive_rate (and other declared caps)
then rank remaining candidates by documented objective (e.g., tokens saved)
record selected threshold, rule name, and constraint satisfaction on held-out
```

A higher cache hit rate is not success if it violates the false-positive or
freshness constraint documented for the operating point.

## Current baseline

### Existing implementation

- [x] Four baseline replays exist: `no-cache`, `exact-cache`, `embedding-cache`,
  and `compatibility-cache` (`src/sscre/baseline.py`).
- [x] `python -m sscre.evaluate --baseline all` runs all four baselines on one
  split and embeds development threshold selection in `threshold_selection`
  (`src/sscre/evaluate.py`).
- [x] Compatibility baseline reports decision counts, false-positive rate,
  precision, recall, abstention rate, label sections, failure categories, and
  bounded failure examples.
- [x] Embedding and compatibility baselines report p50, p95, and p99 request
  latencies from replay observations.
- [x] Split validation enforces disjoint development and held-out IDs and
  manifest consistency.
- [x] Held-out runs require final review status; development threshold selection
  is tested (`tests/test_benchmark.py`,
  `tests/test_workstream3_replay.py`).
- [x] Evaluation reports attach schema metadata and redact operational fields
  per Workstream 1.
- [x] Storage control evaluation exists as a separate deterministic report
  (`src/sscre/storage_evaluation.py`) with entries, bytes, and evictions.
- [x] Provider comparison artifact keeps synthetic and real environments
  separate (`src/sscre/provider_compare.py`,
  `artifacts/evaluation/workstream4-provider-comparison.json`).
- [x] Evaluate CLI attaches `statistics` by default; `--no-statistics` opts out
  (`tests/test_evaluate_statistics_attachment.py`).

### Open baseline gaps

- [x] Versioned statistical contract:
  [`EVALUATION_STATISTICS_CONTRACT_v1.md`](./EVALUATION_STATISTICS_CONTRACT_v1.md),
  `evaluation-statistics-1.0`.
- [x] Proportion and distribution CIs on CLI reports (Steps 4–5).
- [x] `measurement_environment: synthetic_replay` on enriched reports.
- [x] Stratified metric tables by `failure_category` and `freshness_class` in
  the consolidated held-out report (beyond raw counts where needed).
- [x] Correctness and preference reporting aligned with label contract sections
  for reused versus generated paths.
- [x] Pareto reuse/storage plane wiring (`build_reuse_storage_pareto_point`,
  Step 7); held-out footprint points remain **unavailable** until a matching
  `storage_evaluate` run on `reviewed-query-pairs-2.0` (see evidence limitations).
- [x] Pareto frontier artifacts regenerable from checked-in config and commands.
- [x] Frozen **held-out evaluation artifact** checked in or recorded with exact
  command, git commit, and config versions.
- [x] Operating-point constraint satisfaction documented on held-out.
- [x] Phase 2 scale gate (`--phase2`) documented in evidence when claiming
  final statistical conclusions.

## Statistical reporting contract

### Report versions

Introduce explicit versions (exact strings finalized in Step 2):

| Artifact | Proposed version key |
|---|---|
| Statistical summary attachment | `evaluation-statistics-1.0` |
| Pareto frontier artifact | `evaluation-pareto-1.0` |
| Operating-point record | `operating-point-1.0` |

Reports must continue to use `attach_evaluation_report_schema()` and
`redact_operational_evaluation_report()` before persistence.

### Required top-level metadata

Every WS5 statistical artifact must include:

- `statistics_schema_version` or frontier schema version;
- `dataset_version`, `evaluation_split`, and `benchmark_artifact` block;
- `config_version` and path or hash reference to evaluation config;
- `measurement_environment` (`synthetic_replay`, `real_provider`, or
  `mixed_labeled` with row-level provenance);
- `sample_count` (pair directions or requests—define once and use consistently);
- `confidence_level` (default 0.95 unless config overrides);
- `interval_methods` object describing each metric’s method;
- `random_seed` for bootstrap resampling;
- `bootstrap_iterations` (documented minimum, e.g., 1000 for CI tests, 10000 for
  published held-out freeze when runtime permits);
- `software_version`, `git_commit`, and `git_worktree_dirty`;
- `execution_timestamp` (UTC ISO-8601).

### Proportion metrics and intervals

For each baseline and for the compatibility path at the selected operating
point, report intervals for at minimum:

- cache hit rate;
- safe reuse coverage;
- false-positive rate (embedding-only and compatibility-aware where applicable);
- precision of served reuse;
- rates of `SAFE`, `UNSAFE`, and `UNCERTAIN` decisions;
- abstention rate where defined.

**Default method:** Wilson score interval or Clopper–Pearson (exact binomial)
for proportions; document which is used. **Alternative:** bootstrap percentile
interval on per-request indicators with the same seed policy—pick one primary
method per metric class and test it.

Each interval field should use a stable shape, for example:

```json
{
  "point": 0.12,
  "lower": 0.04,
  "upper": 0.24,
  "method": "wilson",
  "n": 64,
  "confidence_level": 0.95
}
```

### Distribution metrics and intervals

For latency, estimated cost, and token counts (generation, embedding, saved
tokens), report:

- point estimate (mean or median—document choice);
- p50, p95, p99 where already computed;
- bootstrap percentile intervals for mean and/or selected quantiles;
- `n` and method metadata.

Use per-request or per-direction observations stored during replay; do not
fabricate pseudo-samples. If the sample size is too small for stable bootstrap,
publish the point estimate with `interval: unavailable` and document why.

### Stratified reporting

Where benchmark records include `failure_category` and freshness metadata,
publish nested sections:

```text
metrics_overall
metrics_by_failure_category
metrics_by_freshness_class
```

Strata with zero requests must omit intervals or mark `n=0` explicitly. Do not
merge strata to hide sparse cells without documenting the rule.

### Provider-labeled rows

When merging baseline replay with Workstream 4 measurements:

- keep synthetic and real rows in separate arrays or require
  `measurement_environment` on each row;
- propagate `token_source`, `cost_source`, and unavailable rules from WS4;
- never copy synthetic zero costs into real-provider slots.

## Pareto analysis contract

Generate **machine-readable** frontier points suitable for Workstream 9
dashboard ingestion. Each point represents one candidate operating configuration
(typically one embedding threshold from the development sweep, applied on
held-out).

### Required trade-off planes

At minimum, emit points or edges for:

| Plane | X axis | Y axis |
|---|---|---|
| Safety vs reuse | false-positive rate or unsafe reuse rate | safe reuse coverage or hit rate |
| Cost vs safety | estimated cost USD | false-positive rate |
| Latency vs cost | p95 latency ms | estimated cost USD |
| Reuse vs storage | safe reuse coverage or tokens saved | total bytes or entry count |

Dominance must be computed with explicit maximize/minimize directions documented
in the artifact. Non-dominated points form the frontier; dominated points may
be listed separately for auditability.

### Operating point marker

The artifact must identify the **selected** point (development rule + held-out
evaluation) and whether held-out constraints were satisfied:

- `max_false_positive_rate` from config;
- optional future caps (freshness violations, max p95 latency)—add fields when
  Workstream 6 constraints exist; until then document “not evaluated”.

## Implementation steps

### 1. Audit existing evaluation metrics and reporting gaps

Inventory baseline reports, CLI outputs, tests, and Phase 2 §5 requirements
before adding statistics modules.

- [x] Record fields emitted by each baseline dataclass in `baseline.py`.
- [x] Record what `--baseline all` writes today (`evaluate.py` payload shape).
- [x] Record threshold selection inputs and `selection_rule` semantics.
- [x] Record label sections, failure examples, and disagreement counts already
  produced for compatibility baseline.
- [x] Record storage metrics available from `storage_evaluation.py` for Pareto
  footprint axis.
- [x] Record provider comparison fields safe to reference from WS4 artifacts.
- [x] List metrics required by Phase 2 §5.2 that are missing or point-only.
- [x] Confirm tests that forbid premature `confidence_interval` keys remain
  valid until WS5 lands (update those tests in Step 8).

Evidence (2026-10-07):

- [x] Audit artifact: [`WORKSTREAM_5_STEP1_AUDIT.md`](./WORKSTREAM_5_STEP1_AUDIT.md).
- [x] Guard verification: `python -m pytest -q tests/test_workstream3_replay.py`
  → 4 passed (2026-10-07).

### 2. Freeze the statistical schema and interval policy

Define versioned JSON shapes and method choices in code and documentation.

Implementation: `src/sscre/evaluation_statistics.py`,
[`EVALUATION_STATISTICS_CONTRACT_v1.md`](./EVALUATION_STATISTICS_CONTRACT_v1.md),
`src/sscre/serialization.py`, `src/sscre/evaluate.py`,
`experiments/evaluation_config.json`, `tests/test_evaluation_statistics.py`.

- [x] Add `evaluation-statistics-1.0` schema attachment helper.
- [x] Define interval object shape and allowed `method` enum values.
- [x] Define bootstrap seed, iteration count, and confidence level config keys
  in `experiments/evaluation_config.json` (with defaults).
- [x] Document binomial/Wilson versus bootstrap usage per metric type.
- [x] Reject non-finite point estimates and inverted intervals.
- [x] Ensure redaction pass preserves statistics blocks (no raw query text).
- [x] Add unit tests for interval math on toy samples with known bounds.

Step 2 evidence (2026-10-07):

- [x] `attach_evaluation_statistics_schema()` and report envelope integration
  via `attach_evaluation_report_schema()`.
- [x] Wilson proportion intervals and seeded bootstrap mean intervals;
  `clopper_pearson` reserved (not implemented in v1.0).
- [x] `python -m pytest -q tests/test_evaluation_statistics.py` → 11 passed
  (2026-10-07); full suite → 569 passed, 14 skipped (2026-10-07).

### 3. Capture per-observation samples during baseline replay

Statistics require request- or direction-level samples, not only aggregates.

Implementation: `src/sscre/baseline.py`, `src/sscre/evaluation_statistics.py`,
`tests/test_baseline_request_samples.py`,
[`EVALUATION_STATISTICS_CONTRACT_v1.md`](./EVALUATION_STATISTICS_CONTRACT_v1.md).

- [x] Extend replay loops to collect bounded numeric samples (latency, tokens,
  cost, hit indicator, false-positive indicator) without storing raw queries or
  answers in the statistics attachment.
- [x] Keep collection optional behind a flag or always-on with strict size
  bounds aligned to benchmark scale.
- [x] Preserve deterministic ordering for reproducible bootstrap.
- [x] Add tests that sample lists length-match `request_count` semantics.

Step 3 evidence (2026-10-07):

- [x] `request_samples` on all baseline report types;
  `collect_request_samples=False` yields an empty tuple.
- [x] `python -m pytest -q tests/test_baseline_request_samples.py` → 7 passed
  (2026-10-07); full suite → 576 passed, 14 skipped (2026-10-07).

### 4. Implement confidence interval computation

Pure functions with no I/O for testability.

Implementation: `src/sscre/evaluation_statistics.py` (`BootstrapResampler`,
`summarize_request_sample_statistics`), `tests/test_evaluation_statistics.py`.

- [x] Implement Wilson or Clopper–Pearson for proportion metrics.
- [x] Implement bootstrap percentile intervals for means and quantiles.
- [x] Share one seeded RNG (`random.Random(seed)`) across metrics in a run.
- [x] Mark intervals unavailable when `n < minimum_n` (document threshold).
- [x] Add focused tests with fixed seeds matching hand-calculated or tight
  tolerances on small samples.

Step 4 evidence (2026-10-07):

- [x] `summarize_request_sample_statistics()` builds proportion and distribution
  intervals from `request_samples`.
- [x] `python -m pytest -q tests/test_evaluation_statistics.py` → 15 passed
  (2026-10-07); full suite → 580 passed, 14 skipped (2026-10-07).

### 5. Attach statistical summaries to evaluation reports

Wire CI blocks into CLI outputs without breaking existing consumers.

Implementation: `src/sscre/evaluate.py`, `src/sscre/baseline.py`,
`src/sscre/evaluation_statistics.py`, `tests/test_evaluate_statistics_attachment.py`.

- [x] Add `statistics` section to `--baseline all` comparison payload.
- [x] Add optional `statistics` to single-baseline runs for development sweeps.
- [x] Include overall and compatibility-selected operating point intervals.
- [x] Include baseline-by-baseline interval blocks under `statistics.by_baseline`.
- [x] Update `attach_evaluation_report_schema()` version metadata.
- [x] Update redaction tests to allow statistics fields while blocking secrets.

Step 5 evidence (2026-10-07):

- [x] CLI flag `--no-statistics` omits attachment; default attaches CIs.
- [x] `python -m pytest -q tests/test_evaluate_statistics_attachment.py` → 3 passed
  (2026-10-07); full suite → 583 passed, 14 skipped (2026-10-07).

### 6. Add stratified metrics by failure category and freshness class

Use reviewed benchmark metadata already on `BenchmarkRecord`.

- [x] Aggregate proportion metrics per `failure_category`.
- [x] Aggregate proportion metrics per freshness / temporal class field used in
  benchmark schema 1.1.
- [x] Include `n` per stratum in the statistics attachment.
- [x] Add tests using the checked-in miniature benchmark fixtures.

Step 6 evidence (2026-10-07):

- [x] `summarize_request_sample_statistics()` emits
  `strata.by_failure_category` and `strata.by_freshness_class`, with one
  directed-request summary per observed non-empty stratum.
- [x] Each stratum preserves interval methods and reports `sample_count` and
  interval `n`; missing optional stratum labels are omitted rather than merged.
- [x] `python -m pytest -q tests/test_evaluation_statistics.py
  tests/test_evaluate_statistics_attachment.py
  tests/test_baseline_request_samples.py` → passed.

### 7. Integrate storage footprint into reuse–storage Pareto points

Reuse Milestone 9 storage evaluation rather than inventing byte estimates inside
baseline replay unless a single command must orchestrate both.

- [x] Document command pairing: held-out baseline comparison + storage report
  with aligned `dataset_version` and config costs.
- [x] Map storage report fields (`total_bytes`, `entries`, `eviction_count`) to
  Pareto point footprint axes.
- [x] Label storage points as `synthetic_storage_simulation` distinct from API
  replay latency/cost points if combined in one artifact.

Implementation touch: `src/sscre/storage_evaluation.py`, WS5 Pareto builder,
`benchmarks/README.md` command section.

Step 7 evidence (2026-10-07):

- [x] `build_reuse_storage_pareto_point()` maps storage reports to the
  `reuse_vs_storage` point shape and carries `total_bytes`, `entries`, and
  `eviction_count`.
- [x] The adapter enforces matching `dataset_version` when an evaluation
  config is supplied and records its `config_version` and costs.
- [x] Storage points are labeled `synthetic_storage_simulation`; command
  pairing and the distinction from provider replay are documented in
  `benchmarks/README.md`.
- [x] `python -m pytest -q tests/test_storage_evaluation.py` → passed.

### 8. Build Pareto frontier artifacts from development sweep + held-out evaluation

- [x] Read development threshold sweep results (`run_embedding_threshold_sweep`
  outputs via evaluate CLI or embedded `threshold_selection`).
- [x] Emit one point per threshold with metrics needed for all required planes.
- [x] Compute non-dominated frontier set with documented dominance rules.
- [x] Mark selected threshold point and held-out constraint check outcome.
- [x] Add CLI entry point (`python -m sscre.pareto`) writing
  `artifacts/evaluation/<name>-pareto.json`.
- [x] Add regeneration test: run CLI twice with same seed → identical frontier.

Step 8 evidence (2026-10-07):

- [x] `src/sscre/pareto.py` reads the development sweep, applies every
  development threshold to held-out records, and never selects from held-out
  labels.
- [x] The artifact contains safety/reuse, cost/safety, latency/cost, and
  reuse/storage planes, with explicit minimize/maximize dominance metadata.
- [x] Selected threshold and held-out `max_false_positive_rate` satisfaction
  are recorded per point and at the artifact level.
- [x] `python -m pytest -q tests/test_pareto.py
  tests/test_storage_evaluation.py` → passed.

Optional: document a manual plotting recipe (external notebook or script) that
reads JSON only—do not require matplotlib in core dependencies.

### 9. Freeze the held-out evaluation package

Run the final comparison only after development operating point is documented.

- [x] Record development threshold selection artifact path and `selection_rule`.
- [x] Run held-out `--baseline all --production` with frozen config.
- [x] Run statistical attachment and Pareto generation on that output.
- [x] Record git commit, dirty flag, Python version, and test suite result.
- [x] Record the benchmark scale and label limitations in evidence.

Step 9 evidence (2026-10-07):

- [x] Interim package and reproducibility record:
  [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md).
- [x] Held-out comparison:
  `artifacts/evaluation/workstream5-held-out-comparison.json`.
- [x] Pareto artifact:
  `artifacts/evaluation/workstream5-held-out-pareto.json`.
- [x] The scale gate is complete: 615 reviewed pairs observed and
  `benchmark_validate --phase2 --production` passed on 2026-10-08.

Suggested commands (verify paths exist before marking complete):

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all `
  --split held-out `
  --production `
  --output artifacts/evaluation/workstream5-held-out-comparison.json
```

Add WS5-specific flags for statistics and Pareto outputs once implemented.

### 10. Document operating-point and development-only threshold policy

- [x] Add a short **Operating point** subsection to `benchmarks/README.md` or
  `experiments/README.md` describing constraint-first selection.
- [x] Cross-link `max_false_positive_rate` in `evaluation_config.json`.
- [x] State explicitly that held-out labels are not used in
  `_select_development_threshold`.
- [x] Document and test the no-eligible-threshold behavior: report
  `constraint_satisfied: false` and select the least-unsafe threshold for
  diagnostic replay; it is not approved as a constraint-satisfying operating
  point.

Step 10 evidence (2026-10-07):

- [x] Operating-point policy is documented in `benchmarks/README.md`.
- [x] Threshold sweep reports now include `constraint_satisfied`.
- [x] `python -m pytest -q tests/test_benchmark.py` covers both eligible and
  no-eligible-threshold cases.

### 11. Provider-labeled comparison row (optional iteration 1)

Iteration 1 may ship synthetic held-out statistics only; real-provider rows stay
optional per WS4 deferral.

- [x] Reference `workstream4-provider-comparison.json` from WS5 evidence.
- [x] If real-provider measurement remains unavailable, report consequences for
  cost/latency CIs on live paths without imputing values.
- [x] No completed real-provider run exists in this iteration; parallel CI
  blocks with matching schema and distinct `measurement_environment` remain
  explicitly deferred.

### 12. Tests, regression, and evidence

- [x] Update `tests/test_workstream3_replay.py` for intentional `statistics`
  on CLI paths (legacy top-level `confidence_interval` still rejected).
- [x] Add `tests/test_evaluation_statistics.py` for interval and bootstrap logic.
- [x] Add CLI integration tests (`tests/test_evaluate_statistics_attachment.py`).
- [x] Confirm held-out threshold still comes from development only
  (`tests/test_workstream3_replay.py`, `tests/test_benchmark.py`).
- [x] Run full suite: `python -m pytest -q` → 588 passed, 14 skipped
  (2026-10-07).
- [x] Record completion evidence in [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md)
  (interim allowed after Step 9; see review audit).

## Verification commands

Run from the repository root. Record command, date, Python version, git commit,
and pass/fail in evidence.

```bash
python -m pytest -q tests/test_benchmark.py tests/test_evaluation_labels.py tests/test_workstream3_replay.py
python -m pytest -q tests/test_evaluation_statistics.py
python -m pytest -q tests/test_serialization_boundary.py
python -m pytest -q
python -m sscre.benchmark_validate --benchmark-dir benchmarks
```

Development replay with statistics (after Step 5):

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all `
  --split development `
  --output artifacts/evaluation/workstream5-development-comparison.json
```

Held-out freeze (after Step 9; interim acceptable at 32 pairs):

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all `
  --split held-out `
  --production `
  --output artifacts/evaluation/workstream5-held-out-comparison.json
```

Storage footprint companion (Pareto reuse vs storage):

```bash
python -m sscre.storage_evaluate --help
```

Phase 2 scale gate (when claiming ≥500 pairs):

```bash
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2
```

For each successful verification, record:

- command and date;
- dataset version, split, config version, statistics schema version;
- bootstrap seed and iteration count;
- sample counts overall and per stratum;
- selected threshold and constraint satisfaction;
- test count and skipped tests;
- pass/fail result;
- known limitations (benchmark size, unavailable real provider, etc.).

Do not mark held-out **final** statistical claims complete when only the
32-pair artifact was used unless the evidence explicitly labels results as
interim.

## Acceptance criteria

Aligned with Phase 2 Workstream 5 and parent definition of done:

- [x] The held-out workload is evaluated against all four baselines with shared
  provider assumptions and accounting rules.
- [x] Reports include confidence intervals for required proportion metrics, not
  only point estimates.
- [x] Latency, cost, and token metrics include documented interval or
  unavailable states with reasons.
- [x] Interval methods, sample counts, seed, and resampling policy are recorded
  in the artifact metadata.
- [x] Pareto artifacts are regenerable from checked-in commands and configuration.
- [x] Threshold selection is documented and enforced as development-only.
- [x] The selected operating point records whether stated constraints (at minimum
  `max_false_positive_rate`) are satisfied on held-out.
- [x] Metrics include breakdowns by failure category and freshness class where
  benchmark metadata supports them.
- [x] Synthetic baseline replay and real-provider measurements remain separately
  labeled if combined in evidence.
- [x] Unavailable measurements remain explicit; synthetic zeros are not copied
  into real-provider fields.
- [x] Serialization and redaction tests pass with statistics blocks present.
- [x] Completion evidence is linked from the Phase 2 parent plan:
  [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md).

## Completion evidence

Record in [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md) (synthetic
package closed 2026-10-08; deferrals listed under **Status**):

- [x] statistics schema version and module paths;
- [x] evaluation config version and any new statistical keys;
- [x] dataset version, split names, and pair/request counts;
- [x] development threshold selection artifact and rule;
- [x] held-out comparison artifact path (interim vs final label);
- [x] Pareto artifact path and regeneration command;
- [x] operating-point constraint evaluation result;
- [x] bootstrap seed, iterations, and confidence level;
- [x] stratified tables or confirmation of sparse strata handling;
- [x] provider comparison cross-reference and environment labels;
- [x] full-suite pytest result;
- [x] benchmark `--phase2 --production` result recorded as a passed scale gate;
- [x] known limitations (sample size, unavailable provider, storage sim vs live).

Do not mark acceptance criteria complete based only on plan documents; each
checkbox requires code, tests, or a documented unavailable record.

## Handoff to later workstreams

**Workstream 6** consumes freshness-class strata and operating-point constraints
when comparing TTL policies; WS5 must expose freshness breakdown fields without
implementing new TTL experiments.

**Workstream 7** consumes failure-category rates and bounded failure examples
already in compatibility reports; WS5 aggregate intervals by category reduce
anecdotal gallery bias.

**Workstream 8** may reference WS5 latency distributions but owns PostgreSQL
restart and concurrency claims separately.

**Workstream 9** dashboard reads WS5 comparison, statistics, and Pareto JSON;
do not build a second metrics pipeline in WS5.

Handoff requirements:

- [x] Publish frozen held-out comparison JSON path and schema versions.
- [x] Publish Pareto artifact path and dominance rules.
- [x] Publish operating-point record and constraint satisfaction flag.
- [x] Confirm development-only threshold selection in evidence.
- [x] Confirm synthetic versus real measurement labels if both appear.
- [x] Link completion evidence from
  [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).

## Execution sequence

1. [x] Audit baseline and CLI reporting versus Phase 2 §5 requirements.
2. [x] Freeze statistical schema, interval methods, and config keys.
3. [x] Collect bounded per-request samples during replay.
4. [x] Implement and unit-test interval functions.
5. [x] Attach statistics to evaluate CLI outputs.
6. [x] Add stratified failure and freshness metrics.
7. [x] Integrate storage footprint into Pareto reuse–storage plane.
8. [x] Generate Pareto artifacts from development sweep points.
9. [x] Run and record held-out evaluation package (interim or final).
10. [x] Document operating-point policy and development-only tuning.
11. [x] Optional: align provider-labeled rows with WS4 artifacts.
12. [x] Run tests, record evidence, and update parent plan links.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Small sample yields wide intervals and weak claims | Report `n` prominently; label 32-pair runs interim; gate final claims on `--phase2`. |
| Held-out labels leak into threshold selection | Reuse `_select_development_threshold`; add tests and evidence excerpts. |
| Bootstrap nondeterminism across Python versions | Fix seed and document iteration count; test tolerance on CI. |
| Double-counting tokens or cost across baselines | Keep per-baseline accounting functions; cross-check totals in tests. |
| CIs expose per-example text | Store only numeric samples; run redaction tests. |
| Pareto points mix incompatible measurements | Separate `measurement_environment`; never merge synthetic and real without labels. |
| Storage sim points compared to live API latency | Label axes and sources; document coupling commands. |
| Intervals implied from normal approximation on tiny `n` | Enforce minimum `n` or use exact binomial; mark unavailable otherwise. |
| New plotting dependency burden | Ship JSON frontiers first; optional external visualization. |
| Real-provider unavailable fields treated as zero | Reuse WS4 unavailable rules in combined evidence. |
| Operating point chosen post hoc on held-out | Freeze development artifact before held-out run; record timestamps and commits. |
| Confidence intervals mistaken for correctness proof | Keep compatibility and correctness labels separate per WS1. |
