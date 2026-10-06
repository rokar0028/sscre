# Milestone 10 Implementation Plan — Production and Interview Readiness

## Goal

Harden the SSCRE research service so it can be run reproducibly as a small
production-like system, exercised under failure and load, and defended clearly
in an interview:

```text
docker compose up
        ↓
database readiness + ordered migrations
        ↓
authenticated administrative operations
        ↓
POST /v1/query
        ↓
bounded dependency calls with controlled failure behavior
        ↓
safe cache reuse or generated response
        ↓
structured metrics and latency measurements
        ↓
load-test and final experiment evidence
```

This milestone packages and verifies the behavior implemented in Milestones 1–9.
It does not add dual-model comparison, cross-encoders, adaptive thresholds,
multi-region deployment, or production-scale infrastructure without a measured
hypothesis.

## Learning objectives

- [ ] Docker images, Compose services, networks, volumes, and health checks
- [ ] Liveness versus readiness and dependency-aware startup
- [ ] Timeout budgets, cancellation, retries, and failure amplification
- [ ] Authentication and authorization for administrative endpoints
- [ ] Secure configuration and secret handling
- [ ] Integration-test isolation and deterministic failure injection
- [ ] Load-test design and representative workload modeling
- [ ] Latency distributions, warm-up effects, and p50/p95/p99
- [ ] Capacity limits, bottleneck identification, and backpressure
- [ ] Reproducible experiment reports and limitations
- [ ] Explaining safety, freshness, storage, and reliability trade-offs

## Implementation steps

### 1. Define the production-readiness contract

- [x] Inventory the current runtime components, endpoints, migrations,
  configuration variables, and external dependencies.
- [x] Define local development, test, and production-like profiles without
  silently changing safety defaults.
- [x] Define liveness behavior when the process is running.
- [x] Define readiness behavior when PostgreSQL, migrations, or required
  dependencies are unavailable.
- [x] Define which failures return a controlled generated response, which fail
  closed for cache reuse, and which return an HTTP error.
- [x] Define timeout budgets for request handling, embedding, generation,
  repository operations, health checks, and administrative work.
- [x] Define bounded request, response, trace, and log sizes.
- [x] Keep credentials, hidden provider data, and raw answers out of logs.
- [x] Document assumptions about single-process versus multi-process
  deployment and concurrent cache writes.

Evidence: `docs/SSCRE_PRODUCTION_READINESS_CONTRACT.md` inventories the current
runtime and maps the target contract to `src/sscre/app.py`,
`src/sscre/config.py`, `src/sscre/migrate.py`,
`src/sscre/postgres_cache.py`, `docker-compose.yml`, `.env.example`, and
existing tests. Runtime enforcement and new failure-path tests remain in later
steps.

### 2. Build a reproducible Docker Compose environment

- [x] Add an application image with a pinned, reproducible Python dependency
  installation.
- [x] Run the application as a non-root user where practical.
- [x] Add the API service to `docker-compose.yml` with explicit environment
  configuration and a dependency on database readiness.
- [x] Preserve PostgreSQL data through a named volume while keeping test
  environments disposable.
- [x] Ensure the container starts only after the migration and schema
  contract is valid.
- [x] Avoid baking secrets into the image, Compose file, or source tree.
- [x] Add a small `.env.example` covering required database and application
  settings without real credentials.
- [x] Document startup, shutdown, logs, reset, and migration commands.
- [ ] Verify that a clean checkout can start the service using documented
  commands.

Evidence: `Dockerfile`, `.dockerignore`, `requirements-docker.txt`, updated
`docker-compose.yml`, `.env.example`, and Compose operation commands in
`docs/SSCRE_PRODUCTION_READINESS_CONTRACT.md`. `docker compose config` and
`docker compose build` pass. Full clean-stack startup remains unchecked until
the local PostgreSQL container can be started and exercised. A startup attempt
reached the migration gate but the existing named volume rejected the current
password; the volume was not destroyed.

