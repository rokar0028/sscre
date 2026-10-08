# Workstream 6 Evidence

Status: **Mostly complete (2026-10-09, Option A).** Freshness policy replay,
artifacts, regression tests, and parent-plan handoff are recorded below.
Residual: sparse semi/dynamic development pairs, WS5 artifact merge not
implemented, WS5 held-out manifest drift (Step 1).

Plan: [`WORKSTREAM_6_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_6_IMPLEMENTATION_PLAN.md).

## Step 1 — Audit of freshness behavior and benchmark coverage

Environment: Python 3.14.5, git `1beed4d`, working tree dirty (uncommitted
benchmark and artifact changes).

### Verification

| Command | Result |
|---|---|
| `python -m sscre.benchmark_validate --benchmark-dir benchmarks --phase2 --production` | passed; `reviewed-query-pairs-2.0`, 400 / 215 / 615, leakage passed |
| `python -m pytest -q tests/test_cache_controls.py tests/test_cache_ttl_integration.py tests/test_workstream3_freshness.py tests/test_cache_control_traces.py` | 31 passed |
| `python -m pytest -q tests/test_cache_eviction.py tests/test_storage_evaluation.py tests/test_evaluate_statistics_attachment.py` | 14 passed |

Full suite was not run: Step 1 changes no code.

### Benchmark freshness coverage (reviewed `freshness_class`)

| Split | stable | semi_dynamic | dynamic | Total |
|---|---:|---:|---:|---:|
| development | 391 | 5 | 4 | 400 |
| held-out | 215 | **0** | **0** | 215 |
| source | 606 | 5 | 4 | 615 |

- Development semi-dynamic: 1 reusable, 4 non-reusable. Dynamic: 4 non-reusable.
  No dynamic pair is labeled reusable.
- Reviewed stale/temporal rows (`stale_answer`, `temporal_mismatch`,
  `temporal_freshness`) are all in development: `pair-0025`, `0026`, `0030`,
  `0031`, `0413`, `0612`, `0613`. Held-out has none.
- `answer_availability` is `none` for all 615 records; no answer-level
  correctness labels exist, so answer-level stale exposure is **unavailable**.
- The Phase 2 coverage gate (`PHASE2_REVIEWED_COVERAGE`) requires only ≥1 record
  per freshness class over the whole dataset, not per split.

### Runtime classifier versus reviewed label

Baseline replay classifies each query with `extract_metadata().temporal_class`;
it does not use the reviewed `freshness_class`. Query-level disagreement:

- development: 31 of 800 queries (e.g. 15 reviewed-stable queries classified
  `dynamic`);
- held-out: 3 of 430 queries (`pair-0136`, `pair-0580`), all reviewed `stable`
  but classified `dynamic`.

Consequence: replay strata and policy behavior are driven by the runtime
classifier; reviewed class counts above do not predict them.

### Current TTL and cache-control behavior

- Defaults (`CacheControlPolicy`, `Settings`): stable 30 days, semi-dynamic
  24 hours, dynamic `None`, `allow_dynamic_entries=False`.
- Enabling dynamic entries requires a positive dynamic TTL
  (`CacheControlPolicy.__post_init__`).
- Evaluation order (`evaluate_cache_control`): dynamic-policy check, TTL
  policy check, missing expiration, naive-timezone expiration, `now >=
  expires_at` → expired, else fresh.
- Legacy baseline replay without `freshness_replay_clock` still uses default
  `CacheControlPolicy()` and wall-clock expiration. Workstream 6 replay passes
  `FreshnessReplayClock` via `run_compatibility_cache_baseline(...,
  freshness_replay_clock=)` (Step 3+). `evaluation_config.json` includes
  `freshness_experiment` (`evaluation-config-1.0`).

### Trace outcome mapping

Source: `cache_control_traces.py`.

| `cache_control_outcome` | Decision | Trace `reason` |
|---|---|---|
| `fresh` | continues to compatibility | compatibility reason |
| `expired` | `UNSAFE` | `cache_control_expired` |
| `dynamic_entries_disabled` | `UNSAFE` | `cache_control_dynamic_disabled` |
| `missing_expiration` | `UNCERTAIN` | `cache_control_missing_expiration` |
| `invalid_expiration` | `UNCERTAIN` | `cache_control_invalid_expiration` |

Blocked traces use stage `retrieval`, carry `freshness_class`, and none can
produce a cache hit. Covered by `tests/test_workstream3_freshness.py` and
`tests/test_cache_ttl_integration.py`.

### Invalidation support

- `delete_by_query_hash` exists on `InMemoryExactCache` and `PostgresCache`
  (also removes orphaned canonical answers).
- Its only caller is `app.py` replacing an expired exact entry. No test calls
  it directly.
- `cleanup_expired` (TTL physical deletion) exists on both repositories and is
  tested (`test_cache_eviction.py`, `test_postgres_integration.py`;
  PostgreSQL skipped without `SSCRE_DATABASE_URL`).
- Public routes are only `/health`, `/ready`, `/v1/cache/stats`,
  `/v1/query`. No invalidation endpoint exists, and none is in scope.
- Conclusion: explicit invalidation can be tested at the repository boundary
  only (Step 7); TTL cleanup must not be reported as invalidation.

### Reusable Workstream 5 fields

`statistics.by_baseline.<baseline>.strata.by_freshness_class.<class>` provides
`sample_count`, `proportions`, `distributions`, `interval_methods`, seed, and
confidence level, via `evaluation-statistics-1.0`. `request_samples` already
carry `freshness_class`. Storage points come from `storage_evaluation.py`
(`total_bytes`, `entries`, `eviction_count`); `StorageWorkloadItem.ttl_seconds` is a
per-item value defaulting to 3600; per-class TTL storage arms need work in
Step 8.

## Findings that block or reshape later steps

1. **Held-out has no semi-dynamic or dynamic examples.** Held-out freshness
   conclusions for those classes are not possible on the current split.
   Policy selection would have only 9 development pairs for those classes,
   so interval-backed claims there are weak.
2. **`workstream5-held-out-comparison.json` is stale against the current
   split.** It records split manifest SHA `69c90c41…` and `frozen_at`
   `2026-10-08T14:46:39+00:00`, with freshness strata of dynamic 6 /
   semi-dynamic 4 / stable 420 requests and held-out IDs such as `pair-0030`,
   `0031`, `0413`, `0612`, `0613`. The checked-in `split_manifest.json`
   (SHA `c0109b36…`, frozen `2026-10-08T15:28:12+00:00`) moved those IDs to
   development. The WS5 held-out and Pareto artifacts, and the WS5
   "final" claim, should be regenerated or annotated before WS6 relies on
   them. (Split files are uncommitted modifications in the working tree.)
3. **Replay cannot vary policy or time.** Step 3 must add a policy parameter
   and clock boundary to replay without altering runtime defaults.
4. **Runtime classifier disagrees with reviewed labels** (above). Step 2 must
   decide which source defines a "freshness class" for policy reporting, and
   report both.
5. **No answer-level labels.** Stale exposure is limited to runtime
   freshness-protection counts plus reviewed `reusable=false`
   stale/temporal rows served by replay; answer-level exposure is
   unavailable.
6. **No real-provider run.** Latency and cost remain synthetic replay.

## Scope decision (Option A — frozen 2026-10-08)

- [x] **Development-only** policy matrix and selection on `development.jsonl`.
- [x] Held-out **stable** only; `semi_dynamic` and `dynamic` marked
  `unavailable` in `freshness_experiment.held_out_freshness_scope`.
- [x] Report **both** reviewed `freshness_class` and runtime temporal class
  (`freshness_class_reporting: both`).
- [ ] Regenerate or annotate stale WS5 held-out artifacts (split manifest
  mismatch; not blocking Step 2 schema).

## Step 2 — Freshness schema and policy config

- [x] Contract:
  [`FRESHNESS_EVALUATION_CONTRACT_v1.md`](./FRESHNESS_EVALUATION_CONTRACT_v1.md).
- [x] Module: `src/sscre/freshness_evaluation.py`
  (`freshness-evaluation-1.0`).
- [x] Config: `experiments/evaluation_config.json` → `freshness_experiment`
  (four policy arms, Option A held-out scope, selection constraints).
- [x] Load path: `apply_freshness_experiment_config_defaults()` from
  `evaluate._load_config`.
- [x] Attachment: `attach_freshness_evaluation_schema()` via
  `attach_evaluation_report_schema()`; redaction preserves numeric freshness
  blocks.
- [x] Tests: `tests/test_workstream6_freshness.py` → 8 passed (2026-10-08).

## Step 3 — Deterministic policy and replay clock

- [x] `FreshnessReplayClock` + `build_replay_clocks_for_matrix` (anchor
  `2026-01-01T00:00:00+00:00`, configurable step).
- [x] Policies via `to_cache_control_policy()` and `to_settings()`.
- [x] `run_compatibility_cache_baseline(..., freshness_replay_clock=)` uses
  injected time for cache control and policy-based insert TTLs.
- [x] Tests: 13 passed in `tests/test_workstream6_freshness.py` (2026-10-08).

## Step 4 — Freshness policy replay

- [x] `freshness_replay.run_freshness_policy_replay()` — isolated arm per policy,
  no-cache reference, `metrics_by_policy`.
- [x] CLI: `python -m sscre.freshness_evaluate --benchmark ... --split
  development --output ...`
- [x] Held-out requires `--selected-policy` (Option A stable-only scope).
- [x] Tests: 16 passed in `tests/test_workstream6_freshness.py` (2026-10-08).

## Step 5 — Freshness metrics and stratified summaries

- [x] `src/sscre/freshness_metrics.py` — point metrics, `statistics_by_policy`
  (WS5 bootstrap/Wilson), `metrics_overall` (default policy on development),
  reviewed/runtime class strata, cache-control outcome rates (candidate unit).
- [x] `runtime_temporal_class` on compatibility replay request samples.
- [x] `invalidation` stub (`not_evaluated`); storage marked unavailable until
  Step 8 pairing.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 18 passed
  (2026-10-08).
- [x] WS5/WS3 regression bundle → 23 passed (2026-10-08).

## Step 6 — Stale-exposure accounting

- [x] `src/sscre/freshness_stale_exposure.py` — numerators/denominators,
  protection vs served counts, Wilson intervals, answer-level unavailable flag.
- [x] Contract updated in `FRESHNESS_EVALUATION_CONTRACT_v1.md`.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 24 passed
  (2026-10-08).

## Step 7 — Explicit invalidation

- [x] `src/sscre/freshness_invalidation.py` — insert/reuse/delete/regenerate
  sequence, latency, storage snapshots, semantic exclusion check.
- [x] PostgreSQL documented, `postgresql_integration.status: not_run`.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 27 passed
  (2026-10-08).

## Step 8 — Storage pairing

- [x] `src/sscre/freshness_storage.py`; replay `policy_storage_snapshot` with
  lazy vs physical cleanup distinction.
- [x] Artifact fields: `storage_by_policy`, `storage_overall`,
  `reuse_vs_storage_points` (`synthetic_storage_simulation`).
- [x] `python -m pytest -q tests/test_workstream6_freshness.py
  tests/test_storage_evaluation.py` → 33 passed (2026-10-08).

## Step 9 — Policy selection and held-out freeze

- [x] `src/sscre/freshness_policy_selection.py` — constraint-first selection,
  `load_frozen_development_selection`, held-out constraint check.
- [x] CLI `--selected-policy` accepts development artifact JSON path.
- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 32 passed
  (2026-10-08).

## Step 10 — Evaluation artifacts

- [x] `src/sscre/freshness_artifacts.py` — package validation, regeneration
  commands, `config_sha256`, unavailable-field summary, invalidation sidecar.
- [x] Artifacts:
  `artifacts/evaluation/workstream6-development-freshness.json`,
  `workstream6-held-out-freshness.json`, `workstream6-invalidation.json`.
- [x] Regeneration (2026-10-08):

  ```powershell
  python -m sscre.freshness_evaluate --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --split development --output artifacts/evaluation/workstream6-development-freshness.json
  python -m sscre.freshness_evaluate --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --split held-out --production --selected-policy artifacts/evaluation/workstream6-development-freshness.json --output artifacts/evaluation/workstream6-held-out-freshness.json
  ```

- [x] `python -m pytest -q tests/test_workstream6_freshness.py` → 33 passed
  (2026-10-08).

## Step 11 — Regression, serialization, and safety tests

- [x] `tests/test_workstream6_freshness.py` — policy construction and TTL
  boundaries (stable/semi-dynamic/dynamic), default dynamic block,
  `dynamic-short` TTL edge, expired entries, reviewed-class replay breakdown,
  short-vs-long matrix arm isolation, stale-exposure and invalidation coverage
  (prior steps), artifact redaction rejection and checked-in artifact guard.
- [x] Workstream 3 freshness regression included in focused command below.
- [x] `python -m pytest -q tests/test_cache_controls.py
  tests/test_cache_ttl_integration.py tests/test_workstream3_freshness.py
  tests/test_workstream6_freshness.py` → 73 passed (2026-10-08).
- [x] `python -m pytest -q` → 648 passed, 14 skipped (PostgreSQL/provider
  integrations skipped when unavailable) (2026-10-08).

## Step 12 — Completion record and Phase 2 handoff

Environment: Python 3.14.x, git `88997ed1d7463c90fb57a2beee39b2b0a78f4b7c`
(artifact `git_worktree_dirty: true` at generation time).

### Schema and config versions

| Item | Version / location |
|---|---|
| Freshness evaluation schema | `freshness-evaluation-1.0` |
| Stale-exposure accounting | `1.0` (`STALE_EXPOSURE_ACCOUNTING_VERSION`) |
| Evaluation config | `evaluation-config-1.0` (`experiments/evaluation_config.json`) |
| Dataset | `reviewed-query-pairs-2.0` |
| Contract | [`FRESHNESS_EVALUATION_CONTRACT_v1.md`](./FRESHNESS_EVALUATION_CONTRACT_v1.md) |
| Statistics attachment | `evaluation-statistics-1.0` (Workstream 5 bootstrap/Wilson) |

### Implementation paths

| Responsibility | Module / artifact |
|---|---|
| Policy schema and replay clock | `src/sscre/freshness_evaluation.py` |
| Policy replay orchestration | `src/sscre/freshness_replay.py` |
| Metrics and strata | `src/sscre/freshness_metrics.py` |
| Stale-exposure accounting | `src/sscre/freshness_stale_exposure.py` |
| Invalidation sequence | `src/sscre/freshness_invalidation.py` |
| Storage pairing | `src/sscre/freshness_storage.py` |
| Development selection / held-out freeze | `src/sscre/freshness_policy_selection.py` |
| Artifact packaging | `src/sscre/freshness_artifacts.py` |
| CLI | `src/sscre/freshness_evaluate.py` |
| Baseline hook | `src/sscre/baseline.py` (`freshness_replay_clock`) |
| Tests | `tests/test_workstream6_freshness.py` (45 tests) |

### Benchmark and split counts (reviewed `freshness_class`)

Same as Step 1 audit: development 391 / 5 / 4 (400 total); held-out 215 /
0 / 0 (215 total); source 606 / 5 / 4 (615 total). Held-out **Option A**
evaluates **stable reviewed class only**; semi-dynamic and dynamic are
`unavailable` in `held_out_freshness_scope`.

### Policy matrix (development replay)

Four arms from `freshness_experiment.policy_matrix`:

| Name | stable TTL | semi-dynamic TTL | dynamic TTL | allow dynamic |
|---|---:|---:|---:|---|
| conservative | 3600 s | 600 s | — | no |
| default | 2 592 000 s (30 d) | 86 400 s (24 h) | — | no |
| dynamic-short | 30 d | 24 h | 300 s | yes |
| long-lived | 7 776 000 s (90 d) | 604 800 s (7 d) | — | no |

### Selected policy (development → held-out)

- **Selection rule:** `constraint_first_then_maximize_safe_reuse_coverage`
- **Objective:** `safe_reuse_coverage`
- **Constraints:** `max_stale_exposure_rate`, `max_false_positive_rate`, and
  `max_dynamic_reuse_served_rate` all **0.0**
- **Development selected policy:** `conservative` (`constraint_satisfied: true`)
- **Held-out:** same frozen policy; `held_out_constraint_satisfied: true`
  (`workstream6-held-out-freshness.json`)

No held-out labels or outcomes were used to tune TTL values; held-out replay
requires the frozen development artifact via `--selected-policy`.

### Commands and artifact paths

Development:

```powershell
python -m sscre.freshness_evaluate `
  --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json `
  --split development `
  --output artifacts/evaluation/workstream6-development-freshness.json
```

Held-out (after development selection):

```powershell
python -m sscre.freshness_evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --split held-out `
  --production `
  --selected-policy artifacts/evaluation/workstream6-development-freshness.json `
  --output artifacts/evaluation/workstream6-held-out-freshness.json
```

Artifacts:

- `artifacts/evaluation/workstream6-development-freshness.json`
- `artifacts/evaluation/workstream6-held-out-freshness.json`
- `artifacts/evaluation/workstream6-invalidation.json` (sidecar; TTL cleanup
  not reported as invalidation)

### Stale-exposure definition and intervals

- **Served reviewed stale exposure:** directed replay request with
  `cache_hit == 1` on a pair whose reviewed `failure_category` is
  `stale_answer` or `temporal_mismatch`, and `safe_reuse_hit` or
  `false_positive` indicates reuse was served (`freshness_stale_exposure.py`).
- **Not stale exposure:** blocked expiration, missing/invalid expiration,
  dynamic disabled, and ordinary incompatible misses.
- **Answer-level stale exposure:** `unavailable` (`answer_availability_none`).
- **Intervals:** Wilson/bootstrap via Workstream 5 `StatisticsConfig`
  (`bootstrap_seed` from evaluation config); recorded under
  `stale_exposure_accounting.intervals` per policy.

Development artifact (conservative policy arm): served reviewed stale exposure
**0** on 12 stale-labeled directed requests; protection counts separate expired
and policy blocks.

### Invalidation

- **Status:** `evaluated` at in-memory repository boundary
  (`delete_by_query_hash`, explicit sequence, `ttl_expiration_used: false`).
- **PostgreSQL:** `postgresql_integration.status: not_run` (documented).
- **Public invalidation API:** none (out of scope).

### Storage pairing

- **Environment:** `synthetic_storage_simulation` on replay (`storage_by_policy`,
  `reuse_vs_storage_points`).
- Lazy expired rejection vs physical cleanup distinguished in
  `policy_storage_snapshot`.

### Verification (Step 12 re-check)

| Command | Result (2026-10-09) |
|---|---|
| `python -m pytest -q tests/test_workstream6_freshness.py` | 45 passed |
| `python -m pytest -q` (Step 11 baseline) | 648 passed, 14 skipped |

Skipped integrations (typical): PostgreSQL integration tests without
`SSCRE_DATABASE_URL`, live provider measure/integration tests without
credentials.

### Limitations affecting Phase 2 claims

1. **Sparse semi-dynamic/dynamic on development** (5 and 4 pairs); class-specific
   intervals are weak; held-out has **zero** semi-dynamic/dynamic pairs.
2. **Runtime `extract_metadata` temporal class ≠ reviewed `freshness_class`**
   on many queries; replay behavior follows runtime class; both are reported
   (`freshness_class_reporting: both`).
3. **Synthetic replay only** for latency, cost, tokens, and storage (`measurement_environment` labels).
4. **No real-provider freshness run**; do not conflate with Workstream 4 live
   measurements.
5. **WS5 held-out comparison artifact** may predate the latest split manifest
   SHA; refresh WS5 artifacts before merging freshness into a single dashboard
   narrative (see Step 1 findings).

### Parent plan link

Linked from [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md)
(Workstream 6 acceptance criteria and execution order).

### Post-review fixes (2026-10-09)

- [x] Held-out artifact `regeneration_commands` use `benchmarks/development.jsonl`
  for the development step (`freshness_artifacts.py`).
- [x] Held-out replay validates frozen `config_version`, `dataset_version`, and
  policy matrix entry (`freshness_policy_selection.py`, `freshness_replay.py`).
- [x] WS5 `evaluate --baseline all` adds `freshness_policy_companion_artifacts`
  reference block when `freshness_experiment` is configured (`evaluate.py`).
