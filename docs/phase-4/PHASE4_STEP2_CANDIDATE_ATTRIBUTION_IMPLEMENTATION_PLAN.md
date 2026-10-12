# Phase 4 Step 2 — Candidate Attribution Implementation Plan

## Goal

Execute parent Step 2 of
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md):
make A/B/C replay metrics describe the cache candidate actually served, not
the current request record's `reusable` flag.

This step authorizes evaluation-attribution code, exact-cache FPR fields, and
focused regression tests. It does not authorize a protocol/config reset, a
real embedding provider, development or held-out evaluation runs, artifact
regeneration, or roadmap close.

**Status:** `closed (Step 2 attribution)` — implementation in `src/` on
2026-10-12; this child plan is the matching authoring artifact.  
**Evidence:**
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md)
§ Step 2.  
**Parent:**
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md)
§ 10 Step 2.  
**Card:** `P4-SEMVALID` (parent § 5).

## Learning objectives

- [ ] Distinguish request-record `reusable` from a served-candidate / current-query
      reviewed edge.
- [ ] Explain why `unlabeled_candidate_reuse` cannot enter the headline FPR
      denominator.
- [ ] Keep compatibility/reuse permission separate from correctness and
      preference labels.

## Prerequisites

- [x] Parent plan exists with hypothesis, pass/fail, and stopping rules
      (`P4-SEMVALID`).
- [x] Step 1 audit is closed:
      [`PHASE4_STEP1_EVALUATION_AUDIT_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP1_EVALUATION_AUDIT_IMPLEMENTATION_PLAN.md).
- [x] Every path in this plan's **Parent**, **contracts**, and **Verification**
      blocks exists in the current checkout, or is recorded under
      **Open baseline gaps**.
- [x] Step 1 evidence records pre-attribution scoring in
      [`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md)
      (historical snapshot; do not use it alone to describe today's
      `baseline.py`).

## Gates and stopping rules

**Gate A — authoring.** Closed when this plan exists, lists the implementation
corpus below, and every linked path exists or is an explicit gap. Authoring
is not a new semantic claim.

**Gate B — implementation protocol.** Mirror parent § 5 (`P4-SEMVALID`) rules
that apply to attribution:

- Score the served candidate/current-query relation, not the request record
  alone.
- A served candidate with no reviewed compatibility relation is
  `unlabeled_candidate_reuse`; it is not silently safe or unsafe and cannot
  contribute to a passing headline FPR.
- Do not change the meaning of compatibility, correctness, or preference
  labels.
- Do not freeze a new protocol/config identity (parent Step 3).
- Do not add an embedding dependency or real-provider path (parent Step 4).
- Do not run development threshold selection or held-out evaluation (parent
  Steps 5–7).
- Do not regenerate Phase 3 artifacts or update `docs/SSCRE_PLAN.md` §§ 20 and
  24 as if the C-versus-A gate had been scored.
- If attribution cannot be made correct without new reviewed candidate/query
  labels, stop and create a label-expansion plan rather than inventing labels.
  Recording `unlabeled_candidate_reuse` is the authorized stop, not a silent
  default to the request record.
- An unrun later step is `deferred`, not `pass` or `fail`.

**Gate C — Step 2 close.** Close only when focused attribution tests pass, a
fixture report shows the metric following the served candidate, fail-closed
Strategy C tests still pass, and parent § 10 Step 2 boxes match that evidence.

## Implementation corpus

Feature-card minimum (`P4-SEMVALID` / parent §§ 5 and 10 Step 2):

- Parent Step 2 purpose, checkboxes, and exit evidence.
- [`../../src/sscre/evaluation_attribution.py`](../../src/sscre/evaluation_attribution.py)
- [`../../src/sscre/baseline.py`](../../src/sscre/baseline.py)
- [`../../src/sscre/evaluation_statistics.py`](../../src/sscre/evaluation_statistics.py)
- [`../../src/sscre/evaluation_labels.py`](../../src/sscre/evaluation_labels.py)
- [`../../tests/test_evaluation_attribution.py`](../../tests/test_evaluation_attribution.py)

