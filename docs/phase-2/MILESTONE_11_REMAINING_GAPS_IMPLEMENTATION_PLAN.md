# Milestone 11 Implementation Plan — Phase 2 Depth and Remaining Gaps

## Goal

Extend the completed local SSCRE MVP with evidence strong enough to support
research conclusions, while separating production-deployment work from
Phase 2 requirements:

```text
reproducible baseline
    ↓
larger reviewed benchmark + human labels
    ↓
real provider measurements
    ↓
confidence intervals + Pareto operating point
    ↓
failure analysis and quality report
    ↓
optional deployment hardening
```

This milestone does not begin with cross-encoders, adaptive thresholds,
multi-region infrastructure, or other Phase 3 work. Those additions require a
measured hypothesis and a pass/fail criterion.

## Scope decisions

- Phase 2 research may begin before full production deployment hardening.
- Real provider measurements and human correctness labels are required before
  making claims about real quality, cost, or latency.
- CI and fresh-volume PostgreSQL verification are early reproducibility gates.
- PostgreSQL scale testing, observability, TLS, network policy, backups, and
  secret rotation are deployment gates, not blockers for the first Phase 2
  experiment.
- Admin cache mutation and cleanup endpoints remain optional. Add them only if
  an operational use case requires manual purge or cleanup; read-only cache
  statistics are sufficient for the current MVP.

## Learning objectives

- [ ] Design a reviewed benchmark and prevent train/development/held-out
  leakage
- [ ] Separate compatibility, factual correctness, and evaluator preference
  labels
- [ ] Measure uncertainty with confidence intervals rather than point estimates
- [ ] Select an operating point using safety, reuse, latency, cost, and storage
  constraints
- [ ] Compare synthetic and real-provider measurements without conflating them
- [ ] Understand PostgreSQL restart, concurrency, and multi-process behavior
- [ ] Design CI, observability, and deployment safety gates

## Current baseline

- [x] Core API, exact and semantic cache paths, compatibility checks, TTL,
  storage caps, and failure-closed behavior exist.
- [x] Development, held-out, and synthetic load reports exist.
- [x] Full local suite passes: `python -m pytest -q` → 183 passed, 13 skipped.
- [x] Docker image build and Compose configuration validation pass with sample
  secrets.
- [x] Clean PostgreSQL startup with a fresh volume is verified.
- [ ] Real provider latency, cost, rate-limit, and failure behavior is
  measured.
- [ ] Human factual-quality labels are collected.
- [x] GitHub Actions CI is configured.

## Implementation steps

### 1. Close reproducibility and MVP hygiene gates

- [x] Run the documented Compose workflow with a disposable PostgreSQL volume,
  without destroying the existing local volume.
- [x] Verify migration ordering, checksum validation, `/health`, `/ready`, and
  `/v1/query` against the fresh database.
- [x] Record the exact commands, image versions, environment shape, and result
  in the final report.
- [x] Reconcile stale Phase 1 checklist items in `docs/SSCRE_PLAN.md` with
  implemented behavior; do not mark items complete without evidence.
- [x] Add a minimal GitHub Actions workflow for dependency installation,
  `python -m pytest -q`, and `docker compose config` using non-secret sample
  values.
- [ ] Keep provider credentials out of CI logs and use a separate opt-in job
  for any real-provider test.

Acceptance criteria:

- [x] A clean checkout can reproduce the local test and container validation
  commands.
- [x] A fresh database reaches ready only after migrations pass.
- [x] CI reports the test result on pull requests and pushes.

Evidence: `docker compose -p sscre-step1 up -d --build` with
`SSCRE_POSTGRES_PORT=55432`, `SSCRE_API_PORT=18000`, and disposable project
volume `sscre-step1_postgres_data` applied migrations `000` through `011`;
`/ready` returned `{"status":"ready","repository":"postgres"}`, `/health`
returned `{"status":"ok"}`, and `POST /v1/query` returned a generated response.
The stack was removed with `docker compose -p sscre-step1 down -v`. The
existing project volume was not touched. CI configuration is in
`.github/workflows/ci.yml`.

### 2. Build the Phase 2 reviewed benchmark

- [ ] Define a versioned benchmark schema containing query pairs, expected
  reuse decision, failure category, freshness class, and annotation source.
- [ ] Expand the reviewed benchmark to at least 500 labeled pairs.
- [ ] Include exact duplicates, paraphrases, intent changes, constraint
  changes, entity changes, format changes, temporal changes, and domain
  changes.
- [ ] Create disjoint development and held-out manifests.
- [ ] Validate that query IDs and source examples do not leak across splits.
- [ ] Record annotation guidance and adjudication rules.
- [ ] Store correctness labels independently from preference labels.

Acceptance criteria:

- Dataset version, split manifests, schema, and annotation guide are checked
  in.
- Split validation fails closed on duplicate IDs or overlapping examples.
- Every evaluation report records the dataset and split version.

### 3. Integrate one real provider path

