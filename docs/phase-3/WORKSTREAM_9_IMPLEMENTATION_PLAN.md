# Phase 3 Workstream 9 Implementation Plan

## Goal

Close the Phase 3 final package by synchronizing the master roadmap, the
machine-readable artifact manifest, the limitations narrative, and the Phase 3
documentation index with the evidence already produced by Workstreams 5–8.
This is a documentation and provenance pass; it does not authorize a new
evaluation, held-out access, product-code change, or dependency.

**Status:** **closed** (Step 4, 2026-10-12).  
**Evidence:** [`WORKSTREAM_9_EVIDENCE.md`](./WORKSTREAM_9_EVIDENCE.md).  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 9.  
**Card:** N/A — final-package synchronization of already-approved workstreams.

## Learning objectives

- [ ] Reconcile a human-readable roadmap with frozen evidence without changing
      the meaning of conditional or deferred work.
- [ ] Extend an artifact manifest without silently replacing historical
      provenance or rerunning experiments.
- [ ] State synthetic-replay, provider, label, storage, and load limitations
      alongside the corresponding results.

## Scope and non-goals

In scope:

- `docs/SSCRE_PLAN.md` § 20 Phase 3 checklist synchronization.
- `artifacts/evaluation/phase4-paper-artifact-manifest.json` as the primary
  machine-readable manifest, with
  `phase3-paper-artifact-manifest.json` retained as the historical preview.
- Limitations and status text in `docs/phase-3/PHASE3_PLAN.md`.
- The status and file index in `docs/phase-3/README.md`.
- A close record in [`WORKSTREAM_9_EVIDENCE.md`](./WORKSTREAM_9_EVIDENCE.md).

Out of scope:

- Re-running any held-out or development evaluation.
- Changing `src/`, experiment behavior, schemas, dependencies, or artifact
  contents.
- Adding MLflow, W&B, a dashboard, or another tracking service.
- Marking conditional int8 quantization as tested when its authorization gate
  did not open.
- Claiming live-provider accuracy, production capacity, or a reached bottleneck.

## Gates and stopping rules

**Gate A — corpus and approval.** Before editing any deliverable, confirm every
referenced evidence file, artifact path, manifest field, and target checklist
exists in the current checkout. Record the current git status and obtain user
approval to execute this documentation plan.

**Gate B — evidence fidelity.** Each status change must point to an existing
evidence section or artifact. If a result cannot be traced, stop the relevant
sync and record the gap; do not infer a result from a neighboring workstream.

**Gate C — close.** Close Workstream 9 only when the manifest path audit,
master-plan checklist, limitations, README, and verification results agree.
If a full-suite or compose verification is unavailable or fails, leave that
criterion unchecked and record the exact outcome.

## Evidence-to-sync map

| Result | Canonical evidence | Manifest / artifact scope |
| --- | --- | --- |
| Float32 storage baseline and int8 deferral | `PHASE3_QUANTIZATION_EVIDENCE.md` § Step 6 | `phase3-embedding-storage-baseline.json`; no int8 compare artifact |
| Memory and PostgreSQL load ladder | `PHASE3_LOAD_EVIDENCE.md` § Step 6 | `phase3-load-ladder-memory.json` and `phase3-load-ladder-postgres.json` |
| Failure-cluster inventory | `PHASE3_FAILURE_CLUSTERS.md` § Step 5 | `PHASE3_FAILURE_CLUSTERS.md` plus frozen source artifacts |
| Provenance audit and `keep_manual` decision | `WORKSTREAM_8_EVIDENCE.md` § Steps 4–5 | Phase 4 manifest and audited paper-result entries |

## Implementation steps

### Step 1 — Audit the synchronization corpus

**Step status:** complete (2026-10-12). Inventory:
[`WORKSTREAM_9_EVIDENCE.md`](./WORKSTREAM_9_EVIDENCE.md) § Step 1.

- [X] Read the parent Workstream 9 section and all unchecked acceptance criteria in `PHASE_3_IMPLEMENTATION_PLAN.md`.
- [X] Read `docs/SSCRE_PLAN.md` § 20 and preserve its pre-registered meaning (int8 stays unchecked; gate below `0.20`).
- [X] Read the feature-card minimum inputs in `PHASE3_PLAN.md` (Feature 5 decision table, limitations, non-goals).
- [X] Audit WS5–8 paper-result artifacts and evidence, not only the four Phase 4 manifest paths.
- [X] Confirm required evidence files and manifests exist on disk (11-path check; re-run 2026-10-12 → `missing 0`).
- [X] Record initial status and corpus inventory in `WORKSTREAM_9_EVIDENCE.md` § Step 1.

### Step 2 — Synchronize the artifact manifest

