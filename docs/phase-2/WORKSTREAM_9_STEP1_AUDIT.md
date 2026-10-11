# Workstream 9 Step 1 Audit

## Status

**Complete (2026-10-11).**

This audit freezes the WS9 dashboard input protocol and the dual-model
experiment-definition boundary. It does not implement a dashboard, run
provider requests, add a dual-model fallback, or claim that the current
artifacts are one fully aligned measurement package.

Plan:
[`WORKSTREAM_9_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_9_IMPLEMENTATION_PLAN.md).

## Audit objective

Inventory the existing WS5–WS8 artifacts, validators, serialization boundary,
measurement environments, and known metadata mismatches before dashboard code
is added. The audit distinguishes:

- aligned held-out evaluation artifacts;
- development-only selection provenance;
- independent freshness-invalidation and operational evidence;
- optional provider artifacts that are not aligned with the current Phase 2
  held-out package.

## Environment snapshot

- [x] HEAD: `74c772d8e08b954111a6c524b8745cbf387bf895`
- [x] Branch: `phase4/setup`
- [x] Python: `3.14.5`
- [x] Installed package versions: `sscre 0.1.0`, `fastapi 0.142.2`,
  `psycopg 3.3.6`, `pytest 9.1.1`, `httpx 0.28.1`
- [x] Working tree: dirty; existing uncommitted WS8 implementation/evidence
  changes, WS9 plan/index changes, and `tests/test_postgres_eviction_scope.py`
  are present. No WS9 runtime implementation exists.
- [x] Operating system and hardware for the WS8 operational source:
  Windows-11-10.0.26200-SP0, AMD64, 8 CPUs.

The dirty working tree is recorded as context. Artifact commit identities are
preserved from each source artifact; the dashboard must not rewrite them as
the current HEAD.

## Source inventory

All nine declared default/optional source paths existed and contained valid
JSON during this audit. Existing boundary validators passed for the applicable
artifacts.

| Source | Schema metadata | Dataset / split | Manifest | Environment / time | Alignment |
|---|---|---|---|---|---|
| `artifacts/evaluation/workstream5-held-out-comparison.json` | top `1.0.0`; statistics `evaluation-statistics-1.0`; failure gallery `failure-gallery-1.0` | `reviewed-query-pairs-2.0` / held-out | `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51` | `synthetic_replay`; `2026-10-10T15:07:16.191026+00:00` | Primary aligned evaluation source |
| `artifacts/evaluation/workstream5-held-out-pareto.json` | Pareto `evaluation-pareto-1.0` | `reviewed-query-pairs-2.0` / held-out | Not recorded in artifact | `synthetic_replay`; timestamp not recorded | Same dataset/split; manifest identity must display as unavailable |
| `artifacts/evaluation/workstream6-development-freshness.json` | top `1.0.0`; freshness `freshness-evaluation-1.0`; package `1.0` | `reviewed-query-pairs-2.0` / development | `c0109b36346442858d712ec13c183c8178ebb3e244b082f845cb7426750d8bbd` | `synthetic_replay`; `2026-10-08T18:12:14.818822+00:00` | Development selection provenance only; not merged with held-out metrics |
| `artifacts/evaluation/workstream6-held-out-freshness.json` | top `1.0.0`; freshness `freshness-evaluation-1.0`; package `1.0` | `reviewed-query-pairs-2.0` / held-out | `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51` | `synthetic_replay`; `2026-10-10T15:08:01.377467+00:00` | Primary aligned freshness source |
| `artifacts/evaluation/workstream6-invalidation.json` | definition `1.0`; artifact `workstream6_invalidation` | `reviewed-query-pairs-2.0` / no split | Not recorded in artifact | `synthetic_repository`; timestamp not recorded | Independent repository-boundary evidence |
| `artifacts/evaluation/workstream7-quality-analysis.json` | failure gallery `failure-gallery-1.0`; kind `workstream7-quality-analysis` | `reviewed-query-pairs-2.0` / held-out | `68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51` | `synthetic_replay`; `2026-10-10T15:08:29.186282+00:00` | Primary aligned quality source |
| `artifacts/operations/workstream8-operational-verification.json` | `ws8-ops-1.0`; kind `workstream8-operational-verification` | No evaluation dataset/split | Not applicable | Windows-11 local PostgreSQL; measured `2026-10-10T16:31:04.756865+00:00` | Independent operational source |
| `artifacts/evaluation/workstream4-provider-comparison.json` | `provider-measurement-comparison-1.0` | `reviewed-query-pairs-1.1` / development | Not recorded in artifact | `comparison`; `2026-10-07T17:06:49.445525+00:00` | Optional but not comparable with Phase 2 held-out sources |
| `artifacts/evaluation/workstream4-real-provider-unavailable.json` | `real-provider-measurement-1.0` | `reviewed-query-pairs-1.1` / development | Not recorded | `real_provider`; unavailable; `2026-10-07T16:43:08.937690+00:00` | Optional unavailable record; never substitute its values |

Current `benchmarks/split_manifest.json` has SHA-256
`68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51`.
Therefore the WS5 held-out comparison, WS6 held-out freshness artifact, and
WS7 quality artifact are aligned to the current manifest. The WS6 development
artifact's `c0109b…` identity is retained as a historical/provenance
indicator and is not treated as a held-out metric input.

## Existing validation and redaction boundaries

- [x] `validate_redacted_report_payload` passed for all seven WS5–WS8
  artifacts.
- [x] `validate_freshness_artifact_package` passed for both WS6 freshness
  artifacts.
- [x] `validate_consolidated_quality_analysis` and
  `validate_failure_gallery_redacted` passed for the WS7 artifact.
- [x] `src/sscre/serialization.py` rejects credential-like and raw-content
  keys including `answer`, `prompt`, `query`, `query_a`, `query_b`,
  `query_text`, `secret`, `token`, and `api_key`.
- [x] WS7's failure-gallery validators require bounded section shapes and
  reject forbidden example fields.
- [x] No equivalent WS9 dashboard validator or bounded HTML renderer exists
  yet; those belong to later implementation steps.
- [x] No dual-model runner or default application fallback exists.

The WS9 loader must reuse these boundaries and add a dashboard-specific
boundary for source references, unavailable blocks, display bounds, and HTML
escaping. It must not assume that passing JSON parsing alone means an
artifact is semantically aligned.

## Frozen dashboard input protocol

### Package and section schemas

The dashboard package schema is frozen as:

```text
dashboard_schema_version = workstream9-dashboard-1.0
```

The package contains these fixed section names:

```text
operating_point
baseline_comparison
confidence_intervals
pareto
failure_categories
freshness
operations
provider_measurements
limitations
```

Each section must carry a source reference and one of:

```text
status = available
status = unavailable
status = not_comparable
status = metadata_mismatch
```

Unavailable or non-comparable sections require a non-empty reason. The
dashboard package is a bounded view manifest, not a replacement for upstream
artifacts and not a new statistics schema.

### Required and optional source behavior

| Source | Sections | Step 1 rule |
|---|---|---|
| WS5 held-out comparison | `operating_point`, `baseline_comparison`, `confidence_intervals` | Required for those sections; malformed or missing input fails export rather than producing a successful empty dashboard |
| WS5 held-out Pareto | `pareto` | Required for an available Pareto section; absent manifest identity is displayed as `not_recorded`, not invented |
| WS6 development freshness | operating-point/freshness provenance | Optional for rendering; if present, show development split and manifest separately from held-out metrics |
| WS6 held-out freshness | `freshness` | Required for an available held-out freshness section; validation or alignment failure produces an explicit unavailable/mismatch result |
| WS6 invalidation | `freshness` invalidation subsection | Optional repository-boundary companion; missing or schema-invalid input is unavailable, never a zero invalidation count |
| WS7 quality analysis | `failure_categories` | Required for an available failure-category section; use copied aggregates and bounded examples only |
| WS8 operational verification | `operations` | Required for an available operations section; keep it independent from evaluation-dataset identity |
| WS4 provider comparison/unavailable | `provider_measurements` | Optional; current `reviewed-query-pairs-1.1` development artifacts are `not_comparable` to the Phase 2 held-out package |

Primary held-out evaluation identity is the tuple:

```text
dataset_version = reviewed-query-pairs-2.0
evaluation_split = held-out
split_manifest_sha256 = 68912e3b1221aae9c0b1b40d6b26ad351c211057898eb4f1e3b1bb87da8b1e51
```

WS5 comparison, WS6 held-out freshness, and WS7 quality may share this
identity. WS6 development selection may be displayed as provenance but must
not be merged into that tuple when computing or labeling held-out results.

### Fail-closed rules

- Missing or malformed input for a section marked required causes a non-zero
  export result; the dashboard must not be published as a complete success.
- Missing optional input produces a bounded `unavailable` section with a
  reason, source path, and expected schema.
- Dataset, split, or manifest mismatch on an aligned merge produces
  `metadata_mismatch`; it must not be silently combined.
- A missing manifest is distinct from a manifest mismatch. The dashboard may
  display the source with `manifest_status=not_recorded`, but must not claim
  manifest alignment.
- An upstream artifact's explicit stale, superseded, or unavailable status is
  copied as a limitation. WS9 does not invent a wall-clock freshness
  threshold.
- Synthetic, simulated, repository-boundary, and real-provider environments
  remain separate values and labels.
- Absent values remain `null` or an explicit unavailable record; they are
  never converted to zero, an empty success, or a passed constraint.
- Diagnostic mismatch overrides, if implemented later, must record the
  mismatch in the output and must not change the source values.

### Read-only transformation rules

Allowed:

- selecting bounded fields already present in a source artifact;
- preserving source metadata and paths;
- ordering sections and rows;
- formatting numbers, timestamps, and categorical statuses;
- rendering an existing aggregate or bounded example.

Not allowed:

- replaying benchmark requests;
- recomputing rates, intervals, Pareto dominance, freshness exposure,
  category counts, storage totals, or operational metrics;
- merging incompatible datasets or measurement environments;
- inferring correctness from preference, compatibility, or a dashboard label;
- embedding unrestricted source rows into HTML.

## Frozen dual-model experiment schema boundary

The experiment-definition schema is frozen separately as:

```text
dual_model_experiment_schema_version = workstream9-dual-model-experiment-1.0
```

The planned configuration path remains
`experiments/workstream9_dual_model_v1.json`. Its required groups are:

- identity: experiment ID, schema version, hypothesis, competing
  interpretation;
- models: model A/B, providers, endpoint origins, model/configuration
  versions;
- generation: prompt template/version, settings, timeout, retry, output
  bounds;
- sample: dataset, split, sample selection, exclusions;
- review: preference question, tie/abstain rules, correctness rubric,
  reviewer count, adjudication, or explicit correctness-unavailable status;
- budget: request, token, cost, time, and reviewer limits;
- decision: minimum sample, success criterion, confidence method if used,
  and stopping rule;
- safety: redaction, retention, opt-in flag, and default-disabled behavior.

This freezes the shape only. It does not approve a model pair, provider
request, budget, sample, or run. A preference result remains a preference
result unless separate correctness review supports a correctness claim.

## Known limitations carried into WS9

- Current WS5/WS6/WS7 evidence is synthetic replay, not live-provider
  evidence.
- The held-out split has sparse/unavailable freshness classes as documented
  by WS6.
- The WS5 reuse-vs-storage Pareto plane is unavailable because a matching
  held-out storage measurement is not present.
- WS6 development provenance is tied to an older manifest and is not aligned
  with the current held-out identity.
- WS8 is a bounded local PostgreSQL package and does not establish production
  capacity, SLA, multi-host, multi-region, live-provider, or distributed
  duplicate-generation claims.
- WS4 provider artifacts use dataset `reviewed-query-pairs-1.1` and
  development scope; they cannot be used as Phase 2 held-out provider
  comparisons.
- Correctness labels are unavailable for the current held-out package.

## Verification record

| Check | Result |
|---|---|
| Git/environment snapshot | Passed; recorded above |
| Default and optional source existence | 9/9 paths existed |
| JSON parse and top-level object check | 9/9 passed |
| Existing redaction validator | 7/7 WS5–WS8 artifacts passed |
| Existing WS6 freshness validator | 2/2 freshness artifacts passed |
| Existing WS7 quality/gallery validators | Passed |
| Current benchmark manifest hash | Passed; current file is `68912e…` |
| Cross-artifact identity audit | Passed with documented WS6 development and WS4 provider mismatches |

Focused regression and full-suite verification belong to Step 9 after code is
added. Step 1 added documentation only and did not alter runtime behavior.

