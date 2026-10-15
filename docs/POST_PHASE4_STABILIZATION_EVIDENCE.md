# Post–Phase 4 stabilization evidence

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Status:** `closed (Workstream 0)` — Step 0.x sections below are the freeze
snapshot. Later workstreams: WS1 Gate A closed; WS2 in-memory and PostgreSQL
Gate B verified (multi-worker deploy deferred); WS3 closed; R1.1 diagnosis
recorded; R1.2 Gate C live deferred. See the parent plan **Status**.

## Workstream 0 — Step 0.1 execution context

Captured **2026-10-13T07:52:42Z** on the machine that ran the commands below.
Machine-readable record: [`../artifacts/stabilization/baseline-manifest.json`](../artifacts/stabilization/baseline-manifest.json).

### Repository

| Field | Value |
| --- | --- |
| Repository root (absolute) | `C:\Users\Admin\Desktop\major` |
| `git rev-parse --show-toplevel` | `C:/Users/Admin/Desktop/major` |
| Commit (`HEAD`) | `cbe5e0d1df7534ed28a2df025c55b351fabec239` |
| Branch | `main` |

**`git status --short` after Step 0.1 outputs** (see manifest `repository.git_status_short`):

```
?? artifacts/stabilization/
?? docs/POST_PHASE4_STABILIZATION_EVIDENCE.md
?? docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md
```

Committed `HEAD` at capture: `cbe5e0d1df7534ed28a2df025c55b351fabec239` on `main`.

### Runtime and dependencies

| Check | Result |
| --- | --- |
| OS | Microsoft Windows 11 Pro (`10.0.26200`) |
| `python --version` | Python 3.14.5 |
| `python -m pip --version` | pip 26.1.2 (Python 3.14) |
| Installed packages | 92 entries in manifest `pip_packages` (full list not duplicated here) |
| `docker --version` | Docker version 29.8.1, build 4a63305 |
| `docker compose version` | Docker Compose version v5.5.1 |

No command in the Step 0.1 procedure was unavailable. `.env` was not read and
no secrets appear in the manifest or this document.

### Verification (Step 0.1)

- [x] Confirmed execution from repository root and recorded absolute path.
- [x] Recorded commit, branch, and worktree state via the listed `git` commands.
- [x] Recorded Python, pip, and package list (`pip list --format=json`).
- [x] Recorded Docker and Compose versions.
- [x] Wrote timestamped snapshot without secrets.

## Workstream 0 — Step 0.2 worktree classification

Recorded in manifest `worktree_boundary` (schema
`stabilization-baseline-manifest-0.2`).

### HEAD vs dirty boundary

| Boundary | Value |
| --- | --- |
| Committed `HEAD` | `cbe5e0d1df7534ed28a2df025c55b351fabec239` (`main`) |
| Modified tracked files | none |
| Deleted tracked files | none |
| Untracked paths (non-ignored) | 3 files under 2 top-level entries |

**Answer:** Stabilization plan, evidence, and baseline manifest exist only in
the dirty worktree, not at committed `HEAD`. All other project claims in
tracked files at `HEAD` are unchanged by this untracked package.

### Path classifications (`git status --short` scope)

| Path | Git state | Classification |
| --- | --- | --- |
| `docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md` | untracked | intended stabilization work |
| `docs/POST_PHASE4_STABILIZATION_EVIDENCE.md` | untracked | intended stabilization work |
| `artifacts/stabilization/baseline-manifest.json` | untracked | generated evidence |

No path was left `unclassified`. Stabilization package is **not** blocked.

### Local environment (gitignored, informational)

These paths appear under `git status --ignored` and are classified as
`local environment`. They are not part of the untracked stabilization
package and were not modified for this step:

`.env`, `.pytest_cache/`, `.venv/`, `build/`, `src/sscre.egg-info/`,
`pytest_full.log`, `fastapi/`, `tutorial_pydan/`, and repository `__pycache__`
trees. `benchmarks/candidates/upstream/cacheeval_v1_filtered.jsonl` is a
local upstream cache file (ignored).

### Verification (Step 0.2)

- [x] Listed every modified, deleted, and untracked path from `git status --short`.
- [x] Classified each non-ignored dirty path.
- [x] Did not stage, discard, reset, or amend other work.
- [x] Recorded the `HEAD` / worktree boundary in the baseline manifest.

## Workstream 0 — Step 0.3 claim inventory

