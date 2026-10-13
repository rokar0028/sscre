# SSCRE Stabilization and Evidence Completion Plan

## Goal

Make the current SSCRE implementation stable, reproducible, and honestly
deployable before adding new capabilities. This plan closes existing safety,
runtime, infrastructure, evaluation, and documentation gaps. It does not add
new product features.

## Status

**Status:** `in progress — Workstream 1 closed (Gate A); Workstream 2 not started`

**Evidence:** [`docs/POST_PHASE4_STABILIZATION_EVIDENCE.md`](POST_PHASE4_STABILIZATION_EVIDENCE.md) (Workstream 0 closed)

**Parent:** [`docs/SSCRE_PLAN.md`](SSCRE_PLAN.md), §§20, 23, and 24.

**Scope:** Stabilization after Phase 4 semantic-validity deferral.

**Exit:** The repository has a reproducible local environment, verified
failure-closed runtime behavior, explicit deployment boundaries, current CI
coverage, and either a valid fresh held-out semantic result or an explicit
documented deferral.

## Current baseline

- WS0–WS1 stabilization package is committed on `main` (Gate A tooling, docs,
  and verification artifacts).
- Gate A verification (WS1 Step 1.7) passed locally: **835** pytest tests
  (with optional `local-embeddings` installed),
  Compose config, import smoke, and env validator; see
  `artifacts/stabilization/gate-a-package-verification.json`.
- PostgreSQL integration markers and live-provider tests remain opt-in
  (Gate B / Gate C); WS1 recorded DB readiness only where Docker was available.
- `docker-compose.yml` and `.env.example` default to Strategy **C**.
- The public query endpoint has no client authentication, tenant, or namespace
  boundary.
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

- [x] Run `python -m pytest -q`.

      **835 passed**, 1 skipped, 21 deselected —
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
and cross-tenant disclosure before external exposure.

- [ ] Decide and document whether the service is single-tenant trusted-local
      software or a multi-tenant API.
- [ ] If externally reachable, require authenticated client requests on
      `POST /v1/query`.
- [ ] Define tenant/namespace identity and include it in exact-cache keys,
      semantic search filters, canonical-answer ownership, eviction, and
      statistics.
- [ ] Add database constraints and, if appropriate, PostgreSQL row-level
      security for the chosen tenancy model.
- [ ] Define authorization for cache reuse, generation, cache insertion, stats,
      purge, and evaluation operations.
- [ ] Add abuse controls: request rate limits, provider budget limits, bounded
      request body size, and safe error responses.
- [ ] Add regression tests proving one tenant cannot read or select another
      tenant's cached answer.
- [ ] Keep `/health` and `/ready` exposure explicitly documented and ingress
      restricted where required.

**Acceptance criteria:**

- [ ] No externally reachable query path is unauthenticated unless the
      deployment contract explicitly places it behind trusted authentication.
- [ ] Cross-tenant lookup, vector search, canonical-answer access, eviction,
      and metrics are isolated.
- [ ] Unauthorized and malformed requests fail closed without provider calls.

**Evidence:** Threat model, API/auth contract, migration/schema evidence, and
passing isolation/authorization tests.

**Stopping rule:** No external or multi-user deployment is authorized until
this workstream passes.

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
3. [ ] Workstream 3 — fix timeout and concurrency safety.
4. [ ] Workstream 2 — define and enforce the external API safety boundary.
5. [ ] Workstream 4 — verify PostgreSQL and vector behavior.
6. [ ] Workstream 5 — construct and run the fresh semantic gate.
7. [ ] Workstream 6 — add correctness labels only if factual claims are required.
8. [ ] Workstream 7 — enforce the verified paths in CI.
9. [ ] Workstream 8 — reconcile documentation and release status.

## Overall exit verdict

The project may be called **stabilized for local research use** only when
Workstreams 0, 1, 3, and 7 pass and all remaining limitations are documented.

The project may be called **ready for external multi-user deployment** only
when Workstream 2 and the required portions of Workstream 4 pass.

The project may claim **semantic safe-reuse superiority** only when Workstream
5 passes its pre-registered gate.

The project may claim **factual answer-quality improvement** only when
Workstream 6 passes.