- [ ] Define provider interfaces for generation and embeddings using the
  existing fake clients as deterministic test doubles.
- [ ] Add configuration for provider selection, endpoint, model, and bounded
  timeouts without logging credentials or raw prompts.
- [ ] Add opt-in integration tests that skip safely when credentials are
  unavailable.
- [ ] Measure provider latency distributions, token usage, pricing inputs,
  rate-limit responses, malformed responses, and timeout behavior.
- [ ] Compare real-provider results with the existing synthetic reports and
  label synthetic values explicitly.
- [ ] Do not tune the held-out threshold using held-out labels.

Acceptance criteria:

- At least one real provider run is reproducible from a redacted configuration
  and a versioned dataset.
- Provider failures preserve the existing failure-closed cache guarantees.
- Cost calculations include embedding, generation, wrapper, and retry costs.

### 4. Complete Phase 2 evaluation depth

- [ ] Add human factual-correctness labels for generated and reused answers.
- [ ] Keep factual correctness, compatibility, and preference as separate
  fields and analyses.
- [ ] Add bootstrap or binomial confidence intervals for hit rate, reuse
  coverage, false-positive rate, precision, tokens saved, and latency.
- [ ] Generate Pareto plots for safety, reuse, latency, cost, and storage.
- [ ] Run freshness-policy experiments across stable, semi-dynamic, and
  dynamic workloads.
- [ ] Add failure-category metrics and a browsable failure gallery.
- [ ] Re-run no-cache, exact-cache, embedding-only, and compatibility-aware
  baselines on the final held-out split.
- [ ] Update the final experiment report only after the evidence is frozen.

Acceptance criteria:

- A selected operating point satisfies the documented false-positive and
  storage constraints with uncertainty reported.
- Held-out labels are not used for threshold selection.
- The report clearly separates measured results, synthetic results, and
  unavailable services.

### 5. Test shared-database operational behavior

- [ ] Test PostgreSQL restart during lookup, generation, cache insert, and
  cleanup.
- [ ] Test concurrent requests from multiple processes for one query.
- [ ] Verify duplicate prevention, transaction behavior, and eviction under
  concurrent writes.
- [ ] Run bounded load tests against PostgreSQL and record p50, p95, p99,
  throughput, errors, timeouts, storage growth, and evictions.
- [ ] Document the first measured bottleneck and avoid claiming universal
  capacity from one environment.

Acceptance criteria:

- No restart or connection-loss path serves an unsafe, expired, or unauthorized
  cache result.
- Multi-process behavior is either verified or explicitly documented as
  unsupported.
- Load limits and test hardware are included in the report.

### 6. Add deployment hardening when deployment is planned

- [ ] Export structured application metrics and dependency failure counters.
- [ ] Add request tracing with bounded, redacted attributes.
- [ ] Define dashboards and alerts for readiness, error rate, timeout rate,
  latency, provider rate limits, cache growth, and eviction.
- [ ] Review secret rotation, TLS termination, network policy, least
  privilege, and admin-token handling.
- [ ] Verify encrypted backups, restore procedure, migration recovery, and
  rollback expectations.
- [ ] Document resource limits, worker/process assumptions, and retention.

Acceptance criteria:

- Deployment controls are tested in the target environment rather than only
  described in documentation.
- Logs, traces, metrics, backups, and alerts do not expose credentials,
  prompts, answers, or unnecessary personal data.

### 7. Decide the optional admin mutation surface

- [ ] Identify a concrete operator need for manual purge or cleanup.
- [ ] If needed, define separate read and mutation scopes, confirmation
  semantics, audit logging, bounded work, and failure responses.
- [ ] Add endpoint tests for authentication, authorization, request limits, and
  partial failure.
- [ ] If no need exists, document that cleanup remains automatic and leave the
  admin surface read-only.

Acceptance criteria:

- The decision is recorded with a rationale.
- No mutation endpoint is added solely to increase feature count.

## Recommended execution order

1. Complete fresh-volume verification and GitHub Actions CI.
2. Freeze the Phase 2 benchmark schema and split rules.
3. Expand reviewed data and collect correctness labels.
4. Integrate one real provider behind opt-in configuration.
5. Run confidence-aware Phase 2 evaluations and update reports.
6. Test PostgreSQL restart and multi-process behavior.
7. Add deployment observability and security controls only for a defined
   deployment target.
8. Decide whether admin mutation endpoints are necessary.

## Definition of done

- [ ] Phase 2 benchmark contains at least 500 reviewed, split-validated pairs.
- [ ] Correctness, compatibility, and preference labels are separate.
- [ ] Real-provider measurements exist or their absence is explicitly reported.
- [ ] Final results include uncertainty, Pareto trade-offs, cost, latency,
  storage, and failure categories.
- [ ] Fresh PostgreSQL startup and CI are reproducible.
- [ ] Multi-process and deployment claims are supported by tests or explicitly
  limited.
- [ ] Production hardening is implemented only for a chosen deployment target.
- [ ] Admin mutation scope is justified or intentionally omitted.
