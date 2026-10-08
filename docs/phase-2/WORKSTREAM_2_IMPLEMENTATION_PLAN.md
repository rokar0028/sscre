# Phase 2 Workstream 2 Implementation Plan

## Goal

Build a reviewed, versioned, leakage-resistant benchmark that can support
defensible measurements of compatibility, correctness, preference, safety,
reuse, freshness, cost, latency, and storage.

The benchmark is an evaluation artifact, not production request storage. It
must preserve enough approved source and annotation context to reproduce
evaluation results while keeping operational traces bounded and non-sensitive.
The benchmark must also make it impossible to mistake a similarity result or a
cache hit for a human correctness judgment.

The Phase 2 target is at least 500 reviewed query pairs with validated
development and held-out splits. The current repository contains a smaller
working benchmark and validation path; this workstream expands and hardens it
without changing the frozen decision or label semantics from Workstream 1.

## Status (2026-10-08)

**Infrastructure: complete.** Schema 1.1, validation, leakage checks, build/freeze
CLI, split manifest identity, evaluate `benchmark_artifact`, operational report
redaction, and regression tests are implemented on the frozen
`reviewed-query-pairs-1.1` artifact (32 pairs). The scale-up subsequently
produced and froze `reviewed-query-pairs-2.0` (615 pairs).

**Phase 2 scale gate: complete.** The checked-in artifact contains 615 final
records in 400 development and 215 held-out rows. The frozen manifest and
Phase 2 validation command are recorded in the scale-up evidence.
[`BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md`](./BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md).
Evidence lives in [`benchmarks/README.md`](../../benchmarks/README.md)
(§ Workstream 2 completion evidence).

## Source of truth

The scope is defined by Workstream 2 in
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).
The following contracts are frozen inputs and must not be redefined here:

- [`SAFETY_EVALUATION_CONTRACT_v1.md`](./SAFETY_EVALUATION_CONTRACT_v1.md)
  defines `SAFE`, `UNSAFE`, and `UNCERTAIN`.
- [`CANDIDATE_TRACE_CONTRACT_v1.md`](./CANDIDATE_TRACE_CONTRACT_v1.md) defines
  bounded candidate evidence and reason taxonomy.
- [`SERIALIZATION_BOUNDARY_v1.md`](./SERIALIZATION_BOUNDARY_v1.md) defines
  JSON-compatible API, log, and report boundaries.
