# Workstream 3 evidence

> **Historical scope note:** Verification below was recorded on the
> **32-pair** `reviewed-query-pairs-1.1` artifact (2026-10-07). Strategy C
> behavior at **615-pair** scale is covered by later workstreams (WS5 replay,
> WS3 tests in the full suite) and remediation lineage
> ([`PHASE_2_REMEDIATION_EVIDENCE.md`](./PHASE_2_REMEDIATION_EVIDENCE.md)).
> Treat this file as the Workstream 3 implementation handoff, not the current
> benchmark identity record.

Decision-depth handoff for Phase 2 Workstreams 4–9. This record is the
working-tree result on 2026-10-07. It is not a real-provider measurement and
not a held-out operating-point claim.

## Contracts and state

- [x] Safety evaluation `1.0.0`, candidate trace `1.0.0`, serialization
  boundary `1.0.0`, evaluation labels `1.0.0`.
- [x] Dataset `reviewed-query-pairs-1.1` (schema 1.1, annotation guide 1.0.0).
  Development split sha256
  `f50d16a2c2dbcb133cbe6d765f6d088bc690414e0212a8a61f872c024e743483`
  (21 pairs). Held-out split is 11 pairs. Source dataset is 32 pairs.
- [x] HEAD `c1d15bac1e00b8d001c9b994c24d48c01dfa4a7f`, software `0.1.0`.
  `git_worktree_dirty` is true; this evidence describes the uncommitted
  worktree, not that commit alone.
- [x] Python 3.14.5, pytest 9.1.1, fastapi 0.142.2, pydantic 2.13.4,
  httpx 0.28.1, psycopg 3.3.6. Providers used: `FakeEmbeddingClient`,
  `MockLLMClient`, in-memory cache. No real provider. No PostgreSQL.

Only `SAFE` is reusable. `UNSAFE` and `UNCERTAIN` stay separate and both
refuse cache reuse.

## Verification (2026-10-07)

- [x] Targeted contract suite:

```bash
python -m pytest -q tests/test_safety.py tests/test_compatibility.py \
  tests/test_trace_contract.py tests/test_serialization_boundary.py \
  tests/test_workstream1_contract.py
```

60 passed.

- [x] Full suite:

```bash
python -m pytest -q
```

412 passed, 13 skipped. Every skip is
`tests/test_postgres_integration.py` because `SSCRE_DATABASE_URL` is unset.

- [x] Benchmark validation:

```bash
python -m sscre.benchmark_validate --benchmark-dir benchmarks
```

Passed. Leakage status `passed`. Development 21, held-out 11, source 32.

- [x] Development replay (fake providers, threshold selected on development):

```bash
python -m sscre.evaluate \
  --benchmark benchmarks/development.jsonl \
  --config experiments/evaluation_config.json \
  --baseline compatibility-cache \
  --split development \
  --output artifacts/evaluation/workstream3-development.json
```

Exit 0. Config `evaluation-config-1.0`. Selected threshold `0.95`
(`threshold_selection_split=development`). Saved report has no `query_a` or
`query_b` text.

## Coverage

- [x] Pure evaluator matrix: 16 rows (8 `UNSAFE`, 7 `UNCERTAIN`, 1 `SAFE`) in
  `tests/fixtures/workstream3_decision_matrix.py`.
- [x] Request-path matrix: 18 rows (7 `SAFE`, 5 `UNSAFE`, 5 `UNCERTAIN`,
  1 error path). Freshness gates in that matrix: `fresh` 11, `expired` 2,
  `dynamic_entries_disabled` 1, `missing_expiration` 1.
- [x] Invalid expiration is covered by
  `test_invalid_ttl_emits_invalid_expiration_trace`, outside the matrix
  freshness-gate counts above.
- [x] Development replay, both directions (`decision_counts`, 42 evaluations):
  `SAFE` 1, `UNSAFE` 38, `UNCERTAIN` 3. Empty retrieval counts as `UNSAFE`.
- [x] Development replay, `b_to_a` pair records (21): observed `UNSAFE` 17,
  `UNCERTAIN` 3, `SAFE` 1. Agreement 12 match, 9 mismatch
  (`evaluator_behavior` 6, `metadata_insufficiency` 3).
