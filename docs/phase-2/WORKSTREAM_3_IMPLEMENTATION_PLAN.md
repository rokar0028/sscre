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

**Baseline exists; decision-depth hardening is open.** The repository already
contains `CandidateTrace`, `SafetyResult`, `resolve_candidate_traces`,
`evaluate_candidate`, Strategy C integration in `app.py`, bounded trace
serialization, and tests for several compatibility and failure paths.

The remaining work is to close the contract gaps and make the behavior
comprehensive and reproducible:

- candidate-level tests do not yet cover every required decision and freshness
  outcome as a single contract suite;
- freshness filtering currently prevents some expired or disallowed candidates
  from appearing in candidate traces;
- the trace contract requires contextual freshness and cache-control evidence
  for evaluated candidates, but the pure evaluator does not produce that
  context itself;
- validator, repository, embedding, and serialization failures need explicit
  failure-closed integration coverage;
- deterministic ordering and aggregate behavior need regression tests across
  multiple candidates;
- completion evidence for this workstream has not yet been recorded.

This plan treats the current implementation as the starting point. Any
behavioral change must remain compatible with the frozen contract versions
unless a separately approved contract revision is created.

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

- [ ] Candidate traces expose every freshness rejection that affected the
  decision, including expired and policy-disallowed candidates.
- [ ] The trace contract's required contextual fields are consistently present
  for every evaluated candidate and every fallback reason.
- [ ] All candidate-level decision branches have direct unit coverage with
  explicit expected reason values.
- [ ] Multi-candidate resolution proves first-safe selection and preserves
  retrieval order after rejected candidates.
- [ ] Validator and serialization exceptions are proven not to produce a hit.
- [ ] Exact and semantic paths have equivalent failure-closed guarantees.
- [ ] Deterministic fake-provider replay proves stable traces and response
  decisions across repeated runs.
- [ ] Completion evidence links commands, test results, and known limitations.

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

- [ ] Add direct tests for every row in the decision table.
- [ ] Test threshold equality and both similarity bounds.
- [ ] Test deterministic precedence when more than one mismatch exists.
- [ ] Test empty, unknown, and partially populated metadata explicitly.
- [ ] Test constraint-key mismatch separately from constraint-value mismatch.
- [ ] Test entity overlap, disjoint entities, and one-sided entity evidence.
- [ ] Test temporal mismatch independently from TTL expiration.
- [ ] Confirm the evaluator never returns `SAFE` for incomplete evidence.
- [ ] Confirm every produced reason passes the frozen taxonomy validator.
- [ ] Confirm malformed candidate metadata is converted to `UNCERTAIN` at the
  boundary that owns validation, without exposing exception text.

Do not add a borderline decision band. Similarity below the configured
threshold is `UNSAFE`; insufficient compatibility evidence is `UNCERTAIN`.

### 3. Make freshness evidence explicit and failure-closed

Freshness is a prerequisite for reuse, not proof of compatibility. The
effective order must remain:

```text
cache-control policy and TTL
    ↓
candidate compatibility
    ↓
similarity threshold
    ↓
aggregate decision
    ↓
serve only when SAFE
```

The runtime must never serve a candidate that is expired, has invalid or
missing expiration data, is a disallowed dynamic class, or is otherwise
ineligible under the active policy.

- [ ] Decide and document whether ineligible retrieved candidates are emitted
  as `UNSAFE` traces with their cache-control reason or represented as a
  separate bounded pre-compatibility trace stage.
- [ ] Keep the decision vocabulary unchanged while making freshness outcomes
  visible in the approved trace fields.
- [ ] Ensure `freshness_class` and `cache_control_outcome` are present whenever
  a candidate was considered by the request path.
- [ ] Test fresh stable and semi-dynamic candidates.
- [ ] Test expired candidates and confirm they cannot be selected.
- [ ] Test dynamic entries when dynamic caching is disabled.
- [ ] Test missing and invalid expiration metadata.
- [ ] Test that a fresh but incompatible candidate remains non-reusable.
- [ ] Test that a stale compatible candidate does not become `SAFE`.
- [ ] Test exact and semantic freshness behavior consistently.
- [ ] Preserve the existing lazy-cleanup behavior unless a separate storage
  task explicitly changes it.

The implementation must not hide a stale-answer risk merely because the
candidate was removed before compatibility evaluation. If the repository API
cannot return rejected candidates, record that limitation and ensure reports
do not claim candidate-level freshness coverage that was not observed.

### 4. Verify deterministic candidate ordering and aggregation

Strategy C receives candidates in retrieval order. The first `SAFE` candidate
must win; later candidates must not replace it. If no candidate is safe, an
`UNCERTAIN` trace must dominate only-negative `UNSAFE` traces.

