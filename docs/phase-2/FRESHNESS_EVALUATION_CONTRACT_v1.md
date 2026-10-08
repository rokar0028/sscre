# Freshness evaluation contract (v1.0)

**Module:** `sscre.freshness_evaluation`
**Schema version:** `freshness-evaluation-1.0`
**Status:** frozen for Workstream 6 Step 2 (Option A scope)

## Purpose

Define machine-readable freshness-policy experiment metadata, policy matrices,
selection records, and metric fields without changing Workstream 1 safety
decisions or benchmark labels.

## Scope (Option A)

- Policy selection and multi-arm comparison run on **development** only.
- Held-out replay, when run, evaluates **stable** reviewed freshness only.
- Held-out **semi_dynamic** and **dynamic** classes are reported as
  `unavailable` with a documented reason (zero reviewed pairs on the current
  split).

## Freshness class reporting

Replay and artifacts must support two independent strata dimensions when
`freshness_class_reporting` is `both`:

| Dimension | Source |
|---|---|
| `reviewed_freshness_class` | benchmark record `freshness_class` |
| `runtime_temporal_class` | `extract_metadata(query).temporal_class` |

Do not infer reviewed labels from runtime classification or vice versa.

## Policy record shape

Each `policy_matrix` entry:

| Field | Type | Rules |
|---|---|---|
| `name` | string | `[a-z][a-z0-9_-]*`, unique in matrix |
| `stable_ttl_seconds` | positive integer | |
| `semi_dynamic_ttl_seconds` | positive integer | |
| `dynamic_ttl_seconds` | positive integer or null | required when `allow_dynamic_entries` is true |
| `allow_dynamic_entries` | boolean | when true, `dynamic_ttl_seconds` must be set |

Policies convert to `CacheControlPolicy` via
`FreshnessPolicySpec.to_cache_control_policy()` or the `Settings` boundary via
`FreshnessPolicySpec.to_settings().cache_control_policy()`.

## Deterministic replay clock (Step 3)

Live requests use wall-clock time. Freshness replay uses `FreshnessReplayClock`
only:

- `FreshnessReplayClock.from_policy_spec(spec, anchor_time)` builds the policy
  and a timezone-aware anchor.
- `evaluate_cache_control(..., now=clock.current_time, policy=clock.policy)`
  is invoked through `FreshnessReplayClock.evaluate_cache_control`.
- Cache inserts during replay set `ttl_expires_at` from
  `ttl_expires_at_for_insert()` at the current comparison time.
- `advance()` moves time forward by a fixed `step` (default one second) after
  each directed benchmark request.

Default anchor for tests and future CLI replay:
`2026-01-01T00:00:00+00:00` (`DEFAULT_REPLAY_ANCHOR_TIME`). Expiration remains
exclusive at `now >= ttl_expires_at`.

Default matrix names: `conservative`, `default`, `dynamic-short`, `long-lived`.

## Selection record

Development-only selection uses constraint-first logic documented in
`freshness_experiment.selection`:

| Field | Meaning |
|---|---|
| `selection_rule` | e.g. `constraint_first_then_maximize_safe_reuse_coverage` |
| `objective` | e.g. `safe_reuse_coverage` |
| `constraints.max_stale_exposure_rate` | cap on served stale exposure |
| `constraints.max_false_positive_rate` | aligns with evaluation config |
| `constraints.max_dynamic_reuse_served_rate` | cap on served dynamic reuse |

`selected_policy` on a report adds:

- `name`, `selection_rule`, `constraints`, `constraint_satisfied`
- optional held-out constraint check fields (Step 9+)

## Stale exposure and freshness violations

These are distinct from blocked expiration.

### Numerators and denominators (Step 6)

| Metric | Numerator | Denominator |
|---|---|---|
| `served_reviewed_stale_exposure_count` | directed requests with `cache_hit=1` and (`safe_reuse_hit=1` or `false_positive=1`) on pairs whose reviewed `failure_category` is `stale_answer` or `temporal_mismatch` | — |
| `served_reviewed_stale_exposure_per_directed_request` | same count | all directed replay requests |
| `served_reviewed_stale_exposure_per_labeled_request` | same count | directed requests whose `pair_id` is stale-labeled |
| `dynamic_reuse_served_count` | directed requests with runtime (or reviewed) `dynamic` class, `cache_hit=1`, and `safe_reuse_hit=1` while policy allows dynamic entries | — |
| `expired_candidate_blocked_count` | cache-control evaluations with outcome `expired` | candidate evaluations (protection, **not** stale exposure) |
| `dynamic_reuse_blocked_count` | cache-control evaluations with outcome `dynamic_entries_disabled` | candidate evaluations |

Reviewed labels come from benchmark `failure_category` only; runtime
`temporal_class` is not substituted for stale labeling.

