# SSCRE Stabilization and Evidence Completion Plan

## Goal

Establish whether SSCRE's compatibility-aware semantic reuse is useful under a
fresh, reproducible evaluation protocol, while keeping deployment hardening
honest and explicitly deferred where it is not required for the research
result. This plan closes the minimum runtime and evidence gaps first; it does
not add new product features or provider-specific integrations.

## Status

**Status:** `in progress — research-first reprioritization; Workstreams 0–1 closed, Workstream 2 in-memory verification passed, Gate B deferred`

**Evidence:** [`docs/POST_PHASE4_STABILIZATION_EVIDENCE.md`](POST_PHASE4_STABILIZATION_EVIDENCE.md) (Workstream 0 closed)

**Parent:** [`docs/SSCRE_PLAN.md`](SSCRE_PLAN.md), §§20, 23, and 24.

**Scope:** Stabilization after Phase 4 semantic-validity deferral.

**Research exit:** The repository has a reproducible local environment, a
diagnosed Strategy C decision profile, an authorized bounded provider run when
available, and either a valid fresh held-out semantic result or an explicit
documented deferral.

**Deployment exit (separate):** External multi-user readiness remains
deferred until Workstreams 2 and 4 pass their applicable gates. Deployment
hardening must not block the research exit unless it affects the validity or
failure safety of the evaluation path.

## Current baseline

- The current working tree is on local branch `main`, tracking
  `origin/phase4/p4-semvalid-close`; stabilization changes are not yet
  committed at this plan revision.
- The earlier Gate A package recorded **835** pytest tests (with optional
  `local-embeddings` installed), Compose config, import smoke, and env
  validation. The latest full-suite run records **857 passed, 20 skipped, and
  21 deselected**; these counts must not be conflated with the older Gate A
  artifact.
- PostgreSQL integration markers and live-provider tests remain opt-in
  (Gate B / Gate C); WS1 recorded DB readiness only where Docker was available.
- `docker-compose.yml` and `.env.example` default to Strategy **C**.
- Workstream 2 now supplies client authentication and tenant/namespace
  boundaries in the in-memory path; PostgreSQL Gate B and multi-worker abuse
  enforcement remain deferred.
- Timed-out dependency calls can retain executor capacity after the request
  returns.
- The Phase 4 fresh held-out semantic gate is deferred because the existing
  215-record held-out split has already been used.
- Human answer-correctness labels are not present.
- Phase 3/4 artifacts include historical, dirty-worktree, synthetic, and
  unavailable evidence that must remain clearly classified.

## Safety and decision gates

### Gate A — local environment only

Local development and unit tests may use fake providers and in-memory storage.
No credentials or external services are required for this gate.

### Gate B — PostgreSQL-backed verification

Requires Docker Compose, a migrated PostgreSQL/pgvector instance, and a local
`.env` containing non-secret development values. PostgreSQL results must include
the database version, migration state, workload, and skipped-test explanation.

### Gate C — real-provider verification

Requires explicit provider approval, credentials supplied out of band, bounded
quotas, a pricing schedule, and a redacted artifact. A free-tier provider is
not assumed to be unlimited or suitable for production.

### Gate D — semantic headline evaluation

Requires a genuinely fresh, licensed, reviewed held-out population and a frozen
manifest. The existing `benchmarks/held_out_test.jsonl` must not be relabeled
or reused as fresh.

### Universal stopping rule

If a required dependency, credential, dataset, license, or environment is not
available, record `unavailable` or `deferred` with the reason. Do not replace
the missing evidence with fake-provider, synthetic, or historical numbers.

## Workstream 0 — Baseline freeze and claim inventory

**Purpose:** Establish a clean starting point before changing code or
regenerating evidence.

### Detailed implementation procedure

Workstream 0 is a read-only baseline exercise. Do not change application code,
benchmarks, configuration defaults, or existing result artifacts while
performing these steps.

#### Step 0.1 — Confirm the repository and capture execution context

- [x] Confirm the command is running from the repository root and record the
      absolute repository path.
- [x] Record the current commit, branch, and worktree state:

      ```powershell
      git rev-parse --show-toplevel
      git rev-parse HEAD
      git branch --show-current
      git status --short
      ```

- [x] Record the runtime and dependency context:

      ```powershell
      python --version
      python -m pip --version
      python -m pip list --format=json
      ```

      Evidence: [`artifacts/stabilization/baseline-manifest.json`](../artifacts/stabilization/baseline-manifest.json)
      (`pip_packages`, captured 2026-10-13T07:52:42Z).

- [x] Record Docker and Compose versions when available:

      ```powershell
      docker --version
      docker compose version
      ```

- [x] Record each unavailable command as `unavailable` with its command and
      reason; do not replace missing version evidence with an estimate.

      None unavailable on the capture host; see evidence Step 0.1 table.

The resulting snapshot must include a timestamp, operating system, Python
version, package list, Docker/Compose result, commit, branch, and short
worktree status. Secrets and the contents of `.env` must not be copied into
the snapshot.

#### Step 0.2 — Classify the starting worktree

- [x] Identify every modified, deleted, and untracked path from
      `git status --short`.

      At Step 0.2 close: no modified or deleted tracked paths; untracked
      `docs/POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`,
      `docs/POST_PHASE4_STABILIZATION_EVIDENCE.md`, and
      `artifacts/stabilization/baseline-manifest.json`.

- [x] For each path, classify it as one of:
      `pre-existing user work`, `intended stabilization work`,
      `generated evidence`, `local environment`, or `unclassified`.

      See evidence Step 0.2 table and manifest `worktree_boundary.path_classifications`.

- [x] Do not stage, discard, reset, or amend any pre-existing user work.
- [x] Record the boundary between committed `HEAD` and the current dirty
      worktree in the baseline manifest.

      Manifest `worktree_boundary` at `cbe5e0d1…` on `main`.

- [x] If a path cannot be classified, stop before implementation and ask for
      clarification or record the stabilization package as blocked.

      `stabilization_package_blocked`: false.

The baseline must make it possible to answer: “Was this claim present at
committed `HEAD`, or did it only appear in the dirty worktree?”

#### Step 0.3 — Build the claim inventory

- [x] Search and review claims in:
      `docs/SSCRE_PLAN.md`, `docs/phase-2/`, `docs/phase-3/`, and
      `docs/phase-4/`.
- [x] Include claims about runtime behavior, safety, authentication,
      tenancy, PostgreSQL, providers, benchmarks, semantic reuse,
      correctness, performance, cost, deployment readiness, and release
      status.
- [x] Record one inventory row per distinct claim, using a stable claim ID.

      [`artifacts/stabilization/claim-inventory.json`](../artifacts/stabilization/claim-inventory.json)
      — 35 claims (`CLM-001`–`CLM-035`).

- [x] Capture the document path and section, exact claim text or a concise
      faithful paraphrase, referenced code/artifact paths, and the evidence
      date or commit when available.
- [x] Identify claims that are duplicated, stale, overstated, unsupported,
      or contradicted by another project document.

      `cross_claim_issues` `XCL-001`–`XCL-005` in the same manifest; summary in
      evidence Step 0.3.

Use only the following status vocabulary:

