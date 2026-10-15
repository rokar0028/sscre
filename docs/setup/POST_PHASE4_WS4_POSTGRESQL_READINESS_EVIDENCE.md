# Post–Phase 4 Workstream 4 — PostgreSQL readiness evidence

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Child plan:** [`POST_PHASE4_WS4_POSTGRESQL_READINESS_IMPLEMENTATION_PLAN.md`](./POST_PHASE4_WS4_POSTGRESQL_READINESS_IMPLEMENTATION_PLAN.md)  
**Status:** `closed (bounded local verification — commit bundle pending)` —
Steps 1–9 (2026-10-15). Evidence authoritative on this machine; default branch
may not yet contain the verified package (see § Step 9 close-out).

---

## Step 1 — Pre-edit audit (historical snapshot)

**Recorded:** 2026-10-15  
**Purpose:** Freeze storage contract, repository surface, configuration, test mapping, and
workload identity before any migration, index, query, or repository changes.

**Stopping rule honored:** No migrations, indexes, query semantics, or repository behavior
were modified during Step 1.

### Environment snapshot (audit time)

| Field | Value |
| --- | --- |
| Git `HEAD` | `6d579304ca6b9afa00af71a168bf7faedf47c9d3` |
| Branch | (current checkout at audit) |
| Python | 3.14.5 |
| `fastapi` | 0.142.2 |
| `psycopg` | 3.3.6 |
| `pytest` | 9.1.1 |
| Docker Compose | v5.6.0 |
| Declared DB image | `pgvector/pgvector:pg16` ([`docker-compose.yml`](../../docker-compose.yml)) |
| `postgres` service (local) | **available** — `docker compose ps` reported `healthy` (host port mapped; connection URL not recorded) |
| `SSCRE_DATABASE_URL` | Set in local `.env` for development; **not copied into this evidence** |
| Live migration apply / test runs | **Not executed in Step 1** — inventory and mapping only |

Re-run environment capture before Step 2+ if `HEAD`, dependencies, or Compose layout change.

### Compose and documented startup path

| Check | Result |
| --- | --- |
| `postgres` service | `pgvector/pgvector:pg16`, healthcheck `pg_isready`, volume `postgres_data` |
| `migrate` service | Runs `sscre-migrate` after `postgres` healthy; `SSCRE_MIGRATIONS_DIR=/app/migrations` |
| `api` service | Depends on `migrate` success; `SSCRE_DATABASE_URL` to same DB |
| Local setup doc | [`POSTGRESQL_LOCAL_SETUP.md`](./POSTGRESQL_LOCAL_SETUP.md) — copy `.env`, `docker compose up -d postgres`, `sscre-migrate`, verify `vector` extension before vector DDL |

### Migration order and checksum validation

Migrations apply in lexicographic order (`000` … `013`). Filenames must match `NNN_name.sql`
with unique three-digit versions ([`src/sscre/migrate.py`](../../src/sscre/migrate.py)).

| Version | File | SHA-256 (file bytes) |
| --- | --- | --- |
| 000 | `000_schema_migrations.sql` | `cac8ade0962f91b97c57ab3958d52fff5e7d34b07815db1b12cfc18c7a8449dc` |
| 001 | `001_create_cache_entries.sql` | `0f5ebff3ceb8ffea593739c594334a3c184732714340a4d9f136fe2834949141` |
| 002 | `002_enable_pgvector.sql` | `31b02165d2159c659cfa62f60200a5977d4415cb1a027e080a511759251e083a` |
| 003 | `003_store_cache_embeddings.sql` | `1bd4bbc0882e73131ee1346de04bcc307c17587ec040dd7d202fcc3514a25160` |
| 004 | `004_store_cache_metadata.sql` | `21218fb4cad86cffeacc2ec77ae1ffe04445771c43e3016ba7140beb98b025d4` |
| 005 | `005_store_cache_ttl.sql` | `8b9e7a8d2fb43c55bf884575ba1b2a99b84be5b7d655d8a3177ce9b0a0e23af4` |
| 006 | `006_store_canonical_answers.sql` | `0aae17a614a356c03e75267a6ab5dc99276706c578416623b04ade342f43d9c7` |
| 007 | `007_cache_access_counters.sql` | `4cb6754622aa96da6819df8edfe810778f601bc4da567a0006fb906fe321766d` |
| 008 | `008_store_cache_sizes.sql` | `ee23e6c56a399df1c71bf0a2f9d323bef8f6eb0cb60042c3eebd2284c243dae0` |
| 009 | `009_backfill_legacy_ttl.sql` | `37d69bdc0880a684fc13e514dec855e2d71de3ae33bf71261d7057017d4217e0` |
| 010 | `010_cache_lifecycle_counters.sql` | `ec22fdbd9e4db40b313152525891fe52e18582f8c5040e3a1209f8ebdc0cb1dc` |
| 011 | `011_validate_sha256_hashes.sql` | `b51c3ec938af211341b8265b5591a160900b015d6c5011570393ee060dd99bfe` |
| 012 | `012_cache_tenant_namespace.sql` | `27f7f0b0d288ddbf83a62d83d267728127a569672531fba7b2813f26665825a8` |
| 013 | `013_cache_scoped_identity.sql` | `12b2d011c1db4de6f36e4b459181d76dc11885ced49c40a0e60b049b34b43a37` |

**Validation behavior:**

- `sscre-migrate` / `apply_migrations`: runs `000` bootstrap, applies each file once,
  stores `version` + `checksum` in `schema_migrations`.
- `validate_migration_state` (repository `__init__` and `check_ready`): requires every
  checked-in migration present, no unknown versions, checksum match; optional read-only
  mode skips `ALTER TABLE … ADD COLUMN IF NOT EXISTS checksum`.
- Legacy DBs with `checksum IS NULL` adopt the file checksum on migrate (see migrate.py).
- `ensure_pgvector_available`: extension `vector` must exist before vector columns
  (migration 002).

### Schema objects (pre-edit)

