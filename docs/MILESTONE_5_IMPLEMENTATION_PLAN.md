# Milestone 5 Implementation Plan — PostgreSQL Persistence

## Goal

Replace the process-local exact cache with a PostgreSQL-backed repository while
preserving the current API behavior:

```text
POST /v1/query
→ normalize and hash query
→ PostgreSQL exact lookup
→ generate on miss
→ insert generated answer
→ return cache/generated source and metrics
```

Milestone 5 is persistence work only. Semantic retrieval, pgvector embeddings,
TTL, eviction, and benchmark evaluation remain later milestones.

## Learning objectives

- [ ] Tables, primary keys, unique constraints, and indexes
- [ ] Transactions and commit/rollback behavior
- [ ] Parameterized SQL and SQL injection prevention
- [ ] Repository interfaces and dependency boundaries
- [ ] PostgreSQL integration testing
- [ ] Persistence across API restarts

## Implementation steps

### 1. Choose the database boundary

- [x] Add the PostgreSQL driver and use versioned SQL migration files.
- [x] Read the connection string from an environment variable.
- [x] Keep the API dependent on a repository interface, not SQL details.
- [x] Preserve the in-memory repository as a fast unit-test double.

### 2. Start PostgreSQL locally

- [x] Add a minimal Docker Compose service for PostgreSQL.
- [x] Use a project-local database, user, and password for development only.
- [x] Add a health check and document the start/stop commands.
- [x] Do not commit real credentials.

### 3. Create the first migration

- [x] Create the smallest schema required for exact caching:

```sql
CREATE TABLE cache_entries (
    id UUID PRIMARY KEY,
    query_hash VARCHAR(64) NOT NULL,
    normalized_query TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cache_entries_query_hash_length CHECK (length(query_hash) = 64),
    CONSTRAINT cache_entries_query_hash_unique UNIQUE (query_hash)
);
```

Use a unique constraint on `query_hash` so concurrent inserts cannot create
duplicate exact entries.

- [x] Apply the migration to the local PostgreSQL database.
- [x] Verify the table and columns exist.

### 4. Define the repository interface

The repository should expose only the operations required by the orchestrator:

- [x] `get_by_query_hash(query_hash)`
- [x] `insert(entry)`

Define clear behavior for:

- [x] cache miss returns `None`
- [x] existing hash is not overwritten
- [x] database connection failure uses `CacheRepositoryError`
- [x] duplicate insert raises `DuplicateCacheEntryError`
- [x] API returns controlled HTTP 503 responses for repository failures

All SQL must use bound parameters.

### 5. Implement PostgreSQL lookup and insert

- [x] Add a PostgreSQL repository implementation.
- [x] Map database rows to the existing `CacheEntry` model.
- [x] Keep database connections short-lived or pooled according to the chosen
  driver.
- [x] Update `last_accessed_at` on a successful hit.
- [x] Avoid storing failed LLM responses.

### 6. Connect the API through dependency injection

- [x] Make the application factory accept a repository.
- [x] Use the PostgreSQL repository in the local runtime configuration.
- [x] Continue using the in-memory repository in unit tests.
- [x] Keep cache hit/miss metrics and failure behavior unchanged.

### 7. Add integration tests

Integration tests should run against a real PostgreSQL instance and verify:

- [x] inserting and retrieving an entry
- [x] exact hash lookup
- [x] missing hash behavior
- [x] duplicate hash protection
- [x] parameterized text containing SQL-like characters
- [x] data remains available after repository/API restart
- [x] generation failures do not create rows

Tests must be isolated and clean up their data.

- [x] Tests are isolated and clean up their data.

### 8. Update documentation and trackers

- [x] Document database setup and test commands.
- [x] Add the persistence step to the request-flow documentation.
- [x] Check completed Milestone 5 items in the learning guide and project tracker
  when implementation and evidence exist.
- [x] Update `docs/README.md` to point to Milestone 6 only after verification.

## Verification checklist

- [x] PostgreSQL starts locally
- [x] Migration applies successfully
- [x] Unit tests pass with the in-memory repository
- [x] Integration tests pass against PostgreSQL (`.venv\Scripts\python.exe -m pytest -q tests/test_postgres_integration.py`; 6 passed with `SSCRE_DATABASE_URL` set)
- [x] `POST /v1/query` returns a generated answer on the first request
- [x] A new API instance returns `source = "cache"` for the same request
- [x] Failed generation is not persisted
- [x] No credentials are committed
- [x] No SQL is built through string concatenation
- [ ] Linter reports no errors (no linter is currently configured)

## Completion criteria

Milestone 5 is complete when the exact-cache behavior survives creating a new
API instance, and the integration tests provide evidence that the PostgreSQL
repository—not the in-memory process state—served the cached answer.
