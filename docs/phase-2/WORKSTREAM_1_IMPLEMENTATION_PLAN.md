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
- [ ] All externally emitted traces expose the required fields consistently.
  Strategy C does. Strategy B still records only the first retrieval trace
  ([WORKSTREAM_1_STEP1_AUDIT.md](./WORKSTREAM_1_STEP1_AUDIT.md)).
- [x] Contract tests cover serialization, bounds, precedence, and failure
  closure (`tests/test_workstream1_contract.py`, `tests/test_trace_contract.py`,
  `tests/test_serialization_boundary.py`, `tests/test_safety.py`).

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
  similarity threshold (opt-in experiment baseline; default strategy is `C`).
- ~~`QueryResponse` does not expose `candidate_traces`~~ (step 5: API returns
  bounded `candidate_traces`, null when none were collected).
- ~~Benchmark artifacts record aggregate decisions only~~ (compatibility
  baseline failure examples include per-candidate traces).

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
unknown intent/domain/format evidence, or dependency failure. Similarity
below the threshold is `UNSAFE`, not a separate borderline band.

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

- [x] Identify every API, metric, persistence, and evaluation path that
  serializes `SafetyResult` or `CandidateTrace`
  (`sscre.serialization.SERIALIZATION_EMITTERS` + boundary doc).
- [x] Define one JSON-compatible representation for decisions and traces
  (`boundary_candidate_traces`, `serialize_safety_result_for_boundary`,
  `QueryResponse.candidate_traces`).
- [x] Preserve `null` for optional fields instead of omitting meaning
  (empty traces → `null` in API and logs).
- [x] Cap trace count and serialized metadata size at the boundary
  (existing caps + `MAX_BOUNDARY_TRACE_JSON_BYTES`).
- [x] Ensure response serialization cannot expose internal exceptions or
  provider credentials (`build_cache_decision_log` forbidden-key guard).
- [x] Keep compatibility traces usable when the request ultimately generates
  a new answer (`candidate_traces` on generated `QueryResponse`).
- [x] Version the contract if a breaking field or semantic change is needed
  (`BOUNDARY_SERIALIZATION_VERSION`, report `schema_version`).

Doc: [SERIALIZATION_BOUNDARY_v1.md](./SERIALIZATION_BOUNDARY_v1.md).

**Verification (2026-10-06):** `python -m pytest -q` → 199 passed, 13 skipped.

Likely integration points:

- `src/sscre/app.py`
- `src/sscre/query.py`
- `src/sscre/metrics.py`
- `src/sscre/evaluate.py`
- `src/sscre/baseline.py`
- benchmark/report serializers

### 6. Add contract and regression tests

#### Unit tests

- [x] Validate all three decision values (`tests/test_workstream1_contract.py`,
  `tests/test_safety.py`).
- [x] Reject invalid decision values (`test_query_response_rejects_invalid_decision`,
  `test_safety_result_rejects_invalid_decision`,
  `test_candidate_trace_rejects_invalid_decision`).
- [x] Validate `SAFE` requires a selected candidate and similarity
  (`test_safe_result_requires_selected_candidate_and_similarity`).
- [x] Validate non-`SAFE` results cannot select a candidate or carry a similarity
  (`test_non_safe_result_cannot_select_candidate`,
  `test_non_safe_result_cannot_include_similarity`). `SafetyResult.__post_init__`
  enforces both.
- [x] Validate empty traces resolve conservatively
  (`test_empty_candidates_fail_closed_without_selection`).
- [x] Validate `SAFE` precedence when a later candidate is safe
  (`test_first_safe_candidate_wins_in_retrieval_order`).
- [x] Validate `UNCERTAIN` precedence over all-`UNSAFE` candidates
  (`test_uncertain_takes_precedence_over_all_unsafe_candidates`).
- [x] Validate similarity, rank, reason, and metadata bounds
  (`tests/test_trace_contract.py`, `tests/test_safety.py` metadata caps,
  `test_boundary_rejects_oversized_trace_payload`).
- [x] Validate deterministic serialization
  (`test_safety_result_boundary_serialization` compares two sorted dumps).

#### Compatibility tests

- [x] Known constraint mismatch returns `UNSAFE`
  (`test_explicit_incompatibility_is_unsafe` / constraint case).