**Extensions:** `pgcrypto` (001), `vector` (002).

**Tables:**

| Table | Purpose |
| --- | --- |
| `schema_migrations` | Applied version + checksum + `applied_at` |
| `cache_entries` | Scoped exact/semantic cache rows |
| `canonical_answers` | Content-addressable answers (`answer_hash` PK) |
| `cache_lifecycle_counters` | Singleton row: dedup hits/savings, expirations, evictions |

**`cache_entries` columns (effective):** `id`, `query_hash`, `normalized_query`, `answer`
(legacy nullable after 006), `created_at`, `last_accessed_at`, `embedding` (`vector`),
`embedding_model`, `embedding_dimension`, `metadata` (jsonb), `ttl_expires_at`,
`hit_count`, `storage_bytes`, `canonical_answer_hash` → `canonical_answers`, `tenant_id`,
`namespace_id`, `content_query_hash`.

**Constraints (selected):**

| Name | Rule |
| --- | --- |
| `cache_entries_query_hash_unique` | Global unique `query_hash` (001) |
| `cache_entries_query_hash_length` | `length(query_hash) = 64` |
| `cache_entries_query_hash_sha256` | lowercase hex SHA-256 (011) |
| `cache_entries_embedding_metadata` | embedding triple all-null or all-set with dim > 0 (003) |
| `cache_entries_storage_bytes_nonnegative` | `storage_bytes >= 0` (008) |
| `cache_entries_content_query_hash_sha256` | content hash format (012) |
| `cache_entries_tenant_id_length` / `namespace_id_length` | 1–128 chars, no CR/LF (013) |
| `canonical_answers_*` | hash length, label enums, SHA-256 (006, 011) |
| FK | `cache_entries.canonical_answer_hash` → `canonical_answers.answer_hash` |

**Indexes:**

| Index | Definition |
| --- | --- |
| `idx_cache_entries_lru` | `(last_accessed_at, query_hash)` |
| `idx_cache_entries_expiration` | `(ttl_expires_at, query_hash)` |
| `idx_cache_entries_canonical_answer` | `(canonical_answer_hash)` |
| `idx_cache_entries_tenant_namespace` | `(tenant_id, namespace_id)` |
| `idx_cache_entries_scoped_content_unique` | **UNIQUE** `(tenant_id, namespace_id, content_query_hash)` |
| `idx_cache_entries_semantic_scope` | `(tenant_id, namespace_id, embedding_dimension)` WHERE `embedding IS NOT NULL` |

**No HNSW/IVFFlat vector index** in checked-in migrations (pre-edit).

### Repository surface (`PostgresExactCacheRepository`)

| Operation | Method | Notes |
| --- | --- | --- |
| Startup / readiness | `__init__`, `check_ready` | `validate_migration_state`; fail closed if migrations missing or checksum mismatch |
| pgvector guard | `ensure_pgvector_available` | Standalone extension check |
| Exact lookup | `get_by_query_hash` | Optional tenant/namespace; answer from `canonical_answers` via `canonical_answer_hash` COALESCE legacy `ce.answer` |
| Hit accounting | `record_hit` | `hit_count`, `last_accessed_at` |
| Vector search | `search_by_embedding` | Requires tenant + namespace; see vector contract below |
| Insert | `insert`, `_insert_cursor` | Upsert canonical answer; `cache_entries.answer` stored NULL; `UniqueViolation` → `DuplicateCacheEntryError` |
| Insert + cap | `insert_and_evict` | `pg_advisory_xact_lock(hashtext('sscre.cache.write'))`; scoped eviction via `only_query_hashes` |
| Eviction | `evict_to_limits`, `_evict_cursor` | LRU by `last_accessed_at`, `query_hash`; byte cap includes canonical answer bytes |
| Cleanup | `cleanup_expired` | `ttl_expires_at <= now()`; optional hash list + tenant scope |
| Delete | `delete_by_query_hash` | Removes unreferenced canonical rows |
| Stats | `storage_stats` | Optional tenant/namespace scope |
| Test/load scoping | `ScopedPostgresExactCacheRepository` | Forces `only_query_hashes` on `insert_and_evict` / `cleanup_expired` |
| Bulk test cleanup | `delete_entries_by_query_hashes` | Module helper |

**Failure harness:** `PostgresFailureInjectionRepository` in
[`postgres_failure_harness.py`](../../src/sscre/postgres_failure_harness.py) wraps the
repository for simulated drops on `lookup`, `insert`, `insert_and_evict`, `cleanup`,
`search`; optional live container restart when `SSCRE_WS8_LIVE_POSTGRES_RESTART` is set.

### Vector representation and runtime settings (pre-edit)

| Topic | Value |
| --- | --- |
| Column type | `vector` (unfixed dimension in DDL; dimension enforced per row + query param) |
| Serialization | Bracketed float list string for psycopg cast to `::vector` |
| Similarity operator | pgvector `<=>` (cosine distance) in `ORDER BY` |
| Reported similarity | `1 - (embedding <=> query_vector)` |
| Repository `max_top_k` default | `100` (`validate_vector_search` caps `top_k`) |
| Repository `embedding_dimension` default | `None` (no fixed dim at repo init; app uses `PostgresExactCacheRepository(url)` only) |
| App semantic defaults ([`config.py`](../../src/sscre/config.py) / Compose) | `SSCRE_SEMANTIC_TOP_K=5`, `SSCRE_SEMANTIC_SIMILARITY_THRESHOLD=0.95`, strategy `C`, semantic enabled |
| Cache caps (defaults) | `max_cache_entries=10000`, `max_cache_bytes=100000000`, answer/metadata/query byte limits per `Settings` |
| TTL policy | `stable` 30d, `semi_dynamic` 1d, `dynamic` optional; `allow_dynamic_entries` default false |
| Scope | `tenant_id` + `namespace_id` required for `search_by_embedding`; optional/required for other ops via `require_scoped_operations` |
| Expiry in SQL search | **Not filtered** in `search_by_embedding` WHERE clause — candidates may include expired rows; serving layer applies cache control (see `test_postgres_search_returns_expired_candidates`) |

