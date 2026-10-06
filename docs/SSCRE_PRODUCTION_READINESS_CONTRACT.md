# SSCRE Production-Readiness Contract

Status: Milestone 10, Step 1
Scope: local development, automated tests, and a production-like single-node
deployment

This contract defines the runtime boundary for Milestone 10. It records the
current system surface and the behavior later implementation steps must
preserve. A target behavior is not considered implemented until its code and
tests provide evidence.

## 1. Runtime inventory

### Components

| Component | Current implementation | Role |
|---|---|---|
| FastAPI application | `src/sscre/app.py` | HTTP lifecycle and request pipeline |
| In-memory cache | `InMemoryExactCache` | Tests and no-database development |
| PostgreSQL cache | `PostgresExactCacheRepository` | Persistent exact/vector cache |
| Migration runner | `src/sscre/migrate.py` | Ordered, checksummed schema changes |
| LLM client | `MockLLMClient` | Deterministic generation in the current implementation |
| Embedding client | `FakeEmbeddingClient` | Deterministic semantic retrieval in the current implementation |
| Metrics | `MetricsCollector` | Request, cache, generation, and storage counters |
| PostgreSQL/pgvector | `docker-compose.yml` | Persistent relational and vector storage |

The provider clients are interfaces at the application boundary. Replacing the
current deterministic clients with real providers is outside this step.

### HTTP surface

| Method | Path | Current purpose | Contract |
|---|---|---|---|
| GET | `/health` | Process health | Public liveness probe; no secrets or dependency details |
| GET | `/ready` | Dependency and schema readiness | Public readiness probe; returns `503` when required PostgreSQL or migrations are unavailable |
| POST | `/v1/query` | Query, reuse, or generate | Public application operation; bounded request and response |
| GET | `/v1/cache/stats` | Storage and request statistics | Administrative read; requires `Authorization: Bearer <admin-token>` |

No purge, cleanup, migration-inspection, or evaluation-trigger endpoint is
currently exposed. Any future administrative endpoint must be added to the
protected admin surface rather than treated as a public query endpoint.

### Database migrations

The checked-in migration sequence is `000_schema_migrations.sql` through
`011_validate_sha256_hashes.sql`. The runner requires:

- `NNN_name.sql` filenames with unique three-digit versions
- every checked-in migration to be applied
- no unknown database migration versions
- matching SHA-256 checksums
- `000_schema_migrations.sql` as the bootstrap migration

`PostgresExactCacheRepository` validates this state before construction.
`sscre-migrate` is the supported way to apply migrations.

### Configuration

`Settings.from_environment()` currently reads:

| Variable | Purpose | Current default |
|---|---|---|
| `SSCRE_DATABASE_URL` | PostgreSQL connection | unset; in-memory cache is selected |
| `SSCRE_RUNTIME_PROFILE` | `test`, `development`, or `production` | `development` |
| `SSCRE_LOG_LEVEL` | Structured logger verbosity | `INFO` |
| `SSCRE_SEMANTIC_ENABLED` | Enable embedding retrieval | `true` |
| `SSCRE_SEMANTIC_STRATEGY` | Strategy B or C | `B` |
| `SSCRE_SEMANTIC_TOP_K` | Candidate count | `5` |
| `SSCRE_SEMANTIC_SIMILARITY_THRESHOLD` | Similarity threshold | `0.95` |
| `SSCRE_CACHE_STABLE_TTL_SECONDS` | Stable TTL | `2592000` |
| `SSCRE_CACHE_SEMI_DYNAMIC_TTL_SECONDS` | Semi-dynamic TTL | `86400` |
| `SSCRE_CACHE_DYNAMIC_TTL_SECONDS` | Optional dynamic TTL | unset |
| `SSCRE_CACHE_ALLOW_DYNAMIC_ENTRIES` | Permit dynamic entries | `false` |
| `SSCRE_CACHE_MAX_ANSWER_BYTES` | Maximum answer size | `65536` |
| `SSCRE_CACHE_MAX_METADATA_BYTES` | Maximum metadata size | `8192` |
| `SSCRE_CACHE_MAX_QUERY_BYTES` | Maximum normalized query size | `32768` |
| `SSCRE_CACHE_MAX_ENTRIES` | Entry cap | `10000` |
| `SSCRE_CACHE_MAX_BYTES` | Storage cap | `100000000` |
| `SSCRE_ADMIN_TOKEN` | Administrative bearer credential | unset; admin operations fail closed |
| `SSCRE_ADMIN_READ_TOKEN` | Optional read-only admin credential | unset |
| `SSCRE_ADMIN_TOKEN_EXPIRES_AT` | ISO-8601 admin-token expiry | unset outside production |
| `SSCRE_ADMIN_READ_TOKEN_EXPIRES_AT` | ISO-8601 read-token expiry | unset |