- [x] Missing constraint evidence returns `UNCERTAIN`
  (`test_incomplete_constraint_evidence_is_uncertain`).
- [x] Dynamic query returns `UNSAFE` (`test_dynamic_query_is_not_reusable`).
- [x] Dynamic candidate returns `UNSAFE` (`test_dynamic_candidate_is_unsafe`).
- [x] Missing metadata returns `UNCERTAIN`
  (`test_missing_candidate_metadata_is_uncertain`,
  `test_missing_metadata_is_uncertain_instead_of_safe`).
- [x] Entity mismatch returns `UNSAFE` (parametrized incompatibility / entity).
- [x] Missing entity evidence returns `UNCERTAIN`
  (`test_incomplete_entity_evidence_is_uncertain`).
- [x] Unknown intent, domain, or format remains conservative
  (mismatch → `UNSAFE` in `test_explicit_incompatibility_is_unsafe`;
  missing evidence → `UNCERTAIN` in `test_missing_field_evidence_is_uncertain`).
- [x] Matching metadata returns `SAFE` (`test_compatible_candidate_is_safe`).

#### Integration tests

- [x] `SAFE` serves the selected cache entry (`tests/test_exact_cache.py` strategy C
  reuse paths).
- [x] `UNSAFE` generates and does not serve the candidate
  (`test_strategy_c_generates_for_an_incompatible_semantic_candidate`:
  decision `UNSAFE`, reason `all candidates were incompatible`, trace
  `constraint_mismatch:language`, cached answer not returned).
- [x] `UNCERTAIN` generates and does not serve the candidate
  (`test_strategy_c_does_not_reuse_exact_entry_without_metadata`: reason
  `no candidate had sufficient compatibility evidence`, trace
  `candidate_metadata_missing`).
- [x] Dynamic exact entries are skipped by cache control before compatibility
  (`test_strategy_c_does_not_reuse_dynamic_exact_entry`: decision `UNCERTAIN`,
  reason `dynamic_entries_disabled`, `candidate_traces` null). Dynamic query
  and dynamic candidate remain `UNSAFE` in `tests/test_compatibility.py`.
- [x] Repository failure cannot produce a cache hit
  (`test_cache_repository_failure_returns_503_with_request_id`,
  `test_repository_timeout_fails_closed_with_503`).
- [x] Expiry failure cannot produce a cache hit
  (`test_expired_exact_entry_is_not_reused`: decision `UNCERTAIN`, reason
  `expired`, traces null, expired answer not returned, and the new stable
  answer is stored).
- [x] API output preserves the final decision and fallback reason
  (assertions above + `test_query_cache_decision_log_includes_schema_version`).
- [x] Trace output is bounded and contains no secrets
  (`test_safe_exact_hit_trace_is_bounded_without_secrets`,
  `test_strategy_c_logs_bounded_candidate_decision_trace` omit
  `sk-test-SECRETVALUE` and the cached answer;
  `test_trace_objects_reject_answer_field`).

**Verification (2026-10-06):**

```bash
python -m pytest -q tests/test_safety.py tests/test_compatibility.py tests/test_trace_contract.py tests/test_serialization_boundary.py tests/test_workstream1_contract.py tests/test_exact_cache.py tests/test_cache_ttl_integration.py
```

→ 79 passed.

```bash
python -m pytest -q
```

→ 218 passed, 13 skipped on that step 6 run. Superseded by the later full-suite
re-run below (230 passed, 13 skipped). Skips are
`tests/test_postgres_integration.py` because `SSCRE_DATABASE_URL` is unset.

### 7. Record evidence and hand off the contracts

- [x] Run targeted safety and compatibility tests (2026-10-06, 79 passed on
  the step 6 files listed above, including `tests/test_safety.py` and
  `tests/test_compatibility.py`).
- [x] Run the full test suite when the environment permits
  (`python -m pytest -q` → 230 passed, 13 skipped on the 2026-10-06
  contract-alignment re-run).
- [x] Inspect linter diagnostics for changed Python files (none).
- [x] Record test commands, result counts, and skipped dependencies
  ([WORKSTREAM_1_EVIDENCE.md](./WORKSTREAM_1_EVIDENCE.md)).
- [x] Update this plan only with evidence-backed completion marks.
  Strategy B trace coverage stays open below.
