# Workstream 3 — Step 1 audit record

Audit date: 2026-10-07  
Parent plan: [WORKSTREAM_3_IMPLEMENTATION_PLAN.md](./WORKSTREAM_3_IMPLEMENTATION_PLAN.md)  
Frozen test matrix: [`tests/fixtures/workstream3_decision_matrix.py`](../../tests/fixtures/workstream3_decision_matrix.py)

Contract versions (unchanged):

| Artifact | Version |
|---|---|
| Safety evaluation | `1.0.0` (`SAFETY_EVALUATION_CONTRACT_VERSION`) |
| Candidate trace | `1.0.0` (`CANDIDATE_TRACE_CONTRACT_VERSION`) |
| Serialization boundary | `1.0.0` (`BOUNDARY_SERIALIZATION_VERSION`) |

Default runtime semantic strategy is **C** (compatibility contract path). Strategy **B**
remains an opt-in retrieval-only experiment baseline.

## Decision producers and consumers

| Module | Role |
|---|---|
| `src/sscre/compatibility.py` | Pure producer: `evaluate_candidate()` → one `CandidateTrace` per candidate. |
| `src/sscre/safety.py` | Types, taxonomy validation, `resolve_candidate_traces()`, trace caps, `SafetyResult` invariants. |
| `src/sscre/cache_controls.py` | Freshness/TTL eligibility via `evaluate_cache_control()`; not a safety decision. |
| `src/sscre/app.py` | Orchestration: exact lookup, semantic search, freshness filter, Strategy B/C branches, generation fallback, logging, `QueryResponse`. |
| `src/sscre/serialization.py` | API/log/report boundary: `boundary_candidate_traces()`, `build_cache_decision_log()`, redaction. |
| `src/sscre/baseline.py` | Evaluation replay: cache control, then `evaluate_candidate_boundary()` and `resolve_candidate_traces()` for compatibility baseline reports. |
| `src/sscre/query.py` | `QueryResponse` Pydantic validation of decision literals and SAFE-only selection fields. |

Production cache reuse under Strategy C flows:

```text
preprocess_query → metadata
    → exact get_by_query_hash
        → cache_control (freshness gate)
        → [C] evaluate_exact_entry → trace_with_context
        → SAFE? cached_response : continue
    → embed + search_by_embedding
        → filter cache_entry_is_reusable (freshness gate)
        → [C] evaluate each candidate → resolve_candidate_traces
        → SAFE? semantic_cached_response : continue
    → generation_guard + recheck exact (same C path when enabled)
    → generate
    → resolve_candidate_traces(decision_traces) for response decision/reason
```

## Contract paths vs Strategy B

| Path | Contract? | Serves from similarity alone? | Notes |
|---|---|---|---|
| Strategy C exact hit | yes | no | Runs `evaluate_candidate` on exact entry when reusable. |
| Strategy C semantic multi-candidate | yes | no | First SAFE trace wins via `resolve_candidate_traces`. |
| Strategy A exact hit (`semantic_strategy != "C"`) | no | n/a | Skips compatibility; `SAFE` / `exact_query_hash_match`. |
| Strategy B semantic hit | no | yes | `similarity_threshold_met`, `stage=retrieval`. |
| Generated fallback | yes (decision only) | n/a | Never serves cache; preserves prior traces when present. |
| Generation failed (502) | yes (log) | n/a | Log `UNCERTAIN` / `generation_failed`; no cache hit. |
| Repository unavailable (503) | yes (failure-closed) | n/a | No reuse; HTTP error. |

## Retrieved-and-rejected vs filtered-before-evaluation