Extended parent scope (parent §§ 4, 7, 9, 11, and 14):

- [`../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
- [`../phase-2/SAFETY_EVALUATION_CONTRACT_v1.md`](../phase-2/SAFETY_EVALUATION_CONTRACT_v1.md)
- [`../../src/sscre/compatibility.py`](../../src/sscre/compatibility.py)
- [`../../src/sscre/query.py`](../../src/sscre/query.py)
- [`../../tests/test_evaluation_statistics.py`](../../tests/test_evaluation_statistics.py)
- [`../../tests/test_baseline_request_samples.py`](../../tests/test_baseline_request_samples.py)
- [`../../tests/test_benchmark.py`](../../tests/test_benchmark.py)
- [`../../tests/test_compatibility.py`](../../tests/test_compatibility.py)
- [`../../tests/test_workstream3_pure_evaluator.py`](../../tests/test_workstream3_pure_evaluator.py)
- [`../../tests/test_evaluation_labels.py`](../../tests/test_evaluation_labels.py)
- Step 1 historical code snapshot in
  [`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md)

## Open baseline gaps

These remain open after Step 2. Do not pre-check them as closed.

- [x] Decide how context-stripped identical-text pairs are represented in the
      frozen protocol (`context_required` exclusion from primary headline
      population — parent Step 3 / config
      `experiments/semantic-validity-evaluation-config-v1.json`).
- [x] Replace zero-denominator FPR in headline reports with
      `false_positive_rate_unavailable_reason` (Step 5; constraints fail-closed
      via `math.inf` when labeled FPR is unknown).
- [ ] Obtain a genuinely fresh held-out population and reviewed candidate/query
      relations for the C-versus-A gate (parent Steps 3 and 6). Replay of
      `unlabeled_candidate_reuse` is implemented; that is not data sufficiency.
- [ ] Select a real fixed-dimension embedding model (parent Step 4). Keep
      `FakeEmbeddingClient` for attribution fixtures.

## Provenance record fields

One row per field. Put long definitions in the notes below, not in cells.

| Field | Required on attributed `b_to_a` served reuse |
| --- | --- |
| `candidate_query_hash` | yes |
| `candidate_normalized_query` | yes |
| `candidate_answer_hash` | yes |
| `source_pair_id` | yes, or `null` when insert source is unknown |
| `source_direction` | yes, or `null` when insert source is unknown |
| `current_query_hash` | yes |
| `current_normalized_query` | yes |

`ServedCandidateProvenance` is attached on scored `b_to_a` served reuse.
`a_to_b` cache hits do not emit reuse outcomes (false positive / safe reuse /
unlabeled all stay 0). Headline FPR uses labeled `b_to_a` reuse
(`safe_reuse_hits + unsafe_reuse_hits`) and excludes unlabeled events.
Ground truth is the reviewed directed pair edge and that pair's `reusable`
flag, not Strategy C's runtime decision and not `compatibility_label` alone.

## Implementation steps

### Step 1 — Define provenance and attribution API

- [x] Add
      [`../../src/sscre/evaluation_attribution.py`](../../src/sscre/evaluation_attribution.py)
      with `ServedCandidateProvenance`, `AttributedReuseOutcome`,
      `DirectedPairReuseIndex`, `attribute_served_reuse_outcome`, and
      `labeled_false_positive_rate`.
- [x] Index reviewed directed edges as `(hash(normalize(query_a)),
      hash(normalize(query_b)))`.
- [x] Treat duplicate conflicting edges as unlabeled (`lookup` returns
      `None`; do not pick an arbitrary record).
- [x] On `b_to_a` served reuse with a reviewed edge, set `safe_reuse_hit` or
      `false_positive` from `grounding.reusable`.
- [x] On `b_to_a` served reuse without a reviewed edge, set
      `unlabeled_candidate_reuse=1` and leave safe/unsafe at 0.

### Step 2 — Update replay bookkeeping

- [x] In [`../../src/sscre/baseline.py`](../../src/sscre/baseline.py), record
      insert source `(pair_id, direction)` per candidate query hash.
