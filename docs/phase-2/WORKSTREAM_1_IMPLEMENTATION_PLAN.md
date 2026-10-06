# Phase 2 Workstream 1 Implementation Plan

## Goal

### Goal

Make the Phase 2 decision, label, and trace contracts explicit, bounded, and
consistent across the safety engine, API responses, benchmark artifacts,
evaluation reports, and tests.

The project already has the main decision and candidate-trace types in
`src/sscre/safety.py`. This workstream should consolidate and verify that
contract rather than introduce a second decision model.

```text
request
    ↓
retrieve candidates and compatibility evidence
    ↓
evaluate candidate-level decision and reason
    ↓
aggregate SAFE / UNSAFE / UNCERTAIN result
    ↓
serve only SAFE; generate for UNSAFE or UNCERTAIN
    ↓
record independent compatibility, correctness, and preference evidence
```

## Scope

### Included

- `SAFE`, `UNSAFE`, and `UNCERTAIN` decision semantics
- compatibility, correctness, and preference label separation
- candidate-level decision trace fields
- bounded and non-sensitive trace serialization
- contract validation and regression tests
- documentation of failure-closed behavior

### Excluded

- Adding new compatibility rules
- Cross-encoder validation
- Human annotation collection
- Real-provider integration
- Dashboard implementation
- Threshold tuning

Those activities consume the contracts produced here.

## Learning objectives

- [ ] Explain why semantic similarity is retrieval evidence rather than a
  reuse decision.
- [ ] Distinguish compatibility from factual correctness and preference.
- [ ] Design a trace that is useful for analysis without exposing sensitive
  request or response data.
- [ ] Verify conservative behavior when evidence or dependencies are missing.

## Implementation steps

### 1. Audit the existing contracts


- [x] `SafetyDecision` defines the three decision values in
  `src/sscre/safety.py`.
- [x] `CandidateTrace` represents an individual candidate evaluation.
- [x] `SafetyResult` represents the aggregate cache-reuse decision.
- [x] `resolve_candidate_traces()` gives `SAFE` precedence only when a safe
  candidate exists.
- [x] `evaluate_candidate()` returns conservative compatibility decisions.
- [x] `QueryMetadata` contains bounded intent, domain, entity, constraint,
  temporal, and output-format signals.
- [x] The contract is documented as a versioned evaluation artifact
  (`SAFETY_EVALUATION_CONTRACT_v1.md`, `SAFETY_EVALUATION_CONTRACT_VERSION`
  in `safety.py`).
- [ ] All externally emitted traces expose the required fields consistently
  (see [WORKSTREAM_1_STEP1_AUDIT.md](./WORKSTREAM_1_STEP1_AUDIT.md) gap table).
- [ ] Contract tests cover serialization, bounds, precedence, and failure
  closure (precedence/compatibility covered; serialization/bounds partial — same
  audit doc).

Evidence locations:

- `src/sscre/safety.py`
- `src/sscre/compatibility.py`
- `src/sscre/metadata.py`
- `src/sscre/app.py`
- `tests/test_safety.py`
- `tests/test_compatibility.py`

Step 1 audit record (producers, consumers, gaps, test matrix):

- [SAFETY_EVALUATION_CONTRACT_v1.md](./SAFETY_EVALUATION_CONTRACT_v1.md)
- [WORKSTREAM_1_STEP1_AUDIT.md](./WORKSTREAM_1_STEP1_AUDIT.md)

Recorded gaps to address in later steps:

- ~~`app.py` selects the first `SAFE` candidate inline~~ (step 2: uses
  `resolve_candidate_traces()` for Strategy C semantic aggregation and generated
  fallback decisions).
- ~~Strategy A uses `EXACT_HIT` in the API~~ (step 2: Strategy A exact hits use
  `SAFE` / `exact_query_hash_match`).
- Strategy B paths still use retrieval-only traces and implicit `SAFE` at the
  similarity threshold (experiment baseline; not the Strategy C contract path).
- `QueryResponse` does not expose `candidate_traces`; traces are log-only.
- Benchmark artifacts record aggregate decisions, not full trace tuples.

### 2. Define the safety decision contract

#### Canonical values

```text
SAFE       → serve the selected cached answer
UNSAFE     → do not serve; generate a new answer
UNCERTAIN  → do not serve; generate a new answer
```

