# Milestone 4 Implementation Plan — Metrics and Reliability

## Goal

Make each SSCRE request observable and handle generation failures safely:

```text
request
    ↓
request ID + timer
    ↓
cache hit or model generation
    ↓
metrics + structured decision log
    ↓
response or controlled failure
```

This milestone adds observability without introducing dashboards, persistence,
or external monitoring services.

## Learning objectives

- [ ] Request IDs and distributed-tracing fundamentals
- [ ] Measuring elapsed time with a monotonic clock
- [ ] Input and output token accounting
- [ ] Counters and application-scoped metrics
- [ ] Structured JSON logging
- [ ] Failure-closed behavior
- [ ] HTTP `502` responses for upstream generation failures
- [ ] Testing logs and failure paths

## Implementation steps

### 1. Extend the LLM result

- [x] Add a structured `LLMResult` model.
- [x] Record generated text.
- [x] Record input token counts.
- [x] Record output token counts.
- [x] Record model-generation latency.
- [x] Allow deterministic mock failures in tests.

### 2. Add request metrics

- [x] Generate a UUID for every valid query request.
- [x] Measure total request latency.
- [x] Record cache hits and misses.
- [x] Record generation failures.
- [x] Return metrics in the query response.
- [x] Keep counters scoped to each application instance.
- [x] Synchronize counter updates and snapshots for concurrent requests.

### 3. Add structured decision logs

- [x] Log cache hits.
- [x] Log generated responses.
- [x] Log generation failures.
- [x] Include request ID, decision, source, token counts, and latency.
- [x] Avoid logging complete answers or secrets.

### 4. Handle generation failures

- [x] Catch mock-generation failures at the API boundary.
- [x] Return HTTP `502`.
- [x] Use a generic error response without exposing internals.
- [x] Do not cache failed generations.
- [x] Record the failure in application metrics.

### 5. Add reliability tests

- [x] Test request IDs and latency fields.
- [x] Test cumulative hit/miss counters.
- [x] Test generated token counts.
- [x] Test structured log content.
- [x] Test cache-hit and generation-failure log fields.
- [x] Test invalid input responses.
- [x] Test controlled generation failures.
- [x] Test that failed answers are not cached.
- [x] Test request correlation for HTTP 502 responses.

### 6. Document the request sequence

- [x] Document request IDs and latency.
- [x] Document token metrics.
- [x] Document structured decision logging.
- [x] Document failure-closed behavior.
- [x] Document request correlation and synchronized counters.

## Verification checklist

- [x] Generated responses contain request metrics.
- [x] Cache hits report zero LLM tokens.
- [x] Cache hits and misses are counted.
- [x] Generation failures return HTTP `502`.
- [x] Failed answers are not stored.
- [x] Decision logs are valid JSON.
- [x] Logs do not contain complete answers.
- [x] The full test suite passes (`.venv\Scripts\python.exe -m pytest -q`;
  29 passed, 6 skipped).
- [ ] No linter errors are reported (no linter is currently configured).

## Completion criteria

Milestone 4 is complete when every successful request has traceable timing and
token metrics, cache decisions are represented in structured logs, and model
failures return safely without polluting the cache.
