# Workstream 9 — dashboard and dual-model evidence

**Status:** Steps 1–9 complete (2026-10-11). Dashboard export and regression
tests are verified. Dual-model live execution, model-pair approval, and budget
approval remain deferred. This is not a production analytics service, live
provider quality claim, or default-path model-routing change.

**Parent:** [WORKSTREAM_9_IMPLEMENTATION_PLAN.md](./WORKSTREAM_9_IMPLEMENTATION_PLAN.md)  
**Step 1 audit:** [WORKSTREAM_9_STEP1_AUDIT.md](./WORKSTREAM_9_STEP1_AUDIT.md)

## Implementation identity

- [x] Branch `phase4/setup` (ahead of origin when recorded).
- [x] HEAD `1fc78ac35f7a6298024671563ddb3374c6d47034` at evidence authoring.
- [x] Python 3.14.5 on Windows; working tree dirty (WS9 code and artifacts
  uncommitted).
- [x] Modules: `src/sscre/dashboard.py`, `src/sscre/dual_model.py`.
- [x] CLIs: `python -m sscre.dashboard` / `sscre-dashboard-export`;
  `python -m sscre.dual_model` / `sscre-dual-model`.

## Dashboard schema and source manifest

- [x] Dashboard schema: `workstream9-dashboard-1.0`
  (`artifact_kind`: `workstream9-dashboard`).
- [x] Metric source policy: `upstream_artifacts` (no replay or re-aggregation).
- [x] Default WS5–WS8 inputs frozen in
  [WORKSTREAM_9_STEP1_AUDIT.md](./WORKSTREAM_9_STEP1_AUDIT.md).

| Input | Default path | Required for |
| --- | --- | --- |
| WS5 comparison | `artifacts/evaluation/workstream5-held-out-comparison.json` | operating point, baselines, intervals |
| WS5 Pareto | `artifacts/evaluation/workstream5-held-out-pareto.json` | Pareto |
| WS6 development freshness | `artifacts/evaluation/workstream6-development-freshness.json` | operating-point provenance |
| WS6 held-out freshness | `artifacts/evaluation/workstream6-held-out-freshness.json` | freshness |
| WS6 invalidation | `artifacts/evaluation/workstream6-invalidation.json` | freshness / invalidation |
| WS7 quality | `artifacts/evaluation/workstream7-quality-analysis.json` | failure categories |
| WS8 operations | `artifacts/operations/workstream8-operational-verification.json` | operations |
| WS4 provider comparison | `artifacts/evaluation/workstream4-provider-comparison.json` | optional provider row |
| WS4 provider unavailable | `artifacts/evaluation/workstream4-real-provider-unavailable.json` | optional provider row |

Primary held-out identity on the default package:
`split_manifest_sha256` =
`0aca5b8d63621b3118886f40b1b626b13a8bd58a8c1a9c27d0728fb2902e14d9`
(regenerated 2026-10-12; see
[`PHASE_2_REMEDIATION_EVIDENCE.md`](./PHASE_2_REMEDIATION_EVIDENCE.md) § Step 2),
`dataset_version` = `reviewed-query-pairs-2.0`.

## Dashboard outputs

| Output | Path |
| --- | --- |
| JSON package | `artifacts/evaluation/workstream9-dashboard.json` |
| Static HTML | `artifacts/evaluation/workstream9-dashboard.html` |

Regeneration (repository root):

```powershell
python -m sscre.dashboard `
  --comparison artifacts/evaluation/workstream5-held-out-comparison.json `
  --pareto artifacts/evaluation/workstream5-held-out-pareto.json `
  --freshness-development artifacts/evaluation/workstream6-development-freshness.json `
  --freshness-held-out artifacts/evaluation/workstream6-held-out-freshness.json `
  --invalidation artifacts/evaluation/workstream6-invalidation.json `
  --quality artifacts/evaluation/workstream7-quality-analysis.json `
  --operations artifacts/operations/workstream8-operational-verification.json `
  --json-output artifacts/evaluation/workstream9-dashboard.json `
  --html-output artifacts/evaluation/workstream9-dashboard.html