### Parent Workstream 4 acceptance → verification mapping

| Parent criterion | Step | Primary verification (pre-edit) |
| --- | --- | --- |
| All PostgreSQL integration/failure/contention/multiprocess/load markers | 6 | `tests/test_postgres_*.py` + markers in [`ws8_postgres_helpers.py`](../../tests/ws8_postgres_helpers.py) |
| Least-privilege app role vs migration role | 3 | **Evidence row TBD** — SQL role setup (not run in Step 1) |
| Startup DDL / extension privilege boundary | 3 | Code: migrate at startup via `validate_migration_state` only (no apply in repo init); extension created in migration 002 |
| Canonical-answer integrity + tamper | 4 | `test_canonical_answer_deduplication_and_lifecycle_stats`, `test_postgres_integration` + **gap probe TBD** for privileged tamper SQL |
| Expired/disallowed filtering / scope safety | 5 | `test_postgres_search_returns_expired_candidates`, `test_expired_and_disallowed_cannot_win_concurrent_lookup`, `test_postgres_cache_scope.py`, failure-closed tests |
| Vector plans `EXPLAIN (ANALYZE, BUFFERS)` | 7 | Frozen protocol `ws4-vector-plan-v1` below; uses `search_by_embedding` SQL |
| HNSW/IVFFlat decision | 7 | No index in schema; decision deferred to measured plans |
| Caps, eviction, cleanup, uniqueness, transactions | 6, 8 | `test_insert_and_evict_enforces_postgres_entry_cap`, `test_postgres_eviction_scope.py`, `test_postgres_contention.py`, `test_ws8_pg_load_v1_two_cold_two_warm` |
| Version/checksum/hardware/workload metadata | 2, 7, 8, 9 | Recorded in Steps 2, 7, 8, and 9; load protocol remains bounded and synthetic |
| No universal production SLA claim | 9 | Stated in frozen load protocol limitation string |

### PostgreSQL test inventory (requires `SSCRE_DATABASE_URL`)

| Module | Marker / skip | Focus |
| --- | --- | --- |
| `test_postgres_integration.py` | skip if no URL | CRUD, vector top-k (dim **2** in tests), canonical dedup, expiry cleanup, connection loss, cap/evict |
| `test_postgres_vector.py` | unit-style pgvector check | Extension verification helpers |
| `test_postgres_cache_scope.py` | skip if no URL | Scoped exact/vector/stats/duplicate content per namespace |
| `test_postgres_eviction_scope.py` | skip if no URL | `only_query_hashes` eviction/cleanup contract |
| `test_postgres_failure_closed.py` | `ws8_postgres_failure_recovery` | Expired/unsafe/incompatible not served; bounded errors |
| `test_postgres_failure_recovery.py` | `ws8_postgres_failure_recovery` | Injected failures + optional live restart |
| `test_postgres_multiprocess_duplicate.py` | `ws8_postgres_multiprocess` | `ws8-multiprocess-dup-v1`, 2 processes × 3 runs |
| `test_postgres_contention.py` | `ws8_postgres_contention` | dup-key, mixed RW, evict cap, cleanup race, expired/disallowed |
| `test_postgres_pg_load.py` | `ws8_postgres_load` | `ws8-pg-load-v1` via [`experiments/workstream8_pg_load_v1.json`](../../experiments/workstream8_pg_load_v1.json) |

**Not in scope for WS4 workloads:** WS5 fresh held-out semantic labels, benchmark
gate JSON, or held-out evaluation protocol changes.

### Frozen workloads (identity locked at Step 1)

#### `ws4-correctness-v1` (deterministic)

Use existing pytest modules and their fixtures only — no new benchmark corpus.

| Parameter | Frozen value |
| --- | --- |
| Commands (Step 6 baseline) | `pytest -q tests/test_postgres_integration.py tests/test_postgres_vector.py tests/test_postgres_cache_scope.py tests/test_postgres_eviction_scope.py` plus conditional `-m ws8_postgres_*` runs from child plan |
| Embedding dimension in integration vector tests | **2** (explicit in `test_embedding_round_trip` / `test_top_k_embedding_search_returns_ranked_candidates`) |
| Query identity | Per-test UUID / hashed queries; teardown via `delete_entries_by_query_hashes` or scoped deletes |
| Semantic threshold / top_k | Application `Settings` defaults unless test overrides (`top_k=5`, threshold `0.95`) |
| Provider | `MockLLMClient` in API integration tests |

#### `ws4-vector-plan-v1` (bounded EXPLAIN — Step 7)

Measure the **production** query shape from `search_by_embedding` (no substitute SQL).

| Parameter | Frozen value |
| --- | --- |
| Query source | [`PostgresExactCacheRepository.search_by_embedding`](../../src/sscre/postgres_cache.py) parameterized SQL |
| Scope | `tenant_id = 'ws4-vector-plan'`, `namespace_id = 'ws4-vector-plan'` (dedicated probe rows only) |
| `embedding_dimension` | **2** (matches integration tests; avoids mixing dims in one probe table) |
| `embedding_model` filter | `NULL` (omit model filter in SQL — both `%s::text IS NULL` branches) |
| `top_k` | **5** (matches `SSCRE_SEMANTIC_TOP_K` default) |
| Row counts | **Two sizes:** `N=200` and `N=2000` scoped rows with distinct `content_query_hash`, synthetic normalized queries, random unit vectors length 2 |
| Plan capture | `EXPLAIN (ANALYZE, BUFFERS)` fresh-session observation and warm repeats per `N`; fresh connection does not clear PostgreSQL shared buffers and is not a true cold-cache run |
| Index expectation (pre-edit) | Sequential scan + sort on `<=>` unless planner chooses `idx_cache_entries_semantic_scope` filter only — **no vector ANN index** |

#### `ws8-pg-load-v1` (bounded load — Step 8, unchanged)