- [ ] Add unit tests for empty traces.
- [ ] Add unit tests for one `SAFE`, one `UNSAFE`, and one `UNCERTAIN`.
- [ ] Add tests for `UNSAFE → SAFE`, proving the safe candidate is selected.
- [ ] Add tests for `SAFE → SAFE`, proving the first safe candidate wins.
- [ ] Add tests for `UNSAFE → UNCERTAIN`, proving aggregate `UNCERTAIN`.
- [ ] Add tests for multiple `UNSAFE`, proving aggregate `UNSAFE`.
- [ ] Verify candidate order remains stable in API, logs, and reports.
- [ ] Verify selected hash and similarity appear only for aggregate `SAFE`.
- [ ] Verify the aggregate trace list is capped without reordering retained
  candidates.
- [ ] Verify a candidate outside the retained trace cap cannot be selected.
- [ ] Verify deterministic fake retrieval produces byte-stable trace JSON
  after sorting through the documented serialization boundary.

### 5. Integrate exact and semantic Strategy C paths

Use the existing request orchestration and keep the pure evaluator independent
of providers and repositories. Exact and semantic paths must share the same
decision semantics even if their retrieval mechanics differ.

- [ ] Test a compatible exact candidate and verify `SAFE`, selected identity,
  similarity, and cached response.
- [ ] Test an exact candidate with missing metadata and verify
  `UNCERTAIN` plus generation.
- [ ] Test an exact candidate with a known mismatch and verify `UNSAFE` plus
  generation.
- [ ] Test multiple semantic candidates where the first is incompatible and a
  later candidate is compatible.
- [ ] Test multiple semantic candidates where all are incompatible.
- [ ] Test multiple semantic candidates where evidence is incomplete.
- [ ] Verify no generated response contains a selected cached candidate.
- [ ] Verify no generated response is labeled `SAFE`.
- [ ] Verify the generated fallback keeps the candidate traces that explain
  the decision.
- [ ] Verify Strategy B remains explicitly retrieval-only and is not used as
  evidence that Strategy C is safe.
- [ ] Verify exact-hit behavior does not bypass Strategy C compatibility
  checks when Strategy C is active.
- [ ] Verify the post-generation exact recheck applies the same safety path.
- [ ] Verify duplicate-write recovery applies the same safety path.

### 6. Cover dependency and validator failures

Any failure in retrieval, embedding validation, metadata validation, candidate
evaluation, trace construction, or repository access must fail closed. A
generated response may still be returned when the provider succeeds, but a
failed safety dependency must not produce a cache hit.

- [ ] Test embedding failure after an exact miss.
- [ ] Test malformed embedding shape, dimension, and non-finite values.
- [ ] Test semantic repository search failure.
- [ ] Test repository timeout during lookup and semantic search.
- [ ] Test candidate metadata validation failure.
- [ ] Test an unexpected evaluator exception and verify
  `safety_validator_error` / `UNCERTAIN` behavior at the approved boundary.
- [ ] Test trace metadata size failure and verify no candidate is served.
- [ ] Test boundary serialization failure and verify no candidate is served.
- [ ] Test generation failure after an `UNSAFE` or `UNCERTAIN` candidate
  decision and verify the controlled error remains non-reusable.
- [ ] Test cache write failure after successful generation and verify the
  generated answer is returned without a false cache hit.
- [ ] Test repository recovery after a failed first lookup without reusing
  unvalidated state.
- [ ] Confirm logs contain bounded error type/reason fields, not exception
  payloads, answers, prompts, or credentials.

### 7. Test concurrent and duplicate-write safety boundaries

Concurrency tests in this workstream establish decision safety, not universal
capacity guarantees. A concurrent request must not cause an unsafe or stale
entry to be served merely because another request populated the repository.

- [ ] Test concurrent same-query requests with a shared in-memory repository.
- [ ] Test concurrent requests where one generated entry lacks valid metadata.
- [ ] Test duplicate insertion followed by an incompatible existing entry.
- [ ] Test duplicate insertion followed by an expired existing entry.
- [ ] Test duplicate insertion followed by a compatible existing entry.
- [ ] Verify every duplicate-write recovery candidate is evaluated before reuse
  under Strategy C.
- [ ] Verify only one response may report a cache reuse for a newly generated
  entry when the repository contract permits that distinction.
- [ ] Keep multi-process PostgreSQL capacity and restart testing in
  Workstream 8, while recording any unsupported behavior here.

### 8. Verify serialization and redaction boundaries

The trace is an operational explanation, not a copy of the request or answer.
All output forms must use the frozen boundary conventions.

