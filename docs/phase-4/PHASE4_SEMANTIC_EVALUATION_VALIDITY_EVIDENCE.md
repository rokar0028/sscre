# Phase 4 — Semantic evaluation validity evidence (`P4-SEMVALID`)

## Status

**Status:** `in progress` — Steps 1–5 closed in repo; Steps 6–8 not started
(2026-10-12).

**Snapshot:** 2026-10-12 (execution on branch `phase4/setup`).

**Child plans:**
[`PHASE4_STEP1_EVALUATION_AUDIT_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP1_EVALUATION_AUDIT_IMPLEMENTATION_PLAN.md)
(Step 1, closed);
[`PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md)
(Step 2, closed);
[`PHASE4_STEP3_PROTOCOL_RESET_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP3_PROTOCOL_RESET_IMPLEMENTATION_PLAN.md)
(Step 3, closed);
[`PHASE4_STEP4_LOCAL_EMBEDDING_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP4_LOCAL_EMBEDDING_IMPLEMENTATION_PLAN.md)
(Step 4, closed);
[`PHASE4_STEP5_DEVELOPMENT_EVALUATION_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP5_DEVELOPMENT_EVALUATION_IMPLEMENTATION_PLAN.md)
(Step 5, closed).

## Repository context

| Item | Value |
| --- | --- |
| `git rev-parse HEAD` | `b7eda9dd45823aaf98eb00897301a31145162627` (`b7eda9d`) |
| Branch | `phase4/setup` (matches parent expected `b7eda9d` at audit time) |
| Worktree dirty | yes at Step 1 audit time (docs/rules/review markdown) |
| `src/` at Step 1 close | unchanged by the read-only audit; Step 2 later modified `baseline.py`, `evaluation_statistics.py`, and added `evaluation_attribution.py` |
| Package import | `$env:PYTHONPATH='src'` (no `pip install` required for commands below) |

## Gate B — corpus and CLI confirmation

- [x] **Audit corpus + artifact inventory scope:** 31/31 paths from the Step 1
      verification one-liner present on disk; extended docs
      `sscre_full_review_2026-10-12_v2.md`, `docs/SSCRE_PLAN.md`, and parent
      plan present.
- [x] **`benchmark_validate` CLI:** `--phase2` and `--production` defined in
      `src/sscre/benchmark_validate.py`.
- [x] **Pytest markers:** `real_provider`, `ws8_postgres_failure_recovery`,
      `ws8_postgres_multiprocess`, `ws8_postgres_contention`, `ws8_postgres_load`
      in `pyproject.toml`; default `addopts` deselects all four `ws8_postgres_*`
      markers.

## Current split manifest (`benchmark_validate`)

Command (repo root, `PYTHONPATH=src`):

```text
python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production
```

Result: **pass**

```text
dataset_version=reviewed-query-pairs-2.0
schema_version=1.1
annotation_guide_version=1.0.0
split_counts=development:400 held_out:215 source:615
leakage_status=passed
frozen_at=2026-10-08T15:28:12+00:00
split_manifest_sha256=0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9
benchmark validation passed (cross_split_fingerprint_overlaps=0)
```

**Historical manifest (Phase 3 lineage):**
`68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51` — classify
as `historical-stale`; do not treat as eligibility for a new C-versus-A claim.

**Canonical evaluation config SHA-256** (from
`scripts/phase2_remediation_inventory.py`):
`5734f113b827675785d610d97702ed95b7021fe83e35714a9a9de7df057b30d8`
(`experiments/evaluation_config.json`, `evaluation-config-1.0`).

## Documentation gap resolution — label contract path

Parent § 4 and § 8 previously stated
`benchmarks/EVALUATION_LABEL_CONTRACT_v1.md` was missing. **Resolved at audit:**
the file exists at `benchmarks/EVALUATION_LABEL_CONTRACT_v1.md` and is cited from
`src/sscre/evaluation_labels.py`. Parent § 4 was updated at Step 1 close to
link the live path.

## Code inspection — Step 1 historical snapshot (pre–Step 2)

The following describes the codebase **at Step 1 close**. Step 2 replaced
request-record reuse scoring with candidate attribution; see **Step 2** below
for current behavior. Do not use this section alone to describe today’s
`baseline.py`.

### Replay bookkeeping (`src/sscre/baseline.py`)

- **Strategy A (`run_exact_cache_baseline`):** For each benchmark record, replays
  `a_to_b` and `b_to_a` with `pair_id=record.id`, `direction`, `cache_hit`
  (0/1), `generated`, and per-hit `false_positive` / `safe_reuse_hit` from
  `reuse_outcome_indicators(..., reusable=record.reusable, served_reuse=True)`.
- **Strategy B/C:** Same `pair_id` / `direction` / `cache_hit` pattern;
  embedding paths attach `embedding_model` / `embedding_dimension` on reports.
- **Strategy A (`run_no_cache_baseline`):** Records samples with `cache_hit=0`,
  `false_positive=0`, `safe_reuse_hit=0`.

### Reuse scoring (`src/sscre/evaluation_statistics.py`)

`reuse_outcome_indicators` (lines 1081–1092) scores **request-record**
`reusable` against `served_reuse` on `b_to_a` only — not served-candidate
provenance. This is pre-attribution behavior documented for Step 2.

### Evaluate CLI (`src/sscre/evaluate.py`)

`_build_parser`: `--baseline` (required; `no-cache` | `exact-cache` |
`embedding-cache` | `compatibility-cache` | `all`), `--split` (default
`development`; held-out must be explicit), `--config`, `--output`,
`--production`, `--no-statistics`, plus adaptive/freshness options.

### Label separation (`src/sscre/evaluation_labels.py`)

Module docstring and validators keep compatibility, correctness, and preference
separate per `benchmarks/EVALUATION_LABEL_CONTRACT_v1.md` and
`docs/phase-2/SAFETY_EVALUATION_CONTRACT_v1.md`.

### Exact-cache FPR behavior

- **Code:** `ExactCacheReport` has no aggregate `false_positive_rate` field;
  per-request `false_positive` is set on cache hits via `reuse_outcome_indicators`.
- **Payload:** `experiments/exact_cache_development.json` omits
  `false_positive_rate` (legacy single-baseline report).
- **Held-out comparison artifacts:** nested `exact-cache` baseline shows
  `false_positive_rate: null` while B/C report numeric FPR; per-sample
  `false_positive` exists inside request samples when present.

### Default embedding identity (`src/sscre/embedding.py`)

`FakeEmbeddingClient` default: `model_name="fake-embedding"`, `dimension=8`.

### Compose deployment default (`docker-compose.yml`)

`SSCRE_SEMANTIC_STRATEGY: ${SSCRE_SEMANTIC_STRATEGY:-B}` — default Strategy B;
recorded as deployment safety gap; file unchanged in this audit.

## Phase 2 inventory supplement

```text
python scripts/phase2_remediation_inventory.py
```

Exit 0; current-manifest rows on `0aca5b8d…` for WS5/WS6/WS7/WS9 artifacts
(see script stdout in verification log). Does not cover the Phase 3 comparison
package inventoried below.

## Artifact inventory (Step 1 starting snapshot)

On-disk JSON under `artifacts/` and `experiments/` was **not** regenerated after
Step 2. Eligibility reasons that cite request-record scoring still describe
those **frozen files**; new evaluation runs use attributed reuse (Step 2).

Notes:

- **Cost fields:** comparison nested baselines use `estimated_cost_usd=0.0`
  (synthetic/zero replay). Adaptive singles record `0.0`.
- **Lineage:** `current-manifest` only when `split_manifest_sha256` is solely
  `0aca5b8d…`; `historical-stale` when `68912e3b…` appears anywhere in file.
- **New-comparison eligibility:** expected **zero** `eligible-new-comparison`
  rows (fake embeddings, used held-out, request-record scoring, and/or stale
  manifest).

| Path | Present | git_commit | dirty | config | dataset | split | split_manifest_sha256 | baselines | embedding | cost | tokens | lineage | new comparison |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `artifacts/evaluation/phase3-final-held-out-comparison.json` | yes | `fe68ce3…` | false | `5734f113…` / v1.0 | nested 2.0 | held-out | `68912e3b…` (provenance) | A/B/C/exact | B/C: fake-embedding d=8 | synthetic 0 | nested | historical-stale | ineligible — stale manifest, used held-out, fake-embedding, request-record scoring |
| `artifacts/evaluation/phase3-development-comparison.json` | yes | `8c65926…` | true | v1.0 | unrecorded top | development | `68912e3b…` | four baselines | fake-embedding in B/C | synthetic 0 | unrecorded top | historical-stale | ineligible — stale manifest, fake-embedding, request-record scoring |
| `artifacts/evaluation/workstream5-held-out-comparison.json` | yes | `2f7aa5e…` | true | `5734f113…` / v1.0 | nested 2.0 | held-out | `0aca5b8d…` | four baselines | B/C fake d=8 | synthetic 0 | nested | current-manifest | ineligible — used held-out, fake-embedding, request-record scoring |
| `artifacts/evaluation/workstream5-development-sweep.json` | yes | `2f7aa5e…` | true | `5734f113…` / v1.0 | 2.0 | development | `0aca5b8d…` | 3 reports | fake in reports | synthetic 0 | nested | current-manifest | ineligible — fake-embedding, request-record scoring |
| `artifacts/evaluation/phase3-development-threshold-sweep.json` | yes | `8c65926…` | true | v1.0 | 2.0 | development | `68912e3b…` | 3 reports | fake | synthetic 0 | nested | historical-stale | ineligible — stale manifest, fake-embedding, request-record scoring |
| `artifacts/evaluation/phase3-adaptive-held-out.json` | yes | `8c65926…` | true | v1.0 | 2.0 | held-out | `68912e3b…` | n/a (single) | fake-embedding d=8 | 0.0 | 3121 | historical-stale | ineligible — stale manifest, used held-out, fake-embedding, request-record scoring |
| `artifacts/evaluation/phase3-adaptive-development.json` | yes | `8c65926…` | true | v1.0 | 2.0 | development | `68912e3b…` | n/a | fake d=8 | 0.0 | 5763 | historical-stale | ineligible — stale manifest, fake-embedding, request-record scoring |
| `artifacts/evaluation/phase3-results-preview.json` | yes | unrecorded | unrecorded | unrecorded | unrecorded | unrecorded | unrecorded | n/a | unrecorded | unrecorded | unrecorded | unrecorded | ineligible — index/preview only; no headline metrics |
| `artifacts/evaluation/phase3-paper-artifact-manifest.json` | yes | unrecorded | unrecorded | v1.0 | null top | unrecorded | unrecorded | n/a | unrecorded | unrecorded | unrecorded | unrecorded | ineligible — manifest pointer only |
| `artifacts/evaluation/phase4-paper-artifact-manifest.json` | yes | `dc451fe…` | true | unrecorded | 2.0 | unrecorded | cites `68912e3b…` | n/a | unrecorded | unrecorded | unrecorded | historical-stale | ineligible — references stale manifest artifacts |
| `artifacts/evaluation/phase4-selected-stack-pareto.json` | yes | `8c65926…` | true | v1.0 | 2.0 | held-out | `68912e3b…` | n/a | unrecorded | unrecorded | unrecorded | historical-stale | ineligible — stale manifest, used held-out |
| `artifacts/evaluation/phase3-embedding-storage-baseline.json` | yes | `e3363cf…` | true | `5734f113…` | 2.0 | unrecorded | unrecorded (`development_sha256` only) | n/a | fake-embedding | unrecorded | unrecorded | unrecorded | ineligible — fake-embedding, storage slice not headline A/B/C |
| `experiments/evaluation_config.json` | yes | unrecorded | unrecorded | v1.0 | 2.0 | unrecorded | unrecorded | n/a | n/a | n/a | n/a | unrecorded | ineligible — config only |
| `experiments/exact_cache_development.json` | yes | `98263ea…` | unrecorded | v1.0 | **1.0** (legacy) | unrecorded | unrecorded | exact-cache only | n/a | 0.0 measured | 187 | unrecorded | ineligible — legacy dataset 1.0, no FPR field |
| `experiments/milestone10_evaluation_development_report.json` | yes | `aa251a2…` | true | v1.0 | unrecorded | development | unrecorded | four baselines | fake in B/C | synthetic 0 | unrecorded | unrecorded | ineligible — fake-embedding, request-record scoring |
| `experiments/milestone10_evaluation_held_out_report.json` | yes | `aa251a2…` | true | v1.0 | unrecorded | held-out | unrecorded | four baselines | fake in B/C | synthetic 0 | unrecorded | unrecorded | ineligible — used held-out, fake-embedding |

### Held-out headline metrics (historical reference only)

From `phase3-final-held-out-comparison.json` nested baselines on **stale**
manifest `68912e3b…` (not eligible for new claim):

| Baseline | hit_rate (approx) | safe_reuse | FPR | embedding |
| --- | --- | --- | --- | --- |
| exact-cache | 0.0535 | 1 safe | `null` aggregate | n/a |
| embedding-cache | 0.0628 | 2 safe / 13 unsafe | 0.4815 | fake-embedding d=8 |
| compatibility-cache | 0.0023 | 1 safe | 0.0 | fake-embedding d=8 |

`workstream5-held-out-comparison.json` (`0aca5b8d…`) reports the same B/C FPR
pattern with current manifest; still **ineligible** for a new semantic headline.

## Eligible vs ineligible for new C-versus-A headline

| Eligibility | Count | Reason |
| --- | --- | --- |
| `eligible-new-comparison` | **0** | No artifact combines fresh held-out population, real fixed-dimension embeddings, candidate-level scoring, and current protocol identity |
| `ineligible-new-comparison` | **16** | See inventory column; dominant blockers: `fake-embedding`, already-used 215-record held-out, `68912e3b…` lineage, request-record `reusable` scoring |

**Explicit:** Current-manifest Phase 2/WS5 regenerations on `0aca5b8d…` are
**not** the new semantic baseline.

## Verification commands

| Command | Result |
| --- | --- |
| Path existence one-liner (Step 1 plan) | `listed 31 missing 0` |
| `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production` | pass (output above) |
| `python scripts/phase2_remediation_inventory.py` | exit 0 |
| `python -m pytest -q tests/test_benchmark.py tests/test_evaluation_labels.py tests/test_workstream3_pure_evaluator.py tests/test_workstream3_serialization.py tests/test_evaluation_statistics.py tests/test_baseline_request_samples.py` | **155 passed**, 1 deprecation warning |
| `docker compose config` (CI sample env) | available — compose v5.5.1, config rendered (first lines include `name: major`) |

No held-out or development `python -m sscre.evaluate` runs in this step.

## Step 2 — Candidate-level attribution (2026-10-12)

**Child plan:**
[`PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP2_CANDIDATE_ATTRIBUTION_IMPLEMENTATION_PLAN.md).