| Status | Meaning |
| --- | --- |
| `implemented` | The code or document behavior exists, but the required verification is not claimed. |
| `locally verified` | Verified with local code/tests and no external service requirement. |
| `PostgreSQL verified` | Verified against the declared PostgreSQL/pgvector setup. |
| `provider verified` | Verified against an explicitly authorized real provider run. |
| `evaluation verified` | Verified by the applicable frozen evaluation protocol and artifact. |
| `deferred` | Intentionally not run or not authorized yet. |
| `unavailable` | Required data, tool, credential, service, or environment was unavailable. |
| `out of scope` | Explicitly excluded by this stabilization plan. |

Do not use `pass`, `complete`, or `production-ready` as a Workstream 0
classification unless the claim also has the corresponding evidence status.

#### Step 0.4 — Reconcile evidence lineage

- [x] For every claim marked verified, identify the exact test command,
      artifact, manifest, or document that supports it.

      Per-claim `evidence_lineage` in
      [`artifacts/stabilization/claim-inventory.json`](../artifacts/stabilization/claim-inventory.json)
      (schema `1.1`).

- [x] Record whether the evidence came from committed `HEAD`, the dirty
      worktree, a historical run, synthetic/fake providers, or an unavailable
      conditional path.
- [x] Check that referenced artifacts and benchmark paths exist.

      [`artifacts/stabilization/evidence-lineage-audit.json`](../artifacts/stabilization/evidence-lineage-audit.json)
      — 0 missing paths (2026-10-13).

- [x] Mark stale, historical, synthetic, contaminated, or dirty-worktree
      evidence explicitly; do not delete it during this workstream.
- [x] Mark claims with no supporting evidence as `deferred` or `unavailable`,
      choosing `unavailable` only when a required dependency is missing.
- [x] Record contradictions for resolution in Workstream 8 instead of
      silently changing the original claim during the inventory.

      `cross_claim_issues` unchanged; helper
      [`scripts/stabilization_reconcile_lineage.py`](../scripts/stabilization_reconcile_lineage.py).

#### Step 0.5 — Freeze the stabilization acceptance baseline

- [x] Define the exact baseline facts that later workstreams may change:
      current commit/worktree boundary, default semantic strategy, current
      test result, known unavailable paths, held-out gate status, and release
      limitations.

      Manifest `acceptance_baseline` (frozen 2026-10-13).

- [x] Record the test command and result used as the pre-change local
      baseline. If it is not run, leave the verification item unchecked and
      record why.

      `pre_change_verification`: pytest `807 passed, 15 skipped`;
      `benchmark_validate` pass; `docker compose config -q` pass.
      Opt-in PostgreSQL and live provider not re-run (documented in `not_run`).

- [x] Create the machine-readable baseline manifest with stable paths,
      hashes where applicable, command results, and claim statuses.

      [`artifacts/stabilization/baseline-manifest.json`](../artifacts/stabilization/baseline-manifest.json)
      schema `stabilization-baseline-manifest-1.0`.

- [x] Create the human-readable stabilization evidence document containing:
      the snapshot, worktree boundary, claim-status summary, open conflicts,
      unavailable/deferred gates, and the approved next workstream.
- [x] Have the baseline answer these questions before Workstream 1 begins:
      “What was already changed?”, “What is actually verified?”, “What is
      still only a plan?”, and “What may the next workstream modify?”

      See evidence Step 0.5 gate answers.

### Workstream 0 outputs

- [x] A machine-readable baseline manifest, stored under the stabilization
      artifact directory, with no secrets.
- [x] A human-readable stabilization evidence document with a claim-status
      summary and evidence lineage.
- [x] A list of paths classified as pre-existing, stabilization-owned,
      generated, local-only, or blocked.

      Manifest `worktree_boundary.path_classifications` and Step 0.2 evidence.

- [x] An explicit list of claims that remain `deferred`, `unavailable`, or
      `out of scope`.

      Manifest `acceptance_baseline.claims_*` and evidence Step 0.5 table.

### Workstream 0 acceptance gate

Workstream 0 may be closed only when:

- [x] The commit and dirty-worktree boundary is recorded.
- [x] Every claim in the declared Phase 2–4 documentation scope has a status.

      35 distinct claims in `claim-inventory.json`.

- [x] Every verified claim points to current evidence or is downgraded.
- [x] Historical, synthetic, contaminated, and unavailable evidence is clearly
      separated from current verification.
- [x] No secret, `.env` content, provider credential, or unapproved dataset is
      present in the baseline outputs.
- [x] The next authorized workstream and its prerequisites are written down.

      **Workstream 1** authorized (Gate A).

**Evidence:** A machine-readable baseline manifest and a short claim-status
section in the stabilization evidence document.

**Stopping rule:** Stop if the working-tree changes cannot be separated from
the intended stabilization package.

## Workstream 1 — Reproducible local environment and `.env` setup

**Purpose:** Make local setup explicit without committing secrets.

**Status:** `closed (Gate A verification — Step 1.7)`

**Evidence:** [`docs/setup/POST_PHASE4_WS1_EVIDENCE.md`](setup/POST_PHASE4_WS1_EVIDENCE.md)

**Parent baseline:** Workstream 0 acceptance baseline in
[`artifacts/stabilization/baseline-manifest.json`](../artifacts/stabilization/baseline-manifest.json).

**Current baseline facts:** `.env.example` contains the current configuration
surface; `src/sscre/config.py` supplies additional defaults and production
fail-closed checks; `docker-compose.yml` requires a password and admin token
but passes only a subset of runtime settings to the API; Compose and
`.env.example` default to Strategy C (B is explicit opt-in). The current Compose
validation command passes with the CI sample
environment. These facts are audit inputs, not completion evidence.

### Goal / exit gate

**Goal:** A new developer can configure and validate Gate A locally without
credentials, while development Compose and production/provider boundaries are
unambiguous and secrets remain local.

**Exit:** Setup instructions, `.env.example`, validation tooling/tests, and
Compose behavior agree with the declared environment contract; the default
unit suite and Compose validation pass; production configuration still fails
closed when required database, admin-token, or token-expiry settings are
absent.

### Detailed implementation procedure

#### Step 1.1 — Inventory and reconcile the environment contract

- [x] Build a source-of-truth matrix from
      [`docker-compose.yml`](../docker-compose.yml),
      [`src/sscre/config.py`](../src/sscre/config.py), `.env.example`,
      [`pyproject.toml`](../pyproject.toml), and existing setup docs.
- [x] Classify every variable as `required`, `optional with default`,
      `development-only`, `PostgreSQL-only`, `production-only`, or
      `provider-specific`.
- [x] Identify variables read by `Settings.from_environment()` but absent from
      Compose forwarding, including cache limits and timeout settings; decide
      whether each omission is intentional or a configuration defect.

      Cache/timeout/semantic keys are forwarded; admin read token and expiry
      keys are not (MIS-002).

- [x] Identify variables used by Compose but not represented in the documented
      local setup path, including ports, migration settings, and admin
      credentials.

      `SSCRE_MIGRATIONS_DIR` in compose only (MIS-003); ports in `.env.example`.

- [x] Confirm `.env.example` contains placeholders only, no real credential,
      user-specific absolute path, or provider key.
- [x] Confirm `.env` is ignored and is not tracked:
      `git check-ignore .env` and `git ls-files --error-unmatch .env` must
      produce the expected ignored/not-tracked result.
