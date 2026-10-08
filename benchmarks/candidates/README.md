# Benchmark candidates

Staged pairs are reviewed here before merge into `reviewed_query_pairs.jsonl`.

Workflow:

1. Author rows in JSONL using schema `1.1`.
2. Set `source_group` to `{family}:{scenario}` from
   [source_inventory.json](../source_inventory.json) (external imports must match
   [BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md](../../docs/phase-2/BENCHMARK_500_EXTERNAL_SOURCE_POLICY.md)).
3. Run redaction and schema validation via `sscre.benchmark_build`.
4. Assign splits (scale-up): [tools/assign_phase4_cacheeval_splits.py](./tools/assign_phase4_cacheeval_splits.py).
5. Merge with `python -m sscre.benchmark_build merge --candidates ... --rebuild-splits`.
6. Bump `dataset_version` when labels change (e.g. `reviewed-query-pairs-2.0`).
7. Rebuild and freeze:

```bash
python -m sscre.benchmark_build --benchmark-dir benchmarks merge --candidates <path> --rebuild-splits
python -m sscre.benchmark_validate --benchmark-dir benchmarks
```

Phase 2 completion requires **500+** reviewed pairs; use
`benchmark_validate --phase2` after the scale-up.

Scale-up plan (CacheEval import, review batches, splits):
[BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md](../../docs/phase-2/BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md).

CacheEval staging (Phase 1 filter): [upstream/README.md](./upstream/README.md).

Draft import batch (Phase 2, **not merged**): `cacheeval_batch_01.jsonl` (575 rows,
`pair-0033`–`pair-0607`, `review_status: draft`). Convert with
[candidates/tools/convert_cacheeval_candidates.py](./tools/convert_cacheeval_candidates.py).

Phase 3 reviewed overlay: `cacheeval_batch_01_reviewed.jsonl` (583 rows, all
`final`). Apply with [apply_phase3_cacheeval_review.py](./tools/apply_phase3_cacheeval_review.py)
(`--batch 1` … `--batch 12`; use `--force` to re-apply overrides on finals).
Legacy wrapper: [apply_phase3_batch01_review.py](./tools/apply_phase3_batch01_review.py).

`expansion_v1.jsonl` adds Phase 2 coverage gaps (temporal, domain, ambiguity,
stale, uncertain) to the working baseline.
