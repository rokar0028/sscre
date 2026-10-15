# Post–Phase 4 stabilization — Workstream 3 Step 3.1 evidence

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Status:** `closed (audit and probe)` — Step 3.2 design recorded separately  
**Machine-readable:** [`../../artifacts/stabilization/ws3-step31-timeout-audit.json`](../../artifacts/stabilization/ws3-step31-timeout-audit.json)

## Step 3.1 — Timeout and capacity boundary audit

**Date:** 2026-10-14  
**HEAD:** `2d7323fa31aa5db576e2d11aa9854832a9d0b9f5`

### Deliverables

- [x] Default timeout budgets recorded from [`src/sscre/config.py`](../../src/sscre/config.py)
- [x] All `run_with_timeout` call sites enumerated and classified in
      [`ws3-step31-timeout-audit.json`](../../artifacts/stabilization/ws3-step31-timeout-audit.json)
- [x] Historical code-inspection snapshot of executor capacity and generation lock
- [x] Deterministic probe tests:
      [`tests/test_workstream3_timeout_capacity_probe.py`](../../tests/test_workstream3_timeout_capacity_probe.py)
- [x] Pre-implementation pass rule and Step 3.1 gate decision recorded
- [x] HTTP mapping gap baselines:
      [`tests/test_workstream3_timeout_http_gaps.py`](../../tests/test_workstream3_timeout_http_gaps.py)

### Default timeout budgets (seconds)

| Setting | Default |
| --- | --- |
| `request_timeout_seconds` | 30 |
| `embedding_timeout_seconds` | 5 |
| `generation_timeout_seconds` | 25 |
| `repository_timeout_seconds` | 2 |
| `health_timeout_seconds` | 1 |
| `admin_timeout_seconds` | 5 |

Per-request dependency budgets use `min(configured_seconds, remaining request deadline)`
via `dependency_budget()` in [`src/sscre/app.py`](../../src/sscre/app.py).

### Capacity snapshot (historical at Step 3.1 close)

| Item | Value |
| --- | --- |
| `dependency_executor` workers | 8 |
| `dependency_slots` (`BoundedSemaphore`) | 8 |
| Thread name prefix | `sscre-dependency` |
| Generation coordination | In-process `threading.Lock` only |
| App teardown executor shutdown | Not registered on `create_app` return |
| Local embedding | New one-worker executor per `embed()`; `shutdown(wait=False)` |

### Pass rule (pre-implementation)

After a **client-visible** dependency timeout, the service must either reclaim
admission capacity safely or isolate work so background retention cannot deny
new admissions beyond the designed bound. Calling `Future.cancel()` alone is
insufficient when the callable continues on a worker thread.

**Clarification:** Retention is **transient** (slots return after the callable
finishes); the failure mode under stall is **denied admission** and
`capacity exhausted`, not an unbounded leak past the fixed pool size.

### Probe result

```powershell
python -m pytest tests/test_workstream3_timeout_capacity_probe.py -q
```

**Result:** `2 passed` (2026-10-14).

### HTTP gaps (pre–Step 3.3)

```powershell
python -m pytest tests/test_workstream3_timeout_http_gaps.py -q
```

**Result:** `2 passed` (2026-10-14).

| Path | Current behavior |
| --- | --- |
| Generation `run_with_timeout` timeout | HTTP **502** `response generation failed` |
| `generation_guard` lock wait timeout | Unhandled `DependencyTimeoutError` → HTTP **500** |

### Step 3.1 gate decision

**Outcome:** The current shared thread-pool + semaphore design **does not**
satisfy the pass rule (no admission reclaim on timeout). Step 3.2 selected
**admission release with request epoch**; dedicated worker pools alone and
cooperative cancellation-only paths are **rejected**. See
[`POST_PHASE4_WS3_STEP32_RUNTIME_DESIGN.md`](./POST_PHASE4_WS3_STEP32_RUNTIME_DESIGN.md).