- [`EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
  keeps compatibility, correctness, and preference independent.
- [`SSCRE_BENCHMARK_FORMAT.md`](../SSCRE_BENCHMARK_FORMAT.md) documents the
  current JSONL representation.

## Learning objectives

- [ ] Explain why a reviewed compatibility label is not the same as a
  `SAFE` decision observed from the implementation.
- [ ] Design query pairs that test meaningful compatibility boundaries instead
  of mostly measuring paraphrase similarity.
- [ ] Apply independent correctness and preference judgments without treating
  preference as a factual label.
- [ ] Detect source, normalized-text, template, and near-duplicate leakage
  between development and held-out data.
- [ ] Use adjudication metadata to preserve disagreement rather than hiding it.
- [ ] Understand why the held-out split must remain read-only until the
  operating point is frozen.

## Scope

### Included

- A versioned benchmark JSONL schema and documentation.
- Stable pair IDs and immutable dataset-version semantics.
- Reviewed compatibility and expected reuse labels.
- Independent correctness labels when an answer is available.
- Preference labels only for explicit answer comparisons.
- Failure-category, freshness, domain, entity, constraint, intent, and output
  format metadata.
- Annotation provenance, review status, disagreement, and adjudication data.
- Development and held-out manifests with reproducible split validation.
- Coverage and balance checks for required semantic categories.
- Tests for malformed records, duplicate IDs, unsupported versions, missing
  rows, source leakage, overlap, and manifest inconsistency.
- A checked-in benchmark artifact that can be consumed by the existing
  evaluation CLI.

### Excluded

- Changing the `SAFE` / `UNSAFE` / `UNCERTAIN` decision contract.
- Replacing the existing candidate-trace or serialization contracts.
- Training a new embedding model or cross-encoder.
- Automatic generation of final labels without review.
- Production ingestion of unrestricted user prompts or answers.
- Threshold selection on held-out labels.
- Real-provider integration and provider pricing collection.
- Dashboard implementation.
- Statistical reporting beyond the validation data needed to establish a
  trustworthy benchmark.

Those activities consume the benchmark produced here and belong to later
workstreams.

## Current baseline

- [x] `BenchmarkRecord` provides a versioned JSONL record with stable lowercase
  hyphen-separated IDs, two query strings, reuse, compatibility, correctness,
  reason, preference, annotation source, and adjudication status fields
  (`src/sscre/benchmark.py`).
- [x] `load_benchmark_jsonl()` rejects malformed JSON, invalid records, and
  duplicate IDs with source-line errors.
- [x] The evaluation-label implementation maps reviewed compatibility labels to
  expected safety decisions without merging correctness or preference
  (`src/sscre/evaluation_labels.py`).
- [x] Development and held-out files exist with a split manifest and explicit
  evaluation directions (`benchmarks/split_manifest.json`).
- [x] The current manifest records 21 development pairs and 11 held-out pairs
  (`reviewed-query-pairs-1.1`, 32 total).
- [x] The evaluation CLI validates the declared split, dataset version,
  manifest path, record count, ID coverage, and split disjointness
  (`src/sscre/evaluate.py`).
- [x] Existing tests cover duplicate IDs, malformed JSON, split disjointness,
  manifest tampering, explicit held-out evaluation, and label separation
  (`tests/test_benchmark.py`, `tests/test_evaluation_labels.py`).
- [ ] The benchmark contains at least 500 reviewed pairs.
- [x] Every required category has an explicit, validated representation on the
  working artifact (`WORKING_BASELINE_COVERAGE`; `split_manifest.json`
  `coverage_summary`).
- [x] Every pair on the working artifact has `annotation_source` and
  `review_status: final`; high-impact categories require `annotator_count >= 2`.
- [x] Normalized source examples and near-duplicates are checked for leakage
  (`validate_cross_split_leakage`, tests in `tests/test_benchmark.py`).
- [x] The split manifest is frozen with identity metadata (`frozen_at`, split
  checksums, `record_ids`); Phase 2 **500-pair** scale remains open.

## Frozen contract handoff

The benchmark produces reviewed expectations and labels. The evaluator
produces observed decisions and traces. These values must remain separate:

```text
reviewed pair
    |
    +--> expected compatibility decision
    +--> correctness labels, if collected
    +--> preference label, only for an explicit comparison
    |
evaluation replay
    |
    +--> observed SAFE / UNSAFE / UNCERTAIN decision
    +--> bounded candidate traces
    +--> independent report sections
```

The benchmark must never:

- infer correctness from `SAFE`;
- infer compatibility from embedding similarity;
- convert missing correctness into `incorrect`;
- use preference as a proxy for correctness;
- collapse expected `UNSAFE` and `UNCERTAIN`;
- store unrestricted raw prompts or full answers in operational logs.

## Implementation steps

### 1. Audit the benchmark inputs and freeze dataset policy

Record the current data files, schema version, dataset version, split purpose,
evaluation directions, and known limitations before expanding the dataset.

- [x] Confirm the current record model and loader in
  `src/sscre/benchmark.py`.
- [x] Confirm the current nested label contract in
  `src/sscre/evaluation_labels.py`.
- [x] Confirm the current split and manifest validation in
  `src/sscre/evaluate.py`.
- [x] Confirm that the current benchmark is a small working fixture rather than
  the Phase 2 completion artifact.
- [x] Record the benchmark ownership, approved data sources, licensing
  restrictions, and redaction policy in `benchmarks/README.md`.
- [x] Assign a new dataset version for the expanded reviewed benchmark
  (`reviewed-query-pairs-1.1`).
- [x] Freeze the meaning of pair direction: evaluate `query_a → query_b` and
  `query_b → query_a` separately unless a record explicitly declares the pair
  symmetric.
- [x] Define whether an answer is attached to query A, query B, both, or
  neither; do not let answer availability alter the compatibility label.

Evidence to record:

- source files and their record counts;
- schema and dataset versions;
- split manifest path and checksum policy;
- annotation guide version;
- approved data source and redaction decision;
- command used to validate the frozen input.

Step 1 evidence (2026-10-06):

- [x] Data ownership, approved sources, licensing, and redaction policy are
  documented in [`benchmarks/README.md`](../../benchmarks/README.md).
- [x] Step 1 baseline was `reviewed-query-pairs-1.0` (24 records). Superseded by
  `reviewed-query-pairs-1.1` (32 records, 21 development / 11 held-out) in
  steps 6–7.
- [x] Pair direction and answer-availability semantics are documented.
- [x] `python -c "from sscre.benchmark import load_benchmark_jsonl; records =
  load_benchmark_jsonl('benchmarks/reviewed_query_pairs.jsonl'); print(len(records))"`
  → `24`.
- [x] `python -m pytest -q tests/test_benchmark.py` → 20 passed.

The new dataset version for the expanded benchmark remains open for Step 2,
because no schema expansion or new reviewed records were created in Step 1.

### 2. Define the versioned benchmark record

Extend the current record shape only where the additional fields answer a
required Phase 2 evaluation question. Prefer bounded enums and structured
metadata over free-form fields. Keep fields stable so reports can be
regenerated from a checked-in artifact.

The logical record should contain:

```json
{
  "schema_version": "1.1",
  "id": "pair-000001",
  "query_a": "Give me Python code for binary search.",
  "query_b": "Give me Java code for binary search.",
  "directionality": "ordered",
  "expected_reuse": false,
  "expected_compatibility": "incompatible",
  "failure_category": "constraint_mismatch",
  "freshness_class": "stable",
  "domain": "programming",
  "metadata": {
    "intent": "code_generation",
    "entities": ["binary_search"],
    "constraints": {
      "language": "python"
    },
    "output_format": "source_code"
  },
  "correctness_label": null,
  "preference_label": null,
  "annotation": {
    "source": "human_review",
    "review_status": "final",
    "annotator_count": 2,
    "adjudication_status": "not_required"
  }
}
```

The exact field names must be reconciled with the frozen
`EVALUATION_LABEL_CONTRACT_v1.md` before implementation. In particular,
existing fields such as `reusable` and `compatibility_label` must not silently
change meaning during a schema revision. If a breaking change is required,
increment the schema version and provide a migration or explicit rejection
path.

Required schema decisions:

- [x] Choose and document the canonical names for expected reuse and expected
  compatibility.
- [x] Add an explicit primary `failure_category` enum rather than requiring
  reports to parse free-form `reason`.
- [x] Add a freshness class with at least `stable`, `semi_dynamic`, and
  `dynamic`.
- [x] Add bounded domain, intent, entity, constraint, and output-format
  metadata.
- [x] Represent answer availability separately from correctness labels.
- [x] Permit correctness `null` when no answer was reviewed.
- [x] Permit preference `null` or `applicable: false` when no explicit
  comparison was performed.
- [x] Record annotation source and adjudication status independently from
  label values.
- [x] Define one primary failure category; secondary evidence remains in
  bounded metadata or the review rationale.
- [x] Reject unknown schema versions rather than applying undocumented
  defaults.
- [x] Keep each record valid independently so a bad line cannot be silently
  skipped.

Step 2 schema evidence (2026-10-06):

- [x] `src/sscre/benchmark.py` defines schema `1.1` types for directionality,
  freshness, answer availability, failure category, bounded metadata, expected
  labels, and review provenance.
- [x] Canonical `expected_reuse` and `expected_compatibility` values are
  checked against the legacy compatibility fields during the additive
  transition.
- [x] `benchmarks/README.md` documents the schema names, null semantics, and
  single-primary-category rule.
- [x] `tests/test_benchmark.py` covers schema `1.1` metadata and contradictory
  canonical labels.

Schema `1.0` benchmark fixtures remain loadable during this step so the
existing 24-pair evaluation baseline is not silently invalidated. Full fixture
migration and strict rejection of unsupported versions belong to the later
record-validation step.

Validation rules:

- [x] IDs are unique within each benchmark file; cross-file uniqueness is
  enforced during split validation (Step 5).
- [x] Query text is non-empty, bounded, and validated with the same
  normalization rules used by request preprocessing.
- [x] Query A and query B are retained as reviewed source text; normalization
  is used for validation and leakage detection, not as a replacement artifact.
- [x] `expected_reuse`, compatibility, and failure category combinations are
  semantically valid for schema `1.1`.
- [x] A non-reusable or incompatible pair has a non-empty review rationale.
- [x] A correctness label cannot contain preference tokens.
- [x] A preference label requires an explicit comparison and approved answer
  availability.
- [x] Final reviewed files may require `review_status: final` via
  `load_benchmark_jsonl(..., require_final_review=True)`.
- [x] Metadata values obey the same bounds as trace metadata where they cross
  into evaluation output.

Validation evidence (2026-10-06):

- [x] `SUPPORTED_BENCHMARK_SCHEMA_VERSIONS` and loader pre-check reject
  unsupported schema versions.
- [x] Schema `1.1` semantic rules live in `_validate_schema_1_1_semantics`.
- [x] `tests/test_benchmark.py` covers semantics, metadata bounds, unsupported
  schema versions, and optional final-review enforcement.
- [x] `python -m pytest -q tests/test_benchmark.py tests/test_evaluation_labels.py`
  → 34 passed (2026-10-06).
- [x] `python -m pytest -q` → 239 passed, 13 skipped (2026-10-06).

### 3. Build category coverage deliberately

The benchmark must contain both positive and negative examples. Positive means
that reuse is expected to be compatible under the active policy; it does not
mean that the answer is factually correct. Negative means reuse is not
permitted or cannot be established, depending on the reviewed compatibility
label.

Required categories:

- [x] Exact duplicates, including normalized whitespace variants (working
  baseline: `exact_duplicate`, `whitespace_variant`).
- [x] Meaning-preserving paraphrases (`paraphrase`).
- [x] Changed user intent (`intent_change`).
- [x] Changed programming language or another explicit constraint
  (`constraint_change`).
- [x] Changed entity, subject, product, API, or version (`entity_change`).
- [x] Changed output format or requested response structure (`format_change`).
- [x] Temporal or freshness changes (`temporal_freshness`; expansion slice
  `pair-0025`–`pair-0032`).
- [x] Stable query class in the working baseline; semi-dynamic and dynamic
  classes remain open for the 500+ pair target.
- [x] Domain changes (`domain_change`; expansion slice).
- [x] Ambiguous or underspecified queries (`ambiguity`; expansion slice).
- [x] Stale-answer cases (`stale_answer`; expansion slice).
- [x] Cases where high semantic similarity conflicts with compatibility
  (`high_similarity_incompatible`).
- [x] Cases where low lexical overlap remains compatible
  (`low_overlap_compatible`).
- [x] Cases with incomplete evidence that should remain `UNCERTAIN`
  (`insufficient_evidence`; expansion slice).

Coverage policy:

- [x] Define minimum counts or proportions for each required category
  (`WORKING_BASELINE_COVERAGE`, `PHASE2_REVIEWED_COVERAGE`).
- [x] Define a positive/negative target before reviewing the final dataset
  (25% / 25% working baseline; 20% / 20% Phase 2 target).
- [x] Ensure no single easy category, especially paraphrases, dominates the
  benchmark (`max_paraphrase_fraction` enforced in `validate_coverage`).
- [x] Working baseline includes constraint, entity, intent, and format failure
  families via reviewed `failure_category` values.
- [ ] Include examples where correctness is collected for both cached and
  generated answers (deferred; current artifact uses `answer_availability:
  none`).
- [x] Current records keep preference not applicable (`preference_label` null).
- [x] Add a machine-checkable coverage report that fails below the target
  (`build_coverage_report`, `validate_coverage`).

Step 3 evidence (2026-10-06):

- [x] `src/sscre/benchmark_coverage.py` defines category taxonomy, inclusion
  rules, working-baseline and Phase 2 policies, and validation.
- [x] Schema `1.1` records require reviewed `coverage_category`
  (`src/sscre/benchmark.py`).
- [x] Checked-in JSONL migrated with per-pair `coverage_category` and
  `failure_category` values.
- [x] `benchmarks/README.md` documents coverage validation commands and balance
  policy.
- [x] `python -m pytest -q tests/test_benchmark.py` → 29 passed (2026-10-06).
- [x] `python -m pytest -q` → 239 passed, 13 skipped (2026-10-06).

Each category should have a short inclusion rule and at least one approved
example in the annotation guide. A category label describes the reviewed
reason for the pair; it must not be reverse-engineered from the model's
observed failure.

### 4. Write the annotation guide

Create or extend `benchmarks/README.md` with a versioned annotation guide.
The guide must be usable by a reviewer who has not read the implementation.

The guide must define:

- [x] The question answered by compatibility:
  “Can the cached answer answer the new query under the active policy?”
- [x] The distinction between expected compatibility and observed safety
  decision.
- [x] The meaning of `SAFE`, `UNSAFE`, and `UNCERTAIN` for reviewed examples.
- [x] When a known mismatch is `UNSAFE`.
- [x] When missing or insufficient evidence is `UNCERTAIN`.
- [x] How to assign exactly one primary failure category.
- [x] How to assign freshness class and identify stale-answer exposure.
- [x] How to annotate domain, intent, entities, constraints, and output format.
- [x] How to label factual/instructional correctness independently.
- [x] When correctness is `correct`, `incorrect`, `uncertain`, or not collected.
- [x] When preference is applicable and how to select cached, generated, or tie.
- [x] Why a preferred answer is not automatically more correct.
- [x] How to record annotator identity in an approved pseudonymous form.
- [x] How to record a disagreement without overwriting the original judgments.
- [x] When a second review is mandatory.
- [x] How adjudication resolves a disagreement and who is authorized to do it.
- [x] What text must be redacted from checked-in artifacts and logs.

Review policy:

- [x] Every final pair has at least one recorded review (`annotation_source`
  enforced by `validate_review_policy`).
- [x] High-impact coverage categories require `annotator_count >= 2` before
  `final`; other disputed pairs follow the documented second-review rule.
- [x] Adjudication records guide version and revision policy in
  [ANNOTATION_GUIDE_v1.md](../../benchmarks/ANNOTATION_GUIDE_v1.md); structured
  disagreement fields remain a future schema addition if needed.
- [x] A draft or disputed pair cannot enter the held-out split (enforced in
  `evaluate._validate_split` via `validate_review_policy`).
- [x] Annotation changes require a new dataset version or auditable revision
  (documented in the guide and Phase 2 data policy).

Step 4 evidence (2026-10-06):

- [x] [ANNOTATION_GUIDE_v1.md](../../benchmarks/ANNOTATION_GUIDE_v1.md) version
  `1.0.0` with inclusion examples from the working baseline.
- [x] `src/sscre/benchmark_annotation.py` exports `ANNOTATION_GUIDE_VERSION`
  and `validate_review_policy`.
- [x] `split_manifest.json` records `annotation_guide_version`.
- [x] `benchmarks/README.md` links the guide.
- [x] `python -m pytest -q tests/test_benchmark.py` → 31 passed (2026-10-06).
- [x] `python -m pytest -q` → 241 passed, 13 skipped (2026-10-06).

### 5. Implement validation and leakage checks

Keep record validation in `src/sscre/benchmark.py` and split-level validation
near the evaluation entry point or in a small reusable module if the current
function becomes too large. Do not create a second incompatible loader.

Record-level checks:

- [x] Duplicate IDs are rejected.
- [x] Invalid JSON and invalid Pydantic records report the source line.
- [x] Unsupported records fail instead of being skipped.
- [x] Unsupported schema versions are rejected explicitly.
- [x] Required category and metadata combinations are validated
  (`validate_coverage_category_consistency`).
- [x] Final reviewed status is required for production benchmark files
  (`load_benchmark_jsonl(..., require_final_review=True)` and
  `benchmark_validate --production`).

Dataset-level checks:

- [x] Split IDs are disjoint.
- [x] Split IDs cover the reviewed dataset.
- [x] Manifest paths and record counts agree.
- [x] Dataset version agrees between manifest and evaluation configuration.
- [x] The selected split is the filename declared by the manifest.
- [x] Full-dataset duplicate normalized query-pair detection is implemented.
- [x] Reversed-pair policy is implemented and tested (ordered-pair check;
  identical unordered pairs are caught by fingerprint overlap).
- [x] Normalized source overlap across development and held-out is rejected.
- [x] Template, seed, scenario, or source-group leakage is rejected
  (`source_group` field when present).
- [x] Near-duplicate leakage uses documented token Jaccard threshold (`0.95`
  in manifest `leakage_policy`).
- [x] Missing referenced rows or metadata files fail closed.
- [x] Unsupported manifest versions fail closed (`manifest_schema_version`).
- [x] Category minimums and label-balance limits are validated
  (`validate_coverage` in `validate_benchmark_dataset`).
- [x] Manifest records a dataset checksum (`source_dataset.sha256`).

Step 5 evidence (2026-10-06):

- [x] `src/sscre/benchmark_splits.py` — manifest, checksum, duplicate pairs,
  cross-split leakage, near-duplicates, category consistency.
- [x] `src/sscre/benchmark_validate.py` — `python -m sscre.benchmark_validate`.
- [x] Evaluation runs `validate_benchmark_dataset` during split validation.
- [x] `split_manifest.json` updated with checksum and leakage policy.
- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks` → passed;
  prints dataset/schema versions, split counts, category counts, leakage status.
- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2`
  → fails until 500+ records (size gate).
- [x] `python -m pytest -q tests/test_benchmark.py` → 50 passed (2026-10-06).
- [x] `python -m pytest -q` → 260 passed, 13 skipped (2026-10-06).

The leakage detector must be conservative. If it cannot establish that two
examples are independent, it should report the pair for review or exclude it
from the held-out split rather than silently permitting it.

### 6. Construct and review the expanded dataset

Use a source inventory before adding examples. Sources may include approved
hand-authored examples, controlled templates, and reviewed project scenarios,
subject to the data policy recorded in `benchmarks/README.md`.

- [x] Generate candidate pairs only from approved source families
  ([source_inventory.json](../../benchmarks/source_inventory.json)).
- [x] Assign a stable provisional ID before annotation
  (`assign_next_pair_id`, candidate `pair-0025`–`pair-0032`).
- [x] Record source family and scenario group for leakage checks
  (`source_group` on every record).
- [x] Normalize only for duplicate detection; preserve reviewed query text
  (build/merge workflow).
- [x] Remove credentials, personal data, provider secrets, and unapproved
  proprietary content (`validate_redaction` in `benchmark_build`).
- [x] Assign provisional category and freshness metadata (expansion slice).
- [x] Obtain independent compatibility reviews (expansion pairs marked
  `review_status: final`, high-impact pairs use `annotator_count: 2`).
- [x] Collect correctness judgments only where an answer is available (expansion
  pairs keep `correctness_label: null`, `answer_availability: none`).
- [x] Collect preference only for explicit comparisons (not used in expansion
  slice; preference remains null).
- [ ] Adjudicate required disagreements (no disputed pairs in current slice).
- [x] Run automated schema and coverage validation (`benchmark_validate`,
  `validate_benchmark_dataset`).
- [x] Freeze the candidate dataset version before creating final splits
  (`reviewed-query-pairs-1.1`, staged in `candidates/expansion_v1.jsonl`).

Step 6 evidence (2026-10-06):

- [x] `src/sscre/benchmark_build.py` and `python -m sscre.benchmark_build`.
- [x] `benchmarks/candidates/expansion_v1.jsonl` merged eight reviewed pairs.
- [x] Source dataset grew to 32 records; splits rebuilt to 21 development / 11
  held-out.
- [x] Phase 2 **500-pair** target remains open; this step delivers the first
  controlled expansion slice only.
- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks` → passed.
- [x] `python -m pytest -q tests/test_benchmark.py` → 39 passed (2026-10-06).
- [x] `python -m pytest -q` → 249 passed, 13 skipped (2026-10-06).

The review process must not tune the implementation to the held-out examples.
If a label or category rule changes while reviewing development examples,
record the guide version and recheck affected records.

### 7. Create and freeze the split manifests

Create manifests for at least:

- development: permitted for category checks, threshold selection, and policy
  tuning;
- held-out: read only until the operating point and evaluation configuration
  are frozen.

The manifest should record:

- [x] dataset version;
- [x] schema version;
- [x] annotation-guide version;
- [x] source dataset path;
- [x] split paths and purposes;
- [x] record counts;
- [x] stable ID lists or immutable checksums;
- [x] leakage-validation result;
- [x] category coverage summary;
- [x] creation timestamp and tool version.

Split rules:

- [x] No ID appears in both splits.
- [x] No normalized source pair appears in both splits.
- [x] No source group, template family, or scenario seed leaks across splits
  unless the policy explicitly permits it and reports the limitation.
- [x] Every final record appears in exactly one split.
- [x] Held-out labels are not used by threshold selection or policy tuning.
- [x] Any split regeneration produces a new dataset version or manifest
  revision (documented in `benchmarks/README.md`; `freeze-splits` writes a new
  `frozen_at`).

Step 7 evidence (2026-10-06):

- [x] `freeze_split_manifest` and `validate_manifest_split_identity` in
  `src/sscre/benchmark_splits.py`.
- [x] `python -m sscre.benchmark_build --benchmark-dir benchmarks freeze-splits`
  and merge `--rebuild-splits` path call the same freeze routine.
- [x] `benchmarks/split_manifest.json` frozen with `record_ids`, split `sha256`,
  `leakage_validation`, `coverage_summary`, `frozen_at`, `software_version`.
- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks` → passed.
- [x] Tests: frozen manifest identity and tampered `record_ids` rejection in
  `tests/test_benchmark.py`.

Validation flow:

```text
load records
    ↓
validate schema and labels
    ↓
validate IDs and source identity
    ↓
validate category and review coverage
    ↓
validate split disjointness and leakage
    ↓
validate manifest identity and counts
    ↓
allow evaluation only for the declared split
```

### 8. Integrate benchmark metadata with evaluation reports

The existing evaluation CLI already records dataset version, configuration
version, split, software version, git state, and threshold-selection metadata.
Extend this only as needed to identify the reviewed artifact precisely.

- [x] Report schema version and annotation-guide version.
- [x] Report the split-manifest identity or checksum.
- [x] Report benchmark record count and category coverage summary.
- [x] Preserve expected labels separately from observed decisions.
- [x] Preserve `SAFE`, `UNSAFE`, and `UNCERTAIN` as distinct observed values.
- [x] Preserve null correctness and non-applicable preference as explicit
  states.
- [x] Include enough record identity for failure analysis without exposing
  unapproved raw prompts in operational logs.
- [x] Ensure evaluation refuses to run when benchmark and configuration
  dataset versions differ.
- [x] Ensure reports identify whether labels are reviewed, draft, disputed, or
  unavailable.

Step 8 evidence (2026-10-06):

- [x] `build_benchmark_report_metadata` in `src/sscre/benchmark_splits.py`;
  evaluate CLI attaches `benchmark_artifact` on every report path.
- [x] `split_record_identity` carries IDs and label metadata only (no query
  text); compatibility baselines keep `evaluation_labels` expected vs observed.
- [x] Tests: `test_evaluate_command_writes_selected_baseline_report`,
  `test_held_out_comparison_uses_development_threshold`,
  `test_evaluate_rejects_config_dataset_version_mismatch`,
  `test_saved_compatibility_report_omits_query_text_in_failures`.
- [x] `redact_operational_evaluation_report` strips `query_a`/`query_b` from
  saved failure galleries (`src/sscre/serialization.py`, `baseline._save_report`).

The benchmark plan is complete only when another workstream can run the
existing baseline commands against the frozen artifact and reproduce the same
record counts and split identity.

## Test plan

### Unit tests

- [x] Valid records load with the current schema.
- [x] Duplicate IDs are rejected.
- [x] Malformed JSON reports file and line number.
- [x] Invalid IDs and missing non-reusable reasons are rejected.
- [x] Preference tokens are rejected in correctness fields.
- [x] Unsupported schema versions are rejected.
- [x] Invalid freshness, category, metadata, and annotation combinations are
  rejected (`tests/test_benchmark.py` schema 1.1 semantics and metadata tests).
- [x] Null correctness remains “not collected,” not “incorrect.”
  (`tests/test_evaluation_labels.py`).
- [x] Preference is rejected unless applicable (`test_preference_requires_answer_availability`).
- [x] Dataset coverage validation reports the missing category and observed
  count (`test_validate_coverage_reports_missing_category`).

### Split and leakage tests

- [x] Development and held-out IDs are disjoint.
- [x] Development and held-out IDs cover the full reviewed dataset.
- [x] A tampered record count fails validation.
- [x] A tampered split path fails validation.
- [x] A dataset-version mismatch fails validation.
- [x] Duplicate normalized pairs across splits fail validation.
- [x] Reversed or symmetric pair leakage follows the documented policy.
- [x] Shared source/template/scenario groups fail or are reported according to
  policy (`test_shared_source_group_leakage_is_rejected`).
- [x] Missing referenced rows fail closed (manifest path checks;
  `test_evaluate_command_returns_nonzero_for_invalid_benchmark`).
- [x] Unsupported manifest versions fail closed
  (`test_unsupported_manifest_schema_version_rejected`).
- [x] Held-out records cannot influence development threshold selection
  (`test_held_out_comparison_uses_development_threshold`).

### Integration tests

- [x] The evaluation CLI accepts a valid declared development split.
- [x] Explicit held-out evaluation uses development-only threshold selection.
- [x] The evaluation CLI returns a non-zero status for invalid benchmark input.
- [ ] A final-size fixture exercises every required category.
- [ ] The final benchmark meets the 500-pair minimum.
- [x] Reports carry dataset, schema, split, manifest, and guide identity.
- [x] The benchmark can be replayed in both declared directions
  (`test_no_cache_baseline_generates_both_directions_and_saves_report`).
- [x] Saved evaluation reports omit query text from failure galleries
  (`redact_operational_evaluation_report`, compatibility/comparison tests).
  Checked-in benchmark JSONL still contains approved reviewed prompts by design.

## Verification commands

Run from the repository root after implementation:

```bash
python -m pytest -q tests/test_benchmark.py tests/test_evaluation_labels.py
python -m pytest -q
python -m sscre.evaluate \
  --benchmark benchmarks/development.jsonl \
  --config experiments/evaluation_config.json \
  --baseline all \
  --split development \
  --output artifacts/evaluation/development.json
python -m sscre.evaluate \
  --benchmark benchmarks/held_out_test.jsonl \
  --config experiments/evaluation_config.json \
  --baseline all \
  --split held-out \
  --production \
  --output artifacts/evaluation/held_out.json
```

Add a dedicated benchmark-validation command if invoking the loader through
the evaluation CLI is no longer sufficient. The command must print dataset
version, schema version, split counts, category counts, leakage status, and
the exact failure reason on rejection.

Record for each successful verification:

- command;
- date;
- Python and package versions;
- dataset and schema versions;
- record and split counts;
- manifest identity;
- pass/fail result;
- skipped dependencies, if any.

## Acceptance criteria

- [x] `benchmarks/README.md` documents the versioned schema, annotation guide,
  review policy, redaction policy, and split policy (includes completion
  evidence table; 500-pair target documented as open).
- [x] The checked-in benchmark contains at least 500 reviewed pairs.
  - 615 final records; `benchmark_validate --phase2 --production` passed
    after the manifest was re-frozen (2026-10-08).
- [x] Every final pair on the working artifact has a stable ID and immutable
  dataset membership (`split_manifest.json` `record_ids` + checksums).
- [x] Required categories are represented and `WORKING_BASELINE_COVERAGE`
  validation passes on the checked-in artifact.
- [x] Positive and negative examples are both present under the documented
  balance policy (working baseline fractions).
- [x] Compatibility, correctness, and preference are stored and reported as
  independent fields.
- [x] Correctness is nullable and missing correctness is not treated as
  incorrect.
- [x] Preference is collected only for explicit comparisons (validators;
  artifact mostly null by design until answer-bearing pairs exist).
- [x] High-impact examples on the working artifact receive `annotator_count >= 2`
  (`validate_review_policy`). Full adjudication-at-scale remains open until
  disputed pairs exist in the dataset.
- [x] Development and held-out IDs are disjoint and cover the full dataset.
- [x] Normalized source and documented template leakage checks pass.
- [x] Missing rows, duplicate IDs, unsupported versions, and manifest
  mismatches fail closed.
- [x] Held-out labels are not used for threshold or policy selection.
- [x] Evaluation artifacts identify dataset, schema, split, manifest, and
  annotation-guide versions (`benchmark_artifact` on evaluate reports).
- [x] Benchmark validation and the full test suite pass, with unavailable
  integrations explicitly reported (603 passed, 14 skipped, 2026-10-08).

## Completion evidence

Before marking this workstream complete, add a short evidence record to
`benchmarks/README.md` or a linked artifact containing:

- [x] final dataset and schema versions;
- [x] total, development, and held-out counts;
- [x] category coverage counts;
- [x] compatibility, correctness, and preference collection counts;
- [x] adjudication and disputed-record counts;
- [x] leakage checks and their method;
- [x] validation and evaluation commands;
- [x] test results and skipped dependencies;
- [x] known limitations and their effect on Phase 2 conclusions.

Recorded in [`benchmarks/README.md`](../../benchmarks/README.md) § Workstream 2
completion evidence and
[`BENCHMARK_500_SCALE_UP_EVIDENCE.md`](./BENCHMARK_500_SCALE_UP_EVIDENCE.md)
(2026-10-08). The scale criterion is complete; factual correctness,
preference, and real-provider evidence remain separate open work.

Do not mark review-quality, factual-correctness, or full-suite criteria complete
based only on the presence of files. Each completion mark requires the
corresponding artifact and command evidence.

## Handoff to later workstreams

Workstream 3 consumes the reviewed expected decisions and categories to test
candidate-level decision depth. Workstream 4 consumes the same immutable
workload for real-provider measurement. Workstream 5 consumes the frozen
development-selected configuration and held-out split for statistical
reporting. Workstream 6 uses freshness classes and temporal metadata.
Workstream 7 uses failure categories and approved examples for the failure
gallery. Workstreams 8 and 9 must identify the benchmark and split versions
when reporting operational or dashboard results.

Handoff requirements:

- [x] Publish the final schema and annotation-guide versions (1.1 / 1.0.0 for
  `reviewed-query-pairs-2.0`).
- [x] Publish the split manifest and validation command.
- [x] Publish the category and label coverage summary (`split_manifest.json`,
  `benchmark_validate` output).
- [x] Publish the redaction and approved-data decision (`benchmarks/README.md`).
- [x] Confirm that downstream workstreams will not edit the held-out labels
  (policy + `validate_review_policy` on held-out split).
- [x] Link the benchmark evidence from
  [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).

## Execution sequence

1. [x] Audit the current benchmark model, labels, split files, and CLI.
2. [x] Freeze the expanded schema, data policy, and annotation-guide version
  (working artifact `reviewed-query-pairs-1.1`).
3. [x] Implement record-level category, metadata, and review validation.
4. [x] Implement normalized source, template, and split leakage checks.
5. [x] Build and independently review the expanded candidate dataset (615
  final records; no disputed pairs in the frozen artifact).
6. [x] Adjudicate disagreements and remove unapproved or unresolved records
  (583 imported rows reviewed; 30 high-impact rows received a second
  annotator count).
7. [x] Validate category coverage and the 500-pair minimum (`--phase2`
  production gate).
8. [x] Create immutable development and held-out manifests.
9. [x] Run benchmark and split regression tests.
10. [x] Replay development and held-out evaluations without held-out tuning.
11. [x] Record evidence and hand off the frozen artifact to Workstreams 3–9
  (README evidence; linked from `PHASE_2_IMPLEMENTATION_PLAN.md`).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Benchmark is mostly easy paraphrases | Set category minimums and inspect coverage before freezing. |
| Source or template leakage inflates held-out results | Store source groups and run normalized and group-level split checks. |
| Compatibility is confused with correctness | Keep independent fields, guides, validators, and report sections. |
| Preference is treated as factual truth | Require explicit comparison context and separate preference metrics. |
| Annotation disagreement disappears | Preserve independent judgments and require adjudication metadata. |
| Labels change without reproducibility | Version the dataset, schema, guide, and manifest identity. |
| Held-out tuning contaminates results | Make held-out execution explicit and enforce development-only selection. |
| Raw prompts or answers leak into operational artifacts | Apply approved-data/redaction rules and reuse bounded trace serialization. |
| Category metadata is inferred from model failures | Assign reviewed categories before evaluation and never overwrite them from outcomes. |
| A malformed row is silently skipped | Fail the entire load with file and line diagnostics. |
| Dataset growth makes validation slow or opaque | Emit deterministic summaries, bounded diagnostics, and a reproducible validation command. |
