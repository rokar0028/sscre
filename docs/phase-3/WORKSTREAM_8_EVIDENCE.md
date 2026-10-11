# Phase 3 Workstream 8 evidence — experiment-tracking gate

**Workstream:** 8 (Feature 5 audit)  
**Plan:** [`WORKSTREAM_8_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_8_IMPLEMENTATION_PLAN.md)  
**Status:** **closed** (Step 5, 2026-10-12). Feature 5 **pass**; decision **`keep_manual`**.

## Step 1 — Audit corpus loaded

Read-only inventory per Feature 5 card. No artifacts or code were modified.

### Manifests

| File | Role | Notes |
| --- | --- | --- |
| `artifacts/evaluation/phase4-paper-artifact-manifest.json` | Primary index | `schema_version` `phase4-artifact-manifest-1.0`; `status` `complete_with_documented_deferrals`; root `git_commit` `dc451fed…`; `dataset_version` `reviewed-query-pairs-2.0`; split SHA `68912e3b…`; statistics seed `42` / 1000 iterations / CI `0.95`. |
| `artifacts/evaluation/phase3-paper-artifact-manifest.json` | Historical preview | `status` `preview_before_final_held_out_run`; `dataset_version` **null**; defers final held-out — superseded by final package + Phase 4 manifest. |

### Phase 4 `tracks.*.artifacts[].path` (normalized)

| Track | Path | On disk |
| --- | --- | --- |
| P4-PARETO | `artifacts/evaluation/phase4-selected-stack-pareto.json` | yes |
| P4-PROVIDER | `artifacts/evaluation/phase4-provider-validation.json` | yes |
| P4-SCALE | `artifacts/evaluation/phase4-storage-profile.json` | yes |
| P4-SCALE | `artifacts/evaluation/phase4-scale-profile.json` | yes |

**Path check (2026-10-11):** `listed 4`, `missing 0`.

Phase 4 track evidence pointers (for Step 2 matrix):

| Track | Evidence doc |
| --- | --- |
| P4-PARETO | `docs/phase-4/PHASE4_PARETO_EVIDENCE.md` |
| P4-PROVIDER | `docs/phase-4/PHASE4_PROVIDER_EVIDENCE.md` |
| P4-RELEASE | `docs/phase-4/PHASE4_RELEASE_EVIDENCE.md` (no artifact paths) |
| P4-SCALE | `docs/phase-4/PHASE4_SCALE_EVIDENCE.md` |

Documented deferrals on Phase 4 manifest (not missing files): clean-checkout replay, credentialed provider, production-scale claim, GPU/int8.

### Phase 3 preview `sources.*` (normalized)

| Key | Path | On disk |
| --- | --- | --- |
| adaptive_held_out | `artifacts/evaluation/phase3-adaptive-held-out.json` | yes |
| development_comparison | `artifacts/evaluation/phase3-development-comparison.json` | yes |
| eviction_held_out | `artifacts/evaluation/phase3-held-out-eviction.json` | yes |
| frozen_held_out_comparison | `artifacts/evaluation/workstream5-held-out-comparison.json` | yes |
| frozen_held_out_pareto | `artifacts/evaluation/workstream5-held-out-pareto.json` | yes |
| threshold_map | `artifacts/evaluation/phase3-adaptive-threshold-map.json` | yes |

All six preview sources resolve. Final paper stack uses
`artifacts/evaluation/phase3-final-held-out-comparison.json` (not listed in preview
`sources`).

### Phase 3 final package (evidence + JSON header)

[`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md): documents CLI command,
commit `01166574615b3f43faf2adf6848a130df0c9a98e` (dirty worktree note), config
SHA `5734f113…`, dataset `reviewed-query-pairs-2.0`, split manifest SHA
`68912e3b…`, bootstrap seed `42`.

`phase3-final-held-out-comparison.json` report header (same day rerun): `git_commit`
`fe68ce3b3cc6cdc35507e8faebbea5549ce5b50e`, `git_worktree_dirty` **false**,
`config_sha256` / `config_version` match evidence; `benchmark_artifact.split_manifest_sha256`
`68912e3b…`; `statistics.by_baseline.*.random_seed` **42**. Commit mismatch vs
evidence prose is flagged for Step 2 (not scored as a gap in Step 1).

### Feature evidence corpus (Feature 5 minimum)