| Disposition | Meaning | Where it happens | Trace expectation (current) |
|---|---|---|---|
| **evaluated** | Candidate passed freshness gate and received `evaluate_candidate()` (and context enrichment). | Strategy C exact/semantic paths, duplicate-write recheck. | One or more full `CandidateTrace` rows in response/logs when traces collected. |
| **filtered_before_evaluation** | Entry blocked by `evaluate_cache_control` before compatibility runs. | Expired, missing/invalid TTL, dynamic policy disabled. | A `stage=retrieval` cache-control trace. Search does not drop these rows before tracing. |
| **not_retrieved** | Lookup/search failed or never ran; empty candidate set. | Repo errors, no semantic hits, embedding failure before search. | `candidate_traces: null` or empty; `no candidates were retrieved` when applicable. |

Ineligible retrieved candidates are `stage=retrieval` cache-control traces.
The public vocabulary stays `SAFE`, `UNSAFE`, and `UNCERTAIN`.

## Frozen test matrix

- **Pure evaluator rows:** 16 conditions → expected decision and reason (step 2 unit tests).
- **Request path rows:** 18 orchestration scenarios (7 `SAFE`, 5 `UNSAFE`,
  5 `UNCERTAIN`, 1 error) → strategy, source, decision, reason pattern, trace
  count floor, disposition, planned step, optional existing test name.

Matrix guard tests: `tests/test_workstream3_decision_matrix.py`.

## Tests asserting cache reuse without explicit `SAFE`

### Needs explicit response `decision == "SAFE"` (or equivalent) when tightened

| Test | File | Notes |
|---|---|---|
| `test_first_query_generates_and_repeated_query_uses_cache` | `tests/test_exact_cache.py` | Default Strategy C; only checks `source == "cache"`. |
| `test_semantic_candidate_is_reused_after_exact_miss` | `tests/test_exact_cache.py` | Strategy B experiment path. |
| `test_exact_hit_bypasses_embedding_lookup` | `tests/test_exact_cache.py` | Strategy **B** exact skip (not Strategy C). |
| `test_cache_hit_decision_log_is_structured` | `tests/test_metrics.py` | Log row requires `decision == "SAFE"`; HTTP body not checked. |
| `test_api_reads_persisted_entry_across_app_instances` | `tests/test_postgres_integration.py` | Skipped when `SSCRE_DATABASE_URL` unset. |
| `test_concurrent_same_query_generates_once_and_reuses_safely` | `tests/test_failure_paths.py` | Cache hit leg has no `decision` assertion. |

### Already asserts `SAFE` on reuse (listed for grep completeness only)

| Test | File |
|---|---|
| `test_strategy_c_reuses_only_a_compatible_semantic_candidate` | `tests/test_exact_cache.py` |
| `test_safe_exact_hit_trace_is_bounded_without_secrets` | `tests/test_workstream1_contract.py` |

No change to those tests in step 1; this inventory drives step 5–7 hardening.

## Intentional compatibility limitations (do not weaken tests to match)

| Limitation | Evidence | Planned step |
|---|---|---|
| Strategy B serves on similarity alone | `app.py` semantic_strategy `"B"` branch | Document only; not contract path (WS1 evidence). |
| Expired/dynamic-filtered candidates omit compatibility traces | `cache_entry_is_reusable` filter before evaluation | Step 3 freshness trace policy. |
| `evaluate_candidate()` does not set freshness/cache_control fields | Pure function in `compatibility.py` | Step 3 via `trace_with_context` in `app.py`. |
| `safety_validator_error` path not covered by dedicated integration test | `evaluate_exact_entry` except handler | Step 6. |
| Multi-candidate first-SAFE ordering not fully matrix-driven | Partial coverage in `test_safety.py` + Strategy C tests | Step 4. |
| Held-out benchmark not used for tuning during WS3 | Policy | Step 9 replay development only. |

## Known gaps → planned steps

| Gap | Step |
|---|---|
| Full pure-evaluator row coverage in tests | 2 |
| Freshness trace visibility for filtered candidates | 3 |
| Ordered multi-candidate aggregation suite | 4 |
| Exact/semantic/post-lock/duplicate parity | 5–7 |
| Dependency failure matrix | 6 |
| Serialization/redaction regression bundle | 8 |
| Development-split replay vs expected labels | 9 |
| Completion evidence block in plan/README | 10 |

