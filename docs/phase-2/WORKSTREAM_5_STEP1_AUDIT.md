# Workstream 5 Step 1 Audit

## Audit status

**Completed:** 2026-10-07  
**Scope:** baseline evaluation reports, `sscre.evaluate` CLI payloads, threshold
selection, label and failure galleries, storage evaluation, Workstream 4 provider
comparison artifacts, and Phase 2 §5.2–§5.4 requirements.  
**Result:** four-baseline held-out comparison and rich compatibility metrics
exist as **point estimates** on deterministic synthetic replay; confidence
intervals, Pareto frontiers, explicit `measurement_environment` labels, and
benchmark-stratified statistics are **not implemented yet**. Step 2+ should
add statistics without changing Workstream 1–3 safety semantics.

This audit does not add intervals, Pareto artifacts, or held-out freeze runs.

## Evidence reviewed

| Area | Artifact |
|---|---|
| Baseline dataclasses and replay | `src/sscre/baseline.py` |
| Evaluation CLI and split validation | `src/sscre/evaluate.py` |
| Reviewed labels and disagreement | `src/sscre/evaluation_labels.py` |
| Report schema and redaction | `src/sscre/serialization.py` |
| Provider comparison (WS4) | `src/sscre/provider_compare.py`, `artifacts/evaluation/workstream4-provider-comparison.json` |
| Storage footprint simulation | `src/sscre/storage_evaluation.py` |
| Evaluation configuration | `experiments/evaluation_config.json` |
| Benchmark schema and splits | `benchmarks/`, `src/sscre/benchmark.py` |
| CI absence guards (pre-WS5) | `tests/test_workstream3_replay.py` |
| Held-out threshold isolation tests | `tests/test_benchmark.py`, `tests/test_workstream3_replay.py` |
| Phase 2 scope | `docs/phase-2/PHASE_2_IMPLEMENTATION_PLAN.md` §5 |
| WS5 plan | `docs/phase-2/WORKSTREAM_5_IMPLEMENTATION_PLAN.md` |

## 1. Baseline report field inventory

All baseline reports are `@dataclass(frozen=True)` values serialized with
`asdict()`, passed through `attach_evaluation_report_schema()` and
`redact_operational_evaluation_report()`, then merged with CLI metadata in
`_save_report()` or the `--baseline all` path in `evaluate.py`.

Schema envelope on every saved report:

- `schema_version` (`BOUNDARY_SERIALIZATION_VERSION`, currently `1.0.0`)
- `safety_contract_version`
- `trace_contract_version`
- report-specific fields below

### 1.1 `NoCacheReport` (`baseline="no-cache"`)

| Field | Role |
|---|---|
| `baseline`, `dataset_version` | Identity |
| `request_count`, `generated_requests` | Workload volume |
| `cache_hits`, `cache_misses`, `hit_rate` | Always zero hit / all miss |
| `input_tokens`, `output_tokens`, `tokens_saved` | Token accounting |
| `total_latency_ms`, `average_latency_ms` | Latency (mean only) |
| `input_cost_per_1k_tokens`, `output_cost_per_1k_tokens` | Config rates |
| `estimated_cost_usd` | Point cost |
| `safe_reuse_hits`, `reusable_opportunities`, `safe_reuse_coverage` | Reuse vs reviewed opportunities |
| `input_tokens_saved`, `output_tokens_saved` | Saved-token placeholders |
| `cache_lookup_cost_usd`, `preprocessing_cost_usd` | Wrapper costs (defaults 0) |
| `cache_miss_categories`, `failure_categories` | Category counts |

**Gaps vs Phase 2 §5.2:** no p50/p95/p99; no decision rates; no per-request
sample export; no confidence intervals; no storage fields.

### 1.2 `ExactCacheReport` (`baseline="exact-cache"`)

Same core volume, token, latency (mean), cost, reuse, and category fields as
no-cache, plus:

- `hit_rate` from exact normalized-query matches
- `cache_miss_categories`, `failure_categories` populated on misses

**Gaps:** no latency percentiles; no embedding/generation token split beyond
aggregate input/output; no intervals or stratified tables.

### 1.3 `EmbeddingCacheReport` (`baseline="embedding-cache"`)

Strategy B (similarity threshold only). Adds:

