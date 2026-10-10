# Workstream 7 — failure gallery and quality analysis (evidence)

**Status:** implementation complete (Steps 1–11); parent plan handoff (Step 12) pending explicit Phase 2 WS7 acceptance sign-off.

## Contract and schema

- Failure gallery contract: [`FAILURE_GALLERY_CONTRACT_v1.md`](./FAILURE_GALLERY_CONTRACT_v1.md)
- Schema version: `failure-gallery-1.0`
- Consolidated artifact kind: `workstream7-quality-analysis`
- Step 1 audit: [`WORKSTREAM_7_STEP1_AUDIT.md`](./WORKSTREAM_7_STEP1_AUDIT.md)

## Selected sample

- Split: held-out (`benchmarks/held_out_test.jsonl`)
- Dataset version: `reviewed-query-pairs-2.0`
- Sample unit: `directed_request` (430 directed replays at frozen development threshold)
- Measurement environment: `synthetic_replay`
- Primary comparison input: `artifacts/evaluation/workstream5-held-out-comparison.json`

## Input artifacts (aligned manifest)

| Artifact | Path | Notes |
| --- | --- | --- |
| WS5 comparison | `artifacts/evaluation/workstream5-held-out-comparison.json` | `baseline: comparison`, enriched `failure_gallery` |
| WS6 freshness | `artifacts/evaluation/workstream6-held-out-freshness.json` | `selected_policy`: conservative (via development policy artifact) |
| Split manifest | `benchmarks/split_manifest.json` | SHA `68912e3b1221aae9…` on WS5/WS6/WS7 inputs (2026-10-10 regen) |

## Gallery counts (held-out comparison)

| Section | Count |
| --- | ---: |
| `embedding_only_false_positives` | 13 |
| `embedding_only_false_positives_caught_by_strategy_c` | 13 |
| `strategy_c_failures` | 97 |

- `false_positive_category_complete`: **true** on consolidated artifact (pack-time enrichment + audit)

## Freshness companion (WS6)

- Selected policy: `conservative`
- `held_out_freshness_scope`: `dynamic` / `semi_dynamic` unavailable on held-out; `stable` evaluated
- Protection counts (from WS6 `stale_exposure_accounting`): all zero on current held-out replay (`dynamic_reuse_blocked_count`: 0)

## Outputs

| Output | Path |
| --- | --- |
| Consolidated JSON | `artifacts/evaluation/workstream7-quality-analysis.json` |
| Consolidated HTML | `artifacts/evaluation/workstream7-quality-gallery.html` |
| WS5 gallery HTML (lite) | `artifacts/evaluation/workstream5-held-out-comparison-gallery.html` |

## Regeneration commands

From repository root (use `$env:PYTHONPATH="src"` when running from source tree without an editable install):

```powershell
$env:PYTHONPATH="src"
python -m sscre.evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all --split held-out --production `
  --output artifacts/evaluation/workstream5-held-out-comparison.json

python -m sscre.freshness_evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --split held-out --production `
  --selected-policy artifacts/evaluation/workstream6-development-freshness.json `
  --output artifacts/evaluation/workstream6-held-out-freshness.json

python -m sscre.failure_gallery_export `
  --comparison artifacts/evaluation/workstream5-held-out-comparison.json `
  --freshness-companion artifacts/evaluation/workstream6-held-out-freshness.json `
  --output artifacts/evaluation/workstream7-quality-analysis.json `
  --html artifacts/evaluation/workstream7-quality-gallery.html

python -m sscre.gallery_export `
  artifacts/evaluation/workstream5-held-out-comparison.json `
  -o artifacts/evaluation/workstream5-held-out-comparison-gallery.html
```

Console entry point: `sscre-failure-gallery-export` (same flags as `python -m sscre.failure_gallery_export`).

Diagnostic only: add `--allow-manifest-mismatch` when WS5/WS6 manifest SHA or dataset version disagree.

## Redaction fix (threshold sweep)

- **Issue:** `dataclasses.asdict` emits `threshold_selection.reports` as a **tuple**; operational redaction previously only recursed into lists, leaving `query_a` / `query_b` in sweep reports.
- **Fix:** `redact_operational_evaluation_report` accepts `(list, tuple)` for sweep reports and example lists; evaluate/baseline saves call `validate_redacted_report_payload` before write.

## Verification (2026-10-10)

```powershell
$env:PYTHONPATH="src"
python -m pytest -q tests/test_serialization_boundary.py tests/test_workstream7_failure_gallery.py tests/test_failure_gallery_export_cli.py
```

- Result: **34 passed**
- Manual: `validate_redacted_report_payload` on regenerated WS5 comparison and WS7 consolidated JSON — **pass**

## Known limitations

- Recorded in consolidated artifact `limitations`: synthetic replay only (compatibility and freshness metrics are replay-only).
- Sparse held-out coverage for `dynamic` / `semi_dynamic` freshness classes (documented in WS6 scope).
- Correctness-labeled and live-provider failure sections remain explicitly unavailable per contract.

## Code touch points

- `src/sscre/failure_quality.py` — enrichment, quality analysis, freshness companion
- `src/sscre/failure_gallery.py` — contract validation, packaging
- `src/sscre/failure_gallery_export.py` — CLI
- `src/sscre/gallery_export.py` — consolidated HTML
- `src/sscre/serialization.py` — redaction (including threshold sweep reports)
- `src/sscre/evaluate.py` — gallery enrichment on comparison save
