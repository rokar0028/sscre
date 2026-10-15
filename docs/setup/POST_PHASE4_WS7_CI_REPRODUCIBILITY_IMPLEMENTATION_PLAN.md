# Post–Phase 4 Workstream 7 — CI, reproducibility, and artifact hygiene

## Goal

Make the repository's verified research paths explicit and independently
observable in CI. The default job must remain fast; benchmark, Compose,
PostgreSQL, provider, and artifact checks must report separate outcomes rather
than being hidden behind one green unit-test result.

**Status:** `planning-complete` — implementation not started.

**Parent:** [`../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)
Workstream 7.

**Evidence:** To be created at
`docs/setup/POST_PHASE4_WS7_CI_REPRODUCIBILITY_EVIDENCE.md` during Step 8.

**Canonical CI workflow:** [`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

## Goal / exit gates

### Gate A — CI contract

Add and locally validate separate CI jobs for:

- the fast default unit suite;
- production benchmark validation;
- P4 semantic gate/deferred-path tests;
- Compose configuration using the same non-secret sample environment as the
  existing workflow;
- opt-in PostgreSQL integration and WS8 marker coverage;
- an explicitly authorized provider path, if credentials and quota exist.

Gate A is complete only when each job has an explicit pass, skip, or
unavailable interpretation and the workflow does not expose secrets.

### Gate B — artifact and clean-checkout reproducibility

Add deterministic validation for current artifact references, hashes, lineage,
redaction, and historical classification. Replay the current claims from a
clean checkout or record the exact unavailable condition. Gate B must not
promote historical, deferred, synthetic, or dirty-worktree artifacts to current
headline evidence.

### Exit

Workstream 7 may be marked closed only when the evidence file records CI job
results, artifact-validation output, redaction results, clean-checkout status,
and all skipped or unavailable conditional paths. A green unit job alone is not
an exit.

## Learning objectives

- [ ] Distinguish a passing default test suite from separately verified
      benchmark, Compose, PostgreSQL, provider, and artifact paths.
- [ ] Preserve fail-closed behavior when a conditional dependency or credential
      is unavailable.
- [ ] Define “current,” “historical,” “deferred,” and “unavailable” without
      deleting historical evidence.
- [ ] Reproduce a claim from committed inputs rather than the dirty worktree.

## Prerequisites and audit corpus

### Feature minimum inputs

- [ ] Inspect [`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
      and preserve the existing `test` and `compose-config` intent.
- [ ] Confirm the declared development dependencies and marker exclusions in
      [`../../pyproject.toml`](../../pyproject.toml).
- [ ] Confirm the production benchmark command:
      `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2
      --production`.
- [ ] Confirm P4 validation paths:
      `tests/test_semantic_validity_gate.py`,
      `tests/test_semantic_validity_held_out.py`, and
      `python -m sscre.semantic_validity_gate`.
- [ ] Confirm the CI sample environment:
      `POSTGRES_PASSWORD=ci-local-password` and
      `SSCRE_ADMIN_TOKEN=ci-local-admin-token-123456`.

### Broader stabilization scope

- [ ] Audit all current benchmark and P4 inputs:
      `benchmarks/split_manifest.json`,
      `benchmarks/fresh_held_out.jsonl`,
      `benchmarks/fresh_held_out_manifest.json`,
      `benchmarks/semantic-validity-held-out-gate.json`,
      `experiments/semantic-validity-evaluation-config-v1.json`,
      `artifacts/evaluation/phase4-semantic-validity-held-out.json`, and
      `artifacts/evaluation/phase4-semantic-validity-gate.json`.
- [ ] Inventory all artifact paths cited as current in
      `docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`,
      `docs/setup/POST_PHASE4_WS5_FRESH_HELD_OUT_EVIDENCE.md`, and
      `docs/phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`.
- [ ] Include the broader stabilization evidence under `artifacts/`, while
      preserving historical Phase 2–4 artifacts and their classifications.
- [ ] Record the initial `git status --short`, current `HEAD`, Python version,
      and dependency installation state before implementation.

## Implementation steps

### Step 1 — Freeze the CI and claim contract

- [ ] Record the current workflow jobs, triggers, permissions, Python version,
      install commands, and environment values.
- [ ] Map each parent WS7 acceptance criterion to one workflow job, validator,
      artifact, or evidence row.
- [ ] Define the status vocabulary `pass`, `skip`, `unavailable`, `deferred`,
      and `fail`; do not turn an unrun conditional path into pass.
- [ ] Define which artifacts are current headline inputs and which are
      historical, deferred, synthetic, or diagnostic.
- [ ] Save the audit in the WS7 evidence file as a historical pre-edit
      snapshot before changing `.github/workflows/ci.yml`.

**Stopping rule:** If a required path does not exist, add an explicit baseline
gap to the evidence and do not write a passing verification claim for it.

### Step 2 — Preserve and separate the fast default job

- [ ] Keep the existing `ubuntu-latest` checkout, Python setup, `.[dev]`
      installation, and `python -m pytest -q` path.
- [ ] Ensure the default suite continues to deselect
      `ws8_postgres_*` markers as declared in `pyproject.toml`.
- [ ] Report the default suite's pass count and deselected conditional tests
      separately from every other job.
- [ ] Do not add local embedding weights, provider credentials, Docker, or
      PostgreSQL requirements to this fast job.

### Step 3 — Add benchmark and P4 validity jobs

- [ ] Add a `benchmark-validation` job that installs `.[dev]` and runs
      `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2
      --production`.
- [ ] Add a `p4-validity` job that runs both semantic validity test modules and
      the deferred/pass-safe gate CLI against the committed paths.
- [ ] Make the P4 job assert the expected authorized state from the committed
      gate record: after WS5, the fresh held-out gate is ready and the current
      headline artifact/gate are pass artifacts, while the old
      `held_out_test.jsonl` remains forbidden for this claim.
- [ ] Ensure the job fails on stale manifest references, forbidden held-out
      substitution, hash mismatch, malformed redacted output, or an
      unexpected gate status.
- [ ] Publish only non-secret summaries; do not upload raw queries, answers,
      vectors, tokens, or provider responses.

### Step 4 — Add Compose configuration validation

- [ ] Keep this as a separate `compose-config` job rather than coupling it to
      unit tests.
- [ ] Use the documented sample values from the current workflow:
      `POSTGRES_PASSWORD=ci-local-password` and
      `SSCRE_ADMIN_TOKEN=ci-local-admin-token-123456`.
- [ ] Run `docker compose config -q` and verify the resolved semantic strategy
      is **C**, matching [`../../docker-compose.yml`](../../docker-compose.yml)
      and [`../../.env.example`](../../.env.example).
- [ ] Avoid reading or uploading `.env`; CI must not require real credentials.
- [ ] If Docker is unavailable on a runner, report that job unavailable rather
      than silently folding it into unit-test success.

### Step 5 — Add the opt-in PostgreSQL job

- [ ] Add a separate PostgreSQL job using the repository-compatible
      `pgvector/pgvector:pg16` service or an equivalent explicitly documented
      service.
- [ ] Install `.[dev]`, set only ephemeral CI database credentials, wait for
      readiness, run `sscre-migrate --database-url ...`, and export
      `SSCRE_DATABASE_URL` for the tests.
- [ ] Run the existing PostgreSQL integration/vector tests:
      `tests/test_postgres_integration.py`,
      `tests/test_postgres_vector.py`, and
      `tests/test_postgres_cache_scope.py`.
- [ ] Run each existing WS8 marker family in an explicitly named step:
      `ws8_postgres_failure_recovery`, `ws8_postgres_multiprocess`,
      `ws8_postgres_contention`, and `ws8_postgres_load`.
- [ ] Record PostgreSQL version, pgvector availability, migration result,
      marker results, and any intentional skips in the evidence artifact.
- [ ] Keep this job opt-in or separately required according to runner cost and
      Docker availability; do not imply that its absence is a unit-test pass.

### Step 6 — Add the authorized provider path

- [ ] Add a separately named provider job only behind an explicit workflow
      authorization condition and repository/environment secrets.
- [ ] Require the existing provider configuration contract and live opt-in
      flag; do not substitute fake-provider or local-embedding numbers.
- [ ] Use the bounded provider test path only:
      `python -m pytest -q tests/test_r1_provider_run.py
      tests/test_provider_measure.py -m real_provider` or the repository's
      equivalent marker-filtered command after confirming its exact selection.
- [ ] Redact logs and artifacts; never echo credential values, authorization
      headers, prompts, answers, or raw provider responses.
- [ ] If credentials, quota, approval, or the live flag is absent, emit
      `unavailable` with reason and zero requests. Do not mark the job failed
      solely for an intentionally unrun provider measurement.

**Stopping rule:** No provider job may be enabled by default, and no live
measurement may run merely because CI has access to a secret.

### Step 7 — Implement artifact lineage and hygiene validation

- [ ] Reuse existing hash and redaction helpers where possible:
      `sscre.benchmark_splits.file_sha256`,
      `sscre.serialization.validate_redacted_report_payload`, and
      `sscre.semantic_validity_gate` hash checks.
- [ ] Add the smallest focused validator (script or module) for current
      stabilization artifacts. It must:
      - resolve every declared current path;
      - compare each recorded SHA-256 with the on-disk file;
      - verify benchmark, split, config, gate, model, dimension, attribution,
        and artifact identity fields where declared;
      - reject stale manifest references in current/headline artifacts;
      - classify historical artifacts without deleting them;
      - reject sensitive fragments and raw operational content; and
      - produce a deterministic machine-readable summary.
- [ ] Add focused tests for missing paths, hash mismatch, stale manifest,
      historical classification, redaction failure, and a valid current
      package.
- [ ] Keep generated caches (`__pycache__`, `.pytest_cache`, build output),
      local `.env`, and accidental files out of the deliverable and CI
      artifacts.
- [ ] Make CI fail on a current-artifact violation, while allowing an explicit
      `historical` or `deferred` record when the artifact contract says so.

**Design constraint:** Do not silently rewrite existing artifacts during CI.
Validation is read-only; regeneration requires a separately recorded command,
provenance, and user-authorized scope.

### Step 8 — Clean-checkout replay and evidence close

- [ ] Run the fast, benchmark, P4, Compose, artifact, and available
      PostgreSQL/provider checks from a clean checkout at the recorded commit.
- [ ] Confirm all verification commands and referenced paths still exist
      immediately before recording results.
- [ ] Write
      `docs/setup/POST_PHASE4_WS7_CI_REPRODUCIBILITY_EVIDENCE.md` with:
      job-by-job status, command, commit, worktree state, environment class,
      artifact validator output, redaction result, and skip/unavailable
      reasons.
- [ ] Link the evidence file from this plan and the parent stabilization plan.
- [ ] Update the parent WS7 checklist only for work actually evidenced.
- [ ] Recheck the parent plan's overall exit verdict; do not call the project
      stable while current claims depend on uncommitted or untracked files.

## Verification commands

These commands are the planned local equivalents. Confirm each path and marker
again at execution time before recording a result.

```powershell
python -m pip install ".[dev]"
python -m pytest -q
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
python -m pytest -q tests/test_semantic_validity_gate.py tests/test_semantic_validity_held_out.py
python -m sscre.semantic_validity_gate
$env:POSTGRES_PASSWORD = 'ci-local-password'
$env:SSCRE_ADMIN_TOKEN = 'ci-local-admin-token-123456'
docker compose config -q
```

PostgreSQL commands are conditional and require a migrated local service:

```powershell
$env:SSCRE_DATABASE_URL = '<documented local CI-equivalent URL>'
python -m pytest -q tests/test_postgres_integration.py tests/test_postgres_vector.py tests/test_postgres_cache_scope.py
python -m pytest -q -m ws8_postgres_failure_recovery
python -m pytest -q -m ws8_postgres_multiprocess
python -m pytest -q -m ws8_postgres_contention
python -m pytest -q -m ws8_postgres_load
```

## Acceptance criteria

- [ ] Unit, benchmark, P4, Compose, PostgreSQL, and provider coverage are
      reported separately.
- [ ] Default CI remains fast and does not require Docker, PostgreSQL, model
      weights, or live credentials.
- [ ] Conditional skips and unavailable infrastructure are visible with reasons.
- [ ] Current artifacts resolve to existing files with matching hashes and
      valid lineage.
- [ ] Sensitive values and raw operational content are rejected from CI
      summaries and evidence artifacts.
- [ ] Historical artifacts remain available but cannot enter current headline
      summaries.
- [ ] A clean checkout reproduces every claim marked verified.
- [ ] No completion checkbox is marked from an unrun conditional feature.

## Out of scope

- [ ] Re-running the semantic evaluation or changing its pre-registered gate.
- [ ] New benchmark construction or relabeling.
- [ ] Enabling live provider measurement without explicit authorization.
- [ ] Making PostgreSQL, provider, multi-worker, or deployment claims universal.
- [ ] Deleting historical artifacts solely to make validation pass.
- [ ] CI redesign unrelated to the WS7 acceptance criteria.
