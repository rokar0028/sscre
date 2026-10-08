# CacheEval upstream staging (Phase 1)

Do **not** commit unfiltered `cachebench.jsonl`. Obtain it locally:

```powershell
git clone --depth 1 https://github.com/BudEcosystem/CacheEval.git $env:TEMP\CacheEval
```

Read upstream `LICENSE`, `ATTRIBUTION.md`, and `SCHEMA.md` before filtering.

Build the commercial-safe export (QQP + xLAM-NC rows removed):

```powershell
python benchmarks/candidates/tools/filter_cacheeval_commercial.py `
  --input $env:TEMP\CacheEval\cachebench.jsonl `
  --output benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl `
  --audit benchmarks/candidates/upstream/cacheeval_v1_filter_audit.json `
  --upstream-revision $(git -C $env:TEMP\CacheEval rev-parse HEAD)
```

Committed artifacts:

- `cacheeval_v1_filter_audit.json` — row counts, excluded IDs, output SHA-256
- `cacheeval_v1_filtered.jsonl` — optional local-only (gitignored); regenerate with the command above

Convert to SSCRE candidates (schema `1.1`, draft labels):

```powershell
python benchmarks/candidates/tools/convert_cacheeval_candidates.py `
  --input benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl `
  --output benchmarks/candidates/cacheeval_batch_01.jsonl `
  --limit 575

python -m sscre.benchmark_build --benchmark-dir benchmarks validate-candidates `
  --candidates benchmarks/candidates/cacheeval_batch_01.jsonl
```

Phase 2 plan: [BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md](../../../docs/phase-2/BENCHMARK_500_SCALE_UP_IMPLEMENTATION_PLAN.md).
