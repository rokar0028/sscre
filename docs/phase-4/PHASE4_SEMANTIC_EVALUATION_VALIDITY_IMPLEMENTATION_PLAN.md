# Phase 4 — Semantic Evaluation Validity and Real-Embedding Vertical Slice

## 1. Goal

Establish whether SSCRE's compatibility-aware Strategy C provides a semantic
safe-reuse benefit over exact caching when evaluated with:

- a real, fixed-dimension embedding model;
- corrected candidate-level outcome attribution;
- a fresh, leakage-checked evaluation protocol; and
- a pre-registered held-out gate.

The intended result is either a defensible positive result or a defensible
negative result. Engineering completion, a zero measured FPR produced by
abstention, and successful artifact generation are not semantic success.

## 2. Status

**Status:** `closed (docs reconciliation; headline gate deferred)` — Steps 1–8
closed in repo (2026-10-12). Fresh held-out headline replay remains a future data
gate, not an open implementation step in this workstream.

**Goal / Exit gate — authoring:** closed when this plan exists with the
protocol, stopping rules, and verification commands below.

**Verification gate — implementation:** closed for authorized scope (Steps 1–7
code + Step 8 reconciliation). Fresh held-out headline evaluation and semantic
**pass** remain explicitly **deferred** (not authorized on contaminated split).

## 3. Evidence

- Current review:
  [`sscre_full_review_2026-10-12_v2.md`](../../sscre_full_review_2026-10-12_v2.md)
- Master roadmap:
  [`docs/SSCRE_PLAN.md`](../SSCRE_PLAN.md), §§20 and 24
- Close-out branch / HEAD: `main`, `8c18d3772af3e690fa28af4a330de29cacafb08c`
      (historical audit baseline: `phase4/setup`, `b7eda9d`)
- Current benchmark:
  `reviewed-query-pairs-2.0`, 615 records, 400 development / 215 held-out
- Current split manifest:
  `benchmarks/split_manifest.json`, expected hash prefix `0aca5b8d…`
- Current Phase 3 final artifacts still reference manifest `68912e3b…`
- Current B/C artifacts use `fake-embedding`, dimension 8
- Test evidence: Step 5 rectification **794** passed; Step 8 full suite **807**
      passed, 15 skipped, 21 deselected (2026-10-12 close-out)
- Current correctness evidence:
  no human answer-correctness labels; all current records have
  `answer_availability: none`

The current Phase 2 artifacts were regenerated against the current manifest.
The Phase 3 final package is historical until it is either regenerated or
explicitly superseded.

## 4. Parent

