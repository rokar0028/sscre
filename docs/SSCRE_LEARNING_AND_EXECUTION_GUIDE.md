# SSCRE Learning and Execution Guide

This guide explains how to learn the concepts and implement SSCRE without treating
Cursor as a replacement for understanding. The existing documents define the
architecture and research plan; this document defines the working process.

## 1. Project Rule

Use Cursor as a tutor, pair programmer, and reviewer.

For every feature:

```text
Learn → Design → Implement → Test → Debug → Explain → Review
```

Do not continue with code that you cannot explain.

### How to read this checklist

- This guide is the active implementation and learning tracker.
- `SSCRE_PLAN.md` is the research and experiment plan, not the day-to-day
  implementation checklist.
- An implementation item is checked only after code and verification exist.
- A learning item stays unchecked until the student can explain the concept and
  apply it independently.

## 2. Implementation Order

Build one small vertical slice at a time. Tick tasks only after you understand
and test them.

### Milestone 0 — Workspace and learning setup

- [x] Confirm Python and Git installations
- [x] Create a project virtual environment
- [x] Create `pyproject.toml`
- [x] Create `src/sscre/` and `tests/`
- [x] Run one pytest test successfully
- [ ] Learn Python modules, typing, exceptions, and dataclasses
- [x] Write a one-page explanation of the SSCRE request flow

### Milestone 1 — Minimal FastAPI service

- [x] Install FastAPI and an ASGI server
- [x] Create an application factory
- [x] Add `GET /health`
- [x] Start the server locally
- [x] Call the endpoint with a browser or HTTP client
- [x] Add a test for the health endpoint
- [ ] Learn HTTP methods, status codes, JSON, and Pydantic validation

### Milestone 2 — Query preprocessing

- [x] Define the query request and response models
- [x] Normalize whitespace
- [x] Validate empty and oversized queries
- [x] Hash normalized queries with SHA-256
- [x] Add unit tests for normalization
- [x] Add unit tests for hash stability
- [x] Document normalization trade-offs

### Milestone 3 — Exact-match cache

- [x] Define a cache entry model
- [x] Implement `get`
- [x] Implement `put`
- [x] Implement cache hit and miss behavior
- [x] Add a mock LLM client
- [x] Implement `POST /v1/query`
- [x] Return `source = generated` on a miss
- [x] Return `source = cache` on a hit
- [x] Test repeated requests
- [x] Test that different queries do not collide

### Milestone 4 — Metrics and reliability

- [x] Generate a request ID
- [x] Measure total request latency
- [x] Record generated token counts
- [x] Count hits and misses
- [x] Add structured decision logs
- [x] Handle mock-generation errors
- [x] Write the request sequence in a short design note

### Milestone 5 — PostgreSQL persistence

- [ ] Learn tables, constraints, indexes, and transactions
- [x] Start PostgreSQL locally
- [x] Create a database migration
- [x] Implement a repository interface
- [x] Implement PostgreSQL exact lookup
- [x] Implement PostgreSQL insert
- [x] Add parameterized queries
- [x] Add repository integration tests
- [x] Verify behavior across new API instances

### Milestone 6 — Evaluation baseline

- [x] Define the JSONL benchmark format
- [x] Create at least 20 manually reviewed pairs
- [x] Label exact, reusable, and non-reusable relationships
- [x] Implement the no-cache baseline
- [x] Implement the exact-cache baseline
- [x] Calculate hit rate and reuse coverage
- [x] Calculate tokens saved
- [x] Save results as JSON
- [x] Make runs reproducible from a config file

### Milestone 7 — Embedding retrieval

- [ ] Learn embeddings and cosine similarity
- [x] Add an embedding client interface
- [x] Add a deterministic fake embedding client for tests
- [x] Enable pgvector
- [x] Store embeddings
- [x] Implement top-K retrieval
- [x] Implement Strategy B
- [x] Sweep similarity thresholds
- [x] Measure embedding-only false positives

### Milestone 8 — Compatibility-aware safety

- [x] Define `SAFE`, `UNSAFE`, and `UNCERTAIN`
- [x] Extract intent
- [x] Extract language and other constraints
- [x] Extract entities
- [x] Extract output format
- [x] Classify temporal freshness
- [x] Implement Strategy C
- [x] Record candidate decision traces
- [x] Create a failure gallery
- [x] Compare Strategy B and Strategy C on held-out data

### Milestone 9 — Cache controls

- [x] Add stable, semi-dynamic, and dynamic freshness classes
- [x] Apply TTL to exact and semantic hits
- [x] Reject dynamic entries by default
- [x] Add answer deduplication
- [x] Add a canonical-answer data model
- [x] Add a maximum answer size
- [x] Add LRU eviction
- [x] Add a storage-cap test

Milestone 9 implementation is covered by
`docs/phase-1/MILESTONE_9_IMPLEMENTATION_PLAN.md`. Storage-control evaluation is
available through `sscre-storage-evaluate`; PostgreSQL-specific verification,
concurrency evaluation, and held-out storage comparisons remain open.

### Milestone 10 — Production and interview readiness