#### Semantics

`SAFE` means that the active compatibility and freshness policy found enough
evidence to treat the selected candidate as reusable.

`UNSAFE` means that a known incompatibility exists. Examples include a
constraint mismatch, entity mismatch, dynamic query, or dynamic candidate.

`UNCERTAIN` means that reuse cannot be established safely. Examples include
missing metadata, incomplete constraint evidence, missing entity evidence,
unknown intent/domain/format evidence, dependency failure, or an ambiguous
borderline result.

#### Required invariants

- [x] Only `SAFE` can select a candidate query hash (`SafetyResult.__post_init__`,
  `cached_response` / `semantic_cached_response` guards).
- [x] Only `SAFE` can expose a reusable cache-hit source (`is_reusable_decision`
  at cache response boundaries).
- [x] `UNSAFE` always falls back to generation or a controlled error (`app.py`
  generated path preserves `UNSAFE`).
- [x] `UNCERTAIN` always falls back to generation or a controlled error.
- [x] Empty candidates resolve to a non-`SAFE` result (`resolve_candidate_traces`).
- [x] Dependency failure cannot be converted into `SAFE` (existing 503/502 paths;
  no change in step 2).
- [x] Expired candidates cannot be converted into `SAFE` (`cache_entry_is_reusable`;
  no change in step 2).
- [x] Dynamic queries cannot be served from the cache (`evaluate_candidate`;
  no change in step 2).

#### Implementation tasks

- [x] Keep `SafetyDecision` as the single source of truth for decision values.
- [x] Audit string comparisons and response mappings; removed `EXACT_HIT` from
  `QueryResponse`.
- [x] Added `is_reusable_decision()` shared helper (`safety.py`).
- [x] API and generated decision logs preserve `UNSAFE` vs `UNCERTAIN` via
  `resolve_candidate_traces()` on `decision_traces`.
- [x] Document the contract on `QueryResponse` (`query.py`).

- [x] Producers/consumers use canonical values (`app.py`, `baseline.py`).
- [x] Strategy C semantic and generated paths use `resolve_candidate_traces()`.
- [x] Remaining gap: Strategy B retrieval-only path (documented above).

**Verification (2026-10-06):** `python -m pytest -q` → 184 passed, 13 skipped.

### 3. Define independent evaluation labels

#### Label definitions

| Label | Type | Question |
|---|---|---|
| Compatibility | decision/evaluation | Can the cached answer answer the new query under the policy? |
| Correctness | human or evaluator label | Is the answer factually and instructionally acceptable? |
| Preference | comparison label | Which of two acceptable answers is preferred? |

#### Required separation

- Compatibility is not correctness.
- Correctness is not preference.
- Preference is not required for a single answer.
- Similarity is not a label.
- A `SAFE` decision does not prove that the cached answer is factually
  correct.
- A preferred answer is not automatically more factually correct.

#### Canonical record shape

Define one documented record shape for evaluation artifacts. The exact storage
format may remain JSONL, but the fields must have stable names and meanings:

```json
{
  "compatibility": {
    "expected_decision": "SAFE",
    "observed_decision": "SAFE"
  },
  "correctness": {
    "cached_answer": null,
    "generated_answer": null
  },
  "preference": {
    "winner": null,
    "applicable": false
  }
}
```

`null` means “not collected or not applicable”; it must not be silently
converted to a negative label.

#### Implementation tasks

- [x] Document the label schema under `benchmarks/` or the evaluation
  contract documentation (`benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`).
- [x] Use separate fields for expected compatibility and observed decision
  (`evaluation_labels.build_evaluation_labels`, failure example payloads).
- [x] Reject records that place preference in the correctness field
  (`benchmark.BenchmarkRecord` validator).
- [x] Define allowed values and nullability for every label (contract doc +
  `evaluation_labels.py` models).
- [x] Record annotation source and adjudication status independently from the
  label value (optional benchmark fields + `AnnotationProvenance`).
- [x] Ensure reports calculate compatibility, correctness, and preference
  metrics in separate sections (`CompatibilityCacheReport.label_sections`).
- [x] Add tests proving that missing correctness does not imply incorrectness
  (`tests/test_evaluation_labels.py`).

### 4. Define the candidate-level trace contract