### Implementation

- [`src/sscre/evaluation_attribution.py`](../../src/sscre/evaluation_attribution.py):
  `ServedCandidateProvenance`, `DirectedPairReuseIndex`, and
  `attribute_served_reuse_outcome` (reviewed directed `(query_a → query_b)`
  edges; ambiguous edges → unlabeled).
- [`src/sscre/baseline.py`](../../src/sscre/baseline.py): exact / embedding /
  compatibility replay scores `b_to_a` served reuse from the served candidate
  relation and attaches `served_candidate_provenance` when attribution returns
  provenance (`a_to_b` hits do not score reuse outcomes).
- [`src/sscre/evaluation_statistics.py`](../../src/sscre/evaluation_statistics.py):
  `unlabeled_candidate_reuse` on `RequestObservationSample`; headline
  `false_positive_rate` in sample statistics uses labeled hits only.
- **Exact-cache report:** `unsafe_reuse_hits`, `unlabeled_candidate_reuse_hits`,
  `false_positive_rate` (labeled denominator).

### Metrics and compatibility notes

- **Headline FPR denominator:** report and sample statistics use labeled
  `b_to_a` reuse (`safe_reuse_hits + unsafe_reuse_hits`), not all cache hits.
  Sample statistics also expose `false_positive_rate_among_all_hits` for
  comparison with frozen Phase 2/3 artifacts.
