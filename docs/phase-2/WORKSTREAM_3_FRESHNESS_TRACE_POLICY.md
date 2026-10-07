# Workstream 3 freshness trace policy

**Status:** adopted for Phase 2 Workstream 3 step 3  
**Related:** [CANDIDATE_TRACE_CONTRACT_v1.md](./CANDIDATE_TRACE_CONTRACT_v1.md)

## Decision

Ineligible cache entries are **not** dropped before tracing. Each considered
candidate emits a bounded trace at **`stage=retrieval`** before compatibility
evaluation runs.

| `cache_control_outcome` | Trace `decision` | Trace `reason` |
|---|---|---|
| `expired` | `UNSAFE` | `cache_control_expired` |
| `dynamic_entries_disabled` | `UNSAFE` | `cache_control_dynamic_disabled` |
| `missing_expiration` | `UNCERTAIN` | `cache_control_missing_expiration` |
| `invalid_expiration` | `UNCERTAIN` | `cache_control_invalid_expiration` |

Fresh entries proceed to `evaluate_candidate_boundary()` at
`stage=compatibility` with `freshness_class` and `cache_control_outcome`
populated from TTL policy evaluation.

Public decision vocabulary remains `SAFE`, `UNSAFE`, and `UNCERTAIN` only.
Aggregate response decisions use `resolve_candidate_traces()` when traces exist.

## Limitation

Repository search returns stored neighbors inside `top_k`, including expired
and TTL-less rows, so the request path can trace them. Entries removed by
storage maintenance before lookup cannot be traced; reports must not claim
freshness coverage for candidates that were never retrieved.
