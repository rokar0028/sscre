# Milestone 9 Implementation Plan — Cache Controls

## Goal

Extend SSCRE from compatibility-aware cache safety to bounded, freshness-aware
cache storage:

```text
POST /v1/query
    ↓
normalize and exact lookup
    ↓
reject expired or non-reusable entries
    ↓
embed query and retrieve top-K candidates
    ↓
apply compatibility and freshness checks
    ↓
SAFE candidate → reuse and update access metadata
UNSAFE or UNCERTAIN → generate
    ↓
validate generated answer
    ↓
deduplicate against canonical answers
    ↓
insert or update entry
    ↓
enforce answer-size, entry-count, byte, TTL, and LRU limits
```

This milestone implements the cache lifecycle and storage controls deferred
from Milestone 8. It does not add a new safety validator, dual-model fallback,
adaptive thresholds, or production-scale infrastructure.

## Learning objectives

- [x] Stable, semi-dynamic, and dynamic freshness policies
- [x] TTL semantics and expiration checks
- [x] Cache invalidation and delete behavior
- [x] Content-addressable answer deduplication
- [x] Canonical answers and metadata merging
- [x] Maximum answer-size validation
- [x] LRU eviction and access accounting
- [x] Storage-cap enforcement and byte accounting
- [x] Atomic cache mutations under concurrent requests
- [x] Storage growth, deduplication, and eviction evaluation
- [x] Failure-closed behavior when cache-control operations fail

## Implementation steps

### 1. Define the cache-control contract

- [x] Define freshness classes as `stable`, `semi_dynamic`, and `dynamic`.
- [x] Define the default TTL policy for each freshness class.
- [x] Define whether dynamic entries can ever be stored or served; default to
  rejecting them unless an explicit policy permits it.
- [x] Define expiration as `now >= ttl_expires_at`.
- [x] Define behavior for a missing, invalid, or timezone-naive expiration
  timestamp.
- [x] Ensure expired entries are never served by exact or semantic lookup.
- [x] Define whether expired entries are deleted eagerly, lazily, or both.
- [x] Define the precedence between freshness policy, TTL, compatibility, and
  similarity decisions.
- [x] Document that TTL controls availability, while compatibility controls
  whether a non-expired answer is safe to reuse.

Evidence: `src/sscre/cache_controls.py` and
`tests/test_cache_controls.py`; `python -m pytest -q
tests/test_cache_controls.py tests/test_safety.py` → 18 passed.

### 2. Implement freshness and TTL policy

- [x] Reuse Milestone 8 temporal classification rather than creating a second
  classifier.
- [x] Add configuration for class TTLs, dynamic-entry behavior, and clock
  tolerance if needed.
- [x] Calculate `ttl_expires_at` when an answer becomes cacheable.
- [x] Apply TTL checks to exact lookup results.
- [x] Apply TTL checks to semantic retrieval candidates before compatibility
  evaluation or serving.
- [x] Ensure an expired exact match cannot bypass semantic safety checks.
- [x] Exclude expired entries from candidate ranking where the repository
  supports filtering.
- [x] Add a bounded cleanup operation for expired entries.
- [x] Make clock access injectable or deterministic in unit tests.
- [x] Test stable, semi-dynamic, dynamic, expired, and missing-TTL cases.

Evidence: `src/sscre/cache_controls.py`, `src/sscre/config.py`,
`src/sscre/cache.py`, `src/sscre/app.py`,
`migrations/005_store_cache_ttl.sql`, and
`tests/test_cache_ttl_integration.py`; targeted cache/config tests → 30
passed. Expired-entry cleanup remains deferred.

### 3. Define canonical-answer storage

- [x] Define the canonical answer record independently from query-specific
  cache metadata.
- [x] Compute a stable `answer_hash` from the canonical answer content.
- [x] Store one answer body for multiple compatible cache entries.
- [x] Preserve the metadata needed to make a safe reuse decision for each
  query or compatibility cluster.
- [x] Define how model source, correctness status, validation status, and
  freshness metadata are represented.
- [x] Define whether incompatible metadata may share an answer body without
  sharing a reusable cache entry.