- **Ground truth:** attribution uses the reviewed directed pair edge and the
  pair’s `reusable` flag, not Strategy C runtime decisions or
  `compatibility_label` alone.
- **Zero labeled hits:** reports emit `false_positive_rate=null` and
  `false_positive_rate_unavailable_reason=no_labeled_reuse_hits`; threshold and
  policy constraints treat unknown FPR as ineligible (`math.inf`), not as 0.0.
- **Legacy `request_samples`:** statistics treat a missing
  `unlabeled_candidate_reuse` field as `0` so frozen JSON can be re-summarized.

### Fixture demonstration

`tests/test_evaluation_attribution.py::test_embedding_false_positive_follows_served_candidate_not_request_label`
shows `pair-0002` `b_to_a` scored unsafe when the served candidate is
`gamma query` (reviewed incompatible edge), not from the evaluation record’s
misleading request label alone.

### Verification

Commands (`PYTHONPATH=src`, repo root):

| Command | Result |
| --- | --- |
| `python -m pytest -q tests/test_evaluation_attribution.py tests/test_evaluation_statistics.py::test_summarize_request_samples_without_unlabeled_field_defaults_to_zero` | **8 passed** (7 attribution + 1 legacy statistics) |
| `python -m pytest -q tests/test_compatibility.py tests/test_workstream3_pure_evaluator.py tests/test_evaluation_labels.py tests/test_baseline_request_samples.py tests/test_benchmark.py` | **131 passed** (fail-closed / label-separation bundle) |
| `python -m pytest -q` | **775 passed**, 15 skipped, 21 deselected, 1 warning |

