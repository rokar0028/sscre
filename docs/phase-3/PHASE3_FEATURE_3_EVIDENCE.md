# Phase 3 Feature 3 evidence — Strategy D gate

**Date:** 2026-10-10  
**Branch:** `phase3/implementation`  
**Decision:** **deferred; trigger not met**

## Gate evaluation

The pre-registered trigger is a final Phase 3 stack held-out
`false_positive_rate > 0.0`.

- Retained stack: Feature 1 adaptive thresholds with default/WS6 conservative
  eviction.
- Feature 1 held-out FPR: `0.0`.
- Feature 2 candidate held-out FPR: `0.0`, but the candidate failed its reuse
  improvement criterion and was not retained.
- Safety ceiling: `0.0`.

The Strategy D trigger did not fire. No cross-encoder code, validator telemetry,
development tuning, protocol reset, or additional held-out run was performed.

## Decision

- Strategy D remains deferred from the Phase 3 v1 shipped stack.
- The paper stack reports the Feature 1 result with default/WS6 conservative
  eviction.
- If a future final stack held-out run exceeds the `0.0` FPR ceiling, the protocol
  must be reset in writing before any additional held-out evaluation.

## Re-check (Workstream 1 Step 6)

**Date:** 2026-10-11  
**Record:** [`WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md`](./WORKSTREAM_1_STEP6_STRATEGY_D_GATE.md)

- Card promotions (Features 4–8) did not change benchmark, config cap, or shipped stack.
- Frozen final comparison still reports Strategy C + Feature 1 **`false_positive_rate` `0.0`**.
- Trigger **not fired**; Strategy D remains deferred.

## Workstream 4 Steps 1–3

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_4_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_4_IMPLEMENTATION_PLAN.md) Steps 1–3  
**Decision:** **deferred; trigger not met** (unchanged)

### Step 1 — final-stack FPR

Read-only. No replay and no write to the comparison artifact.

```powershell
$env:PYTHONPATH='src'
python -c "import json; d=json.load(open('artifacts/evaluation/phase3-final-held-out-comparison.json',encoding='utf-8')); c=d['baselines']['compatibility-cache']; print('fpr', c['false_positive_rate']); print('fp_examples', len(c.get('false_positive_examples',[]))); print('hit_rate', c['hit_rate']); print('freshness', c.get('freshness_replay_policy_name')); print('dataset', c.get('dataset_version')); print('adaptive_sha', d.get('adaptive_threshold_map_sha256')); print('policy', d.get('freshness_policy_name')); print('keys_validator', [k for k in c if 'validator' in k.lower()]); print('top_eviction', d.get('eviction_strategy')); print('commit', d.get('git_commit'))"
```

| Field | Value |
| --- | --- |
| Arm | `baselines.compatibility-cache` |
| `false_positive_rate` | `0.0` |
| `false_positive_examples` | `0` |
| `hit_rate` | `0.002325581395348837` |
| `freshness_replay_policy_name` | `conservative` |
| Report `freshness_policy_name` | `conservative` |
| `dataset_version` | `reviewed-query-pairs-2.0` |
| `adaptive_threshold_map_sha256` | `cf665370c369605c0089bd1e8391b03a62799e58281b431539b4fa689bd3de16` |
| `eviction_strategy` | absent |
| `git_commit` | `fe68ce3b3cc6cdc35507e8faebbea5549ce5b50e` |
| Validator keys on the arm | none |

The map hash matches `artifacts/evaluation/phase3-adaptive-threshold-map.json`
(SHA-256 of the file bytes). Feature 2 pattern eviction is not on this report.
Safety cap in `experiments/evaluation_config.json` is `max_false_positive_rate`
**`0.0`**. Trigger (`FPR > 0.0`) does not fire.

### Step 2 — stopping rule

- No `src/sscre/phase3_validator.py`.
- `src/sscre/serialization.py` has no `validator_invocation_count`,
  `validator_latency_ms`, or `validator_tokens`.
- No protocol reset and no additional held-out run.
- Existing `safety_validator_error` in `src/sscre/compatibility.py` is the
  compatibility rule path, not a Strategy D cross-encoder.

### Step 3 — Gate A