- [ ] Test API `candidate_traces` for safe, unsafe, and uncertain outcomes.
- [ ] Test `null` traces when no candidate was considered.
- [ ] Test log serialization with deterministic key ordering.
- [ ] Test report serialization with contract and trace versions.
- [ ] Test trace count and combined JSON byte limits.
- [ ] Test per-trace metadata bounds.
- [ ] Test forbidden fields including answer, prompt, query text, token,
  secret, authorization, and provider-secret variants.
- [ ] Test selected candidate identity is absent for non-`SAFE` results.
- [ ] Test similarity is absent for non-`SAFE` results.
- [ ] Test failure-gallery/report redaction remains intact.
- [ ] Test JSON round-trip through the public boundary without changing
  decisions, reasons, order, or null semantics.
- [ ] Confirm trace serialization does not duplicate complete cached answers.

### 9. Replay reviewed benchmark examples without changing labels

Use the Workstream 2 artifact as an input to decision-depth tests and replay.
The observed implementation decision must be stored separately from the
reviewed expected compatibility label.

- [ ] Run the development split through the existing evaluation path using a
  frozen configuration.
- [ ] Record observed decisions and traces by stable pair ID.
- [ ] Compare expected compatibility labels to observed runtime decisions
  without rewriting either field.
- [ ] Classify disagreements as evaluator behavior, metadata insufficiency,
  freshness policy, retrieval miss, or benchmark/data limitation.
- [ ] Do not use held-out labels to alter thresholds or compatibility rules.
- [ ] Confirm correctness and preference fields remain independent and nullable
  where the benchmark says they are unavailable.
- [ ] Add only bounded record identity to operational reports.
- [ ] Leave statistical confidence intervals and final operating-point claims
  to Workstream 5.

### 10. Record completion evidence and hand off

The evidence record must make it possible for another workstream to understand
what was tested, what passed, and what remains unsupported.

- [ ] Record contract versions and implementation commit/state.
- [ ] Record the targeted test command and result.
- [ ] Record the full-suite command and result, or explicitly record why it
  could not run.
- [ ] Record any skipped PostgreSQL or provider-dependent tests.
- [ ] Record decision counts by `SAFE`, `UNSAFE`, and `UNCERTAIN`.
- [ ] Record trace-reason coverage and freshness-outcome coverage.
- [ ] Record representative failure-closed examples by category.
- [ ] Record deterministic replay evidence.
- [ ] Record known limitations, especially filtered-candidate visibility and
  unsupported multi-process behavior.
- [ ] Link the evidence from `PHASE_2_IMPLEMENTATION_PLAN.md`.
- [ ] Hand off the tested trace/decision artifacts to Workstreams 4–9.

## Test plan

### Unit tests

- [ ] `SAFE` is the only reusable decision.
- [ ] `UNSAFE` and `UNCERTAIN` are valid and non-reusable.
- [ ] Invalid decisions, similarities, candidate identities, and reasons are
  rejected.
- [ ] Every compatibility reason maps to the correct decision.
- [ ] Similarity threshold behavior is deterministic and inclusive at the
  configured boundary.
- [ ] Missing metadata and incomplete evidence produce `UNCERTAIN`.
- [ ] Known conflicts produce `UNSAFE`.
- [ ] Trace metadata and reason values remain bounded.
- [ ] `SafetyResult` invariants reject selected candidates on non-`SAFE`
  results.

### Aggregate and ordering tests

- [ ] Empty trace list returns `UNSAFE` / `no candidates were retrieved`.
- [ ] First `SAFE` wins.
- [ ] `UNCERTAIN` dominates only-negative `UNSAFE` traces.
- [ ] All-negative traces aggregate to `UNSAFE`.
- [ ] Trace order and candidate rank are preserved.
- [ ] Trace caps do not permit selection outside the cap.

### Freshness tests

- [ ] Fresh stable candidates may proceed to compatibility evaluation.
- [ ] Fresh semi-dynamic candidates may proceed under configured policy.
- [ ] Dynamic candidates are not served when policy disables them.
- [ ] Expired candidates are not served.
- [ ] Missing expiration is not treated as fresh.
- [ ] Invalid expiration is not treated as fresh.
- [ ] Freshness outcomes are visible in the approved trace/context fields.
- [ ] Freshness rejection cannot be converted to a `SAFE` decision by exact,
  semantic, or duplicate-write paths.

### Integration tests

- [ ] Exact Strategy C compatible candidate is reused.
- [ ] Exact Strategy C incompatible candidate generates.
- [ ] Exact Strategy C uncertain candidate generates.
- [ ] Semantic Strategy C selects only a compatible candidate.
- [ ] Semantic Strategy C generates for all-incompatible candidates.
- [ ] Semantic Strategy C generates for incomplete evidence.
- [ ] Strategy B remains opt-in retrieval-only behavior.
- [ ] Post-generation recheck and duplicate-write recovery remain safe.
- [ ] Repository, embedding, validator, timeout, and serialization failures
  cannot produce a cache hit.