- Parent roadmap: [`docs/SSCRE_PLAN.md`](../SSCRE_PLAN.md)
- Relevant roadmap sections: §§20, 24, and 25
- Evaluation contracts:
  [`docs/phase-2/SAFETY_EVALUATION_CONTRACT_v1.md`](../phase-2/SAFETY_EVALUATION_CONTRACT_v1.md)
  and
  [`benchmarks/README.md`](../../benchmarks/README.md) plus the implementation
  contract in [`src/sscre/evaluation_labels.py`](../../src/sscre/evaluation_labels.py).
  Label contract file:
  [`benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
  (present; parent dead-path claim removed at Step 1 close — see evidence).
- Prior evaluation implementation:
  [`src/sscre/baseline.py`](../../src/sscre/baseline.py)
  and [`src/sscre/evaluate.py`](../../src/sscre/evaluate.py)

## 5. Card

**Card ID:** `P4-SEMVALID`

**Hypothesis:** With a real semantic embedding model and candidate-level
scoring, Strategy C will provide strictly greater safe-reuse coverage than
Strategy A at or below the pre-registered unsafe-reuse-rate cap, without
depending on an unacceptable abstention rate.

**Primary comparison:** Strategy A exact cache versus Strategy C
compatibility-aware cache. Strategy B remains a diagnostic baseline and is
not a safety-approved path.

**Primary pass rule:** On the fresh held-out scoring population, C must have
strictly greater safe-reuse coverage than A, satisfy the configured unsafe
reuse/FPR cap, and satisfy the pre-registered abstention ceiling.

**Fail rule:** If C does not strictly improve safe-reuse coverage, violates the
unsafe-reuse cap, or only passes by exceeding the abstention ceiling, record a
negative result and retain the conservative existing stack.

**Data sufficiency rule:** A served candidate with no reviewed compatibility
relation to the current query is not silently scored as safe or unsafe. It is
reported as `unlabeled_candidate_reuse` and cannot contribute to a passing
headline metric. The held-out gate cannot run until the scored population has
adequate reviewed candidate/query relations.

**Stopping rules:**

- Stop before real-provider execution if no approved local real-embedding
  dependency/model is already available and adding one would violate the
  dependency or licensing constraints.
- Stop before held-out reporting if a genuinely fresh, licensed, leakage-checked
  held-out population cannot be constructed.
- Stop before threshold selection if development candidate attribution cannot
  identify the actual served candidate.
- Stop and generate fresh output if any evaluation artifact has a mismatched
  dataset, split, config, model, or manifest identity.
- Stop and record `deferred`, not `pass`, for unavailable provider, data,
  PostgreSQL, or environment gates.

## 6. Out of scope for this document

- Cross-encoder Strategy D.
- Int8 or other embedding quantization.
- Multi-tenancy, sessions, prompt caching, warming, or authorization redesign.
- Dashboard or frontend work.
- Production deployment or capacity claims.
- PostgreSQL schema/index optimization unless the real-embedding slice cannot
  execute or validate storage/retrieval without it.
- Human correctness labeling of the full benchmark.
- A live commercial-provider cost claim.
- Adding a dependency without first checking the installed environment,
  licensing, and whether the local vertical slice requires it.

## 7. Current baseline

### Software baseline

- `src/sscre/app.py` provides exact and semantic request paths, bounded
  dependency execution, TTL checks, cache insertion, and generation fallback.
- `src/sscre/compatibility.py` implements Strategy C's fail-closed metadata
  checks.
- `src/sscre/embedding.py` provides `FakeEmbeddingClient` for tests and local
  synthetic experiments.
- `src/sscre/remote_embedding.py` provides an OpenAI-compatible remote boundary.
- `src/sscre/baseline.py` runs A, B, and C replay baselines with candidate-level
  reuse attribution (`evaluation_attribution.py`, Step 2).
- `src/sscre/evaluation_statistics.py` computes aggregate statistics; reuse
  headline FPR uses labeled served-reuse outcomes and supports
  `unlabeled_candidate_reuse` on request samples.

### Evaluation baseline

The historical Phase 3 held-out comparison reports approximately:

- A: hit rate `0.0535`, one safe reuse, FPR unavailable;
- B: hit rate `0.0628`, FPR `0.4815`, two safe reuses, thirteen unsafe reuses;
- C: hit rate `0.0023`, FPR `0.0`, one safe reuse, zero unsafe reuses;
- C abstention rate approximately `0.607`;
- B/C embedding model `fake-embedding`, dimension `8`;
- synthetic costs and token-count proxies.

These values are historical synthetic evidence, not the baseline for a new
semantic claim. The Phase 3 artifact lineage must be repaired or explicitly
excluded from the new comparison.

### Repository and environment baseline

- Full suite after Step 2 remediation: **775 passed**, 15 skipped, 21 deselected
  (`PYTHONPATH=src`, 2026-10-12); re-run `python -m pytest -q` before later
  gate claims.
- PostgreSQL and real-provider tests are opt-in or unavailable by default.
- `docker-compose.yml` currently defaults to Strategy B; this plan must not
  promote that default and must record it as a deployment safety gap.

## 8. Open baseline gaps

- [x] Correctly identify and score the actual served candidate
      ([`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md)
      Step 2; `src/sscre/evaluation_attribution.py`).
