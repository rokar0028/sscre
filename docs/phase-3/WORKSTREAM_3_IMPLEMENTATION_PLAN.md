# Phase 3 Workstream 3 Implementation Plan

## Goal

Record [Feature 2 — Pattern-aware eviction](./PHASE3_PLAN.md#feature-2--pattern-aware-eviction)
(`P3-FEAT-EVICT`): under a development-selected entry cap, evict lower-`hit_count`
entries first within each reviewed `freshness_class`, then decide from one
held-out replay whether that ordering beats default (`lru`) eviction.

**Status:** **failed; deferred from the shipped stack** — 2026-10-10. This plan
records the completed slice. It does not authorize retuning, a second held-out
run, or putting pattern eviction in the paper stack.  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 3.  
**Card:** [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) Feature 2.  
**Evidence:** [`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md).  
**Execution checklist:** [`../internal/PHASE3_IMPLEMENTATION_PLAN.md`](../internal/PHASE3_IMPLEMENTATION_PLAN.md)
§ Step 2.

Hypothesis: when a pre-registered entry cap forces evictions during Strategy C
replay, evicting lower `hit_count` first within each `freshness_class` increases
`hit_rate` or `safe_reuse_coverage` versus WS6 `conservative` plus default
eviction, without `stale_exposure_rate` or `false_positive_rate` above `0.0`.

## Scope

### Included

- Optional `lru` and `pattern` eviction on the in-memory cache
- Pattern order: lower `hit_count` first; then `dynamic`, `semi_dynamic`,
  `stable`; then access order and `query_hash`
- Development-only selection of the smallest entry cap that forces at least one
  eviction on the `lru` reference arm
- One held-out replay of `pattern` versus `lru` at that frozen cap
- WS6 `conservative` TTLs and the Feature 1 frozen τ map left unchanged
- Focused tests for pattern order, cap enforcement, and the default `lru` path

### Excluded

- Shipping pattern eviction after a failed reuse comparison
- Held-out retuning of the cap or the ordering rule
- A new TTL policy matrix
- Multi-process eviction, PostgreSQL eviction, and a public invalidation API
- Strategy D (Workstream 4)

## Learning objectives

- [ ] Force eviction with a development-selected cap so the ordering rule can
      be measured.
- [ ] Keep TTL and τ frozen while changing only eviction priority.
- [ ] Treat equal held-out reuse as a fail, and leave the default policy in
      the shipped stack.

## Source of truth

| Item | Value / path |
| --- | --- |
| Dataset | `reviewed-query-pairs-2.0` |
| Splits | 400 development / 215 held-out / 615 source |
| Development file | `benchmarks/development.jsonl` |
| Held-out file | `benchmarks/held_out_test.jsonl` |
| Config | `experiments/evaluation_config.json` (`evaluation-config-1.0`) |
| Safety cap | `max_false_positive_rate` **`0.0`** |
| τ | Feature 1 map `artifacts/evaluation/phase3-adaptive-threshold-map.json` |
| TTL policy | WS6 `conservative` (`stable` 3600 s, `semi_dynamic` 600 s, dynamic disallowed) |
| Entry-cap grid | `1, 2, 4, 8, 16, 32` (`DEFAULT_ENTRY_CAP_GRID` in `src/sscre/phase3_eviction.py`) |
| Byte cap | `100_000_000` (does not bind; the entry cap forces eviction) |
| Reference strategy | `lru` (pre-Feature-2 default) |
| Candidate strategy | `pattern` |
| Held-out freshness | stable reviewed class only |

The card allowed a `phase3_eviction_experiment` config block or an equivalent.
The equivalent is `python -m sscre.phase3_eviction` plus the grid above. No
new evaluation-config block was added.

## Outcome (2026-10-10)

| Arm | Split | `entry_cap` | `hit_rate` | `safe_reuse_coverage` | `false_positive_rate` | `stale_exposure_rate` | Artifact |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pattern` | held-out | `1` | `0.002325581395348837` | `0.011764705882352941` | `0.0` | `0.0` | `artifacts/evaluation/phase3-held-out-eviction.json` |
| `lru` (same cap) | held-out | `1` | `0.002325581395348837` | `0.011764705882352941` | `0.0` | `0.0` | same file, `reference_arm` |

Development selection (`artifacts/evaluation/phase3-development-eviction.json`):

- Smallest cap with reference `eviction_count` ≥ 1: **`entry_cap=1`**
- Reference evictions at that cap: **`777`**
- Candidate constraints satisfied: `stale_exposure_rate` `0.0`,
  `false_positive_rate` `0.0`, `dynamic_reuse_served_rate` `0.0`

Decision: **fail/defer**. Safety constraints held, and reuse was equal to the
same-cap `lru` arm, so the strict-improvement rule failed. The paper stack
keeps Feature 1 plus default / WS6 conservative eviction.

Open limitations (parent baseline): synthetic replay only; held-out freshness
scope is stable-only, so the held-out stale-exposure check does not cover
semi-dynamic or dynamic pairs; Strategy C hit rate is very low, so reuse
comparisons have little headroom.

## Implementation steps

### Step 1 — Eviction priority

**Track ID:** `P3-FEAT-EVICT`

- [x] Add `lru` and `pattern` strategies on `InMemoryExactCache`
      (`src/sscre/cache.py`, `_eviction_key`). `pattern` sorts by `hit_count`,
      then freshness rank (`dynamic` `0`, `semi_dynamic` `1`, `stable` `2`),
      then access order and `query_hash`. Unknown temporal class ranks as
      `stable`.
- [x] Thread `eviction_strategy` through compatibility replay
      (`src/sscre/baseline.py`, `run_compatibility_cache_baseline`). Default
      remains `lru`. Values other than `lru` or `pattern` are rejected.
- [x] Keep WS6 `conservative` TTLs. Replay loads that policy from
      `freshness_experiment` and does not retune the four-arm matrix.
- [x] Tests in `tests/test_cache_eviction.py` cover pattern priority
      (`test_pattern_eviction_prioritizes_low_hits_within_freshness_class`),
      reviewed freshness class on replay
      (`test_replay_uses_reviewed_freshness_class_for_cached_entries`), LRU
      ties, and cap enforcement.

### Step 2 — Development freeze

- [x] Tune only on `benchmarks/development.jsonl` via
      `select_development_eviction_policy` in `src/sscre/phase3_eviction.py`.
- [x] Walk the cap grid on the `lru` arm and take the smallest cap with
      `eviction_count` ≥ 1. Fail closed if the grid produces no eviction.
- [x] Run `pattern` at that cap. Accept the candidate on development only when
      `stale_exposure_rate` ≤ `0.0`, `false_positive_rate` ≤ `0.0`, and
      `dynamic_reuse_served_rate` ≤ `0.0`.
- [x] Write the frozen policy before held-out:
      `artifacts/evaluation/phase3-pattern-eviction-policy.json`
      (`selected_entry_cap` `1`, `eviction_strategy` `pattern`,
      `schema_version` `phase3-pattern-eviction-1.0`).
- [x] Write the development report:
      `artifacts/evaluation/phase3-development-eviction.json`.

Held-out replay rejects a policy whose schema, dataset version, config version,
config SHA-256, or strategy does not match (`_validate_policy_artifact`).

Provenance: [`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md)
(branch `phase3/implementation`, config SHA-256 `5734f113…`).

### Step 3 — Held-out decision

- [x] One held-out replay with the frozen cap, frozen `conservative` TTLs, and
      the Feature 1 map:
      `artifacts/evaluation/phase3-held-out-eviction.json`.
- [x] Reference arm is `lru` at the same `entry_cap=1` inside that artifact.
- [x] Pass rule not met: FPR `0.0` and stale exposure `0.0`, but `hit_rate` and
      `safe_reuse_coverage` were equal to the reference, not strictly greater.
- [x] Stopping rule applied: retain default eviction; no held-out retune.
- [x] Record the decision in
      [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Implementation progress and
      [`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md).

### Step 4 — Close

- [x] Parent acceptance criteria checked
      ([`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
      § Workstream 3).
- [x] Shipped stack does not load the pattern policy. Later slices (Strategy D
      gate, final held-out package) use Feature 1 plus default eviction.

## Execution sequence

1. [x] Step 1 — pattern ordering, replay flag, tests.
2. [x] Step 2 — development cap and policy freeze.
3. [x] Step 3 — one held-out replay and fail/defer decision.
4. [x] Step 4 — evidence and parent acceptance.

## Acceptance criteria

- [x] Eviction priority implemented and tested (`src/sscre/cache.py`,
      `src/sscre/phase3_eviction.py`, `tests/test_cache_eviction.py`).
- [x] Policy and `entry_cap=1` frozen on development
      (`artifacts/evaluation/phase3-pattern-eviction-policy.json`).
- [x] One held-out replay: reuse equal to the same-cap reference, so the pass
      criterion failed (`artifacts/evaluation/phase3-held-out-eviction.json`).
- [x] Shipped stack keeps default eviction; no held-out retuning.

## Verification

Recorded 2026-10-10 in
[`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md). This plan
does not re-run the suite.

```powershell
$env:PYTHONPATH='src'
python -m sscre.phase3_eviction --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --split development --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-development-eviction.json --policy-output artifacts/evaluation/phase3-pattern-eviction-policy.json
python -m sscre.phase3_eviction --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --split held-out --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --selected-policy artifacts/evaluation/phase3-pattern-eviction-policy.json --output artifacts/evaluation/phase3-held-out-eviction.json
python -m pytest -q tests/test_cache_eviction.py tests/test_adaptive_thresholds.py
python -m pytest -q
```

- [x] Full suite at decision time: **661 passed**, **15 skipped**, one existing
      Starlette/httpx deprecation warning
      ([`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md)).
      The evidence file does not record a separate focused-test count.

Regeneration commands also live in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md)
§ regeneration (Feature 2 block). Do not treat a regeneration as a new
held-out evaluation unless a protocol reset is written first.

## Risks

| Risk | What was done |
| --- | --- |
| Held-out leakage | Cap selected on development; held-out loads the frozen policy |
| Eviction never triggered | Smallest cap with `eviction_count` ≥ 1; grid with no eviction raises |
| Unsafe or stale hits | Development constraints plus held-out FPR and stale exposure `0.0` |
| Equal reuse shipped as a win | Pass requires a strict increase; equality deferred the policy |
| TTL or τ changed with the experiment | `conservative` TTLs and the Feature 1 map stayed frozen |
| Held-out stale exposure over-read | Held-out freshness scope is stable-only |

## Out of scope

- Retuning Feature 2 on held-out data
- Promoting pattern eviction into the shipped stack without a new card and
  protocol reset
- Quantization, load ladder, clustering, experiment tracking (Workstreams 5–8)
- Editing `SSCRE_PLAN.md` checkboxes (Workstream 9)

## Handoff

| Consumer | Uses from WS3 |
| --- | --- |
| Workstream 4 | Retained stack excludes pattern eviction; D trigger stayed FPR `0.0` |
| Workstream 9 | Final held-out package uses default eviction; Feature 2 is a recorded miss |
| Later readers | Cite the fail/defer evidence. Do not reselect the cap or claim a reuse gain |
