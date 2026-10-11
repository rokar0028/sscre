# Phase 3 quantization and storage evidence

**Workstream:** 5 (Features 6–7)  
**Plan:** [`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md)  
**Status:** Gate A closed (2026-10-11). Step 6 closed (2026-10-11).
`quantize_authorized` **no**. Feature 7 **not authorized**. The int8
compare was not scored.

| Feature | Artifact | Status |
| --- | --- | --- |
| 6 — float32 baseline | `artifacts/evaluation/phase3-embedding-storage-baseline.json` | recorded; `embedding_share` `0.123641` |
| 7 — int8 compare | `artifacts/evaluation/phase3-quantization-development.json` | not authorized (share < `0.20`) |

## Step 1 — shared breakdown

**Date:** 2026-10-11  
**Scope:** `CacheByteBreakdown`, `entry_byte_components`, and
`InMemoryExactCache.byte_breakdown` in `src/sscre/cache.py`.
`storage_bytes()` returns that total. `StorageControlReport` unchanged.
No development replay and no int8 code.

- [x] `python -m pytest -q tests/test_embedding_storage.py tests/test_storage_evaluation.py tests/test_cache_eviction.py tests/test_exact_cache.py` → **40 passed** (2026-10-11).
- [x] `python -m pytest -q` → **748 passed, 15 skipped, 21 deselected** (2026-10-11). Skips are existing unavailable-service tests, not a Step 1 failure.

## Step 2 — development replay

**Date:** 2026-10-11  
**Scope:** `measure_development_embedding_storage` in
`src/sscre/phase3_embedding_storage.py`. Loads development JSONL, 800 directed
requests, `FakeEmbeddingClient`, uncapped insert via the baseline entry helper.
No baseline JSON and no int8 code.

- [x] `python -m pytest -q tests/test_embedding_storage.py` → **7 passed** (2026-10-11), including `requests == 800` on `benchmarks/development.jsonl` and rejection when a cap evicts.
- [x] `python -m pytest -q` → **751 passed, 15 skipped, 21 deselected** (2026-10-11).

## Step 3 — baseline artifact and dominance gate

**Date:** 2026-10-11  
**Dataset:** `reviewed-query-pairs-2.0`  
**Split:** `development`  
**Command:**

```powershell
$env:PYTHONPATH='src'
python -m sscre.phase3_embedding_storage --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --output artifacts/evaluation/phase3-embedding-storage-baseline.json --dataset-version reviewed-query-pairs-2.0
```

Output: `quantize_authorized=false embedding_share=0.123641`.

| Field | Value |
| --- | --- |
| `git_commit` | `e3363cfdebed9d9f0734e3b9458fdfede8ac199c` |
| `git_worktree_dirty` | `true` (uncommitted work present when the artifact was written) |
| `config_sha256` | `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8` |
| `development_sha256` | `14a1d2acd976c2fc891e6d5c3b7c33b729e69e37e66809929d1f74a759f01305` |
| `requests` / `entries` / `duplicate_requests` | `800` / `728` / `72` |
| `embedding_bytes` / `total_bytes` | `23296` / `188417` |
| `embedding_share` | `0.123641` |
| `embedding_dimensions` | `8` (`float32`, 4 bytes per component) |
| `eviction_count` | `0` |
| **quantize authorized** | **no** |

Fake embeddings at dimension 8 are a storage measurement, not a general
accuracy claim. Feature 7 code was not added.

- [x] `python -m pytest -q tests/test_embedding_storage.py` → **11 passed** (2026-10-11).
- [x] `python -m pytest -q` → **755 passed, 15 skipped, 21 deselected** (2026-10-11).

## Step 4 — int8 boundary

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md) Step 4  
**Decision:** **blocked; Gate B not authorized**

Step 4 opens only when Feature 6 reports `embedding_share` ≥ `0.20` and the
pre-registered thresholds are confirmed in writing. The Step 3 artifact does
not clear the share gate.

| Gate B input | Result |
| --- | --- |
| Artifact | `artifacts/evaluation/phase3-embedding-storage-baseline.json` |
| `embedding_share` | `0.123641` (not ≥ `0.20`) |
| `quantize_authorized` | `false` |
| Written confirmation of Feature 7 thresholds | not granted; share gate already failed |
| int8 quantize/dequantize module | not added |
| `tests/test_embedding_quantization.py` | not added |
| PostgreSQL float payloads | unchanged |

No quantization code was added. Step 5 was evaluated next and is also blocked.
Step 6 records the close. Gate B stays unauthorized.

## Step 5 — development compare

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md) Step 5  
**Decision:** **blocked; comparison not run**

Step 5 replays development float32 vs int8 only after Gate B is authorized.
Step 4 did not authorize it.

| Check | Result |
| --- | --- |
| Gate B | not authorized (`embedding_share` `0.123641` < `0.20`) |
| Feature 1 τ map | not applied to an int8 arm |
| Held-out file | not used |
| `artifacts/evaluation/phase3-quantization-development.json` | not written |
| `hit_rate`, `false_positive_rate`, decision agreement, similarity drift | not measured |
| Paper stack | float32; int8 not added |

The untriggered acceptance rule stays in force: no quantization comparison
until `embedding_share` ≥ `0.20`
([`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 5.2).

## Step 6 — close

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_5_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_5_IMPLEMENTATION_PLAN.md) Step 6  
**Result:** **not authorized**

Feature 7 does not open. `embedding_share` `0.123641` is below `0.20`, so
the int8 compare was not run and has no pass or fail on the 3.5×,
false-positive, or hit-rate rule. `quantize_authorized` is **no**.

Fake embeddings at dimension 8 are a storage measurement. A storage result is
not a general accuracy claim.

No held-out quantization run. The checkout has no
`artifacts/evaluation/phase3-quantization-development.json` and no other
quantization artifact. `src/sscre/phase3_embedding_storage.py` does not
quantize. Float32 remains the stored path. Steps 4–5 stay unchecked.