- [x] Make the frozen contract available to benchmark, provider, and
  evaluation workstreams
  ([WORKSTREAM_1_EVIDENCE.md](./WORKSTREAM_1_EVIDENCE.md), linked from
  [PHASE_2_IMPLEMENTATION_PLAN.md](./PHASE_2_IMPLEMENTATION_PLAN.md)).

## Verification checklist

- [x] `SAFE`, `UNSAFE`, and `UNCERTAIN` have documented semantics.
- [x] Only `SAFE` can select and serve a cache candidate.
- [x] `UNSAFE` and `UNCERTAIN` remain distinguishable in traces and reports
  (`test_compatibility_report_keeps_unsafe_and_uncertain_distinct`).
- [x] Missing metadata and dependency failures cannot produce a cache hit.
- [x] Compatibility, correctness, and preference are independent fields.
- [x] Strategy C candidate traces explain the decision and reason for each
  evaluated candidate (step 6 API tests and the compatibility report test).
- [ ] Strategy B records a trace for every retrieved candidate. It records the
  first candidate only (`similarity_threshold_met`).
- [x] Trace count, metadata, reason, and similarity values are bounded.
- [x] Operational traces do not contain credentials, authorization headers,
  unrestricted prompts, or full answers (decision logs reject `answer`,
  `authorization`, and `api_key`; generation-failure and Strategy C traces
  omit query text and the cached answer).
- [x] Serialization is deterministic and saved reports use
  `BOUNDARY_SERIALIZATION_VERSION`
  (`test_saved_report_uses_boundary_schema_version`).
- [x] Targeted tests pass (2026-10-06, included in the 79-passed step 6 run):

```bash
python -m pytest -q tests/test_safety.py tests/test_compatibility.py
```

- [x] Full suite passes (2026-10-06 contract-alignment re-run: 230 passed,
  13 skipped):

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
5. [x] Standardize trace serialization and API boundaries (step 5).
6. [x] Add unit and integration contract tests (step 6 — `tests/test_workstream1_contract.py`
   plus extensions in compatibility, trace, exact-cache tests).
7. [x] Run the existing full suite and targeted contract tests (2026-10-06:
   79 passed targeted on the step 6 file set; later full suite 230 passed /
   13 skipped).
8. [x] Record evidence and mark only verified checklist items complete.
9. [x] Hand the frozen contracts to Workstreams 2–9
   ([WORKSTREAM_1_EVIDENCE.md](./WORKSTREAM_1_EVIDENCE.md)).

## Acceptance criteria

- [ ] One canonical decision vocabulary is used throughout the codebase.
  Strategy B still serves from similarity alone (`similarity_threshold_met`);
  see the step 1 gap. Strategy C uses `SAFE` / `UNSAFE` / `UNCERTAIN`.
- [x] `SAFE` is the only decision that can serve a cache candidate.
- [x] `UNSAFE` and `UNCERTAIN` are distinguishable in traces and reports
  (`test_compatibility_report_keeps_unsafe_and_uncertain_distinct`).
- [x] Compatibility, correctness, and preference are independent fields.
- [x] Strategy C candidate traces explain why each evaluated candidate was
  accepted or rejected. Strategy B still records only the first candidate.
- [x] Trace output is bounded, deterministic, and non-sensitive.
- [x] Contract tests pass (2026-10-06, included in the 79-passed step 6 run):

```bash
python -m pytest -q tests/test_safety.py tests/test_compatibility.py
```

- [x] Full verification passes (2026-10-06 contract-alignment re-run:
  230 passed, 13 skipped):

```bash
python -m pytest -q
```

- [x] The implementation evidence is recorded in
  [WORKSTREAM_1_EVIDENCE.md](./WORKSTREAM_1_EVIDENCE.md). Workstream 1 is a
  contract freeze, not a provider experiment.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| `UNSAFE` and `UNCERTAIN` are collapsed | Preserve both values in API, traces, and reports. |
| Preference is treated as correctness | Require separate fields and analyses. |
| Traces leak prompts or answers | Serialize bounded metadata and approved identifiers only. |
| A dependency failure creates a false hit | Test failure-closed behavior at every boundary. |
| Reason strings drift across modules | Maintain a documented reason taxonomy. |
| Contract changes break report tooling | Version breaking changes and test serialization. |