**Failure-path traceability (parent Step 2):** Strategy C fail-closed behavior
is unchanged in `compatibility.py`; replay abstention/UNCERTAIN coverage
includes
`tests/test_benchmark.py::test_compatibility_baseline_reports_safety_and_abstention_metrics`
and `tests/test_compatibility.py` UNCERTAIN cases (within the 131-test bundle).

**Parent milestone rows (intentionally still open):** parent §11
`python -m pytest -q` and §12 full-suite / Compose / `benchmark_validate`
checkboxes stay unchecked until Phase 4 close-out even though the full suite
passed at Step 2 re-verify.

Re-verified 2026-10-12 (Step 2 doc review; commands above re-run in chat).

## Step 3 — Protocol reset (2026-10-12)

**Child plan:**
[`PHASE4_STEP3_PROTOCOL_RESET_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP3_PROTOCOL_RESET_IMPLEMENTATION_PLAN.md).

### Frozen protocol identity

| Item | Value |
| --- | --- |
| Config path | [`experiments/semantic-validity-evaluation-config-v1.json`](../../experiments/semantic-validity-evaluation-config-v1.json) |
| `config_version` | `semantic-validity-evaluation-config-1.0` |
| Config SHA-256 | `cf23807941a639af751d02c250d22ab676e83a37a3dc373c9a17fc8846f51ac4` |
| Supersedes (unchanged) | `experiments/evaluation_config.json` (`evaluation-config-1.0`, SHA-256 `5734f113…`) |
| Development split manifest | `0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9` |

Frozen operating parameters: embedding thresholds `[0.8, 0.9, 0.95]`, `top_k`
5, `max_false_positive_rate` 0.0, `max_abstention_rate` 0.5 (Strategy C
headline gate), Wilson/bootstrap statistics aligned with Phase 2 config,
threshold tie-break matching `select_embedding_threshold` in
[`baseline.py`](../../src/sscre/baseline.py).

### Held-out manifest decision

| Item | Value |
| --- | --- |
| Gate record | [`benchmarks/semantic-validity-held-out-gate.json`](../../benchmarks/semantic-validity-held-out-gate.json) |
| **Status** | **`held-out-deferred`** |
| Fresh manifest | none (`semantic-validity-split-manifest.json` not created) |
| Existing `held_out_test` | 215 records — classified `contaminated_for_headline_gate` (Phase 3 final, WS5, adaptive held-out artifacts) |

The pre-registered C-versus-A headline gate **cannot run** until a fresh
held-out population is constructed and the gate status moves to
`fresh-held-out-ready`. Relabeling the current 215-record split as fresh is
**forbidden**.

### Context-stripped identical-text pairs

**Policy:** `context_required` — retain all 27 pairs in the benchmark; exclude
their pair IDs from the **primary headline population**; report metrics for them
in a separate stratum in Step 5+ artifacts.

Identification: identical normalized `query_a`/`query_b` with CacheEval
anaphoric / insufficient-evidence labeling (e.g. `pair-0036` "incorrect"/
"incorrect"). Counts: 17 development, 10 `held_out_test` (full ID list in
config JSON).

### Metric denominators (headline)

Documented in config § `metric_denominators`: hit rate over all directed
requests in the primary population; reuse outcomes on `b_to_a` served hits;
FPR over labeled reuse (`safe + unsafe`, excluding `unlabeled_candidate_reuse`);
abstention on Strategy C only. Zero labeled reuse FPR emits an unavailable reason
in replay reports and comparison `operating_point` statistics (Step 5).

### Step 3 remediation (protocol load + population filter)

- Removed invalid `freshness_experiment.scope` from the frozen config; headline
  runs omit that block (use `evaluation-config-1.0` for freshness experiments).
- `sscre.evaluate` applies `context_required` exclusions after split validation
  via [`evaluation_protocol.py`](../../src/sscre/evaluation_protocol.py);
  artifact metadata includes `primary_headline_population` when pairs are
  dropped.
- Threshold tie-break fallback text aligned with `select_embedding_threshold`
  (higher threshold on final tie).

### Legacy data classification

| Data / artifact class | Authorized use under P4 protocol |
| --- | --- |
| `benchmarks/development.jsonl` | Threshold selection and development A/B/C (Step 5+) |
| `benchmarks/held_out_test.jsonl` | Debug/historical replay only until fresh gate |
| `68912e3b…` manifest lineage | Historical-stale |
| `fake-embedding` B/C artifacts | Tests and historical comparison only |

### Verification

| Command | Result |
| --- | --- |
| Protocol JSON assert one-liner (Step 3 child plan) | `protocol_files_ok` |
| `python -m pytest -q tests/test_evaluation_protocol.py` | **3 passed** (config load + population filter) |
| `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production` | pass (`split_manifest_sha256=0aca5b8d…`, leakage passed) |

No `python -m sscre.evaluate` development or held-out runs in Step 3.

## Step 4 — Local embedding provider (2026-10-12)

**Child plan:**
[`PHASE4_STEP4_LOCAL_EMBEDDING_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP4_LOCAL_EMBEDDING_IMPLEMENTATION_PLAN.md).