Machine-readable inventory (35 distinct claims, 5 cross-claim issues):
[`../artifacts/stabilization/claim-inventory.json`](../artifacts/stabilization/claim-inventory.json).

Inventory scoped to committed `HEAD` (`cbe5e0d1…`) documentation in
`docs/SSCRE_PLAN.md`, `docs/phase-2/`, `docs/phase-3/`, and `docs/phase-4/`.
Stabilization-plan-only rows (e.g. CLM-033) are flagged `present_at_head: false`.

### Status summary

| Status | Count |
| --- | ---: |
| implemented | 6 |
| locally verified | 9 |
| PostgreSQL verified | 1 |
| provider verified | 0 |
| evaluation verified | 7 |
| deferred | 8 |
| unavailable | 2 |
| out of scope | 3 |

### Cross-claim issues (resolve in Workstream 8)

| ID | Type | Summary |
| --- | --- | --- |
| XCL-001 | stale | §19 ≥100-pair checkbox vs §20 615-pair close |
| XCL-002 | overstated_without_gate | §24 criterion 3 vs deferred fresh semantic gate |
| XCL-003 | deployment_misalignment | Compose default B vs documented C safety path |
| XCL-004 | historical_lineage | Split manifest `68912e3b…` vs canonical `0aca5b8d…` |
| XCL-005 | vocabulary | Evidence “complete/closed” vs stabilization status words |

### Verification (Step 0.3)

- [x] Reviewed claim-bearing sections in SSCRE_PLAN and Phase 2–4 docs.
- [x] Recorded distinct claims with stable IDs, sources, references, and status.
- [x] Flagged duplicated, stale, overstated, and contradicted pairs in `cross_claim_issues`.
- [x] Did not use `pass`, `complete`, or `production-ready` as inventory status.

## Workstream 0 — Step 0.4 evidence lineage

Each claim in
[`../artifacts/stabilization/claim-inventory.json`](../artifacts/stabilization/claim-inventory.json)
(schema `1.1`) now has an `evidence_lineage` block: primary evidence paths,
verification command or document audit, provenance, measurement environment, and
contamination flags where applicable.

Path existence audit:
[`../artifacts/stabilization/evidence-lineage-audit.json`](../artifacts/stabilization/evidence-lineage-audit.json)
— **0** claims with missing referenced paths at `HEAD` `cbe5e0d1`.

Reconciliation helper (rerunnable):
[`../scripts/stabilization_reconcile_lineage.py`](../scripts/stabilization_reconcile_lineage.py).

### Provenance mix (35 claims)

| Provenance | Claims |
| --- | --- |
| committed_head | 19 |
| historical_run | 10 |
| dirty_worktree | 2 (CLM-020, CLM-033) |
| unavailable_conditional_path | 2 (CLM-009, CLM-030) |

### Verified claims (17) — lineage attached

Statuses `locally verified`, `PostgreSQL verified`, or `evaluation verified`
each point to at least one primary artifact, test command, or audit document.
Historical, synthetic, fake-embedding, and dirty-worktree-at-generation runs
are labeled in `contamination_flags` (not deleted).

### Deferred / unavailable without upgrade

| Claim | Status | Lineage note |
| --- | --- | --- |
| CLM-003, CLM-008, CLM-024, CLM-027, CLM-035 | deferred | document or gate deferral recorded |
| CLM-006 | deferred | gate artifacts at HEAD; fresh population missing |
| CLM-009, CLM-030 | unavailable | fail-closed / no live provider path |

Contradictions **XCL-001**–**XCL-005** unchanged for Workstream 8; no source
claims were rewritten in Step 0.4.

### Verification (Step 0.4)

- [x] Lineage recorded for every verified-status claim.
- [x] Provenance classified (HEAD, historical, synthetic, dirty worktree, unavailable).
- [x] Referenced artifact and benchmark paths checked on disk.
- [x] Contamination and deferral flags preserved; artifacts not deleted.
- [x] Cross-claim issues left for Workstream 8.

## Workstream 0 — Step 0.5 acceptance baseline freeze

Frozen in
[`../artifacts/stabilization/baseline-manifest.json`](../artifacts/stabilization/baseline-manifest.json)
(schema `stabilization-baseline-manifest-1.0`, `workstream_0_status`: `closed`).

### Baseline facts (mutable only by later workstreams)

