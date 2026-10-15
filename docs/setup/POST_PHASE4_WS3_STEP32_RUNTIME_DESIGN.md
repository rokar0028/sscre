# Post–Phase 4 stabilization — Workstream 3 Step 3.2 runtime design

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Prerequisite:** [`POST_PHASE4_WS3_STEP31_EVIDENCE.md`](./POST_PHASE4_WS3_STEP31_EVIDENCE.md)  
**Status:** `closed (design selected)` — implementation in Steps 3.3–3.4  
**Machine-readable:** [`../../artifacts/stabilization/ws3-step32-runtime-design.json`](../../artifacts/stabilization/ws3-step32-runtime-design.json)

## Problem statement (from Step 3.1)

`run_with_timeout` returns `DependencyTimeoutError` to the caller while the
submitted callable may still run on a worker thread. The dependency
`BoundedSemaphore` slot is released only when the future completes, so:

- Admission is **denied transiently** until the callable finishes (follow-up
  calls may see `capacity exhausted`).
- Capacity is **not leaked forever** (probe shows release after completion).
- `Future.cancel()` does **not** stop in-flight Python thread work.

The Workstream 3 pass rule requires that, after a client-visible dependency
timeout, either admission is **reclaimed safely** or work is **isolated** so
background retention cannot exhaust request admission.

## Design options compared

| Option | Reclaims admission on timeout? | Stops unstoppable work? | Complexity | Verdict |
| --- | --- | --- | --- | --- |
| A. Status quo (slot held until future done) | No | No | Low | **Reject** — fails pass rule under stall |
| B. More thread pools / “dedicated workers” only | No | No | Medium | **Reject** — does not change cancellation |
| C. Cooperative cancellation inside providers | Partial | Only if providers cooperate | High / uncertain | **Defer** — not reliable at boundary |
| D. Admission release + request-scoped cancel token | Yes | No (orphans may run) | Medium | **Select** — primary path |
| E. Subprocess / worker isolation per dependency | Yes | Yes (terminate isolate) | High | **Defer** — use only if D insufficient |

### Option D — selected design (smallest correct path)

**Name:** `admission_release_with_request_epoch`

1. **Admission:** On client-visible dependency timeout, release the dependency
   slot immediately (exactly once). Do not wait for the callable to finish.
2. **Request epoch:** Each `/v1/query` request gets a monotonic token. All
   cache writes, cache hits served from post-timeout paths, and success metrics
   for that request check the token; timed-out requests mark the token
   **cancelled** so late callables cannot publish results.
3. **Orphan bound:** Keep a single shared `ThreadPoolExecutor` with fixed
   `max_workers` (default 8). Orphaned work may finish in the pool but cannot
   admit unbounded queued load beyond the existing executor policy; Step 3.3
   must reject or shed new dependency work when the pool is saturated rather
   than growing an unbounded queue.
4. **Shutdown:** Register executor shutdown on app lifespan teardown (tests may
   continue to use short-lived `TestClient` apps).

**Does not change:** provider SDKs, retry policy, Strategy C rules, or
tenant/auth boundaries.

### Option E — deferred escalation

If Step 3.3–3.4 verification shows encoder or provider stalls still threaten
admission under realistic load, escalate **generation** and/or **local
embedding** to a bounded subprocess isolate with hard kill on timeout. Remote
HTTP providers remain timeout-at-socket only.

## Invariants (must hold after Step 3.3)

- A timed-out request cannot publish a cache insert, replacement, canonical
  answer, or reusable cache hit attributable to that request.
- Late callable completion may log `late_completion` with stable fields only
  (request id, operation name, error type); no prompts, answers, or embeddings.
- `capacity_exhausted` and `dependency_timeout` remain distinguishable in logs
  and tests.

## HTTP mapping (Step 3.3)

| Condition | Current (pre-3.3) | Target |
| --- | --- | --- |
| `generation_guard` lock wait timeout | HTTP 500 (unhandled) | HTTP 503 or 504 + `X-Request-ID` |
| `generation` `run_with_timeout` timeout | HTTP 502 `response generation failed` | HTTP 504 (or documented 503) + `X-Request-ID` |
| Repository lookup timeout inside generate path | HTTP 503 `cache unavailable` | Keep 503 |
| `ensure_request_budget` | HTTP 504 | Keep 504 |

## Step 3.2 gate

- [x] Options compared against Python thread semantics and provider boundary.
- [x] One design selected without provider-policy changes.
- [x] Late-result and admission invariants written.
- [x] Isolation escalation path documented as deferred.
- [x] Machine-readable record written before Step 3.3 code changes.