| Parameter | Frozen value (from JSON) |
| --- | --- |
| Config | [`experiments/workstream8_pg_load_v1.json`](../../experiments/workstream8_pg_load_v1.json) |
| Protocol id | `ws8-pg-load-v1` |
| Processes / workers | 1 / 1 |
| Warmup / requests | 8 / 32 |
| Concurrency | 4 |
| Caps | `max_cache_entries=8`, `max_cache_bytes=10000` |
| Passes | 2 configured cold + 2 configured warm; execution stopped after the first load pass under the registered rule |
| Limitation | JSON `limitation` field — not production capacity/SLA |

### Step 1 handoff

- [x] Pre-edit schema, checksums, repository map, settings, and workload IDs recorded.
- [x] Step 2 may begin: clean migrated database + recorded versions (no code changes required from Step 1).

---

## Step 2 — Clean pgvector database and migration evidence

**Recorded:** 2026-10-15  
**Git `HEAD`:** `6d579304ca6b9afa00af71a168bf7faedf47c9d3`

### Procedure (no secrets recorded)

```powershell
docker compose down -v
docker compose up -d postgres
# wait until `docker compose ps` shows postgres healthy
docker compose exec -T postgres psql -U sscre -d sscre -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
$env:PYTHONPATH = "src"
$env:SSCRE_DATABASE_URL = "<from local .env; not committed>"
python -m sscre.migrate --database-url $env:SSCRE_DATABASE_URL
python scripts/ws4_step2_verify.py
```

### Results

| Check | Result |
| --- | --- |
| Fresh volume | `docker compose down -v` then `up -d postgres` — volume `major_postgres_data` recreated |
| Compose health | `healthy` before probes |
| `vector` extension **before** migrate | **0 rows** (expected on empty DB; extension created by migration `002`) |
| `sscre-migrate` exit code | **0** |
| Applied migrations (CLI) | `000` through `013` (all fourteen) |
| PostgreSQL version | **16.15** (Debian pgdg12+2, x86_64) |
| pgvector `extversion` | **0.8.7** |
| `schema_migrations` rows | 14 versions; checksums match Step 1 file table |
| Required tables | `cache_entries`, `canonical_answers`, `cache_lifecycle_counters`, `schema_migrations` — present |
| `cache_entries` columns | 17 columns including `embedding`, scope ids, `canonical_answer_hash` (see probe JSON below) |
| Indexes on `cache_entries` | `cache_entries_pkey`, `cache_entries_query_hash_unique`, `idx_cache_entries_canonical_answer`, `idx_cache_entries_expiration`, `idx_cache_entries_lru`, `idx_cache_entries_scoped_content_unique`, `idx_cache_entries_semantic_scope`, `idx_cache_entries_tenant_namespace` |
| Vector operator `<=>` | **available** (`vector_cosine_distance_operator: true`) |
| Canonical FK enforcement | Insert with missing `canonical_answers` row → **rejected** (`fk_probe: rejected`) |
| `PostgresExactCacheRepository` init + `check_ready(read_only=True)` | **ok** (migration validator via repository) |

Probe output (redacted run):

```json
{
  "repository_init": "ok",
  "check_ready": "ok",
  "tables": { "cache_entries": true, "canonical_answers": true, "cache_lifecycle_counters": true, "schema_migrations": true },
  "cache_entries_constraint_count": 20,
  "vector_cosine_distance_operator": true,
  "fk_probe": "rejected"
}
```

Full column list and index names are in [`scripts/ws4_step2_verify.py`](../../scripts/ws4_step2_verify.py) output when re-run locally.

### Step 2 handoff

- [x] Migrated clean local `pgvector/pgvector:pg16` instance documented at declared scale.
- [x] Step 3 may begin: least-privilege migration vs application roles.

---

## Step 3 — Least-privilege startup boundary

**Recorded:** 2026-10-15  
**Git `HEAD`:** `6d579304ca6b9afa00af71a168bf7faedf47c9d3`

### Code change (runtime DDL removed)

`PostgresExactCacheRepository.__init__` now calls `validate_migration_state(...,
read_only=True)` so application startup only **SELECT**s `schema_migrations` (no
`ALTER TABLE … ADD COLUMN` on the app path). Migration checksum backfill remains on
`sscre-migrate` / `apply_migrations` only.

### Local roles (credentials out of band)

| Role | Purpose |
| --- | --- |
| `sscre_migrate` | Apply migrations; owns `public` tables on `sscre` after setup |
| `sscre_app` | Runtime DML + `SELECT` on `schema_migrations` only |

Passwords: optional `SSCRE_WS4_MIGRATE_PASSWORD` / `SSCRE_WS4_APP_PASSWORD` (defaults
are local-dev placeholders in the probe script only; not committed).

### Privilege boundary

| Capability | `sscre_migrate` | `sscre_app` |
| --- | --- | --- |
| `CREATE` on schema `public` | yes (via ownership / grants) | **no** |
| `INSERT` on `schema_migrations` | yes | **no** |
| `SELECT` on `schema_migrations` | yes | **yes** |
| DML on `cache_entries`, `canonical_answers`, `cache_lifecycle_counters` | yes | **yes** |

This is least privilege for the tested runtime operations, not a database-level
tenant-isolation boundary. The application role can issue DML against rows
outside a tenant or namespace if a caller bypasses the repository/application
scope checks; PostgreSQL row-level security was not enabled or tested.

**Extension bootstrap (deployment note):** `CREATE EXTENSION` for `vector` and `pgcrypto`
requires a **superuser** (or equivalent) on this image. Fresh databases must install
extensions once as the admin role before `sscre_migrate` runs as `sscre_migrate`
(migrations `001`/`002` use `CREATE EXTENSION IF NOT EXISTS`). The probe uses admin
bootstrap on database `sscre_migrate_probe` only; production procedure: superuser
bootstrap → migrate role → app role.

### Verification