Compose additionally reads `POSTGRES_DB`, `POSTGRES_USER`, and
`POSTGRES_PASSWORD`. The example values are for local development only.

### External dependencies

- PostgreSQL with the `pgvector` extension
- the filesystem containing the checked-in migration files
- an embedding provider when semantic retrieval is enabled
- an LLM provider for generated responses
- the process clock for TTL and latency decisions

## 2. Runtime profiles

| Profile | Repository | Clients | Intended use |
|---|---|---|---|
| Test | Injected repository or in-memory | Injected fakes | Unit and integration tests |
| Local development | In-memory unless `SSCRE_DATABASE_URL` is set | Current deterministic clients | Fast development and demonstrations |
| Production-like | PostgreSQL with validated migrations | Explicitly configured providers | Compose and load testing |

Profiles must not silently weaken safety defaults. In particular, dynamic
entries remain disabled, TTL checks remain active, storage limits remain
enforced, and a dependency error never becomes permission to reuse a cache
entry. A production-like profile must not use the development fake clients
implicitly.

The `production` profile requires a database URL, an admin token of at least
16 characters, and explicitly injected provider clients. The default mock LLM
and fake embedding clients are rejected in that profile. The Compose
development profile is intentionally suitable for deterministic local
demonstrations; it is not evidence of provider production readiness.

Environment variables are parsed and validated at startup. Constructor
settings used by tests or embedding applications take precedence over
environment defaults where the API exposes an explicit override. Secret
rotation is performed by replacing `SSCRE_ADMIN_TOKEN` in the environment and
restarting the API; the old token is not accepted after restart and secrets
are never logged.

## 3. Health and readiness contract

### Liveness

`GET /health` indicates that the HTTP process is running and can execute the
health handler. It must:

- return a small non-secret response;
- not claim that PostgreSQL, migrations, embedding, or generation are ready;
- remain usable by orchestration without administrative credentials;
- avoid returning stack traces, connection strings, or provider details.

The current response is `{"status": "ok"}`. `/ready` is the separate readiness
check required before a production-like PostgreSQL service can accept traffic.
The in-memory profile reports `{"status": "ready", "repository": "memory"}`;
the PostgreSQL profile validates connectivity and migration state with a
one-second connection budget using read-only validation and reports a bounded
`503` on failure.

### Readiness target

Readiness must be false when any required condition is unavailable:

- PostgreSQL cannot be reached within its health-check budget;
- the migration set is incomplete, unknown, or checksum-invalid;
- a required production dependency is not configured;
- the configured provider or repository cannot satisfy its startup contract.

An in-memory development profile may be ready without PostgreSQL because the
database is not a required dependency in that profile. Readiness must identify
the selected profile without exposing sensitive configuration.

## 4. Failure behavior contract

| Failure | Cache reuse | Response target |
|---|---|---|
| Exact or semantic repository lookup fails | Never reuse | `503` with request ID |
| Embedding fails before retrieval | Never reuse semantic candidate | Generate if possible; otherwise controlled generation error |
| Safety validator fails | Never reuse candidate | Generate if possible |
| Candidate is expired or policy-ineligible | Never reuse | Continue to generation |
| Generation fails or times out | No cache response | `502` with request ID |
| Generated answer is too large or otherwise uncacheable | No cache write | Return the valid generated answer |
| Cache insert, deduplication, or eviction fails after generation | No newly written cache hit | Return the valid generated answer where possible and record the failure |
| Cache statistics/admin operation fails | No effect on query safety | `503` with bounded detail |
| Authentication or authorization fails | No admin data or mutation | `401` or `403` with bounded detail |

All cache reuse remains failure-closed: infrastructure failure, missing
metadata, validator uncertainty, or unavailable freshness state cannot yield a
cache hit. Status codes, request deadlines, dependency timeouts, and bounded
executor capacity are enforced at the request boundary.

## 5. Administrative access

Administrative endpoints require a bearer token configured through
`SSCRE_ADMIN_TOKEN` or the optional read-only `SSCRE_ADMIN_READ_TOKEN`.
Credentials are compared with `hmac.compare_digest`; they are never logged or
returned. Missing or malformed credentials return `401` with a bearer
challenge, invalid or expired credentials return `401`, and an unconfigured
admin secret returns bounded `503` rather than exposing the endpoint.
Authorization is evaluated separately from authentication through endpoint
scopes; the current stats endpoint requires `cache:read`. Future mutation
endpoints must require `cache:write`. Production requires an expiry for the
full admin token.

`/health` and `/ready` remain public orchestration probes and expose no admin
data. Admin responses contain only bounded storage and metric summaries.