### 3. Implement database health and migration readiness

- [x] Add a database connectivity check with a short timeout.
- [x] Distinguish process liveness from database readiness.
- [x] Validate migration completion, ordering, and checksums before accepting
  PostgreSQL-backed traffic.
- [x] Return a bounded, non-secret health response.
- [x] Ensure a failed health check cannot produce a false-ready status.
- [x] Define behavior for a database that is restarting, unavailable, or has
  an incomplete migration.
- [x] Keep cache reuse failure-closed when readiness or schema validation fails.
- [x] Add tests for healthy, unavailable, and incompatible database states.

Evidence: `/health` and `/ready` in `src/sscre/app.py`,
`check_ready()` in `src/sscre/postgres_cache.py`, bounded migration validation
in `src/sscre/migrate.py`, Compose readiness wiring, and
`tests/test_health.py`/`tests/test_migrate.py`. Targeted tests → 7 passed,
13 skipped PostgreSQL tests; full suite → 183 passed, 13 skipped. Container
startup remains blocked by the pre-existing local PostgreSQL volume password
mismatch documented under Step 2.

### 4. Add timeout and controlled dependency-failure handling

- [x] Add configurable timeouts around LLM generation, embedding, database
  lookup, database writes, statistics, and cleanup operations.
- [x] Preserve cancellation and avoid holding request or generation locks past
  the configured budget.
- [x] Do not retry non-idempotent cache mutations blindly.
- [x] Add bounded retries only where the operation and failure mode justify
  them, with backoff and a clear maximum attempt count.
- [x] Ensure embedding failure never turns a generated answer into an unsafe
  cache hit.
- [x] Ensure repository failure never produces a cache hit or bypasses TTL and
  compatibility checks.
- [x] Return a valid generated response when generation succeeds but caching
  fails and policy allows it.
- [x] Return controlled status codes and request IDs for unavailable required
  dependencies.
- [x] Record timeout, retry, and dependency-failure reasons in bounded metrics.
- [x] Test slow, raising, malformed, and partially successful fake clients.

Evidence: timeout settings in `src/sscre/config.py` and `.env.example`,
bounded execution and executor-capacity backpressure in `src/sscre/app.py`,
provider validation in `src/sscre/llm.py`, and failure metrics in
`src/sscre/metrics.py`.
`tests/test_exact_cache.py` covers slow generation, malformed generation,
repository failure/timeout, and cache-write failure. Targeted tests → 33
passed. No automatic retries are enabled for non-idempotent cache mutations;
retry policy is therefore bounded at zero until a justified idempotent case
exists.

### 5. Protect administrative operations

- [x] Identify administrative endpoints such as cache statistics, purge,
  cleanup, migration inspection, or evaluation triggers.
- [x] Require authentication for every administrative operation.
- [x] Enforce authorization separately from authentication for read and
  mutation operations.
- [x] Use constant-time comparison or a standard authentication mechanism for
  configured credentials or tokens.
- [x] Reject missing, malformed, expired, and insufficient-privilege
  credentials with bounded responses.
- [x] Do not expose database URLs, provider keys, full prompts, answers, or
  internal exception details through admin responses.
- [x] Keep `/health` usable by orchestration without exposing admin data.
- [x] Add tests proving unauthenticated and unauthorized requests cannot read
  or mutate protected cache state.
- [x] Document the deliberately limited scope of the admin surface.

Evidence: bearer authentication and scope authorization in `src/sscre/app.py`,
`SSCRE_ADMIN_TOKEN` configuration in `src/sscre/config.py` and
`.env.example`, protected `/v1/cache/stats`, public `/health` and `/ready`,
optional read-only credentials and expiry validation, and `tests/test_admin.py`
plus the endpoint inventory in
`docs/SSCRE_PRODUCTION_READINESS_CONTRACT.md`. The current admin surface has
only a read operation; no mutation endpoint exists yet.

### 6. Harden configuration and operational defaults

