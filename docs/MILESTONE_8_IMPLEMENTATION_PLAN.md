# Milestone 8 Implementation Plan — Compatibility-Aware Safety

## Goal

Extend SSCRE from embedding-only retrieval (Strategy B) to a conservative,
compatibility-aware safety engine (Strategy C):

```text
POST /v1/query
    ↓
normalize and exact lookup
    ↓
embed query and retrieve top-K candidates
    ↓
extract compatibility metadata
    ↓
evaluate similarity, intent, constraints, entities, format, and freshness
    ↓
SAFE candidate → reuse
UNSAFE or UNCERTAIN → generate a new answer
    ↓
record decision traces and evaluation metrics
```

This milestone implements the first rule-based compatibility validator and
measures whether it reduces embedding-only false positives. It does not
implement answer deduplication, storage caps, LRU eviction, or the complete
TTL lifecycle; those remain Milestone 9 work.

## Learning objectives

- [ ] Safe cache reuse versus semantic similarity
- [ ] `SAFE`, `UNSAFE`, and `UNCERTAIN` decision semantics
- [ ] Rule-based intent and constraint extraction
- [ ] Entity and output-format compatibility
- [ ] Temporal freshness classification
- [ ] Conservative abstention and failure-closed behavior
- [ ] Candidate-level decision traces
- [ ] False-positive, abstention, precision, recall, and coverage analysis
- [ ] Development decisions versus held-out evaluation
- [ ] Explainable safety decisions without an additional LLM call

## Implementation steps

### 1. Define the safety decision contract

- [x] Define `SAFE` as permission to serve the selected cached answer.
- [x] Define `UNSAFE` as evidence that the candidate is incompatible and must
  not be served.
- [x] Define `UNCERTAIN` as insufficient evidence; generate instead of serving.
- [x] Define the result model for a selected candidate, reason, strategy,
  similarity, and candidate traces.
- [x] Define deterministic precedence when candidates have mixed outcomes:
  return the first compatible `SAFE` candidate in similarity order; otherwise
  generate.
- [x] Ensure no infrastructure failure can produce a `SAFE` result.
- [x] Document that Strategy B similarity is a retrieval signal, not a safety
  decision.

### 2. Define query and cache metadata

- [x] Add a compact metadata model shared by the new query and cache entries.
- [x] Represent intent, domain, entities, explicit constraints,
  temporal class, and output format.
- [x] Bound the number and size of extracted entities and constraints.
- [x] Preserve unknown values instead of guessing missing metadata.
- [x] Keep metadata extraction deterministic and free of additional LLM calls.
- [x] Define how metadata is serialized for cache entries and evaluation
  traces.
- [x] Preserve existing embedding model and dimension compatibility checks.

### 3. Extract intent and output format

- [x] Classify the primary intent with explicit rule precedence, including
  explain, code, compare, factual, summarize, and unknown.
- [x] Detect requested output formats such as prose, code, list, table, and
  JSON.
- [x] Treat conflicting or absent format signals as unknown or uncertain.
- [x] Add examples for imperative, interrogative, and short-form queries.
- [x] Test that formatting requirements are not discarded during normalization.
- [ ] Record the matched rule or reason without storing unnecessary raw data.

### 4. Extract constraints, entities, and domain

- [x] Detect explicit programming-language constraints such as Python, Java,
  JavaScript, SQL, and language-neutral requests.
- [x] Detect other reusable constraints such as audience, version, platform,
  library, region, quantity, and requested scope where supported.
- [x] Normalize equivalent constraint spellings before comparison.
- [x] Extract bounded entities and compare them conservatively.
- [x] Classify the initial domain using rules, with `unknown` as the fallback.
- [x] Distinguish an explicit mismatch from an unstated requirement.
- [x] Define whether missing metadata produces `UNCERTAIN` rather than `SAFE`.
- [x] Add unit tests for matching, conflicting, and ambiguous constraints.

### 5. Classify temporal freshness

- [x] Classify queries as `stable`, `semi_dynamic`, or `dynamic`.
- [x] Detect temporal terms such as now, today, current, latest, recent, and
  this year.
- [x] Detect temporal constraints in both the new query and cached metadata.
- [x] Treat dynamic requests as non-reusable by default in this milestone.
- [x] Treat incompatible temporal classes as `UNSAFE` or `UNCERTAIN` according
  to the documented policy.
- [x] Ensure exact matches do not bypass the freshness safety decision.
- [ ] Keep actual TTL expiration and eviction mechanics explicitly tracked for
  Milestone 9.

### 6. Implement the rule-based compatibility validator

- [x] Add a pure, unit-testable compatibility function for one candidate.
- [x] Reject candidates below the configured similarity threshold.
- [x] Reject explicit conflicts in language, platform, version, entity, intent,
  domain, or output format.
- [x] Reject dynamic queries when no valid freshness policy permits reuse.
- [x] Return `SAFE` only when required compatibility evidence agrees and the
  candidate meets the configured high-confidence threshold.
- [x] Return `UNCERTAIN` for missing or ambiguous evidence instead of guessing.
- [x] Return an inspectable reason code such as
  `constraint_mismatch`, `entity_mismatch`, `format_mismatch`,
  `temporal_mismatch`, or `insufficient_evidence`.