| Field | Role |
|---|---|
| `threshold`, `top_k`, `embedding_model`, `embedding_dimension` | Operating config |
| `unsafe_reuse_hits`, `precision`, `recall`, `false_positive_rate` | Safety/reuse quality |
| `threshold_rejections`, `semantic_misses` | Miss reasons |
| `embedding_tokens` | Embedding usage |
| `p50_latency_ms`, `p95_latency_ms`, `p99_latency_ms` | Distribution summaries |
| `embedding_cost_per_1k_tokens`, wrapper costs | Cost inputs |
| `failure_categories`, `false_positive_examples` | Failure gallery inputs |

**Gaps:** percentiles are point estimates only (no CI); no `UNCERTAIN` rate
(Strategy B serves on similarity); no benchmark `failure_category` /
`freshness_class` strata; examples are bounded but not aggregated with rates.

### 1.4 `EmbeddingThresholdSweepReport` (`baseline="embedding-cache-threshold-sweep"`)

Development-only sweep wrapper:

- `thresholds`, `selected_threshold`, `selection_rule`
- `reports`: tuple of `EmbeddingCacheReport`, one per threshold

Used by `_select_development_threshold()` and development-only
`--baseline embedding-cache` on the development split.

### 1.5 `CompatibilityCacheReport` (`baseline="compatibility-cache"`)

Strategy C (compatibility-aware). Superset of embedding metrics plus:

| Field | Role |
|---|---|
| `uncertain_decisions`, `abstention_rate` | `UNCERTAIN` exposure |
| `decision_counts`, `decision_breakdowns` | `SAFE` / `UNSAFE` / `UNCERTAIN` and metadata dimensions |
| `failure_examples` | Strategy C failure gallery |
| `correctness_label_counts`, `compatibility_label_counts`, `preference_label_counts` | Reviewed label histograms |
| `label_sections` | Grouped compatibility/correctness/preference counts |
| `observed_pair_records` | Per-pair observed vs expected (bounded, no query text) |
| `disagreement_class_counts` | WS3 disagreement taxonomy |

`decision_breakdowns` keys: `intent`, `domain`, `format`, `temporal`,
`constraint`, `entity` — counts of `{value}:{outcome}` from **extracted query
metadata**, not benchmark `failure_category` or `freshness_class` fields.

`failure_categories` counts **runtime** evaluation outcomes (`false_positive`,
`semantic_miss`, `false_negative`, `unnecessary_abstention`, etc.), not reviewed
benchmark `failure_category` labels.

**Gaps:** no confidence intervals; no explicit held-out **constraint
satisfied** flag; correctness sections are label counts, not correctness **rates
of served reuse vs generation** with intervals; `observed_pair_records` is one
row per pair (direction `b_to_a` only) while `request_count` includes both
directions (`a_to_b` and `b_to_a`).

## 2. `--baseline all` comparison payload

When `evaluate.main()` runs with `--baseline all`, it:

1. Calls `_select_development_threshold()` (development split only).
2. Runs `run_no_cache_baseline`, `run_exact_cache_baseline`,
   `run_embedding_cache_baseline`, and `run_compatibility_cache_baseline` on
   the **requested** split records using `selection.selected_threshold`.
3. Builds `failure_gallery` diff between embedding-only and Strategy C false
   positives.
4. Writes one JSON object (no separate `_save_report` helper).

Top-level keys (in addition to schema envelope):

| Key | Content |
|---|---|
| `config_version`, `execution_timestamp`, `software_version` | Run metadata |
| `git_commit`, `git_worktree_dirty` | Reproducibility |
| `evaluation_split`, `benchmark_artifact` | Split identity and manifest summary |
| `baseline` | Always `"comparison"` |
| `threshold_selection` | Full `EmbeddingThresholdSweepReport` as dict (includes nested `reports`) |
| `baselines` | `no-cache`, `exact-cache`, `embedding-cache`, `compatibility-cache` |
| `failure_gallery` | `embedding_only_false_positives`, `embedding_only_false_positives_caught_by_strategy_c`, `strategy_c_failures` |

**Absent today:** `statistics`, `pareto`, `operating_point`,
`measurement_environment`, `confidence_level`, `random_seed`, constraint
satisfaction on held-out, and any link to storage or real-provider artifacts.

Single-baseline CLI paths add metadata such as `selected_threshold`,
`threshold_selection_split` (`"development"`), and
`threshold_selection_rule` for embedding/compatibility on non-development
sweep paths.

## 3. Threshold selection semantics

**Inputs** (`experiments/evaluation_config.json`):

- `embedding_thresholds` (default `[0.8, 0.9, 0.95]`)
- `embedding_top_k` (default `5`)
- `max_false_positive_rate` (default `0.0`)
- cost fields (currently all `0.0` in the checked-in config)

**Algorithm** (`select_embedding_threshold()` in `baseline.py`):

