# Benchmark candidates

Staged pairs are reviewed here before merge into `reviewed_query_pairs.jsonl`.

Workflow:

1. Author rows in JSONL using schema `1.1`.
2. Set `source_group` to `{family}:{scenario}` from
   [source_inventory.json](../source_inventory.json).
3. Run redaction and schema validation via `sscre.benchmark_build`.
4. Merge with `python -m sscre.benchmark_build merge --candidates ...`.
5. Add each new pair ID to `development` or `held_out_test` `record_ids` in
   `split_manifest.json` (and bump `dataset_version` when labels change).
6. Rebuild and freeze:

```bash
python -m sscre.benchmark_build --benchmark-dir benchmarks merge --candidates <path> --rebuild-splits
python -m sscre.benchmark_validate --benchmark-dir benchmarks
```

Phase 2 completion requires **500+** reviewed pairs; use
`benchmark_validate --phase2` after the scale-up.

`expansion_v1.jsonl` adds Phase 2 coverage gaps (temporal, domain, ambiguity,
stale, uncertain) to the working baseline.
