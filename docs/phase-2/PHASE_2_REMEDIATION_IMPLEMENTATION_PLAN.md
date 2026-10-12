# SSCRE Phase 2 Remediation Implementation Plan

## Goal

Restore a reproducible and accurately scoped Phase 2 record after the
read-only audit of the implementation, evidence, artifacts, and plans.

This plan prioritizes provenance and claim correctness before optional new
experiments. It does not assume that every identified evidence gap must be
implemented; each resource-dependent experiment has a separate decision gate.

## Status

`closed` (2026-10-12) — Steps 1–7 complete. Phase 2 remediation restored
reproducible artifact lineage, dashboard manifest checks, reconciled
documentation, and explicit **keep-deferred** optional gates A–E. See
[`PHASE_2_REMEDIATION_EVIDENCE.md`](./PHASE_2_REMEDIATION_EVIDENCE.md) § Step 7
for the final limitations statement and Step 7 verification.

## Evidence

[`PHASE_2_REMEDIATION_EVIDENCE.md`](./PHASE_2_REMEDIATION_EVIDENCE.md)

## Parent

- [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md)
- [`../SSCRE_PLAN.md`](../SSCRE_PLAN.md)

## Card

This document is the remediation workstream card. It is subordinate to the
frozen Phase 2 contracts and must not introduce a second decision, label,
trace, or serialization model.

## Audit baseline (historical — pre-remediation)

The read-only audit that opened this workstream found that Strategy C safety
and failure-closed behavior were substantially implemented and tested, but the
**Phase 2 claim package** was not defensible because:

- checked-in evaluation artifacts reference manifest SHA
  `68912e3b…`, while the current manifest hashes to
  `0aca5b8d…`;
- correctness and preference labels are absent from all 615 benchmark records;
- held-out freshness evidence contains no semi-dynamic or dynamic records;
- no credentialed real-provider run exists;
- live PostgreSQL restart testing was skipped;
- the held-out storage Pareto plane is unavailable;
- several plan, evidence, and approval statuses contradict one another;
- Strategy B remains outside the canonical Strategy C compatibility path.

**Post-remediation verification baseline** (Step 5 and Step 7, 2026-10-12):

- `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production`
  — passed; manifest `0aca5b8d…`; 615 records; `cross_split_fingerprint_overlaps=0`.
- `python scripts/phase2_remediation_inventory.py` — WS5/WS6/WS7/WS9 evaluation
  artifacts `current`; WS3 `historical`; WS4 `unavailable` / `not_comparable`.
- `python -m pytest -q` — **767 passed**, 15 skipped, 21 deselected, 1 warning.

## Scope and non-goals

### Included

- Artifact and manifest provenance.
- Dashboard lineage validation.
- Plan, evidence, and acceptance-status synchronization.
- Explicit narrowing of unsupported Phase 2 claims.
- Reproducibility reruns and regression tests.
- User-gated decisions for correctness labels, provider measurements,
  freshness coverage, PostgreSQL restart, and storage evaluation.

### Not automatically included

- New provider spending.
- Human annotation work without an approved protocol and resources.
- Live database restart testing without an approved safe environment.
- New Phase 3 features.
- Replacing the frozen Phase 2 decision, label, trace, or serialization
  contracts.

## Exit criteria

Phase 2 remediation may close only when:

- [x] All checked-in artifacts either match the current benchmark manifest or
  are explicitly marked historical and excluded from current conclusions.
- [x] Dashboard validation verifies the current manifest rather than relying
  only on copied artifact metadata (Step 3; `repo_lineage` in WS9 export).
- [x] Plan, evidence, and roadmap statuses agree about complete, deferred,
  unavailable, and approval-gated work (Steps 4 and 7).
- [x] Current verification commands pass after remediation (Steps 5 and 7).
- [x] The final Phase 2 conclusion distinguishes compatibility evidence from
  correctness, provider, freshness, storage, and operational evidence (evidence
  § Step 7).
- [x] Every optional evidence gap has an explicit keep-deferred or approved
  implementation decision (Step 6: all gates **keep-deferred**, 2026-10-12).