- [x] Keep raw prompts, hidden reasoning, credentials, and unbounded
  evaluation data out of canonical answer storage.
- [x] Document ownership and deletion behavior when the final reference to a
  canonical answer is evicted.

Evidence: `src/sscre/canonical.py`, `src/sscre/cache.py`,
`migrations/006_store_canonical_answers.sql`, and
`tests/test_canonical.py`; reference population and deduplication are
implemented in Step 4.

### 4. Add answer deduplication

- [x] Deduplicate generated answers by `answer_hash`.
- [x] Reuse an existing canonical answer record when the answer content is
  identical.
- [x] Avoid storing a second answer body when a compatible canonical answer
  already exists.
- [x] Merge only bounded, explicitly supported metadata on a deduplication
  hit.
- [x] Keep query hashes unique and preserve exact lookup semantics.
- [x] Ensure deduplication does not merge incompatible query metadata into a
  single reusable entry.
- [x] Handle concurrent inserts for the same answer hash with a database
  uniqueness constraint or equivalent atomic operation.
- [x] Test identical answers with different queries, models, freshness
  classes, and compatibility metadata.

Evidence: `src/sscre/cache.py` reuses one in-memory
`CanonicalAnswer`, `src/sscre/postgres_cache.py` uses
`INSERT ... ON CONFLICT DO NOTHING`, and
`migrations/006_store_canonical_answers.sql` defines the unique answer
identity and nullable cache-entry reference. `tests/test_canonical.py` verifies
shared content with distinct query metadata; `python -m pytest -q` → 144
passed, 8 skipped.

### 5. Enforce answer and metadata size limits

- [x] Add a configurable maximum answer size in bytes or characters.
- [x] Reject or bypass caching for generated answers above the configured
  limit; never truncate an answer silently.
- [x] Add bounded limits for serialized metadata and query text where stored.
- [x] Validate limits before writing to the repository.
- [x] Return a generated response even when the answer is not cacheable.
- [x] Record a bounded reason such as `answer_too_large` for observability.
- [x] Test boundary, over-limit, empty, and multibyte answer values.

Evidence: `CacheSizeLimits` in `src/sscre/cache_controls.py`, settings and
environment configuration in `src/sscre/config.py`/`.env.example`, and
pre-insert enforcement in `src/sscre/app.py`. Targeted cache-size tests →
17 passed.

### 6. Implement LRU and storage-cap eviction

- [x] Define the storage budget using maximum entries and maximum bytes.
- [x] Track `hit_count` and a last-access timestamp or equivalent recency key.
- [x] Update access metadata on exact and semantic cache reuse.
- [x] Define deterministic eviction ordering, including ties.
- [x] Evict least-recently-used entries when the entry-count limit is reached.
- [x] Evict least-recently-used entries when the byte limit is reached.
- [x] Remove orphaned canonical answers after their final cache entry is
  evicted.
- [x] Make insertion plus eviction atomic enough that the configured cap is
  not exceeded after a successful mutation.
- [x] Define `insert_and_evict()` as the required bounded-write operation;
  direct `insert()` remains an unbounded primitive for tests and maintenance.
- [x] Define behavior when one answer is larger than the entire configured
  storage budget.
- [x] Keep cleanup work bounded per request or expose it as a separate
  maintenance operation.
- [x] Test eviction ordering, recency updates, ties, orphan cleanup, and
  repeated insertions.

Evidence: `insert_and_evict()` in `src/sscre/cache.py` and
`src/sscre/postgres_cache.py`, PostgreSQL access counters and eviction,
migrations `007_cache_access_counters.sql`, and
`tests/test_cache_eviction.py`. Bounded production writes perform insertion
and eviction as one repository operation; direct `insert()` does not enforce
caps.

### 7. Update the repository and schema

- [x] Add the minimum schema required for canonical answers, references,
  access metadata, byte counts, and TTL state.
- [x] Add constraints and indexes for answer hashes, expiration timestamps,
  recency, and reference ownership.
- [x] Use parameterized SQL for all new operations.
- [x] Add repository methods for expired-entry cleanup, deduplication,
  access updates, storage statistics, and eviction.
