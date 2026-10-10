# Phase 2 Workstream 7 Implementation Plan

## Goal

Turn evaluation failures into a **defensible quality-analysis package**, not
only anecdotal examples. Workstream 7 must combine bounded failure examples,
aggregate metrics by reviewed failure category and related strata, and explicit
links to freshness-policy outcomes from Workstream 6—while preserving redaction
and the frozen decision/label contracts.

The target outcome is a reproducible failure gallery package that answers:

- whether every false positive in the **selected held-out evaluation sample**
  has a reviewed or runtime failure category and bounded trace evidence;
- how failure counts and rates break down by category, freshness class, and
  (where available) cache-control outcome;
- which embedding-only false positives Strategy C catches, and which Strategy C
  still fails on;
- which freshness-related failures are **protection** (blocked expiration,
  dynamic disabled) versus **served** stale or disallowed dynamic reuse;
- how to regenerate static gallery exports and a consolidated JSON artifact
  from checked-in WS5/WS6 inputs without a second metrics pipeline;
- which conclusions require regenerating stale WS5 held-out artifacts against
  the current split manifest.

This workstream consumes frozen contracts from Workstream 1, benchmark labels
from Workstream 2, Strategy C traces from Workstream 3, held-out comparison
and statistics from Workstream 5, and freshness stale-exposure accounting from
Workstream 6. It owns **failure presentation and quality synthesis**, not
baseline replay or policy selection.

## Status

**In progress (Step 1 complete).** Phase 1 carryover (**P2-GALLERY**) delivered
a minimal static HTML exporter and satisfied three parent-plan acceptance boxes
for the held-out comparison sample only; see
[`PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md`](../internal/PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md).
That lite scope does **not** replace this workstream’s consolidated artifact,
freshness failure companion, schema freeze, or split-manifest alignment.

Current known baseline:

- `--baseline all` writes `failure_gallery` with three sections on the comparison
  JSON (`evaluate.py`).
- Strategy C populates `false_positive_examples` and `failure_examples` with
  bounded fields; operational saves redact `query_a` / `query_b`
  (`serialization.py`).
- `statistics.by_baseline.compatibility-cache.strata.by_failure_category`
  attaches sample counts and proportion intervals (Workstream 5).
- Workstream 6 artifacts expose stale-exposure numerators, protection counts,
  and per-policy strata; they do **not** include a `failure_gallery` block.
- `python -m sscre.gallery_export` renders HTML from a single evaluation JSON
  (`gallery_export.py`, `tests/test_gallery_export.py`).
- Checked-in `workstream5-held-out-comparison.json` may record an older
  `split_manifest_sha256` than `benchmarks/split_manifest.json` (WS6 Step 1).

Open status:

- [x] Audit failure outputs and document the selected evaluation sample scope
  ([`WORKSTREAM_7_STEP1_AUDIT.md`](./WORKSTREAM_7_STEP1_AUDIT.md)).
- [ ] Freeze the failure-gallery report schema and example record contract.
- [ ] Publish a consolidated workstream7 quality artifact (JSON).
- [ ] Attach freshness failure companion data from WS6 without recomputing replay.
- [ ] Regenerate or explicitly annotate WS5 held-out comparison for manifest drift.
- [ ] Extend static export (HTML and/or Markdown) for the consolidated package.
- [ ] Record completion evidence and link from the Phase 2 parent plan.

## Source of truth

The scope is defined by Workstream 7 in
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).
Related carryover scope: P2-GALLERY in
[`PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md`](../internal/PHASE1_CARRYOVERS_IMPLEMENTATION_PLAN.md).

General behavior is implemented by:

- `src/sscre/baseline.py` — example collection during replay;
- `src/sscre/evaluate.py` — comparison payload and `failure_gallery` assembly;
- `src/sscre/evaluation_statistics.py` — strata and proportion intervals;
- `src/sscre/serialization.py` — schema attachment and operational redaction;
- `src/sscre/gallery_export.py` — static HTML export (Phase 1 carryover);
- `src/sscre/freshness_stale_exposure.py` — served vs protection stale metrics;
- `src/sscre/freshness_artifacts.py` — WS6 artifact validation and metadata.

Frozen inputs:

- [`SAFETY_EVALUATION_CONTRACT_v1.md`](./SAFETY_EVALUATION_CONTRACT_v1.md)
- [`CANDIDATE_TRACE_CONTRACT_v1.md`](./CANDIDATE_TRACE_CONTRACT_v1.md)
- [`SERIALIZATION_BOUNDARY_v1.md`](./SERIALIZATION_BOUNDARY_v1.md)
- [`EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
- [`EVALUATION_STATISTICS_CONTRACT_v1.md`](./EVALUATION_STATISTICS_CONTRACT_v1.md)
- [`FRESHNESS_EVALUATION_CONTRACT_v1.md`](./FRESHNESS_EVALUATION_CONTRACT_v1.md)
- [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md)
- [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md)

Canonical artifact locations to add or update:

| Responsibility | Current or planned module/artifact |
|---|---|
| Replay example collection | `src/sscre/baseline.py` |
| Comparison gallery assembly | `src/sscre/evaluate.py` |
| Category / freshness strata | `src/sscre/evaluation_statistics.py`, `src/sscre/freshness_metrics.py` |
| Redaction and schema | `src/sscre/serialization.py` |
| Static HTML export | `src/sscre/gallery_export.py` |
| Consolidated packaging (planned) | `src/sscre/failure_gallery.py`, `src/sscre/failure_quality.py` |
| Gallery CLI (planned) | `src/sscre/failure_gallery_export.py` or extend `gallery_export.py` |
| Quality artifact | `artifacts/evaluation/workstream7-quality-analysis.json` |
| Static exports | `artifacts/evaluation/workstream7-quality-gallery.html` |
| Tests | `tests/test_workstream7_failure_gallery.py`, extend `tests/test_gallery_export.py` |
| Contract (planned) | `docs/phase-2/FAILURE_GALLERY_CONTRACT_v1.md` |
| Completion evidence | `docs/phase-2/WORKSTREAM_7_EVIDENCE.md` |

## Learning objectives

- [ ] Distinguish reviewed benchmark `failure_category` from runtime outcome
  categories (`false_positive`, `semantic_miss`, etc.).
- [ ] Explain why gallery examples omit raw query text in operational artifacts.
- [ ] Interpret aggregate strata tables alongside individual failure examples.
- [ ] Describe how embedding-only false positives differ from Strategy C
  failures and from freshness protection counts.
- [ ] Design a consolidated artifact that references WS5/WS6 without
  duplicating replay logic.
- [ ] Document mitigation or open limitations per failure class without
  inventing fixes not implemented in code.
- [ ] Recognize when split-manifest drift invalidates cross-workstream claims.
- [ ] Preserve failure-closed semantics when trace or label fields are missing.

## Scope

### Included

- A versioned **failure gallery contract** for example records, gallery sections,
  aggregate tables, and companion references.
- The **selected held-out evaluation sample** as primary scope: Strategy C at
  the WS5 frozen development threshold on `reviewed-query-pairs-2.0` held-out
  (430 directed requests unless the sample definition is explicitly widened in
  the contract).
- Bounded examples with: pair id, direction, expected reuse/compatibility
  labels where available, predicted decision, similarity, reviewed `reason`,
  outcome `failure_category`, and bounded `candidate_traces` per trace contract.
- Aggregate **quality analysis**: failure-category counts and rates with WS5
  interval metadata; optional freshness-class and cache-control strata when
  present in inputs.
- A **freshness failure companion** sourced from WS6 held-out artifacts
  (stale-exposure accounting, protection counts, unavailable fields)—not a second
  freshness replay.
- Static export (HTML minimum; Markdown optional) from the consolidated JSON.
- Tests for redaction, schema validation, category completeness for false
  positives in the selected sample, and deterministic regeneration commands.
- Completion evidence with commands, input artifact paths, limitations, and
  parent-plan handoff.

### Excluded

- Changing `SAFE`, `UNSAFE`, or `UNCERTAIN` meaning or benchmark labels.
- Retuning thresholds or freshness policy from gallery review.
- A second evaluation or statistics pipeline (no reimplementation of
  `evaluate`, `freshness_evaluate`, or bootstrap logic).
- Storing unrestricted query or answer text in operational gallery artifacts.
- `GET /v1/failures` or other public HTTP gallery APIs (Workstream 9 / product
  gate unless separately specified).
- Streamlit dashboard, failure clustering ML, or dual-model experiments.
- Claiming answer-level stale exposure when `answer_availability` is `none`.
- PostgreSQL restart, concurrency, or load claims (Workstream 8).

## Frozen failure-gallery semantics

Failure analysis dimensions must remain separate:

```text
reviewed failure_category     != runtime outcome category
compatibility false positive  != correctness failure
embedding-only FP             != Strategy C FP
blocked expiration            != served stale exposure
gallery anecdote              != aggregate rate claim
development threshold         != held-out threshold tuning
unavailable field             != zero
```

Required invariants:

- operational saved artifacts must not contain `query_a`, `query_b`, or
  unrestricted answer text;
- every false positive in the **selected sample** must carry a category or an
  explicit `category_unavailable` reason in the consolidated artifact;
- aggregate tables must cite sample counts and interval methods when intervals
  exist in source statistics;
- freshness companion rows must label `measurement_environment` and must not
  imply real-provider freshness;
- consolidated packaging must reference input artifact paths and schema versions,
  not silently merge incompatible dataset or manifest versions.

### Gallery sections (minimum)

| Section | Source | Purpose |
|---|---|---|
| `embedding_only_false_positives` | WS5 comparison | Similarity-only unsafe reuse |
| `embedding_only_false_positives_caught_by_strategy_c` | WS5 comparison diff | Strategy C mitigation evidence |
| `strategy_c_failures` | WS5 compatibility baseline | Residual Strategy C failures |
| `freshness_protection_and_exposure` (planned) | WS6 held-out freshness | Protection vs served stale/dynamic |

Optional future sections (document as unavailable until implemented):

- correctness-labeled failures (requires human correctness labels);
- real-provider failure rows (requires WS4 live run).

### Example record (operational save)

Minimum bounded fields after redaction:

- `id`, `direction`
- `predicted_decision`, `expected_reusable`, `expected_compatibility` (when labeled)
- `failure_category` (runtime outcome or reviewed category per section rules)
- `similarity`, `reason` (reviewed pair reason text where policy permits)
- `candidate_traces` (bounded per trace contract)
- `mitigation` or `open_limitation` (string or enum; may be `unknown`)

## Current baseline

### Existing implementation (Phase 1 carryover and WS5)

- [x] Comparison JSON includes `failure_gallery` with three sections
  (`evaluate.py`).
- [x] Strategy C false positives include traces and label fields before redaction
  (`baseline.py`, `example_with_labels`).
- [x] Operational redaction strips query text from gallery and baseline example lists
  (`serialization.py`).
- [x] Statistics strata include `by_failure_category` on compatibility baseline
  (`evaluation_statistics.py`).
- [x] Static HTML export and redaction tests (`gallery_export.py`,
  `tests/test_gallery_export.py`).
- [x] Documented export command in `benchmarks/README.md`.
- [x] WS5 evaluate attaches `freshness_policy_companion_artifacts` when configured
  (`evaluate.py`).

### Open baseline gaps

- [ ] No `FAILURE_GALLERY_CONTRACT_v1.md` or `failure-gallery-1.0` schema version.
- [ ] No consolidated `workstream7-quality-analysis.json` artifact.
- [ ] No freshness failure section in gallery exports.
- [ ] No explicit **false-positive category completeness** audit in tests for
  the held-out comparison artifact.
- [ ] WS5 held-out comparison may predate current `split_manifest.json` SHA
  (regenerate or annotate before claiming cross-artifact consistency).
- [ ] `gallery_export` reads a single JSON; no merge of WS5 + WS6 companions.
- [ ] Mitigation / open-limitation field not standardized on examples.
- [ ] Phase 2 parent plan WS7 acceptance boxes checked via carryover only; full
  WS7 evidence file not yet written.

## Implementation steps

### 1. Audit failure outputs and sample scope

Inventory gallery sections, example shapes, statistics strata, WS6 stale-exposure
blocks, redaction behavior, and split-manifest metadata on checked-in artifacts.

- [x] Record paths and schema versions for WS5 held-out comparison and WS6
  held-out freshness JSON.
- [x] Count false positives and Strategy C failures in the selected held-out sample.
- [x] Record whether each false positive has `failure_category` or reviewed `reason`.
- [x] Compare `split_manifest_sha256` on WS5 artifact vs `benchmarks/split_manifest.json`.
- [x] List fields present in `candidate_traces` vs trace contract bounds.
- [x] Write audit notes in `WORKSTREAM_7_EVIDENCE.md` or `WORKSTREAM_7_STEP1_AUDIT.md`
  ([`WORKSTREAM_7_STEP1_AUDIT.md`](./WORKSTREAM_7_STEP1_AUDIT.md)).

### 2. Freeze the failure gallery contract and schema version

Define machine-readable rules before changing export code.

Planned touch points:
`docs/phase-2/FAILURE_GALLERY_CONTRACT_v1.md`,
`src/sscre/serialization.py`,
`tests/test_workstream7_failure_gallery.py`.

- [ ] Add schema version `failure-gallery-1.0` (or attach under evaluation report envelope).
- [ ] Define section names, example record required keys, and redaction rules.
- [ ] Define aggregate table shape (`quality_analysis.by_failure_category`, etc.).
- [ ] Define freshness companion attachment referencing WS6 artifact paths.
- [ ] Define selected-sample scope (held-out comparison at frozen threshold).
- [ ] Document unavailable sections (correctness, live provider) explicitly.

### 3. Standardize example enrichment and mitigation metadata

Align example records with the contract without adding raw query text to saves.

- [ ] Map runtime outcome categories to display labels consistently.
- [ ] Add optional `mitigation` / `open_limitation` on Strategy C and embedding FPs
  (rule-based defaults: e.g. caught-by-Strategy-C → `compatibility_validator`).
- [ ] Ensure `evaluation_labels` compatibility subset remains bounded in exports.
- [ ] Preserve redaction: enrichment runs before save; no new secret fields.
- [ ] Unit tests for enrichment on fixture examples.

Touch points: `src/sscre/baseline.py` and/or `src/sscre/failure_quality.py`
(post-process layer preferred if replay changes are avoidable).

### 4. Implement quality analysis aggregation (read-only)

Build aggregate tables from existing statistics and benchmark strata—do not rerun
bootstrap unless source artifacts lack required fields.

- [ ] Read `statistics.by_baseline.compatibility-cache.strata.by_failure_category`.
- [ ] Include sample counts, false-positive proportion points, and interval metadata.
- [ ] Add freshness-class strata when present on the same baseline payload.
- [ ] Mark sparse categories (`sample_count` below declared minimum) as diagnostic.
- [ ] Tests mirroring `tests/test_gallery_export.py::test_failure_category_rows_*`.

Planned module: `src/sscre/failure_quality.py`.

### 5. Attach freshness failure companion from Workstream 6

Merge WS6 held-out stale-exposure and protection counts into the consolidated
artifact by reference and copied bounded summaries.

- [ ] Validate WS6 held-out artifact via `freshness_artifacts` helpers where applicable.
- [ ] Copy `stale_exposure_accounting`, protection counts, and selected policy name.
- [ ] Include `held_out_freshness_scope` unavailable classes explicitly.
- [ ] Do not recompute freshness replay in WS7.
- [ ] Tests: companion missing → explicit unavailable block; present → bounded merge.

### 6. Package consolidated JSON artifact

Single machine-readable output for Workstream 9 dashboard gate.

Planned artifact: `artifacts/evaluation/workstream7-quality-analysis.json`.

- [ ] Top-level metadata: dataset version, split, manifest SHA, git identity, timestamps.
- [ ] `input_artifacts`: paths and schema versions for WS5 comparison and WS6 freshness.
- [ ] `failure_gallery`: three WS5 sections (by reference or embedded copy).
- [ ] `quality_analysis`: aggregate tables from Step 4.
- [ ] `freshness_failure_companion`: Step 5 block.
- [ ] `limitations` and `measurement_environment` labels.
- [ ] Regeneration commands recorded in artifact footer or evidence doc.

Planned module: `src/sscre/failure_gallery.py`.

### 7. CLI for consolidate and export

Prefer extending `gallery_export` or adding a thin CLI—no duplicate evaluate path.

- [ ] `python -m sscre.failure_gallery_export` (name TBD) with:
  `--comparison`, `--freshness-companion`, `--output` JSON, optional `--html`.
- [ ] Fail closed when comparison and freshness `dataset_version` or manifest SHA disagree.
- [ ] Optional `--allow-manifest-mismatch` for diagnostic runs only (document in evidence).
- [ ] Exit non-zero on redaction validation failure.

### 8. Regenerate or annotate WS5 held-out comparison

Align primary gallery input with current split manifest when feasible.

- [ ] Run documented `sscre.evaluate --baseline all --split held-out --production`
  when environment permits, **or**
- [ ] Record `manifest_mismatch: true` and stale SHA in WS7 artifact limitations.
- [ ] Update `workstream5-held-out-comparison-gallery.html` only after comparison regen
  or document that HTML reflects stale input.

### 9. Extend static HTML (and optional Markdown) export

- [ ] Render aggregate category table from consolidated JSON.
- [ ] Render freshness companion summary (protection vs served counts).
- [ ] Section anchors for three gallery lists + freshness block.
- [ ] Preserve forbidden-key validation (`query_a`, `query_b`, `query_text`).
- [ ] Link dataset version and input artifact paths in page header.

Touch points: `src/sscre/gallery_export.py` or split render helpers used by CLI.

### 10. False-positive completeness and regression tests

- [ ] Test: every embedding and Strategy C false positive in fixture/comparison
  slice has category or documented exclusion.
- [ ] Test: consolidated artifact validates against contract schema.
- [ ] Test: operational redaction on consolidated output.
- [ ] Test: WS3 serialization/redaction regressions remain green.
- [ ] Test: checked-in `workstream7-quality-analysis.json` passes redaction guard
  (when committed).

Planned: `tests/test_workstream7_failure_gallery.py`.

### 11. Documentation and benchmarks README

- [ ] Add WS7 row to `docs/phase-2/README.md`.
- [ ] Add regeneration commands to `benchmarks/README.md` (consolidated + HTML).
- [ ] Cross-link `FAILURE_GALLERY_CONTRACT_v1.md` from serialization boundary doc
  if appropriate.

### 12. Record evidence and update parent handoff

- [ ] Create `WORKSTREAM_7_EVIDENCE.md` with commands, artifact paths, counts,
  limitations (manifest drift, sparse freshness classes, synthetic replay).
- [ ] Update `PHASE_2_IMPLEMENTATION_PLAN.md` WS7 section with evidence link and
  adjust acceptance checkboxes to reflect full WS7 completion (not carryover-only).
- [ ] Note handoff to Workstream 9 (dashboard reads artifacts; no recompute).

## Verification commands

Run from the repository root. Confirm paths exist before recording as evidence.

Phase 1 carryover export (baseline):

```powershell
python -m sscre.gallery_export `
  artifacts/evaluation/workstream5-held-out-comparison.json `
  -o artifacts/evaluation/workstream5-held-out-comparison-gallery.html
```

Planned consolidated package (after Step 7):

```powershell
python -m sscre.failure_gallery_export `
  --comparison artifacts/evaluation/workstream5-held-out-comparison.json `
  --freshness-companion artifacts/evaluation/workstream6-held-out-freshness.json `
  --output artifacts/evaluation/workstream7-quality-analysis.json `
  --html artifacts/evaluation/workstream7-quality-gallery.html
```

Optional held-out comparison regeneration (Step 8):

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all --split held-out --production `
  --output artifacts/evaluation/workstream5-held-out-comparison.json
```

Focused tests:

```powershell
python -m pytest -q tests/test_gallery_export.py tests/test_workstream7_failure_gallery.py
python -m pytest -q tests/test_workstream3_serialization.py tests/test_evaluate_statistics_attachment.py
```

Full suite:

```powershell
python -m pytest -q
```

For each verification, record: command, date, input artifact schema versions,
manifest SHA, false-positive counts, category completeness result, and
known limitations.

## Acceptance criteria

Aligned with Phase 2 Workstream 7 and P2-GALLERY carryover:

- [ ] Every false positive in the **selected held-out evaluation sample** has a
  category or an explicit documented exclusion in the consolidated artifact.
- [ ] Failure counts and rates by category appear in the consolidated JSON
  (sourced from WS5 statistics, not recomputed ad hoc).
- [ ] Gallery rendering and consolidated saves pass redaction tests; no secrets
  or unapproved raw query text in operational outputs.
- [ ] Bounded examples include expected vs actual decision fields and trace
  evidence where Strategy C produced traces.
- [ ] Freshness protection vs served stale exposure is summarized via WS6
  companion attachment (not conflated with compatibility false positives).
- [ ] Static HTML (minimum) regenerates from checked-in commands.
- [ ] Input artifact versions and manifest SHA are recorded; manifest mismatch
  is either resolved or explicitly flagged.
- [ ] Completion evidence is linked from `PHASE_2_IMPLEMENTATION_PLAN.md`.

Parent plan items already satisfied by Phase 1 carryover remain valid for the
**lite** export path; this workstream closes the **full** Phase 2 WS7 package.

## Completion evidence

Record in [`WORKSTREAM_7_EVIDENCE.md`](./WORKSTREAM_7_EVIDENCE.md):

- [ ] failure-gallery schema version and contract path;
- [ ] selected sample definition and directed request count;
- [ ] input WS5/WS6 artifact paths and manifest SHA comparison;
- [ ] false-positive and Strategy C failure counts;
- [ ] category completeness audit result;
- [ ] freshness companion summary (protection vs served);
- [ ] consolidated JSON and HTML output paths;
- [ ] regeneration commands, git commit, test results;
- [ ] limitations (synthetic replay, sparse semi/dynamic, stale WS5 artifact).

Do not check an item based only on this plan. Each requires code, test,
artifact, or documented unavailability evidence.

## Handoff to later workstreams

**Workstream 5** — WS7 reads comparison and statistics; it must not alter
threshold selection or rerun development sweeps except via documented regen in
Step 8.

**Workstream 6** — WS7 reads held-out freshness artifacts for companion metrics;
it must not change selected policy or stale-exposure definitions.

**Workstream 8** — operational failure modes (restart, concurrency) are out of
scope; do not imply ops failures from gallery examples.

**Workstream 9** — dashboard may render `workstream7-quality-analysis.json` and
HTML; it must not recompute category rates or freshness exposure independently.

Handoff requirements:

- [ ] Publish `failure-gallery-1.0` schema version and example section definitions.
- [ ] Publish consolidated artifact path and regeneration commands.
- [ ] Publish limitations block suitable for dashboard display.
- [ ] Link evidence from `PHASE_2_IMPLEMENTATION_PLAN.md`.

## Execution sequence

1. [x] Audit failure outputs, sample scope, and manifest alignment
   ([`WORKSTREAM_7_STEP1_AUDIT.md`](./WORKSTREAM_7_STEP1_AUDIT.md)).
2. [ ] Freeze failure gallery contract and schema version.
3. [ ] Standardize example enrichment and mitigation metadata.
4. [ ] Implement read-only quality analysis aggregation.
5. [ ] Attach WS6 freshness failure companion.
6. [ ] Package consolidated JSON artifact.
7. [ ] Add consolidate/export CLI.
8. [ ] Regenerate or annotate WS5 held-out comparison.
9. [ ] Extend static HTML export for consolidated package.
10. [ ] Add completeness, schema, and redaction tests.
11. [ ] Update README and benchmarks documentation.
12. [ ] Record evidence and update parent plan.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| WS5 held-out artifact stale vs manifest | Regenerate comparison or flag mismatch in WS7 limitations; fail closed on silent merge. |
| Sparse false positives on held-out | Report counts honestly; avoid strong category-rate claims when `n` is tiny. |
| Query text leaks in gallery | Reuse operational redaction; forbidden-key tests on consolidated output. |
| Second metrics pipeline creep | Read-only aggregation from WS5/WS6 JSON only. |
| Freshness vs compatibility conflation | Separate `freshness_failure_companion` section and contract semantics. |
| Correctness labels absent | Mark correctness gallery unavailable; do not infer from compatibility. |
| HTTP gallery scope creep | Defer `/v1/failures` to product/WS9; CLI/static only here. |
| Phase 1 carryover mistaken for done | Parent plan WS7 checkboxes updated only after WS7 evidence file exists. |
| Runtime vs reviewed category confusion | Contract defines which field each section uses; report both in audit when they differ. |