- [x] Record unresolved contract mismatches in the WS1 evidence file before
      editing defaults; do not silently normalize them.

      MIS-001–MIS-006 in
      [`docs/setup/POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md`](setup/POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md).

**Deliverable:** A checked-in environment contract section in the setup
documentation, with each variable mapped to its owner and lifecycle.

      [`docs/setup/POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md`](setup/POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md)
      and
      [`artifacts/stabilization/ws1-environment-contract.json`](../artifacts/stabilization/ws1-environment-contract.json).

#### Step 1.2 — Define the four supported operating modes

- [x] Document **unit-test mode**:
      in-memory repository, fake providers, no `.env`, no PostgreSQL,
      no external credentials, and the default test command.
- [x] Document **development Compose mode**:
      `.env.example` copied to `.env`, local PostgreSQL/pgvector, migration
      service, API service, non-secret local values, and explicit Strategy C
      safety expectation.

      Strategy C default documented; MIS-001 resolved in Step 1.5.

- [x] Document **PostgreSQL verification mode**:
      migrated `pgvector/pg16`, database URL, migration checksum validation,
      health/readiness checks, opt-in `ws8_postgres_*` markers, and the
      requirement to record version, migration state, workload, and skips.
- [x] Document **production/provider mode**:
      explicit production runtime profile, PostgreSQL URL, admin token,
      token expiry, authorized provider boundary, bounded quotas/pricing, and
      no assumption that free-tier providers are unlimited.
- [x] State which mode each command targets and prohibit treating fake,
      synthetic, or unavailable runs as provider or production evidence.
- [x] Link the existing
      [`docs/setup/POSTGRESQL_LOCAL_SETUP.md`](../docs/setup/POSTGRESQL_LOCAL_SETUP.md)
      from the new setup entry point rather than duplicating its database
      lifecycle instructions.

**Deliverable:** A concise setup decision tree and mode-specific command
sequences under `docs/setup/`; update [`docs/README.md`](README.md) only if a
new notable setup document is added.

      [`docs/setup/LOCAL_ENVIRONMENT_MODES.md`](setup/LOCAL_ENVIRONMENT_MODES.md);
      [`docs/README.md`](README.md) setup table updated.

#### Step 1.3 — Add reproducible dependency and import setup

- [x] Document the supported Python range from `pyproject.toml` and the
      Windows PowerShell virtual-environment sequence.
- [x] Document installation of declared development dependencies:
      `python -m pip install ".[dev]"`.
- [x] Document optional local embedding installation separately:
      `python -m pip install ".[local-embeddings]"`; do not make it a
      prerequisite for unit-test mode.
- [x] Add an import smoke command that exercises the installed package and
      the CLI entry points without contacting PostgreSQL or a provider.

      [`scripts/gate_a_import_smoke.py`](../scripts/gate_a_import_smoke.py)

- [x] Ensure the setup commands use the current checkout and do not depend on
      ignored build outputs, `src/sscre.egg-info/`, or a pre-existing global
      virtual environment.
- [x] Record package installation and import results in WS1 evidence, including
      unavailable optional embedding tooling when it is not installed.

**Deliverable:** Reproducible Gate A setup sequence and import-smoke evidence.

      [`docs/setup/GATE_A_LOCAL_SETUP.md`](setup/GATE_A_LOCAL_SETUP.md);
      log [`artifacts/stabilization/gate-a-import-smoke.log`](../artifacts/stabilization/gate-a-import-smoke.log).

#### Step 1.4 — Add non-secret environment validation

- [x] Reuse `Settings.from_environment()` and existing validation instead of
      duplicating parsing rules in a second configuration model.
- [x] Add the smallest project CLI/script that validates a supplied environment
      without printing secret values or `.env` contents.

      [`src/sscre/env_validate.py`](../src/sscre/env_validate.py);
      `sscre-env-validate` in [`pyproject.toml`](../pyproject.toml).

- [x] Validate required-variable presence by mode:
      production database URL, admin token, and timezone-aware admin-token
      expiry; development Compose password and admin token; unit-test mode
      external services optional.
- [x] Validate booleans, enum values, numeric ranges, cache limits, byte
      limits, timestamp formats, and timeout positivity.

      Via `Settings.from_environment()` and `Settings` post-init checks.

- [x] Validate timeout relationships explicitly:
      request timeout must provide enough budget for the declared dependency
      timeouts, or document and test the accepted relationship before choosing
      the rule.

      Rule: each dependency timeout `<= request_timeout_seconds`
      ([`tests/test_env_validate.py`](../tests/test_env_validate.py)).

- [x] Validate semantic strategy values (`B` or `C`) and report the Compose
      default mismatch until it is resolved.

      Embedding-only warning when strategy is explicitly B (post–Step 1.5).

- [x] Return non-zero for invalid configuration and a zero exit code for the
      documented non-secret sample environment.
- [x] Add unit tests for valid samples, missing production requirements,
      invalid values, malformed timestamps, timeout relationships, and
      redaction of secret-like values.

**Deliverable:** Environment-validation command, focused tests, and a redacted
validation log.

      [`artifacts/stabilization/env-validate-development-compose.log`](../artifacts/stabilization/env-validate-development-compose.log);
      [`docs/setup/GATE_A_LOCAL_SETUP.md`](setup/GATE_A_LOCAL_SETUP.md) § Environment validation.

#### Step 1.5 — Reconcile Compose defaults and provider boundary

- [x] Decide the documented development Compose default using the stabilization
      safety rule: Strategy C unless a written safety exception retains B.

      **Decision:** default **C** (no safety exception for B).

- [x] If changing the default to C, update `docker-compose.yml`, `.env.example`,
      setup docs, and tests/evidence in the same pass.

      `SSCRE_SEMANTIC_STRATEGY:-C` in Compose; `.env.example` `=C`; `SSCRE_PLAN.md`
      §20/§24; [`tests/test_env_validate.py`](../tests/test_env_validate.py).

- [x] If retaining B, record the exception, intended trusted-local boundary,
      explicit override command for C, and why B is safe for that boundary.

      Not applicable — B remains explicit opt-in only (`SSCRE_SEMANTIC_STRATEGY=B`).

- [x] Ensure Compose sample values pass `docker compose config` without
      reading or exposing `.env` contents in logs.

      CI sample env; exit `0` (2026-10-13).

- [x] Document that Gemini, OpenRouter, Ollama, or another provider must
      implement the existing OpenAI-compatible generation and embedding
      boundary, or require a separately reviewed adapter; no provider SDK is
      added in WS1.

      [`docs/setup/PROVIDER_BOUNDARY.md`](setup/PROVIDER_BOUNDARY.md).

- [x] Keep live-provider execution outside Gate A and mark it unavailable
      unless explicit credentials, quota, pricing, and authorization exist.

**Deliverable:** Reconciled Compose configuration and documented provider
boundary; no live provider run.

#### Step 1.6 — Record local embedding provenance

- [x] Document the currently validated local embedding identity:
      `all-MiniLM-L6-v2`, 384 dimensions, model package/version, device, and
      weight provenance.

      [`docs/setup/LOCAL_EMBEDDING_PROVENANCE.md`](setup/LOCAL_EMBEDDING_PROVENANCE.md).

