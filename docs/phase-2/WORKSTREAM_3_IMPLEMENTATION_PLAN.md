# Phase 2 Workstream 3 Implementation Plan

## Goal

Implement and verify the depth of SSCRE cache-reuse decisions. Every retrieved
candidate must receive a bounded, explainable `SAFE`, `UNSAFE`, or `UNCERTAIN`
decision, and every non-`SAFE` path must remain failure-closed by generating a
new answer.

This workstream turns the frozen Workstream 1 contracts into a tested
candidate-evaluation path. It does not redefine the decision vocabulary,
invent a second trace shape, or treat embedding similarity as proof of
compatibility.

The target outcome is a deterministic Strategy C path that can explain:

- which candidates were retrieved and in what order;
- which freshness and cache-control rules applied;
- which compatibility rule produced each candidate decision;
- why a candidate was selected or rejected;
- why generation occurred when no candidate was safe.

## Status

**Decision-depth checks are recorded.** Execution steps 1–11 are checked. The
handoff is [WORKSTREAM_3_EVIDENCE.md](./WORKSTREAM_3_EVIDENCE.md) (2026-10-07:
full suite 412 passed, 13 PostgreSQL skips). Behavioral changes stay
compatible with the frozen contract versions unless a separately approved
contract revision is created.

## Source of truth

The scope is defined by Workstream 3 in
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).
The following artifacts are frozen inputs and must not be redefined here:

- [`SAFETY_EVALUATION_CONTRACT_v1.md`](./SAFETY_EVALUATION_CONTRACT_v1.md)
  defines `SAFE`, `UNSAFE`, and `UNCERTAIN`, reusable-decision rules, and
  aggregate precedence.
- [`CANDIDATE_TRACE_CONTRACT_v1.md`](./CANDIDATE_TRACE_CONTRACT_v1.md) defines
  bounded candidate evidence, rank, stage, freshness fields, and the reason
  taxonomy.
- [`SERIALIZATION_BOUNDARY_v1.md`](./SERIALIZATION_BOUNDARY_v1.md) defines
  API, log, and report JSON boundaries and redaction requirements.
- [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) records the frozen
  handoff and known limits.
