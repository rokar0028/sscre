# Phase 3 Workstream 6 Implementation Plan

## Goal

Execute [Feature 8 — Simulated load ladder](./PHASE3_PLAN.md#feature-8--simulated-load-ladder-1k100k-qday)
(`P3-FEAT-LOAD`): 1K → 10K → 100K simulated Q/day on Strategy C, then name
the first reproducible bottleneck or record `not_reached`.

Two gates. Do not treat them as one “workstream complete” verdict.

**Gate A — Plan authoring.** This document. It locks the harness delta, the
artifact fields, and the stop rule. No ladder run in this gate.

**Gate B — Feature 8 execution.** Steps 1–6 closed. Memory and PostgreSQL
ladder artifacts are `status: complete`. A missing `SSCRE_DATABASE_URL` does
not block the in-memory arm.

**Status:** Step 6 closed (2026-10-11). Evidence filled. Memory and PostgreSQL
`first_bottleneck` are `not_reached` (`reproducibility` `agree`).  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 6.  
**Card:** [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 8.  
**Evidence:** [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md).

**Not** Phase 2 freshness experiments
([`../phase-2/WORKSTREAM_6_IMPLEMENTATION_PLAN.md`](../phase-2/WORKSTREAM_6_IMPLEMENTATION_PLAN.md)).
**Not** the milestone 10 or Phase 2 WS8 32-request load protocols.

## Scope

### Included (Gate B)

- One workload config: `experiments/phase3_load_ladder_v1.json`
- Ladder runner in `src/sscre/load_test.py` (do not add a load-test framework)
- In-memory artifact: `artifacts/operations/phase3-load-ladder-memory.json`
- PostgreSQL artifact: `artifacts/operations/phase3-load-ladder-postgres.json`
  with `status: unavailable` when `SSCRE_DATABASE_URL` is unset
- Evidence filled from those artifacts

### Excluded

- Held-out replay, held-out tuning, or a protocol reset
- Changing `RequestMetrics` or `QueryResponse`
- Changing `run()`, `_stop_reason`, or `classify_first_bottleneck` results for
  `experiments/milestone10_load_v1.json` and
  `experiments/workstream8_pg_load_v1.json`
- Milestone 10 failure fixtures inside the ladder mix
- The Feature 1 adaptive τ map on this HTTP path
- Optimization, extra hosts, a pool exporter, or a new dependency after the
  bottleneck (or `not_reached`) is recorded
- Treating the Phase 4 32-request profile or `ws8-pg-load-v1` as this result

## Learning objectives

- [ ] Map simulated Q/day to a fixed local request count and a recorded
      compression factor.
- [ ] Keep intentional fixture failures out of the ladder error rate.
- [ ] Stop at the first reproducible bottleneck and leave the code unchanged
      afterward.

## Source of truth

| Item | Value |
| --- | --- |
| Dataset | `reviewed-query-pairs-2.0` |
| Query pool | `benchmarks/development.jsonl` via `load_benchmark_jsonl` (`src/sscre/benchmark.py`) |
| Pool rows | unique normalized `query_a` and `query_b`, file order, `a` then `b` |
| Held-out | not used |
| Protocol id | `phase3-load-ladder-v1` |
| Mode | `compatibility` only (Strategy C) |
| Threshold arm | `global_0.95` (`similarity_threshold` **0.95**) |
| Seed | **20261011** (`random.Random`) |
| Repeat ratio | **0.30** configured; record the realized measured-window ratio |
| Caps | `max_cache_entries` **10000**, `max_cache_bytes` **100000000** (`Settings` defaults in `src/sscre/config.py`) |
| Process count | **1** |
| Hash helper | `file_sha256` in `src/sscre/benchmark_splits.py` |
| In-memory p95 budget | ≤ **500** ms end-to-end |
| PostgreSQL p95 budget | ≤ **3000** ms end-to-end |
| Error budget (both) | `non_fixture_error_rate` ≤ **0.01** |
| Timeout budget (both) | `timeout_rate` ≤ **0.01** |
| Not a substitute | `experiments/milestone10_load_v1.json`, `experiments/workstream8_pg_load_v1.json` |

`/v1/query` builds metadata with `extract_metadata` (`src/sscre/query.py`).
That is not benchmark `metadata.domain`, and `Settings` holds one threshold.
This ladder uses global τ **0.95**. It does not load
`artifacts/evaluation/phase3-adaptive-threshold-map.json`.

## Current baseline

`src/sscre/load_test.py` already runs a bounded in-process load through
`TestClient` and `ThreadPoolExecutor`:

- `run()` walks cache modes, then a cold pass and an optional warm pass.
- `_stop_reason` stops at error rate **0.10**, timeout rate **0.05**, or
  p99 > **5×** p50. Those are the milestone 10 / WS8 rules. They are not
  Feature 8 budgets.
- Component data on the response is `llm_latency_ms` and a derived wrapper.
  `classify_first_bottleneck` leaves repository, embedding, and live-provider
  spans unavailable on purpose.
- Milestone 10 and WS8 configs are a static `items` list with `request_count`
  **32**. Their default modes include `no_cache`, `exact_cache`,
  `embedding_only`, and `compatibility`.
- Step 1 added `experiments/phase3_load_ladder_v1.json` (`compatibility` only,
  L1/L2/L3 counts, Feature 8 budgets).
- Step 2 added `run_ladder()`. `main` dispatches `protocol_id`
  `phase3-load-ladder-v1` to it and leaves `run()` on the old path. The
  ladder artifact omits per-request rows.
- Step 3 wrote `artifacts/operations/phase3-load-ladder-memory.json`
  (`status: complete`). Executed steps: L1, L2, L3 (`run_index` 1), and L3
  (`run_index` 2). Every step has `cap_compliant: true`. Artifact fields:
  `first_bottleneck` `not_reached`, `reproducibility` `agree`,
  `bottleneck_step` null.
- Step 4 first wrote `artifacts/operations/phase3-load-ladder-postgres.json`
  as `unavailable` when `SSCRE_DATABASE_URL` was unset. A later rerun with
  URL from `.env` produced `status: complete` (L1, L2, L3 run 1, L3 run 2;
  every step `cap_compliant: true`; `first_bottleneck` `not_reached`,
  `reproducibility` `agree`; PostgreSQL 16.15).
- Step 5 read `first_bottleneck` from each `status: complete` artifact.
  Memory and PostgreSQL each record `not_reached` with `reproducibility`
  `agree` and no L1–L3 budget breach.
  No component was chosen by hand. Cache, timeout, and deployment settings
  were not changed.
- Step 6 filled [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) § Step 6
  with the close fields, the fake-provider limit, and the
  `synthetic_replay` label. No cache, timeout, or deployment setting was
  changed.
- Each `run()` pass still stores every request in `results`.
- `LoadTestEmbeddingClient` and `LoadTestLLMClient` already sit on the
  injected boundary. `RequestMetrics` has `embedding_latency_ms` and
  `llm_latency_ms` only. Compatibility evaluation stays inside `app.py`.

Gate B added a separate `run_ladder()` path. It does not change WS8 reports.

## Ladder

Warmup is **10%** of the measured count, minimum **20**. Each step is its
own sequence from seed **20261011** (not a prefix of a longer day). One
measured pass after warmup. No extra cold pass.

| Step | Simulated Q/day | Measured requests | Warmup | Concurrency |
| --- | ---: | ---: | ---: | ---: |
| L1 | 1,000 | 200 | 20 | 4 |
| L2 | 10,000 | 2,000 | 200 | 4 |
| L3 | 100,000 | 20,000 | 2,000 | 8 |

Simulated rate for the evidence note: `simulated_q_per_day / 86400`.
`compression_factor = requests_per_second / simulated_qps`. Record both.
Neither is a budget.

Sampling, per step, length = warmup + measured requests:

1. If the index is 0, or `rng.random() >= 0.30`, take the next pool query,
   cycling.
2. Otherwise copy an earlier index (`rng.randrange(index)`).

Labels are `development_unique` and `development_repeat`. The realized ratio
is repeat labels in the **measured** window divided by measured requests.
Record it. Do not redraw to force 0.30.

PostgreSQL passes set `isolate_queries` and the existing `ws8:` prefix so
leftover rows are not candidates. Apply the prefix after the sequence is
built. Memory passes do not prefix. The logical mix is the sequence; the
prefix is hygiene and must be named in the artifact.

## Component timers

Time the injected objects with `threading.local` storage. One request runs
on one pool thread, so a thread-local last-call duration cannot collide.
Do not add fields to `RequestMetrics`.

| Component | Timer | In the share |
| --- | --- | --- |
| `embed` | wall clock inside `LoadTestEmbeddingClient.embed` | yes |
| `vector_search` | wall clock of repository `search_by_embedding` | yes |
| `repository` | wall clock of `get_by_query_hash`, `insert_and_evict`, and `record_hit` | yes |
| `generation` | wall clock inside `LoadTestLLMClient.generate` | yes |
| `wrapper_other` | `max(0, end_to_end_ms − embed − vector_search − repository − generation)` for that request | yes |
| `compatibility_check` | no separate callable on the injected clients | **unavailable** |

End-to-end is the existing harness clock in `_request` (`perf_counter`
around `POST /v1/query`), not `metrics.total_latency_ms`. Provider-reported
`embedding_latency_ms` and `llm_latency_ms` stay on the response and are
often 0 for these fakes. Do not use them as the component p95.

`wrapper_other` still contains compatibility work, TestClient overhead, and
anything the wrappers do not cover. If it wins, the name is `wrapper_other`.
Do not rename it to compatibility or repository.

Share for a measured component = its p95 / the sum of measured-component
p95 values. Unavailable components stay out of the denominator. If that sum
is 0, shares are undefined.

Tie-break, high to low: `embed`, `vector_search`, `repository`,
`generation`, `wrapper_other`.

## Bottleneck rule

Score a step against the budgets in the config (the card values above):

- `p95_end_to_end_latency_ms`
- `non_fixture_error_rate`
- `timeout_rate`

`non_fixture_error_rate` = HTTP status ≥ 400 among requests whose label is
not `embedding_failure` or `generation_failure`, divided by the count of
those non-fixture requests. This pool has no fixture labels. If a fixture
label appears, it is neither an error nor part of the denominator. A step
with zero non-fixture requests is invalid and is not a pass.

`timeout_rate` = measured requests whose error reason contains `timed out`,
divided by measured requests. A timeout may also be an error. That double
count is accepted.

The first breached step is the lowest of L1, L2, L3 that misses any of those
three budgets. The bottleneck is the measured component with the largest p95
share on that step. If shares are undefined, the name is `unattributed`, not
a guessed component.

Cap check is separate. `cap_compliant` is true only when
`storage.bytes ≤ max_cache_bytes` and `entries ≤ max_cache_entries`. A cap
miss stops the ladder and fails the protocol. It does not create a component
name.

Reproducibility, per backend:

1. Walk L1, then L2, then L3. Stop at the first breach.
2. Repeat that step once. The same component name on both runs is
   `first_bottleneck`. Do not run higher steps.
3. If the two runs disagree, set `first_bottleneck` to null and
   `reproducibility` to `disagree`. Do not run a third time. That outcome
   is not a protocol pass.
4. If L1–L3 all stay inside the budgets, repeat L3 once. Both clean →
   `not_reached`. A second L3 that breaches, or a different name, is
   `disagree`, not `not_reached`.

Memory and PostgreSQL each have their own stop. A memory bottleneck still
allows the PostgreSQL arm.

Do not call `_stop_reason` on this path.

## Artifact

One JSON object per backend. Omit per-request `results` and the query list.
The sequence is a function of seed, pool, repeat ratio, warmup, and
request count; tests lock a short prefix instead of storing 20,000 rows.

| Field | Rule |
| --- | --- |
| `report_type` | `phase3_load_ladder` |
| `protocol_id` | `phase3-load-ladder-v1` |
| `status` | `complete` or `unavailable` |
| `dataset_version` | `reviewed-query-pairs-2.0` |
| `split` | `development` |
| `development_sha256` | `file_sha256` of `benchmarks/development.jsonl` |
| `config_sha256` | `file_sha256` of the config file |
| `git_commit`, `git_worktree_dirty` | same facts as the load-test git helper |
| `measurement_environment` | `synthetic_replay` |
| `threshold_arm` | `global_0.95` |
| `similarity_threshold` | `0.95` |
| `seed`, `repeat_ratio` | `20261011`, `0.30` |
| `pool_size` | unique queries actually loaded |
| `cache_mode` | `compatibility` |
| `cache_policy` | the two caps |
| `repository` | `memory` or `postgres` |
| `unavailable_reason` | set when `status` is `unavailable`; else null |
| `steps` | one object per step that ran, in order |
| `first_bottleneck` | component name, `not_reached`, or null when `disagree` / `unattributed` / unavailable |
| `bottleneck_step` | `L1`, `L2`, `L3`, or null |
| `reproducibility` | `agree` or `disagree` |
| `limitation` | local synthetic replay; not a production SLA |

Each step object:

| Field | Rule |
| --- | --- |
| `step_id` | `L1` / `L2` / `L3` |
| `simulated_q_per_day`, `simulated_qps` | from the table; qps = per-day / 86400 |
| `request_count`, `warmup_requests`, `concurrency`, `process_count` | from the table; process count **1** |
| `elapsed_seconds`, `requests_per_second`, `compression_factor` | measured window only |
| `realized_repeat_ratio` | measured window |
| `p50_latency_ms`, `p95_end_to_end_latency_ms`, `p99_latency_ms` | harness end-to-end |
| `error_count`, `non_fixture_error_rate`, `timeout_count`, `timeout_rate` | definitions above |
| `entries`, `total_bytes`, `eviction_count` | `storage_stats()` after the measured window |
| `cap_compliant` | both caps |
| `isolate_queries` | false for memory, true for postgres |
| `component_p95_ms`, `component_p95_share` | measured components only |
| `unavailable_components` | includes `compatibility_check` |
| `budget_breached` | which budget failed, or null |
| `run_index` | `1` or `2` |

`connection_measurement` is `not_instrumented`. Record `postgresql_version`
from the existing helper when the postgres arm runs. Do not add a pool metric.

When the URL is missing, the postgres file still has `report_type`,
`protocol_id`, `status: unavailable`, `unavailable_reason`, `repository`,
and `measurement_environment`. It has no step results and no bottleneck claim.

## Prerequisites

- [x] Feature 8 card in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) (budgets, ladder,
      stopping rule).
- [x] This step plan written (Gate A).
- [x] Pre-code checklist for the Step 1 slice recorded in
      [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) (2026-10-11).
- [x] User approved Step 6 in writing. Steps 1–6 were approved in chat on
      2026-10-11.

## Gate B — Feature 8

### Step 1 — Workload config

- [x] Add `experiments/phase3_load_ladder_v1.json` with `protocol_id`
      `phase3-load-ladder-v1`, the source-of-truth table, the step table, and
      both backend budgets.
- [x] Set `modes` to `["compatibility"]` and `repository` to `memory`.
- [x] Do not copy milestone 10 `items`, caps (`8` / `10000`), or failure queries.
      The file has no `items` key. Caps are `10000` / `100000000`.
- [x] Test in `tests/test_load_test.py`: the file’s counts, warmup, concurrency,
      repeat ratio, seed, threshold, caps, and budgets equal the card.
      `test_phase3_load_ladder_config_matches_feature_8_card`. Evidence:
      [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) § Step 1.

### Step 2 — Harness

- [x] Add `run_ladder()`. Dispatch from `main` when `protocol_id` is
      `phase3-load-ladder-v1`. Leave `run()` on the old path.
- [x] Build the pool with `load_benchmark_jsonl`. Build each step sequence
      with the sampling rules above. `load_ladder_pool`, `build_ladder_sequence`.
- [x] Add the timers and the repository proxy in `load_test.py` only.
      `TimingHub`, `_TimedRepository`.
- [x] Score Feature 8 budgets. Do not call `_stop_reason`.
- [x] Apply the two-run stop rule. Strip `results` and query text from the
      written artifact.
- [x] `--repository` overrides the config repository. Postgres with no
      `SSCRE_DATABASE_URL` writes `status: unavailable` and returns exit 0.
- [x] Tests in `tests/test_load_test.py` (no L3, no 20,000 requests):
      - same seed rebuilds the same short sequence and the same realized ratio
      - `non_fixture_error_rate` ignores `embedding_failure` and
        `generation_failure`
      - a synthetic over-budget step selects the largest p95 share
      - an under-budget step is `not_reached`
      - `compatibility_check` cannot win
      - a p95 tie follows the documented order
      - a zero share sum yields `unattributed`
      - disagreeing repeats yield `reproducibility: disagree` and do not
        continue
      - bytes or entries over the cap clear `cap_compliant` and stop the ladder
      - missing postgres URL writes `unavailable` and does not raise
      - existing WS8 and milestone 10 tests still match their old reports
      Evidence: [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) § Step 2.

### Step 3 — In-memory ladder

- [x] Run L1 → L2 → L3, plus the one confirmation repeat the stop rule requires.
      Executed: L1, L2, L3 run 1, L3 run 2. Command and result:
      [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) § Step 3 (2026-10-11).
- [x] Write `artifacts/operations/phase3-load-ladder-memory.json`.
- [x] Confirm every executed step has `cap_compliant: true`.
      L1, L2, L3 run 1, and L3 run 2. Entries ≤ 706, `total_bytes` 181649.

```powershell
$env:PYTHONPATH='src'
python -m sscre.load_test --config experiments/phase3_load_ladder_v1.json --output artifacts/operations/phase3-load-ladder-memory.json
```

### Step 4 — PostgreSQL ladder

- [x] With `SSCRE_DATABASE_URL` set, run the same config and
      `--repository postgres` to
      `artifacts/operations/phase3-load-ladder-postgres.json`.
      Rerun with URL from `.env` (2026-10-11). Evidence:
      [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) § Step 4.
- [x] If the URL is unset, write that path with `status: unavailable` and the
      reason. Do not start a database for this step unless the user asked.
      `unavailable_reason` is `SSCRE_DATABASE_URL is not set`. No database
      was started. Evidence:
      [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) § Step 4.

```powershell
$env:PYTHONPATH='src'
python -m sscre.load_test --config experiments/phase3_load_ladder_v1.json --repository postgres --output artifacts/operations/phase3-load-ladder-postgres.json
```

### Step 5 — Bottleneck

- [x] Read `first_bottleneck` from each artifact that has `status: complete`.
      Memory and PostgreSQL each read `not_reached`.
      Evidence: [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) § Step 5
      (2026-10-11).
- [x] Record `not_reached` only when `reproducibility` is `agree` and no
      budget breached through L3.
      Memory: `agree`. L1, L2, L3 run 1, and L3 run 2 all have
      `budget_breached` null. Recorded result: `not_reached` on L1–L3.
- [x] On `disagree` or `unattributed`, leave the protocol short of pass and
      do not pick a component by hand.
      N/A on 2026-10-11: memory is `not_reached` / `agree`, not `disagree` or
      `unattributed`. `wrapper_other` was not named as the bottleneck.
- [x] Do not change cache, timeout, or deployment settings after the result.
      No such settings were changed on 2026-10-11.

### Step 6 — Evidence

- [x] Fill [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) with the
      commands, git commit, config hash, development hash, seed, environment
      (OS, CPU, Python, PostgreSQL version or unavailable, process count,
      per-step concurrency), budgets, compression factors, cap result, and
      `first_bottleneck` or `not_reached`.
      § Step 6 (2026-10-11). PostgreSQL 16.15 on the postgres artifact.
- [x] State the fake-provider limit: embed and generation times are local
      wrapper times, and `compatibility_check` was not split out.
- [x] Label the result `synthetic_replay`. Do not call it a capacity or SLA
      figure.

## Verification

These paths exist today: `src/sscre/load_test.py`, `tests/test_load_test.py`,
`experiments/milestone10_load_v1.json`, `experiments/workstream8_pg_load_v1.json`.

After Step 2, before any 20,000-request run:

```powershell
$env:PYTHONPATH='src'
python -m pytest -q tests/test_load_test.py
```

After any substantive code change, run the full suite and record pass, fail,
or skip:

```powershell
python -m pytest -q
```

Do not mark the full suite complete if it was not run. Unit tests must not
execute L2 or L3. PostgreSQL integration stays skipped when the URL is unset;
record that skip separately from a failed budget.

After Step 6 close (2026-10-11): `python -m pytest -q tests/test_load_test.py`
→ **18 passed**, 1 warning. After the PostgreSQL ladder rerun:
`python -m pytest -q` → **780 passed**, 1 skipped, 21 deselected, 1 warning.

## Acceptance criteria

- [x] Card with ladder, budgets, and stopping rule in `PHASE3_PLAN.md`.
- [x] In-memory ladder recorded:
      `artifacts/operations/phase3-load-ladder-memory.json` (2026-10-11).
- [x] PostgreSQL ladder recorded, or `status: unavailable` with a reason:
      `artifacts/operations/phase3-load-ladder-postgres.json` (2026-10-11).
      `status: complete` after URL rerun.
- [x] `first_bottleneck` named from component p95 share, or `not_reached`
      with the L1–L3 range and `reproducibility: agree`.
      Memory and PostgreSQL L1–L3: `not_reached`, `agree` (2026-10-11).
- [x] `cap_compliant` true on every executed step (memory and PostgreSQL
      L1, L2, L3 run 1, L3 run 2).
- [x] Environment recorded; `measurement_environment` is `synthetic_replay`.
      [`PHASE3_LOAD_EVIDENCE.md`](./PHASE3_LOAD_EVIDENCE.md) § Step 6.
- [x] Evidence filled in `docs/phase-3/PHASE3_LOAD_EVIDENCE.md`.

## Out of scope

- Production capacity, multi-host, or 1M Q/day claims
- Held-out evaluation
- Wiring the Feature 1 domain map into `/v1/query`
- New `RequestMetrics` fields for compatibility time
- Editing WS8 stop thresholds to match Feature 8 budgets
- Infrastructure or policy changes after the bottleneck observation