1. Filter sweep reports where `false_positive_rate <= max_false_positive_rate`.
2. If any eligible: maximize `safe_reuse_coverage`, then minimize
   `false_positive_rate`, then prefer higher `threshold`.
3. If none eligible: minimize `false_positive_rate`, then maximize coverage,
   then prefer higher `threshold`.

**Documented rule string** (`selection_rule`):

```text
maximize safe reuse coverage subject to the development false-positive rate <= {max_false_positive_rate}
```

**Isolation:** `_select_development_threshold()` always loads
`benchmarks/development.jsonl`, validates the development split, and runs
`run_embedding_threshold_sweep()` on development records only. Held-out CLI
tests assert `threshold_selection_split == "development"` when evaluating
held-out (`tests/test_workstream3_replay.py`,
`tests/test_benchmark.py::test_held_out_comparison_uses_development_threshold`).

**WS5 gap:** no serialized record that the selected threshold **satisfied**
`max_false_positive_rate` on held-out (only development sweep eligibility is
implicit in selection).

## 4. Compatibility label, failure, and disagreement outputs

Already produced on Strategy C reports:

- **`label_sections`:** `compatibility` (reviewed labels + agreement + observed
  decision counts), `correctness` (bucket counts via
  `correctness_metrics_bucket()`), `preference` (label or `not_collected`).
- **`false_positive_examples` / `failure_examples`:** bounded dicts with IDs,
  direction, failure metadata, optional `evaluation_labels`, optional
  `candidate_traces`; query text stripped on save.
- **`disagreement_class_counts`:** subset of `DISAGREEMENT_CLASSES` from
  `evaluation_labels.py`.
- **`observed_pair_records`:** expected vs observed compatibility decisions per
  pair; tests forbid `confidence_interval` and `operating_point` keys
  (`tests/test_workstream3_replay.py`).

Redaction: `redact_operational_evaluation_report()` removes `query_a` /
`query_b` from failure galleries and nested lists.

## 5. Storage metrics (Pareto footprint axis)

`src/sscre/storage_evaluation.py` produces `StorageControlReport`
(`report_type="storage_controls"`) from a **separate** deterministic workload,
not from benchmark pair replay:

| Field | Pareto relevance |
|---|---|
| `entries`, `total_bytes`, `average_entry_bytes` | Storage footprint |
| `eviction_count`, `expiration_count` | Growth / churn |
| `hit_rate`, `tokens_saved`, `controlled_cost_usd` | Reuse vs cost |
| `max_entries`, `max_bytes` | Policy caps |
| `latency_source`, `token_source` | Provenance labels |

CLI: `python -m sscre.storage_evaluate` (see module for arguments).

**WS5 gap:** baseline comparison JSON does not embed storage metrics; Pareto
“reuse vs storage” requires an explicit pairing step or orchestration command
(documented in WS5 plan Step 7).

## 6. Provider comparison fields safe for WS5 (Workstream 4)

Checked-in comparison artifact:
`artifacts/evaluation/workstream4-provider-comparison.json`.

| Element | Safe use in WS5 |
|---|---|
| `comparison_schema` / `provider-measurement-comparison-1.0` | Separate artifact type from evaluation reports |
| `measurement_environment: "comparison"` | Do not treat as synthetic baseline replay |
| `rows[].synthetic` / `rows[].real_provider` | Parallel columns with `measurement_environment` per side |
| `real_provider.value: null` | Must stay null; never impute from synthetic |
| `comparison_rules` and `limitations` | Copy into evidence, not into baseline JSON |
| Metrics in `provider_compare.METRICS` | `request_count`, latencies, tokens, `estimated_cost_usd` only |

Synthetic side is derived from compatibility baseline fields via
`_synthetic_metrics()` (uses `average_latency_ms` as generation/total latency
proxy; `embedding_latency_ms` is `null` for synthetic).

Real side maps from `provider_measure` artifact shape when available.

**WS5 gap:** evaluation reports lack `measurement_environment`; merging WS4 rows
into WS5 statistics must remain optional and labeled.

## 7. Phase 2 §5.2 requirement matrix

Legend: **Yes** = point or aggregate present on held-out comparison path;
**Partial** = related data exists but not in required shape; **No** = missing.