- [x] Resolve the missing `benchmarks/EVALUATION_LABEL_CONTRACT_v1.md`
      documentation path or record it as a documentation gap (file exists;
      [`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md)).
- [x] Add exact-cache FPR and candidate-level unsafe-reuse metrics (Step 2;
      `ExactCacheReport.false_positive_rate` uses labeled reuse denominator).
- [x] Decide how context-stripped identical-text pairs are represented (Step 3;
      `context_required` exclusion list in
      `experiments/semantic-validity-evaluation-config-v1.json`).
- [ ] Obtain or construct a genuinely fresh held-out scoring population (gate
      `held-out-deferred` at Step 3; see
      `benchmarks/semantic-validity-held-out-gate.json`).
- [ ] Prove that fresh candidate/query relations have reviewed compatibility
      labels (held-out gate). Replay reporting of `unlabeled_candidate_reuse` is
      implemented (Step 2 evidence).
- [x] Freeze a new protocol/config version (Step 3;
      `semantic-validity-evaluation-config-1.0`,
      SHA-256 `cf238079…` — evidence § Step 3/4).
- [x] Select and validate an approved real embedding model and fixed dimension
      (Step 4; `sentence-transformers/all-MiniLM-L6-v2`, dim 384 — evidence §
      Step 4).
- [x] Re-run development A/B/C with real embeddings (Step 5;
      `artifacts/evaluation/phase4-semantic-validity-development.json`).
- [ ] Run one untouched held-out evaluation (blocked — `held-out-deferred`).
- [x] Regenerate or supersede stale Phase 3 artifacts — **not required** by
      protocol; Phase 3 final package marked historical in evidence (Step 8).
- [x] Reconcile §20 checkboxes and §24 claims with measured results (Step 8).

## 9. Risks and stopping rules

### Data and label risks

- The existing 215-record held-out split has already been used in final and
  follow-up artifacts. It is not automatically fresh.
- Existing compatibility labels describe the reviewed pair relation, not
  arbitrary nearest-neighbor candidate relations.
- Existing records contain no reviewed answer correctness. The milestone must
  not claim factual correctness.
- CacheEval-derived material must retain approved filtering, attribution, and
  license evidence. Unlicensed or unreviewed rows must not be committed.

### Model and environment risks

- A local embedding package/model may not be installed or may have a license
  incompatible with repository artifacts.
- Real embeddings may change vector dimension and storage behavior.
- CPU inference may be slow enough to make the run impractical. Record this as
  an environment result; do not substitute fake embeddings in the semantic
  headline run.
- Provider failures must generate fresh responses or controlled errors, never
  cache reuse.

### Interpretation risks

- A zero FPR with near-zero coverage is not a useful semantic success.
- A threshold selected after inspecting held-out results is invalid.
- A high hit rate from unlabeled or incorrectly attributed candidates is not
  evidence.
- Cost and token values must identify whether they are measured, provider
  reported, estimated, or unavailable.

### Required stopping classifications

Every gate records exactly one of:

- `pass` — the pre-registered rule was scored and satisfied;
- `fail` — the pre-registered rule was scored and not satisfied;
- `skip` — a declared conditional check was not applicable;
- `unavailable` — required environment/provider/data was unavailable;
- `deferred` — execution was not authorized or was intentionally postponed.

An unrun conditional feature is not `pass` or `fail`.

## 10. Ordered implementation steps

### Step 1 — Audit current evaluation code and artifacts

**Purpose:** Establish the exact starting state before changing scoring or
protocol.

Child plan:
[`PHASE4_STEP1_EVALUATION_AUDIT_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP1_EVALUATION_AUDIT_IMPLEMENTATION_PLAN.md)
(closed 2026-10-12).

- [x] Confirm that every referenced source, test, artifact, CLI command, and
      marker exists in the current checkout.
- [x] Inspect `src/sscre/baseline.py`,
      `src/sscre/evaluation_statistics.py`,
      `src/sscre/evaluate.py`, and the relevant tests.
- [x] Inventory A/B/C artifact schemas, nested baseline payloads, model names,
      dimensions, costs, token fields, split names, config hashes, commit
      identities, dirty-tree flags, and manifest hashes.
- [x] Confirm the current manifest hash with
      `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production`.
- [x] Classify Phase 3 artifacts referencing `68912e3b…` as historical/stale
      in the evidence record.
- [x] Record the audit in
      `docs/phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`.

**Exit evidence:** A checked inventory table and a list of artifacts eligible
or ineligible for the new comparison.

### Step 2 — Correct candidate-level evaluation attribution

**Purpose:** Ensure metrics describe the candidate actually served.

Child plan:
[`PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md)
(closed 2026-10-12).

- [x] Define an explicit candidate provenance record containing at least the
      candidate query hash, normalized query identity, answer identity,
      source pair ID when available, source direction when available, and
      current query identity.
- [x] Update replay bookkeeping so each cache hit records the selected
      candidate, not only the current request record.
- [x] For known reviewed pair relations, score compatibility against the
      actual candidate/current-query relation.
- [x] For candidate/current-query relations without a reviewed label, record
      `unlabeled_candidate_reuse` and exclude it from the headline FPR/pass
      calculation until reviewed labels exist.
- [x] Add exact-cache FPR and unsafe-reuse fields to the exact report without
      changing the meaning of compatibility, correctness, or preference labels.
- [x] Preserve the distinction between:
      - compatibility/reuse permission;
      - answer factual correctness; and
      - answer preference.
- [x] Add regression tests for:
      - duplicate normalized queries;
      - context-stripped identical text marked non-reusable;
      - an embedding false positive whose served candidate differs from the
        current benchmark pair;
      - exact-cache FPR;
      - unlabeled candidate reuse;
      - directional `a_to_b` and `b_to_a` scoring.
- [x] Verify failure-path behavior remains fail closed.

**Exit evidence:** Focused tests pass and a small fixture report demonstrates
that the metric follows the served candidate
([`PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md`](./PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md)
§ Step 2).

### Step 3 — Define and freeze the protocol reset

**Purpose:** Prevent further threshold or held-out contamination.

Child plan:
[`PHASE4_STEP3_PROTOCOL_RESET_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP3_PROTOCOL_RESET_IMPLEMENTATION_PLAN.md)
(closed 2026-10-12).

- [x] Create a new config/protocol version; do not overwrite the historical
      configuration identity (`experiments/semantic-validity-evaluation-config-v1.json`;
      `evaluation-config-1.0` unchanged).
- [x] Freeze the threshold grid, top-K, FPR cap, abstention ceiling, latency
      reporting rules, token/cost reporting rules, and tie-break rules.
- [x] Define the exact primary population and denominator for safe coverage,
      FPR, precision, recall, and abstention.
- [x] Decide how context-stripped identical-text pairs are handled:
      retain in a separate `context_required` category and exclude from the
      primary headline population (27 pair IDs in frozen config).
- [x] Determine whether a genuinely fresh held-out population exists outside
      the already-used 615-pair evaluation package (none in repo at Step 3
      close).
- [ ] If available, select fresh records from approved/licensed sources,
      assign immutable IDs, review them, and freeze a new manifest (deferred —
      see held-out gate record).
- [x] If unavailable, stop the held-out gate as `unavailable` or `deferred`;
      do not relabel the old held-out split as fresh (`held-out-deferred` in
      `benchmarks/semantic-validity-held-out-gate.json`).
- [x] Ensure development records are the only records used for threshold
      selection.
- [x] Document all reuse of old data as development/debug-only.

**Exit evidence:** New protocol/config identity and a manifest decision:
`fresh-held-out-ready`, `held-out-unavailable`, or `held-out-deferred`
(recorded: **`held-out-deferred`** — evidence § Step 3).

### Step 4 — Add or select a real local embedding path

**Purpose:** Replace fake semantic evidence without adding unnecessary
infrastructure.

Child plan:
[`PHASE4_STEP4_LOCAL_EMBEDDING_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP4_LOCAL_EMBEDDING_IMPLEMENTATION_PLAN.md)
(closed 2026-10-12).

- [x] Inspect installed packages and available local models before editing
      dependencies (`torch` present; `sentence-transformers` via optional extra
      `local-embeddings`).
- [x] Choose one approved fixed-dimension local model only if it is available,
      licensed for the intended use, and reproducible in the environment
      (`all-MiniLM-L6-v2`, Apache-2.0, 384-dim).
- [x] If no suitable local model exists, record the provider gate as
      `unavailable` and do not substitute fake embeddings for the headline
      result (gate file supports `unavailable`; this environment: `available`).
- [x] Add a provider implementation only at the existing embedding boundary
      (`src/sscre/local_embedding.py`).
- [x] Record model name/version, provider type, dimension, normalization,
      dtype, device, latency, batch behavior, and failure behavior (config +
      smoke artifact).
- [x] Validate vector finiteness, dimension, model identity, and configuration
      identity before storage or retrieval (`validate_embedding_result`).
- [x] Keep `FakeEmbeddingClient` for tests and synthetic regression fixtures.
- [x] Add tests for successful embedding, malformed output, dimension mismatch,
      provider failure, timeout, and no-cache-on-failure
      (`tests/test_local_embedding.py`).
- [x] Do not change PostgreSQL schema or add an ANN index in this step unless
      the selected provider cannot operate with the existing boundary (unchanged).

**Exit evidence:** Provider contract tests pass and a non-secret local smoke
artifact records model identity and dimension (evidence § Step 4).

### Step 5 — Run development A/B/C evaluation

**Purpose:** Select thresholds and validate the corrected evaluator without
touching held-out results.

Child plan:
[`PHASE4_STEP5_DEVELOPMENT_EVALUATION_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP5_DEVELOPMENT_EVALUATION_IMPLEMENTATION_PLAN.md)
(closed 2026-10-12). Threshold decision:
[`PHASE4_STEP5_THRESHOLD_DECISION.md`](./PHASE4_STEP5_THRESHOLD_DECISION.md).

- [x] Run A, B, and C on the frozen development population.
- [x] Use the real embedding provider for B/C (`local_embedding_replay`).
- [x] Select thresholds only from development data.
- [x] Record, for every arm:
      hit rate, safe-reuse coverage, unsafe reuse count, FPR, precision,
      recall, abstention, p50/p95/p99 latency, embedding latency, generation
      latency, measured/provider-reported/estimated token fields, and cost
      assumptions.
- [x] Record candidate attribution coverage and unlabeled-candidate counts
      (`reuse_attribution_summary` in artifact).
- [x] Record exact-cache FPR even when its denominator is zero or unavailable;
      use an explicit unavailable reason rather than silently emitting zero
      (`false_positive_rate_unavailable_reason` when no labeled reuse).
- [x] Generate a development artifact with config, dataset, split, provider,
      model, dimension, commit, clean/dirty state, and environment provenance.
- [x] Confirm no held-out labels or held-out outcomes influenced selection
      (`held_out_influence: none`).

**Exit evidence:** Development artifact, selection diagnostics, and a written
threshold decision satisfying the new protocol (evidence § Step 5).

### Step 6 — Run one fresh held-out evaluation

**Purpose:** Produce the only new headline comparison.

Child plan:
[`PHASE4_STEP6_HELD_OUT_EVALUATION_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP6_HELD_OUT_EVALUATION_IMPLEMENTATION_PLAN.md)
(closed 2026-10-12, **deferred** — no fresh population).

- [x] Confirm the held-out manifest is fresh — **not satisfied**; gate remains
      `held-out-deferred`; contaminated split documented (Step 3 / gate JSON).
- [x] Confirm checkout state — recorded on deferred artifact (`git_commit`,
      `git_worktree_dirty`).
- [ ] Run the frozen A/B/C comparison exactly once — **not run** (data gate).
- [x] Evaluate CLI fail-closed for P4 on `held_out_test.jsonl` and non-ready gate.
- [x] Deferred evidence artifact (not a synthetic held-out replay):
      `artifacts/evaluation/phase4-semantic-validity-held-out-deferred.json`.
- [ ] Full held-out metrics artifact — open until `fresh-held-out-ready`.

**Exit evidence:** Deferred artifact + validation log (evidence § Step 6); headline
held-out JSON remains a future gate-unblock deliverable.

### Step 7 — Score the pre-registered gate

**Purpose:** Decide whether the semantic claim is supported.

- [x] Compare C against A on the declared fresh held-out scoring population
      (implemented in [`semantic_validity_gate.py`](../../src/sscre/semantic_validity_gate.py);
      **not run** — held-out gate `held-out-deferred`).
- [x] Apply the unsafe-reuse/FPR cap (`evaluate_pre_registered_requirements`).
- [x] Apply the abstention ceiling.
- [x] Apply the strict safe-reuse-coverage improvement requirement.
- [x] Report confidence intervals and denominators where the statistics
      contract supports them (Wilson intervals from held-out artifact when present).
- [x] Report unlabeled candidate reuse separately and fail the headline gate
      if it materially affects the comparison (any Strategy C unlabeled hit
      fails closed).
- [x] Record exactly `pass`, `fail`, `unavailable`, or `deferred` according to
      the stopping rules (**`deferred`** — evidence § Step 7).
- [x] If the gate fails, explicitly retain the conservative stack and do not
      authorize Strategy D or unrelated feature expansion as a workaround
      (`conservative_stack_retained` on gate artifact).

**Exit evidence:** Signed-off gate section in the evidence file, including the
decision, metrics, denominators, limitations, and artifact paths.

### Step 8 — Reconcile documentation and roadmap

**Purpose:** Make repository claims match measured reality.

- [x] Update `PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md` with final
      status and all verification results (evidence § Step 8).
- [x] Regenerate stale Phase 3 artifacts only if the protocol explicitly
      requires it; otherwise mark them historical/superseded (not regenerated;
      historical classification retained — evidence § Step 1 / Step 8).
- [x] Update `docs/SSCRE_PLAN.md` §20 checkboxes only for work whose code,
      evidence, and verification are complete (P4-SEMVALID subsection added).
- [x] Update §24 success criteria with measured, limited claims (§24 P4 block).
- [x] Do not mark semantic success based only on provider integration or test
      completion (`semantic_claim_supported: false` on gate artifact).
- [x] Record correctness labels as still open unless actual answer-bearing
      human review occurred (§20 Phase 4 + §24).
- [x] Document the deployment default mismatch if Strategy B remains the
      Compose default (`SSCRE_SEMANTIC_STRATEGY: B` — verification JSON).
- [x] Link the final evidence and artifact manifest from the relevant
      Phase 4/benchmark README files.

**Exit evidence:** Documentation and checkboxes agree with the gate result.

## 11. Verification commands

Before recording any command, confirm every path, marker, and option exists in
the current checkout.

### Baseline and focused checks

- [x] `python -m pytest -q tests/test_benchmark.py tests/test_evaluation_labels.py`
      — **68 passed** (Step 8 close-out).
- [x] `python -m pytest -q tests/test_workstream3_pure_evaluator.py tests/test_workstream3_serialization.py`
      — **65 passed**, 1 warning (Step 8).
- [x] Run the new candidate-attribution test path
      (`tests/test_evaluation_attribution.py`; see evidence Step 2).
- [x] Run the new provider-contract test path
      (`tests/test_local_embedding.py`; evidence § Step 4).
- [x] `python -m pytest -q` — **807 passed**, 15 skipped, 21 deselected, 1 warning
      (2026-10-12 Step 8 close-out; includes gate + held-out tests).

Record pass/fail/skip counts, warnings, Python version, and whether PostgreSQL
or real-provider markers were skipped.

### Benchmark and lineage

- [x] `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production`
      — pass (Step 8).
- [x] Validate the new split manifest and record its full SHA-256.
      (`0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9`).
- [x] Validate dataset version, split counts, record IDs, leakage status, and
      approved source/license metadata (`reviewed-query-pairs-2.0`, 400/215,
      leakage passed — Step 8).

### Compose

- [x] In PowerShell, use the same non-secret sample environment as CI:

```powershell
$env:POSTGRES_PASSWORD = "ci-local-password"
$env:SSCRE_ADMIN_TOKEN = "ci-local-admin-token-123456"
docker compose config
```

Record whether the Compose file defaults Strategy B or C — **B** (`SSCRE_SEMANTIC_STRATEGY: B`).

### Artifact validation

- [x] Validate every new JSON artifact against its schema (comparison reports use
      `attach_evaluation_report_schema`; deferred/gate/manifest JSON are metadata-only).
- [x] Run redaction validation on evaluation and gallery payloads
      (`redact_operational_evaluation_report` on development artifact — Step 8).
- [x] Compare recorded dataset/config/split hashes with the files used (manifest +
      verification JSON; development artifact `config_sha256` frozen at Step 5 replay).
- [x] Confirm no artifact contains credentials, authorization headers, private
      URLs, complete provider transcripts, or unlicensed source text (spot check +
      existing redaction tests).
- [x] Confirm all held-out artifacts have a clean-worktree record or an
      explicit dirty-path explanation (`git_worktree_dirty: true` on P4 artifacts).

### Evaluation execution

- [x] Run the development command recorded in the frozen protocol (Step 5).
- [x] Run the held-out command only after the fresh-held-out gate is `pass`
      (**not run** — gate `held-out-deferred`; CLI fail-closed).
- [x] Confirm held-out configuration is not derived from held-out outcomes
      (`held_out_influence: none` on development artifact).
- [x] Store stdout/stderr or an equivalent machine-readable verification log
      ([`phase4-semantic-validity-verification.json`](../../artifacts/evaluation/phase4-semantic-validity-verification.json)).

## 12. Acceptance criteria

### Goal / Exit — authoring gate

- [x] This implementation plan exists at
      `docs/phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_IMPLEMENTATION_PLAN.md`.
- [x] The plan separates authoring completion from implementation and
      evaluation approval.
- [x] The plan defines a hypothesis, primary comparison, pass/fail rule,
      stopping rules, and evidence outputs.

### Verification — implementation gate

- [x] Candidate-level attribution is implemented and covered by regression
      tests (Step 2 close;
      [`PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md),
      evidence § Step 2).