- [x] Record whether model weights are already present, downloaded during the
      run, or unavailable; do not claim replayability when weights are absent.

      [`build_ws1_local_embedding_provenance_record`](../src/sscre/local_embedding.py);
      [`scripts/ws1_local_embedding_provenance.py`](../scripts/ws1_local_embedding_provenance.py).

- [x] Keep fake embeddings explicitly limited to tests and historical/synthetic
      artifacts.

      Documented in provenance note (`FakeEmbeddingClient`, Phase 3 JSON).

- [x] Add a redacted provenance record or validation output that contains no
      token, prompt, answer, or credential.

      [`artifacts/stabilization/local-embedding-provenance.json`](../artifacts/stabilization/local-embedding-provenance.json).

- [x] Do not pin or download a new model in WS1 without a measured need and
      licensing/provenance record.

      Registered id unchanged; default script is probe/cache-only.

**Deliverable:** Local embedding provenance note and, if available, a
machine-readable redacted record.

      [`docs/setup/LOCAL_EMBEDDING_PROVENANCE.md`](setup/LOCAL_EMBEDDING_PROVENANCE.md);
      [`artifacts/stabilization/local-embedding-provenance.json`](../artifacts/stabilization/local-embedding-provenance.json).

#### Step 1.7 — Verify the Gate A package

- [x] Confirm every verification path and marker exists before running it.

      Paths confirmed in
      [`gate-a-package-verification.json`](../artifacts/stabilization/gate-a-package-verification.json).

- [x] Run `python -m pip install ".[dev]"` in the declared environment.

      Log: [`gate-a-pip-install.log`](../artifacts/stabilization/gate-a-pip-install.log).

- [x] Run the environment import smoke command.

      [`gate-a-import-smoke.log`](../artifacts/stabilization/gate-a-import-smoke.log).

- [x] Run the non-secret validator against the documented sample.

      [`env-validate-unit-test.log`](../artifacts/stabilization/env-validate-unit-test.log),
      [`env-validate-development-compose.log`](../artifacts/stabilization/env-validate-development-compose.log).

- [x] Run `python -m pytest -q` for the historical Gate A snapshot.

      **Historical result:** 835 passed, 1 skipped, 21 deselected —
      [`gate-a-pytest.log`](../artifacts/stabilization/gate-a-pytest.log).

- [x] Run `docker compose config -q` with the same non-secret sample values
      documented by CI.

      [`docker-compose-config.log`](../artifacts/stabilization/docker-compose-config.log).

- [x] If PostgreSQL is available, run only the declared WS1 setup/readiness
      checks; record version, migration state, and skipped integration tests.

      Readiness only (12/12 migrations, pgvector 0.8.7); integration markers
      **deferred** to Gate B —
      `postgres-readiness-*.log` under `artifacts/stabilization/`.

- [x] Do not run a real provider under WS1 without Gate C approval; record
      `unavailable` or `deferred` with the reason.

      Live provider: **deferred** (Gate C) in package verification JSON.

- [x] Write `docs/phase-4/` only when evidence belongs to an existing Phase 4
      record; otherwise store the WS1 evidence under `docs/setup/` or
      `docs/internal/` according to the documentation layout rule.

      WS1 evidence remains under `docs/setup/`.

- [x] Update this plan’s Status, Acceptance criteria, Current baseline, and
      linked evidence in the same pass.

**Deliverable:** WS1 evidence package with command results, skips, redaction
check, dependency versions, and Compose output.

      [`gate-a-package-verification.json`](../artifacts/stabilization/gate-a-package-verification.json);
      [`POST_PHASE4_WS1_EVIDENCE.md`](setup/POST_PHASE4_WS1_EVIDENCE.md) Step 1.7.

### WS1 stopping rules

- Stop before provider execution when credentials, quota, pricing, licensing,
  or endpoint compatibility are not explicitly approved.
- Stop before changing the Compose strategy default if the trusted-local
  versus externally reachable deployment boundary is not documented.
- Stop if validation would need to print `.env`, credentials, provider
  payloads, or model inputs.
- Stop if a required declared dependency cannot be installed; record the
  exact command and unavailable reason rather than substituting a global or
  unpinned package.
- Stop and leave the relevant boxes unchecked when PostgreSQL is unavailable;
  Gate A may still close for local tests, but PostgreSQL verification must
  remain `unavailable` or `deferred`.

### WS1 implementation gate

**Goal / Exit gate:** WS1 authoring is complete when the environment contract,
mode documentation, dependency setup, validator, Compose decision, provider
boundary, and embedding provenance record exist. This does not authorize
provider execution or claim PostgreSQL verification.

**Verification gate:** WS1 implementation is complete only when the declared
Gate A commands pass and all unavailable conditional checks are recorded with
reasons. A conditional check that was not run is not pass or fail.

**Acceptance criteria:**

- [x] A new developer can run local tests without external credentials using
      the documented PowerShell sequence.
- [x] The four operating modes and their evidence boundaries are documented.
- [x] The environment validator rejects malformed, incomplete, unsafe, or
      inconsistent values without exposing secrets.
- [x] `docker compose config -q` passes using only documented non-secret sample
      values.
- [x] `.env` is ignored, untracked, and absent from generated evidence.
- [x] Compose’s semantic strategy default is either C or has a documented,
      safety-reviewed trusted-local exception.
- [x] Production mode fails closed when required database, admin-token,
      expiry, or provider boundary settings are absent.
- [x] Local embedding identity, dimension, device, and weight provenance are
      recorded sufficiently for replay, or explicitly marked unavailable.
- [x] No provider execution, production readiness, or PostgreSQL capacity
      claim is made from Gate A evidence.

**Evidence:** Setup instructions, environment-validation output, dependency
version record, local embedding provenance, redaction audit, and Compose
configuration output.

**Stopping rule:** Stop before provider execution if credentials, quota,
licensing, or endpoint compatibility is not explicitly approved.

## Workstream 2 — Public API safety, authentication, and tenancy boundary

**Purpose:** Prevent unauthorized cache reads, cache poisoning, provider abuse,
cross-tenant disclosure, and uncontrolled provider spend before external
exposure. This workstream defines the boundary and enforcement required for
external deployment; it does not add a dashboard, account-management product,
or provider-specific identity system.

**Status:** `closed (in-memory verification)` — PostgreSQL Gate B **deferred**; external deployment **not authorized** until Gate B is recorded

**Evidence:** [`docs/setup/POST_PHASE4_WS2_EVIDENCE.md`](setup/POST_PHASE4_WS2_EVIDENCE.md)

**Parent:** This plan’s Workstream 2 and the external-deployment verdict in
[`docs/SSCRE_PLAN.md`](SSCRE_PLAN.md), §§20, 23, and 24.

**Code baseline:** The API and current authorization helper are in
[`src/sscre/app.py`](../src/sscre/app.py); request validation and the current
query hash are in [`src/sscre/query.py`](../src/sscre/query.py); repository
interfaces are in [`src/sscre/cache.py`](../src/sscre/cache.py), with the
PostgreSQL implementation in
[`src/sscre/postgres_cache.py`](../src/sscre/postgres_cache.py). Existing
schema evolution is under [`migrations/`](../migrations/).

### Boundary decision

The supported contract has two deliberately different modes:

1. **Trusted-local mode:** the service is single-tenant, binds only to a
   loopback or explicitly private interface, and may use the current
   development setup. This mode is not evidence for external deployment.