- [x] Keep exact lookup and top-K vector retrieval behavior compatible with
  existing callers.
- [x] Handle missing migrations, unsupported schema versions, and database
  failures without serving an unsafe or expired candidate.
- [x] Require `sscre-migrate` to complete before PostgreSQL-backed startup;
  validate migration versions and SHA-256 checksums.
- [x] Enforce lowercase hexadecimal SHA-256 format for query and canonical
  answer hashes at the database boundary.
- [x] Add unit tests for repository decisions and PostgreSQL integration tests
  for constraints, deduplication, TTL filtering, and eviction.

Evidence: tracked migrations `000_schema_migrations.sql`,
`006_store_canonical_answers.sql`,
`007_cache_access_counters.sql`, `008_store_cache_sizes.sql`,
`009_backfill_legacy_ttl.sql`, and `010_cache_lifecycle_counters.sql`, plus
`011_validate_sha256_hashes.sql`, the ordered/checksummed runner
`src/sscre/migrate.py`, and startup validation in
`src/sscre/postgres_cache.py`;
repository
methods in `src/sscre/cache.py` and `src/sscre/postgres_cache.py`; and
`tests/test_cache_eviction.py` and expanded PostgreSQL lifecycle tests.
Unit suite → 158 passed, 12 skipped without the database environment;
PostgreSQL integration/vector suite → 15 passed
with the local database.

### 8. Integrate controls into the request path

- [x] Preserve exact lookup as the first operation.
- [x] Reject expired or policy-ineligible exact entries before reuse.
- [x] Filter expired semantic candidates before Strategy C evaluates them.
- [x] Preserve `SAFE`, `UNSAFE`, and `UNCERTAIN` semantics from Milestone 8.
- [x] Update recency only after a response is actually served.
- [x] Cache only generated answers that satisfy freshness, metadata, and size
  requirements.
- [x] Deduplicate before creating a new answer body.
- [x] Enforce storage caps after successful cache insertion.
- [x] Ensure cache-control failures fail closed for reuse while preserving a
  valid generated response when possible.
- [x] Keep Strategy A, B, and C selectable for comparison.
- [x] Return cache source, freshness state, and bounded cache-control metadata
  without exposing internal storage details or secrets.

Evidence: request-path enforcement in `src/sscre/app.py`, response fields in
`src/sscre/query.py`, and TTL integration coverage in
`tests/test_cache_ttl_integration.py`.

### 9. Add storage and lifecycle observability

- [x] Report entry count, canonical-answer count, total bytes, and average
  bytes per entry.
- [x] Report deduplication hits, deduplication savings, expirations, and
  eviction counts by reason.
- [x] Report rejected answers by size, freshness, metadata, and storage policy.
- [x] Record cache-control events with bounded structured fields.
- [x] Keep request traces bounded even when cleanup or eviction removes many
  entries.
- [x] Do not log full answers, credentials, hidden provider data, or
  unnecessary raw prompts.
- [x] Make storage statistics available to the evaluation harness and an
  administrative inspection path if one already exists.

Evidence: `GET /v1/cache/stats`, `CacheStorageStats`,
`MetricsCollector.cache_rejections`, and bounded structured request logging.
`tests/test_cache_eviction.py` verifies the inspection endpoint.

### 10. Evaluate storage controls

- [x] Add experiments comparing no deduplication with canonical-answer
  deduplication.
- [x] Replay the same workload through real deduplicating and
  non-deduplicating repositories rather than deriving no-dedup bytes.
- [x] Accept provider-supplied token and generation-latency usage per workload
  item, with explicit synthetic fallback labels.
- [x] Measure storage growth under repeated exact queries, paraphrases, and
  repeated answer content.
- [x] Measure bytes per entry, canonical-answer count, deduplication ratio,
  eviction rate, and expired-entry rate.
- [x] Measure hit rate, safe reuse coverage, tokens saved, cost, and latency
  before and after TTL and eviction controls.
- [x] Verify that TTL policies reduce stale reuse without masking compatibility
  failures.
- [x] Test storage caps under insertion workloads that exceed both entry and
  byte limits.
