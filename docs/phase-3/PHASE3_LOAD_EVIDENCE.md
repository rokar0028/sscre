# Phase 3 load ladder evidence

**Workstream:** 6 (Feature 8)  
**Plan:** [`WORKSTREAM_6_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_6_IMPLEMENTATION_PLAN.md)  
**Status:** Step 6 closed (2026-10-11). Evidence filled. Memory and PostgreSQL
`first_bottleneck` are `not_reached` (`reproducibility` `agree`).

Card promoted 2026-10-11 (Workstream 1 Step 5). Pre-registered budgets are in
[`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Feature 8. Harness delta, artifact
fields, and the stop rule are in
[`WORKSTREAM_6_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_6_IMPLEMENTATION_PLAN.md).

## Pre-code checklist (Step 1 slice)

Recorded 2026-10-11 before the config and test. Approver: chat request
“implement step 1”. This slice is the JSON file and
`test_phase3_load_ladder_config_matches_feature_8_card` only.

- [x] Feature 8 card is in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md).
- [x] Implementation ID `P3-FEAT-LOAD` matches Workstream 6 in
      [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md).
- [x] Strategies A/B/C are not redefined. The config arm is `compatibility`
      at global τ `0.95`.
- [x] The pool path is `benchmarks/development.jsonl`. Held-out is not used.
- [x] Budgets in the config are the card numbers (p95 500 / 3000,
      non-fixture error rate 0.01, timeout rate 0.01).
- [x] Later artifact names stay `phase3-load-ladder-memory.json` and
      `phase3-load-ladder-postgres.json`. Neither file existed at this
      Step 1 check. Step 3 wrote the memory artifact on 2026-10-11.
- [x] User OK for Step 1 is the 2026-10-11 chat request. At that check,
      Steps 2–6 were not approved. Steps 2–6 were approved later the same day.
- [x] No live-provider, dashboard, or capacity work in this slice.

## Step 1 — workload config

**Date:** 2026-10-11  
**Config:** `experiments/phase3_load_ladder_v1.json`  
**Protocol:** `phase3-load-ladder-v1`  
**Mode:** `compatibility`, repository `memory`, threshold arm `global_0.95`  
**Caps:** `max_cache_entries` 10000, `max_cache_bytes` 100000000  
**Steps:** L1 200/20/4, L2 2000/200/4, L3 20000/2000/8 (measured / warmup / concurrency)  
No `items` list and no `[fail_embedding]` or `[fail_generation]` queries.

- [x] `python -m pytest -q tests/test_load_test.py` → **8 passed**, 1 warning (2026-10-11).
- [x] `python -m pytest -q` → **756 passed, 15 skipped, 21 deselected**, 1 warning (2026-10-11). Skips are existing unavailable-service tests, not a Step 1 failure.

## Step 2 — harness

**Date:** 2026-10-11  
**Scope:** `run_ladder()` in `src/sscre/load_test.py`. `main` sends
`phase3-load-ladder-v1` there. `run()` and `_stop_reason` are unchanged.
No L1–L3 artifact.

Component time is taken on the injected embedding client, LLM client, and a
repository proxy. The app runs those calls on its own thread pool, so each
duration is published back onto the in-flight request. `compatibility_check`
stays in `unavailable_components`. A zero p95-share sum is
`bottleneck_outcome: unattributed` and `first_bottleneck: null`.

- [x] `python -m pytest -q tests/test_load_test.py` → **18 passed**, 1 warning (2026-10-11). The new cases use a fake step runner or a 2-request smoke. They do not run L2 or L3.
- [x] `python -m pytest -q tests/test_postgres_eviction_scope.py tests/test_load_test.py` → **23 passed**, 1 warning (2026-10-11), after the proxy forwarded `insert_and_evict` without issuing its own delete.
- [x] `python -m pytest -q` → **766 passed, 15 skipped, 21 deselected**, 1 warning (2026-10-11). Skips are existing unavailable-service tests, not a Step 2 failure.

| Artifact | Status |
| --- | --- |
| `artifacts/operations/phase3-load-ladder-memory.json` | written, `status: complete` (Step 3) |
| `artifacts/operations/phase3-load-ladder-postgres.json` | written, `status: complete` (Step 4 rerun) |

| Field | Value |
| --- | --- |
| `first_bottleneck` (memory) | `not_reached` |
| `reproducibility` (memory) | `agree` |
| `first_bottleneck` (PostgreSQL) | `not_reached` |
| `reproducibility` (PostgreSQL) | `agree` |

## Step 3 — in-memory ladder

**Date:** 2026-10-11  
**Command** (exit 0, wall clock 457095 ms):

```powershell
$env:PYTHONPATH='src'
python -m sscre.load_test --config experiments/phase3_load_ladder_v1.json --output artifacts/operations/phase3-load-ladder-memory.json
```

Stdout ended with `Wrote load-test report to artifacts\operations\phase3-load-ladder-memory.json`. A Starlette `TestClient` deprecation warning printed and is not a budget result.

The stop rule ran L1, L2, and L3, then repeated L3 once. No budget breached, so it did not stop early. `measurement_environment` is `synthetic_replay`. This is not a capacity or SLA figure.

| Field | Value |
| --- | --- |
| `git_commit` | `e3363cfdebed9d9f0734e3b9458fdfede8ac199c` |
| `git_worktree_dirty` | `true` |
| `config_sha256` | `8412af812b61a2933d896dd4f1c5f5ef4da6f6f81c64be17b7092e43c35e3b8d` |
| `development_sha256` | `14a1d2acd976c2fc891e6d5c3b7c33b729e69e37e66809929d1f74a759f01305` |
| `seed` / `pool_size` | `20261011` / 728 |
| OS / Python | Windows-11-10.0.26200-SP0 / 3.14.5 |
| CPU | Intel64 Family 6 Model 140 Stepping 1, GenuineIntel (`cpu_count` 8) |
| Process count | 1 |
| PostgreSQL | not used (`postgresql_version` null) |
| `measured_at` | `2026-10-11T11:41:46.733249+00:00` |

Memory budgets used: p95 ≤ 500 ms, `non_fixture_error_rate` ≤ 0.01, `timeout_rate` ≤ 0.01. Caps: 10000 entries, 100000000 bytes.

| Step | Run | p95 ms | Error rate | Timeout rate | Entries | Bytes | Cap | Requests/s | Compression |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| L1 | 1 | 34.694 | 0 | 0 | 157 | 40473 | true | 166.122 | 14352.93076 |
| L2 | 1 | 44.929 | 0 | 0 | 706 | 181649 | true | 121.538 | 1050.09167 |
| L3 | 1 | 101.270 | 0 | 0 | 706 | 181649 | true | 106.742 | 92.225054 |
| L3 | 2 | 110.857 | 0 | 0 | 706 | 181649 | true | 98.879 | 85.431047 |

Concurrency was 4 on L1 and L2, and 8 on both L3 runs. Realized repeat ratios: 0.245, 0.312, 0.3049, 0.3049. `budget_breached` is null on every step. `isolate_queries` is false. `unavailable_components` is `compatibility_check`.

Artifact outcome: `first_bottleneck` `not_reached`, `reproducibility` `agree`, `bottleneck_step` null. The largest L3 p95 share is `wrapper_other`. No budget missed, so that share is not a bottleneck name.

- [x] L1 → L2 → L3 plus the L3 confirmation ran, and the memory artifact was written.
- [x] Every executed step has `cap_compliant: true`.
- [x] No cache, timeout, or deployment setting was changed after this run.

## Step 4 — PostgreSQL ladder

**Date:** 2026-10-11  

First attempt (exit 0, about 1.5 s): `SSCRE_DATABASE_URL` was unset in the
shell. The harness wrote `status: unavailable` with
`unavailable_reason` `SSCRE_DATABASE_URL is not set` and did not run L1–L3.

Rerun (exit 0): URL loaded from `.env` against local `major-postgres-1`
(pgvector 16.15). Command:

```powershell
$env:PYTHONPATH='src'
python -m sscre.load_test --config experiments/phase3_load_ladder_v1.json --repository postgres --output artifacts/operations/phase3-load-ladder-postgres.json
```

(Equivalent to loading `SSCRE_DATABASE_URL` from `.env` before the same CLI.)

The stop rule ran L1, L2, and L3, then repeated L3 once. PostgreSQL budgets:
p95 ≤ 3000 ms, `non_fixture_error_rate` ≤ 0.01, `timeout_rate` ≤ 0.01.

| Step | Run | p95 ms | Error rate | Timeout rate | Entries | Bytes | Cap | Requests/s | Compression |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| L1 | 1 | 438.528 | 0 | 0 | 157 | 55121 | true | 10.841 | 936.6254 |
| L2 | 1 | 359.219 | 0 | 0 | 863 | 302654 | true | 14.64 | 126.486791 |
| L3 | 1 | 1062.376 | 0 | 0 | 1569 | 550144 | true | 11.059 | 9.55477 |
| L3 | 2 | 958.388 | 0 | 0 | 3844 | 1347735 | true | 10.42 | 9.003228 |

Concurrency 4 on L1 and L2, 8 on both L3 runs. `isolate_queries` is true.
`postgresql_version` is `16.15 (Debian 16.15-1.pgdg12+2)`.
`first_bottleneck` `not_reached`, `reproducibility` `agree`.

- [x] URL unset: first artifact recorded `unavailable` (superseded by rerun file).
- [x] URL set: L1–L3 PostgreSQL ladder ran and overwrote the artifact as `complete`.
      Authoritative rerun exit 0 (~75 min wall clock, `measured_at`
      `2026-10-11T13:15:54Z`). A overlapping duplicate attempt later crashed
      on L3 run 2 with `DependencyTimeoutError` and did not rewrite the artifact.

## Step 5 — Bottleneck

**Date:** 2026-10-11  
**Sources:** `artifacts/operations/phase3-load-ladder-memory.json` (`status: complete`) and `artifacts/operations/phase3-load-ladder-postgres.json` (`status: unavailable`).

Both artifacts are `complete`. Each `first_bottleneck` is `not_reached` and
`reproducibility` is `agree`. `budget_breached` is null on L1, L2, L3 run 1,
and L3 run 2 on each backend.

`wrapper_other` has the largest L3 p95 share in the memory artifact. No budget missed, so it is not the bottleneck. No component was chosen by hand. Cache, timeout, and deployment settings were not changed.

`measurement_environment` remains `synthetic_replay`. This is not a capacity or SLA figure.

- [x] Complete artifact read: memory `not_reached` with `reproducibility` `agree` and no L1–L3 budget breach.
- [x] PostgreSQL complete artifact read: `not_reached` with `reproducibility` `agree`.
- [x] The complete artifact is not `disagree` or `unattributed`. No component was chosen by hand.
- [x] No cache, timeout, or deployment setting changed after the result.

## Step 6 — Evidence close

**Date:** 2026-10-11  
**Label:** `measurement_environment` is `synthetic_replay`. This record is a local synthetic replay. It is not a production capacity figure and not an SLA.

Commands, hashes, seed, budgets, compression, caps, and `not_reached` are in §§ Step 3–5. This section is the close checklist.

| Item | Value |
| --- | --- |
| Memory command | `python -m sscre.load_test --config experiments/phase3_load_ladder_v1.json --output artifacts/operations/phase3-load-ladder-memory.json` with `PYTHONPATH=src` (exit 0) |
| PostgreSQL command | same config, `--repository postgres`, output `artifacts/operations/phase3-load-ladder-postgres.json` (exit 0) |
| `git_commit` | `e3363cfdebed9d9f0734e3b9458fdfede8ac199c` |
| `git_worktree_dirty` | `true` |
| `config_sha256` | `8412af812b61a2933d896dd4f1c5f5ef4da6f6f81c64be17b7092e43c35e3b8d` |
| `development_sha256` | `14a1d2acd976c2fc891e6d5c3b7c33b729e69e37e66809929d1f74a759f01305` |
| `seed` | `20261011` |
| OS | Windows-11-10.0.26200-SP0 |
| CPU | Intel64 Family 6 Model 140 Stepping 1, GenuineIntel (`cpu_count` 8) |
| Python | 3.14.5 |
| PostgreSQL | 16.15 (Debian 16.15-1.pgdg12+2) on local Docker (`major-postgres-1`) |
| Process count | 1 |
| Concurrency | L1: 4, L2: 4, L3 run 1: 8, L3 run 2: 8 |
| Memory budgets | p95 ≤ 500 ms, `non_fixture_error_rate` ≤ 0.01, `timeout_rate` ≤ 0.01 |
| Caps | 10000 entries, 100000000 bytes. Every executed step `cap_compliant: true` (entries ≤ 706, bytes 181649) |
| Compression | L1 14352.93076, L2 1050.09167, L3 run 1 92.225054, L3 run 2 85.431047 |
| `first_bottleneck` | memory and PostgreSQL each `not_reached`, `reproducibility` `agree`, L1–L3 |

Fake-provider limit: embed and generation times are local wrapper times on `LoadTestEmbeddingClient` and `LoadTestLLMClient`. `compatibility_check` was not split out. It stays in `unavailable_components` and inside `wrapper_other`.

- [x] Commands, git commit, config hash, development hash, seed, environment, budgets, compression factors, cap result, and `not_reached` are recorded above.
- [x] Fake-provider limit stated: local wrapper times, and `compatibility_check` was not split out.
- [x] Result labeled `synthetic_replay`. Not called a capacity or SLA figure.

**Verification (2026-10-11, after PostgreSQL ladder):** `python -m pytest -q`
→ **780 passed**, 1 skipped, 21 deselected, 1 warning.
