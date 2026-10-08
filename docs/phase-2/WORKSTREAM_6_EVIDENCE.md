# Workstream 6 Evidence

Status: **Step 1 audit complete (2026-10-08).** Steps 2–12 are open. This file
records baseline facts only; no freshness-policy experiment has been run.

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
- Baseline replay (`baseline.py`) hard-codes `CacheControlPolicy()` and
  uses wall-clock `datetime.now` inside `evaluate_cache_control`; there is no
  policy parameter and no clock injection. `evaluation_config.json`
  (`evaluation-config-1.0`) has no freshness keys.

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

## Decisions needed before Step 2

- [ ] Rebalance the split (or add reviewed semi-dynamic and dynamic pairs to
  both splits) so held-out has freshness coverage; this changes the frozen
  benchmark and needs explicit approval and a new dataset version.
- [ ] Or accept a development-only freshness experiment and label held-out as
  stable-only/unavailable for other classes.
- [ ] Regenerate or annotate the stale WS5 held-out artifacts.