- [x] On exact, embedding, and compatibility cache hits, attribute reuse from
      the served entry's normalized query and answer hash, not
      `record.reusable`.
- [x] Attach `served_candidate_provenance` on request samples when attribution
      returns provenance (`b_to_a` served reuse only; `a_to_b` hits omit it).
- [x] Keep `FakeEmbeddingClient` as the B/C test provider; do not add a real
      model in this step.

### Step 3 — Exclude unlabeled events from headline FPR

- [x] Add `unlabeled_candidate_reuse` to
      `RequestObservationSample` in
      [`../../src/sscre/evaluation_statistics.py`](../../src/sscre/evaluation_statistics.py).
- [x] Compute sample-statistics `false_positive_rate` over labeled hits only.
- [x] Expose `false_positive_rate_among_all_hits` for comparison with frozen
      Phase 2/3 artifacts; do not use it as the new headline.
- [x] Treat a missing `unlabeled_candidate_reuse` field on legacy
      `request_samples` as `0` so frozen JSON can be re-summarized
      (`test_summarize_request_samples_without_unlabeled_field_defaults_to_zero`).

### Step 4 — Add exact-cache FPR and unsafe-reuse fields

- [x] Add `unsafe_reuse_hits`, `unlabeled_candidate_reuse_hits`, and
      `false_positive_rate` to `ExactCacheReport` without changing label
      contracts.
- [x] Set `false_positive_rate` with `labeled_false_positive_rate(unsafe,
      safe)` (labeled denominator).
- [x] Record the zero-labeled-hits `0.0` behavior as a Step 5 reporting gap,
      not as a silent pass.

### Step 5 — Preserve label separation

