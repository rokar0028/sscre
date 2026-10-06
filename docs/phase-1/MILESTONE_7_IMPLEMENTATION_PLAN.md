# Milestone 7 Implementation Plan — Embedding Retrieval

## Goal

Extend SSCRE from exact-match lookup to embedding-based candidate retrieval
while keeping reuse safety decisions out of this milestone:

```text
POST /v1/query
    ↓
normalize and exact lookup
    ↓
embed query on exact miss
    ↓
retrieve top-K vector candidates
    ↓
apply similarity threshold
    ↓
reuse candidate or generate a new answer
    ↓
record retrieval, token, cost, and latency metrics
```

This milestone introduces semantic retrieval and measures embedding-only
reuse. It does not implement compatibility validation, freshness policies,
answer deduplication, or the safety engine from Milestone 8.

## Learning objectives

- [ ] Embeddings and vector representations
- [ ] Cosine similarity and distance
- [ ] Approximate nearest-neighbor retrieval
- [ ] pgvector types and indexes
- [ ] Embedding-client interfaces and provider isolation
- [ ] Deterministic fakes for external services
- [ ] Top-K retrieval and similarity thresholds
- [ ] Precision, recall, and false-positive rate
- [ ] Embedding token, cost, and latency accounting
- [ ] Development threshold selection versus held-out evaluation

## Implementation steps

### 1. Define the embedding boundary

- [x] Define an embedding result model containing the vector, model name,
  token count, and latency.
- [x] Add an embedding client interface with an asynchronous or synchronous
  method consistent with the existing LLM boundary.
- [x] Define behavior for invalid text, provider failures, dimension
  mismatches, and empty vectors.
- [x] Keep provider-specific SDK details outside the API and repository layers.
- [x] Document the configured embedding dimension and model identifier.

### 2. Add a deterministic fake embedding client

- [x] Implement a deterministic fake embedding client for unit and benchmark
  tests.
- [x] Ensure identical normalized text produces the same vector.
- [x] Ensure test fixtures can produce controlled similar and dissimilar
  vectors.
- [x] Add configurable token counts, latency, and failures.
- [x] Test that fake behavior is stable across process runs.

### 3. Enable pgvector

- [x] Add pgvector to the local PostgreSQL setup.
- [x] Add a migration that enables the required PostgreSQL extension.
- [x] Verify the extension is available before creating vector columns.
- [x] Document the local setup and a clear failure message when pgvector is
  unavailable.
- [x] Keep existing exact-cache behavior working when vector retrieval is not
  configured.

### 4. Store cache embeddings

- [x] Add an embedding vector column to cache entries.
- [x] Store the embedding model and dimension metadata with each entry.
- [x] Generate and persist an embedding for each eligible generated response.
- [x] Do not persist embeddings when generation or embedding fails.
- [x] Use parameterized database operations for vector values.
- [ ] Add a vector index only after measuring the initial retrieval behavior.
- [ ] Add migration and repository tests for inserting and reading embeddings.

### 5. Implement top-K vector retrieval

- [x] Extend the repository interface with top-K similarity search.
- [x] Calculate cosine similarity using pgvector's supported operators.
- [x] Return candidate identifiers, answers, similarity scores, and metadata
  needed by the orchestrator.
- [x] Enforce a positive `top_k` limit and a configured maximum.
- [x] Handle an empty repository without errors.
- [x] Reject incompatible embedding dimensions before querying.
- [x] Add integration tests for ranking, ties, missing candidates, and limits.

### 6. Integrate embedding lookup after exact lookup

- [x] Preserve exact lookup as the first cache operation.
- [x] Embed the normalized query only after an exact-cache miss.
- [x] Retrieve the configured top-K candidates.
- [x] Reuse the highest-scoring candidate only when it meets the configured
  similarity threshold.
- [x] Require candidate model and dimension compatibility.
- [x] Generate and store a new response when no candidate reaches the
  threshold.