- [x] Pair-record trace reasons: `similarity_below_threshold` 90,
  `missing_domain_evidence` 2, `missing_intent_evidence` 1,
  `compatible_metadata` 1, `cache_control_dynamic_disabled` 1. Aggregate
  reasons: `all candidates were incompatible` 17,
  `no candidate had sufficient compatibility evidence` 3,
  `compatible_metadata` 1.
- [x] Replay trace `cache_control_outcome` counts: `fresh` 94,
  `dynamic_entries_disabled` 1.
- [x] Correctness and preference on the development split remain
  `not_collected`. A `SAFE` decision does not fill a correctness label.

## Failure-closed examples

Passed in the full suite:

- [x] Embedding failure after an exact miss:
  `test_embedding_failure_after_exact_miss_generates_without_cache`.
- [x] Malformed embedding shape, dimension, and non-finite values:
  `test_invalid_embedding_results_do_not_create_cache_hits`.
- [x] Semantic repository search failure:
  `test_semantic_repository_search_failure_fails_closed`.
- [x] Repository timeout on lookup and semantic search:
  `test_repository_timeout_on_lookup_returns_503`,
  `test_repository_timeout_on_semantic_search_does_not_serve_cache`.
- [x] Evaluator exception:
  `test_evaluator_exception_maps_to_safety_validator_error`.
- [x] Boundary serialization failure returns HTTP 500 and does not serve the
  cached answer: `test_oversized_trace_metadata_prevents_cache_reuse`.
- [x] Generation failure after a non-safe candidate:
  `test_generation_failure_after_unsafe_candidate_is_non_reusable`.
- [x] Cache write failure returns the generated answer without a cache hit:
  `test_cache_write_failure_returns_generated_answer_without_false_hit`.

## Handoff

- [x] Workstream 4: use the frozen `SAFE` / `UNSAFE` / `UNCERTAIN` boundary.
  This record has no real-provider run.
- [x] Workstream 5: use `observed_pair_records` and `decision_counts` in
  `artifacts/evaluation/workstream3-development.json`. Do not treat the
  development-selected threshold `0.95` as a held-out operating point.
  Confidence intervals are not in this artifact.
- [x] Workstream 6: freshness outcomes are on request-path traces and on
  compatibility-cache replay traces (`fresh`, `expired`,
  `dynamic_entries_disabled`, `missing_expiration`, `invalid_expiration`).
- [x] Workstream 7: failure categories and redacted examples are in the
  compatibility report (`failure_examples`, `disagreement_class_counts`).
- [x] Workstream 8: in-process duplicate and concurrent tests passed in this
  WS3 record. Later bounded PostgreSQL evidence is
  [WORKSTREAM_8_EVIDENCE.md](./WORKSTREAM_8_EVIDENCE.md); do not read WS3
  in-memory concurrency as that package.
- [x] Workstream 9: API, log, and report JSON stay on serialization boundary
  `1.0.0`. Operational traces omit raw queries, answers, and secrets.

## Known limits

- [ ] PostgreSQL integration tests were not run (`SSCRE_DATABASE_URL` unset).
- [ ] Multi-process and live restart behavior are not claimed in this WS3
  record. Workstream 8 later measured two-process duplicate generation and
  simulated failure-closed paths
  ([WORKSTREAM_8_EVIDENCE.md](./WORKSTREAM_8_EVIDENCE.md)); live restart
  remains skipped.
- [ ] No real-provider measurement. Workstream 4 owns that run.
- [ ] The reviewed benchmark is the 32-pair working artifact, not 500 pairs.
- [ ] Strategy B still serves from similarity alone. It is opt-in. Strategy C
  is the contract path.
- [ ] After an expired exact entry is replaced, later waiters on the same
  in-process lock may reuse the new fresh answer. The expired answer is not
  served (`test_concurrent_exact_expired_entries_never_served`).
- [ ] Benchmark replay disagreement classes do not include `freshness_policy`
  or `retrieval_miss` on this split. Those classes are implemented and unit
  tested; this dataset's mismatches were evaluator behavior and metadata
  insufficiency.