**Historical freeze at Step 0.5** (2026-10-13). Compose default **B** below is
the freeze value; Workstream 1 later set Compose and `.env.example` to **C**.

| Fact | Frozen value |
| --- | --- |
| `HEAD` / branch | `cbe5e0d1df7534ed28a2df025c55b351fabec239` / `main` |
| Tracked tree delta | no modified or deleted tracked files |
| Compose default strategy | **B** (`SSCRE_SEMANTIC_STRATEGY`) |
| Documented safety path | **C** |
| Pre-change pytest | `807 passed`, `15 skipped`, `21 deselected`, `1 warning` (~169s) — log: `pytest-baseline.log` |
| Pre-change benchmark validate | **pass**; `split_manifest_sha256=0aca5b8d…` — log: `benchmark-validate-baseline.log` |
| Compose config (CI sample token) | **pass** (`docker compose config -q`) |
| Held-out semantic headline gate | **deferred** |
| Human correctness labels | **deferred** (CLM-003) |

**Not re-run for freeze:** opt-in `ws8_postgres_*` pytest markers (historical CLM-011); live
provider measurement (unavailable).

### Deferred / unavailable / out of scope (claim IDs)

| Status | IDs |
| --- | --- |
| deferred | CLM-003, CLM-006, CLM-008, CLM-024, CLM-025, CLM-027, CLM-035 |
| unavailable | CLM-009, CLM-030 |
| out of scope | CLM-015, CLM-017, CLM-033 |

### Gate answers (before Workstream 1)

**Historical snapshot at Step 0.5 close** (2026-10-13). Later workstreams
closed or advanced; do not read these answers as the current repository
state.

1. **What was already changed?** Only the untracked stabilization package
   (plan, evidence, `artifacts/stabilization/`, helper scripts). `HEAD` code
   and committed artifacts are unchanged.
2. **What is actually verified?** 17 inventory claims with verified statuses
   plus Step 0.5 pytest / benchmark_validate / compose checks above; lineage
   in `claim-inventory.json`.
3. **What is still only a plan?** Workstreams 1–8 in the stabilization
   implementation plan (docs only until committed and executed).
4. **What may Workstream 1 modify?** `.env.example`, setup documentation,
   environment validation commands — not benchmarks, auth/tenancy code, or
   deletion of historical artifacts without explicit later scope.

### Workstream 1 close (Gate A)

**Date:** 2026-10-13  
**Evidence:** [`setup/POST_PHASE4_WS1_EVIDENCE.md`](setup/POST_PHASE4_WS1_EVIDENCE.md)  
**Package record:** [`../artifacts/stabilization/gate-a-package-verification.json`](../artifacts/stabilization/gate-a-package-verification.json)

Gate A verification: `pytest -q` **835 passed** (refreshed at package commit);
import smoke; env validator;
Compose config. Live provider **deferred**; PostgreSQL integration **deferred**
(readiness logged where Docker was available).

### Approved next workstream

**Historical at Workstream 0 close:** **Workstream 2** — public API safety,
authentication, and tenancy boundary.

Open documentation conflicts **XCL-001**–**XCL-005** remain for Workstream 8.

### Verification (Step 0.5)

- [x] Baseline facts recorded in machine-readable manifest.
- [x] Pre-change `pytest` and `benchmark_validate` run and logged.
- [x] Manifest includes artifact SHA-256 hashes and claim status summary.
- [x] Evidence document includes snapshot, boundary, claims, conflicts, gates, next WS.
- [x] No secrets in stabilization outputs.

### Workstream 0 close-out

- [x] Commit / dirty boundary recorded.
- [x] Phase 2–4 scoped claims inventoried with status vocabulary.
- [x] Verified claims linked to lineage; historical/synthetic separated.
- [x] Next workstream and prerequisites documented.

## Workstream 3 — Step 3.1 timeout audit

**Status:** `closed (audit/probe)` — see
[`setup/POST_PHASE4_WS3_STEP31_EVIDENCE.md`](setup/POST_PHASE4_WS3_STEP31_EVIDENCE.md).

- [x] Timeout budgets, `run_with_timeout` call-site matrix, and capacity snapshot
      recorded in
      [`artifacts/stabilization/ws3-step31-timeout-audit.json`](../artifacts/stabilization/ws3-step31-timeout-audit.json).
- [x] Probe tests:
      `python -m pytest tests/test_workstream3_timeout_capacity_probe.py -q` →
      **2 passed** (2026-10-14).
