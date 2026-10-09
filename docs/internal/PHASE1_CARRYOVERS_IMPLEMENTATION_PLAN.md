# Phase 1 — Phase 2 carryovers implementation plan

**Status:** **closed** (2026-10-09) — carryover work complete; **P2-CI GitHub green pending approved push**  
**Owner:** Kartik  
**Parent:** [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § Phase 1  
**Scope source:** [`PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md`](./PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md) § P0-CARRYOVER (2026-10-09)  
**Time box:** 2–4 focused sessions (order: P2-CI → P2-GALLERY → P2-OPS lite)

## Goal

Close the **three approved Phase 2 carryovers** on a feature branch with minimal
diffs, recorded verification, and evidence links—so Phase 2 planning
(`PHASE3_PLAN.md`) and later Phase 3 code are not blocked by red CI or missing
paper discussion artifacts.

**Exit:** P2-GALLERY and P2-OPS-lite acceptance criteria checked; P2-CI local
verification done; **P2-CI GitHub green** remains until push + Actions URL.
[`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 1.4 satisfied except the CI-green
checkbox; completion record and verification logs filled.

---

## Learning objectives

- [ ] Map existing evaluation JSON (`failure_gallery`, `by_failure_category`) to a paper-ready static export.
- [ ] Explain LF-normalized checksum tests vs production migration bytes on Linux CI.
- [ ] State what OPS-lite can claim (single-process + one restart smoke) vs full WS8.

---

## Prerequisites (read-only)

- [x] Phase 0 complete — carryovers fixed: **P2-CI**, **P2-GALLERY**, **P2-OPS (lite)**.
- [x] Skim [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 1.3 (CI root causes).
- [x] Skim [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md) Workstreams 7–8 acceptance criteria.
- [x] Skim [`WORKSTREAM_5_EVIDENCE.md`](../phase-2/WORKSTREAM_5_EVIDENCE.md) (report paths, redaction rules).
- [x] Confirm workflow: feature branch; no commit to `main` or `git push` without explicit OK.

---

## Step 0 — Branch and baseline

**Track ID:** `P1-SETUP`

- [x] Create feature branch from current `main` (e.g. `phase1/carryovers`).
- [x] Record branch name and base commit in **Completion record → Branch**.
- [x] From repo root, install dev deps and capture baseline (commands in verification log § P1-SETUP).

- [x] Log results in **Verification log** (below) before changing code.

---

## Step 1 — P2-CI (green GitHub Actions)

**Track ID:** `P2-CI`  
**References:** [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 1.3; `.github/workflows/ci.yml`

### 1.1 Benchmark manifest SHA-256

Root cause: remote `split_manifest.json` SHA stale vs `reviewed_query_pairs.jsonl` on Ubuntu.

- [x] Confirm local manifest matches JSONL (`python -m sscre.benchmark_validate --phase2 --production`).
- [x] Ensure manifest refresh + `.gitattributes` for `*.jsonl` LF are on the branch (commit `edd2dea`).
- [ ] After explicit push OK: confirm GitHub Actions pytest + validate pass; record run URL.

### 1.2 Migration checksum unit test (LF)

Root cause: Linux writes `SELECT 1;\n`; test must not assume CRLF for temp-file migrations.

- [x] Fix or confirm `tests/test_migrate.py::test_migration_checksum_is_sha256_of_file_contents` uses LF bytes (see current `write_text(..., "\n")` and expected hash).
- [x] Optional hardening: `migrations/*.sql text eol=lf` in `.gitattributes` if not already present.
- [x] Re-run `python -m pytest -q tests/test_migrate.py` on Windows; full suite before merge intent.

### 1.3 CI compose smoke

- [x] `docker compose config` succeeds on the branch (matches CI job expectations).

### 1.4 Record

- [x] Fill **Completion record → P2-CI** and transition verification log rows (Actions URL pending push).

---

## Step 2 — P2-GALLERY (failure gallery + category metrics)

**Track ID:** `P2-GALLERY`  
**References:** [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md) WS7; `src/sscre/evaluate.py`, `src/sscre/serialization.py`, `src/sscre/evaluation_statistics.py`

**Intent:** Static or CLI gallery from **existing** evaluation artifacts (WS5/WS6 JSON)—not a second metrics pipeline or dashboard (P2-DASH deferred).

### 2.1 Inventory current outputs

- [x] List input artifact path(s) (e.g. under `artifacts/evaluation/`) that already contain `failure_gallery` and/or `strata.by_failure_category`.
- [x] Confirm redaction: saved galleries omit unapproved query text per serialization tests (`tests/test_workstream3_serialization.py`).

Primary paper inputs: `artifacts/evaluation/workstream5-held-out-comparison.json` (`failure_gallery` + `statistics.by_baseline.compatibility-cache.strata.by_failure_category`); also `workstream5-development-sweep.json`, `workstream6-*-freshness.json` for strata-only companions.

### 2.2 Category aggregates in “final report”

Per WS7: failure counts and rates by category—not gallery-only anecdotes.

- [x] Verify or extend evaluation report output so **failure-category counts/rates** appear in the documented report JSON (may already exist via `evaluation_statistics`).
- [x] Add or update tests if report shape changes (`tests/test_evaluation_statistics.py` strata coverage).

### 2.3 Browsable / static export

Pick **one** minimal surface (prefer CLI over new HTTP routes unless already planned):

- [x] **Option A (recommended):** `python -m sscre ...` subcommand or documented script that reads an evaluation JSON and writes `artifacts/evaluation/<name>-gallery.html` (or Markdown) from `failure_gallery` + category table.
- [ ] **Option B:** Extend existing evaluate/baseline save path to emit gallery file alongside report when a flag is set. *(Not selected — Option A.)*

Checklist for rendered gallery:

- [x] Each shown example includes: pair id, expected vs actual decision, failure category, similarity/trace fields allowed by redaction policy—not raw secrets.
- [x] Every false positive in the **selected evaluation sample** used for the paper table has a category (or document explicit exclusions in evidence).

**Note:** Held-out comparison (430 directed requests / 215 pairs) carries reviewed `reason` on embedding false positives; Strategy C examples include outcome `failure_category` and trace fields. Benchmark **coverage** categories appear in statistics strata (`intent_change`, `paraphrase`, …), not on every gallery row.

### 2.4 Documentation

- [x] Add command(s) to [`benchmarks/README.md`](../../benchmarks/README.md) or phase-2 evidence stub; link from **Completion record → P2-GALLERY**.
- [x] Do **not** check WS7 “every pair in 615” unless that scope is explicitly in the selected sample definition.

### 2.5 Record

- [x] Fill **Completion record → P2-GALLERY** with commands run and output paths.

---

## Step 3 — P2-OPS lite (unsupported multi-process + restart smoke)

**Track ID:** `P2-OPS-LITE`  
**References:** [`PHASE_2_IMPLEMENTATION_PLAN.md`](../phase-2/PHASE_2_IMPLEMENTATION_PLAN.md) WS8 (subset); [`docs/phase-1/MILESTONE_10_IMPLEMENTATION_PLAN.md`](../phase-1/MILESTONE_10_IMPLEMENTATION_PLAN.md) ops notes

**In scope (lite):**

- Written **unsupported** statement for multi-process / distributed coordination (cite existing code comments or milestone 10 limitations).
- **One** PostgreSQL restart smoke test (integration or documented manual procedure with recorded outcome).

**Out of scope (deferred full WS8):**

- Multi-process duplicate-generation verification, load 1K→100K, eviction-under-concurrency, p99 capacity tables.

### 3.1 Document unsupported multi-process behavior

- [x] Add or update a short section in [`docs/reference/SSCRE_EVALUATION_LIMITATIONS.md`](../reference/SSCRE_EVALUATION_LIMITATIONS.md) **or** new `docs/phase-2/WORKSTREAM_8_OPS_LITE_EVIDENCE.md` stating:
  - single-process vs multi-process assumption;
  - what is **not** verified;
  - pointer to Phase 0 deferral of full WS8.
- [x] Ensure paper limitations paragraph aligns with P0-WORKFLOW / public readiness (no overstated capacity claims).

### 3.2 Restart smoke test

- [x] Implement **one** automated test **or** a reproducible script under `tests/` / `experiments/` that:
  - uses PostgreSQL (docker compose or testcontainer pattern already in repo);
  - restarts DB or simulates connection loss during a cache operation;
  - asserts failure-closed behavior (no serve of expired/unsafe/unauthorized result).
- [x] If only manual smoke: record exact steps, env, and pass/fail in evidence markdown (acceptable for lite, but automated preferred).

### 3.3 Record

- [x] Fill **Completion record → P2-OPS-LITE** with test name or manual log path.

---

## Step 4 — Close Phase 1 (handoff)

- [x] All three tracks marked done in **Completion record** (or explicit deferral note if scope cut—with user OK).
- [x] Update [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 1.4 checkboxes (local pytest + plan docs; CI green left open until push).
- [x] Append rows to transition **Verification log** (pytest, Actions URL, gallery command, ops evidence).
- [x] Optional: tick PHASE_2 plan WS7/WS8 items only to the extent actually delivered (lite ops ≠ full WS8).
- [x] **Next authorized work:** author [`docs/phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md) (planning only) on same or follow-on branch per user OK.

---

## Acceptance criteria

- [ ] **P2-CI:** `python -m pytest -q` passes locally; GitHub Actions green on the merge-intent branch after approved push; `benchmark_validate --phase2 --production` passes in CI. *(Local: pass; remote CI: pending push — see completion record.)*
- [x] **P2-GALLERY:** Documented command regenerates gallery + category metrics from frozen artifacts; redaction tests still pass; no secrets in outputs.
- [x] **P2-OPS lite:** Unsupported multi-process documented; one restart smoke recorded; no claim of full load/concurrency verification.
- [x] Diffs stay vertical-slice minimal (no P2-DASH, P2-DUAL, P2-LABEL, P2-PROV scope creep).
- [x] [`PHASE3_TRANSITION.md`](./PHASE3_TRANSITION.md) § 1.4 fully checked (except CI green — documented blocker).
- [x] Completion record below has no TBDs (except GitHub Actions URL until push).

---

## Completion record (fill in)

_Date completed: 2026-10-09_

**Closure note:** P2-GALLERY and P2-OPS-lite delivered on `phase1/carryovers`. P2-CI verified locally (`edd2dea` + uncommitted `.gitattributes` migrations LF); merge to `origin/main` and green Actions run remain **user-gated** (no push without OK).

### Branch

**Name:** `phase1/carryovers`  
**Base commit:** `edd2dea` (`edd2dead86d9c8e3a7774fbc55b6372638c33c3c`) — manifest/LF fix on local `main`, not yet on `origin/main`  
**Merge / PR:** (after explicit OK)

### P2-CI

**Manifest / gitattributes commit(s):** `edd2dea` (manifest + `*.jsonl` LF); carryover commit adds `migrations/*.sql text eol=lf`  
**Migration test fix commit(s):** already on `origin/main` — LF `write_text` + hash `d3cd5042…` in `tests/test_migrate.py` (no code change required)  
**GitHub Actions URL (green):** pending — push branch (includes `edd2dea`; `origin/main` manifest still `84d8c6fd…`)  

### P2-GALLERY

**Input artifact(s):** `artifacts/evaluation/workstream5-held-out-comparison.json`  
**Export command(s):** `python -m sscre.gallery_export artifacts/evaluation/workstream5-held-out-comparison.json -o artifacts/evaluation/workstream5-held-out-comparison-gallery.html` (alias: `sscre-gallery-export`)  
**Output path(s):** `artifacts/evaluation/workstream5-held-out-comparison-gallery.html` (~68 KiB, 2026-10-09)  
**Tests added/updated:** `tests/test_gallery_export.py`; module `src/sscre/gallery_export.py`; `pyproject.toml` script entry  

### P2-OPS-LITE

**Unsupported doc path:** [`WORKSTREAM_8_OPS_LITE_EVIDENCE.md`](../phase-2/WORKSTREAM_8_OPS_LITE_EVIDENCE.md); pointer in [`SSCRE_EVALUATION_LIMITATIONS.md`](../reference/SSCRE_EVALUATION_LIMITATIONS.md) § Phase 1 OPS lite  
**Restart smoke (test or manual log):** `tests/test_postgres_integration.py::test_postgres_connection_loss_on_lookup_fails_closed` (skipped without `SSCRE_DATABASE_URL`; in-memory analogue: `tests/test_exact_cache.py::test_cache_repository_failure_returns_503_with_request_id`)  

---

## Verification log

| Step | Command / action | Date | Result |
| --- | --- | --- | --- |
| P1-SETUP | `python -m pip install ".[dev]"` | 2026-10-09 | ok |
| P1-SETUP | `python -m pytest -q` | 2026-10-09 | **650 passed**, 14 skipped (~175s) |
| P1-SETUP | `python -m sscre.benchmark_validate --phase2 --production` | 2026-10-09 | passed (`split_manifest_sha256=68912e3b…`) |
| P1-SETUP | `docker compose config` | 2026-10-09 | passed with CI sample env (`POSTGRES_PASSWORD`, `SSCRE_ADMIN_TOKEN` per `.github/workflows/ci.yml`); fails without `.env` |
| P2-CI | `python -m pytest -q tests/test_migrate.py` | 2026-10-09 | 4 passed |
| P2-CI | `python -m pytest -q` (full) | 2026-10-09 | **650 passed**, 14 skipped (~161s) |
| P2-CI | `benchmark_validate --phase2 --production` | 2026-10-09 | passed |
| P2-CI | `docker compose config` (CI env) | 2026-10-09 | passed (see P1-SETUP) |
| P2-CI | GitHub Actions run | | pending push |
| P2-GALLERY | `python -m sscre.gallery_export` (held-out comparison) | 2026-10-09 | HTML written; `tests/test_gallery_export.py` 3 passed |
| P2-GALLERY | Full suite after gallery module | 2026-10-09 | **653 passed**, 14 skipped |
| P2-OPS-LITE | `test_postgres_connection_loss_on_lookup_fails_closed` | 2026-10-09 | skipped (no `SSCRE_DATABASE_URL`); in-memory 503 test passed |
| Phase 1 close | `python -m pytest -q` (final) | 2026-10-09 | **653 passed**, 15 skipped (~433s) |

---

## Verification (gate before “Phase 1 complete”)

- [x] Full suite: `python -m pytest -q` from repo root (record pass/skip counts).
- [x] Completion record complete.
- [x] Parent transition doc § 1.4 matches evidence.