## Execution sequence

1. [x] Freeze the audit baseline and artifact inventory.
2. [x] Repair artifact lineage.
3. [x] Repair dashboard provenance validation.
4. [x] Reconcile plans, evidence, and claims.
5. [x] Rerun reproducibility and regression verification.
6. [x] Review optional evidence gates.
7. [x] Close or defer the remediation workstream with synchronized evidence.

## Step 1 — Freeze the baseline and inventory

### Goal / Exit

Record the current manifest hash, artifact hashes, generation commits, config
hashes, dataset versions, split identities, and current working-tree state
before changing remediation files or artifacts.

### Tasks

- [x] Create `WORKSTREAM_10`-style remediation evidence at
  `docs/phase-2/PHASE_2_REMEDIATION_EVIDENCE.md`.
- [x] Record the exact current `benchmarks/split_manifest.json` SHA-256.
- [x] Inventory WS5–WS9 artifact manifest identities and generation metadata.
- [x] Record which artifacts are current, stale, historical, unavailable, or
  not comparable.
- [x] Record the existing unrelated working-tree modification without
  including it in remediation changes.

### Verification

- [x] `Get-FileHash benchmarks\split_manifest.json -Algorithm SHA256`
  matches the evidence record (`0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9`).
- [x] Read-only inventory:
  `python scripts/phase2_remediation_inventory.py` (see evidence § Step 1).

## Step 2 — Repair artifact lineage

### Goal / Exit

Ensure the current evaluation package can be regenerated from the current
benchmark, split manifest, configuration, and source code.

### Tasks

- [x] Decide whether the current manifest or the historical `68912e3b…`
  manifest is authoritative for the final Phase 2 package.
  - **Decision:** current checkout manifest `0aca5b8d…` is authoritative.
- [x] If the current manifest is authoritative, regenerate WS5 comparison and
  Pareto artifacts (including development sweep input).
- [x] Regenerate WS6 development and held-out freshness artifacts on the
  current manifest (held-out uses frozen development policy).
- [x] Regenerate the WS7 quality package from the regenerated WS5/WS6 inputs.
- [x] Regenerate the WS9 dashboard from the synchronized WS5–WS8 package.
- [x] Update remediation evidence and affected workstream evidence notes (see
  [`PHASE_2_REMEDIATION_EVIDENCE.md`](./PHASE_2_REMEDIATION_EVIDENCE.md) § Step 2).
- [x] Preserve superseded content as historical via Step 1 file hashes
  (in-place regen at canonical paths; no duplicate artifact filenames).

### Verification

- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production`
  passed (2026-10-12).
- [x] WS5/WS6/WS7/WS9 evaluation artifacts record manifest `0aca5b8d…`
  (`workstream5-held-out-pareto.json` has no manifest field; provenance via
  development sweep).
- [x] Regeneration commands exited 0 (recorded in remediation evidence).
- [x] Stale “aligned” / “final” wording reconciled in Step 4 (WS5/WS6/WS7/WS9
  and parent plans).

## Step 3 — Repair dashboard provenance validation

### Goal / Exit

Prevent the dashboard from accepting internally consistent but stale artifact
lineage.

### Tasks

- [x] Add a dashboard-side hash check for the current
  `benchmarks/split_manifest.json` (`src/sscre/dashboard.py`,
  `repo_lineage` block).
- [x] Keep historical or diagnostic artifact loading explicit and opt-in
  (`--allow-metadata-mismatch` / `allow_stale_manifest=True`).
- [x] Replace hard-coded current-manifest expectations in tests with
  `file_sha256(split_manifest.json)` (`tests/test_workstream9_dashboard.py`).
- [x] Preserve explicit `metadata_mismatch` behavior for mismatched sources.
- [x] Add a regression test where all artifacts agree with one another but
  disagree with the current manifest.

### Verification

- [x] Dashboard export fails closed for stale lineage without override
  (`test_repo_lineage_fails_when_sources_agree_on_stale_manifest`,
  `test_export_requires_explicit_override_for_metadata_mismatch`).
- [x] Dashboard export succeeds for regenerated current artifacts
  (re-export 2026-10-12; `test_export_writes_json_and_html_from_the_view_manifest`).
- [x] `python -m pytest -q tests/test_workstream9_dashboard.py` — **22 passed**
  (2026-10-12).

## Step 4 — Reconcile plans, evidence, and claims

### Goal / Exit

Make the documentation tell one consistent story without changing evidence
into a stronger claim.

### Tasks

- [x] Update `docs/SSCRE_PLAN.md` Phase 2 checkboxes and notes to reflect the
  current implementation and explicit gaps.
- [x] Update `PHASE_2_IMPLEMENTATION_PLAN.md` so every broad acceptance claim
  is narrowed where evidence is limited.
- [x] Label WS3 old 32-pair records as historical.
- [x] Reconcile WS5 “final” wording with its incomplete full development replay
  and unavailable storage plane.
- [x] Reconcile WS6 “mostly complete” wording with stable-only held-out
  freshness evidence and manifest status.
- [x] Reconcile WS7 and WS9 implementation closure with their open handoff or
  user-approval gates.
- [x] Reconcile WS8 completion wording with skipped live restart and bounded
  local PostgreSQL scope (unchanged in WS8 evidence; referenced in parent plan
  scope section).
- [x] State explicitly that correctness and preference labels are unavailable.
- [x] State explicitly that real-provider measurements are unavailable.
- [x] State explicitly that Strategy B is an opt-in unsafe baseline, not the
  canonical compatibility path.
- [x] Clarify the relationship between the 500-pair Phase 2 gate and the
  original 2,000+ roadmap target.

### Verification

- [x] Checklist audit: parent plan, `SSCRE_PLAN.md`, and WS5–WS9 evidence
  reconciled 2026-10-12 (see remediation evidence § Step 4).
- [x] Deferred items retain reason/consequence in WS4/WS5/WS6/WS9 evidence and
  parent **Phase 2 scope and limitations**.
- [x] Defensible Phase 2 conclusion is **synthetic compatibility safety/reuse**
  only (remediation evidence § Step 4).

## Step 5 — Reproducibility and regression rerun

### Goal / Exit

Verify the repaired package from the current checkout.

### Tasks

- [x] Run the benchmark validator.
- [x] Run the full test suite.
- [x] Run WS5 evaluation and Pareto commands.
- [x] Run WS6 freshness development and held-out commands.
- [x] Run WS7 gallery export and redaction validation.
- [x] Run WS9 dashboard export and dashboard tests.
- [x] Run applicable lint/editor diagnostics on changed Python files
  (`ruff` unavailable; IDE diagnostics clean on `dashboard.py` and
  `test_workstream9_dashboard.py`).
- [x] Record all commands, results, skips, deselections, warnings, and
  environment requirements in the remediation evidence file.

### Verification

- [x] `python -m pytest -q` passes after remediation (**767 passed**, 2026-10-12).
- [x] All required artifact-generation commands pass.
- [x] Skipped provider/PostgreSQL tests are recorded as unavailable, not passed.
- [x] The final artifact package passes its own provenance checks.

## Step 6 — Optional evidence gates

These tasks remain unauthorized until their resources, protocol, and value are
approved. A deferred item is not a failed item.

**Step 6 outcome (2026-10-12):** no gate received a new approval package in
this pass. Each gate is recorded **keep-deferred** in
[`PHASE_2_REMEDIATION_EVIDENCE.md`](./PHASE_2_REMEDIATION_EVIDENCE.md) § Step 6.
Re-opening a gate requires explicit approval of protocol, owner, and resources
before the implementation tasks below may be checked off.

### Gate A — Correctness and preference labels

- [ ] Approve an annotation protocol, sampling plan, adjudication rules, and
  resource owner.
- [ ] Add independent correctness labels where answers are available.
- [ ] Add preference labels only for explicit answer comparisons.
- [ ] Re-run only the reports whose claims depend on those labels.
- [x] Record a keep-deferred decision if annotation resources are unavailable.
  — **Decision:** `keep-deferred` (no protocol or annotation budget approved).

### Gate B — Real-provider measurement

- [ ] Approve provider, model, budget, credentials, and redaction protocol.
- [ ] Run a development-only credentialed measurement.
- [ ] Keep live-provider metrics separate from synthetic metrics.
- [x] Record a keep-deferred decision if no safe budget or credentials exist.
  — **Decision:** `keep-deferred` (WS4 unavailable artifact; no credentialed run).

### Gate C — Freshness coverage

- [ ] Approve a benchmark expansion that guarantees semi-dynamic and dynamic
  records in both development and held-out splits.
- [ ] Freeze the expanded split before replay.
- [ ] Re-run freshness policy selection only on development.
- [ ] Evaluate the frozen policy on held-out data.
- [x] Record a keep-deferred decision and retain the stable-only claim if the
  split cannot be expanded safely.
  — **Decision:** `keep-deferred` (held-out remains stable-only on `0aca5b8d…`).

### Gate D — PostgreSQL restart

- [ ] Approve a safe local restart protocol and failure-injection environment.
- [ ] Run restart during lookup, generation persistence, insert, and cleanup.
- [ ] Verify failure-closed behavior and recovery.
- [x] Record a keep-deferred decision if live restart is not required for the
  final claim.
  — **Decision:** `keep-deferred` (narrowed Phase 2 ops claim; WS8 bounded package).

### Gate E — Held-out storage evaluation

- [ ] Approve a storage protocol aligned to the authoritative benchmark,
  configuration, and manifest.
- [ ] Generate the held-out storage companion.
- [ ] Attach the storage plane to WS5 and WS9 only after provenance checks pass.
- [x] Record a keep-deferred decision if storage remains a documented
  unavailable plane.
  — **Decision:** `keep-deferred` (reuse/storage Pareto plane unavailable per WS5).

### Step 6 verification

- [x] Each gate has an explicit `keep-deferred` or `approved` decision in
  remediation evidence (all **keep-deferred**).
- [x] Deferred gates do not expand Phase 2 claims beyond Step 4 reconciliation.
- [x] Implementation tasks for deferred gates remain unchecked (unauthorized).

## Step 7 — Close or defer remediation

### Goal / Exit

Publish a synchronized, honest Phase 2 status and preserve a clear boundary
between implemented evidence and future work.

### Tasks

- [x] Update this plan’s Status, Exit criteria, Execution sequence, and
  acceptance results.
- [x] Update the parent Phase 2 plan in the same pass as its evidence.
- [x] Update the Phase 2 documentation index if new evidence files were added
  (no new evidence filenames; README remediation row updated).
- [x] Record each optional gate as approved, completed, or explicitly deferred
  (Step 6: all **keep-deferred**).
- [x] Write the final Phase 2 limitations and conclusions statement (evidence
  § Step 7).
- [x] Re-run broad verification after the final documentation and artifact
  changes (2026-10-12; evidence § Step 7).

### Final acceptance

- [x] Phase 2 is described as complete only to the level supported by current
  evidence.
- [x] Current artifact lineage is reproducible (Step 2 commands; Step 5 rerun).
- [x] No Phase 3 or Phase 4 evidence is used to fill a Phase 2 gap.
- [x] Remaining gaps are visible in the parent plan and final limitations.

## Acceptance results (close-out)

| Item | Result |
| --- | --- |
| Authoritative manifest | `0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9` |
| Canonical WS5–WS9 evaluation package | Regenerated and re-verified (Steps 2, 5) |
| Optional gates A–E | All **keep-deferred** (Step 6) |
| Defensible Phase 2 claim | Synthetic Strategy C compatibility safety/reuse on 615-pair replay |
| Open product gates | WS9 optional user delivery approval (unchanged; not a remediation blocker) |
| Git parity (verified bundle in repo) | **Open** — remediation docs, `dashboard.py`, dashboard tests, inventory script, and regenerated `artifacts/evaluation/*` were verified locally but not committed at close-out; run `/commit` before treating origin as authoritative |