| Requirement | no-cache | exact-cache | embedding-cache | compatibility-cache | Notes |
|---|---|---|---|---|---|
| Cache hit rate | Yes | Yes | Yes | Yes | Ratio, no CI |
| Reuse coverage | Partial | Partial | Yes | Yes | `safe_reuse_coverage` on cache baselines |
| SAFE / UNSAFE / UNCERTAIN rates | No | No | No | Partial | `decision_counts` + `abstention_rate`; not normalized rates with CI |
| False-positive rate | N/A | N/A | Yes | Yes | Strategy B/C only |
| Precision of served reuse | No | No | Yes | Yes | Point only |
| Correctness of reused vs generated answers | No | No | No | Partial | Label counts, not answer-outcome correctness rates |
| Downstream tokens saved | Partial | Partial | Yes | Yes | `tokens_saved` |
| Embedding and generation tokens | Partial | Partial | Yes | Yes | Split on embedding/compatibility |
| Estimated cost | Yes | Yes | Yes | Yes | Config-driven; zeros in default config |
| p50 / p95 / p99 latency | No | No | Yes | Yes | No CI on quantiles |
| Cache entries, bytes, evictions, growth | No | No | No | No | Use `storage_evaluation` separately |
| Metrics by failure category | No | No | No | Partial | Runtime `failure_categories`, not benchmark `failure_category` strata |
| Metrics by freshness class | No | No | No | Partial | Trace `freshness_class`; benchmark `freshness_class` not aggregated |

### §5.3 Uncertainty

| Requirement | Status |
|---|---|
| Bootstrap or binomial CIs for proportions | **No** |
| Interval method for latency / cost / token distributions | **No** |
| Documented method, sample count, seed, resampling policy | **No** |
| Per-request sample lists for bootstrap | **No** (only aggregate latencies list internally during replay; not persisted) |

### §5.4 Pareto analysis

| Requirement | Status |
|---|---|
| Safety vs reuse frontier | **No** |
| False positives vs tokens saved | **No** |
| Latency vs cost | **No** |
| Reuse vs storage footprint | **No** |
| Regenerable machine-readable artifact | **No** |
| Operating point vs predeclared constraints on held-out | **No** (development selection only) |

## 8. Test guards before WS5 statistics land

`tests/test_workstream3_replay.py` intentionally asserts:

- `"confidence_interval" not in` payload, `observed_pair_records` rows,
  `label_sections`, and saved compatibility reports.
- `"operating_point" not in` observed pair rows.

**Verification (2026-10-07):**

```text
python -m pytest -q tests/test_workstream3_replay.py → 4 passed
```

**Step 8 action (later):** when statistics are added, replace absence checks
with schema assertions for interval shape and redaction safety.

Other relevant tests:

- `tests/test_benchmark.py` — held-out comparison, split disjointness, compatibility metrics.
- `tests/test_workstream4_regression.py` — baseline labeling for provider regression.

## 9. Recommended Step 2+ implementation targets

Priority order aligned with WS5 plan:

1. **`evaluation-statistics-1.0` schema** and config keys (`confidence_level`,
   `bootstrap_seed`, `bootstrap_iterations`) in `evaluation_config.json`.
2. **Persist bounded per-request indicators** during replay in
   `baseline.py` (or a side channel) for bootstrap without storing query text.
3. **Attach `statistics` block** to `--baseline all` and single-baseline saves.
4. **Stratify** by benchmark `failure_category` and `freshness_class` on
   compatibility replay (new aggregations; keep existing `decision_breakdowns`).
5. **Pareto builder** consuming development sweep `threshold_selection.reports`
   plus held-out comparison baselines and optional storage report.
6. **`measurement_environment: synthetic_replay`** on evaluation outputs;
   optional cross-reference to WS4 comparison artifact paths in evidence only.

## 10. Known limitations affecting claim strength

- Benchmark scale: **32 pairs** (21 development / 11 held-out); Phase 2 target
  ≥500 (`benchmark_validate --phase2`). Intervals will be wide; label as interim
  until scale gate passes.
- Default `evaluation_config.json` uses **zero** cost rates; cost Pareto planes
  need non-zero config or explicit “placeholder pricing” in evidence.
- Synthetic replay uses **MockLLMClient** / **FakeEmbeddingClient**; not
  real-provider latency or token provenance (WS4 live run deferred).
- Sample unit ambiguity: **`request_count`** is per directed query replay;
  **`observed_pair_records`** is one row per pair (b→a). Statistics schema
  must document which `n` is used for each metric.

## Audit conclusion

The repository is **ready for WS5 Step 2**: baseline comparison plumbing,
development-only threshold selection, and compatibility-depth reporting are in
place. WS5 must add **versioned statistics and Pareto artifacts** without
 altering threshold selection inputs, held-out isolation, or redaction rules.