```

Deterministic fields: all section payloads and `input_artifacts` metadata
except `generation.generated_at`, `generation.git_commit`, and
`generation.git_worktree_dirty`.

## Dual-model experiment and result

| Artifact | Path |
| --- | --- |
| Experiment definition (disabled) | `experiments/workstream9_dual_model_v1.json` |
| Unavailable result package | `artifacts/evaluation/workstream9-dual-model-v1.json` |

Experiment schema: `workstream9-dual-model-experiment-1.0`.  
Result schema: `workstream9-dual-model-result-1.0`.

Unavailable packaging (no provider calls):

```powershell
python -m sscre.dual_model --package-unavailable `
  --config experiments/workstream9_dual_model_v1.json `
  --output artifacts/evaluation/workstream9-dual-model-v1.json
```

Live execution requires `--opt-in`, enabled definition, approved model pair
and budget, and credentialed provider configuration. **Not run** for this
evidence record.

## Verification (2026-10-11)

```powershell
python -m pytest -q tests/test_workstream9_dashboard.py
python -m pytest -q tests/test_workstream9_dual_model.py
python -m pytest -q
```

Results:

- [x] `tests/test_workstream9_dashboard.py` → **19 passed**.
- [x] `tests/test_workstream9_dual_model.py` → **16 passed**.
- [x] Combined WS9 tests → **35 passed**.
- [x] Full suite → **740 passed**, 15 skipped, 21 deselected; one existing
  FastAPI/httpx deprecation warning.

Dashboard export command above → passed (JSON + HTML written).

## Regression coverage (Step 9)

- [x] Input loading and metadata alignment (`metadata_mismatch`, primary
  identity).
- [x] Source-value fidelity per section (operating point, intervals, failure,
  operations, and existing section assertions).
- [x] Mutated upstream value copied without recomputation.
- [x] Optional provider sources absent → explicit unavailable.
- [x] Malformed / missing required sources fail closed.
- [x] Redaction, HTML escaping, bounds, accessibility landmarks.
- [x] CLI non-zero exit on export failure; `--help` exits 0.
- [x] Deterministic JSON except documented generation metadata.
- [x] Dual-model disabled-by-default, budget stops, preference/correctness
  separation, unavailable packaging.

## Skipped gates and limitations

- [ ] User implementation gate: explicit approval to treat the dashboard as
  the bounded delivery form (optional product gate; implementation artifacts
  exist).
- [ ] Dual-model approval gate: model pair and budget (`pending_approval` in
  the checked-in definition; experiment definition only).
- [ ] Live dual-model provider run (deferred; unavailable artifact packaged).
- [x] WS5–WS7 default evidence is **synthetic replay**, not live-provider
  measurement.
- [x] WS6 development vs held-out **split** differs by design; dashboard may
  record `provenance_only_manifest_mismatch` for development provenance while
  repo manifest lineage matches on regeneration (remediation Steps 2–3).
- [x] WS5 held-out storage Pareto plane unavailable; dashboard marks storage
  unavailable on the Pareto view.
- [x] WS4 provider artifacts use dataset 1.1 / development scope;
  `provider_measurements` is `not_comparable`, not a Phase 2 held-out claim.
- [x] Correctness labels unavailable; dashboard and dual-model results do not
  infer correctness from preference.
- [x] Dual-model unavailable artifact states it is not a production quality,
  cost, latency, or capacity guarantee.

## Handoff

- [x] Parent plan updated:
  [PHASE_2_IMPLEMENTATION_PLAN.md](./PHASE_2_IMPLEMENTATION_PLAN.md) Workstream 9.
- [x] Phase 2 index lists this evidence file.
- [x] Phase 3 transition distinguishes artifact-reading dashboard from a second
  analytics stack and dual-model preference from correctness
  ([`PHASE3_TRANSITION.md`](../internal/PHASE3_TRANSITION.md)).
