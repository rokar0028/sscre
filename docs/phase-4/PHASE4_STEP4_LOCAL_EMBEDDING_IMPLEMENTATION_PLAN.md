# Phase 4 Step 4 — Local embedding provider implementation plan

## Goal

Execute parent Step 4 of
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md):
add a real fixed-dimension **local** embedding path at the existing
`EmbeddingClient` boundary without PostgreSQL or ANN changes.

**Status:** `closed (Step 4 local embedding)` — 2026-10-12.  
**Evidence:**
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md)
§ Step 4.  
**Parent:** parent § 10 Step 4.  
**Card:** `P4-SEMVALID`.

## Learning objectives

- [ ] Explain why `FakeEmbeddingClient` remains for tests but not semantic
      headline runs.
- [ ] Describe how smoke artifacts avoid storing raw query text or full vectors.

## Prerequisites

- [x] Step 3 protocol frozen
      (`experiments/semantic-validity-evaluation-config-v1.json`).
- [x] `EmbeddingClient` boundary in [`../../src/sscre/embedding.py`](../../src/sscre/embedding.py).

## Implementation corpus

- [`../../src/sscre/local_embedding.py`](../../src/sscre/local_embedding.py)
- [`../../src/sscre/local_embedding_probe.py`](../../src/sscre/local_embedding_probe.py)
- [`../../tests/test_local_embedding.py`](../../tests/test_local_embedding.py)
- [`../../benchmarks/semantic-validity-local-embedding-gate.json`](../../benchmarks/semantic-validity-local-embedding-gate.json)
- [`../../artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json`](../../artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json)

## Implementation steps

- [x] Inspect environment: `torch` present; `sentence-transformers` added via
      optional extra `local-embeddings` in `pyproject.toml`.
- [x] Register `sentence-transformers/all-MiniLM-L6-v2` (384-dim, Apache-2.0).
- [x] Implement `LocalSentenceTransformerEmbeddingClient` with validation,
      timeout, injectable encoder for tests.
- [x] Record probe + smoke artifact (fingerprint only, no query text).
- [x] Contract tests: success, malformed output, dimension mismatch, failure,
      timeout, no-cache-on-failure (`tests/test_local_embedding.py`).
- [x] Live model test opt-in: `pytest -m local_embedding`.

## Verification

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_local_embedding.py -m "not local_embedding"
python -m sscre.local_embedding_probe
```

## Acceptance criteria

- [x] Provider code at embedding boundary only; `FakeEmbeddingClient` unchanged.
- [x] Frozen config documents `local_embedding_provider` block.
- [x] Gate `available` with smoke `status=pass` in this environment (re-run
      probe after dependency changes).
- [x] No development/held-out A/B/C headline run (parent Step 5).