- [x] Step 3.1 gate: transient slot retention fails pass rule; admission must
      be reclaimed or isolated (see Step 3.1 evidence).
- [x] Step 3.2 design selected:
      [`setup/POST_PHASE4_WS3_STEP32_RUNTIME_DESIGN.md`](setup/POST_PHASE4_WS3_STEP32_RUNTIME_DESIGN.md)
      (`admission_release_with_request_epoch`).

## Workstream 3 — Step 3.6 cross-process duplicate semantics

**Status:** `closed (live verified)` — see
[`setup/POST_PHASE4_WS3_STEP36_MULTIPROCESS_EVIDENCE.md`](setup/POST_PHASE4_WS3_STEP36_MULTIPROCESS_EVIDENCE.md).

- [x] Live `pytest -m ws8_postgres_multiprocess` with migrated PostgreSQL → **1 passed** (2026-10-14).
- [x] Opt-in harness:
      [`tests/test_postgres_multiprocess_duplicate.py`](../tests/test_postgres_multiprocess_duplicate.py)
      (`ws8-multiprocess-dup-v1`).
- [x] Verified record:
      [`artifacts/stabilization/ws3-step36-multiprocess-duplicate.json`](../artifacts/stabilization/ws3-step36-multiprocess-duplicate.json).
- [x] Cross-process claims not inferred from in-process WS3 concurrency tests.

## Workstream 3 — close (Steps 3.1–3.7)

**Status:** `closed (verification complete)` — see
[`setup/POST_PHASE4_WS3_STEP37_EVIDENCE.md`](setup/POST_PHASE4_WS3_STEP37_EVIDENCE.md).

- [x] Runtime design `admission_release_with_request_epoch` implemented and verified.
- [x] Focused WS3 pytest → **65 passed**; default `python -m pytest -q` → **892 passed**, **1 skipped**, **21 deselected** (2026-10-14, HEAD `2d7323fa31aa5db576e2d11aa9854832a9d0b9f5`).
- [x] Cross-process duplicate semantics **verified** (Step 3.6).
- [x] Machine-readable close record:
      [`artifacts/stabilization/ws3-step37-verification.json`](../artifacts/stabilization/ws3-step37-verification.json).
- [x] User-approved commit containing WS3 code, tests, artifacts, and evidence docs
      (`32c99e5`–`0948837`, 2026-10-15).

## Research track R1 — Step 1.1 Strategy C diagnosis

**Status:** diagnosis recorded (non-headline).

**Evidence:**
[`setup/POST_PHASE4_R1_STEP11_EVIDENCE.md`](setup/POST_PHASE4_R1_STEP11_EVIDENCE.md).

- [x] Development-split diagnosis export (non-headline):
      [`artifacts/stabilization/r1-step11-strategy-c-diagnosis.json`](../artifacts/stabilization/r1-step11-strategy-c-diagnosis.json).
- [x] `python -m pytest tests/test_r1_strategy_c_diagnosis.py -q` → **4 passed**.

## Research track R1 — Step 1.2 bounded Gate C provider measurement

**Status:** Gate C live measurement **deferred** (unavailable artifact recorded).
Live-run tasks in the parent plan remain unchecked.

**Evidence:**
[`setup/POST_PHASE4_R1_STEP12_EVIDENCE.md`](setup/POST_PHASE4_R1_STEP12_EVIDENCE.md).

- [x] Gate C **deferred** — unavailable measurement (no fake-provider substitute):
      [`artifacts/stabilization/r1-step12-provider-measurement.json`](../artifacts/stabilization/r1-step12-provider-measurement.json).
- [ ] Live bounded provider measurement (not run; 0 requests).
- [x] `python -m pytest tests/test_r1_provider_run.py tests/test_provider_measure.py -q` → **7 passed** (2026-10-15).

## Current position (after later workstreams)

Not part of the Step 0.5 freeze. Matches the parent plan **Status**:

- Workstreams 0–1 closed; Workstream 2 in-memory and PostgreSQL Gate B
  verified; multi-worker external deploy still not authorized.
- Workstream 3 closed (`32c99e5`–`0948837`).
- Research track R1 in progress (R1.1 recorded; R1.2 Gate C live deferred;
  `0020143`–`37109ca`).
- Next research step: Workstream 5 (fresh held-out data or keep deferred),
  then Workstream 7 (CI).