#### Required fields

Each retrieved candidate trace must contain bounded values for:

- candidate identifier or query hash
- retrieval rank
- similarity score
- candidate decision
- decision reason
- evaluation stage
- query metadata summary
- candidate metadata summary
- freshness class and expiry outcome, when freshness is evaluated
- validator/rule outcomes, when available

The current `CandidateTrace` fields are the minimum base contract. Freshness
and rule evidence may be represented in bounded metadata until a dedicated
typed field is justified.

#### Aggregate result fields

The final `SafetyResult` must contain:

- final decision
- strategy identifier
- final reason
- selected candidate only for `SAFE`
- selected similarity only for `SAFE`
- bounded candidate traces

#### Trace rules

- [x] Candidate order is deterministic (similarity-ranked search + fixed cap order).
- [x] Similarity is bounded to `[-1.0, 1.0]` (`CandidateTrace.__post_init__`).
- [x] Candidate count is capped (`MAX_CANDIDATE_TRACES`, `cap_candidate_traces`,
  `serialize_candidate_traces`).
- [x] Reason strings use documented taxonomy (`validate_trace_reason`).
- [x] Metadata is bounded before serialization (`bound_trace_metadata`).
- [x] Raw prompts and full answers are not emitted in operational logs
  (hash + bounded metadata only).
- [x] Credentials and secrets are not trace fields (by schema design).
- [x] Trace serialization is stable (`to_log_dict` sorted keys).

Contract doc: [CANDIDATE_TRACE_CONTRACT_v1.md](./CANDIDATE_TRACE_CONTRACT_v1.md).

#### Reason taxonomy

Document the current reasons and their semantics, including:

- `similarity_below_threshold`
- `dynamic_query_not_reusable`
- `candidate_metadata_missing`
- `candidate_is_dynamic`
- `constraint_mismatch:<key>`
- `incomplete_constraint_evidence`
- `entity_mismatch`
- `incomplete_entity_evidence`
- `intent_mismatch`
- `domain_mismatch`
- `format_mismatch`
- `missing_<field>_evidence`
- `temporal_class_mismatch`
- `compatible_metadata`

Add a new reason only when it improves failure analysis. Avoid using a generic
reason where the evaluator needs to identify the failed safety condition.

**Verification (2026-10-06):** `python -m pytest -q` → 194 passed, 13 skipped.

### 5. Standardize serialization and API boundaries

#### Implementation tasks

- [ ] Identify every API, metric, persistence, and evaluation path that
  serializes `SafetyResult` or `CandidateTrace`.
- [ ] Define one JSON-compatible representation for decisions and traces.
- [ ] Preserve `null` for optional fields instead of omitting meaning.
- [ ] Cap trace count and serialized metadata size at the boundary.
- [ ] Ensure response serialization cannot expose internal exceptions or
  provider credentials.
- [ ] Keep compatibility traces usable when the request ultimately generates
  a new answer.
- [ ] Version the contract if a breaking field or semantic change is needed.

Likely integration points:

- `src/sscre/app.py`
- `src/sscre/query.py`
- `src/sscre/metrics.py`
- `src/sscre/evaluate.py`
- `src/sscre/baseline.py`
- benchmark/report serializers

### 6. Add contract and regression tests

#### Unit tests

- [ ] Validate all three decision values.
- [ ] Reject invalid decision values.
- [ ] Validate `SAFE` requires a selected candidate and similarity.
- [ ] Validate non-`SAFE` results cannot select a candidate.
- [ ] Validate empty traces resolve conservatively.
- [ ] Validate `SAFE` precedence when a later candidate is safe.
- [ ] Validate `UNCERTAIN` precedence over all-`UNSAFE` candidates.
- [ ] Validate similarity, rank, reason, and metadata bounds.
- [ ] Validate deterministic serialization.

#### Compatibility tests

- [ ] Known constraint mismatch returns `UNSAFE`.
- [ ] Missing constraint evidence returns `UNCERTAIN`.
- [ ] Dynamic query returns `UNSAFE`.
- [ ] Dynamic candidate returns `UNSAFE`.
- [ ] Missing metadata returns `UNCERTAIN`.
- [ ] Entity mismatch returns `UNSAFE`.
- [ ] Missing entity evidence returns `UNCERTAIN`.
- [ ] Unknown intent, domain, or format remains conservative.
- [ ] Matching metadata returns `SAFE`.

