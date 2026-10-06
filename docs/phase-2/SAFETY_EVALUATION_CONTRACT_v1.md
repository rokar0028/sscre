# Safety evaluation contract (v1.0.0)

**Status:** frozen for Phase 2 Workstreams 2–9  
**Evidence:** [WORKSTREAM_1_EVIDENCE.md](./WORKSTREAM_1_EVIDENCE.md)  
**Canonical implementation:** `src/sscre/safety.py`, `src/sscre/compatibility.py`  
**Version policy:** increment minor for additive fields; increment major for semantic or
breaking serialization changes.

## Purpose

This artifact defines the bounded contracts for cache-reuse **decisions** and
**candidate-level traces**. Embedding similarity is retrieval evidence only; a
`SAFE` decision requires a later compatibility evaluation.

Evaluation **labels** (correctness, preference) are out of scope for v1.0.0 and
are defined in Workstream 1 step 3.

## Decision vocabulary

| Value | Meaning | Serve cached answer? |
|---|---|---|
| `SAFE` | Policy found enough compatibility evidence to reuse the selected candidate | Yes |
| `UNSAFE` | Known incompatibility (constraint, entity, dynamic query/candidate, similarity below threshold, explicit mismatch) | No — generate |
| `UNCERTAIN` | Reuse cannot be established safely (missing metadata, incomplete evidence, dependency/validator failure, temporal mismatch) | No — generate |

Strategy A and Strategy B exact-hash hits that skip compatibility use `SAFE`
with reason `exact_query_hash_match`. The default semantic strategy is `C`,
so exact hits on that path run `evaluate_candidate`. The public API exposes
only `SAFE`, `UNSAFE`, and `UNCERTAIN`.

## Core types

### `QueryMetadata`

Bounded signals: `intent`, `domain`, `entities`, `constraints`, `temporal_class`,
`output_format`. Defaults use `unknown` where extraction is ambiguous. Limits:
`MAX_METADATA_*` constants in `safety.py`. JSON shape via `to_dict()` /
`from_dict()`.

### `CandidateTrace`

Per-candidate evaluation record:

| Field | Required | Bounds / notes |
|---|---|---|
| `candidate_query_hash` | yes | non-empty |
| `similarity` | yes | `[-1.0, 1.0]` |
| `decision` | yes | `SAFE` \| `UNSAFE` \| `UNCERTAIN` |
| `reason` | yes | non-empty; see reason taxonomy |
| `candidate_order` | no (default `0`) | non-negative; rank in retrieval order |
| `stage` | no (default `compatibility`) | `retrieval` \| `compatibility` |
| `query_metadata` | no | bounded dict from `QueryMetadata.to_dict()` |
| `candidate_metadata` | no | bounded dict or `{}` if missing |

`freshness_class` and `cache_control_outcome` are optional typed fields on
the trace.

### `SafetyResult`

Aggregate cache-reuse outcome:

| Field | Required | Notes |
|---|---|---|
| `decision` | yes | aggregate decision |
| `strategy` | yes | non-empty (e.g. `"C"`) |
| `reason` | yes | non-empty |
| `similarity` | if `SAFE` | required with selected candidate |
| `selected_candidate_query_hash` | if `SAFE` | forbidden for non-`SAFE` |
| `candidate_traces` | no | ordered tuple of traces |

### `resolve_candidate_traces(traces, strategy=...)`

Precedence (failure-closed):

1. First trace with `decision == "SAFE"` wins (retrieval order).
2. Else if any `UNCERTAIN` → aggregate `UNCERTAIN`.
3. Else if traces non-empty → aggregate `UNSAFE`.
4. Empty traces → `UNSAFE`, reason `no candidates were retrieved`.

## Reason taxonomy (compatibility evaluator)

Produced by `evaluate_candidate()` in `compatibility.py`:

| Reason | Typical decision |
|---|---|
| `similarity_below_threshold` | `UNSAFE` |
| `dynamic_query_not_reusable` | `UNSAFE` |
| `candidate_metadata_missing` | `UNCERTAIN` |
| `candidate_is_dynamic` | `UNSAFE` |
| `constraint_mismatch:<key>` | `UNSAFE` |
| `incomplete_constraint_evidence` | `UNCERTAIN` |
| `entity_mismatch` | `UNSAFE` |
| `incomplete_entity_evidence` | `UNCERTAIN` |
| `intent_mismatch` / `domain_mismatch` / `format_mismatch` | `UNSAFE` |
| `missing_<field>_evidence` | `UNCERTAIN` |
| `temporal_class_mismatch` | `UNCERTAIN` |
| `compatible_metadata` | `SAFE` |

Additional operational reasons (not from pure evaluator):

| Reason | Typical decision |
|---|---|
| `safety_validator_error` | `UNCERTAIN` |
| `similarity_threshold_met` | `SAFE` (Strategy B retrieval-only) |

## Producers and consumers (v1 audit)

| Component | Role |
|---|---|
| `compatibility.evaluate_candidate` | Pure trace producer |
| `safety.resolve_candidate_traces` | Aggregate resolver used by Strategy C in `app.py` and by the compatibility baseline |
| `app.query` | Evaluates candidates, selects the first `SAFE`, and emits boundary traces |
| `baseline.run_compatibility_cache_baseline` | Keeps `UNSAFE` and `UNCERTAIN` in separate `decision_counts` |
| `QueryResponse` | Exposes `decision`, `reason`, and `candidate_traces` (`null` when no traces were collected) |

Operational trace emission: structured `cache_decision` logs in `app.py` and
optional `candidate_traces` on `QueryResponse` (`sscre.serialization` boundary).

## Serialization

- Metadata: `QueryMetadata.to_dict()` (stable key order not guaranteed; log JSON uses `sort_keys=True`).
- Traces in logs: `CandidateTrace.to_log_dict()` via `serialize_candidate_traces()`.
- API: Pydantic `QueryResponse` validates decision literals and similarity bounds.
