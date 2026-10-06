# Milestone 2 Implementation Plan — Query Preprocessing

## Goal

Convert raw query input into a validated, deterministic exact-cache key:

```text
raw query
    ↓
validate length and content
    ↓
normalize whitespace
    ↓
SHA-256 hash
    ↓
normalized query + query hash
```

This milestone prepares requests for exact caching. Semantic similarity and
compatibility analysis are later milestones.

## Learning objectives

- [ ] Pydantic request models and field validation
- [ ] Pure functions and deterministic transformations
- [ ] Unicode text and whitespace behavior
- [ ] SHA-256 and hexadecimal digests
- [ ] Hash stability and cache-key design
- [ ] Input-size limits and validation errors
- [ ] Trade-offs between normalization and preserving user intent

## Implementation steps

### 1. Define query models

- [x] Add `QueryRequest`.
- [x] Add a preprocessing response model.
- [x] Enforce a maximum query length of 8,000 characters.
- [x] Normalize valid query input during model validation.

### 2. Normalize query text

- [x] Trim leading and trailing whitespace.
- [x] Collapse repeated spaces, tabs, and newlines to one space.
- [x] Reject empty strings.
- [x] Reject whitespace-only queries.

### 3. Hash normalized queries

- [x] Encode normalized text as UTF-8.
- [x] Generate a SHA-256 hexadecimal digest.
- [x] Keep hashing deterministic for identical normalized queries.
- [x] Ensure different normalized queries produce different keys in tests.

### 4. Add unit tests

- [x] Test whitespace normalization.
- [x] Test empty and whitespace-only input.
- [x] Test oversized input.
- [x] Test hash stability.
- [x] Test whitespace-equivalent queries share a hash.
- [x] Test different queries do not share a hash.
- [x] Test a known SHA-256 digest format and value.
- [x] Test preservation of Unicode text, case, and punctuation.

### 5. Document normalization decisions

- [x] Explain why whitespace is normalized.
- [x] Explain why text is not lowercased.
- [x] Explain why punctuation and Unicode characters are preserved.
- [x] Explain why semantic equivalence belongs to later stages.

## Verification checklist

- [x] Valid queries produce normalized text.
- [x] Empty queries are rejected.
- [x] Oversized queries are rejected.
- [x] Equivalent whitespace formatting produces the same hash.
- [x] SHA-256 output is deterministic.
- [x] Milestone tests pass (`.venv\Scripts\python.exe -m pytest -q tests/test_query.py tests/test_health.py`; 8 passed).
- [ ] No linter errors are reported (no linter is currently configured).

The full repository suite previously had an unrelated floating-point assertion
failure in `tests/test_benchmark.py:233`. That failure was fixed by rounding
reported currency estimates to six decimal places in `src/sscre/baseline.py`.
The current full-suite result is `27 passed, 6 skipped`.

## Completion criteria

Milestone 2 is complete when every accepted query has a deterministic normalized
form and SHA-256 key, invalid input is rejected before cache processing, and
the normalization trade-offs are documented clearly.