- [ ] Concurrent requests do not bypass candidate evaluation.

### Boundary and regression tests

- [ ] API response decision, reason, selected hash, similarity, and traces are
  mutually consistent.
- [ ] Structured logs contain contract versions and no forbidden content.
- [ ] Evaluation reports preserve expected versus observed values.
- [ ] Saved reports remain redacted.
- [ ] Deterministic fake-provider replay produces stable decisions and traces.
- [ ] Existing Workstream 1 contract tests remain green.

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
  --baseline compatibility \
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

- [ ] The evaluator emits only `SAFE`, `UNSAFE`, or `UNCERTAIN`.
- [ ] Only `SAFE` can serve a cache candidate or include selected-candidate
  identity and similarity.
- [ ] Unit tests cover all required candidate decisions and reason taxonomy.
- [ ] Known incompatibilities are `UNSAFE`; incomplete evidence and dependency
  failures are `UNCERTAIN`.
- [ ] Similarity below threshold is `UNSAFE` with no separate borderline band.
- [ ] Expired, dynamically disallowed, missing-TTL, and invalid-TTL entries
  cannot be served.
- [ ] Freshness and cache-control outcomes are available for considered
  candidates without exposing raw prompts or answers.
- [ ] Candidate traces identify the evidence or rule that caused each
  candidate decision.
- [ ] Candidate order is deterministic and first-safe selection is tested.
- [ ] Aggregate `UNCERTAIN` is preserved when no candidate is safe and any
  candidate lacks sufficient evidence.
- [ ] Exact, semantic, post-generation, and duplicate-write paths share the
  same Strategy C safety boundary.
- [ ] Repository, embedding, validator, timeout, and serialization failures
  remain failure-closed.
- [ ] Trace count, metadata, and combined serialized payload remain bounded.
- [ ] API, logs, and reports preserve the frozen serialization boundary.
- [ ] Operational traces contain no raw query, answer, prompt, credential, or
  provider-secret fields.
- [ ] Deterministic fake-provider replay reproduces the same decisions and
  trace order.
- [ ] Runtime observed decisions remain separate from Workstream 2 expected
  compatibility, correctness, and preference labels.
- [ ] Targeted regression tests pass.
- [ ] The full test suite passes, or unavailable checks and their consequences
  are explicitly documented.
- [ ] Completion evidence is linked from the Phase 2 parent plan.

## Completion evidence

Before marking this workstream complete, add a short evidence record to this
file or a linked artifact containing:

- [ ] implementation files and contract versions;
- [ ] decision matrix and reason taxonomy coverage;
- [ ] exact and semantic candidate counts exercised;
- [ ] `SAFE`, `UNSAFE`, and `UNCERTAIN` counts;
- [ ] freshness and cache-control outcome counts;
- [ ] failure-path and failure-closed test results;
- [ ] trace-bound and redaction test results;
- [ ] deterministic replay command and result;
- [ ] targeted test command and result;
- [ ] full-suite result and skipped dependencies;
- [ ] benchmark dataset/split identity used for replay;
- [ ] known limitations and their effect on Phase 2 conclusions.

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

- [ ] Publish the tested safety and trace contract versions.
- [ ] Publish the targeted and full-suite verification commands.
- [ ] Publish the decision matrix and reason/freshness coverage summary.
- [ ] Publish the bounded trace serialization and redaction behavior.
- [ ] Confirm that only `SAFE` is reusable.
- [ ] Confirm that `UNSAFE` and `UNCERTAIN` remain separately reportable.
- [ ] Confirm that observed runtime decisions are separate from benchmark
  labels.
- [ ] Document unsupported PostgreSQL/provider/concurrency checks for the
  workstreams that own them.
- [ ] Link the completion evidence from
  [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).

## Execution sequence

1. [x] Audit all decision producers, consumers, and current tests.
2. [ ] Freeze the candidate decision matrix and test fixtures.
3. [ ] Complete pure evaluator unit coverage.
4. [ ] Make freshness evidence explicit without changing the frozen vocabulary.
5. [ ] Add deterministic aggregate and ordering tests.
6. [ ] Verify exact, semantic, post-generation, and duplicate-write paths.
7. [ ] Verify dependency failures and serialization failures are
  failure-closed.
8. [ ] Run boundary, redaction, and deterministic replay tests.
9. [ ] Replay the development benchmark without changing reviewed labels.
10. [ ] Run targeted tests and the full suite.
11. [ ] Record evidence, limitations, and downstream handoff.

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
