# Failure gallery contract (v1.0)

**Module:** `sscre.failure_gallery`
**Schema version:** `failure-gallery-1.0`
**Status:** frozen for Workstream 7 Steps 2–9
**Related:** [WORKSTREAM_7_STEP1_AUDIT.md](./WORKSTREAM_7_STEP1_AUDIT.md),
[SERIALIZATION_BOUNDARY_v1.md](./SERIALIZATION_BOUNDARY_v1.md),
[CANDIDATE_TRACE_CONTRACT_v1.md](./CANDIDATE_TRACE_CONTRACT_v1.md)

## Purpose

Define machine-readable failure gallery sections, example records, aggregate
quality-analysis tables, and freshness companion attachments without changing
Workstream 1 safety decisions, benchmark labels, or replay semantics.

Operational saves must remain redacted: no raw query or answer text in gallery
examples or consolidated artifacts.

## Semantics (must stay separate)

| Dimension | Notes |
|---|---|
| Reviewed `failure_category` (benchmark) | Stratum labels in `statistics.*.strata.by_failure_category` |
| Runtime `failure_category` (outcome) | On Strategy C gallery rows (`false_negative`, etc.) |
| Embedding-only false positive | Strategy B unsafe reuse; not the same as Strategy C FP |
| `strategy_c_failures` | Compatibility `failure_examples`; includes false negatives and abstentions |
| Freshness protection vs served stale | WS6 companion only; not compatibility false positives |
| Gallery anecdote | Does not replace aggregate rate claims |

## Selected sample scope (primary)

Workstream 7 quality analysis targets the **held-out comparison** replay:

- `evaluation_split`: `held-out`
- `dataset_version`: `reviewed-query-pairs-2.0`
- Directed requests: `430` (`215` pair records × two directions) unless the
  contract scope is explicitly widened in a future schema version
- Strategy C uses the **frozen development-selected** embedding threshold from
  `threshold_selection.selected_threshold` on the comparison artifact
- `measurement_environment`: must be labeled (typically `synthetic_replay`)

Consolidated artifacts must copy this scope in `selected_sample`.

## Gallery sections

### Required on comparison reports (`baseline: comparison`)

| Section | Source | Content |
|---|---|---|
| `embedding_only_false_positives` | Strategy B replay | Similarity-only unsafe reuse rows |
| `embedding_only_false_positives_caught_by_strategy_c` | WS5 diff | Embedding FPs absent from Strategy C FP set |
| `strategy_c_failures` | Strategy C replay | Bounded `failure_examples` |

All three keys must be present (lists, possibly empty).

### Planned (consolidated package only until implemented)

| Section | Source |
|---|---|
| `freshness_protection_and_exposure` | WS6 held-out freshness summaries |

### Unavailable (document explicitly; do not fabricate)

| Section | Reason |
|---|---|
| `correctness_labeled_failures` | Correctness labels not collected on held-out comparison |
| `real_provider_failures` | Requires Workstream 4 live provider runs |

List unavailable sections in consolidated `unavailable_sections` when publishing
the Workstream 7 JSON artifact.

## Example records (operational save)

Forbidden keys on every example (validation rejects at attach time):

`query_a`, `query_b`, `query_text`, `query`, `prompt`, `answer`, and
credential-like fields (`token`, `secret`, `api_key`, …).

### Embedding sections

Required: `id`, `direction` (`a_to_b` | `b_to_a`), `similarity`.

Optional: `reason` (reviewed pair text where policy permits).

After Step 3 enrichment on comparison saves (`enrich_failure_gallery`):

- `failure_category` (reviewed benchmark) **or** `category_unavailable: true`
- `category_source`: `reviewed_benchmark`
- `failure_category_display`, `mitigation`, `open_limitation`
- `evaluation_labels`: compatibility (+ optional annotation) subset only

No `candidate_traces` on embedding-only rows in the current replay path.

### `strategy_c_failures`

Required:

- `id`, `direction`, `similarity`, `reason` (runtime aggregate text)
- `predicted_decision` (`SAFE` | `UNSAFE` | `UNCERTAIN`)
- `expected_reusable`, `expected_compatibility` (when benchmark labels exist)
- `failure_category` (runtime outcome category)