### Environment probe

| Check | Result |
| --- | --- |
| `torch` | installed |
| `sentence-transformers` | installed in dev env (`pip install '.[local-embeddings]'` / optional extra) |
| Registered model | `sentence-transformers/all-MiniLM-L6-v2` |
| Dimension | 384 |
| License | Apache-2.0 |

Gate:
[`benchmarks/semantic-validity-local-embedding-gate.json`](../../benchmarks/semantic-validity-local-embedding-gate.json)
→ **`available`**.

### Implementation

- [`local_embedding.py`](../../src/sscre/local_embedding.py):
  `LocalSentenceTransformerEmbeddingClient`, `probe_local_embedding_environment`,
  `create_local_embedding_client_from_mapping`, smoke helpers.
- Frozen config block `local_embedding_provider` in
  `experiments/semantic-validity-evaluation-config-v1.json`.
- `FakeEmbeddingClient` unchanged for synthetic replay/tests.

### Smoke artifact (non-secret)

[`artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json`](../../artifacts/evaluation/phase4-semantic-validity-local-embedding-smoke.json)

- `status`: `pass`
- `latency_ms`: 75 (CPU smoke)
- `vector_fingerprint_sha256` only (no raw query text or full vector)

Regenerate:

```powershell
$env:PYTHONPATH = "src"
python -m sscre.local_embedding_probe
```