- [x] Do not fold correctness or preference into reuse outcomes.
- [x] Keep `build_evaluation_labels` / `build_label_sections` as the
      compatibility ≠ correctness ≠ preference boundary
      ([`../../src/sscre/evaluation_labels.py`](../../src/sscre/evaluation_labels.py),
      [`../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)).
- [x] Attribution uses the reviewed `reusable` flag on the grounded pair, not
      `compatibility_label` as a substitute correctness or preference signal.

### Step 6 — Add regression tests

Map each parent-required case to a test that exists in this checkout:

| Parent case | Test |
| --- | --- |
| Duplicate normalized queries | `test_directed_pair_index_flags_ambiguous_edges` |
| Context-stripped identical text marked non-reusable | `test_context_stripped_identical_text_uses_reviewed_non_reusable_edge` |
| Embedding false positive whose served candidate differs from the current pair | `test_embedding_false_positive_follows_served_candidate_not_request_label` |
| Served candidate vs request-record label | `test_attribute_scores_reviewed_edge_not_request_record` |
| Exact-cache FPR | `test_exact_cache_reports_false_positive_rate_on_labeled_reuse` |
| Unlabeled candidate reuse (no reviewed edge) | `test_attribute_marks_unlabeled_cross_pair_without_reviewed_edge` (cross-pair branch) |
| Directional `a_to_b` and `b_to_a` scoring | `test_a_to_b_direction_never_scores_reuse_outcomes` plus b_to_a tests above |

- [x] Add the tests in
      [`../../tests/test_evaluation_attribution.py`](../../tests/test_evaluation_attribution.py).
- [x] Keep existing request-sample binary-indicator coverage in
      [`../../tests/test_baseline_request_samples.py`](../../tests/test_baseline_request_samples.py)
      (`unlabeled_candidate_reuse` in `{0, 1}`).

### Step 7 — Verify fail-closed behavior

- [x] Do not weaken Strategy C fail-closed paths in
      [`../../src/sscre/compatibility.py`](../../src/sscre/compatibility.py).
- [x] Re-run fail-closed and Strategy C replay regressions (evidence § Step 2
      verification table):
      [`../../tests/test_compatibility.py`](../../tests/test_compatibility.py);
      [`../../tests/test_workstream3_pure_evaluator.py`](../../tests/test_workstream3_pure_evaluator.py);
      `tests/test_benchmark.py::test_compatibility_baseline_reports_safety_and_abstention_metrics`.
- [x] Record that unlabeled reuse is reported, not served as a headline-safe
      hit.

### Step 8 — Write evidence and close

- [x] Record implementation, fixture demonstration, FPR denominator notes,
      and verification counts in evidence § Step 2.
- [x] Label the Step 1 code-inspection section historical / pre-attribution.
- [x] Update parent § 10 Step 2, **Open baseline gaps**, and **Current
      baseline** so they describe attributed replay, not the Step 1 snapshot.
- [x] Sync parent § 12 rows satisfied at Step 2 close (attribution + label
      separation); leave FPR unavailable-reason row unchecked until Step 5.
- [x] Leave parent Steps 3–8 unchecked.

## Verification

Run from the repository root after confirming every path and option exists.
Record the exact command and result in evidence. An unrun check is
`deferred`, not `pass`.

Required focused tests:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_evaluation_attribution.py tests/test_evaluation_statistics.py::test_summarize_request_samples_without_unlabeled_field_defaults_to_zero
```

Fail-closed and label-separation regressions (must still pass; this step must
not change their meaning):

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_compatibility.py tests/test_workstream3_pure_evaluator.py tests/test_evaluation_labels.py tests/test_baseline_request_samples.py tests/test_benchmark.py
```

Full suite after attribution changes (environment permitting):

```powershell
$env:PYTHONPATH='src'
python -m pytest -q
```

Recorded in evidence § Step 2 (2026-10-12, re-verified 2026-10-12):

- [x] Focused attribution + legacy statistics: **8 passed** (7 in
      `test_evaluation_attribution.py`, 1 legacy-sample statistics test).
- [x] Fail-closed / label-separation bundle: **131 passed**.
- [x] Full suite: **775 passed**, 15 skipped, 21 deselected, 1 warning.

Parent §11 `python -m pytest -q` and §12 milestone verification rows remain
unchecked until Phase 4 close-out (Compose, `benchmark_validate`, roadmap).

Do not run held-out or development `python -m sscre.evaluate` in this step.
Do not treat `docker compose config` as a Step 2 close requirement.

## Acceptance criteria

### Goal / Exit — authoring gate

- [x] This plan exists at
      `docs/phase-4/PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md`.
- [x] The plan links `P4-SEMVALID` and parent § 10 Step 2.
- [x] The implementation corpus lists the card minimum and the broader parent
      scope.
- [x] Linked contract, source, and test paths exist, or are recorded under
      **Open baseline gaps**.

### Verification — implementation gate

- [x] `ServedCandidateProvenance` includes the required identity fields.
- [x] Exact, embedding, and compatibility replay score the served candidate.
- [x] Unlabeled candidate reuse is recorded and excluded from headline FPR.
- [x] Exact-cache reports expose FPR and unsafe-reuse fields using labeled
      `b_to_a` reuse counts (`labeled_false_positive_rate`; zero-hit `0.0`
      unavailable reason remains parent §12 / Step 5).
- [x] Compatibility, correctness, and preference labels remain separate.
- [x] Parent-required regression cases have tests in this checkout.
- [x] Fail-closed Strategy C tests still pass (131-test regression bundle in
      evidence § Step 2).
- [x] Evidence § Step 2 names the fixture that follows the served candidate
      (`test_embedding_false_positive_follows_served_candidate_not_request_label`).
- [x] Parent Step 2 boxes match that evidence; Steps 3–8 remain unchecked.
- [x] No protocol freeze, real-provider addition, held-out run, or
      `SSCRE_PLAN.md` § 20 / § 24 semantic-success claim was made in this step.

## Out of scope for this document

- Parent Steps 3–8 (protocol freeze, real embeddings, evaluation runs, gate
  scoring, roadmap close).
- Regenerating or deleting Phase 3 artifacts.
- Changing `docker-compose.yml` defaults.
- Adding an embedding dependency or model.
- Human correctness labeling or new reviewed candidate/query labels.
- Re-running the Step 5 development artifact after rectification (unchanged
  headline numbers; constraint semantics tightened in code).
- Committing or pushing without explicit user approval.
