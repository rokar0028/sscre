# SSCRE Storage-Control Failure Gallery

These cases are deterministic lifecycle checks from the Milestone 9 tests and
storage evaluator. They describe the expected safe behavior; they are not
claims about production database frequency.

## Oversized answer

- Input: generated answer exceeds `max_answer_bytes`.
- Expected: return the complete generated answer, skip insertion, report
  `answer_too_large`.
- Coverage: `tests/test_cache_ttl_integration.py`.

## Expired entry

- Input: exact or semantic candidate has `ttl_expires_at <= now`.
- Expected: reject the candidate, generate a response, and allow bounded
  cleanup to remove the entry.
- Coverage: `tests/test_cache_ttl_integration.py`,
  `tests/test_cache_eviction.py`.

## Dynamic query

- Input: query metadata classifies as `dynamic` with the default policy.
- Expected: generate and return the answer without storing it.
- Coverage: `tests/test_cache_ttl_integration.py`.

## Byte-cap insertion

- Input: insertion causes total storage to exceed `max_cache_bytes`.
- Expected: evict deterministic least-recently-used entries, including the
  newly inserted entry if it cannot fit, and remove orphaned canonical data.
- Coverage: `tests/test_cache_eviction.py`.

## Concurrent identical answers

- Input: interleaved inserts contain different query hashes and identical
  answer content.
- Expected: one canonical answer, separate query metadata, and no duplicate
  canonical body.
- Coverage: `tests/test_cache_eviction.py`.

## Repository unavailable

- Input: PostgreSQL lookup, insert, statistics, or eviction fails.
- Expected: do not serve an unsafe candidate; preserve a generated response
  when possible; return a controlled infrastructure error when lookup cannot
  be completed.
- Coverage: repository error paths in `src/sscre/app.py` and PostgreSQL
  integration tests.
