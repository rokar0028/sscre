# Phase 2 Workstream 9 Implementation Plan

## Goal

Turn the stable Phase 2 evaluation artifacts into a bounded, read-only
dashboard package and define a separate, opt-in dual-model experiment gate.
The dashboard must display existing evidence without becoming a second
statistics or metrics pipeline. The dual-model path must not enter the default
MVP request path and must keep preference, correctness, compatibility, and
operational measurements separate.

The target outcome is a reproducible package that answers:

- which evaluation artifacts were loaded and whether their dataset, split, and
  schema metadata agree;
- what the frozen operating point, baseline comparison, confidence intervals,
  Pareto results, failure categories, freshness results, and storage/eviction
  observations say;
- which values are unavailable, sparse, synthetic, simulated, or otherwise
  limited;
- whether a proposed second-model experiment has a written hypothesis,
  budget, review process, success criterion, and stopping rule;
- whether any dual-model result is clearly separated from the default cache
  path and from factual-correctness claims.

This workstream owns dashboard presentation and the experiment gate. It does
not own evaluation replay, threshold selection, freshness-policy selection,
failure-category aggregation, PostgreSQL verification, live-provider
measurement, or product-scale observability.

## Status

**Step 4 dashboard views complete; presentation-safety refinements and
dual-model implementation not started (2026-10-11).**

Audit:
[`WORKSTREAM_9_STEP1_AUDIT.md`](./WORKSTREAM_9_STEP1_AUDIT.md).

Parent:
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).

Upstream inputs:

- [`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md)
- [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md)
- [`WORKSTREAM_7_EVIDENCE.md`](./WORKSTREAM_7_EVIDENCE.md)
- [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md)

No dashboard artifact, dual-model artifact, or WS9 completion evidence is
claimed by this plan.

## Goal / exit gates

### Planning gate

- [x] Define dashboard scope, source artifacts, display sections, and
  non-recomputation rules.
- [x] Define the dual-model experiment gate, required metadata, and separate
  preference/correctness semantics.
- [x] Identify the current implementation baseline and open gaps.
- [x] Keep dashboard implementation and dual-model execution independently
  approvable.

### Dashboard implementation gate

- [ ] User explicitly approves implementation of the dashboard slice.
- [ ] The input artifact list, schema versions, and manifest-alignment policy
  are frozen before implementation.
- [ ] The dashboard delivery form is approved as a static export or another
  bounded read-only form; no public API or live analytics service is assumed.

### Dual-model experiment gate

- [ ] User explicitly approves a dual-model experiment separately from the
  dashboard.
- [ ] A written experiment definition is reviewed before any provider request.
- [ ] Credentials, model pair, prompt settings, budget, review capacity, and
  stop conditions are available and approved.
- [ ] The experiment is opt-in and absent from the default application path.

### Verification gate

- [ ] Dashboard values are verified against source artifacts on the same
  dataset, split, and schema versions.
- [ ] Dashboard redaction, unavailable-state, accessibility, and bounded-size
  behavior are tested.
- [ ] Dual-model outputs, if run, pass schema, redaction, budget, and
  preference/correctness separation tests.
- [ ] Focused and full-suite verification results are recorded.
- [ ] Parent plan, README, limitations, and transition references match the
  actual implementation and any deferred gate.

### Exit gate

- [ ] A dashboard artifact and regeneration command are published, or the
  dashboard gate is explicitly deferred with the reason.
- [ ] A dual-model artifact is published, or the dual-model gate is explicitly
  deferred with the reason.
- [ ] All displayed and recorded values retain their source environment,
  dataset, split, and limitation metadata.
- [ ] No dashboard or experiment artifact exposes credentials, unrestricted
  prompts, unrestricted answers, or unsupported production claims.
- [ ] Completion evidence is linked from the parent plan.

## Learning objectives

- [ ] Explain why a dashboard that reads artifacts is not a second metrics
  pipeline.
- [ ] Distinguish a copied point estimate from a recomputed aggregate.
- [ ] Interpret unavailable, sparse, synthetic, simulated, and real-provider
  measurement states without converting them to zero.
- [ ] Keep compatibility, correctness, and preference as independent
  evaluation dimensions.
- [ ] Design a dual-model experiment with a predeclared hypothesis, budget,
  success criterion, and stopping rule.
- [ ] Identify when a preference comparison cannot support a correctness
  conclusion.
- [ ] Preserve artifact redaction and boundedness at a presentation boundary.

## Scope

### Included

- A read-only dashboard package consuming the existing WS5, WS6, WS7, and WS8
  machine-readable artifacts.
- Artifact discovery, schema validation, source metadata checks, and explicit
  unavailable-state handling.
- An operating-point summary, baseline comparison, confidence-interval view,
  Pareto view, failure-category view, freshness view, and storage/eviction
  view.
- Source paths, artifact schema versions, dataset version, split, manifest
  identity, measurement environment, timestamps, and limitations.
- Static export suitable for local review and checked-in evidence, unless a
  separately approved delivery form replaces it.
- HTML escaping, bounded text rendering, redaction checks, and basic keyboard
  and screen-reader-friendly structure.
- A versioned dual-model experiment definition and, only after approval, a
  bounded opt-in runner and result artifact.
- Independent preference and correctness review fields when those reviews are
  actually available.
- Regression tests proving that dashboard values come from source artifacts and
  that absent inputs remain unavailable.

### Excluded

- A second evaluation, bootstrap, confidence-interval, Pareto, freshness, or
  failure-category computation pipeline.
- Threshold tuning, operating-point selection, or held-out replay.
- Changes to SAFE, UNSAFE, UNCERTAIN, compatibility, freshness, or cache
  serving semantics.
- A public `/dashboard` or `/v1/failures` API unless separately approved as a
  product requirement.
- Database-backed analytics, event ingestion, unbounded telemetry, user
  accounts, or multi-tenant dashboard authorization.
- Automatic refresh that silently changes the evidence shown to a reviewer.
- Credentialed provider calls as part of dashboard generation.
- Enabling a second model in the default request or fallback path.
- Treating preference as factual correctness, compatibility, or safety.
- A dual-model claim about production quality, cost, latency, or capacity
  without the corresponding approved measurement protocol.
- Full human correctness labeling of the 615-pair benchmark.
- Model training, fine-tuning, prompt optimization, or provider selection.

## Frozen semantics

The following rules remain unchanged:

```text
dashboard                -> read generated artifacts only
missing input             -> explicit unavailable state
schema mismatch           -> fail closed or explicit diagnostic mode
synthetic metric          != real-provider metric
simulated failure         != live restart result
point estimate            != recomputed dashboard metric
preference                != correctness
compatibility             != correctness
dual-model experiment     != default application behavior
dashboard                 != production-capacity or SLA evidence
```

Required invariants:

- a dashboard must not silently combine artifacts with different dataset
  versions, split names, manifest identities, or incompatible schema versions;
- a missing or invalid source must not be rendered as zero, an empty success,
  or a passed result;
- source values must retain their measurement environment and limitations;
- a dashboard transformation may format, order, or select bounded fields, but
  must not recalculate evaluation metrics;
- raw queries, answers, credentials, provider secrets, and unrestricted
  prompts must not be emitted into dashboard or experiment artifacts;
- dual-model results must identify model, provider, prompt/configuration,
  sample, review, and budget metadata;
- preference labels and correctness labels must be stored and reported in
  separate fields, with unavailable correctness remaining unavailable;
- any provider failure, timeout, budget exhaustion, or review shortfall must
  be visible and must not be treated as a successful comparison.

## Current baseline

### Existing implementation and evidence

- [x] WS5 publishes held-out comparison, statistics, and Pareto artifacts.
  Evidence: `artifacts/evaluation/workstream5-held-out-comparison.json` and
  `artifacts/evaluation/workstream5-held-out-pareto.json`.
- [x] WS5 records confidence intervals, operating-point metadata, and
  synthetic-replay limitations.
  Evidence: `WORKSTREAM_5_EVIDENCE.md`.
- [x] WS6 publishes development, held-out, and invalidation freshness
  artifacts with selected-policy and sparse-scope metadata.
  Evidence: `WORKSTREAM_6_EVIDENCE.md`.
- [x] WS7 publishes a consolidated quality-analysis JSON and static HTML
  failure gallery with redaction and unavailable-section handling.
  Evidence: `WORKSTREAM_7_EVIDENCE.md`.
- [x] WS8 publishes bounded operational verification JSON with explicit
  simulated/live distinctions and non-capacity language.
  Evidence: `WORKSTREAM_8_EVIDENCE.md`.
- [x] Existing static HTML export code uses standard-library HTML generation
  and escaping; no dashboard framework is currently declared.
  Touch points: `src/sscre/gallery_export.py`,
  `src/sscre/failure_gallery_export.py`, and `pyproject.toml`.
- [x] Provider comparison tooling keeps synthetic and real-provider values
  separate.
  Touch point: `src/sscre/provider_compare.py`.
- [x] The default application path has no dual-model fallback.
  Touch point: `src/sscre/app.py`.

### Open baseline gaps

- [x] WS9 dashboard JSON/HTML artifacts and an export CLI now exist.
  Evidence: `artifacts/evaluation/workstream9-dashboard.json`,
  `artifacts/evaluation/workstream9-dashboard.html`,
  `src/sscre/dashboard.py`, and the `sscre-dashboard-export` entry point.
- [x] The loader builds a single bounded input manifest and validates all
  declared WS5–WS8 sources together.
  Evidence: `src/sscre/dashboard.py`,
  `tests/test_workstream9_dashboard.py`.
- [x] Focused dashboard-loader tests prove source-value fidelity for the
  implemented Step 2 projections and explicit metadata mismatch behavior.
  Evidence: `tests/test_workstream9_dashboard.py`.
- [ ] No dashboard accessibility or bounded-rendering checks exist.
- [ ] No written dual-model experiment configuration exists in the repository;
  the separate schema boundary is frozen in the Step 1 audit.
- [ ] No opt-in dual-model runner or result schema exists.
- [ ] No approved model pair, provider budget, review capacity, or stopping
  rule exists.
- [ ] Correctness labels remain unavailable for the current held-out package;
  the dashboard must preserve that state.
- [ ] Live-provider evidence remains unavailable or separately labeled; the
  dashboard must not imply it from synthetic artifacts.

## Input artifact contract

The dashboard reads these artifacts by default. The Step 1 audit freezes the
known schema versions and metadata identities; runtime implementation must
validate them rather than assume them from filenames.

| Source | Planned dashboard use | Required behavior |
|---|---|---|
| `artifacts/evaluation/workstream5-held-out-comparison.json` | Baselines, rates, intervals, operating point | Copy bounded comparison values and preserve synthetic-replay labels. |
| `artifacts/evaluation/workstream5-held-out-pareto.json` | Pareto frontier and constraint result | Render available frontier points; identify unavailable planes. |
| `artifacts/evaluation/workstream6-development-freshness.json` | Selected-policy provenance | Show development selection provenance, not as held-out performance. |
| `artifacts/evaluation/workstream6-held-out-freshness.json` | Freshness protection and stale exposure | Copy scope and unavailable classes without replay. |
| `artifacts/evaluation/workstream6-invalidation.json` | Invalidation result | Show pass, unavailable, or limited status from the artifact. |
| `artifacts/evaluation/workstream7-quality-analysis.json` | Failure categories and bounded examples | Render consolidated aggregates and permitted example fields only. |
| `artifacts/operations/workstream8-operational-verification.json` | Storage, eviction, latency, and operational limitations | Preserve bounded local-environment and non-capacity language. |
| `artifacts/evaluation/workstream4-provider-comparison.json` when present | Provider comparison | Keep synthetic and real-provider rows separate. |
| `artifacts/evaluation/workstream4-real-provider-unavailable.json` when present | Provider availability | Display the unavailable reason; never substitute synthetic values. |

The dashboard must be able to render a complete but partially unavailable
package. It must not require optional real-provider evidence to display the
synthetic and operational sections.

## Planned artifact contracts

### Dashboard package

Planned outputs:

- `artifacts/evaluation/workstream9-dashboard.json`
- `artifacts/evaluation/workstream9-dashboard.html`
- `docs/phase-2/WORKSTREAM_9_EVIDENCE.md`

The JSON package is a bounded view manifest, not a replacement for upstream
reports. It should contain:

- a dashboard schema version;
- generation timestamp, git identity, and dirty-state metadata;
- input artifact paths, schema versions, dataset version, split, and manifest
  identity;
- bounded display sections for summary, baselines, intervals, Pareto,
  failures, freshness, operations, and limitations;
- explicit `unavailable` records with non-empty reasons;
- source references for each display section;
- a list of omitted or unsupported sections;
- no raw query, answer, credential, token, or unrestricted prompt fields.

The HTML package should be reproducible from the JSON package and should not
make the JSON package the only auditable source. If a static HTML-only
delivery is selected, the same source and redaction rules still apply.

### Dual-model experiment definition

Planned configuration:

- `experiments/workstream9_dual_model_v1.json`

Required fields:

- experiment ID and schema version;
- hypothesis and competing interpretation;
- model A and model B identifiers, provider names, endpoint origins, and
  version/configuration identifiers;
- prompt template/version, generation settings, timeout, retry policy, and
  output bounds;
- dataset version, split, sample selection, and exclusion rules;
- preference question and reviewer instructions;
- correctness review rubric and adjudication process, or an explicit
  `correctness_unavailable` record;
- token, request, cost, time, and reviewer budgets;
- success criterion, minimum sample, confidence method if applicable, and
  stopping rule;
- redaction and retention policy;
- opt-in execution flag that defaults to disabled.

### Dual-model result

Planned output:

- `artifacts/evaluation/workstream9-dual-model-v1.json`

The result must distinguish:

- request/provider status and failure counts;
- model-specific latency, token, and cost values when measured;
- preference outcomes and their denominator;
- correctness outcomes and their denominator;
- compatibility or safety outcomes if separately evaluated;
- abstentions, ties, reviewer disagreements, and unavailable fields;
- budget usage and stop reason;
- limitations and whether the result is synthetic, real-provider, or mixed.

No result may claim that the preferred model is more factually correct unless
the approved correctness review supports that claim.

## Implementation steps

### 1. Audit and freeze the dashboard input protocol

Inventory the stable WS5–WS8 artifacts, their schemas, optional inputs, source
limitations, and current redaction boundaries before adding dashboard code.

- [x] Record the current commit, branch, Python version, dependency versions,
  and working-tree status.
  Evidence: [`WORKSTREAM_9_STEP1_AUDIT.md`](./WORKSTREAM_9_STEP1_AUDIT.md)
  § Environment snapshot.
- [x] Confirm every default input artifact path exists and is valid JSON.
  Evidence: Step 1 audit § Source inventory; 9/9 paths passed.
- [x] Record each input artifact's schema version, dataset version, split,
  manifest identity, measurement environment, and timestamp.
  Evidence: Step 1 audit § Source inventory.
- [x] Define which inputs are required for each dashboard section.
  Evidence: Step 1 audit § Required and optional source behavior.
- [x] Define fail-closed behavior for missing, malformed, stale, or
  metadata-incompatible inputs.
  Evidence: Step 1 audit § Fail-closed rules.
- [x] Freeze the dashboard package schema and section names before generating
  checked-in output.
  Schema: `workstream9-dashboard-1.0`; sections and source rules are in the
  Step 1 audit.
- [x] Freeze the dual-model experiment schema separately from the dashboard
  schema.
  Schema: `workstream9-dual-model-experiment-1.0`; boundary is in the Step 1
  audit.

Planned touch points:
`src/sscre/serialization.py`, existing artifact validators, the WS5–WS8
artifact paths above, and
[`WORKSTREAM_9_STEP1_AUDIT.md`](./WORKSTREAM_9_STEP1_AUDIT.md).

### 2. Build a bounded artifact loader and view manifest

Add the smallest reusable loader needed to validate source metadata and build a
read-only dashboard view. Reuse existing validators and serializers; do not
replay evaluation or duplicate metric calculations.

- [x] Load each source through a typed or explicitly validated boundary.
  `src/sscre/dashboard.py` uses `_LoadedSource` and explicit source contracts.
- [x] Validate top-level shape, schema version, dataset version, split, and
  manifest identity where the source provides them.
  Primary identity and source descriptors are validated before projection.
- [x] Reject silent cross-split or cross-dataset merges.
  Mismatches become explicit `metadata_mismatch` sections; malformed required
  sources raise `DashboardInputError`.
- [x] Allow documented optional artifacts to be absent and emit an explicit
  unavailable block.
  Provider inputs, Pareto, development freshness, and invalidation are
  represented with bounded unavailable metadata when absent.
- [x] Preserve source paths and source metadata for every displayed section.
  Each section records bounded source descriptors.
- [x] Copy only bounded numeric, categorical, and approved display fields.
  `_bounded_tree`, field allowlists, forbidden-key checks, depth/list/map
  limits, and a 250,000-byte manifest limit enforce the boundary.
- [x] Validate the final view manifest with the serialization/redaction
  boundary before writing it.
  `validate_dashboard_view_manifest` calls
  `validate_redacted_report_payload`; Step 3 will add file export.
- [x] Ensure a source value is not recalculated during loading.
  Loader projections copy source fields and do not replay or aggregate metrics.

Verification (2026-10-11):

- `python -m pytest -q tests/test_workstream9_dashboard.py` →
  **5 passed**.
- `python -m pytest -q tests/test_serialization_boundary.py
  tests/test_workstream7_failure_gallery.py
  tests/test_failure_gallery_export_cli.py` → **35 passed**.
- `python -m pytest -q` → **710 passed, 15 skipped, 21 deselected**;
  one existing FastAPI/httpx deprecation warning.

Candidate module:
`src/sscre/dashboard.py` or a similarly small module selected after the audit.
Do not add a framework or database solely for this view manifest.

### 3. Implement the dashboard export

Generate a deterministic local artifact from the validated view manifest.
Reuse the existing static-export style where practical.

- [x] Add a CLI with explicit input paths and output paths.
  `python -m sscre.dashboard` and `sscre-dashboard-export`.
- [x] Make default paths point to the checked-in WS5–WS8 artifacts without
  requiring live provider or PostgreSQL access.
- [x] Provide a diagnostic override only for intentionally mismatched inputs;
  record the mismatch prominently instead of hiding it.
  `--allow-metadata-mismatch` is required for export when a section has
  `metadata_mismatch`.
- [x] Emit the JSON package before or alongside HTML so the source values are
  independently inspectable.
  Outputs: `artifacts/evaluation/workstream9-dashboard.json` and
  `artifacts/evaluation/workstream9-dashboard.html`.
- [x] Make regeneration deterministic except for explicitly documented
  timestamp and git identity fields.
  `generation.generated_at`, `git_commit`, and `git_worktree_dirty` are the
  documented variable fields.
- [x] Return a non-zero exit code for malformed required inputs or redaction
  violations.
  CLI catches `DashboardInputError` and returns exit code 1.

Verification (2026-10-11):

- `python -m sscre.dashboard --help` → passed.
- `sscre-dashboard-export --help` → passed after editable
  `python -m pip install -e ".[dev]"`.
- `python -m sscre.dashboard --json-output
  artifacts/evaluation/workstream9-dashboard.json --html-output
  artifacts/evaluation/workstream9-dashboard.html` → passed.
- Generated artifact sizes: JSON 168,314 bytes; HTML 172,341 bytes.
- `python -m pytest -q tests/test_workstream9_dashboard.py` →
  **7 passed**.
- `python -m pytest -q` → **712 passed, 15 skipped, 21 deselected**;
  one existing FastAPI/httpx deprecation warning.

Planned entry point:
`sscre-dashboard-export`, with `python -m sscre.dashboard` as the source-tree
equivalent if that module is selected.

### 4. Add the required dashboard views

Each view must identify its source artifact and measurement environment.

- [x] Operating-point summary: selected threshold/policy, constraint result,
  selection split, and development-only provenance.
- [x] Baseline comparison: no-cache, exact-cache, embedding-only, and
  compatibility-aware results where present.
- [x] Confidence intervals: point estimates, interval bounds, sample counts,
  method, seed, and confidence level copied from WS5.
- [x] Pareto view: available frontier points, axes, dominance/constraint
  metadata, and unavailable storage plane when applicable.
- [x] Failure-category view: WS7 category counts/rates and interval metadata;
  no category recomputation.
- [x] Freshness view: selected policy, class scope, stale-exposure accounting,
  invalidation status, and explicit sparse/unavailable classes.
- [x] Operations view: WS8 latency, throughput, errors, storage, eviction,
  environment, and unsupported-claim language.
- [x] Limitations view: source limitations, unavailable sections, and
  synthetic/simulated/live distinctions.
- [x] Provider view: synthetic and real-provider rows remain visually and
  semantically separate.

Evidence: `src/sscre/dashboard.py`,
`artifacts/evaluation/workstream9-dashboard.json`,
`artifacts/evaluation/workstream9-dashboard.html`, and
`tests/test_workstream9_dashboard.py`.

Verification (2026-10-11):

- `python -m pytest -q tests/test_workstream9_dashboard.py` →
  **7 passed**.
- `python -m pytest -q` → **712 passed, 15 skipped, 21 deselected**;
  one existing FastAPI/httpx deprecation warning.

### 5. Enforce presentation safety and accessibility

Treat the dashboard as a new serialization boundary, not as a trusted
internal page.

- [ ] Escape all displayed text before HTML insertion.
- [ ] Reject forbidden raw-content and credential-like keys in the dashboard
  package.
- [ ] Bound lists, strings, nested objects, and rendered HTML size.
- [ ] Preserve explicit unavailable and error states in text, not only color.
- [ ] Use headings, landmarks, table headers, labels, and keyboard-accessible
  navigation for the static view.
- [ ] Avoid charts that have no text equivalent; provide bounded data or
  summaries alongside any visual.
- [ ] Add tests for malformed artifacts, redaction, HTML escaping, and
  unavailable-state rendering.

### 6. Write and review the dual-model experiment definition

Do not run provider requests until the experiment is sufficiently specified to
interpret a result.

- [ ] State the hypothesis and what would count as evidence against it.
- [ ] Choose the model pair and record provider/model versions without
  storing credentials.
- [ ] Freeze prompt, system instructions, generation settings, timeout,
  retry, and output-size limits.
- [ ] Select a bounded development or explicitly approved held-out sample
  without changing the Phase 2 operating point.
- [ ] Define the preference question, tie/abstain handling, and reviewer
  instructions.
- [ ] Define a separate correctness rubric, reviewer count, adjudication, and
  missing-label behavior.
- [ ] Set token, cost, request, time, and human-review budgets.
- [ ] Set a minimum sample, success criterion, and stopping rule before
  execution.
- [ ] Define provider failure, timeout, refusal, and nondeterminism handling.
- [ ] Obtain explicit approval for the model pair and budget.

### 7. Implement the opt-in dual-model runner only after approval

Reuse existing provider interfaces and measurement boundaries. Keep this
runner separate from `app.py`'s default request path.

- [ ] Require an explicit opt-in flag or command invocation.
- [ ] Reject execution when the experiment definition is missing, disabled,
  malformed, or over budget.
- [ ] Load only the declared sample and record exclusions.
- [ ] Generate bounded outputs through the existing provider abstraction.
- [ ] Record model-specific status, latency, token, cost, timeout, retry, and
  failure fields where available.
- [ ] Never write unrestricted prompts or answers to the result artifact.
- [ ] Stop when the declared budget, sample, or stopping rule is reached.
- [ ] Make reruns identify their experiment configuration and sample.
- [ ] Ensure the default test suite and default application behavior do not
  make provider requests.

The runner is not authorized to add a second fallback model to the serving
path. Any serving change requires a separate product and safety decision.

### 8. Review and package dual-model results

Produce an auditable result even when the run is unavailable or incomplete.

- [ ] Validate preference and correctness fields independently.
- [ ] Report denominators, ties, abstentions, disagreements, and missing
  reviews explicitly.
- [ ] Keep provider measurement fields separate from evaluation judgments.
- [ ] Record whether correctness was reviewed, unavailable, or out of scope.
- [ ] Record budget usage and the exact stop reason.
- [ ] Apply serialization and redaction validation before writing the result.
- [ ] Add an unavailable artifact path when credentials or approved provider
  access are absent; do not substitute synthetic values silently.

### 9. Add regression tests and documentation handoff

- [ ] Test dashboard input loading and metadata alignment.
- [ ] Test exact source-value fidelity for every dashboard section.
- [ ] Test unavailable optional artifacts and malformed required artifacts.
- [ ] Test no metric recomputation by mutating source values and checking the
  rendered values.
- [ ] Test redaction, HTML escaping, bounds, and accessibility markers.
- [ ] Test CLI exit codes and deterministic regeneration behavior.
- [ ] Test dual-model config validation, disabled-by-default behavior, budget
  enforcement, stop conditions, and result separation.
- [ ] Run the full test suite after substantive code changes.
- [ ] Update `PHASE_2_IMPLEMENTATION_PLAN.md` only for verified WS9 scope.
- [ ] Update `docs/phase-2/README.md`, limitations, and transition documents.
- [ ] Link WS9 evidence and artifacts from the parent plan.

## Verification commands

Run from the repository root. Confirm the paths, options, and environment
before recording any result.

### Baseline inputs

```powershell
python -m pytest -q
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
python -m sscre.failure_gallery_export `
  --comparison artifacts/evaluation/workstream5-held-out-comparison.json `
  --freshness-companion artifacts/evaluation/workstream6-held-out-freshness.json `
  --output artifacts/evaluation/workstream7-quality-analysis.json
```

### Planned dashboard verification

These commands become executable after the WS9 module, CLI, and tests exist.
Record the exact command and result in `WORKSTREAM_9_EVIDENCE.md`; do not
claim them as current verification from this planning document.

```powershell
python -m sscre.dashboard --help
python -m sscre.dashboard `
  --comparison artifacts/evaluation/workstream5-held-out-comparison.json `
  --pareto artifacts/evaluation/workstream5-held-out-pareto.json `
  --freshness-development artifacts/evaluation/workstream6-development-freshness.json `
  --freshness-held-out artifacts/evaluation/workstream6-held-out-freshness.json `
  --invalidation artifacts/evaluation/workstream6-invalidation.json `
  --quality artifacts/evaluation/workstream7-quality-analysis.json `
  --operations artifacts/operations/workstream8-operational-verification.json `
  --json-output artifacts/evaluation/workstream9-dashboard.json `
  --html-output artifacts/evaluation/workstream9-dashboard.html
python -m pytest -q tests/test_workstream9_dashboard.py
```

### Planned dual-model verification

These commands become executable only after the experiment schema and opt-in
runner are approved and implemented:

```powershell
python -m sscre.dual_model --help
python -m sscre.dual_model `
  --config experiments/workstream9_dual_model_v1.json `
  --output artifacts/evaluation/workstream9-dual-model-v1.json
python -m pytest -q tests/test_workstream9_dual_model.py
```

The default test suite must run with the dual-model path disabled and without
provider credentials. Any real-provider run must record its environment,
provider/model identifiers, budget, and unavailable fields without recording
secrets.

## Acceptance criteria

### Dashboard

- [ ] The dashboard reads WS5–WS8 artifacts through a validated input boundary.
- [ ] Dashboard values match source artifact values for all implemented views.
- [ ] The dashboard does not recompute metrics, confidence intervals, Pareto
  points, freshness exposure, or failure-category rates.
- [ ] Dataset, split, manifest, schema, environment, timestamp, and source
  references are visible or machine-readable.
- [ ] Missing, malformed, sparse, and unavailable inputs are explicit and
  never converted to zero or success.
- [ ] Operating point, baseline, interval, Pareto, failure, freshness,
  storage/eviction, and limitations views are present or individually marked
  unavailable.
- [ ] Synthetic, simulated, and real-provider measurements are visibly
  separated.
- [ ] Dashboard artifacts contain no credentials, unrestricted prompts,
  unrestricted answers, or forbidden raw-content fields.
- [ ] Static output is bounded, escaped, and minimally keyboard/screen-reader
  usable.
- [ ] Regeneration and focused test commands are documented in evidence.

### Dual-model experiment

- [ ] A written hypothesis, model pair, prompt/configuration, sample, review
  process, budget, success criterion, and stopping rule exists before
  execution.
- [ ] Dual-model execution is explicitly opt-in and absent from the default
  MVP path.
- [ ] Results preserve model-specific provider measurements and failures.
- [ ] Preference and correctness are separate fields with separate
  denominators and unavailable states.
- [ ] No preference result is described as factual correctness without
  correctness-review evidence.
- [ ] Budget exhaustion, provider unavailability, review shortfall, ties, and
  abstentions are explicit.
- [ ] No result is presented as a production quality, cost, latency, or
  capacity guarantee.

### Handoff

- [ ] `WORKSTREAM_9_EVIDENCE.md` records implementation identity, source
  artifacts, schemas, commands, results, limitations, and skipped gates.
- [ ] The parent Phase 2 plan links the WS9 plan and verified evidence.
- [ ] Phase 3 transition and evaluation limitations distinguish a dashboard
  view from a new analytics system and distinguish dual-model preference from
  correctness.
- [ ] README/index links and artifact paths are current.

## Completion evidence

Record in `WORKSTREAM_9_EVIDENCE.md`:

- [ ] implementation commit, branch, Python version, and dirty-state status;
- [ ] dashboard schema and source-artifact manifest;
- [ ] dataset, split, manifest, schema, and measurement-environment metadata;
- [ ] dashboard JSON and HTML paths plus regeneration commands;
- [ ] source-value fidelity and redaction test results;
- [ ] accessibility and bounded-output verification;
- [ ] unavailable or skipped input sections and reasons;
- [ ] dual-model experiment definition and approval record, if approved;
- [ ] dual-model result or explicit unavailable/deferred record;
- [ ] preference and correctness review counts separately;
- [ ] budget usage, stop reason, and provider limitation metadata;
- [ ] focused and full-suite test results;
- [ ] parent-plan, README, and transition-document handoff;
- [ ] unsupported claims and limitations.

## Handoff to later work

**Workstreams 5–8** — WS9 consumes their artifacts and does not change their
evaluation, freshness, gallery, or operational results.

**Phase 3 / Phase 4** — the dashboard does not establish 1K–100K Q/day,
cloud, multi-region, managed-PostgreSQL, live-provider, or SLA claims.
Dual-model results do not authorize a production fallback or model-routing
change.

Handoff requirements:

- [ ] Publish the dashboard schema, source manifest, and output paths.
- [ ] State which upstream artifacts were available and which were unavailable.
- [ ] State that displayed metrics were copied from upstream artifacts.
- [ ] State the measurement environment and limitations beside each section.
- [ ] Publish the dual-model experiment definition or its explicit deferral.
- [ ] State whether correctness labels were available; never infer them from
  preference.
- [ ] Link verified evidence from `PHASE_2_IMPLEMENTATION_PLAN.md`.

## Execution sequence

1. [x] Define WS9 scope, gates, artifact inputs, and frozen semantics.
2. [x] Audit all WS5–WS8 inputs and freeze the dashboard protocol.
   Evidence: [`WORKSTREAM_9_STEP1_AUDIT.md`](./WORKSTREAM_9_STEP1_AUDIT.md).
3. [x] Freeze dashboard and dual-model schemas.
   Evidence: Step 1 audit § Frozen dashboard input protocol and § Frozen
   dual-model experiment schema boundary.
4. [x] Implement bounded artifact loading and metadata validation.
   Module: `src/sscre/dashboard.py`; tests:
   `tests/test_workstream9_dashboard.py`.
5. [x] Generate dashboard JSON and static HTML.
   Artifacts: `artifacts/evaluation/workstream9-dashboard.json` and
   `artifacts/evaluation/workstream9-dashboard.html`.
6. [x] Add summary, baseline, interval, Pareto, failure, freshness,
   operations, provider, and limitations views.
   Evidence: `src/sscre/dashboard.py` and regenerated WS9 JSON/HTML artifacts.
7. [ ] Add redaction, bounds, accessibility, and source-fidelity tests.
8. [ ] Draft and approve the dual-model experiment definition.
9. [ ] Implement and run the opt-in dual-model experiment, or record deferral.
10. [ ] Package dual-model results or an unavailable artifact.
11. [ ] Run focused tests and the full suite.
12. [ ] Update evidence, parent status, README, limitations, and transitions.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Dashboard becomes a second metrics pipeline | Load and copy validated source fields; do not replay or aggregate upstream samples. |
| Stale or incompatible artifacts are combined | Validate dataset, split, manifest, schema, and source timestamps; fail closed or show a diagnostic mismatch. |
| Missing evidence is rendered as zero | Use explicit unavailable blocks with reasons and denominators. |
| Synthetic results look like live-provider results | Preserve measurement environment in every section and display limitations prominently. |
| HTML exposes raw prompts or answers | Reuse serialization/redaction validation, escape output, and test forbidden keys. |
| Large artifacts make the dashboard unwieldy | Use bounded summaries and source references; do not embed unrestricted rows. |
| Accessibility depends on color or charts | Provide text summaries, headings, table headers, labels, and keyboard navigation. |
| Preference is mistaken for correctness | Require separate fields, reviewers, denominators, and correctness-unavailable states. |
| Dual-model work changes the default serving path | Keep it in a separate opt-in command and prohibit `app.py` fallback changes in WS9. |
| Provider cost or latency exceeds the experiment budget | Predeclare hard request/token/time limits and stop before executing beyond them. |
| Model nondeterminism makes results irreproducible | Record model/configuration versions, seeds where supported, sample IDs, and repeat policy. |
| Dashboard scope expands into product analytics | Defer APIs, databases, accounts, live refresh, and telemetry to a separate requirement. |
| User approval is implied by plan creation | Keep implementation and dual-model approval checkboxes separate and unchecked. |