- [x] Validate all environment-derived values before application startup.
- [x] Keep semantic safety, dynamic-entry, TTL, answer-size, and storage-cap
  defaults conservative.
- [x] Add explicit configuration for dependency timeouts and log verbosity.
- [x] Fail startup for missing required production secrets rather than using
  unsafe fallbacks.
- [x] Keep test-only fake clients and development shortcuts out of the
  production profile.
- [x] Ensure error responses and logs do not disclose secret configuration.
- [x] Document configuration precedence and safe rotation behavior.
- [x] Add tests for invalid, missing, boundary, and conflicting settings.

Evidence: runtime profiles, startup validation, timeout/log-level settings,
and fake-provider guards in `src/sscre/config.py` and `src/sscre/app.py`;
configuration reference in `.env.example` and
`docs/SSCRE_PRODUCTION_READINESS_CONTRACT.md`; and expanded tests in
`tests/test_config.py` and `tests/test_admin.py`.

### 7. Add integration coverage for failure paths

- [x] Test API behavior with a real or containerized PostgreSQL service where
  available.
- [x] Test startup with missing, incomplete, and checksum-invalid migrations.
- [x] Test database restart and connection loss during lookup and mutation.
- [x] Test embedding timeout/failure, generation timeout/failure, and malformed
  provider responses.
- [x] Test expired, incompatible, oversized, and over-cap cache entries under
  request load.
- [x] Test concurrent requests for the same query and duplicate answer.
- [x] Test that no failure path serves an unsafe, expired, or unauthorized
  cache result.
- [x] Test request IDs, status codes, bounded response bodies, and structured
  failure metrics.
- [x] Keep integration tests isolated, repeatable, and safe to run repeatedly.

Evidence: `tests/test_failure_paths.py`, existing TTL, safety, eviction,
admin, and PostgreSQL integration tests, plus migration/readiness tests. Full
suite → 183 passed, 13 skipped; PostgreSQL skips are reported when
`SSCRE_DATABASE_URL` is unavailable. The available tests use disposable
in-memory repositories or unique query identifiers; no database volume was
destroyed.

### 8. Design and run a representative load test

- [x] Define a workload containing exact hits, safe semantic hits, unsafe and
  uncertain candidates, misses, dynamic queries, oversized answers, and
  dependency failures.
- [x] Define warm-up, steady-state, duration, concurrency, and dataset
  version before running measurements.
- [x] Include cache-empty and cache-warm runs.
- [x] Include configured entry and byte caps so eviction behavior is exercised.
- [x] Measure request throughput, errors, cache outcomes, dependency calls,
  storage growth, and eviction activity.
- [x] Keep generated-provider behavior deterministic or label synthetic
  provider latency and token values explicitly.
- [x] Save machine-readable workload configuration and raw results.
- [x] Do not tune thresholds against the final held-out evaluation workload.

Evidence: `sscre-load-test`/`sscre.load_test`, versioned
`experiments/milestone10_load_v1.json`, and generated
`experiments/milestone10_load_v1_report.json`. The report contains cold and
warm passes at concurrency 4 with p50/p95/p99 latency, throughput, error
rates, cache sources, storage totals, workload labels, and raw bounded
per-request results. Provider failures and latency are synthetic and labeled.

### 9. Measure latency and identify the first bottleneck

- [x] Report p50, p95, and p99 total request latency.
- [x] Break latency down into preprocessing, embedding, retrieval, safety
  evaluation, generation, persistence, and response serialization where
  instrumentation supports it.
- [x] Report separate warm-cache, cold-cache, and failure-path distributions.
- [x] Compare no-cache, exact-cache, embedding-only, and compatibility-aware
  paths using the same workload.
- [x] Measure error rate and timeout rate alongside latency percentiles.
- [x] Identify the first bottleneck supported by measurements rather than
  assuming it is PostgreSQL, embeddings, or generation.
- [x] State the tested concurrency and hardware/environment so results are
  not presented as universal capacity claims.