| Metric | Meaning |
|---|---|
| `stale_exposure_count` / `stale_exposure_rate` | alias of served reviewed stale exposure (per directed request) |
| `freshness_violation_count` / `freshness_violation_rate` | alias bucket for benchmark-observable freshness failures |
| `dynamic_reuse_served_count` | served safe reuse when dynamic entries were allowed |

Artifacts include `stale_exposure_accounting` (overall policy) and
`stale_exposure_accounting_by_policy` with Wilson/bootstrap intervals on
proportion fields.

Answer-level stale exposure remains **unavailable** when
`answer_availability` is `none` for all benchmark pairs (`answer_level_stale_exposure.status`).

## Cache-control outcome counts

Optional `cache_control_outcome_counts` object with non-negative integer counts
for: `fresh`, `expired`, `dynamic_entries_disabled`, `missing_expiration`,
`invalid_expiration`.

## Report sections (Step 4+)

```text
metrics_overall
metrics_by_policy
metrics_by_reviewed_freshness_class
metrics_by_runtime_temporal_class
metrics_by_cache_control_outcome
storage_by_policy
storage_overall
reuse_vs_storage_points
selected_policy
invalidation
limitations
```

## Storage pairing (Step 8)

Each policy arm includes a `storage_by_policy` record aligned to the same
`dataset_version`, `config_version`, and TTL values used during replay.
`measurement_environment` is always `synthetic_storage_simulation` for these
rows.

| Field | Meaning |
|---|---|
| `entries` / `total_bytes` | Footprint after replay, before physical cleanup |
| `lazy_expired_rejection_count` | Expired outcomes on the read path (entries may remain) |
| `physical_expiration_cleanup_count` | Rows removed by post-replay `cleanup_expired` |
| `eviction_count` | Evictions during replay inserts |

`reuse_vs_storage_points` maps each evaluated arm to the WS5
`reuse_vs_storage` plane using the paired footprint and replay
`safe_reuse_coverage`.

## Configuration

Nested under `experiments/evaluation_config.json` → `freshness_experiment`.
Validated by `apply_freshness_experiment_config_defaults()` when evaluation
config is loaded.

## Replay orchestration (Step 4)

Development replay runs every `policy_matrix` entry via
`run_freshness_policy_replay()` using the development-selected compatibility
threshold. Each arm gets a fresh in-memory cache and a new
`FreshnessReplayClock` anchored at `DEFAULT_REPLAY_ANCHOR_TIME`.

Held-out replay runs one `--selected-policy` only after development selection
is frozen. Option A marks held-out semi-dynamic and dynamic claims unavailable.

Development replay writes `selected_policy` and `policy_selection` using
constraint-first logic from `freshness_policy_selection`. Held-out replay
requires `--selected-policy` pointing at the development artifact JSON (or a
matching frozen selection); it records `held_out_constraint_satisfied` on the
selected policy without re-running development selection.

CLI: `python -m sscre.freshness_evaluate`.

## Artifact package (Step 10)

Final JSON reports include `freshness_artifact_metadata` with
`regeneration_commands`, `config_sha256`, schema version pointers, companion
paths, and `unavailable_fields_summary`. Development runs emit
`artifacts/evaluation/workstream6-invalidation.json` as a sidecar when using
the standard development output path (or `--invalidation-output`).

## Attachment and redaction

1. Build the `freshness_experiment` object on the report.
2. Call `attach_freshness_evaluation_schema()` (or `attach_evaluation_report_schema()`).
3. Apply `redact_operational_evaluation_report()` — freshness blocks are
   numeric/categorical only; no raw query or answer text.

Top-level field added when present:

- `freshness_evaluation_schema_version`: `freshness-evaluation-1.0`

## Invalidation

`invalidation_scope: repository_boundary_only` means explicit invalidation is
tested via repository `delete_by_query_hash`, not a public API. TTL
`cleanup_expired` is **not** invalidation.

### Repository capabilities (Step 7)

| Repository | `delete_by_query_hash` | Notes |
|---|---|---|
| `InMemoryExactCache` | yes | Removes entry, access metadata, and orphaned canonical answers |
| `PostgreSQLCacheRepository` | yes | SQL `DELETE` on `cache_entries`; prunes unreferenced canonical rows |

The freshness artifact `invalidation` block records a controlled sequence:

1. insert and verify fresh cache-control eligibility;
2. verify exact and semantic retrieval include the entry;
3. measure `invalidation_latency_ms` for `delete_by_query_hash`;
4. verify exact lookup empty and semantic retrieval excludes the hash;
5. insert replacement entry and verify regeneration.

`measurement_environment` is `synthetic_repository` for the in-memory probe.
PostgreSQL integration is documented with `postgresql_integration.status:
not_run` unless a supported integration test executes.

Fields must not include raw query or answer text (hashes and counts only).
