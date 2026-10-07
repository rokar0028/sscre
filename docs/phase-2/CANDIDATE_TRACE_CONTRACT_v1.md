# Candidate trace contract (v1.0.0)

**Implementation:** `src/sscre/safety.py` (`CANDIDATE_TRACE_CONTRACT_VERSION`)
**Status:** frozen for Phase 2 Workstreams 2–9
**Related:** [SAFETY_EVALUATION_CONTRACT_v1.md](./SAFETY_EVALUATION_CONTRACT_v1.md)

## Purpose

Operational traces explain per-candidate compatibility decisions without exposing
raw prompts, full answers, credentials, or provider secrets.

## `CandidateTrace` fields

| Field | Required | Notes |
|---|---|---|
| `candidate_query_hash` | yes | Stable identifier; not raw query text |
| `similarity` | yes | `[-1.0, 1.0]` |
| `decision` | yes | `SAFE` \| `UNSAFE` \| `UNCERTAIN` |
| `reason` | yes | Documented taxonomy (below) |
| `candidate_order` | yes for emitted traces | 1-based retrieval rank |
| `stage` | yes | `retrieval` \| `compatibility` |
| `query_metadata` | yes | Bounded `QueryMetadata.to_dict()` |
| `candidate_metadata` | yes | Bounded dict or `{}` |
| `freshness_class` | when evaluated | From candidate metadata / policy |
| `cache_control_outcome` | when evaluated | e.g. `fresh`, `expired`, `missing_expiration` |

Rule outcomes from the compatibility evaluator appear in `reason` (and
constraint keys in `constraint_mismatch:<key>`).

## `SafetyResult` aggregate

- `decision`, `strategy`, `reason`
- `selected_candidate_query_hash` and `similarity` only when `decision == SAFE`
- `candidate_traces` capped at `MAX_CANDIDATE_TRACES` (100)

## Serialization

Use `CandidateTrace.to_log_dict()` and `serialize_candidate_traces()` for logs
and reports. Metadata is re-validated through `QueryMetadata` and limited to
`MAX_TRACE_METADATA_JSON_BYTES` (8 KiB JSON).

## Reason taxonomy

| Reason | Typical decision |
|---|---|
| `similarity_below_threshold` | `UNSAFE` |
| `similarity_threshold_met` | `SAFE` (Strategy B retrieval-only) |
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
| `safety_validator_error` | `UNCERTAIN` |
| `exact_query_hash_match` | `SAFE` (Strategy A exact-hash boundary trace) |
| `cache_control_expired` | `UNSAFE` (freshness gate, `stage=retrieval`) |
| `cache_control_dynamic_disabled` | `UNSAFE` (freshness gate) |
| `cache_control_missing_expiration` | `UNCERTAIN` (freshness gate) |
| `cache_control_invalid_expiration` | `UNCERTAIN` (freshness gate) |

Aggregate resolver reasons (on `SafetyResult`, not candidate traces):

- `no candidate had sufficient compatibility evidence`
- `all candidates were incompatible`
- `no candidates were retrieved`

## Trace rules

- Retrieval order is deterministic (similarity ranking from search).
- Trace count is capped at serialization and in `resolve_candidate_traces()`.
- Reasons must pass `validate_trace_reason()` when constructing `CandidateTrace`.