```powershell
$env:PYTHONPATH = "src"
$env:SSCRE_DATABASE_URL = "<admin URL from local .env; not recorded>"
python scripts/ws4_step3_privilege_probe.py
```

| Check | Result |
| --- | --- |
| Migrate as `sscre_migrate` on `sscre` (already migrated) | exit **0**, `applied_migrations: []` |
| Migrate as `sscre_migrate` on fresh `sscre_migrate_probe` (extensions bootstrapped) | exit **0**, applied **`000`–`013`** (first run) |
| App runtime path (lookup, insert/evict, hit, vector, evict, cleanup) | **ok** |
| `GET /ready` with app repository | HTTP **200** |
| Stale checksum / missing migration at startup | `CacheRepositoryError` (**fail closed**) |
| App lacks `CREATE` / `INSERT` on `schema_migrations` after recheck | **confirmed** |
| `check_ready` after privilege recheck | **ok** |

Re-run probe JSON is authoritative for the current machine; do not commit role passwords.

### Step 3 handoff

- [x] Least-privilege startup classified; extension bootstrap documented.
- [x] Step 4 may begin: canonical-answer tamper probes.

---

## Step 4 — Canonical-answer integrity and tamper behavior

**Recorded:** 2026-10-15  
**Git `HEAD`:** `6d579304ca6b9afa00af71a168bf7faedf47c9d3`

### Code change

`PostgresExactCacheRepository` validates `hash_answer(answer) == canonical_answer_hash`
on **exact lookup** and **vector search** (`_assert_canonical_integrity`). Tampered
`canonical_answers` rows fail closed with `CacheRepositoryError` instead of serving
mismatched reusable content.

### Verification mapping

| Step 4 criterion | Evidence |
| --- | --- |
| Shared canonical dedup, stats, lifecycle | `test_canonical_answer_deduplication_and_lifecycle_stats`, `test_postgres_delete_removes_unreferenced_canonical_answer`, `test_cleanup_expired_removes_entry_and_updates_counter` |
| Reads use canonical store, not stale `cache_entries.answer` | `test_postgres_canonical_read_ignores_stale_denormalized_column` |
| Privileged SQL tamper | `test_postgres_tampered_canonical_answer_fails_closed_on_lookup`, `test_postgres_tampered_canonical_answer_fails_closed_on_vector_search` |
| Malformed / mismatched SHA-256 | `test_invalid_query_hash_is_rejected_by_database`, `test_postgres_cache_entry_rejects_mismatched_canonical_hash`, `test_database_errors_recorded_separately_from_validation` |
| Generation / insert failure without persist | `test_generation_failure_does_not_persist_an_entry`, `test_generation_failure_does_not_persist_entry_or_serve_cache`, `test_fr_gen_persist_insert_failure_does_not_persist` |
| DB failure + request correlation | `test_postgres_connection_loss_on_lookup_fails_closed` (`503`, `X-Request-ID`) |

### Commands (2026-10-15)

```powershell
$env:PYTHONPATH = "src"
$env:SSCRE_DATABASE_URL = "<local .env; not recorded>"
python -m pytest -q tests/test_postgres_integration.py -k "canonical or invalid_query or generation_failure or cleanup_expired or tampered or mismatched or delete_removes"
python -m pytest -q tests/test_postgres_failure_closed.py::test_generation_failure_does_not_persist_entry_or_serve_cache
python -m pytest -q tests/test_postgres_contention.py::test_database_errors_recorded_separately_from_validation
```

**Result:** **9 passed** on the integration filter above; failure-closed and contention
tests **passed** in the same session.

Tamper tests use privileged `UPDATE` on the live dev database and clean up via
`delete_entries_by_query_hashes` in fixtures.

### Step 4 handoff

- [x] Canonical integrity and tamper behavior verified at repository boundary.
- [x] Step 5 may begin: candidate filtering and scope safety.

---

## Step 5 — Candidate filtering and scope safety

**Recorded:** 2026-10-15  
**Git `HEAD`:** `6d579304ca6b9afa00af71a168bf7faedf47c9d3`

### Architecture (pre-edit, confirmed)

| Layer | Scope / eligibility |
| --- | --- |
| `search_by_embedding` SQL | `tenant_id`, `namespace_id`, `embedding_dimension`, optional `embedding_model`; orders by `<=>`; **no** `ttl_expires_at` or cache-control predicate |
| Application (`app.py`) | `cache_entry_is_reusable` / Strategy B–C filters expired, disallowed dynamic, and compatibility **after** retrieval |
| Exact path | Scoped `query_hash`; cache control on hit |

**Limitation:** When an expired row outranks a fresh row in SQL, a valid reusable candidate is reachable only if
`top_k` is large enough to include it in the retrieved set (measured below).
The safety result therefore applies to the application-served semantic path;
`search_by_embedding` is a candidate-retrieval API and may return an ineligible
candidate to a direct repository caller.

### Recall probe (`ws4-candidate-filter-v1`)

Command: `python scripts/ws4_step5_candidate_probe.py` (requires `SSCRE_DATABASE_URL`).

| Metric | Value |
| --- | --- |
| Population | 1 expired (best similarity), 1 fresh, 1 cross-namespace (excluded by SQL) |
| `db_top1_includes_expired` | **true** |
| `top_k_1_valid_reachable` | **false** |
| `top_k_2_valid_reachable` | **true** |
| `db_top2_reusable_count` | **1** (after in-process `evaluate_cache_control`) |

### Verification mapping

| Step 5 criterion | Evidence |
| --- | --- |
| Mixed fresh / expired / disallowed / cross-scope population | `ws4_step5_candidate_probe.py`, `test_postgres_candidate_filtering.py`, `test_expired_and_disallowed_cannot_win_concurrent_lookup` |
| SQL scope vs post-query filtering | Probe JSON + `test_postgres_search_returns_expired_candidates` (DB returns expired) |
| Expired / disallowed cannot win served result | `test_postgres_db_returns_expired_but_semantic_path_does_not_serve_it`, failure-closed + contention tests |
| Tenant / namespace predicates | `test_postgres_cache_scope.py`, `test_postgres_cross_namespace_candidate_not_in_scoped_search`, `test_postgres_requires_scope_predicates_when_configured` |
| Ordering / `top_k` / tie-break | `test_top_k_embedding_search_returns_ranked_candidates`, `test_postgres_vector_tie_breaks_on_query_hash` |