- [x] Define a small, evidence-backed optimization only if a bottleneck is
  material and the change preserves safety.

Evidence: `experiments/milestone10_load_v1_report.json` compares all four
cache modes at concurrency 4 with cold and warm passes. It reports p50/p95/p99
latency, error/timeout rates, and available API/LLM timing fields. The first
measured bottleneck is wrapper overhead (average 1.522 ms versus synthetic
LLM latency 0 ms); preprocessing, provider, database, and serialization
sub-stages were not independently instrumented. No production optimization was
selected because the in-process synthetic run does not justify changing
safety-critical request behavior.

### 10. Produce the final experiment and interview report

- [x] Freeze dataset versions, strategy settings, cache policies, software
  revision, and environment metadata.
- [x] Report safety, reuse coverage, freshness, storage, token, cost, error,
  and latency results together.
- [x] Include p50/p95/p99 latency and load-test limits.
- [x] Compare all required baselines and separate development tuning from
  held-out evaluation.
- [x] Include representative failures for compatibility, freshness,
  dependency, authorization, and capacity behavior.
- [x] State what was not measured, what was synthetic, and which services
  were unavailable.
- [x] Explain the wrapper-overhead and break-even trade-off.
- [x] Answer why similarity alone is insufficient, why failures fail closed,
  how stale reuse is prevented, and where the first bottleneck appears.
- [x] Update system design, request-flow, learning guide, project tracking,
  and limitations documents only after evidence exists.

Evidence: `docs/MILESTONE_10_FINAL_EXPERIMENT_AND_INTERVIEW_REPORT.md`,
development and held-out evaluation reports, the storage-control report, and
the load-test report. The report records unavailable PostgreSQL/remote-provider
measurements and synthetic fallbacks explicitly.

## Verification checklist

- [ ] A clean checkout can start the documented Docker Compose environment.
- [ ] The database reports ready only after connectivity and schema validation.
- [x] Liveness remains distinct from dependency readiness.
- [x] Missing or invalid production configuration fails safely at startup.
- [x] Dependency calls have bounded timeouts and controlled failure behavior.
- [x] Repository, embedding, and validator failures never create a cache hit.
- [x] Generated responses remain available when caching fails and policy allows.
- [x] Administrative read and mutation operations require appropriate
  authentication and authorization.
- [x] Health responses and logs do not expose secrets or unbounded data.
- [x] Migration, restart, timeout, malformed-response, and concurrency tests
  pass or are explicitly reported as unavailable.
- [x] Load tests exercise cold and warm caches with representative outcomes.
- [x] Final reports include p50, p95, p99, throughput, errors, and test
  environment metadata.
- [x] The first measured bottleneck and its evidence are documented.
- [x] Existing cache, safety, TTL, deduplication, eviction, and evaluation
  tests still pass.
- [x] No linter errors are reported by IDE diagnostics; unavailable tooling is
  distinguished from a clean result.
- [x] Final documentation distinguishes measured behavior from assumptions and
  synthetic fallback data.

Verification evidence: `python -m pytest -q` → 183 passed, 13 skipped;
`sscre.evaluate` generated development and held-out comparison reports;
`sscre.load_test` generated the cold/warm baseline report. PostgreSQL
integration tests remain explicitly skipped without `SSCRE_DATABASE_URL`, and
the existing local volume was not destroyed.

## Completion criteria

Milestone 10 is complete when SSCRE can be started through a documented,
reproducible containerized workflow; reports accurate liveness and dependency
readiness; validates migrations before PostgreSQL-backed traffic; bounds
dependency calls with controlled failure behavior; protects administrative
operations; and passes integration tests for the important failure paths.
Load-test evidence must quantify throughput, errors, and p50/p95/p99 latency
for representative cache workloads, identify the first measured bottleneck,
and feed a final experiment and interview report. All conclusions must
distinguish reproducible measurements from unavailable services and synthetic
fallback values, while preserving the failure-closed safety guarantees from
earlier milestones.
