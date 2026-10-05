# Milestone 3 Implementation Plan — Exact-Match Cache

## Goal

Build the first end-to-end SSCRE request path with an in-memory exact cache:

```text
POST /v1/query
    ↓
normalize and hash query
    ↓
exact cache lookup
    ├── hit  → return cached answer
    └── miss → generate with mock LLM → store → return answer
```

This milestone proves the basic reuse flow before metrics, PostgreSQL, and
semantic retrieval are added. The in-memory repository is the default for
isolated application instances; later PostgreSQL support is an optional
configured repository.

## Learning objectives

- [ ] Cache keys and exact equality
- [ ] In-memory dictionaries and lookup complexity
- [ ] Dataclasses and immutable cache entries
- [ ] Dependency boundaries between API, cache, and LLM client
- [ ] Cache hit and miss behavior
- [ ] FastAPI `POST` endpoints
- [ ] Response models and source metadata
- [ ] Why a mock dependency makes tests deterministic

## Implementation steps

### 1. Define the cache entry

- [x] Add an immutable `CacheEntry` model.
- [x] Store the query hash.
- [x] Store the normalized query.
- [x] Store the generated answer.

### 2. Implement the in-memory cache

- [x] Implement exact `get` lookup by query hash.
- [x] Implement `put`/insert behavior.
- [x] Return `None` for a cache miss.
- [x] Keep entries isolated inside each application instance.

### 3. Add the mock LLM client

- [x] Add a deterministic mock generation method.
- [x] Generate an answer from the normalized query.
- [x] Keep the client replaceable for later real providers.

### 4. Implement `POST /v1/query`

- [x] Accept a validated `QueryRequest`.
- [x] Normalize and hash the query.
- [x] Check the exact cache before generation.
- [x] Generate only on a cache miss.
- [x] Store successful generated answers.
- [x] Return `source = "generated"` on a miss.
- [x] Return `source = "cache"` on a hit.

### 5. Add exact-cache tests

- [x] Test cache `get` and `put`.
- [x] Test the first request generates an answer.
- [x] Test a repeated request uses the cache.
- [x] Test whitespace-equivalent queries reuse the answer.
- [x] Test different queries do not collide.
- [x] Test the returned answer remains consistent across a hit.
- [x] Test generation is called only once for a repeated query.
- [x] Test cache isolation between application instances.

## Verification checklist

- [x] A cache miss calls the mock LLM.
- [x] A cache hit avoids another generation.
- [x] Cache source metadata is correct.
- [x] Different query hashes use different entries.
- [x] The endpoint returns valid response-model data.
- [x] Exact-cache tests pass (`.venv\Scripts\python.exe -m pytest -q tests/test_exact_cache.py`; 5 passed).
- [x] The full test suite passes (`.venv\Scripts\python.exe -m pytest -q`;
  28 passed, 6 skipped).
- [ ] No linter errors are reported (no linter is currently configured).

Concurrent misses are protected by an application-instance generation lock.
This intentionally serializes cache misses within one process; a future
high-throughput implementation should use per-key or distributed coordination.
The shared PostgreSQL repository also handles a cross-process duplicate insert
by reading the entry written by the other process. Separate processes can
still perform duplicate model generation before the database conflict is
observed; eliminating that requires distributed coordination beyond this
milestone.

## Completion criteria

Milestone 3 is complete when `POST /v1/query` can generate and cache an answer,
then return that answer for an equivalent repeated query without generating
again. The cache must remain deterministic and isolated from unrelated
application instances.