### Commands (2026-10-15)

```powershell
$env:PYTHONPATH = "src"
$env:SSCRE_DATABASE_URL = "<local .env; not recorded>"
python scripts/ws4_step5_candidate_probe.py
python -m pytest -q tests/test_postgres_candidate_filtering.py tests/test_postgres_cache_scope.py
python -m pytest -q tests/test_postgres_contention.py::test_expired_and_disallowed_cannot_win_concurrent_lookup
```

**Result:** probe JSON as above; **4 + 5 + 1** tests **passed** in this session.

### Step 5 handoff

- [x] Candidate filtering, scope isolation, and recall limitation documented.
- [x] Step 6 may begin: full PostgreSQL correctness matrix.

---

## Step 6 — PostgreSQL correctness and failure matrix

**Recorded:** 2026-10-15  
**Git `HEAD`:** `6d579304ca6b9afa00af71a168bf7faedf47c9d3`  
**Database:** local `pgvector/pgvector:pg16` (`docker compose ps` → **healthy**); `SSCRE_DATABASE_URL` from local `.env` (not recorded).

### Code fix (eviction-scope static guard)

`test_postgres_requires_scope_predicates_when_configured` now calls
`cleanup_expired(only_query_hashes=None)` so the Step 6 eviction-scope AST guard
still exercises the global-cleanup path that requires tenant/namespace predicates.

### Commands

```powershell
$env:PYTHONPATH = "src"
$env:SSCRE_DATABASE_URL = "<local .env; not recorded>"
python -m pytest -q tests/test_postgres_integration.py tests/test_postgres_vector.py tests/test_postgres_cache_scope.py tests/test_postgres_eviction_scope.py
python -m pytest -q -m ws8_postgres_failure_recovery
python -m pytest -q -m ws8_postgres_multiprocess
python -m pytest -q -m ws8_postgres_contention
```

### Results

| Suite | Command / marker | Result |
| --- | --- | --- |
| Core integration | four modules above | **32 passed** |
| Failure closed + recovery | `ws8_postgres_failure_recovery` | **12 passed**, **1 skipped** |
| Multiprocess duplicate | `ws8_postgres_multiprocess` | **1 passed** |
| Contention | `ws8_postgres_contention` | **6 passed** |

**Skipped (not counted as pass):** `tests/test_postgres_failure_recovery.py` live
container restart — requires `SSCRE_WS8_LIVE_POSTGRES_RESTART=1` (opt-in).

### Multiprocess protocol (`ws8-multiprocess-dup-v1`)

| Field | Value |
| --- | --- |
| Processes | **2** |
| Runs per session | **3** |
| Provider generations per run | **2** (one per process; in-process lock does not coordinate across processes) |
| `insert_success` / `insert_conflict` per run | **1** / **1** |
| `insert_error` | **0** |
| Surviving rows per `query_hash` | **1** |
| Teardown | `cleanup_query_hashes` in test `finally` |

### Contention coverage (`ws8_postgres_contention`)

| Test | Behavior verified |
| --- | --- |
| `test_ct_dup_key_duplicate_insert_is_deterministic` | Duplicate-key insert classified deterministically |
| `test_ct_mixed_rw_concurrent_insert_and_lookup` | Mixed concurrent insert + lookup |
| `test_ct_evict_cap_holds_under_concurrent_writes` | Entry cap under concurrent writes |
| `test_ct_cleanup_race_does_not_remove_fresh_entry` | Scoped cleanup race vs fresh row |
| `test_expired_and_disallowed_cannot_win_concurrent_lookup` | Expired/disallowed cannot win served path |
| `test_database_errors_recorded_separately_from_validation` | DB errors vs validation errors |

Tests use scoped `only_query_hashes` on shared-database deletes where applicable;
integration/multiprocess/contention modules clean owned hashes in fixtures/`finally`.

### Step 6 handoff

- [x] Correctness and failure matrix executed at declared scale (local single host).
- [x] Step 7 may begin: vector `EXPLAIN` plans and index decision.

---

## Step 7 — Vector query plans and index decision

**Recorded:** 2026-10-15  
**Git `HEAD`:** `6d579304ca6b9afa00af71a168bf7faedf47c9d3`  
**Protocol:** `ws4-vector-plan-v1` (frozen in Step 1 evidence).

### Query shape

Production SQL is duplicated in
[`scripts/ws4_step7_vector_plan_probe.py`](../../scripts/ws4_step7_vector_plan_probe.py)
(`VECTOR_SEARCH_SQL`) and matches
[`PostgresExactCacheRepository.search_by_embedding`](../../src/sscre/postgres_cache.py)
(`ORDER BY ce.embedding <=> %s::vector, ce.query_hash`, cosine distance via `<=>`).

### Declared workload

| Parameter | Value |
| --- | --- |
| `tenant_id` / `namespace_id` | `ws4-vector-plan` |
| `embedding_dimension` | **2** |
| `embedding_model` filter (SQL) | **NULL** (omit model predicate) |
| `top_k` | **5** |
| Row counts | **N=200**, **N=2000** scoped inserts per run |
| Query vector | `(1.0, 0.0)` |
| Fresh-session plan | New psycopg connection after `ANALYZE cache_entries` (not a cold-cache run) |
| Warm plan | Same connection, **2** consecutive `EXPLAIN` repeats |
| Similarity threshold | Application layer only (not in SQL) |

### Command

```powershell
$env:PYTHONPATH = "src"
$env:SSCRE_DATABASE_URL = "<local .env; not recorded>"
python scripts/ws4_step7_vector_plan_probe.py -o artifacts/ws4_step7_vector_plan_probe.json
```

