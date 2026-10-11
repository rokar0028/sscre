# Phase 3 Workstream 1 — Step 0 inventory (v1 registry)

**Track ID:** `P3-WS1-INVENTORY`  
**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_1_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_1_IMPLEMENTATION_PLAN.md) § Step 0  
**Branch at verification:** `phase4/setup`  
**Git commit:** `da323d051506f210e5b25f1bc509b8aeb2158884`

Read-only audit. No evaluation or cache code changed.

## Frozen inputs (verified on disk)

| Item | Expected | Verified |
| --- | --- | --- |
| Dataset version | `reviewed-query-pairs-2.0` | `benchmark_validate --phase2 --production` (2026-10-11) |
| Split counts | 400 / 215 / 615 | same command |
| Split manifest SHA-256 | `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51` | same command |
| Evaluation config SHA-256 | `5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8` | `experiments/evaluation_config.json` hash matches `PHASE3_PLAN.md` |
| WS5 held-out comparison | `artifacts/evaluation/workstream5-held-out-comparison.json` | file exists |
| Phase 3 final comparison | `artifacts/evaluation/phase3-final-held-out-comparison.json` | file exists |
| Leakage | cross-split fingerprint overlaps = 0 | validation passed |

## Feature card completeness (Features 1–3)

In-scope cards must have hypothesis, development protocol, held-out protocol,
pass/fail, primary metrics, baselines, and evidence paths. No `TBD` in those
sections (historical runbook comments may still say TBD for superseded CLI
drafts).

| ID | Hypothesis | Pass / fail | Dev / held-out split | Trigger / stopping | Outcome evidence |
| --- | --- | --- | --- | --- | --- |
| `P3-FEAT-ADAPT` | yes § Feature 1 | yes | yes | N/A | [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md) — **pass** |
| `P3-FEAT-EVICT` | yes § Feature 2 | yes | yes | fail/defer rule | [`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md) — **fail/defer** |
| `P3-FEAT-D` | yes (conditional) | yes | yes | trigger FPR `> 0.0`; stopping § Feature 3 | [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) — **deferred** |

Summary table in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature cards matches the
three full cards.

### Strategy D gate snapshot

| Check | Source | Value |
| --- | --- | --- |
| Safety cap | `experiments/evaluation_config.json` | `max_false_positive_rate` **0.0** |
| Pre–Phase 3 Strategy C FPR | `workstream5-held-out-comparison.json` | **0.0** (per `PHASE3_PLAN.md` citation) |
| Final stack FPR | `phase3-final-held-out-comparison.json` | Strategy C + adaptive: **0.0** at report time |
| Trigger fired? | Feature 3 | **no** — D not authorized |

## Optional deferral table vs parent workstreams

[`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Optional features must align with
[`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md) Workstreams 5–8.

| Optional ID | `PHASE3_PLAN.md` v1 decision | Parent workstream | Match |
| --- | --- | --- | --- |
| `P3-OPT-Q8` | Defer (v2); baseline first | WS5 storage + quantization | yes |
| `P3-OPT-LOAD` | Defer (v2); not WS8 32-req protocol | WS6 load ladder | yes |
| `P3-OPT-CLUSTER` | Defer (code); manual paper OK | WS7 failure clustering | yes |
| `P3-OPT-TRACK` | Defer (v2); manual JSON sufficient | WS8 tracking audit | yes |

Phase 0 order (adaptive → eviction → conditional D) is recorded in
[`../internal/PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md`](../internal/PHASE0_DECISIONS_IMPLEMENTATION_PLAN.md)
and matches Features 1–3 order in `PHASE3_PLAN.md`.

## v1 authoring closure

| Document | Status |
| --- | --- |
| [`../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md`](../internal/PHASE2_PHASE3_PLAN_IMPLEMENTATION_PLAN.md) | **closed (authoring)** 2026-10-09 |
| [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) | Features 1–3 + optional table complete |
| Phase 3 code gate | User OK 2026-10-10; implementation closed per [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md) |

## Open registry gap (expected)

- [x] **`P3-FEAT-CLUSTER`** promoted as Feature 4 (2026-10-11, WS1 Step 2).
- [x] **`P3-FEAT-TRACK`** promoted as Feature 5 (2026-10-11, WS1 Step 3).
- [x] **`P3-FEAT-EMBED-BASE`** / **`P3-FEAT-Q8`** promoted as Features 6–7 (2026-10-11, WS1 Step 4).
- [x] **`P3-FEAT-LOAD`** promoted as Feature 8 (2026-10-11, WS1 Step 5).
- [x] All **`P3-OPT-*`** rows promoted (Features 4–8); Workstream 1 card promotion Steps 2–5 complete.

## Verification command

```powershell
$env:PYTHONPATH='src'
python -m sscre.benchmark_validate --phase2 --production
```

**2026-10-11:** passed (`leakage_status=passed`, `split_manifest_sha256=68912e3b…`).