**Step status:** complete (2026-10-12). Details:
[`WORKSTREAM_9_EVIDENCE.md`](./WORKSTREAM_9_EVIDENCE.md) § Step 2.

- [X] Use `phase4-paper-artifact-manifest.json` as the primary manifest; Phase 3 preview manifest unchanged.
- [X] Add WS5–WS8 tracks with evidence links, provenance, and measurement labels (`4` → `9` artifact paths).
- [X] Baseline + `P3-FEAT-Q8` deferral (`not_authorized_deferred`); no int8 compare artifact.
- [X] Memory and PostgreSQL load ladders; `first_bottleneck` `not_reached` in metadata.
- [X] Manual clustering doc + frozen input paths and redaction note in metadata.
- [X] P4 tracks and artifact SHA-256 values preserved.
- [X] SHA-256 computed from on-disk files for new entries only.
- [X] Before/after counts and paths recorded in evidence § Step 2.

### Step 3 — Synchronize the roadmap and limitations

**Step status:** complete (2026-10-12). Details:
[`WORKSTREAM_9_EVIDENCE.md`](./WORKSTREAM_9_EVIDENCE.md) § Step 3.

- [X] `SSCRE_PLAN.md` Phase 3 rows synced with evidence links (9 checked, int8 unchecked).
- [X] int8 row left `[ ]` with dominance-gate deferral note.
- [X] Strategy D rows checked as not implemented / N/A at held-out FPR `0.0`.
- [X] `PHASE3_PLAN.md` § Limitations updated (storage, load, clustering, tracking).
- [X] Limitations state synthetic replay, no live-provider table, no production SLA.
- [X] `PHASE3_PLAN.md` last-updated 2026-10-12; non-goals aligned with measured WS5–6.
- [X] `README.md` status line updated (WS9 Steps 1–3 closed).
- [X] Parent tracker WS9 acceptance and execution order synced in the same pass.

### Step 4 — Verify and close

**Step status:** complete (2026-10-12). Details:
[`WORKSTREAM_9_EVIDENCE.md`](./WORKSTREAM_9_EVIDENCE.md) § Step 4.

- [X] Primary manifest path audit recorded (`9` listed, `0` missing).
- [X] Both manifests valid JSON; `0` duplicate artifact paths.
- [X] Doc-only diff review (no `src/` changes in WS9 scope).
- [X] `pip install`, pytest, benchmark_validate run; compose with CI sample env.
- [X] Outcomes recorded in evidence (bare compose fails without env — expected).
- [X] Workstream closed; parent, README, and master plan aligned.

## Acceptance criteria

- [X] Every WS5–WS8 paper result indexed (Step 2) or deferral documented (`P3-FEAT-Q8`).
- [X] All manifest paths resolve; JSON valid (Step 4).
- [X] `SSCRE_PLAN.md` § 20 reflects completed, deferred, and conditional work
      without converting an unrun feature into a pass (Step 3).
- [X] Limitations state the measured storage, load, clustering, tracking, and
      synthetic-replay boundaries (Step 3).
- [X] `PHASE3_PLAN.md`, `README.md`, and the parent tracker have matching status
      and links (Step 3).
- [X] Verification outcomes recorded with exact commands (Step 4).
- [X] No evaluation, held-out access, product-code change, dependency, or tracker added.

## Verification commands

Run from the repository root after confirming every referenced path and option
exists:

```powershell
python -c "import json, pathlib; m=json.load(open('artifacts/evaluation/phase4-paper-artifact-manifest.json',encoding='utf-8')); paths=[a['path'].replace(chr(92),'/') for t in m.get('tracks',{}).values() for a in t.get('artifacts',[])]; missing=[p for p in paths if not pathlib.Path(p).exists()]; print({'listed':len(paths),'missing':len(missing)}); [print('MISSING',p) for p in missing]"
python -m json.tool artifacts/evaluation/phase4-paper-artifact-manifest.json > $null
python -m pip install ".[dev]"
python -m pytest -q
python -m sscre.benchmark_validate --phase2 --production
$env:POSTGRES_PASSWORD='ci-local-password'
$env:SSCRE_ADMIN_TOKEN='ci-local-admin-token-123456'
docker compose config
```

The path audit and JSON validation are required for this documentation pass.
The full suite, benchmark validation, and Compose validation are release
checks. Compose requires the non-secret CI sample environment above; a bare
`docker compose config` invocation is not a valid pass/fail check because the
repository intentionally requires `SSCRE_ADMIN_TOKEN`.

## Handoff

After close, the Phase 3 package is documentation-synchronized. Any later
provider, human-label, production-scale, GPU, Strategy D, or int8 work requires
its own scope/protocol decision and must not reuse this close as authorization.