- [x] Test concurrent or interleaved insertions for duplicate answers and cap
  enforcement.
- [x] Keep development tuning separate from held-out evaluation.
- [x] Save machine-readable reports with strategy, policy, caps, dataset
  version, and software/worktree metadata.
- [x] Add representative storage failures and lifecycle edge cases to the
  failure gallery.

Evidence: `docs/SSCRE_STORAGE_FAILURE_GALLERY.md` links each lifecycle case to
its implementation or test coverage.

Evidence: `src/sscre/storage_evaluation.py`,
`experiments/storage_controls_development.json`, and generated
`experiments/storage_controls_development_report.json`; `python -m pytest -q`
→ 156 passed, 8 skipped. The existing baseline harness still owns token,
cost, latency, and held-out safety evaluation; those storage-control
comparisons now include deterministic token, configurable cost, latency,
safe-reuse coverage, and expired-reuse-prevention fields. The storage
evaluator now runs real deduplicating and non-deduplicating caches and labels
synthetic token/latency fallbacks.

### 11. Document limitations and update project tracking

- [x] Document TTL as a freshness approximation, not proof that an answer is
  factually current.
- [x] Document that answer hashes deduplicate identical content but do not
  establish semantic equivalence.
- [x] Document metadata/reference trade-offs in canonical-answer storage.
- [x] Document eviction effects on future reuse and reproducibility.
- [x] Document behavior when a cache-control operation is unavailable.
- [x] Update request-flow, system-design, schema, and evaluation documents
  only after implementation and measurements exist.
- [x] Update the learning guide and project tracker only after code, tests,
  and evidence exist.

Evidence: limitations are documented in
`docs/SSCRE_EVALUATION_LIMITATIONS.md`; request behavior is documented in
`docs/SSCRE_REQUEST_FLOW.md`; architecture status is updated in
`docs/SSCRE_SYSTEM_DESIGN.md`; and tracking is updated in
`docs/SSCRE_PLAN.md` and `docs/SSCRE_LEARNING_AND_EXECUTION_GUIDE.md`.

## Verification checklist

- [x] Stable and semi-dynamic entries receive the configured TTL.
- [x] Dynamic entries are rejected by default.
- [x] Expired exact entries are never served.
- [x] Expired semantic candidates are never served.
- [x] Compatibility and freshness checks both apply before every cache hit.
- [x] Identical answer content is stored once through canonical-answer
  deduplication.
- [x] Incompatible query metadata is not merged merely because answer bodies
  match.
- [x] Oversized answers are returned to the caller but are not cached.
- [x] Entry-count and byte caps are enforced after insertion.
- [x] LRU ordering is deterministic and access updates occur only on reuse.
- [x] Orphaned canonical answers are removed safely.
- [x] Cache-control and repository failures do not produce a cache hit.
- [x] Storage metrics report counts, bytes, deduplication, expiration, and
  eviction behavior.
- [x] Existing exact-cache, semantic retrieval, Strategy C, and no-cache tests
  still pass.
- [x] New unit and integration tests pass (`158 passed, 12 skipped` without
  `SSCRE_DATABASE_URL`; PostgreSQL integration/vector tests separately pass
  `15 passed`).
- [x] Evaluation reports quantify freshness and storage trade-offs.
- [x] No linter errors are reported by IDE diagnostics; no standalone linter
  is configured.

Verification evidence: `python -m pytest -q` → 155 passed, 8 skipped; the
8 skipped tests are PostgreSQL integration tests because
`SSCRE_DATABASE_URL` is unavailable. IDE diagnostics report no linter errors.

## Completion criteria

Milestone 9 is complete when SSCRE applies explicit freshness and TTL policy
to exact and semantic candidates, rejects dynamic entries by default, stores
identical answer content through canonical-answer deduplication, and enforces
answer-size, entry-count, byte, and LRU limits. The request path must remain
failure-closed for reuse, while generated responses remain available when an
answer is not cacheable. Tests and reproducible evaluations must demonstrate
that the controls bound storage and stale reuse without invalidating the
compatibility guarantees established in Milestone 8.
