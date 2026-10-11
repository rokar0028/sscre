# Phase 3 Workstream 5 Implementation Plan

## Goal

Measure float32 embedding storage on the full development split, then
quantize only if that measurement says embeddings are large enough to matter.

Two gates. Do not treat them as one “workstream complete” verdict.

**Gate A — Feature 6 baseline.** Execute
[Feature 6 — Float32 embedding storage baseline](./PHASE3_PLAN.md#feature-6--float32-embedding-storage-baseline)
(`P3-FEAT-EMBED-BASE`). Write the byte breakdown and the dominance decision.
No int8 code in this gate.

**Gate B — Feature 7 quantization.** Not authorized. Steps 4–6 stay unchecked
until Gate A reports `embedding_share` **≥** `0.20` **and** the user confirms
the pre-registered thresholds in writing. Card:
[Feature 7 — int8 embedding quantization](./PHASE3_PLAN.md#feature-7--int8-embedding-quantization-conditional)
(`P3-FEAT-Q8`).

**Status:** `in progress` — Gate A Step 1 closed 2026-10-11. Steps 2–3 not
started. Gate B not authorized.  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 5.  
**Evidence:** [`PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md)
(pending execution).

## Scope

### Included (Gate A)

- Development replay of `benchmarks/development.jsonl` (400 pairs → 800
  directed requests: `a_to_b` / `query_a`, `b_to_a` / `query_b`, same loop as
  `run_compatibility_cache_baseline` in `src/sscre/baseline.py`)
- Byte breakdown using the existing `_entry_size` rules in
  `src/sscre/cache.py`
- One artifact:
  `artifacts/evaluation/phase3-embedding-storage-baseline.json`
- Dominance decision recorded in the evidence file

### Included only after Gate B is authorized

- Symmetric per-vector int8 quantize on write and dequantize before similarity,
  in-memory replay only
- Development compare of float32 vs int8 on the same workload
- `artifacts/evaluation/phase3-quantization-development.json`

### Excluded

- Held-out replay, held-out tuning, or a protocol reset for this workstream
- PostgreSQL schema changes, pgvector `halfvec`, or a custom int8 column
- Treating Phase 4’s 4-request storage profile or 32-request load profile as
  this baseline
- Changing `StorageControlReport` / Pareto point shape in
  `src/sscre/storage_evaluation.py`
- Raising embedding dimension, dropping the per-vector scale from the byte
  count, or retuning τ to clear a gate
- Live-provider embeddings

## Learning objectives

- [ ] Account cache bytes consistently with `_entry_size` semantics.
- [ ] Gate optional optimizations on measured dominance, not assumptions.
- [ ] Report fake-embedding limitations on storage-only claims.

## Source of truth

| Item | Value / path |
| --- | --- |
| Dataset | `reviewed-query-pairs-2.0` |
| Development file | `benchmarks/development.jsonl` (400 pairs) |
| Directed requests | 800 (`a_to_b`, `b_to_a`) |
| Held-out | not used |
| Config | `experiments/evaluation_config.json` (`evaluation-config-1.0`) |
| Embedding client | `FakeEmbeddingClient` (`src/sscre/embedding.py`), default dimension **8**, model `fake-embedding` |
| Dtype / width | float32, **4** bytes per component (`_entry_size`) |
| Cache | `InMemoryExactCache` default `deduplicate=True` (Strategy B/C path) |
| Insert path | `_baseline_cache_entry_after_generation` stores `embedding_result.vector` |
| Caps for this baseline | `max_entries` and `max_bytes` both unset (`cache.insert`, no eviction) |
| Dominance gate | `embedding_share` ≥ **0.20** |
| Byte reduction (Gate B) | ≥ **3.5×** vs float32 `embedding_bytes` |
| Safety (Gate B) | development `false_positive_rate` ≤ **0.0** |
| Reuse (Gate B) | development `hit_rate` ≥ float32 reference |
| τ (Gate B decisions) | frozen Feature 1 map `artifacts/evaluation/phase3-adaptive-threshold-map.json`; do not retune |
| Hash helper | `file_sha256` in `src/sscre/benchmark_splits.py` |
| Not a substitute | `experiments/storage_controls_development.json` (4 requests; entries have no embedding) |

## Current code gap

Step 1 is in `src/sscre/cache.py`: `entry_byte_components` feeds `_entry_size`,
and `InMemoryExactCache.byte_breakdown()` sums query, metadata, embedding, and
answer bytes (canonical answers included once when dedup is on).
`storage_bytes()` is that total. `StorageControlReport` is unchanged.

Still open for Steps 2–3: `run_storage_control_evaluation` inserts `CacheEntry`
without an embedding, so a Milestone 9 storage report still has
`embedding_bytes` of 0. Phase 4’s 4-request profile is not the Feature 6
baseline. Strategy C stores vectors via `_baseline_cache_entry_after_generation`,
but no development artifact writes the breakdown yet.

## Byte accounting

One formula, shared with `_entry_size`:

- `query_bytes` = UTF-8 length of `normalized_query`
- `metadata_bytes` = UTF-8 length of `json.dumps(metadata.to_dict() or {}, separators=(",", ":"), ensure_ascii=False)`
- `embedding_bytes` = `len(embedding or ()) * 4` (0 when the vector is absent)
- `answer_bytes` = UTF-8 length of the answer **once** in the canonical store
  when dedup is on; otherwise the per-entry answer bytes `_entry_size` already
  adds
- `total_bytes` = `storage_bytes()` (entry sizes + canonical answer bytes)

Identity the tests must enforce:

`query_bytes + metadata_bytes + embedding_bytes + answer_bytes == total_bytes`

`embedding_share = embedding_bytes / total_bytes`. If `total_bytes` is 0, the
baseline is invalid and Gate B stays closed.

Dedup on (the default) moves answer bytes out of `_entry_size` and into
`_canonical_answers`. The breakdown must still count them in `answer_bytes` so
the identity matches `storage_bytes()`.

## Prerequisites

- [x] Features 6–7 cards in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- [x] Pre-code checklist for Gate A Step 1 recorded in
      [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) (2026-10-11).
      Repeat it before Steps 2–3.
- [x] User approved Gate A Step 1 in writing (2026-10-11). Steps 2–3 still
      need a separate approval.
- [ ] User confirms dominance **0.20**, reduction **3.5×**, and the safety/reuse
      rules before any Gate B code. Card text is not that confirmation.

## Gate A — Feature 6

### Step 1 — Shared breakdown

- [x] Add a helper used by `_entry_size` (or that `_entry_size` calls) so
      component sums and `storage_bytes()` cannot drift.
      `entry_byte_components` in `src/sscre/cache.py`.
- [x] Expose an aggregate breakdown on `InMemoryExactCache` (entries plus
      canonical answers). Do not put these fields on `StorageControlReport`.
      `InMemoryExactCache.byte_breakdown()` → `CacheByteBreakdown`.
- [x] Tests: absent embedding → `embedding_bytes == 0` and existing storage
      totals unchanged; present embedding → `embedding_bytes == dimension * 4`;
      dedup answer counted once; components sum to `storage_bytes()`.
      `tests/test_embedding_storage.py`. Evidence:
      [`PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md)
      § Step 1.

### Step 2 — Development replay

- [ ] New measurement entry point (module or CLI). Suggested module:
      `src/sscre/phase3_embedding_storage.py`. It loads development records
      with `load_benchmark_jsonl`, replays both directions, embeds with
      `FakeEmbeddingClient()`, and inserts through the existing baseline entry
      helper with **no** `max_entries` / `max_bytes`.
- [ ] Do not call `python -m sscre.storage_evaluation` on
      `experiments/storage_controls_development.json` for this artifact.
- [ ] Require `eviction_count == 0`. If a cap is set and evictions occur, do
      not write the baseline; raise the cap or leave caps unset and rerun.
- [ ] Record `requests` (800) separately from `entries` (unique inserted
      queries). Duplicate normalized queries stay one entry
      (`DuplicateCacheEntryError` path).

### Step 3 — Artifact and dominance gate

- [ ] Write `artifacts/evaluation/phase3-embedding-storage-baseline.json`
      with at least:

      | Field | Rule |
      | --- | --- |
      | `report_type` | `phase3_embedding_storage_baseline` |
      | `dataset_version` | `reviewed-query-pairs-2.0` |
      | `split` | `development` |
      | `development_sha256` | `file_sha256` of `benchmarks/development.jsonl` |
      | `config_sha256` | `file_sha256` of `experiments/evaluation_config.json` |
      | `git_commit`, `git_worktree_dirty` | same git helper pattern as `storage_evaluation._git_metadata` |
      | `measurement_environment` | `synthetic_replay` |
      | `embedding_provider` | `fake` |
      | `embedding_model` | client config model name |
      | `embedding_dimensions` | client dimension (expected **8**) |
      | `embedding_dtype` | `float32` |
      | `bytes_per_dimension` | `4` |
      | `requests`, `entries` | as replayed |
      | `embedding_bytes`, `answer_bytes`, `metadata_bytes`, `query_bytes`, `total_bytes` | breakdown |
      | `embedding_share` | `embedding_bytes / total_bytes` |
      | `average_entry_bytes` | `total_bytes / entries` when `entries > 0` |
      | `eviction_count` | must be `0` |
      | `max_entries`, `max_bytes` | `null` when caps are unset |
      | `quantize_authorized` | `true` iff `embedding_share >= 0.20` |

- [ ] Record the command, commit, config hash, dataset version, and
      **quantize authorized: yes/no** in
      [`PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md).
- [ ] If **no**, stop. Feature 7 stays **not authorized**. Do not add quantize
      code. Gate A can still close.

## Gate B — Feature 7 (if authorized)

### Step 4 — int8 boundary

- [ ] Symmetric per-vector int8: `scale = max(abs(component)) / 127` (0 for an
      all-zero vector). Store int8 codes plus that scale. Dequantize before
      `_cosine_similarity`. Quantize at insert; do not change stored float
      payloads in PostgreSQL.
- [ ] `embedding_bytes` for the int8 arm includes codes **and** the scale
      (one float32, 4 bytes, per vector). Omitting the scale to clear 3.5× is
      a failed measurement.
- [ ] At dimension 8 that ratio is `(4 * 8) / (8 + 4) = 2.67×`, which is below
      **3.5×**. Keep dimension 8. A miss on byte reduction is a fail: keep
      float32. Do not switch to a wider fake dimension to pass.
- [ ] Tests in `tests/test_embedding_quantization.py` (create with this step):
      round-trip absolute error ≤ `scale / 127` per component; dimension
      preserved; empty, non-finite, and dimension-mismatch inputs fail closed
      and do not insert a hit-able entry; zero vector round-trips to zeros.

### Step 5 — Development compare

- [ ] Same development records, `FakeEmbeddingClient`, and Feature 1 τ map as
      the float32 Strategy C arm. No held-out file.
- [ ] Write `artifacts/evaluation/phase3-quantization-development.json` with
      float32 and int8 `embedding_bytes`, byte ratio,
      `hit_rate`, `false_positive_rate`, `decision_agreement_rate`
      (SAFE / UNSAFE / UNCERTAIN), `similarity_drift_max`, and
      `similarity_drift_p95`.
- [ ] Drift: on each development similarity comparison, absolute difference
      between float32 cosine and cosine after both vectors are int8-round-tripped.
      Drift is reported, not an extra pass threshold.
- [ ] **Pass** iff all of: int8 `embedding_bytes` ≤ float32 `embedding_bytes / 3.5`,
      int8 `false_positive_rate` ≤ `0.0`, int8 `hit_rate` ≥ float32 `hit_rate`.
- [ ] **Fail:** keep float32; do not put int8 on the paper stack. No second
      development run that changes scale, dimension, or τ.

### Step 6 — Close

- [ ] Evidence states pass or fail, `quantize_authorized`, and the fake-embedding
      limitation: a storage result is not a general accuracy claim.
- [ ] No held-out quantization run.

## Verification

Confirm these paths exist before recording a run: `tests/test_storage_evaluation.py`,
`tests/test_cache_eviction.py`. Add quantization tests only in Step 4.

After Step 1 (breakdown only):

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_storage_evaluation.py tests/test_cache_eviction.py
```

After Step 4, include `tests/test_embedding_quantization.py` in that command.
After any substantive code change, run the full suite and record pass, fail,
or skip:

```powershell
python -m pytest -q
```

Do not mark the full suite complete if it was not run.

## Acceptance criteria

- [x] Card (hypothesis, metric, pass/fail, stopping rule) in `PHASE3_PLAN.md`.
- [ ] Float32 development-scale baseline recorded:
      `artifacts/evaluation/phase3-embedding-storage-baseline.json`.
- [ ] Quantization comparison recorded, or deferral justified by Gate A:
      `artifacts/evaluation/phase3-quantization-development.json` or an
      explicit **not authorized** row in the evidence file.
- [ ] Unit tests cover the byte identity and, if Gate B opens, round-trip
      bounds, dimension preservation, and failure-closed malformed vectors.
- [ ] Evidence filled in `docs/phase-3/PHASE3_QUANTIZATION_EVIDENCE.md`.

## Out of scope

- PostgreSQL `halfvec` or any schema migration (later slice: compare `halfvec`
  before a custom int8 column; pgvector has no native int8 vector type)
- Held-out threshold or quantization tuning
- Phase 4 storage or scale profiles as a stand-in for Feature 6
- Shipping int8 when Gate A or the 3.5× / safety / reuse rules fail