| Document | Loaded |
| --- | --- |
| `PHASE3_FEATURE_1_EVIDENCE.md` | yes |
| `PHASE3_FEATURE_2_EVIDENCE.md` | yes |
| `PHASE3_FEATURE_3_EVIDENCE.md` | yes |
| `PHASE3_ARTIFACTS_EVIDENCE.md` | yes |
| `PHASE3_FINAL_EVIDENCE.md` | yes |

### Verification cross-checks

| Source | Use in audit |
| --- | --- |
| [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) | Feature 5 promotion row `P3-FEAT-TRACK`; WS8 execution **pending** before Step 1 close. |
| [`../internal/PHASE4_IMPLEMENTATION_PLAN.md`](../internal/PHASE4_IMPLEMENTATION_PLAN.md) | Phase 4 verification log; manifest path `phase4-paper-artifact-manifest.json`. |

## Step 2 — Provenance matrix

One row per **paper result** (not one row per manifest track). Field values:
**present**, **missing**, or **deferred-with-reason**. Primary sources are each
result’s artifact plus its evidence markdown; Phase 4 manifest metadata is a
cross-check. Statistics/seed is required only when the result reports
confidence intervals.

Legend for split proof: held-out rows expect `split_manifest_sha256`; development
or ladder rows may use `development_sha256` or `workload_sha256` as an
equivalent when the protocol is not a held-out evaluate run.