Re-run JSON is authoritative for full `plan_text` and buffer lines.

### Environment (probe capture)

| Field | Value |
| --- | --- |
| PostgreSQL | **16.15** (Debian pgdg, x86_64) |
| pgvector | **0.8.7** |
| `shared_buffers` | **128MB** |
| `effective_cache_size` | **4GB** |
| `work_mem` | **4MB** |
| Host | Windows 11 client → Docker `pgvector/pgvector:pg16` volume |
| Processes / workers / connections | **1** / **1** / **1** |

### Plan summary

| N | Cache state | Planning (ms) | Execution (ms) | Scan | `idx_cache_entries_semantic_scope` | ANN index | Sort |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 200 | fresh session (not cold cache) | 1.151 | 0.655 | Seq Scan on `cache_entries` + filter | **not used** | **none** | top-N heapsort on `<=>` |
| 200 | warm repeat | 0.387 | 0.815 | Seq Scan on `cache_entries` + filter | **not used** | **none** | top-N heapsort |
| 2000 | fresh session (not cold cache) | 2.742 | 4.254 | Seq Scan on `cache_entries` + filter | **not used** | **none** | top-N heapsort |
| 2000 | warm repeat | 0.240 | 3.444 | Seq Scan on `cache_entries` + filter | **not used** | **none** | top-N heapsort |

All runs: **Rows Removed by Filter: 21** (non-probe rows in shared table); **5** rows returned (`LIMIT`).

`idx_cache_entries_semantic_scope` is a btree partial index on
`(tenant_id, namespace_id, embedding_dimension)`; the planner chose sequential scan
plus predicate filter at these cardinalities.

### Index decision

| Decision | Detail |
| --- | --- |
| Add HNSW / IVFFlat | **No** — not authorized without recall/build evidence |
| Measured reason | Seq scan + in-memory top-N sort remains sub-10 ms execution at N=2000, DIM=2, single connection on local Docker |
| Revisit when | Re-measure with deployed embedding dimensions, scoped cardinality, `top_k`, concurrency, and cache conditions before making a production-shaped ANN decision |
| Production SLA / capacity | **Out of scope** — one local bounded probe only; fresh-session results are not cold-cache results |

Probe rows are removed via `delete_entries_by_query_hashes` after each N.

### Step 7 handoff

- [x] Vector plans captured; ANN index deferred with recorded boundary.
- [x] Step 8 may begin: bounded load and cap/eviction verification.

---

## Step 8 — Caps, eviction, cleanup, uniqueness, and transactions

**Recorded:** 2026-10-15  
**Git `HEAD`:** `6d579304ca6b9afa00af71a168bf7faedf47c9d3`  
**Config:** [`experiments/workstream8_pg_load_v1.json`](../../experiments/workstream8_pg_load_v1.json)  
**Config SHA-256 (git blob):** `03156f99a7d3c56333af7f4199093b05172ce38c`

### Bounded load (`ws8-pg-load-v1`)

```powershell
$env:PYTHONPATH = "src"
$env:SSCRE_DATABASE_URL = "<local .env; not recorded>"
python -m pytest -q -m ws8_postgres_load
python -m sscre.load_test --config experiments/workstream8_pg_load_v1.json --output artifacts/operations/workstream8-pg-load-v1.json
python -m sscre.ops_evidence --output artifacts/operations/workstream8-operational-verification.json
```

| Check | Result |
| --- | --- |
| `pytest -m ws8_postgres_load` | **1 passed** (`test_ws8_pg_load_v1_two_cold_two_warm`) |
| Load artifact | [`artifacts/operations/workstream8-pg-load-v1.json`](../../artifacts/operations/workstream8-pg-load-v1.json) |
| Ops evidence artifact | [`artifacts/operations/workstream8-operational-verification.json`](../../artifacts/operations/workstream8-operational-verification.json) |

`workstream8-operational-verification.json` merges the **2026-10-15** load run
with frozen **2026-10-10** contention/multiprocess summaries (`evidence_note` on
those protocol blocks). The packaged `ws8-pg-load-v1` bottleneck is taken from
the load artifact's `bottleneck_analysis`, not a stale sidecar alone.

**Declared workload (JSON):** `process_count` / `worker_count` **1** / **1**; `warmup_requests` **8**;
`request_count` **32**; `concurrency` **4**; caps `max_cache_entries=8`, `max_cache_bytes=10000`;
2 cold + 2 warm passes configured; execution stopped after the first pass;
`isolate_queries=true` (scoped hash list for eviction/cleanup).

**Measured run (artifact header authoritative):**

| Field | Value |
| --- | --- |
| `stopped_reason` | **`p99_above_5x_p50`** (protocol stop after first completed cold pass) |
| Completed passes | **1** (`cold` only in `comparison.exact_cache`) |
| Cold pass `request_count` | **32** |
| Cold pass errors | **3** @ **9.375%** (`answer_too_large` / injection labels; within 10% stop band) |
| Provider data | **`synthetic`** (`bottleneck_analysis.environment.provider_data`) |
| `optimization_decision` | **`none`** (observation only) |

Not a production capacity or SLA claim; early stop is by design when tail latency exceeds the declared ratio.

### Property verification mapping (Steps 6 + 8)

| Step 8 criterion | Evidence |
| --- | --- |
| Entry / byte caps under write load | `test_insert_and_evict_enforces_postgres_entry_cap`, `test_ct_evict_cap_holds_under_concurrent_writes`, load caps + `evictions_delta` / `bytes_delta` in load JSON |
| Canonical-answer sharing / cleanup | `test_canonical_answer_deduplication_and_lifecycle_stats`, `test_postgres_delete_removes_unreferenced_canonical_answer` |
| Scoped eviction / cleanup only | `tests/test_postgres_eviction_scope.py`, load JSON `limitation` + `isolate_queries` |
| Expired / cleanup race vs fresh row | `test_ct_cleanup_race_does_not_remove_fresh_entry`, `test_expired_and_disallowed_cannot_win_concurrent_lookup` |
| Uniqueness vs DB vs validation errors | `test_ct_dup_key_duplicate_insert_is_deterministic`, `test_database_errors_recorded_separately_from_validation` |
| Transaction / locking assumption | `insert_and_evict` uses `pg_advisory_xact_lock(hashtext('sscre.cache.write'))` per connection transaction ([`postgres_cache.py`](../../src/sscre/postgres_cache.py)); rollback on failure closes transaction |

