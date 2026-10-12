# Phase 4 Step 1 — Evaluation Audit Implementation Plan

## Goal

Execute parent Step 1 of
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md):
establish the exact evaluation starting state before any scoring, protocol,
provider, or held-out change.

This is a read-only audit. It does not authorize candidate-attribution code,
a protocol reset, a real embedding provider, development replay, or held-out
reporting.

**Status:** `closed (Step 1 audit)` — read-only audit executed 2026-10-12.  
**Evidence:**
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md).  
**Parent:**
[`PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md)
§ 10 Step 1.  
**Card:** `P4-SEMVALID` (parent § 5).

## Learning objectives

- [ ] Distinguish a current-manifest artifact from an artifact eligible for a
      new semantic headline comparison.
- [ ] Identify when reuse metrics score the request-record `reusable` label
      instead of the served candidate.
- [ ] Classify historical Phase 3 lineage without regenerating or deleting it.

## Prerequisites

- [x] Parent plan exists with hypothesis, pass/fail, and stopping rules
      (`P4-SEMVALID`).
- [x] Every path in this plan's **Parent**, **contracts**, and **Verification**
      blocks exists in the current checkout, or is recorded under
      **Open baseline gaps**.
- [x] User approval in writing to start this audit (user requested Step 1
      execution in chat, 2026-10-12).
- [x] Confirm the package is importable before running
      `python -m sscre.benchmark_validate` (`$env:PYTHONPATH='src'` at audit
      time; see evidence **Repository context**).

## Gates and stopping rules

**Gate A — authoring.** Closed when this plan exists, lists the audit corpus
below, and every linked path exists or is an explicit gap. Authoring is not
audit execution.

**Gate B — audit protocol.** Mirror parent § 5 (`P4-SEMVALID`) stopping rules
that apply before any implementation:

- Do not change scoring, replay bookkeeping, configs, artifacts, or code.
- Do not treat a current split-manifest hash as eligibility for the new
  C-versus-A claim.
- Do not relabel the already-used 215-record held-out split as fresh.
- Do not substitute `pass` or `fail` for unrun later steps; use `deferred`.
- If a listed command, marker, or path is missing, stop that check as
  `unavailable` and record the gap; do not invent a substitute.

**Gate C — audit close.** Close only when the evidence file contains a checked
inventory table, an eligible/ineligible artifact list, the current manifest
hash from `benchmark_validate`, and a classification of Phase 3 artifacts that
cite `68912e3b…`. Parent Step 1 boxes stay unchecked until that evidence exists.

## Audit corpus

Feature-card minimum (`P4-SEMVALID` / parent §§ 5 and 10):

- Parent Step 1 purpose, checkboxes, and exit evidence.
- [`../../src/sscre/baseline.py`](../../src/sscre/baseline.py)
- [`../../src/sscre/evaluation_statistics.py`](../../src/sscre/evaluation_statistics.py)
- [`../../src/sscre/evaluate.py`](../../src/sscre/evaluate.py)
- [`../../src/sscre/evaluation_labels.py`](../../src/sscre/evaluation_labels.py)
- [`../../benchmarks/split_manifest.json`](../../benchmarks/split_manifest.json)
- [`../../experiments/evaluation_config.json`](../../experiments/evaluation_config.json)
- Primary A/B/C reports listed in **Artifact inventory scope**.

Extended parent scope (parent §§ 3, 4, 7, and 11):

- [`../../sscre_full_review_2026-10-12_v2.md`](../../sscre_full_review_2026-10-12_v2.md)
- [`../SSCRE_PLAN.md`](../SSCRE_PLAN.md) §§ 20, 24, and 25
- [`../phase-2/SAFETY_EVALUATION_CONTRACT_v1.md`](../phase-2/SAFETY_EVALUATION_CONTRACT_v1.md)
- [`../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
- [`../../benchmarks/README.md`](../../benchmarks/README.md)
- [`../../src/sscre/embedding.py`](../../src/sscre/embedding.py),
  [`../../src/sscre/remote_embedding.py`](../../src/sscre/remote_embedding.py),
  [`../../src/sscre/compatibility.py`](../../src/sscre/compatibility.py)
- [`../../docker-compose.yml`](../../docker-compose.yml)
- [`../../scripts/phase2_remediation_inventory.py`](../../scripts/phase2_remediation_inventory.py)
- Evaluation tests listed in **Verification**
- Phase 3/4 paper manifests and remaining B/C fake-embedding artifacts in
  **Artifact inventory scope**

## Open baseline gaps

Record these during execution; do not pre-check them as closed.

- [x] Parent § 4 / § 8 still says
      `benchmarks/EVALUATION_LABEL_CONTRACT_v1.md` is missing. The file exists
      in this checkout. Resolve that parent-plan contradiction in evidence;
      do not leave the parent claiming a dead path.
- [x] `PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md` created at Step 1 close.
- [x] Phase 3 final comparison and paper artifacts still cite `68912e3b…`
      while the checkout manifest is expected `0aca5b8d…`. Classify; do not
      regenerate in this step.
- [x] Reconfirm branch `phase4/setup` HEAD against parent expected `b7eda9d`
      at execution time (authoring snapshot: `b7eda9d`).

## Inventory fields

One row per artifact. Put long definitions in the notes below, not in cells.

| Field | Required |
| --- | --- |
| Path | yes |
| Present on disk | yes |
| `git_commit` | yes, or `unrecorded` |
| `git_worktree_dirty` | yes, or `unrecorded` |
| `config_sha256` / `config_version` | yes, or `unrecorded` |
| `dataset_version` | yes, or `unrecorded` |
| `evaluation_split` | yes, or `unrecorded` |
| `split_manifest_sha256` | yes, or `unrecorded` |
| Nested baseline keys | yes for comparison reports |
| `embedding_model` | yes for B/C payloads |
| `embedding_dimension` | yes for B/C payloads |
| Cost fields | yes; note measured / estimated / synthetic / zero |
| Token fields | yes, or `unrecorded` |
| Lineage status | yes (see note) |
| New-comparison eligibility | yes (see note) |

Lineage status: `current-manifest`, `historical-stale` (`68912e3b…` or other
non-current hash), `unrecorded`, `missing`.

New-comparison eligibility is independent of lineage. An artifact is
`ineligible-new-comparison` if it uses `fake-embedding`, the already-used
held-out split, unmatched dataset/config/commit identity, or pre-attribution
scoring. `eligible-new-comparison` requires a fresh leakage-checked held-out
population, real fixed-dimension embeddings, and candidate-level scoring.
This audit is expected to find zero eligible headline artifacts; record that
explicitly rather than treating current-manifest Phase 2 regeneration as the
new semantic baseline.

## Artifact inventory scope

Primary A/B/C comparison and sweep reports:

- `artifacts/evaluation/phase3-final-held-out-comparison.json`
- `artifacts/evaluation/phase3-development-comparison.json`
- `artifacts/evaluation/workstream5-held-out-comparison.json`
- `artifacts/evaluation/workstream5-development-sweep.json`
- `artifacts/evaluation/phase3-development-threshold-sweep.json`
- `artifacts/evaluation/phase3-adaptive-held-out.json`
- `artifacts/evaluation/phase3-adaptive-development.json`

Extended parent scope (manifests, nested B/C identity, paper index):

- `artifacts/evaluation/phase3-results-preview.json`
- `artifacts/evaluation/phase3-paper-artifact-manifest.json`
- `artifacts/evaluation/phase4-paper-artifact-manifest.json`
- `artifacts/evaluation/phase4-selected-stack-pareto.json`
- `artifacts/evaluation/phase3-embedding-storage-baseline.json`
- `experiments/evaluation_config.json`
- `experiments/exact_cache_development.json`
- `experiments/milestone10_evaluation_development_report.json`
- `experiments/milestone10_evaluation_held_out_report.json`

Reuse [`../../scripts/phase2_remediation_inventory.py`](../../scripts/phase2_remediation_inventory.py)
as a read-only Phase 2 supplement. It does not cover the Phase 3 comparison
package. Prefer a documented read-only Python one-liner in evidence over a new
script. If the existing script is extended, keep it read-only and do not
change already-classified Phase 2 rows.

## Implementation steps

### Step 1 — Confirm corpus paths and commands

- [x] Confirm every file in **Audit corpus** and **Artifact inventory scope**
      exists; list any missing path as `unavailable`.
- [x] Confirm CLI options exist:
      `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production`
      (`--phase2` and `--production` are defined in
      [`../../src/sscre/benchmark_validate.py`](../../src/sscre/benchmark_validate.py)).
- [x] Confirm pytest markers in `pyproject.toml`: `real_provider` and the
      `ws8_postgres_*` opt-in markers. Default addopts deselect the WS8
      PostgreSQL markers.
- [x] Record `git rev-parse HEAD`, branch name, and whether the worktree is
      dirty. Do not include unrelated dirty paths in this audit's edits.
- [x] Confirm
      [`../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
      exists and record the parent-plan contradiction as a documentation gap.

### Step 2 — Inspect evaluation code

Read-only. Record function/module pointers in evidence; do not patch.

- [x] In [`../../src/sscre/baseline.py`](../../src/sscre/baseline.py), record
      how A, B, and C replay bookkeeping attach pair identity, direction,
      cache-hit, and the request record's `reusable` flag.
- [x] In [`../../src/sscre/evaluation_statistics.py`](../../src/sscre/evaluation_statistics.py),
      record that `reuse_outcome_indicators` currently scores
      `(direction, reusable, served_reuse)` against the request record, not a
      served-candidate provenance record.
- [x] In [`../../src/sscre/evaluate.py`](../../src/sscre/evaluate.py), record
      the CLI (`--baseline`, `--split`, `--config`, `--output`,
      `--production`, `--no-statistics`) and that held-out must be explicit.
- [x] Confirm label separation still matches
      [`../../src/sscre/evaluation_labels.py`](../../src/sscre/evaluation_labels.py)
      and the label contract (compatibility ≠ correctness ≠ preference).
- [x] Record exact-cache FPR behavior (present, `null`, or omitted) from code
      and from one exact-cache payload.
- [x] Record B/C default embedding identity from
      [`../../src/sscre/embedding.py`](../../src/sscre/embedding.py)
      (`fake-embedding`, dimension 8).
- [x] Record Compose default `SSCRE_SEMANTIC_STRATEGY` from
      [`../../docker-compose.yml`](../../docker-compose.yml) as a deployment
      safety gap (expected `B`). Do not change the file.

### Step 3 — Inventory artifacts and classify lineage

- [x] For every path in **Artifact inventory scope**, fill the inventory
      fields above.
- [x] For comparison reports, list nested `baselines` keys
      (`no-cache`, `exact-cache`, `embedding-cache`, `compatibility-cache`
      or actual keys present).
- [x] Classify each artifact's lineage status and new-comparison eligibility.
- [x] Classify every Phase 3 artifact citing `68912e3b…` as
      `historical-stale` and `ineligible-new-comparison`.
- [x] Classify regenerated Phase 2 artifacts on `0aca5b8d…` as
      `current-manifest` only if the hash matches; they remain
      `ineligible-new-comparison` while they use `fake-embedding` and the
      already-used held-out split.
- [x] List artifacts eligible vs ineligible for the new C-versus-A headline
      comparison, with one reason each.

### Step 4 — Confirm the current manifest

- [x] Run, from repo root, after the package is importable:

```powershell
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
```

- [x] Record the full `split_manifest_sha256`, dataset version, split counts,
      leakage status, and `cross_split_fingerprint_overlaps`.
- [x] Compare that hash to every inventoried `split_manifest_sha256`.
- [x] Do not regenerate artifacts if hashes disagree.

### Step 5 — Write evidence and close the audit

- [x] Create
      `docs/phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`
      with corpus, inventory table, eligible/ineligible list, manifest
      command output, code-attribution notes, Compose default, and
      label-contract resolution.
- [x] Label this inventory as the Step 1 starting snapshot. Later steps that
      close a gap must mark the corresponding Step 1 row historical or
      reconcile it in the same evidence pass.
- [x] Update parent § 10 Step 1 checkboxes and parent **Open baseline gaps**
      only for items this audit actually verified.
- [x] At Step 1 close (2026-10-12), parent Steps 2–8 were left unchecked and no
      attribution code was started (Step 2 began in a later change set).

## Verification

Run from the repository root after confirming every path and option exists.
Record the exact command and result in evidence. An unrun check is
`deferred`, not `pass`.

Path existence (PowerShell):

```powershell
python -c "from pathlib import Path; paths=['src/sscre/baseline.py','src/sscre/evaluation_statistics.py','src/sscre/evaluate.py','src/sscre/evaluation_labels.py','src/sscre/embedding.py','src/sscre/remote_embedding.py','src/sscre/compatibility.py','benchmarks/split_manifest.json','benchmarks/EVALUATION_LABEL_CONTRACT_v1.md','benchmarks/README.md','docs/phase-2/SAFETY_EVALUATION_CONTRACT_v1.md','experiments/evaluation_config.json','docker-compose.yml','scripts/phase2_remediation_inventory.py','artifacts/evaluation/phase3-final-held-out-comparison.json','artifacts/evaluation/phase3-development-comparison.json','artifacts/evaluation/workstream5-held-out-comparison.json','artifacts/evaluation/workstream5-development-sweep.json','artifacts/evaluation/phase3-development-threshold-sweep.json','artifacts/evaluation/phase3-adaptive-held-out.json','artifacts/evaluation/phase3-adaptive-development.json','artifacts/evaluation/phase3-results-preview.json','artifacts/evaluation/phase3-paper-artifact-manifest.json','artifacts/evaluation/phase4-paper-artifact-manifest.json','artifacts/evaluation/phase4-selected-stack-pareto.json','artifacts/evaluation/phase3-embedding-storage-baseline.json','tests/test_benchmark.py','tests/test_evaluation_labels.py','tests/test_workstream3_pure_evaluator.py','tests/test_workstream3_serialization.py','tests/test_evaluation_statistics.py']; missing=[p for p in paths if not Path(p).exists()]; print('listed',len(paths),'missing',len(missing)); [print('MISSING',p) for p in missing]"
```

Required:

```powershell
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
python scripts/phase2_remediation_inventory.py
```

Focused tests (existence and current collection; not a semantic-claim pass):

```powershell
python -m pytest -q tests/test_benchmark.py tests/test_evaluation_labels.py tests/test_workstream3_pure_evaluator.py tests/test_workstream3_serialization.py tests/test_evaluation_statistics.py tests/test_baseline_request_samples.py
```

Compose default may be read from `docker-compose.yml`. Optional config render
uses the same non-secret CI sample environment as `.github/workflows/ci.yml`.
If Docker is unavailable, record `unavailable`; do not treat a bare
`docker compose config` as a pass:

```powershell
$env:POSTGRES_PASSWORD = "ci-local-password"
$env:SSCRE_ADMIN_TOKEN = "ci-local-admin-token-123456"
docker compose config
```

Do not run `python -m pytest -q` as a Step 1 close requirement. Do not run
held-out or development evaluation commands in this step.

## Acceptance criteria

### Goal / Exit — authoring gate

- [x] This plan exists at
      `docs/phase-4/PHASE4_STEP1_EVALUATION_AUDIT_IMPLEMENTATION_PLAN.md`.
- [x] The plan links `P4-SEMVALID` and parent § 10 Step 1.
- [x] The audit corpus lists the card minimum and the broader parent scope.
- [x] Linked contract, source, test, artifact, and CLI paths exist, or are
      recorded under **Open baseline gaps**.

### Verification — audit execution gate

- [x] User approved starting the audit.
- [x] Inventory table is complete for every in-scope artifact.
- [x] Every Phase 3 artifact citing `68912e3b…` is classified
      `historical-stale` and ineligible for the new comparison.
- [x] Eligible vs ineligible lists exist; current-manifest fake-embedding
      results are not treated as the new semantic baseline.
- [x] `benchmark_validate --benchmark-dir benchmarks --phase2 --production`
      output is recorded, including the full manifest SHA-256.
- [x] Code inspection records request-record scoring vs served-candidate
      attribution, exact-cache FPR behavior, and `fake-embedding` / dimension 8.
- [x] The label-contract parent-plan contradiction is resolved in evidence.
- [x] Compose Strategy B default is recorded; the file is unchanged.
- [x] Evidence file exists; parent Step 1 boxes match that evidence.
- [x] No product-code, config, artifact, dependency, or held-out change
      occurred as part of this audit.

## Out of scope for this document

- Parent Steps 2–8 (attribution, protocol freeze, real embeddings, evaluation
  runs, gate scoring, roadmap close).
- Regenerating or deleting Phase 3 artifacts.
- Changing `docker-compose.yml` defaults.
- Adding an embedding dependency or model.
- Human correctness labeling.
- Full-suite pytest as a Step 1 close requirement.
- Committing or pushing without explicit user approval.
