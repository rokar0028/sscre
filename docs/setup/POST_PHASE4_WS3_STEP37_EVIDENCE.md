# Post–Phase 4 stabilization — Workstream 3 Step 3.7 evidence

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Status:** `closed` — Workstream 3 verification complete; commit bundle `32c99e5`–`0948837` (2026-10-15)  
**Machine-readable:** [`../../artifacts/stabilization/ws3-step37-verification.json`](../../artifacts/stabilization/ws3-step37-verification.json)

## Step 3.7 — Verification and evidence close

**Date:** 2026-10-14  
**HEAD:** `2d7323fa31aa5db576e2d11aa9854832a9d0b9f5`

### Implementation decision (Steps 3.2–3.4)

- Design: `admission_release_with_request_epoch` ([`ws3-step32-runtime-design.json`](../../artifacts/stabilization/ws3-step32-runtime-design.json)).
- Code: [`dependency_runtime.py`](../../src/sscre/dependency_runtime.py), [`app.py`](../../src/sscre/app.py), [`local_embedding.py`](../../src/sscre/local_embedding.py).

### Focused WS3 tests

- [x] `python -m pytest tests/test_workstream3_concurrency.py tests/test_workstream3_failure_paths.py tests/test_workstream3_strategy_c_paths.py tests/test_local_embedding.py tests/test_workstream3_timeout_capacity_probe.py tests/test_workstream3_timeout_http_gaps.py -q` → **65 passed** (~80s).

### Default suite

- [x] `python -m pytest -q` → **892 passed**, **1 skipped**, **21 deselected** (~410s).
- [x] `PYTHONPATH=src` set for runs against the worktree.

### PostgreSQL multiprocess

- [x] Recorded as **verified** in Step 3.6 ([`ws3-step36-multiprocess-duplicate.json`](../../artifacts/stabilization/ws3-step36-multiprocess-duplicate.json)); not re-run in this step.

### Redaction audit

- [x] WS3 artifacts under `artifacts/stabilization/ws3-step*.json` contain no query text, answers, embeddings, tokens, or credentials.

### Workstream 3 acceptance gate

- [x] Admission released on client-visible dependency timeout (probe + concurrency tests).
- [x] Generation-lock contention → controlled 503/504 with `X-Request-ID` (no cache reuse/write).
- [x] Repeated timeout recovery with bounded dependency worker threads.
- [x] Failure-closed lookup, semantic, embedding, generation, insert/replacement, freshness paths (failure + strategy C suites).
- [x] In-process concurrency verified; cross-process duplicate semantics verified separately (Step 3.6).

### Remaining limitations

- No distributed generation lock; duplicate generation across processes remains possible.
- Late dependency completion cannot be stopped on in-flight Python threads; request epoch prevents publishing results.
- Host-side PostgreSQL on Windows may need Docker-reachable host/port (Step 3.6 note).

### Worktree

**Historical snapshot at Step 3.7 close:** modified/untracked WS3 paths remained
on disk at HEAD `2d7323fa…`; user-approved `/commit` was still required.

**Later:** WS3 code, tests, artifacts, and evidence were committed as
`32c99e5`–`0948837` (2026-10-15). This file’s verification counts remain the
Step 3.7 record (**892 passed**); a later WS2 Gate B default suite recorded
**893 passed**.