#### Integration tests

- [ ] `SAFE` serves the selected cache entry.
- [ ] `UNSAFE` generates and does not serve the candidate.
- [ ] `UNCERTAIN` generates and does not serve the candidate.
- [ ] Repository failure cannot produce a cache hit.
- [ ] Expiry failure cannot produce a cache hit.
- [ ] API output preserves the final decision and fallback reason.
- [ ] Trace output is bounded and contains no secrets.

### 7. Record evidence and hand off the contracts

- [ ] Run targeted safety and compatibility tests.
- [ ] Run the full test suite when the environment permits.
- [ ] Inspect linter diagnostics for changed Python files.
- [ ] Record test commands, result counts, and skipped dependencies.
- [ ] Update this plan only with evidence-backed completion marks.
- [ ] Make the frozen contract available to benchmark, provider, and
  evaluation workstreams.

## Verification checklist

- [ ] `SAFE`, `UNSAFE`, and `UNCERTAIN` have documented semantics.
- [ ] Only `SAFE` can select and serve a cache candidate.
- [ ] `UNSAFE` and `UNCERTAIN` remain distinguishable in traces and reports.
- [ ] Missing metadata and dependency failures cannot produce a cache hit.
- [ ] Compatibility, correctness, and preference are independent fields.
- [ ] Candidate traces explain the decision and reason for every evaluated
  candidate.
- [ ] Trace count, metadata, reason, and similarity values are bounded.
- [ ] Operational traces do not contain credentials, authorization headers,
  unrestricted prompts, or full answers.
- [ ] Serialization is deterministic and compatible with report tooling.
- [ ] Targeted tests pass:

```bash
python -m pytest -q tests/test_safety.py tests/test_compatibility.py
```

- [ ] Full suite passes:

```bash
python -m pytest -q
```

## Completion criteria

Workstream 1 is complete when SSCRE has one documented and tested contract for
decisions, labels, and candidate traces. `SAFE` is the only reusable outcome;
`UNSAFE` and `UNCERTAIN` both fall back safely while remaining distinguishable
for analysis. Compatibility, factual correctness, and preference are reported
independently, and bounded traces explain the evidence behind each candidate
decision without exposing sensitive data.

## Execution sequence

1. [x] Audit current decision, label, and trace producers and consumers
   ([WORKSTREAM_1_STEP1_AUDIT.md](./WORKSTREAM_1_STEP1_AUDIT.md)).
2. [x] Freeze the canonical decision and reason contracts (step 2 code + contract
   doc update).
3. [x] Define the independent evaluation-label schema.
4. [x] Define the candidate-level trace contract (step 4 — trace doc, validation,
   serialization helpers, app log integration).
5. [ ] Add unit and integration contract tests.
6. [ ] Run the existing full suite and targeted contract tests.
7. [ ] Record evidence and mark only verified checklist items complete.
8. [ ] Hand the frozen contracts to Workstreams 2–9.

## Acceptance criteria

- [ ] One canonical decision vocabulary is used throughout the codebase.
- [ ] `SAFE` is the only decision that can serve a cache candidate.
- [ ] `UNSAFE` and `UNCERTAIN` are distinguishable in traces and reports.
- [ ] Compatibility, correctness, and preference are independent fields.
- [ ] Candidate traces explain why each candidate was accepted or rejected.
- [ ] Trace output is bounded, deterministic, and non-sensitive.
- [ ] Contract tests pass with:

```bash
python -m pytest -q tests/test_safety.py tests/test_compatibility.py
```

- [ ] Full verification passes with:

```bash
python -m pytest -q
```

- [ ] The implementation evidence is recorded in the Phase 2 experiment
  report.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `UNSAFE` and `UNCERTAIN` are collapsed | Preserve both values in API, traces, and reports. |
| Preference is treated as correctness | Require separate fields and analyses. |
| Traces leak prompts or answers | Serialize bounded metadata and approved identifiers only. |
| A dependency failure creates a false hit | Test failure-closed behavior at every boundary. |
| Reason strings drift across modules | Maintain a documented reason taxonomy. |
| Contract changes break report tooling | Version breaking changes and test serialization. |