### Verification

| Command | Result |
| --- | --- |
| `python -m pytest -q tests/test_local_embedding.py -m "not local_embedding"` | **11 passed**, 1 deselected |
| `python -m sscre.local_embedding_probe` | `status=pass` |

Opt-in live load: `python -m pytest -q tests/test_local_embedding.py -m local_embedding`.

## Step 5 — Development A/B/C evaluation (2026-10-12)

**Child plan:**
[`PHASE4_STEP5_DEVELOPMENT_EVALUATION_IMPLEMENTATION_PLAN.md`](./PHASE4_STEP5_DEVELOPMENT_EVALUATION_IMPLEMENTATION_PLAN.md).  
**Threshold decision:**
[`PHASE4_STEP5_THRESHOLD_DECISION.md`](./PHASE4_STEP5_THRESHOLD_DECISION.md).

### Command

```powershell
$env:PYTHONPATH = "src"
python -m sscre.evaluate `
  --benchmark benchmarks/development.jsonl `
  --config experiments/semantic-validity-evaluation-config-v1.json `
  --baseline all `
  --split development `
  --production `
  --output artifacts/evaluation/phase4-semantic-validity-development.json
```

Result: exit **0**, ~386s wall time (CPU local embeddings).

### Artifact header

| Field | Value |
| --- | --- |
| Path | [`artifacts/evaluation/phase4-semantic-validity-development.json`](../../artifacts/evaluation/phase4-semantic-validity-development.json) |
| `measurement_environment` | `local_embedding_replay` |
| `config_version` | `semantic-validity-evaluation-config-1.0` |
| `config_sha256` | `cf23807941a639af751d02c250d22ab676e83a37a3dc373c9a17fc8846f51ac4` |
| `git_commit` | `b7eda9dd45823aaf98eb00897301a31145162627` |
| `git_worktree_dirty` | true |
| `held_out_influence` | `none` |
| `primary_headline_population` | 383 records (17 `context_required` excluded) |