- [x] Keep the validator free of database and provider-specific code.

### 7. Integrate Strategy C into the request path

- [x] Preserve exact lookup as the first operation.
- [x] Apply the same compatibility and freshness checks to exact candidates.
- [x] Reuse the existing embedding top-K retrieval path.
- [x] Evaluate candidates in descending similarity order with Strategy C.
- [x] Serve only a candidate whose result is `SAFE`.
- [x] Generate on `UNSAFE`, `UNCERTAIN`, no candidates, validator errors, or
  missing metadata.
- [x] Preserve the existing single-model generation fallback.
- [x] Avoid inserting a generated response without valid metadata required by
  the active strategy.
- [x] Keep Strategy A, Strategy B, and semantic-disabled behavior selectable
  for comparison.
- [x] Return decision, strategy, selected candidate, and similarity metadata
  without exposing internal secrets or unnecessary answer data.

### 8. Record candidate decision traces

- [x] Record the candidate order, similarity, extracted compatibility signals,
  decision, and reason for every evaluated candidate.
- [x] Distinguish retrieval rejection from compatibility rejection.
- [x] Record whether the final outcome was cache reuse or generation.
- [x] Keep traces bounded so a large `top_k` cannot create unbounded responses or
  logs.
- [x] Add structured logging for `SAFE`, `UNSAFE`, `UNCERTAIN`, and generated
  outcomes.
- [x] Define a machine-readable trace schema stable across Strategy B and C.
- [x] Do not log API keys, full prompts when unnecessary, or hidden provider
  credentials.

### 9. Add compatibility-focused evaluation

- [x] Replay the development split with Strategies A, B, and C.
- [x] Keep correctness and compatibility labels separate in all calculations.
- [x] Measure hit rate, safe reuse coverage, precision, recall, FPR, and
  abstention rate.
- [x] Measure generated tokens, embedding tokens, estimated cost, and latency.
- [x] Break down decisions by intent, constraint, entity, format, domain, and
  temporal failure category.
- [x] Verify that Strategy C is compared with the same dataset, cache state,
  model, and threshold configuration as Strategy B.
- [x] Select any rule or threshold configuration using development data only.
- [x] Run the selected configuration on held-out data without using held-out
  labels for tuning.
- [x] Save machine-readable reports containing strategy, configuration,
  dataset version, and software/worktree metadata.

### 10. Build the failure gallery and document limitations

- [x] Save representative embedding-only false positives that Strategy C
  catches.
- [x] Save Strategy C false positives, false negatives, and unnecessary
  abstentions when found.
- [x] Include new query, cached query, similarity, predicted decision,
  expected label, reason, and failure category.
- [x] Add examples for language, entity, intent, format, temporal, and unknown
  metadata failures.
- [x] Document that rule-based extraction cannot infer unstated user intent.
- [x] Document that `UNCERTAIN` is an intentional safe fallback, not a failed
  request.
- [x] Document the boundary between compatibility safety in this milestone and
  TTL, deduplication, and storage controls in Milestone 9.
- [x] Update request-flow, system-design, and learning-guide documents only
  after implementation and evaluation evidence exist.

## Verification checklist

- [x] `SAFE`, `UNSAFE`, and `UNCERTAIN` have documented, tested semantics
  (`tests/test_safety.py`).
- [x] Metadata extraction is deterministic and bounded.
- [x] Matching constraints can produce `SAFE` when similarity and freshness
  requirements are satisfied.
- [x] Explicit language, entity, intent, format, and temporal conflicts are
  rejected.
- [x] Missing or ambiguous evidence produces `UNCERTAIN`, not a cache hit.
- [x] Dynamic queries are not served without an explicit valid policy.
- [x] Exact hits cannot bypass compatibility and freshness checks.
- [ ] Strategy C never serves a candidate after an embedding, repository, or
  validator failure.
- [x] Candidate traces contain the selected candidate or a clear generation
  reason.
- [x] Strategy B remains available as an embedding-only comparison baseline.
- [x] Development evaluation produces machine-readable Strategy B and C
  reports.
- [x] Held-out evaluation uses configuration selected independently of held-out
  labels.
- [x] The failure gallery includes reviewed examples and failure categories.
- [x] Existing exact-cache, semantic retrieval, and no-cache tests still pass.
- [x] Unit tests and available integration tests pass
  (`python -m pytest -q`: 127 passed, 8 PostgreSQL integration tests skipped
  because `SSCRE_DATABASE_URL` was unavailable).
- [x] No linter errors are reported by IDE diagnostics; no standalone linter is
  configured.

## Completion criteria

Milestone 8 is complete when SSCRE extracts bounded compatibility metadata,
evaluates retrieved candidates with a deterministic rule-based Strategy C, and
serves cached answers only for `SAFE` decisions. `UNSAFE` and `UNCERTAIN`
results must fall back to generation, with candidate-level traces explaining
why. Development and held-out reports must quantify whether Strategy C lowers
embedding-only false positives while preserving useful reuse, and must include
the cost, token, latency, coverage, and abstention trade-offs.