- [x] Add Docker Compose
- [x] Add database health checks
- [x] Add timeouts and controlled dependency failures
- [x] Add admin authentication
- [x] Add integration tests for failure paths
- [x] Run a load test
- [x] Measure p50, p95, and p99 latency
- [x] Write the final experiment report
- [x] Prepare answers to the interview questions in
  `docs/MILESTONE_10_FINAL_EXPERIMENT_AND_INTERVIEW_REPORT.md`

Do not start with dual-model comparison, cross-encoders, adaptive thresholds, or
production-scale infrastructure. Add them only after a measured hypothesis
justifies them.

Do not start with dual-model comparison, cross-encoders, adaptive thresholds, or
production-scale infrastructure.

## 3. Learning Sequence

### Stage 1 — Python and testing

Learn:

- functions, classes, typing, exceptions, and dataclasses
- modules and packaging
- pytest, fixtures, and mocks

Practice by building a file-backed key-value cache and a TTL cache.

### Stage 2 — Backend development

Learn:

- HTTP methods, status codes, JSON, and REST
- FastAPI routes and Pydantic validation
- dependency injection
- synchronous versus asynchronous I/O

Deliverable:

```text
GET /health
POST /v1/query
```

### Stage 3 — Databases

Learn:

- tables, constraints, indexes, and transactions
- parameterized SQL
- migrations and connection pooling
- PostgreSQL query plans

Implement exact-match persistence before vector search.

### Stage 4 — Information retrieval

Learn:

- embeddings
- cosine similarity
- top-K nearest-neighbor search
- precision, recall, FPR, and threshold calibration

Implement Strategy B and measure its false positives.

### Stage 5 — Safety and experimentation

Learn:

- compatibility features
- freshness and TTL policies
- benchmark construction
- train/dev/test separation
- confidence intervals
- cost and latency accounting

Implement Strategy C and compare it with Strategies A and B.

### Stage 6 — Production engineering

Learn:

- Docker Compose
- structured logging
- health checks
- timeouts and retries
- authentication
- load testing
- failure-closed behavior

## 4. How to Use Cursor

Before implementation:

> Teach me the concepts required for this feature. Do not write code yet. Give me
> a small example and quiz me.

For implementation:

> Implement only this feature, add tests, and explain the design decisions. Do not
> modify unrelated files.

For review:

> Review this code as an interviewer. Ask me five questions about its behavior,
> failure modes, performance, and trade-offs. Do not give the answers first.

For debugging:

> Help me form hypotheses from this failure. Do not immediately rewrite the code.

Use small tasks. Avoid asking Cursor to build the complete project in one step.

## 5. Definition of Done for Each Feature

A feature is complete only when:

- its inputs and outputs are documented
- its main failure cases are understood
- unit tests exist
- at least one integration path works where applicable
- logs or metrics exist for important behavior
- the implementation can be explained without reading it line by line
- the relevant experiment or acceptance criterion is defined

## 6. Research Evaluation Rules

The evaluation harness must include these baselines:

1. No cache
2. Exact-match cache
3. Embedding-only cache
4. Compatibility-aware cache

Keep threshold tuning separate from final testing:

```text
development data → choose thresholds
held-out test data → report final results
```

Report:

- cache precision and recall
- false-positive rate
- safe reuse coverage
- abstention rate
- tokens saved
- total cost including embedding cost
- p50, p95, and p99 latency
- storage growth and bytes per entry
- failure categories with examples

Do not optimize only for hit rate.

## 7. Safety Rules

- Dynamic queries must not be served from cache without a valid freshness policy.
- Exact matches must still respect TTL and freshness rules.
- Infrastructure errors must fail closed; generate or return a controlled error.
- User input must not directly create trusted cache entries.
- Cached answers must be separated from query metadata and canonical answer storage.
- Preference, correctness, and compatibility labels must remain separate.

## 8. Interview Preparation

Be able to answer:

- Why is embedding similarity insufficient?
- Why does Strategy C reduce false positives?
- How were thresholds selected?
- How did you avoid benchmark leakage?
- What is the cost break-even hit rate?
- Why use PostgreSQL with pgvector?
- What happens if the embedding or LLM provider fails?
- How are stale answers prevented?
- What is the main bottleneck at higher traffic?
- When should the system refuse to cache?

Maintain a short decision log for every important architecture change:

```text
Decision:
Alternatives:
Reason:
Evidence:
Trade-off:
```

## 9. Documentation Maintenance

Keep the existing documents focused:

- `SSCRE_PLAN.md` — objectives, phases, experiments, and success criteria
- `SSCRE_SYSTEM_DESIGN.md` — architecture, interfaces, data flow, and deployment
- `SSCRE_LEARNING_AND_EXECUTION_GUIDE.md` — learning process and implementation order

Update the system design when measured behavior changes the architecture. Do not
add components merely because they appear advanced.

## 10. First Milestone

The first milestone is a working exact-cache vertical slice:

```text
POST /v1/query
→ normalize query
→ exact cache lookup
→ mock generation on miss
→ cache eligible answer
→ return source, answer, and metrics
```

Required evidence:

- tests for normalization and cache behavior
- hit and miss requests
- measured latency
- logged token counts
- a short explanation of the request flow