- [`WORKSTREAM_2_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_2_IMPLEMENTATION_PLAN.md)
  defines reviewed expected labels consumed by decision-depth evaluation.
- [`EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
  keeps compatibility, correctness, and preference independent from observed
  runtime decisions.

Canonical implementation locations:

| Responsibility | Current module |
|---|---|
| Decision vocabulary and aggregate result | `src/sscre/safety.py` |
| Pure candidate compatibility checks | `src/sscre/compatibility.py` |
| Freshness and TTL eligibility | `src/sscre/cache_controls.py` |
| Request-path orchestration | `src/sscre/app.py` |
| API and log serialization | `src/sscre/serialization.py` |
| Cache candidate and repository behavior | `src/sscre/cache.py`, `src/sscre/postgres_cache.py` |
| Targeted safety and compatibility tests | `tests/test_safety.py`, `tests/test_compatibility.py` |
| Trace and boundary tests | `tests/test_trace_contract.py`, `tests/test_serialization_boundary.py` |
| Request and failure-path tests | `tests/test_exact_cache.py`, `tests/test_cache_ttl_integration.py`, `tests/test_failure_paths.py` |

## Learning objectives

- [ ] Explain why retrieval similarity is evidence for evaluation, not a
  sufficient condition for serving a cached answer.
- [ ] Distinguish `UNSAFE` known incompatibility from `UNCERTAIN` insufficient
  evidence or dependency failure.
- [ ] Trace a candidate from retrieval through freshness policy, compatibility
  evaluation, aggregation, response serialization, and fallback generation.
- [ ] Design deterministic tests for ordered multi-candidate resolution.
- [ ] Verify that failures cannot turn into cache hits through exception
  handling, stale state, or concurrent writes.
- [ ] Apply bounded and non-sensitive trace rules to operational diagnostics.
- [ ] Understand why observed runtime decisions must remain separate from
  reviewed benchmark expectations.

## Scope

### Included

- Candidate-level decision tests for all three public decisions.
- Compatibility tests for threshold, dynamic, metadata, constraints, entities,
  intent, domain, output format, and temporal evidence.
- Freshness-policy integration with candidate traces.
- Deterministic multi-candidate ordering and aggregate resolution.
- Exact, semantic, and duplicate-write paths under Strategy C.
- Failure-closed behavior for validator, embedding, repository, timeout, and
  trace-serialization failures.
- Bounded candidate traces at API, log, and evaluation-report boundaries.
- Regression evidence that selected candidates are `SAFE` only.
- A completion evidence record and handoff to Workstreams 4–9.

### Excluded

- Changing the `SAFE` / `UNSAFE` / `UNCERTAIN` vocabulary.
- Changing the frozen reason taxonomy or serialization shape without a
  separately versioned contract decision.
- Training or adding a cross-encoder, adaptive threshold, or new embedding
  model.
- Real-provider integration, pricing, or provider-quality measurement.
- Statistical reporting, confidence intervals, or operating-point selection.
- Freshness policy experiments beyond the decision-depth behavior needed to
  prove eligibility and failure-closed reuse.
- Dashboard implementation or a second analytics pipeline.
- Correctness or preference labeling of cached/generated answers.

## Frozen decision semantics

The implementation must preserve this vocabulary:

```text
SAFE       → evidence supports reuse under the active policy
UNSAFE     → a known incompatibility or explicit reuse prohibition exists
UNCERTAIN  → evidence is insufficient or a dependency/validator failed
```

Only `SAFE` may select a candidate, include selected-candidate identity, include
the served similarity, or return the cached answer.

`UNSAFE` and `UNCERTAIN` both generate a new answer, but they remain separate:

- `UNSAFE` is a known negative result, such as a constraint mismatch,
  dynamic-query prohibition, dynamic candidate, or below-threshold similarity.
- `UNCERTAIN` is a conservative non-reuse result caused by missing or
  conflicting evidence, temporal ambiguity, malformed metadata, or dependency
  failure.

The aggregate resolver remains failure-closed:

1. the first `SAFE` trace in deterministic retrieval order wins;
2. otherwise any `UNCERTAIN` produces aggregate `UNCERTAIN`;
3. otherwise non-empty all-negative traces produce aggregate `UNSAFE`;
4. no traces produce `UNSAFE` with `no candidates were retrieved`.

No caller may interpret `UNCERTAIN` as a cache hit or silently collapse it into
`UNSAFE`.

## Current baseline

### Existing implementation

- [x] `SafetyDecision` exposes only `SAFE`, `UNSAFE`, and `UNCERTAIN`.
- [x] `is_reusable_decision()` returns true only for `SAFE`.
- [x] `CandidateTrace` validates decision, similarity bounds, reason taxonomy,
  candidate identity, metadata bounds, and trace metadata size.
- [x] `SafetyResult` forbids selected-candidate identity and similarity for
  non-`SAFE` results.
- [x] `resolve_candidate_traces()` applies conservative aggregate precedence
  and caps trace count.
- [x] `evaluate_candidate()` performs pure compatibility checks for threshold,
  temporal class, metadata, constraints, entities, intent, domain, and format.
- [x] Strategy C evaluates exact and semantic candidates before reuse.
- [x] Strategy C generates when all candidates are incompatible or evidence is
  insufficient.
- [x] Exact-hit, semantic-hit, generated-fallback, and duplicate-write paths
  use the safety decision boundary.
- [x] Candidate traces are serialized without raw prompts, answers, or
  credential fields.
- [x] Trace count and metadata payloads are bounded at serialization
  boundaries.
- [x] Existing tests cover compatible reuse, incompatible constraint reuse,
  missing metadata, dynamic exact entries, stale exact entries, malformed
  embeddings, generation failure, repository failure, and concurrent
  same-query generation.

### Open baseline gaps

- [x] Candidate traces expose every freshness rejection that affected the
  decision, including expired and policy-disallowed candidates (step 3).
- [x] Freshness contextual fields on considered candidates (step 3); compatibility
  paths unchanged for unevaluated rows.
- [x] All candidate-level decision branches have direct unit coverage with
  explicit expected reason values (step 2 matrix + `test_workstream3_pure_evaluator.py`).
- [x] Multi-candidate resolution proves first-safe selection and preserves
  retrieval order after rejected candidates (step 4).
- [x] Validator and serialization exceptions are proven not to produce a hit
  (step 6).
- [x] Exact and semantic paths have equivalent failure-closed guarantees (step 5
  integration tests; step 6 covers dependency failures).
- [x] Deterministic fake-provider replay proves stable traces and response
  decisions across repeated runs (step 8 boundary replay; step 10 full suite
  includes the HTTP replay).
- [x] Completion evidence links commands, test results, and known limitations
  ([WORKSTREAM_3_EVIDENCE.md](./WORKSTREAM_3_EVIDENCE.md)).

## Contract handoff

The reviewed benchmark and runtime evaluator have different meanings:

```text
reviewed benchmark pair
    |
    +--> expected compatibility / reuse label
    +--> independent correctness label, when collected
    +--> independent preference label, when applicable
        (Workstream 2 artifact)

runtime replay
    |
    +--> retrieved candidates
    +--> freshness and cache-control outcomes
    +--> observed SAFE / UNSAFE / UNCERTAIN traces
    +--> selected candidate or generated fallback
        (Workstream 3 artifact)
```

Workstream 3 must not:

- change a reviewed benchmark label because the implementation disagrees;
- infer factual correctness from a `SAFE` runtime decision;
- infer compatibility from similarity alone;
- turn missing correctness into `incorrect`;
- use preference as a correctness proxy;
- store unrestricted prompts, answers, credentials, or provider output in
  operational traces;
- tune the held-out benchmark split while developing these tests.

## Implementation steps

### 1. Audit the decision path and freeze the test matrix

Map every path that can return a cached answer or generate a response:

- exact lookup before embedding;
- semantic retrieval under Strategy B;
- semantic retrieval under Strategy C;
- exact recheck after the generation lock;
- duplicate-write recovery;
- expired, dynamic, missing-TTL, and invalid-TTL entries;
- repository, embedding, validator, and generation failures.

The test matrix must identify the expected decision, reason, source, selected
candidate fields, trace count, and whether generation is required.

- [x] Inventory the current decision producers and consumers in
  `safety.py`, `compatibility.py`, `cache_controls.py`, `app.py`, and
  `serialization.py`.
- [x] Document which paths are contract paths and which are explicit
  Strategy B experiment behavior.
- [x] Define one table or fixture family for candidate metadata, freshness
  outcome, similarity, expected decision, and expected reason.
- [x] Define the distinction between “candidate was retrieved and rejected” and
  “candidate was filtered before evaluation.”
- [x] Identify every current test that asserts reuse without an explicit
  `SAFE` decision.
- [x] Record any intentional compatibility limitation instead of weakening the
  test to match it.

Evidence to record:

- [x] decision-path inventory — [`WORKSTREAM_3_STEP1_AUDIT.md`](./WORKSTREAM_3_STEP1_AUDIT.md);
- [x] test-matrix location — [`tests/fixtures/workstream3_decision_matrix.py`](../../tests/fixtures/workstream3_decision_matrix.py);
- [x] current contract versions — audit § Contract versions;
- [x] list of known gaps and their planned step — audit § Known gaps.

Step 1 evidence (2026-10-07):

- [x] [`WORKSTREAM_3_STEP1_AUDIT.md`](./WORKSTREAM_3_STEP1_AUDIT.md) published.
- [x] Matrix guard tests in `tests/test_workstream3_decision_matrix.py`.
- [x] `python -m pytest -q tests/test_workstream3_decision_matrix.py tests/test_safety.py tests/test_compatibility.py` → 40 passed (2026-10-07).

### 2. Harden the pure candidate evaluator

Keep `evaluate_candidate()` pure: it should not access a repository, provider,
clock, or global mutable state. It should receive all evidence required for a
candidate-level compatibility decision and return one validated
`CandidateTrace`.

Required outcomes:

| Condition | Decision | Reason |
|---|---|---|
| Similarity below threshold | `UNSAFE` | `similarity_below_threshold` |
| Dynamic query | `UNSAFE` | `dynamic_query_not_reusable` |
| Missing candidate metadata | `UNCERTAIN` | `candidate_metadata_missing` |
| Dynamic candidate | `UNSAFE` | `candidate_is_dynamic` |
| Conflicting constraint | `UNSAFE` | `constraint_mismatch:<key>` |
| Incomplete constraint evidence | `UNCERTAIN` | `incomplete_constraint_evidence` |
| Disjoint known entities | `UNSAFE` | `entity_mismatch` |
| Incomplete entity evidence | `UNCERTAIN` | `incomplete_entity_evidence` |
| Known intent/domain/format mismatch | `UNSAFE` | documented mismatch reason |
| Missing intent/domain/format evidence | `UNCERTAIN` | `missing_<field>_evidence` |
| Temporal class mismatch | `UNCERTAIN` | `temporal_class_mismatch` |
| Complete compatible evidence | `SAFE` | `compatible_metadata` |

- [x] Add direct tests for every row in the decision table.
- [x] Test threshold equality and both similarity bounds.
- [x] Test deterministic precedence when more than one mismatch exists.
- [x] Test empty, unknown, and partially populated metadata explicitly.
- [x] Test constraint-key mismatch separately from constraint-value mismatch.
- [x] Test entity overlap, disjoint entities, and one-sided entity evidence.
- [x] Test temporal mismatch independently from TTL expiration.
- [x] Confirm the evaluator never returns `SAFE` for incomplete evidence.
- [x] Confirm every produced reason passes the frozen taxonomy validator.
- [x] Confirm malformed candidate metadata is converted to `UNCERTAIN` at the
  boundary that owns validation, without exposing exception text.

Do not add a borderline decision band. Similarity below the configured
threshold is `UNSAFE`; insufficient compatibility evidence is `UNCERTAIN`.

Step 2 evidence (2026-10-07):

- [x] `evaluate_candidate_boundary()` in `src/sscre/compatibility.py`; Strategy C
  paths in `app.py` use it for failure-closed evaluation.
- [x] Matrix-driven cases in `tests/fixtures/workstream3_evaluator_cases.py`.
- [x] Contract tests in `tests/test_workstream3_pure_evaluator.py`.
- [x] `python -m pytest -q tests/test_workstream3_pure_evaluator.py tests/test_compatibility.py` → 56 passed (2026-10-07).

#### Step 2 independent review (2026-10-07)

**Verdict:** Step 2 checklist is satisfied. Pure `evaluate_candidate()` is unchanged
in semantics; coverage is matrix-driven; Strategy C request paths use
`evaluate_candidate_boundary()`.

| Checklist item | Assessment |
|---|---|
| All decision-table rows | 16/16 via parametrized `test_pure_evaluator_matrix_row` |
| Threshold equality / bounds | At-threshold SAFE at ±1; just-below UNSAFE; invalid threshold rejected |
| Precedence | Similarity before constraint; dynamic query before missing metadata; constraint before entity |
| Metadata shapes | Empty entities, all-unknown scalars, overlap |
| Constraint key vs value | Extra keys → `incomplete_*`; shared key diff → `constraint_mismatch:*` |
| Taxonomy | `validate_trace_reason` on matrix assertions |
| Malformed / validator failure | `evaluate_candidate_boundary` + invalid similarity 2.0 case |

**Minor follow-ups (not step 2 blockers):** duplicate scenarios in
`test_compatibility.py`; replay uses `evaluate_candidate_boundary` and applies
cache control before that boundary; broad `except Exception` on the boundary
is intentional failure-closed but untyped.

### 3. Make freshness evidence explicit and failure-closed

Freshness is a prerequisite for reuse, not proof of compatibility. The
effective order must remain:

```text
cache-control policy and TTL
    ↓
similarity threshold
    ↓
other compatibility rules
    ↓
aggregate decision
    ↓
serve only when SAFE
```

The runtime must never serve a candidate that is expired, has invalid or
missing expiration data, is a disallowed dynamic class, or is otherwise
ineligible under the active policy.

- [x] Decide and document whether ineligible retrieved candidates are emitted
  as `UNSAFE` traces with their cache-control reason or represented as a
  separate bounded pre-compatibility trace stage.
- [x] Keep the decision vocabulary unchanged while making freshness outcomes
  visible in the approved trace fields.
- [x] Ensure `freshness_class` and `cache_control_outcome` are present whenever
  a candidate was considered by the request path.
- [x] Test fresh stable and semi-dynamic candidates.
- [x] Test expired candidates and confirm they cannot be selected.
- [x] Test dynamic entries when dynamic caching is disabled.
- [x] Test missing and invalid expiration metadata.
- [x] Test that a fresh but incompatible candidate remains non-reusable.
- [x] Test that a stale compatible candidate does not become `SAFE`.
- [x] Test exact and semantic freshness behavior consistently.
- [x] Preserve the existing lazy-cleanup behavior unless a separate storage
  task explicitly changes it.

The implementation must not hide a stale-answer risk merely because the
candidate was removed before compatibility evaluation. If the repository API
cannot return rejected candidates, record that limitation and ensure reports
do not claim candidate-level freshness coverage that was not observed.

Step 3 evidence (2026-10-07):

- [x] Policy: [`WORKSTREAM_3_FRESHNESS_TRACE_POLICY.md`](./WORKSTREAM_3_FRESHNESS_TRACE_POLICY.md).
- [x] `build_cache_control_trace()` in `src/sscre/cache_control_traces.py`.
- [x] Strategy C exact/semantic paths trace ineligible candidates at
  `stage=retrieval`; Strategy B still filters before serve.
- [x] Tests: `tests/test_cache_control_traces.py`,
  `tests/test_workstream3_freshness.py`; TTL/exact-cache expectations updated.
- [x] `python -m pytest -q tests/test_cache_control_traces.py tests/test_workstream3_decision_matrix.py tests/test_trace_contract.py tests/test_workstream3_pure_evaluator.py tests/test_compatibility.py` → 74 passed (2026-10-07).
- [x] `tests/test_workstream3_freshness.py` and TTL integration passed in the
  2026-10-07 full suite (412 passed, 13 PostgreSQL skips).

### 4. Verify deterministic candidate ordering and aggregation

Strategy C receives candidates in retrieval order. The first `SAFE` candidate
must win; later candidates must not replace it. If no candidate is safe, an
`UNCERTAIN` trace must dominate only-negative `UNSAFE` traces.

- [x] Add unit tests for empty traces.
- [x] Add unit tests for one `SAFE`, one `UNSAFE`, and one `UNCERTAIN`.
- [x] Add tests for `UNSAFE → SAFE`, proving the safe candidate is selected.
- [x] Add tests for `SAFE → SAFE`, proving the first safe candidate wins.
- [x] Add tests for `UNSAFE → UNCERTAIN`, proving aggregate `UNCERTAIN`.
- [x] Add tests for multiple `UNSAFE`, proving aggregate `UNSAFE`.
- [x] Verify candidate order remains stable in API, logs, and reports.
- [x] Verify selected hash and similarity appear only for aggregate `SAFE`.
- [x] Verify the aggregate trace list is capped without reordering retained
  candidates.
- [x] Verify a candidate outside the retained trace cap cannot be selected.
- [x] Verify deterministic fake retrieval produces byte-stable trace JSON
  after sorting through the documented serialization boundary.

Step 4 evidence (2026-10-07):

- [x] `tests/test_workstream3_aggregation.py` — resolve matrix, caps, boundary
  logs, API multi-candidate ordering (when `create_app` imports).
- [x] Existing coverage retained in `tests/test_safety.py` and
  `tests/test_serialization_boundary.py`.
- [x] `python -m pytest -q tests/test_workstream3_aggregation.py tests/test_safety.py tests/test_serialization_boundary.py` → 43 passed, 1 skipped (2026-10-07).

### 5. Integrate exact and semantic Strategy C paths

Use the existing request orchestration and keep the pure evaluator independent
of providers and repositories. Exact and semantic paths must share the same
decision semantics even if their retrieval mechanics differ.

- [x] Test a compatible exact candidate and verify `SAFE`, selected identity,
  similarity, and cached response.
- [x] Test an exact candidate with missing metadata and verify
  `UNCERTAIN` plus generation.
- [x] Test an exact candidate with a known mismatch and verify `UNSAFE` plus
  generation.
- [x] Test multiple semantic candidates where the first is incompatible and a
  later candidate is compatible.
- [x] Test multiple semantic candidates where all are incompatible.
- [x] Test multiple semantic candidates where evidence is incomplete.
- [x] Verify no generated response contains a selected cached candidate.
- [x] Verify no generated response is labeled `SAFE`.
- [x] Verify the generated fallback keeps the candidate traces that explain
  the decision.
- [x] Verify Strategy B remains explicitly retrieval-only and is not used as
  evidence that Strategy C is safe.
- [x] Verify exact-hit behavior does not bypass Strategy C compatibility
  checks when Strategy C is active.
- [x] Verify the post-generation exact recheck applies the same safety path.
- [x] Verify duplicate-write recovery applies the same safety path.

Step 5 evidence (2026-10-07):

- [x] `tests/test_workstream3_strategy_c_paths.py` — Strategy C/B path matrix.
- [x] Duplicate-write path records `decision_traces` when raced entry fails
  compatibility (`app.py`).
- [x] `python -m pytest -q tests/test_workstream3_strategy_c_paths.py` passed
  inside the 2026-10-07 full suite.

### 6. Cover dependency and validator failures

Any failure in retrieval, embedding validation, metadata validation, candidate
evaluation, trace construction, or repository access must fail closed. A
generated response may still be returned when the provider succeeds, but a
failed safety dependency must not produce a cache hit.

- [x] Test embedding failure after an exact miss.
- [x] Test malformed embedding shape, dimension, and non-finite values.
- [x] Test semantic repository search failure.
- [x] Test repository timeout during lookup and semantic search.
- [x] Test candidate metadata validation failure.
- [x] Test an unexpected evaluator exception and verify
  `safety_validator_error` / `UNCERTAIN` behavior at the approved boundary.
- [x] Test trace metadata size failure and verify no candidate is served.
- [x] Test boundary serialization failure and verify no candidate is served.
- [x] Test generation failure after an `UNSAFE` or `UNCERTAIN` candidate
  decision and verify the controlled error remains non-reusable.
- [x] Test cache write failure after successful generation and verify the
  generated answer is returned without a false cache hit.
- [x] Test repository recovery after a failed first lookup without reusing
  unvalidated state.
- [x] Confirm logs contain bounded error type/reason fields, not exception
  payloads, answers, prompts, or credentials.

Step 6 evidence (2026-10-07):

- [x] `tests/test_workstream3_failure_paths.py` consolidates dependency failure
  coverage (existing overlap in `tests/test_exact_cache.py`,
  `tests/test_failure_paths.py`).
- [x] Boundary serialization failure on cache emit returns HTTP 500 (no false
  cache hit).
- [x] `python -m pytest -q tests/test_workstream3_failure_paths.py` passed
  inside the 2026-10-07 full suite. Boundary serialization failure is observed
  as HTTP 500 (`raise_server_exceptions=False` on that TestClient).
- [x] Candidate metadata validation failure paths covered in
  `tests/test_workstream3_strategy_c_paths.py` (exact missing metadata) and
  `tests/test_workstream3_pure_evaluator.py` / matrix row
  `pe_missing_candidate_metadata`.

### 7. Test concurrent and duplicate-write safety boundaries

Concurrency tests in this workstream establish decision safety, not universal
capacity guarantees. A concurrent request must not cause an unsafe or stale
entry to be served merely because another request populated the repository.

- [x] Test concurrent same-query requests with a shared in-memory repository.
- [x] Test concurrent requests where one generated entry lacks valid metadata.
- [x] Test duplicate insertion followed by an incompatible existing entry.
- [x] Test duplicate insertion followed by an expired existing entry.
- [x] Test duplicate insertion followed by a compatible existing entry.
- [x] Verify every duplicate-write recovery candidate is evaluated before reuse
  under Strategy C.
- [x] Verify only one response may report a cache reuse for a newly generated
  entry when the repository contract permits that distinction.
- [x] Keep multi-process PostgreSQL capacity and restart testing in
  Workstream 8, while recording any unsupported behavior here.

Step 7 evidence (2026-10-07):

- [x] `tests/test_workstream3_concurrency.py` — Strategy C concurrent same-query
  races, metadata-less duplicate recovery, duplicate incompatible/expired/
  compatible recovery, concurrent expired exact hits.
- [x] Overlap retained in `tests/test_workstream3_strategy_c_paths.py` (post-lock
  recheck) and `tests/test_failure_paths.py` (legacy concurrent reuse without
  explicit Strategy C assertions).
- [x] Multi-process PostgreSQL capacity, restart, and cross-host duplicate races
  remain **out of scope** (Workstream 8); in-memory / simulated duplicate insert
  only.
- [x] `python -m pytest -q tests/test_workstream3_concurrency.py` passed
  inside the 2026-10-07 full suite. Expired exact answers are not served;
  in-process waiters may reuse the fresh replacement.

### 8. Verify serialization and redaction boundaries

The trace is an operational explanation, not a copy of the request or answer.
All output forms must use the frozen boundary conventions.

- [x] Test API `candidate_traces` for safe, unsafe, and uncertain outcomes.
- [x] Test `null` traces when no candidate was considered.
- [x] Test log serialization with deterministic key ordering.
- [x] Test report serialization with contract and trace versions.
- [x] Test trace count and combined JSON byte limits.
- [x] Test per-trace metadata bounds.
- [x] Test forbidden fields including answer, prompt, query text, token,
  secret, authorization, and provider-secret variants.
- [x] Test selected candidate identity is absent for non-`SAFE` results.
- [x] Test similarity is absent for non-`SAFE` results.
- [x] Test failure-gallery/report redaction remains intact.
- [x] Test JSON round-trip through the public boundary without changing
  decisions, reasons, order, or null semantics.
- [x] Confirm trace serialization does not duplicate complete cached answers.

Step 8 evidence (2026-10-07):

- [x] `tests/test_workstream3_serialization.py` — API `QueryResponse` traces for
  SAFE/UNSAFE/UNCERTAIN, `null` when no candidate was considered, sorted log
  keys, report contract/trace versions, count/byte/metadata bounds, forbidden
  fields, non-SAFE selection/similarity omission, nested failure-gallery
  redaction, JSON round-trip, answer-free traces, byte-stable fake-retrieval
  replay.
- [x] Empty aggregate payloads use `candidate_traces: null` via
  `serialize_safety_result_for_boundary()` / `boundary_candidate_traces()`.
- [x] `attach_evaluation_report_schema()` stamps `safety_contract_version` and
  `trace_contract_version`; saved reports asserted in
  `test_saved_report_uses_boundary_schema_version`.
- [x] `python -m pytest -q tests/test_workstream3_serialization.py tests/test_serialization_boundary.py tests/test_trace_contract.py tests/test_safety.py tests/test_workstream3_aggregation.py tests/test_benchmark.py::test_saved_report_uses_boundary_schema_version tests/test_benchmark.py::test_saved_compatibility_report_omits_query_text_in_failures` → 79 passed, 2 skipped (2026-10-07, Python 3.14.5). Skips: HTTP `create_app` tests (`psycopg`/libpq unavailable on this host).
- [x] `python -m pytest -q tests/test_workstream3_serialization.py` including
  `test_api_http_traces_for_safe_unsafe_uncertain_and_null` passed inside the
  2026-10-07 full suite.

### 9. Replay reviewed benchmark examples without changing labels

Use the Workstream 2 artifact as an input to decision-depth tests and replay.
The observed implementation decision must be stored separately from the
reviewed expected compatibility label.

- [x] Run the development split through the existing evaluation path using a
  frozen configuration.
- [x] Record observed decisions and traces by stable pair ID.
- [x] Compare expected compatibility labels to observed runtime decisions
  without rewriting either field.
- [x] Classify disagreements as evaluator behavior, metadata insufficiency,
  freshness policy, retrieval miss, or benchmark/data limitation.
- [x] Do not use held-out labels to alter thresholds or compatibility rules.
- [x] Confirm correctness and preference fields remain independent and nullable
  where the benchmark says they are unavailable.
- [x] Add only bounded record identity to operational reports.
- [x] Leave statistical confidence intervals and final operating-point claims
  to Workstream 5.

Step 9 evidence (2026-10-07):

- [x] `tests/test_workstream3_replay.py` — development-split replay keeps reviewed
  labels unchanged; `observed_pair_records` keyed by pair ID with separate
  `expected_compatibility` / `expected_decision` / `observed_decision` /
  `evaluation_labels`; traces and disagreement class included; no query text.
- [x] `classify_compatibility_disagreement()` in `src/sscre/evaluation_labels.py`
  plus unit rows in `tests/test_evaluation_labels.py`.
- [x] Held-out compatibility-cache CLI still selects the threshold from
  development (`threshold_selection_split=development`).
- [x] Frozen config: `experiments/evaluation_config.json`
  (`evaluation-config-1.0`, dataset `reviewed-query-pairs-1.1`); replay tests
  use threshold `0.9`.
- [x] Development replay at threshold 0.9 (21 pairs): 12 match, 9 mismatch;
  disagreement classes `evaluator_behavior` 6, `metadata_insufficiency` 3;
  correctness and preference remain `not_collected` (nullable, not inferred
  from `SAFE`).
- [x] `python -m pytest -q tests/test_workstream3_replay.py tests/test_evaluation_labels.py tests/test_benchmark.py::test_compatibility_baseline_reports_safety_and_abstention_metrics tests/test_benchmark.py::test_compatibility_report_keeps_unsafe_and_uncertain_distinct tests/test_benchmark.py::test_saved_compatibility_report_omits_query_text_in_failures tests/test_benchmark.py::test_held_out_comparison_uses_development_threshold` → 21 passed (2026-10-07, Python 3.14.5).
- [x] CLI uses `--baseline compatibility-cache` (not `compatibility`):
  `python -m sscre.evaluate --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --baseline compatibility-cache --split development --output <tmp>/workstream3-development.json`.

### 10. Record completion evidence and hand off

The evidence record must make it possible for another workstream to understand
what was tested, what passed, and what remains unsupported.

- [x] Record contract versions and implementation commit/state.
- [x] Record the targeted test command and result.
- [x] Record the full-suite command and result, or explicitly record why it
  could not run.
- [x] Record any skipped PostgreSQL or provider-dependent tests.
- [x] Record decision counts by `SAFE`, `UNSAFE`, and `UNCERTAIN`.
- [x] Record trace-reason coverage and freshness-outcome coverage.
- [x] Record representative failure-closed examples by category.
- [x] Record deterministic replay evidence.
- [x] Record known limitations, especially filtered-candidate visibility and
  unsupported multi-process behavior.
- [x] Link the evidence from `PHASE_2_IMPLEMENTATION_PLAN.md`.
- [x] Hand off the tested trace/decision artifacts to Workstreams 4–9.

Step 10 evidence (2026-10-07): [WORKSTREAM_3_EVIDENCE.md](./WORKSTREAM_3_EVIDENCE.md).

- [x] Targeted suite 60 passed. Full suite `python -m pytest -q` → 412 passed,
  13 skipped (`tests/test_postgres_integration.py`; `SSCRE_DATABASE_URL` unset).
- [x] Development replay artifact:
  `artifacts/evaluation/workstream3-development.json` (threshold 0.95,
  42 direction evaluations: `SAFE` 1 / `UNSAFE` 38 / `UNCERTAIN` 3).
- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks` passed.

## Test plan

### Unit tests

- [x] `SAFE` is the only reusable decision.
- [x] `UNSAFE` and `UNCERTAIN` are valid and non-reusable.
- [x] Invalid decisions, similarities, candidate identities, and reasons are
  rejected.
- [x] Every compatibility reason maps to the correct decision.
- [x] Similarity threshold behavior is deterministic and inclusive at the
  configured boundary.
- [x] Missing metadata and incomplete evidence produce `UNCERTAIN`.
- [x] Known conflicts produce `UNSAFE`.
- [x] Trace metadata and reason values remain bounded.
- [x] `SafetyResult` invariants reject selected candidates on non-`SAFE`
  results.

### Aggregate and ordering tests

- [x] Empty trace list returns `UNSAFE` / `no candidates were retrieved`.
- [x] First `SAFE` wins.
- [x] `UNCERTAIN` dominates only-negative `UNSAFE` traces.
- [x] All-negative traces aggregate to `UNSAFE`.
- [x] Trace order and candidate rank are preserved.
- [x] Trace caps do not permit selection outside the cap.

### Freshness tests

- [x] Fresh stable candidates may proceed to compatibility evaluation.
- [x] Fresh semi-dynamic candidates may proceed under configured policy.
- [x] Dynamic candidates are not served when policy disables them.
- [x] Expired candidates are not served.
- [x] Missing expiration is not treated as fresh.
- [x] Invalid expiration is not treated as fresh.
- [x] Freshness outcomes are visible in the approved trace/context fields.
- [x] Freshness rejection cannot be converted to a `SAFE` decision by exact,
  semantic, or duplicate-write paths.

### Integration tests

- [x] Exact Strategy C compatible candidate is reused.
- [x] Exact Strategy C incompatible candidate generates.
- [x] Exact Strategy C uncertain candidate generates.
- [x] Semantic Strategy C selects only a compatible candidate.
- [x] Semantic Strategy C generates for all-incompatible candidates.
- [x] Semantic Strategy C generates for incomplete evidence.
- [x] Strategy B remains opt-in retrieval-only behavior.
- [x] Post-generation recheck and duplicate-write recovery remain safe.
- [x] Repository, embedding, validator, timeout, and serialization failures
  cannot produce a cache hit.
- [x] Concurrent requests do not bypass candidate evaluation.

### Boundary and regression tests

- [x] API response decision, reason, selected hash, similarity, and traces are
  mutually consistent.
- [x] Structured logs contain contract versions and no forbidden content.
- [x] Evaluation reports preserve expected versus observed values.
- [x] Saved reports remain redacted.
- [x] Deterministic fake-provider replay produces stable decisions and traces.
- [x] Existing Workstream 1 contract tests remain green.

## Verification commands

Run from the repository root after implementation:

```bash
python -m pytest -q tests/test_safety.py tests/test_compatibility.py \
  tests/test_trace_contract.py tests/test_serialization_boundary.py \
  tests/test_workstream1_contract.py

python -m pytest -q tests/test_exact_cache.py \
  tests/test_cache_ttl_integration.py tests/test_failure_paths.py

python -m pytest -q

python -m sscre.benchmark_validate --benchmark-dir benchmarks

python -m sscre.evaluate \
  --benchmark benchmarks/development.jsonl \
  --config experiments/evaluation_config.json \
  --baseline compatibility-cache \
  --split development \
  --output artifacts/evaluation/workstream3-development.json
```

If the evaluation CLI or benchmark artifact changes before this workstream is
completed, update the commands to the current checked-in interface and record
the exact command in the evidence section. Do not mark full-suite,
PostgreSQL, provider, or held-out claims complete when those checks were not
run successfully.

For each successful verification, record:

- command and date;
- Python and package versions;
- contract and dataset versions;
- test count and skipped tests;
- decision and trace-reason counts;
- repository/provider dependencies used;
- pass/fail result;
- known limitations.

## Acceptance criteria

- [x] The evaluator emits only `SAFE`, `UNSAFE`, or `UNCERTAIN`.
- [x] Only `SAFE` can serve a cache candidate or include selected-candidate
  identity and similarity.
- [x] Unit tests cover all required candidate decisions and reason taxonomy.
- [x] Known incompatibilities are `UNSAFE`; incomplete evidence and dependency
  failures are `UNCERTAIN`.
- [x] Similarity below threshold is `UNSAFE` with no separate borderline band.
- [x] Expired, dynamically disallowed, missing-TTL, and invalid-TTL entries
  cannot be served.
- [x] Freshness and cache-control outcomes are available for considered
  candidates without exposing raw prompts or answers.
- [x] Candidate traces identify the evidence or rule that caused each
  candidate decision.
- [x] Candidate order is deterministic and first-safe selection is tested.
- [x] Aggregate `UNCERTAIN` is preserved when no candidate is safe and any
  candidate lacks sufficient evidence.
- [x] Exact, semantic, post-generation, and duplicate-write paths share the
  same Strategy C safety boundary.
- [x] Repository, embedding, validator, timeout, and serialization failures
  remain failure-closed.
- [x] Trace count, metadata, and combined serialized payload remain bounded.
- [x] API, logs, and reports preserve the frozen serialization boundary.
- [x] Operational traces contain no raw query, answer, prompt, credential, or
  provider-secret fields.
- [x] Deterministic fake-provider replay reproduces the same decisions and
  trace order.
- [x] Runtime observed decisions remain separate from Workstream 2 expected
  compatibility, correctness, and preference labels.
- [x] Targeted regression tests pass.
- [x] The full test suite passes, or unavailable checks and their consequences
  are explicitly documented.
- [x] Completion evidence is linked from the Phase 2 parent plan.

## Completion evidence

Before marking this workstream complete, add a short evidence record to this
file or a linked artifact containing:

- [x] implementation files and contract versions;
- [x] decision matrix and reason taxonomy coverage;
- [x] exact and semantic candidate counts exercised;
- [x] `SAFE`, `UNSAFE`, and `UNCERTAIN` counts;
- [x] freshness and cache-control outcome counts;
- [x] failure-path and failure-closed test results;
- [x] trace-bound and redaction test results;
- [x] deterministic replay command and result;
- [x] targeted test command and result;
- [x] full-suite result and skipped dependencies;
- [x] benchmark dataset/split identity used for replay;
- [x] known limitations and their effect on Phase 2 conclusions.

Do not mark safety, freshness, trace, or failure-closed criteria complete based
only on the presence of code. Each completion mark requires the corresponding
test or artifact evidence.

## Handoff to later workstreams

Workstream 4 consumes the stable decision and trace boundary when measuring a
real provider. Workstream 5 consumes observed decisions and traces for
confidence intervals, baseline comparison, and Pareto analysis. Workstream 6
consumes freshness classes and cache-control outcomes. Workstream 7 consumes
bounded failure examples and reason categories. Workstream 8 consumes the
failure-closed concurrency behavior and its documented environment limits.
Workstream 9 consumes the stable report/trace artifacts for dashboards and any
gated dual-model experiment.

Handoff requirements:

- [x] Publish the tested safety and trace contract versions.
- [x] Publish the targeted and full-suite verification commands.
- [x] Publish the decision matrix and reason/freshness coverage summary.
- [x] Publish the bounded trace serialization and redaction behavior.
- [x] Confirm that only `SAFE` is reusable.
- [x] Confirm that `UNSAFE` and `UNCERTAIN` remain separately reportable.
- [x] Confirm that observed runtime decisions are separate from benchmark
  labels.
- [x] Document unsupported PostgreSQL/provider/concurrency checks for the
  workstreams that own them.
- [x] Link the completion evidence from
  [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).

## Execution sequence

1. [x] Audit all decision producers, consumers, and current tests.
2. [x] Freeze the candidate decision matrix and test fixtures.
3. [x] Complete pure evaluator unit coverage.
4. [x] Make freshness evidence explicit without changing the frozen vocabulary.
5. [x] Add deterministic aggregate and ordering tests.
6. [x] Verify exact, semantic, post-generation, and duplicate-write paths.
7. [x] Verify dependency failures and serialization failures are
  failure-closed.
8. [x] Run boundary, redaction, and deterministic replay tests.
9. [x] Replay the development benchmark without changing reviewed labels.
10. [x] Run targeted tests and the full suite.
11. [x] Record evidence, limitations, and downstream handoff.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Similarity is treated as compatibility | Require a Strategy C compatibility trace before reuse. |
| `UNCERTAIN` is collapsed into `UNSAFE` | Preserve the frozen decision enum, aggregate precedence, and separate report counts. |
| Expired candidates disappear without evidence | Define and test the freshness trace policy; document any repository visibility limitation. |
| A later safe candidate is skipped after an unsafe first candidate | Test ordered multi-candidate resolution and first-safe selection. |
| A non-safe candidate is served through a race or duplicate write | Re-evaluate every post-generation and duplicate-write candidate under Strategy C. |
| Validator or serializer failure produces a false hit | Convert failures to `UNCERTAIN` and test the full response boundary. |
| Trace growth exposes sensitive data or exhausts limits | Enforce candidate count, metadata, combined payload, and forbidden-key checks. |
| Exact and semantic paths diverge | Use shared decision invariants and integration tests for both paths. |
| Runtime decisions are confused with benchmark labels | Keep expected labels and observed traces in separate report fields. |
| Tests overstate production capacity | Keep PostgreSQL load/restart capacity claims in Workstream 8. |
| Test-only behavior masks real provider differences | Use deterministic fakes here and label real-provider evidence separately in Workstream 4. |
| Held-out evaluation is tuned during implementation | Replay development data only until the operating point is frozen. |