2. **External mode:** the service is a multi-tenant API. Every query request
   carries authenticated client credentials that resolve to exactly one
   tenant and an optional namespace. The caller cannot choose or override that
   identity in the JSON body. Admin credentials remain separate from client
   credentials.

The first implementation may use a deployment-configured client-auth
adapter/token registry; it must not silently treat an arbitrary
`X-Tenant-ID` header, query parameter, or body field as authentication.
Account provisioning, token issuance, rotation UI, and federated identity are
out of scope. If an approved client-auth adapter cannot be supplied, external
mode remains unavailable and the service must fail closed at startup or ingress.

### Detailed implementation procedure

#### Step 2.1 — Freeze the threat model and deployment contract

- [x] Inventory every HTTP route and every repository operation reachable from
      the API, starting with `/health`, `/ready`, `/v1/query`, and
      `/v1/cache/stats` in `src/sscre/app.py`.
- [x] Record the protected assets: cached answers, query metadata, embeddings,
      canonical answers, provider capacity and spend, storage limits, request
      metrics, and readiness information.
- [x] Record the threats: unauthenticated cache reads, cache poisoning,
      cross-tenant exact hits, cross-tenant vector selection, canonical-answer
      disclosure, quota exhaustion, oversized payloads, token leakage, and
      high-cardinality metric abuse.
- [x] Document the trusted-local ingress requirements: loopback/private
      binding, no direct Internet exposure, and an operator-controlled network
      boundary.
- [x] Document the external-mode requirements: authenticated client identity,
      tenant/namespace derivation, TLS or an equivalent trusted proxy boundary,
      bounded quotas, and separate admin ingress.
- [x] Mark external mode `deferred` if the deployment cannot provide an
      approved client-auth adapter, tenant registry, or trusted ingress.

**Deliverable:** A checked-in threat-model and API/auth contract document under
`docs/setup/` or `docs/internal/` (choose the location according to whether it
describes supported deployment or internal release control). It must state
which mode each route supports and what evidence is required before exposure.

      [`docs/setup/POST_PHASE4_WS2_API_AUTH_BOUNDARY.md`](setup/POST_PHASE4_WS2_API_AUTH_BOUNDARY.md);
      [`artifacts/stabilization/ws2-api-auth-boundary.json`](../artifacts/stabilization/ws2-api-auth-boundary.json);
      [`docs/setup/POST_PHASE4_WS2_EVIDENCE.md`](setup/POST_PHASE4_WS2_EVIDENCE.md).

#### Step 2.2 — Define the authenticated request context

- [x] Introduce one internal request-context value containing the authenticated
      principal, tenant ID, namespace, granted scopes, and a stable request ID.
      Do not pass raw bearer tokens into repository methods or logs.
- [x] Define the client credential contract, including token scheme,
      constant-time verification, expiry/rotation behavior, tenant binding,
      scope vocabulary, and failure responses.
- [x] Keep admin authentication separate from client authentication. Existing
      `admin_token` and `admin_read_token` must not authorize arbitrary tenant
      queries.
- [x] Require authenticated client context for `POST /v1/query` in external
      mode before preprocessing, cache lookup, embedding, generation, or any
      provider call.
- [x] Make missing, malformed, expired, unknown, and insufficient credentials
      return a stable 401/403 response with no tenant existence oracle and no
      provider invocation.
- [x] Ensure request IDs are returned through `X-Request-ID` on protected
      errors and are safe to include in logs.
- [x] Add configuration validation for external mode so an absent or invalid
      auth adapter cannot fall back to anonymous access.

      [`src/sscre/api_auth.py`](../src/sscre/api_auth.py);
      [`tests/test_api_client_auth.py`](../tests/test_api_client_auth.py);
      boundary doc § Client credential contract (Step 2.2).

**Implementation touchpoints:** `src/sscre/app.py`, `src/sscre/config.py`,
`src/sscre/env_validate.py`, and the existing admin tests in
`tests/test_admin.py`. Reuse the project’s standard library and installed
FastAPI/Pydantic facilities; do not add an identity-provider dependency.

#### Step 2.3 — Make tenant and namespace identity part of cache identity

- [x] Define the canonical identity tuple:
      `(tenant_id, namespace_id, normalized_query)` for exact lookup and
      insertion. Treat the namespace as a tenant-owned value; use a documented
      default only where the authenticated contract permits it.
- [x] Version the derived cache-key format rather than silently changing the
      current global SHA-256 interpretation. Preserve the query hash as a
      diagnostic field, but ensure repository identity cannot collide across
      tenants or namespaces.
- [x] Decide whether the public response may expose query hashes or selected
      candidate hashes. If retained for diagnostics, make them opaque to
      another tenant and document that they are not authorization credentials.
- [x] Carry tenant and namespace identity through exact lookup, semantic search,
      candidate evaluation, insertion, replacement, expiration cleanup, and
      hit accounting.
- [x] Reject caller-supplied tenant or namespace values that disagree with the
      authenticated request context. Do not infer tenant identity from query
      text or an untrusted header.
- [x] Add unit tests for normalization, key versioning, same-query separation,
      and stable behavior for the permitted default namespace.

      [`src/sscre/query.py`](../src/sscre/query.py) (`CACHE_KEY_VERSION`, `CacheScope`,
      `storage_query_hash`); migration
      [`migrations/012_cache_tenant_namespace.sql`](../migrations/012_cache_tenant_namespace.sql);
      [`tests/test_cache_scope.py`](../tests/test_cache_scope.py).

**Implementation touchpoints:** `src/sscre/query.py`, `src/sscre/cache.py`,
`src/sscre/app.py`, `src/sscre/postgres_cache.py`, and their focused tests.

#### Step 2.4 — Add storage isolation and migration evidence

- [x] Choose the storage representation for tenant and namespace IDs and
      record length, character, and case-normalization rules.
- [x] Add non-null tenant/namespace columns to cache entries, with a
      versioned backfill policy for existing rows. Existing rows must not be
      assigned to a real external tenant without an explicit operator decision.
- [x] Make the uniqueness constraint cover the scoped cache identity, not only
      the current global `query_hash`.
- [x] Scope canonical-answer ownership and foreign-key references so a
      canonical answer cannot be selected or deleted across tenant boundaries.
      If canonical answers are intentionally shared, record the separate
      authorization proof and prevent answer content disclosure through
      unscoped joins.
- [x] Scope hit counters, eviction, cleanup, storage-byte accounting, and
      statistics. Define whether caps are per tenant/namespace or global with
      an independently enforced per-tenant quota; the default external
      contract should be per tenant/namespace.
- [x] Update both the in-memory repository and PostgreSQL repository so tests
      cannot pass only because the in-memory implementation has weaker scope.
- [x] Add migration checksum, backfill, rollback/restore, and least-privilege
      notes. Run migration validation before claiming PostgreSQL verification.
- [x] Add PostgreSQL constraints and indexes for scoped lookup and vector
      filtering. Consider row-level security only after measuring the role and
      connection-pooling boundary; do not claim RLS protection unless it is
      enabled, tested, and documented.