Optional: `evaluation_labels` (compatibility subset after enrichment),
`candidate_traces` (bounded per trace contract v1).

After enrichment: `category_source` (`runtime_outcome`), `failure_category_display`,
`mitigation`, `open_limitation` (rule-based defaults in `failure_quality.py`).

## Aggregate `quality_analysis`

Consolidated artifacts include read-only tables copied from Workstream 5
statistics (no second bootstrap pipeline).

Required shape:

```text
quality_analysis
  by_failure_category   → { <reviewed_category>: <stratum_summary> }
  by_freshness_class    → optional; same stratum shape when present
```

Each `by_failure_category` entry must include at least `sample_count`. When
sourced from WS5, entries should preserve interval metadata from
`statistics.by_baseline.compatibility-cache.strata.by_failure_category`
(`proportions`, `interval_methods`, `confidence_level`, etc.).

HTML export may display `proportions.false_positive_rate.point` for diagnostics;
interval claims must cite the copied WS5 metadata.

## `freshness_failure_companion`

Bounded attachment referencing a WS6 held-out freshness artifact (no freshness
replay in Workstream 7).

When available, required fields:

| Field | Meaning |
|---|---|
| `source_artifact_path` | Checked-in or generated WS6 JSON path |
| `measurement_environment` | e.g. `synthetic_replay` |
| `dataset_version` | Must match comparison when merge is allowed |
| `stale_exposure_accounting` | Copy of WS6 `freshness_experiment.stale_exposure_accounting` |
| `protection_counts` | Copy under stale exposure accounting |
| `held_out_freshness_scope` | Include unavailable freshness classes explicitly |

When a companion cannot be merged (missing file, manifest mismatch):

- set `unavailable: true` and a non-empty `reason`
- omit served/protection numerators rather than implying zero exposure

Optional: `source_schema_version` (`freshness-evaluation-1.0`), `selected_policy`,
`split_manifest_sha256`, `manifest_mismatch`.

## Consolidated artifact envelope

Planned path: `artifacts/evaluation/workstream7-quality-analysis.json`.

Top-level requirements (validated by `validate_consolidated_quality_analysis()`):

| Field | Required |
|---|---|
| `failure_gallery_schema_version` | `failure-gallery-1.0` |
| `selected_sample` | Held-out scope block (see above) |
| `input_artifacts` | `comparison` path + schema/manifest metadata; optional `freshness` |
| `failure_gallery` | Three WS5 sections |
| `quality_analysis` | `by_failure_category` minimum |
| `freshness_failure_companion` | Available or explicit unavailable block |
| `limitations` | Recommended list of strings for dashboard handoff |
| `unavailable_sections` | Optional list of known missing gallery sections |

Comparison-only reports (`evaluate.py --baseline all`) attach
`failure_gallery_schema_version` when `failure_gallery` is present; they do not
require `quality_analysis` until packaged in Step 6.

## Report attachment

1. Build comparison or consolidated payload.
2. Call `attach_evaluation_report_schema()` (delegates to
   `attach_failure_gallery_schema()` when `failure_gallery` is set).
3. Apply `redact_operational_evaluation_report()` before save (query text stripped
   from gallery lists and baseline example arrays).

Fields added when `failure_gallery` is present:

- `failure_gallery_schema_version`: `failure-gallery-1.0`

## Category completeness (Workstream 7 acceptance)

Every **compatibility false positive** in the selected sample must appear with a
runtime or reviewed category, or an explicit `category_unavailable` reason in the
consolidated artifact (enrichment Step 3).

Embedding-only false positives may ship with reviewed `reason` only until
enrichment; the consolidated package must not treat them as categorized for rate
claims without `failure_category` or `category_unavailable`.

## Verification

```powershell
python -m pytest -q tests/test_workstream7_failure_gallery.py
python -m pytest -q tests/test_gallery_export.py tests/test_evaluation_statistics.py
```

Validate checked-in comparison input:

```powershell
$env:PYTHONPATH = "src"
python -c "import json; from sscre.failure_gallery import validate_failure_gallery; d=json.load(open('artifacts/evaluation/workstream5-held-out-comparison.json')); validate_failure_gallery(d['failure_gallery'])"
```
