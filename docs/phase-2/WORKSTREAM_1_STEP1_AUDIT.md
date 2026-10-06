# Workstream 1 — Step 1 audit record

Audit date: 2026-10-06  
Contract reference: [SAFETY_EVALUATION_CONTRACT_v1.md](./SAFETY_EVALUATION_CONTRACT_v1.md)

The gap table below is the original step 1 record. Later steps closed the
Strategy A `EXACT_HIT` API value, empty `QueryResponse` traces, and the
test-only resolver. Strategy C calls `resolve_candidate_traces`. A plain miss
with no traces is `UNSAFE` / `no candidates were retrieved`. Generation
failure logs `UNCERTAIN` / `generation_failed`. The default semantic strategy
is `C`.

Still open when Strategy B is selected: it serves from similarity alone and
records only the first candidate. Those gap rows remain accurate for that
opt-in path.

## Verified (code inspection)

- [x] `SafetyDecision` = `SAFE` \| `UNSAFE` \| `UNCERTAIN` in `src/sscre/safety.py`.
- [x] `CandidateTrace`, `SafetyResult`, `QueryMetadata` invariants enforced in `__post_init__`.
- [x] `resolve_candidate_traces()` implements SAFE-first, then UNCERTAIN over all-UNSAFE, empty → non-SAFE.
- [x] `evaluate_candidate()` is conservative; missing evidence → `UNCERTAIN`, known mismatch → `UNSAFE`.
- [x] `QueryMetadata` bounds entities, constraints, and string lengths.

## Trace emission consistency (gaps for steps 4–5)

| Path | Emits traces? | Full `CandidateTrace` fields? | Notes |
|---|---|---|---|
| Strategy C exact hit | log | yes via `trace_with_context` | `stage=compatibility` |
| Strategy C semantic multi-candidate | log | yes | Uses inline first-SAFE selection, not `resolve_candidate_traces()` |
| Strategy B semantic hit | log | partial | `stage=retrieval`; `SAFE` from similarity only |
| Strategy A exact hit | log | empty `candidate_traces` | `decision=EXACT_HIT` in API |
| Generated / miss | log | prior `decision_traces` only | Often empty; API `decision=UNCERTAIN` |
| Generation failed | log | none | No trace array |
| `evaluate_candidate()` alone | n/a | partial | No order/metadata until caller enriches |
| `QueryResponse` JSON | no traces | n/a | Clients see aggregate fields only |
| `baseline` benchmark | summary fields | not full trace tuple | `predicted_decision`, `reason`, similarity |

**Conclusion:** Operational logs under Strategy C are the reference trace shape;
API and several code paths are intentionally or accidentally inconsistent. Step 5
should unify serialization; step 2 should address `EXACT_HIT` vs `SafetyDecision`.

## Contract test coverage

| Area | Covered? | Evidence |
|---|---|---|
| Decision precedence | yes | `tests/test_safety.py` (`resolve_candidate_traces`) |
| SAFE invariants on `SafetyResult` | yes | `tests/test_safety.py` |
| Empty candidates fail closed | yes | `tests/test_safety.py` |
| Metadata bounds / round-trip | yes | `tests/test_safety.py` |
| Compatibility reason matrix | yes | `tests/test_compatibility.py` |
| `CandidateTrace` field validation | partial | No dedicated invalid-similarity / empty-reason tests |
| Trace serialization stability | partial | `test_strategy_c_logs_bounded_candidate_decision_trace` in `tests/test_exact_cache.py` |
| `resolve_candidate_traces` in production path | no | Only unit tests call it today |
| Label separation (correctness/preference) | n/a | Step 3; benchmark uses separate `compatibility_label` |

**Conclusion:** Core precedence and compatibility behavior are tested; serialization
and full boundary tests remain for step 6.

## Verification commands

```bash
python -m pytest -q tests/test_safety.py tests/test_compatibility.py
```

**2026-10-06:** `python -m pytest -q tests/test_safety.py tests/test_compatibility.py` → **22 passed**.

## Checklist (step 1 exit)

- [x] Versioned contract document published (`SAFETY_EVALUATION_CONTRACT_v1.md`).
- [ ] All external trace emitters expose required fields consistently (gaps table above).
- [ ] Contract tests fully cover serialization, bounds, precedence, and failure closure (gaps table above).