**Planned implementation artifact:** a new numbered migration after
`011_validate_sha256_hashes.sql`; the exact filename is chosen during
implementation and must be recorded in the evidence manifest.

      [`migrations/012_cache_tenant_namespace.sql`](../migrations/012_cache_tenant_namespace.sql),
      [`migrations/013_cache_scoped_identity.sql`](../migrations/013_cache_scoped_identity.sql);
      [`docs/setup/POST_PHASE4_WS2_STORAGE_ISOLATION.md`](setup/POST_PHASE4_WS2_STORAGE_ISOLATION.md);
      [`tests/test_postgres_cache_scope.py`](../tests/test_postgres_cache_scope.py).

#### Step 2.5 — Enforce scoped lookup, semantic search, and canonical access

- [x] Require tenant/namespace predicates in exact-cache reads and writes.
- [x] Require the same predicates in vector search before similarity ordering
      and candidate selection. A post-query Python filter is insufficient.
- [x] Verify that metadata, freshness, compatibility, and canonical-answer
      validation run only on candidates from the authenticated scope.
- [x] Ensure replacement of an unsafe or stale answer can affect only the
      current scoped identity.
- [x] Scope canonical-answer reads and unreferenced-canonical deletion to the
      owning tenant/namespace policy.
- [x] Make repository methods reject a missing scope in external mode rather
      than interpreting it as “all tenants.” Keep any migration/admin-wide
      operation explicit and admin-only.
- [x] Add tests where tenant A and tenant B use identical queries, identical
      embeddings, identical answers, and overlapping namespaces; neither may
      read, select, replace, evict, or count the other’s data.

      [`src/sscre/query.py`](../src/sscre/query.py) (`resolve_operation_scope`,
      `MissingCacheScopeError`); [`src/sscre/cache.py`](../src/sscre/cache.py);
      [`src/sscre/postgres_cache.py`](../src/sscre/postgres_cache.py);
      [`src/sscre/app.py`](../src/sscre/app.py);
      [`tests/test_cache_scope_enforcement.py`](../tests/test_cache_scope_enforcement.py).

#### Step 2.6 — Define route authorization and operational exposure

- [x] Require a client scope such as `query:execute` for `/v1/query`.
- [x] Keep `/v1/cache/stats` admin-only and decide whether statistics are
      tenant-scoped by default or platform-wide only for a separate privileged
      scope. Never return platform-wide counts to a tenant-scoped caller.
- [x] Define authorization for future purge, cache inspection, export, and
      evaluation routes before adding any such route. No new destructive route
      is required to close this workstream.
- [x] Keep `/health` unauthenticated only when it returns no tenant, provider,
      database, configuration, or capacity detail and ingress is documented.
- [x] Keep `/ready` restricted to trusted ingress or a separately authorized
      health probe if its response or timing could reveal infrastructure state.
- [x] Use safe error bodies that do not expose SQL, provider payloads, cache
      contents, credential values, or whether another tenant has a matching
      key.
- [x] Document reverse-proxy and container binding settings. Compose
      development exposure must not be presented as an external deployment
      boundary.

      [`src/sscre/api_auth.py`](../src/sscre/api_auth.py);
      [`docs/setup/POST_PHASE4_WS2_API_AUTH_BOUNDARY.md`](setup/POST_PHASE4_WS2_API_AUTH_BOUNDARY.md);
      [`tests/test_api_route_authorization.py`](../tests/test_api_route_authorization.py).

#### Step 2.7 — Add abuse controls without weakening fail-closed behavior

- [x] Enforce the configured query/body byte limits before provider work and
      add an explicit request-body limit at the HTTP/server boundary where
      supported.
- [x] Add bounded per-client/per-tenant request rate limiting with a defined
      algorithm, clock behavior, storage scope, and response (`429` plus safe
      retry guidance). If shared rate-limit storage is unavailable, fail closed
      for external mode rather than silently disabling the control.
- [x] Add per-tenant concurrency and provider-budget limits, distinguishing
      request admission from the dependency timeout work in Workstream 3.
- [x] Ensure failed authentication, rejected size/rate/quota checks, malformed
      requests, repository failures, and provider failures do not insert or
      serve an answer.
- [x] Bound metric labels and logs to stable tenant/principal identifiers;
      never log bearer tokens, raw prompts, answers, embeddings, or provider
      credentials.
- [x] Add tests for oversized bodies, invalid JSON, rate-limit exhaustion,
      budget exhaustion, concurrent admission, and recovery after rejection.

      [`src/sscre/api_abuse_controls.py`](../src/sscre/api_abuse_controls.py);
      [`src/sscre/config.py`](../src/sscre/config.py);
      [`src/sscre/app.py`](../src/sscre/app.py);
      [`tests/test_api_abuse_controls.py`](../tests/test_api_abuse_controls.py).

#### Step 2.8 — Verify the boundary in both storage modes

- [x] Confirm every referenced test path, migration, marker, and CLI option
      exists before running verification.
- [x] Run focused authentication and route tests with the in-memory repository.
- [x] Run focused same-query and semantic cross-tenant isolation tests with
      deterministic fake clients; assert zero provider calls on rejected
      requests.
- [x] Run malformed-input, oversized-body, safe-error, request-ID, and health
      exposure tests.
- [ ] If PostgreSQL is available, apply migrations with the documented role
      boundary and run the scoped exact, vector, canonical, eviction, cleanup,
      statistics, and concurrent isolation tests.
- [x] Record PostgreSQL version, pgvector version, migration state/checksums,
      role configuration, workload, and skipped tests. If unavailable, record
      `unavailable` or `deferred`; do not call in-memory results PostgreSQL
      verification.
- [x] Run the full default unit suite after the focused tests and preserve the
      pre-existing Workstream 1 verification boundary.
- [x] Perform a redaction audit of logs, response bodies, and generated
      evidence before marking the verification gate complete.

      [`artifacts/stabilization/ws2-boundary-verification.json`](../artifacts/stabilization/ws2-boundary-verification.json);
      [`tests/test_ws2_boundary_gate.py`](../tests/test_ws2_boundary_gate.py);
      [`docs/setup/POST_PHASE4_WS2_EVIDENCE.md`](setup/POST_PHASE4_WS2_EVIDENCE.md).

**Evidence deliverables:** threat model, API/auth contract, migration and
schema report, redacted route/isolation test output, and a machine-readable
verification record under `artifacts/stabilization/` with commit, worktree,
configuration mode, dependency versions, and unavailable-path explanations.

### Workstream 2 gates and acceptance criteria

**Authoring gate:** The boundary decision, threat model, API/auth contract,
scope/key design, storage design, route matrix, abuse-control design, and
verification protocol exist. Authoring does not authorize external exposure.

- [x] Trusted-local mode is explicitly loopback/private-ingress only and is
      not described as multi-user or production-ready.
- [x] External mode requires an approved authenticated client context before
      any query cache or provider operation.
- [x] Tenant and namespace scope is enforced in exact lookup, vector search,
      canonical-answer access, insertion, replacement, cleanup, eviction, and
      statistics.
- [x] Admin credentials cannot be used as tenant client identity and tenant
      credentials cannot access admin operations.
- [x] Unauthorized, malformed, oversized, rate-limited, quota-exhausted, and
      repository-failure requests fail closed without provider calls or cache
      writes.
- [x] Health/readiness exposure and trusted ingress requirements are documented.

