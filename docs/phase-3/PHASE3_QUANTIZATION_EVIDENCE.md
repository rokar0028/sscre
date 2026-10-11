# Phase 3 quantization and storage evidence

**Workstream:** 5 (Features 6–7)  
**Plan:** [`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md)  
**Status:** Step 1 closed (2026-10-11). Development baseline and dominance
gate not run. Feature 7 not authorized.

| Feature | Artifact | Status |
| --- | --- | --- |
| 6 — float32 baseline | `artifacts/evaluation/phase3-embedding-storage-baseline.json` | pending (Steps 2–3) |
| 7 — int8 compare | `artifacts/evaluation/phase3-quantization-development.json` | not authorized |

## Step 1 — shared breakdown

**Date:** 2026-10-11  
**Scope:** `CacheByteBreakdown`, `entry_byte_components`, and
`InMemoryExactCache.byte_breakdown` in `src/sscre/cache.py`.
`storage_bytes()` returns that total. `StorageControlReport` unchanged.
No development replay and no int8 code.

- [x] `python -m pytest -q tests/test_embedding_storage.py tests/test_storage_evaluation.py tests/test_cache_eviction.py tests/test_exact_cache.py` → **40 passed** (2026-10-11).
- [x] `python -m pytest -q` → **748 passed, 15 skipped, 21 deselected** (2026-10-11). Skips are existing unavailable-service tests, not a Step 1 failure.
