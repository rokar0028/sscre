# Phase 3 Workstream 2 Implementation Plan

## Goal

Ship [Feature 1 — Adaptive per-domain thresholds](./PHASE3_PLAN.md#feature-1--adaptive-per-domain-thresholds)
(`P3-FEAT-ADAPT`): a development-selected similarity threshold (τ) per
`metadata.domain` for Strategy C (`compatibility-cache`), frozen before one
held-out replay.

**Status:** **passed** — 2026-10-10. This plan records the completed slice.
It does not authorize retuning or a second held-out run.  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 2.  
**Card:** [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) Feature 1.  
**Evidence:** [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md).  
**Execution checklist:** [`../internal/PHASE3_IMPLEMENTATION_PLAN.md`](../internal/PHASE3_IMPLEMENTATION_PLAN.md)
§ Step 1.

Hypothesis: development-selected τ per domain increases Strategy C `hit_rate`
versus global `0.95` without held-out `false_positive_rate` above `0.0`.

## Scope

### Included

- Threshold map keyed by `metadata.domain`; blank or missing → `unknown`
- Selection on `benchmarks/development.jsonl` only, grid `0.8` / `0.9` / `0.95`
- Strata with fewer than 10 development pairs fall back to global `0.95`
- Tie-break: lowest τ among equal safe hit rates
- One held-out replay with the frozen map
- Focused tests for lookup, fallback, malformed maps, and compatibility safety

### Excluded

- Pattern-aware eviction (Workstream 3)
- Strategy D (Workstream 4)
- Held-out retuning of the map
- Changing Strategies A / B / C definitions or the WS5 global τ `0.95` reference
- Live-provider embeddings

## Learning objectives

- [ ] Select a threshold on development data without using held-out outcomes.
- [ ] Explain why small strata stay on the global threshold.
- [ ] Read a pass as “held-out FPR stayed `0.0` and hit rate beat the frozen
      reference,” including how small that hit-rate gain is.

## Source of truth

| Item | Value / path |
| --- | --- |
| Dataset | `reviewed-query-pairs-2.0` |
| Splits | 400 development / 215 held-out / 615 source |
| Development file | `benchmarks/development.jsonl` |
| Held-out file | `benchmarks/held_out_test.jsonl` |
| Config | `experiments/evaluation_config.json` (`evaluation-config-1.0`) |
| Safety cap | `max_false_positive_rate` **`0.0`** |
| Reference τ | global **`0.95`** (WS5, development-selected) |
| Minimum stratum | **10** development pairs |
| Candidate grid | `0.8`, `0.9`, `0.95` |
| Domain field | `metadata.domain` |

## Outcome (2026-10-10)

| Arm | Split | `hit_rate` | `false_positive_rate` | Artifact |
| --- | --- | --- | --- | --- |
| Adaptive Strategy C | held-out | `0.002325581395348837` | `0.0` | `artifacts/evaluation/phase3-adaptive-held-out.json` |
| Global τ `0.95` Strategy C | held-out (frozen reference) | `0.0` | `0.0` | cited in [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md) |

Decision: **pass**. The frozen map ships in the Phase 3 stack. Feature 2 did
not replace it. The paper stack is Feature 1 plus default / WS6 conservative
eviction.

Open limitation (parent baseline): the held-out hit rate is very low, so later
reuse claims have little headroom. Synthetic replay only.

## Implementation steps

### Step 1 — Lookup and selection

**Track ID:** `P3-FEAT-ADAPT`

- [x] Apply a domain-keyed threshold in `src/sscre/baseline.py`
      (`select_adaptive_domain_thresholds`, `_threshold_for_record`).
      Missing or blank domain → `unknown`. Small strata and missing map keys
      use `0.95`.
- [x] Reuse the existing evaluation path in `src/sscre/evaluate.py`
      (`--adaptive-threshold-map-output` on development,
      `--adaptive-threshold-map` on later runs). Map output is rejected unless
      `--split development`.
- [x] Reject malformed map entries (`tests/test_adaptive_thresholds.py`).

### Step 2 — Development freeze

- [x] Tune only on `benchmarks/development.jsonl`.
- [x] For strata with ≥ 10 development pairs, maximize stratum `hit_rate`
      subject to stratum `false_positive_rate` ≤ `0.0`; ties take the lowest τ.
- [x] Write the map before held-out:
      `artifacts/evaluation/phase3-adaptive-threshold-map.json`.
- [x] Write the development report:
      `artifacts/evaluation/phase3-adaptive-development.json`.

Command and provenance: [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md)
(base commit `8c65926227fbdc923a23994c183ac33ba378694f`, config SHA-256
`5734f113…`, split manifest SHA-256 `68912e3b…`).

### Step 3 — Held-out decision

- [x] One held-out replay with the frozen map and unchanged WS5 semantics:
      `artifacts/evaluation/phase3-adaptive-held-out.json`.
- [x] Compare to Strategy C at global `0.95` (hit rate `0.0`, FPR `0.0`).
- [x] Pass rule met: adaptive FPR `0.0` and hit rate strictly higher
      (`0.002325581395348837`). No held-out retune.
- [x] Record the decision in
      [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Implementation progress and
      [`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md).

### Step 4 — Close

- [x] Parent acceptance criteria checked
      ([`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
      § Workstream 2).
- [x] Map eligible for later slices (Feature 2, final held-out package). Those
      slices load the frozen file; they do not reselect τ.

## Execution sequence

1. [x] Step 1 — domain lookup, selector, CLI, tests.
2. [x] Step 2 — development map and report.
3. [x] Step 3 — one held-out replay and pass decision.
4. [x] Step 4 — evidence and parent acceptance.

## Acceptance criteria

- [x] Threshold map keyed by domain, with `unknown` and small-stratum fallback
      to `0.95` (`src/sscre/baseline.py`, `src/sscre/evaluate.py`).
- [x] Tests cover lookup, fallback, malformed config, and safety
      (`tests/test_adaptive_thresholds.py`).
- [x] Map frozen before held-out:
      `artifacts/evaluation/phase3-adaptive-threshold-map.json`.
- [x] One held-out replay: hit rate `0.002325581395348837` vs reference `0.0`,
      FPR `0.0` (`artifacts/evaluation/phase3-adaptive-held-out.json`).

## Verification

Recorded 2026-10-10 in
[`PHASE3_FEATURE_1_EVIDENCE.md`](./PHASE3_FEATURE_1_EVIDENCE.md). This plan
does not re-run the suite.

```powershell
$env:PYTHONPATH='src'
python -m sscre.evaluate --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --baseline compatibility-cache --split development --production --adaptive-threshold-map-output artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-adaptive-development.json
python -m sscre.evaluate --benchmark benchmarks/held_out_test.jsonl --config experiments/evaluation_config.json --baseline compatibility-cache --split held-out --production --adaptive-threshold-map artifacts/evaluation/phase3-adaptive-threshold-map.json --output artifacts/evaluation/phase3-adaptive-held-out.json
python -m pytest -q tests/test_adaptive_thresholds.py
python -m pytest -q
```

- [x] Focused tests: **5 passed** (2026-10-10). The module now defines six
      tests (`test_adaptive_selection_falls_back_for_small_strata`,
      `test_adaptive_selection_uses_lowest_threshold_on_equal_safe_hit_rate`,
      `test_adaptive_selection_rejects_domain_without_safe_threshold`,
      `test_threshold_policy_uses_domain_and_unknown_fallback`,
      `test_adaptive_threshold_map_rejects_malformed_entries`,
      `test_adaptive_policy_preserves_compatibility_safety`). A later count is
      not recorded here.
- [x] Full suite at decision time: **655 passed**, **15 skipped**; after
      review-test additions the evidence file records **661 passed**,
      **15 skipped**.

Regeneration commands also live in [`PHASE3_PLAN.md`](./PHASE3_PLAN.md)
§ regeneration (Feature 1 block). Do not treat a regeneration as a new
held-out evaluation unless a protocol reset is written first.

## Risks

| Risk | What was done |
| --- | --- |
| Held-out leakage | Selection only on development; held-out loads the frozen map |
| Small strata overfit | Fewer than 10 development pairs stay at `0.95` |
| Unsafe τ shipped | Pass requires held-out FPR `0.0`; fail would have kept global `0.95` |
| Hit-rate “win” overstated | Gain is one order of `0.0023` vs `0.0`; parent baseline records low headroom |

## Out of scope

- Retuning Feature 1 on held-out data
- Quantization, load ladder, clustering, experiment tracking (Workstreams 5–8)
- Editing `SSCRE_PLAN.md` checkboxes (Workstream 9)

## Handoff

| Consumer | Uses from WS2 |
| --- | --- |
| Workstream 3 | Frozen map as Strategy C τ; eviction did not replace it |
| Workstream 4 | Retained stack includes the map; D trigger stayed FPR `0.0` |
| Workstream 9 | Final held-out package uses the same map |
| Later readers | Do not reselect τ; cite the frozen artifact and evidence file |