**Verification gate:** Workstream 2 passes only when the applicable focused
tests pass in-memory, the PostgreSQL isolation tests pass when Gate B is
available (or are explicitly recorded as unavailable/deferred), the full
allowed suite passes, and all evidence is redacted and tied to the current
commit/worktree. A conditional test that was not run is not pass or fail.

**Stopping rule:** No external or multi-user deployment is authorized until
the verification gate passes. Stop immediately if tenant identity can be
caller-supplied, if any repository path can omit scope in external mode, if
canonical answers remain globally readable, if rate/quota enforcement can be
bypassed on dependency failure, or if the selected auth/storage boundary
cannot be tested in the actual PostgreSQL path. External mode must also run
with one application process unless a shared rate-limit and provider-budget
store is implemented and verified; process-local controls are not sufficient
for multi-worker or multi-replica deployment.

## Workstream 3 — Timeout, concurrency, and failure-closed runtime stability

**Purpose:** Ensure bounded requests do not exhaust workers or produce
uncontrolled errors.

- [ ] Reproduce and test executor-slot retention after a timed-out dependency
      callable continues running.
- [ ] Replace or redesign timeout execution so capacity is not silently
      exhausted by uninterruptible work; document any unavoidable isolation
      boundary.
- [ ] Convert generation-lock timeout into a controlled 503/504 response with
      request ID and no cache reuse.
- [ ] Test simultaneous generation, embedding, repository, and cache-write
      timeouts.
- [ ] Test repeated timeout recovery and bounded memory/thread growth.
- [ ] Review local embedding timeout executors for thread retention under
      repeated provider stalls.
- [ ] Verify duplicate-generation behavior across processes remains explicitly
      distinguished from duplicate-insert prevention.
- [ ] Preserve fail-closed behavior for lookup, semantic search, freshness,
      embedding validation, generation, insertion, and replacement failures.

**Acceptance criteria:**

- [ ] Timeout storms do not permanently consume the configured request
      capacity.
- [ ] Lock contention returns a controlled response, not an unhandled 500.
- [ ] No expired, unsafe, malformed, or unauthorized answer is served after a
      dependency failure.
- [ ] Concurrency tests pass both in-process and, when PostgreSQL is available,
      across multiple processes.

**Evidence:** Focused timeout/concurrency tests, bounded resource measurements,
and failure-path verification output.

**Stopping rule:** Stop if the chosen timeout mechanism cannot guarantee
bounded resource behavior; document the required process or worker isolation.

## Research track R1 — Strategy C diagnosis and authorized provider run

**Purpose:** Explain the observed low Strategy C reuse rate and obtain the
minimum real-provider evidence needed before constructing the fresh headline
evaluation. This track uses existing cache, trace, evaluation, and provider
interfaces; it does not add a second cache layer, a new rate-limit module, or a
provider-specific SDK.

### Step R1.1 — Diagnose Strategy C before changing policy

- [ ] Select a reproducible diagnostic population that is not used for the
      fresh headline result.
- [ ] Export decision-trace counts by exact versus semantic path, decision,
      reason, stage, similarity band, freshness outcome, missing/conflicting
      metadata, and unlabeled-candidate reuse.
- [ ] Compare candidate availability with candidate rejection so low reuse is
      not attributed to the threshold without evidence.
- [ ] Record the denominators, configuration, model/dimension identity,
      protocol version, commit, and worktree state.
- [ ] Do not retune thresholds or compatibility rules from this diagnostic
      population unless the protocol explicitly permits development-only
      tuning.

**Acceptance criteria:**

- [ ] The dominant causes of Strategy C abstention are identified or recorded
      as unavailable.
- [ ] The diagnostic report is clearly non-headline and cannot be mistaken for
      fresh held-out evidence.
- [ ] No safety rule is weakened to increase reuse during diagnosis.

**Evidence:** One redacted Strategy C diagnosis report and the command or
fixture needed to reproduce it.

### Step R1.2 — Run a bounded real-provider measurement when authorized

- [ ] Obtain explicit provider approval, credentials, quota, pricing, and
      endpoint/model approval under Gate C.
- [ ] Run the smallest authorized provider measurement over the existing
      development/tuning population (currently 400 records) before any fresh
      held-out run.
- [ ] Record provider, model, embedding dimension, request count, retries,
      failures, estimated cost, rate-limit behavior, and redacted outputs.
- [ ] Keep provider results separate from synthetic, fake-provider, historical,
      and fresh-held-out evidence.
- [ ] If approval or credentials are unavailable, record Gate C as deferred;
      do not substitute fake-provider numbers.

**Acceptance criteria:**

- [ ] The run is reproducible from a checked-in command and configuration
      description, with secrets supplied out of band.
- [ ] Provider and cost evidence are complete enough to decide whether the
      fresh evaluation can proceed.
- [ ] No live-provider result is presented as a semantic headline result until
      Workstream 5 passes its fresh-data gate.

**Evidence:** Redacted provider-run manifest, cost/usage summary, failure
summary, and unavailable/deferred explanation when applicable.

**Stopping rule:** Stop before provider execution without explicit approval,
valid credentials, bounded quota, and a redaction plan.

## Workstream 4 — PostgreSQL correctness, schema, and vector-search readiness

**Purpose:** Verify the actual storage path before making deployment or scale
claims.

- [ ] Run all PostgreSQL integration, failure-recovery, contention,
      multiprocess, and load markers against a migrated PostgreSQL/pgvector
      instance.
- [ ] Test startup with a least-privilege application role and separate
      migration role.
- [ ] Remove startup DDL requirements or document the required privilege
      boundary.
- [ ] Validate canonical-answer integrity on reads and tampered-row behavior.
- [ ] Filter expired/disallowed candidates in the database query or prove that
      post-query filtering cannot reduce valid-candidate recall.
- [ ] Measure vector-search plans with `EXPLAIN (ANALYZE, BUFFERS)` at declared
      cache sizes.
- [ ] Decide whether to add and validate HNSW/IVFFlat indexing; do not add an
      index without measured dimension, workload, and migration evidence.
- [ ] Verify storage caps, eviction, cleanup, uniqueness, and transaction
      behavior under concurrent writes.
- [ ] Record PostgreSQL version, pgvector version, schema migration checksums,
      hardware, worker count, and workload.

**Acceptance criteria:**

- [ ] All required PostgreSQL tests either pass or have explicit unavailable
      evidence.
- [ ] Application startup can run with least privilege after migrations.
- [ ] Vector query plans and cap/eviction behavior are documented at the
      declared test scale.
- [ ] No PostgreSQL result is described as a universal production SLA.

**Evidence:** Migration/privilege report, PostgreSQL test output, query plans,
and bounded load artifact.

**Stopping rule:** Stop scale claims if the database is unavailable, the
workload is too small to measure, or query plans are not captured.

## Workstream 5 — Evaluation validity and fresh held-out gate

**Purpose:** Complete or formally defer the only authorized semantic headline
evaluation.

- [ ] Construct a fresh, licensed held-out population outside the previously
      used 615 records.
- [ ] Review compatible, incompatible, uncertain, and high-similarity
      candidate/query relations required for served-candidate attribution.
- [ ] Assign immutable IDs, source/license metadata, review status, and split
      membership.