### Threshold selection

- `threshold_decision.selected_threshold`: **0.9**
- `threshold_selection.constraint_satisfied`: **false** (no grid point met FPR ≤ 0.0 on
  labeled embedding-cache reuse)
- Selection split: development only (see threshold decision doc)

### Code changes (Step 5)

- [`evaluate.py`](../../src/sscre/evaluate.py): local embedding client for B/C;
  provenance metadata; P4 CLI guards; attribution summary.
- [`evaluation_attribution.py`](../../src/sscre/evaluation_attribution.py):
  `false_positive_rate_unavailable_reason` when no labeled reuse.
- [`baseline.py`](../../src/sscre/baseline.py): report fields `labeled_reuse_hits`,
  nullable `false_positive_rate` (optional fields at end of embedding/compatibility reports).
- [`freshness_policy_selection.py`](../../src/sscre/freshness_policy_selection.py):
  skip `max_false_positive_rate` when replay metrics omit labeled FPR (`null`).
- [`baseline.py`](../../src/sscre/baseline.py) adaptive domain selection: vacuous
  when every threshold report has `no_labeled_reuse_hits`; **embedding** threshold
  sweep remains fail-closed (unknown FPR ineligible).

### Verification

| Command | Result |
| --- | --- |
| Development evaluate command above | exit 0, artifact written |
| `python -m pytest -q tests/test_evaluation_attribution.py tests/test_evaluation_protocol.py tests/test_evaluate_statistics_attachment.py` | **15 passed** |
| `python -m pytest -q` (2026-10-12, fail-closed FPR rectification) | **794 passed**, 15 skipped |

## Out of scope (unchanged)

Parent Steps 6–8, fresh held-out headline gate, `docker-compose.yml` edits.