- Parent untriggered acceptance items stay checked
  ([`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
  § Workstream 4).
- Internal Step 3 deferral stands
  ([`../internal/PHASE3_IMPLEMENTATION_PLAN.md`](../internal/PHASE3_IMPLEMENTATION_PLAN.md)).
- This read matches the Workstream 1 Step 6 re-check above. Gate B stays closed.

## Workstream 4 Step 4

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_4_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_4_IMPLEMENTATION_PLAN.md) Step 4  
**Decision:** **blocked; Gate B not authorized**

Step 4 opens only when a final-stack held-out compatibility report shows
`false_positive_rate` **>** `0.0`. The report from Steps 1–3 does not.

| Gate B input | Result |
| --- | --- |
| Artifact | `artifacts/evaluation/phase3-final-held-out-comparison.json` |
| Arm | `baselines.compatibility-cache` |
| `false_positive_rate` | `0.0` (not **>** `0.0`) |
| Newer final-stack held-out report | none |
| Written approval to implement Strategy D | not granted |
| Protocol reset | not written |
| Development-only rule fix before building D | not applicable; D is not authorized |

No validator code, telemetry fields, or held-out replay was added. Steps 5
and 6 were evaluated next and are also blocked. Steps 7–9 stay closed.

## Workstream 4 Step 5

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_4_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_4_IMPLEMENTATION_PLAN.md) Step 5  
**Decision:** **blocked; serialization contract unchanged**

Step 5 adds `validator_invocation_count`, `validator_latency_ms`, and
`validator_tokens` (or a synthetic cost analogue) only after Gate B is
authorized. Step 4 did not authorize it.

| Check | Result |
| --- | --- |
| Gate B | not authorized (held-out FPR `0.0`) |
| [`SERIALIZATION_BOUNDARY_v1.md`](../phase-2/SERIALIZATION_BOUNDARY_v1.md) | not edited |
| `src/sscre/serialization.py` | not edited |
| Serialization tests | not extended |
| Validator telemetry fields | still absent |

The untriggered acceptance rule stays in force: no validator telemetry fields
until the trigger fires
([`PHASE_3_IMPLEMENTATION_PLAN.md`](./PHASE_3_IMPLEMENTATION_PLAN.md)
§ Workstream 4). Fail-closed behavior and report redaction are unchanged.

## Workstream 4 Step 6

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_4_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_4_IMPLEMENTATION_PLAN.md) Step 6  
**Decision:** **blocked; no fake validator added**

Step 6 adds an in-process fake cross-encoder and tests only after Gate B is
authorized and Step 5 has named the telemetry fields. Neither is true.

| Check | Result |
| --- | --- |
| Gate B | not authorized (held-out FPR `0.0`) |
| Step 5 serialization fields | not added |
| `src/sscre/phase3_validator.py` | absent |
| Hook in `run_compatibility_cache_baseline` | not added |
| Validator tests | not added |

`src/sscre/baseline.py` still runs Strategy C without D. Steps 7–9 were
evaluated next and are also blocked.

## Workstream 4 Step 7

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_4_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_4_IMPLEMENTATION_PLAN.md) Step 7  
**Decision:** **blocked; no development freeze**

Step 7 tunes a validator threshold on `benchmarks/development.jsonl` and may
write `artifacts/evaluation/phase3-validator-config.json`. That requires the
Step 6 fake validator. Step 6 did not add one.

| Check | Result |
| --- | --- |
| Gate B | not authorized (held-out FPR `0.0`) |
| Fake validator | absent |
| Development replay for D | not run |
| `p95_latency_ms` measurement | not taken |
| `artifacts/evaluation/phase3-validator-config.json` | not written |

Held-out data was not used to select a threshold. Step 8 was evaluated
next and is also blocked. Step 9 stays closed.

## Workstream 4 Step 8

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_4_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_4_IMPLEMENTATION_PLAN.md) Step 8  
**Decision:** **blocked; no held-out Strategy D replay**

Step 8 is one held-out replay of the stack with a frozen validator config,
after a Step 4 protocol reset. Neither input exists.

| Check | Result |
| --- | --- |
| Gate B | not authorized (held-out FPR `0.0`) |
| Protocol reset | not written |
| `artifacts/evaluation/phase3-validator-config.json` | absent |
| New held-out replay | not run |
| Pass/fail for Strategy D | not applicable |

The frozen comparison
`artifacts/evaluation/phase3-final-held-out-comparison.json` stays the paper
result. Strategy D remains omitted. Step 9 was evaluated next and is also
blocked.

## Workstream 4 Step 9

**Date:** 2026-10-11  
**Plan:** [`WORKSTREAM_4_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_4_IMPLEMENTATION_PLAN.md) Step 9  
**Decision:** **blocked; Gate B not closed**

Step 9 checks the parent conditional acceptance item only after Steps 4–8
record a validator implementation and a pass, fail, or latency stop. Those
steps are blocked, so Gate B never opened.

| Check | Result |
| --- | --- |
| Steps 4–8 implementation evidence | absent (each step blocked) |
| Parent conditional acceptance item | left unchecked |
| Strategy D in the shipped stack | omitted |
| Shipped stack | Feature 1 adaptive τ, default / WS6 conservative eviction |

Gate A remains the close for this workstream. A later FPR above `0.0` can
reopen Steps 4–9.