| ID | Paper result | Artifact / record | Cmd | Commit | Config+SHA | Dataset | Split proof | Seed/CI | File | Remarks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | Phase 3 final held-out stack | `phase3-final-held-out-comparison.json` | present ([`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md)) | present (JSON `fe68ce3b…`; evidence `0116657…` — **mismatch**) | present (`experiments/evaluation_config.json`, `5734f113…`) | present | present (`68912e3b…` in `benchmark_artifact`) | present (`statistics.*.random_seed` 42) | present | Authoritative JSON header; evidence prose predates rerun commit. |
| R02 | Feature 1 adaptive held-out | `phase3-adaptive-held-out.json` | present ([`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md)) | present (JSON + evidence `8c659262…`, dirty note) | present (SHA in evidence; JSON `config_version` only — **SHA not in report root**) | present | present (`68912e3b…`) | present (seed 42, CIs in report) | present | |
| R03 | Feature 2 pattern eviction held-out | `phase3-held-out-eviction.json` | present ([`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md)) | present (JSON; evidence lacks commit line) | present | present | **missing** (`evaluation_split` only; no manifest SHA in artifact or F2 evidence) | present (metrics; no CI block — **n/a**) | present | Split SHA recoverable from R01/R02 corpus (`68912e3b…`); Step 3 to classify. |
| R04 | Strategy D gate (no validator run) | [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) | deferred-with-reason (no authorized evaluate run) | present (re-check cites final stack) | present (via R01) | present (via R01) | present (via R01) | n/a (no new CIs) | n/a | Process result; trigger not met. |
| R05 | Phase 3 preview artifact package | `phase3-paper-artifact-manifest.json` + Step 4 outputs | present ([`PHASE3_ARTIFACTS_EVIDENCE.md`](./PHASE3_ARTIFACTS_EVIDENCE.md)) | **missing** in manifest | **missing** (`config_version` only) | deferred-with-reason (`dataset_version` null in preview manifest) | deferred-with-reason (preview `sources` omit final comparison) | present (manifest `statistics` block) | present | **Superseded** by R01; historical preview only. |
| R06 | Float32 embedding storage baseline | `phase3-embedding-storage-baseline.json` | present ([`PHASE3_QUANTIZATION_EVIDENCE.md`](./PHASE3_QUANTIZATION_EVIDENCE.md)) | present | present | present | present (`development_sha256`) | n/a (point estimates) | present | Development split; not held-out evaluate. |
| R07 | Load ladder (in-memory) | `phase3-load-ladder-memory.json` | present ([`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md)) | present | present (`experiments/phase3_load_ladder_v1.json`, `8412af81…`) | present | present (`development_sha256`) | present (ladder seed `20261011`; no CIs — workload seed) | present | |
| R08 | Load ladder (PostgreSQL) | `phase3-load-ladder-postgres.json` | present ([`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md)) | present | present | present | present (`development_sha256`) | present (seed `20261011`) | present | Same protocol as R07. |
| R09 | Failure clustering (manual) | [`PHASE3_FAILURE_CLUSTERS.md`](./PHASE3_FAILURE_CLUSTERS.md) | present (read-only sanity in doc) | present (from R01 source JSON) | present (from R01) | present (via R01) | present (via R01) | n/a (counts only) | present (source JSON on disk) | No new evaluate run. |
| R10 | Phase 4 selected-stack Pareto | `phase4-selected-stack-pareto.json` | present ([`PHASE4_PARETO_EVIDENCE.md`](../phase-4/PHASE4_PARETO_EVIDENCE.md)) | present (provenance + evidence) | present | present | present (provenance `split_manifest_sha256`) | present (seed 42; curve CIs in artifact) | present | |
| R11 | Phase 4 provider validation | `phase4-provider-validation.json` | present ([`PHASE4_PROVIDER_EVIDENCE.md`](../phase-4/PHASE4_PROVIDER_EVIDENCE.md)) | present | present (`configuration.path` + version) | present | present (development benchmark block) | n/a (`unavailable` status) | present | No live provider; not a reuse metric result. |
| R12 | Phase 4 storage profile | `phase4-storage-profile.json` | present ([`PHASE4_SCALE_EVIDENCE.md`](../phase-4/PHASE4_SCALE_EVIDENCE.md)) | present (provenance) | present (`evaluation_config_sha256` in provenance) | present (`phase4-storage-profile-v1`) | present (`workload_sha256`) | n/a | present | Bounded synthetic workload. |
| R13 | Phase 4 scale profile | `phase4-scale-profile.json` | present ([`PHASE4_SCALE_EVIDENCE.md`](../phase-4/PHASE4_SCALE_EVIDENCE.md)) | present (provenance) | **missing** (workload config SHA only in provenance) | deferred-with-reason (milestone load workload, not reviewed pairs split) | present (`workload_sha256`) | n/a | present | Config path documented in evidence (`milestone10_load_v1.json`). |
| R14 | Phase 4 release / handoff audit | [`PHASE4_RELEASE_EVIDENCE.md`](../phase-4/PHASE4_RELEASE_EVIDENCE.md) | present (verification table) | present (audit notes dirty tree) | n/a | n/a | n/a | n/a | n/a | Process gate; clean-checkout replay **deferred-with-reason** on manifest. |

**Matrix summary (2026-10-12):** **14** paper results audited (includes one
superseded preview row R05 and one process-only row R14). Phase 4 manifest
artifact paths remain **4/4** on disk (Step 1).

**Strict `missing` cells (classified in Step 3 below):** R01 commit alignment;
R02 optional artifact header; R03 split SHA + evidence header; R05 superseded
preview; R13 scale profile config crosswalk.

## Step 3 — Gap classification

Scored against Feature 5 protocol ([`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 5).
No artifacts or code were modified during classification.

### Inventory counts

| Metric | Value | Source |
| --- | ---: | --- |
| `artifacts_in_manifest` | **4** | `phase4-paper-artifact-manifest.json` `tracks.*.artifacts[]` |
| `artifacts_missing_on_disk` | **0** | Step 1 path check (`listed 4`, `missing 0`) |
| `results_audited` | **14** | Step 2 matrix (includes superseded R05 and process R14) |
| `results_active_paper` | **12** | Excludes R05 (superseded preview) and R14 (release process gate) |

### `repro_blocked_gaps`

**0** — For every active paper result, command (or generator), git commit (or
dirty note), config hash, dataset version, and split proof are recoverable from
the artifact, its evidence file, or a sibling artifact in the audit corpus (e.g.
R03 split SHA from R01/R02; R09 via R01). None require a tracker or new
evaluate run to reconstruct.

### `manifest_fixable_gaps`

**5** documentation-only items (optional artifact header enrichment noted where
applicable):

| Gap ID | Result | Field | Source | Remedy (doc-only) |
| --- | --- | --- | --- | --- |
| G1 | R01 | Git commit alignment | [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md) vs `phase3-final-held-out-comparison.json` | Set evidence commit to `fe68ce3b3cc6cdc35507e8faebbea5549ce5b50e` or add one line that the JSON header is authoritative after protocol-reset rerun. |
| G2 | R02 | `config_sha256` in report root | `phase3-adaptive-held-out.json` | No blocker: SHA is in Feature 1 evidence. Optional: one-line cross-link in F1 evidence that held-out JSON carries `config_version` only. |
| G3 | R03 | Split manifest SHA-256 | F2 evidence + eviction JSON | Add `Split manifest SHA-256: 68912e3b…` to [`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md) header (same as Feature 1 / final package). |
| G4 | R03 | Git commit in evidence header | F2 evidence | Add `Base commit` / dirty note matching JSON `8c659262…` (already on artifact). |
| G5 | R13 | Config path + hash at report root | `phase4-scale-profile.json` | Add explicit `experiments/milestone10_load_v1.json` + `workload_sha256` from provenance to [`PHASE4_SCALE_EVIDENCE.md`](../phase-4/PHASE4_SCALE_EVIDENCE.md) provenance table. |

R01 **commit mismatch** is **manifest_fixable**, not `repro_blocked`: both
commits are recorded and the frozen JSON supplies a complete header.

### Explicit deferrals (not scored as gaps)

| Item | Reason | Record |
| --- | --- | --- |
| R05 preview manifest | Superseded by final held-out package (R01) | `phase3-paper-artifact-manifest.json` `status` `preview_before_final_held_out_run` |
| R04 Strategy D | Trigger not met; no validator evaluate authorized | [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) |
| Clean-checkout replay | Explicit Phase 4 deferral | `phase4-paper-artifact-manifest.json` `deferred[]` |
| Credentialed provider / GPU / production scale | Out of scope deferrals | Same manifest `deferred[]` + R11 `unavailable` |

### Seed / statistics (no false gaps)

Confirmed **n/a** (not missing) for rows without uncertainty claims: R03
(point metrics only), R06–R09, R11–R13. R07/R08 ladder seed `20261011` is a
workload seed, not bootstrap CI metadata.

### Pre-registered pass rule (scored Step 4)

- Phase 4 manifest paths: **pass** (0 missing on disk).
- `repro_blocked_gaps`: **0**.
- Phase 3 final held-out: command, commit, config hash, dataset version,
  split-manifest hash, and seed in
  [`PHASE3_FINAL_EVIDENCE.md`](./PHASE3_FINAL_EVIDENCE.md) and/or
  `phase3-final-held-out-comparison.json` — **pass** (G1 is doc alignment only).

## Step 4 — Decision

**Audit date:** 2026-10-12
**Feature 5 verdict:** **pass** (pre-registered audit pass rule)
**Decision:** **`keep_manual`**

Manual JSON under `artifacts/`, phase evidence markdown, and
`phase4-paper-artifact-manifest.json` are **sufficient** for reproducibility.
Do **not** add MLflow, Weights & Biases, or another experiment-tracking
dependency for Phase 3 v1 (stopping rule).

| Field | Value |
| --- | --- |
| `repro_blocked_gaps` | **0** |
| `manifest_fixable_gaps` | **5** (G1–G5; optional doc hygiene, not audit blockers) |
| Tracker dependency added? | **no** (confirmed: no MLflow/W&B in project dependencies) |
| Held-out replay / product code changed for audit? | **no** |

### Optional doc follow-up (not required for `keep_manual`)

G1–G5 from Step 3 may be closed in a separate documentation-only pass
(Workstream 9 manifest sync or ad hoc). The audit **pass** does not depend on
applying those edits.

## Step 5 — Close

**Date:** 2026-10-12

- [x] [`WORKSTREAM_1_EVIDENCE.md`](./WORKSTREAM_1_EVIDENCE.md) updated (promotion
      row, pre-code gate WS8, verification log).
- [x] Parent [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
      Workstream 8 status, execution order, and top-level status synced.
- [x] [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) Implementation progress — Feature 5 entry.
- [x] [`README.md`](./README.md) index line updated.
- [x] Optional doc follow-up G1–G5: **not** required for audit pass; may land in
      Workstream 9 manifest sync (unchecked backlog).

Path-resolution re-check (same command as plan § Verification):

```powershell
python -c "import json, pathlib; m=json.load(open('artifacts/evaluation/phase4-paper-artifact-manifest.json',encoding='utf-8')); paths=[a['path'].replace(chr(92),'/') for t in m.get('tracks',{}).values() for a in t.get('artifacts',[])]; missing=[p for p in paths if not pathlib.Path(p).exists()]; print('listed',len(paths),'missing',len(missing))"
```

**Output (2026-10-12):** `listed 4 missing 0`
