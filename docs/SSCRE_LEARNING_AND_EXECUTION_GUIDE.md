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

- [ ] Define a cache entry model
- [ ] Implement `get`
- [ ] Implement `put`
- [ ] Implement cache hit and miss behavior
- [ ] Add a mock LLM client
- [ ] Implement `POST /v1/query`
- [ ] Return `source = generated` on a miss
- [ ] Return `source = cache` on a hit
- [ ] Test repeated requests
- [ ] Test that different queries do not collide

### Milestone 4 — Metrics and reliability

- [ ] Generate a request ID
- [ ] Measure total request latency
- [ ] Record generated token counts
- [ ] Count hits and misses
- [ ] Add structured decision logs
- [ ] Handle mock-generation errors
- [ ] Write the request sequence in a short design note

### Milestone 5 — PostgreSQL persistence

- [ ] Learn tables, constraints, indexes, and transactions
- [ ] Start PostgreSQL locally
- [ ] Create a database migration
- [ ] Implement a repository interface
- [ ] Implement PostgreSQL exact lookup
- [ ] Implement PostgreSQL insert
- [ ] Add parameterized queries
- [ ] Add repository integration tests
- [ ] Verify behavior after restarting the API

### Milestone 6 — Evaluation baseline

- [ ] Define the JSONL benchmark format
- [ ] Create at least 20 manually reviewed pairs
- [ ] Label exact, reusable, and non-reusable relationships
- [ ] Implement the no-cache baseline
- [ ] Implement the exact-cache baseline
- [ ] Calculate hit rate and reuse coverage
- [ ] Calculate tokens saved
- [ ] Save results as JSON
- [ ] Make runs reproducible from a config file

### Milestone 7 — Embedding retrieval

- [ ] Learn embeddings and cosine similarity
- [ ] Add an embedding client interface
- [ ] Add a deterministic fake embedding client for tests
- [ ] Enable pgvector
- [ ] Store embeddings
- [ ] Implement top-K retrieval
- [ ] Implement Strategy B
- [ ] Sweep similarity thresholds
- [ ] Measure embedding-only false positives

### Milestone 8 — Compatibility-aware safety

- [ ] Define `SAFE`, `UNSAFE`, and `UNCERTAIN`
- [ ] Extract intent
- [ ] Extract language and other constraints
- [ ] Extract entities
- [ ] Extract output format
- [ ] Classify temporal freshness
- [ ] Implement Strategy C
- [ ] Record candidate decision traces
- [ ] Create a failure gallery
- [ ] Compare Strategy B and Strategy C on held-out data

### Milestone 9 — Cache controls

- [ ] Add stable, semi-dynamic, and dynamic freshness classes
- [ ] Apply TTL to exact and semantic hits
- [ ] Reject dynamic entries by default
- [ ] Add answer deduplication
- [ ] Add a canonical-answer data model
- [ ] Add a maximum answer size
- [ ] Add LRU eviction
- [ ] Add a storage-cap test

### Milestone 10 — Production and interview readiness

- [ ] Add Docker Compose
- [ ] Add database health checks
- [ ] Add timeouts and controlled dependency failures
- [ ] Add admin authentication
- [ ] Add integration tests for failure paths
- [ ] Run a load test
- [ ] Measure p50, p95, and p99 latency
- [ ] Write the final experiment report
- [ ] Prepare answers to the interview questions in this guide

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

