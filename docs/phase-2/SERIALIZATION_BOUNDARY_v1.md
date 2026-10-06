# Serialization boundary (v1.0.0)

**Module:** `sscre.serialization` (`BOUNDARY_SERIALIZATION_VERSION`)  
**Status:** frozen for Phase 2 Workstreams 2–9

## Emitters

| Path | What is serialized |
|---|---|
| `POST /v1/query` | `QueryResponse` (includes optional `candidate_traces`) |
| `cache_decision` logs | `build_cache_decision_log()` / `dumps_cache_decision_log()` |
| Evaluation reports | `attach_evaluation_report_schema()` via `baseline._save_report` |
| Failure examples | `evaluation_labels` + optional `candidate_traces` (Strategy C baseline) |

Saved evaluation JSON applies `redact_operational_evaluation_report()` so failure
galleries omit reviewed `query_a` / `query_b` text (record IDs and labels remain).

## Canonical shapes

- **Candidate trace:** `CandidateTrace.to_log_dict()` (see trace contract v1).
- **Trace list:** `boundary_candidate_traces()` → JSON list or `null`.
- **Safety aggregate:** `serialize_safety_result_for_boundary()`.

Optional fields use JSON **`null`** when absent (`candidate_traces`, similarity,
freshness, cache control).

## Bounds

- Trace count: `MAX_CANDIDATE_TRACES` (100).
- Per-trace metadata: `MAX_TRACE_METADATA_JSON_BYTES` (8 KiB).
- Combined trace array: `MAX_BOUNDARY_TRACE_JSON_BYTES`.

## Safety

Decision logs and trace objects must not include answers, raw queries, prompts,
or credential fields (`authorization`, `token`, `secret`, etc.). Validation is
enforced in `build_cache_decision_log()`.
