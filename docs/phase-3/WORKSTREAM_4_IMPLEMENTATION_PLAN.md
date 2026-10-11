# Phase 3 Workstream 4 Implementation Plan

## Goal

Record [Feature 3 — Strategy D (cross-encoder validator)](./PHASE3_PLAN.md#feature-3--strategy-d-cross-encoder-validator)
(`P3-FEAT-D`): decide from the final Phase 3 stack held-out
`false_positive_rate` whether a validator is authorized, and, only if that
trigger fires later, implement it under the card.

Two gates. Do not treat them as one “workstream complete” verdict.

**Gate A — Trigger evaluation.** Closed 2026-10-10; re-checked 2026-10-11.
The retained stack held-out FPR is `0.0`, so Strategy D is deferred. This
plan records that decision. It does not authorize validator code, telemetry
fields, a protocol reset, or another held-out run.

**Gate B — Validator implementation.** Not authorized. Steps 4–10 stay
unchecked until a later final-stack held-out report shows
`false_positive_rate` **>** `0.0` **and** the user approves implementation
in writing.

**Status:** **deferred by gate** — Gate A closed; Gate B not started.  
**Parent:** [`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 4.  
**Card:** [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) Feature 3.  
**Evidence:** [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md).  
**Re-check:** [`WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md`](./WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md).  
**Execution checklist:** [`../internal/PHASE3_IMPLEMENTATION_PLAN.md`](../internal/PHASE3_IMPLEMENTATION_PLAN.md)
§ Step 3.

Hypothesis (applies only if the trigger fires): a cross-encoder step on
Strategy C `SAFE` candidates reduces held-out `false_positive_rate` below the
same stack without D, with validator `p95_latency_ms` inside the latency
budget and `estimated_cost_usd` at or below the no-cache arm.

## Scope

### Included (Gate A, done)

- Read the final held-out compatibility report for the shipped stack
- Apply the pre-registered trigger: `false_positive_rate` **>** `0.0`
- Record deferral when the trigger does not fire
- Leave Features 1–2, serialization, and held-out artifacts unchanged

### Excluded until Gate B is authorized

- Cross-encoder or fake-validator code
- New report fields (`validator_invocation_count`, `validator_latency_ms`,
  `validator_tokens` or a synthetic cost analogue)
- Development tuning of a validator threshold or invocation band
- A held-out replay that includes Strategy D
- A real cross-encoder model, GPU rental, or a new provider dependency
- Retuning Feature 1 τ or Feature 2 eviction on held-out data

## Learning objectives

- [ ] Explain when a cross-encoder is justified by a measured safety shortfall.
- [ ] Keep the zero false-positive cap as a stopping rule, not a tuning target.
- [ ] Separate a deferred gate from an implemented feature that failed its test.

## Source of truth

| Item | Value / path |
| --- | --- |
| Dataset | `reviewed-query-pairs-2.0` |
| Splits | 400 development / 215 held-out / 615 source |
| Development file | `benchmarks/development.jsonl` |
| Held-out file | `benchmarks/held_out_test.jsonl` |
| Config | `experiments/evaluation_config.json` (`evaluation-config-1.0`) |
| Safety cap | `max_false_positive_rate` **`0.0`** |
| Trigger | shipped-stack held-out `false_positive_rate` **>** `0.0` |
| Final comparison | `artifacts/evaluation/phase3-final-held-out-comparison.json` |
| Arm | `baselines.compatibility-cache` (Strategy C + Feature 1) |
| τ | Feature 1 map `artifacts/evaluation/phase3-adaptive-threshold-map.json` |
| Eviction | default `lru` (Feature 2 failed and is not in the shipped stack) |
| TTL | WS6 `conservative` |
| Latency budget (Gate B only) | validator `p95_latency_ms` ≤ **`10.0`** on `synthetic_replay` |
| Reuse band (Gate B only) | development `hit_rate` not more than **`0.05`** absolute below C without D |
| Serialization contract | [`../phase-2/SERIALIZATION_BOUNDARY_v1.md`](../phase-2/SERIALIZATION_BOUNDARY_v1.md), `src/sscre/serialization.py` |
| Replay hook (Gate B only) | `run_compatibility_cache_baseline` in `src/sscre/baseline.py` |
| Fake-client pattern | `FakeEmbeddingClient` in `src/sscre/embedding.py` (mirror; do not reuse it as a validator) |

False-positive definition matches the WS5 Strategy C `compatibility-cache`
report. Do not substitute Strategy B `embedding-cache` FPR for this trigger.

## Outcome (Gate A)

| Check | Value | Source |
| --- | --- | --- |
| Decision date | 2026-10-10 | [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) |
| Re-check | 2026-10-11 | [`WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md`](./WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md) |
| Retained stack | Feature 1 adaptive τ, default / WS6 conservative eviction | same |
| `false_positive_rate` | **`0.0`** | `baselines.compatibility-cache` in the final comparison |
| `false_positive_examples` | **`0`** | same |
| Feature 2 candidate FPR | `0.0`, not retained (reuse did not improve) | [`PHASE3_FEATURE_2_EVIDENCE.md`](./PHASE3_FEATURE_2_EVIDENCE.md) |
| Trigger (`FPR > 0.0`) | **not fired** | — |
| Validator code | none | — |
| Protocol reset | not required | no new held-out run |

Decision: **defer**. The paper stack reports Strategies A / B / C plus Feature 1.
Strategy D is listed as not required because the zero FPR cap was met.
Validator latency and safety comparisons are **not applicable** while D is
untriggered ([`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
definition of done).

Re-check Gate A before any Strategy D code if the benchmark or held-out split
changes, or if τ, eviction, TTL, or compatibility rules change and a new
held-out compatibility report is produced. Card promotions for Features 4–8
did not change those inputs (Step 6, 2026-10-11).

## Implementation steps

### Step 1 — Read the final-stack FPR

**Track ID:** `P3-FEAT-D`

- [x] After Features 1–2, use the shipped stack: Feature 1 map plus default
      eviction. Feature 2 is not in that stack.
- [x] Read `false_positive_rate` and `false_positive_examples` from
      `artifacts/evaluation/phase3-final-held-out-comparison.json`, arm
      `baselines.compatibility-cache`.
- [x] Compare to `max_false_positive_rate` **`0.0`**. Trigger fires only on a
      strict exceedance.

### Step 2 — Apply the stopping rule

- [x] Trigger not met (`0.0`). Do not implement a validator.
- [x] Do not add telemetry fields, development tuning, or a protocol reset.
- [x] Do not retune Features 1–2 and then invoke D on the same held-out run.
- [x] Record the decision in
      [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) and
      [`PHASE3_PLAN.md`](./PHASE3_PLAN.md) § Implementation progress.

### Step 3 — Close Gate A

- [x] Parent acceptance items for the untriggered path are checked
      ([`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
      § Workstream 4).
- [x] Internal execution Step 3 records the same deferral
      ([`../internal/PHASE3_IMPLEMENTATION_PLAN.md`](../internal/PHASE3_IMPLEMENTATION_PLAN.md)).
- [x] Workstream 1 Step 6 re-check (2026-10-11) confirms the frozen artifact
      still reports FPR `0.0` after Features 4–8 card promotions.

### Step 4 — Authorize Gate B (only after a fired trigger)

- [ ] A new final-stack held-out compatibility report shows
      `false_positive_rate` **>** `0.0`. Cite that artifact in
      [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md).
- [ ] User approves Strategy D implementation in writing.
- [ ] Write a protocol reset with the template in
      [`WORKSTREAM_1_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_1_IMPLEMENTATION_PLAN.md)
      before any further held-out use. Record reason, unchanged dataset
      version, split, seed, and config hash. Held-out outcomes must not
      select the validator threshold.
- [ ] Confirm a cheaper development-only rule fix was considered before
      building D (card stopping rule, cost / latency item 3).

**Evaluated 2026-10-11:** blocked. Frozen comparison FPR is `0.0`, so none of
the four boxes above can be checked.
[`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) § Workstream 4
Step 4. No protocol reset and no Strategy D code.

### Step 5 — Serialization contract before code

- [ ] Add the card’s validator fields to
      [`../phase-2/SERIALIZATION_BOUNDARY_v1.md`](../phase-2/SERIALIZATION_BOUNDARY_v1.md)
      and `src/sscre/serialization.py` before any validator emits them:
      `validator_invocation_count`, `validator_latency_ms` (p50 / p95 / p99),
      and `validator_tokens` or a documented synthetic cost analogue.
- [ ] Keep fail-closed rules: `UNCERTAIN` and dependency failures never become
      cache hits. Redaction still drops raw query text.
- [ ] Extend serialization tests only for fields that the contract names.
      Do not invent numeric results in the plan.

**Evaluated 2026-10-11:** blocked. Step 4 did not authorize Gate B, so the
contract, `src/sscre/serialization.py`, and serialization tests were not
changed.
[`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) § Workstream 4
Step 5.

### Step 6 — Deterministic fake validator

- [ ] Add an in-process fake cross-encoder that mirrors `FakeEmbeddingClient`
      (`src/sscre/embedding.py`): deterministic scores, explicit failure
      injection, no network and no new dependency.
- [ ] Invoke it only on Strategy C `SAFE` candidates inside
      `run_compatibility_cache_baseline` (`src/sscre/baseline.py`). Default
      remains Strategy C without D.
- [ ] A validator error or timeout yields `UNCERTAIN`, not a hit.
- [ ] Tests cover score lookup, invocation band, malformed scores, and
      fail-closed behavior. Name the test module in the evidence file when
      it exists; do not cite it as present before that.

**Evaluated 2026-10-11:** blocked. Gate B is not authorized and Step 5 did
not add telemetry fields, so no fake validator, replay hook, or tests were
added.
[`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) § Workstream 4
Step 6.

Real-model swap stays out of v1 unless `P2-PROV` is promoted.

### Step 7 — Development freeze

- [ ] Tune only on `benchmarks/development.jsonl`: validator score threshold
      and when to invoke (all `SAFE` candidates, or a borderline similarity
      band).
- [ ] Minimize development `false_positive_rate` subject to development
      `hit_rate` not below C-without-D by more than **`0.05`** absolute.
- [ ] Measure validator `p95_latency_ms` on that development replay.
- [ ] If development p95 **>** `10.0`, stop. Do not run held-out D. Record
      the deferral and the measured cost in limitations.
- [ ] If the budget holds, write
      `artifacts/evaluation/phase3-validator-config.json` before any held-out
      access. Held-out replay must reject a config whose schema, dataset
      version, config version, or config SHA-256 does not match.

**Evaluated 2026-10-11:** blocked. Step 6 did not add a validator, so no
development replay, latency measurement, or
`artifacts/evaluation/phase3-validator-config.json` was written.
[`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) § Workstream 4
Step 7.

### Step 8 — One held-out decision

- [ ] One held-out replay of the Phase 3 stack **with** the frozen validator
      config, after the Step 4 protocol reset.
- [ ] Reference arm: the same stack **without** D (same τ, TTL, eviction, cap).
- [ ] **Pass** only if all hold on held-out: `false_positive_rate` **<**
      the reference FPR, `false_positive_rate` ≤ **`0.0`**, validator
      `p95_latency_ms` ≤ **`10.0`**, and `estimated_cost_usd` ≤ the no-cache
      arm on that same run (or record an explicit cost-tradeoff failure).
- [ ] **Fail:** omit D from the shipped stack, report C-only results, and do
      not retune on held-out.
- [ ] Record the decision, commands, commit, and config hash in
      [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md).
      Gallery traces for validator-blocked versus served cases use the
      existing redaction path.

**Evaluated 2026-10-11:** blocked. No protocol reset and no frozen validator
config, so no held-out Strategy D replay was run.
[`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) § Workstream 4
Step 8.

### Step 9 — Close Gate B

- [ ] Parent Workstream 4 conditional acceptance item is checked only after
      Steps 4–8 have evidence.
- [ ] Shipped stack includes D only on a recorded pass. A fail or a latency
      stop leaves Feature 1 plus default eviction in place.

**Evaluated 2026-10-11:** blocked. Steps 4–8 have no validator evidence, so
the parent conditional acceptance item stays unchecked and Gate B is not
closed. The shipped stack remains Feature 1 plus default eviction because D
was never built.
[`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) § Workstream 4
Step 9.

## Execution sequence

1. [x] Step 1 — read final-stack held-out FPR.
2. [x] Step 2 — stopping rule; no validator code.
3. [x] Step 3 — Gate A evidence and Step 6 re-check.
4. [ ] Step 4 — fired trigger, written user approval, protocol reset.
   Evaluated 2026-10-11 and blocked (FPR `0.0`).
5. [ ] Step 5 — serialization fields, then implementation.
   Evaluated 2026-10-11 and blocked (Gate B not authorized).
6. [ ] Step 6 — fake validator and tests.
   Evaluated 2026-10-11 and blocked (Gate B not authorized).
7. [ ] Step 7 — development freeze and latency stop.
   Evaluated 2026-10-11 and blocked (no validator to freeze).
8. [ ] Step 8 — one held-out replay and pass/fail.
   Evaluated 2026-10-11 and blocked (no frozen config, no protocol reset).
9. [ ] Step 9 — Gate B close.
   Evaluated 2026-10-11 and blocked (Gate B never opened).

Do not start Step 4 while the frozen final comparison still reports FPR `0.0`.

## Acceptance criteria

- [x] Trigger evaluated on the final stack and recorded
      (`artifacts/evaluation/phase3-final-held-out-comparison.json`,
      [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md)).
- [x] No validator code, telemetry fields, or extra held-out run added.
- [ ] If the trigger fires: add validator telemetry fields to the
      serialization contract before implementation, then follow Steps 4–9.

## Verification

### Gate A (recorded)

Command from
[`WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md`](./WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md)
(2026-10-11). The comparison file exists; this command only reads it.

```powershell
$env:PYTHONPATH='src'
python -c "import json; c=json.load(open('artifacts/evaluation/phase3-final-held-out-comparison.json',encoding='utf-8'))['baselines']['compatibility-cache']; print(c['false_positive_rate'], len(c.get('false_positive_examples',[])))"
```

- [x] Output: `0.0 0`.

Steps 1–3 re-read the same artifact on 2026-10-11. Command and field table:
[`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md) § Workstream 4
Steps 1–3.

- [x] `false_positive_rate` `0.0`, `false_positive_examples` `0`, Feature 1
      map hash matches, freshness policy `conservative`, no validator keys on
      the arm. Trigger not fired. No validator module or telemetry fields added.

Gate A added no modules, so it has no focused pytest target. The Phase 3 v1
suite result (**661 passed**, **15 skipped**) is the close recorded in
[`../internal/PHASE3_IMPLEMENTATION_PLAN.md`](../internal/PHASE3_IMPLEMENTATION_PLAN.md)
§ Step 6, not a Strategy D test run.

### Gate B (do not run yet)

Record commands in [`PHASE3_FEATURE_3_EVIDENCE.md`](./PHASE3_FEATURE_3_EVIDENCE.md)
only after the modules and CLI flags exist. Do not treat a regeneration of
the current final comparison as a new held-out evaluation.

- [ ] Development replay and `phase3-validator-config.json` written under the
      card rules.
- [ ] Held-out comparison written once, after the protocol reset.
- [ ] Focused validator tests pass, then `python -m pytest -q`.

## Risks

| Risk | What to do |
| --- | --- |
| Held-out leakage | Threshold and invocation band selected on development only; held-out loads the frozen config |
| Building D without a shortfall | Gate A blocks code while FPR is `0.0` |
| Using Feature 2’s FPR as the trigger | Trigger reads the shipped stack (`compatibility-cache` + Feature 1), not the deferred pattern-eviction arm |
| Validator errors served as hits | Fail closed to `UNCERTAIN` |
| Latency budget skipped | Development p95 **>** `10.0` stops the work before held-out |
| Equal or worse FPR shipped as a win | Pass requires a strict FPR decrease and FPR ≤ `0.0` |
| Telemetry invented ahead of the contract | Step 5 lands before Step 6 |
| Real-model cost hidden inside the fake | Fake validator is synthetic replay only; a real model needs a separate card |

## Out of scope

- Implementing Strategy D while Gate A still holds
- Live-provider or GPU cross-encoders (`P2-PROV`)
- Quantization, load ladder, clustering, and experiment tracking
  (Workstreams 5–8)
- Editing `SSCRE_PLAN.md` checkboxes (Workstream 9)

## Handoff

| Consumer | Uses from WS4 |
| --- | --- |
| Workstream 9 | Paper stack omits D; cite the safety-gate deferral, not a latency result |
| Workstreams 5–8 | Do not add validator fields or mix a future D arm into their artifacts |
| Later readers | Re-check the trigger on a new final-stack report before any D code. Do not retune Features 1–2 on the run that invokes D |