- [x] Exact-cache FPR is reported with an explicit denominator/unavailable
      rule (Step 5; `false_positive_rate_unavailable_reason` on reports).
- [x] Compatibility, correctness, and preference labels remain separate (Step
      2; attribution uses reviewed `reusable`, not correctness/preference).
- [x] A new protocol/config identity is frozen before threshold selection (Step
      3; `semantic-validity-evaluation-config-1.0`).
- [x] A genuinely fresh held-out population is proven, or the held-out gate
      is explicitly marked unavailable/deferred (`held-out-deferred` at Step 3;
      fresh population not yet constructed).
- [x] A real fixed-dimension embedding provider is selected and validated, or
      the provider gate is explicitly marked unavailable (Step 4;
      `semantic-validity-local-embedding-gate.json` → `available`).
- [x] Development A/B/C evaluation completes without held-out leakage (Step 5
      development artifact).
- [x] One frozen held-out evaluation completes, if authorized and available
      (**deferred** — not authorized; Step 6 evidence).
- [x] Provenance, lineage, redaction, and clean/dirty state validate (Step 8
      manifest + verification).
- [x] The pre-registered C-versus-A gate is scored (**`deferred`**, not pass/fail
      on metrics — Step 7).
- [x] Full pytest, benchmark validation, and Compose validation pass, with
      skips and unavailable checks recorded (verification JSON).