- [x] Preserve failure-closed behavior for embedding and database failures.
- [x] Ensure a generated answer is not returned as a semantic hit for the
  request that created it.
- [x] Keep exact-cache-only behavior when semantic retrieval is disabled.

### 7. Implement and name Strategy B

- [x] Define Strategy B as embedding-only reuse with no compatibility validator.
- [x] Add configuration for enabling Strategy B, `top_k`, and the similarity
  threshold.
- [x] Return the source and similarity metadata needed to explain a decision.
- [x] Record exact hits, semantic hits, threshold rejections, and misses
  separately.
- [x] Keep Strategy A (no cache) and exact-cache evaluation unchanged.
- [x] Document clearly that embedding similarity is not a safety decision.

### 8. Sweep thresholds on development data

- [x] Add an evaluation configuration for a list of similarity thresholds.
- [x] Run Strategy B on the development split without using held-out labels.
- [x] Measure hit rate, precision, recall, safe reuse coverage, and
  embedding-only false-positive rate.
- [x] Measure generated and embedding tokens, estimated cost, and latency.
- [x] Select a threshold using a documented development-set rule.
- [x] Record the selected threshold and dataset version in the experiment
  report.
- [x] Do not use held-out labels to choose the threshold.

### 9. Evaluate on held-out data

- [x] Run the selected Strategy B configuration on the held-out split.
- [x] Compare no-cache, exact-cache, and embedding-only results.
- [x] Report false-positive examples with their reviewed labels and reasons.
- [x] Report p50, p95, and p99 latency where the evaluation harness supports
  them.
- [x] Include embedding cost in total cost calculations.
- [x] Save a machine-readable report with model, dimension, threshold, and
  retrieval configuration.

### 10. Document limitations and update project tracking

- [x] Document cosine similarity and the selected vector distance convention.
- [x] Document fake embeddings and their limits as a proxy for production
  embedding quality.
- [x] Document why high similarity does not prove query compatibility.
- [x] Document embedding-provider and pgvector failure behavior.
- [x] Document embedding model compatibility and exact-only disabled behavior.
- [x] Document that vector indexes and evaluation reports are intentionally
  deferred or generated on demand.
- [x] Update the request-flow and system-design documents after verified
  behavior changes the architecture.
- [x] Update the learning guide and project tracker only after code and
  evidence exist.

## Verification checklist

- [x] The embedding interface has unit tests.
- [x] The deterministic fake returns repeatable vectors.
- [x] Invalid embedding dimensions are rejected.
- [x] pgvector is enabled and the migrations apply successfully (`docker compose
  exec ... psql -f /migrations/001_create_cache_entries.sql`,
  `002_enable_pgvector.sql`, and `003_store_cache_embeddings.sql`).
- [x] Cache entries store and retrieve embeddings (PostgreSQL integration
  tests: 8 passed).
- [x] Top-K retrieval returns candidates in similarity order.
- [x] Exact hits bypass embedding generation.
- [x] Semantic hits require the configured threshold.
- [x] Embedding failures fail closed and do not create invalid entries.
- [x] Strategy B reports semantic hits, misses, scores, and thresholds.
- [x] Development threshold sweeps produce machine-readable results.
- [x] Held-out evaluation is run with a threshold selected independently.
- [x] Embedding tokens, cost, and latency are reported.
- [x] Embedding-only false positives are reported with examples.
- [x] Existing exact-cache and no-cache evaluations still pass.
- [x] Unit and integration tests pass (`python -m pytest -q`: 72 passed,
  8 skipped; PostgreSQL integration tests separately: 8 passed).
- [ ] No linter errors are reported (no standalone linter is configured).

## Completion criteria

Milestone 7 is complete when SSCRE can embed a normalized query after an exact
miss, retrieve top-K PostgreSQL/pgvector candidates, apply a documented
development-selected similarity threshold, and evaluate embedding-only reuse
against held-out reviewed data. The results must show the trade-off between
semantic coverage, false positives, token and embedding cost, and latency while
making clear that compatibility-aware safety remains a later milestone.