## Verification (step 1 exit)

```bash
python -m pytest -q tests/test_workstream3_decision_matrix.py
python -m pytest -q tests/test_safety.py tests/test_compatibility.py
```

**2026-10-07:** `python -m pytest -q tests/test_workstream3_decision_matrix.py tests/test_safety.py tests/test_compatibility.py` → **40 passed**.

## Checklist (step 1 exit)

- [x] Decision producers and consumers inventoried (tables above).
- [x] Contract vs Strategy B paths documented.
- [x] Test matrix defined in `tests/fixtures/workstream3_decision_matrix.py`.
- [x] Retrieved vs filtered vs not-retrieved disposition documented.
- [x] Reuse tests without explicit SAFE listed.
- [x] Intentional limitations recorded with planned steps.
- [x] Evidence: this file + matrix module + matrix guard tests.

## Independent review (2026-10-07)

**Verdict:** Step 1 meets the plan checklist (inventory, contract vs B, matrix,
dispositions, limitations, evidence). Treat it as **complete with documented
follow-ups**, not as proof that runtime behavior is fully matrix-tested yet.

### Confirmed accurate

- Producer/consumer map matches `compatibility.py`, `safety.py`, `cache_controls.py`,
  `app.py`, `serialization.py`, `baseline.py`, and `query.py`.
- Strategy C flow diagram matches `app.py` (freshness gate → evaluate →
  `resolve_candidate_traces` → generate on non-`SAFE`).
- Step 2 adds matrix-driven coverage in `tests/test_workstream3_pure_evaluator.py`
  and `tests/fixtures/workstream3_evaluator_cases.py` (16 rows, precedence,
  boundary helper). Legacy overlap remains in `tests/test_compatibility.py`.
- Contract versions match module constants.
- Matrix guard tests pass together with safety/compatibility (40 tests, 2026-10-07).

### Issues found and corrected in this review

| Issue | Resolution |
|---|---|
| `rp_exact_pre_embed_c` cited `test_exact_hit_bypasses_embedding_lookup`, which uses `semantic_strategy="B"` (exact compatibility skip), not Strategy C | Matrix row updated: `existing_test=None` + gap note |
| `rp_semantic_c_uncertain_metadata` had `min_trace_count=0` but Strategy C emits one `candidate_metadata_missing` trace | Matrix `min_trace_count` set to **1** |
| Reuse-test table mixed tests that already assert `SAFE` with those that do not | Audit split into two subtables |

### Gaps still open (expected; not step 1 blockers)

| Gap | Detail |
|---|---|
| Plan asked for **selected candidate** expectations in the matrix | `RequestPathExpectation` has no `selected_candidate_query_hash` / similarity fields yet; add in step 5 or extend the dataclass |
| **Invalid TTL** request-path row | Covered in `tests/test_cache_controls.py` only; no HTTP matrix row |
| **Strategy B below-threshold** trace path | `test_semantic_candidate_below_threshold_generates_response`; not in `REQUEST_PATH_MATRIX` |
| **Cache write / repo timeout / serialization** failures | Listed in plan path list; matrix has partial coverage (`rp_repo_unavailable`, `rp_embedding_malformed`, `rp_generation_failed`) |
| **`metadata.py`** | Query metadata producer omitted from inventory table (minor) |
| Matrix rows are not yet wired into parametrized integration tests | By design until steps 2–7 |

### Step 1 checklist vs parent plan

| Parent requirement | Status |
|---|---|
| Map all listed path families | Partial in matrix; audit § Gaps documents omissions |
| Matrix includes decision, reason, source, trace count, generation | Yes; **selected candidate fields** missing |
| Evidence recorded | Yes |