- [x] `docs/SSCRE_PLAN.md` §§20 and 24 match the measured outcome (Step 8).

## 13. Evidence artifact list

Planned paths; create only when the corresponding step produces evidence:

- [x] `docs/phase-4/PHASE4_SEMANTIC_EVALUATION_VALIDITY_EVIDENCE.md` (Step 3
      section added)
- [x] `experiments/semantic-validity-evaluation-config-v1.json`
- [x] `benchmarks/semantic-validity-held-out-gate.json` (`held-out-deferred`;
      `semantic-validity-split-manifest.json` remains for a future fresh
      population)
- [x] `artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json`
      (Step 4 smoke; re-run probe after dependency/model changes)
- [x] `benchmarks/semantic-validity-local-embedding-gate.json` (Step 4)
- [x] `artifacts/evaluation/phase4-semantic-validity-development.json` (Step 5)
- [x] `artifacts/evaluation/phase4-semantic-validity-held-out-deferred.json`
      (Step 6 deferred; not a replay artifact)
- [ ] `artifacts/evaluation/phase4-semantic-validity-held-out.json` (requires
      `fresh-held-out-ready`)
- [x] `artifacts/evaluation/phase4-semantic-validity-gate.json` (Step 7;
      **`deferred`** verdict — no held-out replay)
- [x] `artifacts/evaluation/phase4-semantic-validity-manifest.json`
- [x] `artifacts/evaluation/phase4-semantic-validity-verification.json`

Do not create placeholder “successful” artifacts for unrun conditional work.

## 14. Rollback/deferred paths

- If candidate attribution cannot be made correct without new reviewed
  candidate/query labels, stop at Step 2 and create a label-expansion plan.
- If no fresh held-out population exists, complete only the evaluator and
  development validation; mark the semantic conclusion `unavailable`, not
  `pass`.
- If no approved local embedding model is available, keep the fake provider
  limited to tests and defer the real-embedding gate.
- If real embeddings cause dimension/storage incompatibility, preserve the
  existing provider boundary and create a separate storage/index plan; do not
  silently change vector dimensions in historical artifacts.
- If C fails its gate, retain C's conservative fail-closed behavior, record
  the negative result, and do not build Strategy D, quantization, or unrelated
  infrastructure as a reaction.
- If artifact lineage cannot be reconciled, mark old artifacts historical and
  publish only the new package with complete provenance.
- If any safety, validation, authorization, or error-handling regression
  appears, stop the milestone and revert the affected implementation slice
  before further evaluation.