- [ ] Freeze a dedicated manifest and full SHA-256 before threshold selection.
- [ ] Extend `src/sscre/evaluate.py` to accept an explicit fresh benchmark and
      manifest path while retaining fail-closed contamination checks.
- [ ] Strengthen `src/sscre/semantic_validity_gate.py` to verify benchmark,
      manifest, dataset, config, provider, model, dimension, attribution, and
      artifact hashes independently.
- [ ] Select thresholds only on development data.
- [ ] Run local real-embedding A/B/C evaluation once on the authorized fresh
      held-out population.
- [ ] Score the pre-registered C-versus-A requirements without changing them
      after inspecting results.
- [ ] Record `pass`, `fail`, `unavailable`, or `deferred`; never convert an
      unrun conditional check into pass/fail.

**Acceptance criteria:**

- [ ] Freshness and lineage are independently verified.
- [ ] No held-out outcome influences threshold or policy selection.
- [ ] C strictly improves safe-reuse coverage over A.
- [ ] C satisfies the FPR cap and abstention ceiling.
- [ ] Strategy C has zero unlabeled served-candidate reuse for the headline
      result.
- [ ] The final artifact records model, dimension, dataset, manifest, config,
      commit, worktree state, denominators, and confidence intervals.

**Evidence:** Fresh benchmark, manifest, source/license review, held-out
comparison artifact, gate artifact, and verification log.

**Stopping rule:** If fresh data or reviewed candidate relations cannot be
constructed, retain the current deferred verdict.

## Workstream 6 — Correctness and label completeness

**Purpose:** Separate compatibility/reuse safety from factual answer quality.

- [ ] Decide whether factual correctness is a required project claim or an
      explicitly deferred claim.
- [ ] If required, collect answer-bearing responses for the selected benchmark
      population.
- [ ] Define a separate correctness rubric, annotator process, adjudication
      policy, and provenance fields.
- [ ] Keep correctness, compatibility, preference, and served-reuse labels
      independent in code and artifacts.
- [ ] Add inter-annotator agreement or an explicit unavailable rule.
- [ ] Prevent compatibility labels from being presented as factual correctness.

**Acceptance criteria:**

- [ ] Every factual-quality claim has answer-bearing evidence and a documented
      review protocol.
- [ ] Missing correctness data is reported as unavailable, never zero or
      inferred.

**Evidence:** Label contract, reviewed answer dataset, adjudication summary,
and label-quality tests.

**Stopping rule:** If answer generation or human review is not available,
leave factual correctness explicitly deferred.

## Workstream 7 — CI, reproducibility, and artifact hygiene

**Purpose:** Ensure ordinary CI cannot report green while critical paths are
      silently unverified.

- [ ] Keep the fast default unit-test job.
- [ ] Add a benchmark-validation job using the committed benchmark and
      production validation flags.
- [ ] Add P4 gate/deferred-path tests to CI.
- [ ] Add a Compose configuration job using the documented non-secret sample
      environment.
- [ ] Add an opt-in PostgreSQL service job for migrations, integration,
      failure, contention, and vector tests.
- [ ] Add a separate explicitly authorized provider job only when credentials
      and quotas are available; never expose secrets in logs.
- [ ] Add artifact lineage and redaction validation.
- [ ] Fail CI on stale manifest references in artifacts intended as current.
- [ ] Keep historical artifacts but label them historical and exclude them from
      current headline summaries.
- [ ] Remove generated caches and accidental files from the deliverable.

**Acceptance criteria:**

- [ ] CI reports unit, benchmark, Compose, and available PostgreSQL/provider
      coverage separately.
- [ ] Skips and unavailable infrastructure are visible and explained.
- [ ] Current artifacts resolve to existing files and matching hashes.
- [ ] A clean checkout can reproduce every claim marked verified.

**Evidence:** CI logs, artifact-manifest validation output, redaction report,
and clean-checkout replay record.

**Stopping rule:** Do not mark the project stable while current claims depend
on uncommitted code or untracked artifacts.

## Workstream 8 — Documentation, release boundary, and close-out

**Purpose:** Reconcile the repository after stabilization without broadening
scope.

- [ ] Update `docs/SSCRE_PLAN.md` only after implementation evidence exists.
- [ ] Synchronize Phase 2, Phase 3, and Phase 4 statuses with actual results.
- [ ] Explicitly distinguish complete, locally verified, PostgreSQL verified,
      provider verified, historical, deferred, unavailable, and out-of-scope.
- [ ] Update deployment documentation with the authentication, tenancy,
      provider, migration-role, and Compose-default boundaries.
- [ ] Add a concise release-readiness statement.
- [ ] Re-run the full allowed verification suite after the final stabilization
      change.
- [ ] Review `git status` and keep close-out status explicit until the
      stabilization package is committed by an approved git workflow.

**Acceptance criteria:**

- [ ] No document claims semantic superiority without an authorized fresh
      held-out result.
- [ ] No document claims factual correctness without correctness labels.
- [ ] No document claims multi-tenant or production capacity readiness before
      the relevant safety and infrastructure work passes.
- [ ] All checked completion boxes have current evidence.

**Evidence:** Final stabilization evidence document, verification manifest,
      release-boundary note, and final repository status.

## Out of scope for this plan

- Strategy D/cross-encoder implementation.
- Int8 embedding quantization unless a new measured storage gate authorizes it.
- Dashboard or frontend expansion.
- Prompt caching, session caching, cache warming, or RAG features.
- Multi-region, Kubernetes, cloud failover, or universal SLA claims.
- New benchmark categories unrelated to the fresh held-out gate.
- Commercial provider optimization or provider-specific SDK integration before
  the existing boundary is validated.
- Broad refactoring unrelated to a failing acceptance criterion.

## Recommended execution order

1. [x] Workstream 0 — freeze baseline and claim inventory.
2. [x] Workstream 1 — establish reproducible local and Compose setup.
3. [ ] Workstream 3 — complete only the timeout and concurrency fixes that
      affect bounded research execution.
4. [ ] Research track R1 — diagnose Strategy C and run the bounded authorized
      provider measurement, or record Gate C as deferred.
5. [ ] Workstream 5 — construct and run the fresh semantic gate.
6. [ ] Workstream 7 — enforce the verified research paths in CI.
7. [ ] Workstream 8 — reconcile documentation and release status.
8. [x] Deferred deployment track — Workstream 2 external API safety boundary
      implemented; in-memory
      verification gate passed ([`POST_PHASE4_WS2_EVIDENCE.md`](setup/POST_PHASE4_WS2_EVIDENCE.md));
      PostgreSQL Gate B and multi-worker deployment remain deferred.
9. [ ] Deferred deployment track — Workstream 4 PostgreSQL and vector behavior,
      only if external
      deployment, scale, or PostgreSQL-backed evidence is required.
10. [ ] Optional research extension — Workstream 6 correctness labels, only if
      factual answer-quality claims are required.

## Overall exit verdict

The project may be called **research-ready for local evaluation** only when
Workstreams 0, 1, the research-relevant portion of 3, R1, 5, and 7 pass, and
all remaining limitations are documented.

The project may be called **ready for external multi-user deployment** only
when Workstream 2 and the required portions of Workstream 4 pass.

The project may claim **semantic safe-reuse superiority** only when Workstream
5 passes its pre-registered gate.

The project may claim **factual answer-quality improvement** only when
Workstream 6 passes.
