# Evaluation statistics contract (v1.0)

**Module:** `sscre.evaluation_statistics`
**Schema version:** `evaluation-statistics-1.0`
**Status:** frozen for Workstream 5 iteration 1

## Purpose

Define machine-readable confidence intervals and statistical metadata for
evaluation reports without changing Workstream 1 safety decisions or label
semantics.

## Interval object shape

Each interval is a JSON object:

| Field | Type | Required |
|---|---|---|
| `point` | number or null | Yes for `unavailable`; yes for computed intervals |
| `lower` | number or null | Yes (null when `method` is `unavailable`) |
| `upper` | number or null | Yes (null when `method` is `unavailable`) |
| `method` | string | Yes |
| `n` | non-negative integer | Yes |
| `confidence_level` | number in (0, 1) | Yes |
| `reason` | string | Only when `method` is `unavailable` |

Allowed `method` values:

- `wilson` — Wilson score interval for binomial proportions (default).
- `clopper_pearson` — exact binomial interval (config
  `proportion_interval_method`); supported for `n <= 2048`.
- `bootstrap_percentile` — percentile bootstrap for distribution summaries
  (means; quantiles in later steps).
- `unavailable` — explicit absence of an interval (`lower`/`upper` null).

Validation rules:

- Computed intervals must have finite `point`, `lower`, and `upper` with
  `lower <= point <= upper`.
- Non-finite values are rejected at attachment time.

## Method policy by metric class

| Metric class | Default method | Notes |
|---|---|---|
| Proportions (hit rate, FPR, precision, decision rates, coverage) | `wilson` | Uses success count and `n`; config key `proportion_interval_method`. |
| Distributions (latency, cost, tokens) | `bootstrap_percentile` | Requires per-observation samples from replay (Workstream 5 Step 3+). |

Bootstrap resampling uses a fixed `random_seed` and `bootstrap_iterations` from
evaluation configuration so CI tests and held-out reruns are reproducible.

## Evaluation configuration keys

Checked-in defaults live in `experiments/evaluation_config.json`:

| Key | Default | Meaning |
|---|---|---|
| `confidence_level` | `0.95` | Two-sided interval coverage. |
| `bootstrap_seed` | `42` | Seed for bootstrap resampling. |
| `bootstrap_iterations` | `1000` | Minimum 1000 for tests; 10000 recommended for final held-out freeze. |
| `proportion_interval_method` | `wilson` | Proportion interval algorithm. |
| `minimum_n_proportion` | `1` | Minimum trials before Wilson; use `unavailable` below this. |
| `minimum_n_bootstrap` | `5` | Minimum samples before bootstrap; otherwise `unavailable`. |

## Report attachment

When a report JSON includes a `statistics` object:

1. Build statistics from replay samples (Steps 3–5).
2. Call `attach_evaluation_statistics_schema()` (or
   `attach_evaluation_report_schema()`, which delegates when `statistics` is
   present).
3. Apply `redact_operational_evaluation_report()` — statistics blocks are
   numeric-only and preserved; failure galleries still strip query text.

Top-level fields added with statistics:

- `statistics_schema_version`: `evaluation-statistics-1.0`

## Sample count semantics

Document per report which `n` applies:

- **Request-level proportions:** `n = request_count` (directed query replays).
- **Pair-level observations:** `n = split_record_count` when using
  `observed_pair_records` only.

WS5 held-out artifacts must state the chosen unit in `statistics.sample_unit`.

## Request observation samples (baseline replay)

Baseline reports may include `request_samples`: an ordered tuple (JSON array)
with **one entry per directed replay**, where
`len(request_samples) == request_count`.

Each sample is numeric and identifier-only:

- `pair_id`, `direction` (`a_to_b` | `b_to_a`)
- `cache_hit`, `generated`, `false_positive`, `safe_reuse_hit` (0 or 1)
- `latency_ms`, token fields, `estimated_cost_usd`
- optional `observed_decision` (`SAFE` | `UNSAFE` | `UNCERTAIN`) on Strategy C
- optional benchmark `failure_category` and `freshness_class` for stratified
  statistics (Step 6+)

Collection is controlled by `collect_request_samples` on baseline runners
(default `true`). The list is bounded by `MAX_BASELINE_REQUEST_SAMPLES` (2000).
No query or answer text appears in samples.

## Stratified summaries

Statistics summaries include `strata` when request samples contain benchmark
metadata:

- `strata.by_failure_category`
- `strata.by_freshness_class`

Each observed, non-empty label maps to the same request-level summary shape as
the overall report. `sample_count` and every interval's `n` count directed
requests in that stratum. Samples without an optional label are omitted from
that dimension; empty strata are not fabricated.

## Independent label summaries

Compatibility reports may include `statistics.label_metrics` with separate
reviewed-pair counts for `correctness.cached_answer`,
`correctness.generated_answer`, and `preference.winner`. Missing correctness or
preference labels remain `not_collected`; preference values are never treated
as correctness values. These are pair-level label summaries, not request-level
confidence intervals.

## Related contracts

- [`SERIALIZATION_BOUNDARY_v1.md`](./SERIALIZATION_BOUNDARY_v1.md) — redaction and
  report envelope.
- [`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md)
  — implementation sequence.