### Step 8 handoff

- [x] Bounded load executed and stopped after its first pass under
      `p99_above_5x_p50`; caps/eviction/uniqueness properties are tied to
      pytest plus the partial artifact.
- [x] Step 9 may begin: evidence close-out and parent WS4 checklist sync.

---

## Step 9 — Evidence close-out and handoff

**Recorded:** 2026-10-15  
**Verification `HEAD`:** `6d579304ca6b9afa00af71a168bf7faedf47c9d3`

### What this workstream authorizes

| Claim | Verdict |
| --- | --- |
| Local migrated `pgvector/pgvector:pg16` correctness at declared bounded scale | **Supported** (Steps 2–8) |
| Least-privilege app role after migrate + extension bootstrap procedure | **Supported** (Step 3) |
| Universal production SLA, multi-host capacity, managed PostgreSQL readiness | **Not authorized** |
| Multi-worker / multi-replica external deployment | **Not authorized** (WS2 multi-worker store still deferred; WS4 does not replace it) |

### Master verification index

| Step | Command | Result |
| --- | --- | --- |
| 2 | `docker compose down -v`; `up -d postgres`; `python -m sscre.migrate`; `python scripts/ws4_step2_verify.py` | **pass** (PG **16.15**, pgvector **0.8.7**, migrations `000`–`013`) |
| 3 | `python scripts/ws4_step3_privilege_probe.py` | **pass** (`sscre_migrate` / `sscre_app` boundary) |
| 4 | `pytest` integration filter (canonical/tamper); failure-closed + contention spot checks | **pass** (see Step 4) |
| 5 | `python scripts/ws4_step5_candidate_probe.py`; `test_postgres_candidate_filtering.py`; scope/contention | **pass** + documented `top_k` recall limitation |
| 6 | Four core modules + `-m ws8_postgres_failure_recovery` + multiprocess + contention | **51 passed**, **1 skipped** (live restart) |
| 7 | `python scripts/ws4_step7_vector_plan_probe.py -o artifacts/ws4_step7_vector_plan_probe.json` | **pass**; **no** HNSW/IVFFlat added |
| 8 | `-m ws8_postgres_load`; `sscre.load_test`; `sscre.ops_evidence` | **1 passed**; load **`stopped_reason`**: `p99_above_5x_p50` after 1 cold pass |
| Default suite | `python -m pytest -q` | **913 passed, 1 skipped, 21 deselected**; live PostgreSQL markers remain opt-in |

**Skipped (explicit, not pass):** `tests/test_postgres_failure_recovery.py` live
container restart — requires `SSCRE_WS8_LIVE_POSTGRES_RESTART=1`.

**Stopped scope (bounded load):** Protocol stop `p99_above_5x_p50` on first cold
pass; remaining warm/cold passes not executed (see Step 8 artifact).

### Inputs and artifacts (SHA-256, no secrets)

| Input / artifact | SHA-256 |
| --- | --- |
| Migrations `000`–`013` (file bytes) | Step 1 table |
| `experiments/workstream8_pg_load_v1.json` (git blob) | `03156f99a7d3c56333af7f4199093b05172ce38c` |
| `artifacts/ws4_step7_vector_plan_probe.json` (generated) | `b067644286016c8ea7f1b21aeedcfae7ffc5dcaececc388271c2773410b5fa58` |
| `artifacts/operations/workstream8-pg-load-v1.json` (generated) | `23f402ccf0980e8b6182e62ae8a9e153542b61f7f02fb7b9678d4a4c0dc5eee2` |
| `artifacts/operations/workstream8-bottleneck-v1.json` (generated, synced from load) | see load `bottleneck_analysis` |
| `artifacts/operations/workstream8-operational-verification.json` (generated) | `b9ffa28ecf5a1e8ce26b5cf16a3b712686b85e6af1e79b1219bda7c61a38782e` |

Re-run probes and pytest on this machine to refresh hashes after code or config
changes.

### `git status --short` at close-out (canonical WS4 package)

Recorded after doc/ops-evidence reconciliation (2026-10-15); refresh before commit.

```
 M artifacts/operations/workstream8-bottleneck-v1.json
 M artifacts/operations/workstream8-operational-verification.json
 M artifacts/operations/workstream8-pg-load-v1.json
 M docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md
 M docs/setup/POST_PHASE4_WS4_POSTGRESQL_READINESS_IMPLEMENTATION_PLAN.md
 M src/sscre/ops_evidence.py
 M src/sscre/postgres_cache.py
 M tests/test_ops_evidence.py
 M tests/test_postgres_integration.py
?? artifacts/ws4_step7_vector_plan_probe.json
?? docs/setup/POST_PHASE4_WS4_POSTGRESQL_READINESS_EVIDENCE.md
?? scripts/ws4_step2_verify.py
?? scripts/ws4_step3_privilege_probe.py
?? scripts/ws4_step5_candidate_probe.py
?? scripts/ws4_step7_vector_plan_probe.py
?? tests/test_postgres_candidate_filtering.py
```

Commit or push is **not** implied by this close-out.

### Parent linkage

- Child plan acceptance criteria: satisfied at declared local scale (see child plan).
- Parent Workstream 4 checklist updated in
  [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)
  § Workstream 4.
- Deployment-exit language: WS4 bounded PostgreSQL verification **does not**
  authorize multi-worker, multi-replica, managed-cloud, or SLA deployment claims.

### Step 9 handoff

- [x] Evidence file complete; parent WS4 synced; limitations and uncommitted paths recorded.
