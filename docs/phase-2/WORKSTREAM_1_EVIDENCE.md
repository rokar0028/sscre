# Workstream 1 evidence

Frozen contracts for Phase 2 Workstreams 2–9. This record is the handoff
from Workstream 1. It is not a provider or benchmark experiment.

## Contracts

- [x] Decisions and candidate traces:
  [SAFETY_EVALUATION_CONTRACT_v1.md](./SAFETY_EVALUATION_CONTRACT_v1.md)
- [x] Trace bounds and reason taxonomy:
  [CANDIDATE_TRACE_CONTRACT_v1.md](./CANDIDATE_TRACE_CONTRACT_v1.md)
- [x] API, log, and report JSON:
  [SERIALIZATION_BOUNDARY_v1.md](./SERIALIZATION_BOUNDARY_v1.md)
- [x] Compatibility, correctness, and preference:
  [EVALUATION_LABEL_CONTRACT_v1.md](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
- [x] Parent plan points Workstreams 2–9 at those artifacts:
  [PHASE_2_IMPLEMENTATION_PLAN.md](./PHASE_2_IMPLEMENTATION_PLAN.md)

`SAFE` is the only decision that can select a candidate and include a
similarity. `UNSAFE` and `UNCERTAIN` both fall back to generation and stay
separate in API traces and in compatibility-baseline `decision_counts`.

## Verification (2026-10-06)

- [x] Full suite:

```bash
python -m pytest -q
```

230 passed, 13 skipped. The skips are `tests/test_postgres_integration.py`
because `SSCRE_DATABASE_URL` is unset.

- [x] Report separation:
  `test_compatibility_report_keeps_unsafe_and_uncertain_distinct`.
- [x] Saved reports use `BOUNDARY_SERIALIZATION_VERSION` and sorted keys:
  `test_saved_report_uses_boundary_schema_version`.
- [x] Decision logs reject `answer`, `authorization`, and `api_key`.
  The generation-failure log uses decision `UNCERTAIN`, reason
  `generation_failed`, `candidate_traces: null`, and does not include the
  query text. A plain miss with no traces is `UNSAFE` /
  `no candidates were retrieved`. The default semantic strategy is `C`.
- [x] Editor diagnostics on the changed Python files: none. This repository
  does not configure Ruff or Flake8.

## Known limits

- [ ] Strategy B still serves from similarity alone
  (`similarity_threshold_met`) and records only the first retrieved
  candidate. It remains an explicit opt-in. Strategy C is the default and
  the compatibility contract path.
- [ ] PostgreSQL integration tests were not run.
- [ ] No real-provider measurement is included. Workstream 4 owns that run.