## 6. Timeout budgets

These are the production-like budgets enforced by the current dependency
boundary. They remain configurable through `Settings` and environment
variables.

| Operation | Budget |
|---|---:|
| Entire `/v1/query` request | 30 seconds |
| Embedding call | 5 seconds |
| LLM generation | 25 seconds |
| Individual PostgreSQL lookup/search/write | 2 seconds |
| Liveness check | 1 second |
| Readiness/database check | 1 second |
| Administrative read | 5 seconds |
| Administrative mutation or bounded cleanup | 10 seconds |

The request budget includes all retries and wrapper work. No automatic retries
are currently enabled, so non-idempotent cache mutations are not retried.
Timed-out work is submitted through a bounded executor; pending work is
cancelled where possible, and the request/generation lock is released by its
guard before the request exits.

## 7. Resource and logging bounds

The following existing bounds remain the baseline:

- normalized query: 32 KiB;
- generated answer: 64 KiB for cache eligibility;
- serialized metadata: 8 KiB;
- semantic top-K: positive and repository-bounded, with candidate traces capped
  at 100 by `MAX_TRACE_CANDIDATES`;
- cache entries and bytes: `10000` entries and `100000000` bytes by default.

Production-like behavior additionally requires:

- response bodies to contain only bounded answer and trace data;
- structured logs to contain request ID, outcome, bounded reason, status, and
  latency fields;
- no API keys, passwords, connection strings, hidden reasoning, full raw
  provider payloads, or unnecessary full prompts in logs;
- exception details to remain server-side and bounded;
- load-test and admin output to use summaries rather than unbounded cache dumps.

## 8. Deployment assumptions

- The initial production-like deployment is one service instance with one
  PostgreSQL instance.
- PostgreSQL is the source of truth for shared cache state when configured.
- Multiple API processes may issue concurrent cache writes; repository
  uniqueness constraints and `insert_and_evict()` remain authoritative.
- The in-process generation lock prevents duplicate generation only within one
  process. It is not a distributed lock.
- Horizontal scaling, distributed rate limiting, multi-tenant isolation,
  secret rotation infrastructure, and failover PostgreSQL are outside this
  step unless later measurements justify them.
- PostgreSQL data uses the Compose named volume for local persistence; tests
  must use isolated databases or disposable state.

## 9. Evidence map

| Contract area | Current evidence | Remaining implementation |
|---|---|---|
| API and request behavior | `src/sscre/app.py`, existing API tests | Clean-container startup |
| Configuration | `src/sscre/config.py`, `.env.example`, config tests | Production-profile exercise |
| Migration integrity | `src/sscre/migrate.py`, `src/sscre/postgres_cache.py`, `/ready`, `tests/test_migrate.py`, `tests/test_health.py` | Clean-container startup with a fresh database volume |
| Cache safety and bounds | cache-control, eviction, and integration tests | Failure-path and load evidence |
| Local database service | `docker-compose.yml`, `Dockerfile`, `.dockerignore`, `requirements-docker.txt` | Clean-stack startup and runtime exercise |

Steps 1–5 are represented by this contract when the documented behavior is
reviewed. Runtime enforcement and tests are evidence for the corresponding
implementation steps; load measurements remain subsequent work.

## 10. Compose operations

The production-like local stack uses the PostgreSQL service, a one-shot
`migrate` service, and the API service:

```text
postgres healthy → migrate completed successfully → api starts
```

From a clean checkout:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The API is available at `http://localhost:8000` by default. The API container
uses the Compose service name `postgres` in its database URL; the host-facing
`SSCRE_DATABASE_URL` in `.env.example` is for local non-container execution.

Useful lifecycle commands:

```powershell
docker compose logs -f api
docker compose down
docker compose down -v       # destroy local PostgreSQL data
docker compose run --rm migrate
```

The migration service is the only service that applies checked-in migrations.
The PostgreSQL image is not given raw migration init scripts, so a persistent
volume cannot silently bypass the ordered/checksummed migration runner.

## 11. Load-test operations

The deterministic development load test runs cold-cache and warm-cache passes
with bounded concurrency, entry/byte caps, exact and semantic reuse cases,
dynamic queries, oversized answers, synthetic embedding/generation failures,
and eviction candidates:

```powershell
python -m sscre.load_test `
  --config experiments/milestone10_load_v1.json `
  --output experiments/milestone10_load_v1_report.json
```

The report stores aggregate p50/p95/p99 latency, throughput, errors, sources,
reasons, storage totals, workload labels, and bounded per-request results.
Provider latency and failure values are synthetic and explicitly labeled; the
report is not a capacity claim for a real provider or PostgreSQL deployment.
