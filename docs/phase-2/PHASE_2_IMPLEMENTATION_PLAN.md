# SSCRE Phase 2 Implementation Plan

## Goal

Turn the SSCRE semantic-cache MVP into a reproducible evaluation system that
can support defensible conclusions about safety, reuse, quality, cost,
latency, freshness, and storage.

Phase 2 is an evaluation-depth milestone. It does not include cross-encoders,
adaptive thresholds, large-scale infrastructure, or multi-region deployment.
Those are Phase 3 work and require a separate hypothesis and pass/fail
criterion in [`docs/phase-3/PHASE3_PLAN.md`](../phase-3/PHASE3_PLAN.md).

## Source of truth

The scope is defined by the Phase 2 section of
`docs/SSCRE_PLAN.md`. The existing implementation baseline and production
readiness evidence are tracked in
`docs/phase-2/MILESTONE_11_REMAINING_GAPS_IMPLEMENTATION_PLAN.md`.

## Learning objectives

- [ ] Design a reviewed benchmark without split leakage.
- [ ] Separate compatibility, factual correctness, and preference labels.
- [ ] Quantify uncertainty with confidence intervals.
- [ ] Select an operating point using safety, reuse, cost, latency, and storage
  constraints.
- [ ] Compare synthetic and real-provider measurements without conflating them.
- [ ] Understand PostgreSQL restart, concurrency, and multi-process behavior.
- [ ] Design bounded observability and deployment safety gates.

## Current baseline

- [x] Core API, exact and semantic cache paths, compatibility checks, TTL,
  storage caps, and failure-closed behavior exist.
- [x] Deterministic fake providers and baseline evaluation paths exist.
- [x] Development, held-out, and synthetic-load report structure exists.
- [x] Docker Compose configuration and GitHub Actions CI are configured.
- [x] The reviewed benchmark contains at least 500 labeled pairs.
  - **615** pairs, `reviewed-query-pairs-2.0` ([BENCHMARK_500_SCALE_UP_EVIDENCE.md](./BENCHMARK_500_SCALE_UP_EVIDENCE.md)).
- [ ] Human factual-correctness labels are collected.
- [ ] A real-provider run is recorded.
- [x] Confidence-aware held-out results are frozen.
  - WS5 held-out comparison + statistics on `reviewed-query-pairs-2.0` (2026-10-08).

## Phase 2 definition of done

- [x] The benchmark contains at least 500 reviewed pairs and validated,
  disjoint development and held-out splits.
  - 400 / 215 / 615; `benchmark_validate --phase2 --production` passed (2026-10-08).
- [ ] Every pair has independent compatibility, correctness, and preference
  fields where applicable.
- [ ] `SAFE`, `UNSAFE`, and `UNCERTAIN` decisions are explicit and tested.
- [ ] Candidate-level traces explain retrieval, rules, thresholds, freshness,
  and the final decision.
- [x] Results include confidence intervals and Pareto plots.
  - WS5 held-out comparison + Pareto JSON ([WORKSTREAM_5_EVIDENCE.md](./WORKSTREAM_5_EVIDENCE.md), 2026-10-08).
- [x] Freshness policies are compared on stable, semi-dynamic, and dynamic
  workloads.
  - Four-arm development replay + frozen `conservative` held-out stable scope
    ([WORKSTREAM_6_EVIDENCE.md](./WORKSTREAM_6_EVIDENCE.md), 2026-10-09; held-out
    semi/dynamic unavailable).
- [ ] Failure categories and representative examples are reported.
- [x] No-cache, exact-cache, embedding-only, and compatibility-aware
  baselines are rerun on the final held-out split.
  - `artifacts/evaluation/workstream5-held-out-comparison.json` (615-pair scale, 2026-10-08).
- [x] Real-provider evidence is included, or its absence and consequences are
  explicitly reported.
  - Unavailable artifact + WS5 evidence § provider limitations (synthetic replay only).
- [x] PostgreSQL restart and concurrent-request behavior is tested or
  explicitly documented as unsupported.
  Bounded WS8 package 2026-10-11
  ([WORKSTREAM_8_EVIDENCE.md](./WORKSTREAM_8_EVIDENCE.md)): simulated
  failure-closed paths; live container restart skipped; two processes both
  generate; unique insert wins; bottleneck `not_reached`. Not a production
  capacity claim. Phase 1 lite:
  [WORKSTREAM_8_OPS_LITE_EVIDENCE.md](./WORKSTREAM_8_OPS_LITE_EVIDENCE.md).
- [ ] A dashboard is added only after the reports and data contracts are
  stable.
- [ ] Dual-model comparison is implemented only as a defined experiment.

## Workstream 1 — Freeze the evaluation contracts

Status: frozen for Workstreams 2–9. Do not introduce a second decision, label,
or trace model. Implementation evidence is in
[WORKSTREAM_1_EVIDENCE.md](./WORKSTREAM_1_EVIDENCE.md).

| Contract | Artifact |
|---|---|
| Decisions and candidate traces | [SAFETY_EVALUATION_CONTRACT_v1.md](./SAFETY_EVALUATION_CONTRACT_v1.md) |
| Trace bounds and reason taxonomy | [CANDIDATE_TRACE_CONTRACT_v1.md](./CANDIDATE_TRACE_CONTRACT_v1.md) |
| API, log, and report JSON | [SERIALIZATION_BOUNDARY_v1.md](./SERIALIZATION_BOUNDARY_v1.md) |
| Compatibility, correctness, and preference | [EVALUATION_LABEL_CONTRACT_v1.md](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md) |

Strategy C is the compatibility path. Strategy B still serves from similarity
alone (`similarity_threshold_met`) and is an experiment baseline, not this
contract.

### 1.1 Decision contract

Define the decision vocabulary in one shared module and use it in API
responses, traces, reports, and tests:

```text
SAFE       → reuse the candidate answer
UNSAFE     → do not reuse; generate a new answer
UNCERTAIN  → do not reuse; generate a new answer
```

The implementation must distinguish:

- `SAFE`: evidence supports reuse under the active policy.
- `UNSAFE`: a known incompatibility exists.
- `UNCERTAIN`: evidence is insufficient or a dependency failed.

`UNCERTAIN` must remain failure-closed. It must never be treated as a cache
hit.

### 1.2 Label contract

Keep these labels separate:

| Label | Question answered |
|---|---|
| Compatibility | Can the cached answer answer the new query? |
| Correctness | Is the answer factually and instructionally acceptable? |
| Preference | Which of two acceptable answers does a reviewer prefer? |

Do not infer correctness from preference or compatibility from embedding
similarity.

### 1.3 Trace contract

For each retrieved candidate, record bounded, non-sensitive fields:

- candidate identifier
- rank and similarity score
- freshness class and expiry outcome
- constraint/entity/intent comparison outcome
- validator rules that fired
- candidate decision
- final selected decision
- fallback reason, if generation occurred

Do not store credentials or unrestricted raw prompts/answers in operational
logs. Dataset artifacts may contain review text only where the project’s data
policy permits it.

## Workstream 2 — Build the reviewed benchmark

Implementation status and verification evidence:
[`WORKSTREAM_2_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_2_IMPLEMENTATION_PLAN.md),
[`benchmarks/README.md`](../benchmarks/README.md) (§ Workstream 2 completion
evidence). The checked-in artifact is the frozen **615-pair**
`reviewed-query-pairs-2.0` benchmark; `benchmark_validate --phase2
--production` passed on 2026-10-08. Correctness labels and real-provider
measurements remain separate open criteria.

### 2.1 Dataset schema

Add a versioned JSONL schema under `benchmarks/` containing at least:

- stable pair ID
- query A and query B
- expected reuse decision
- failure category
- freshness class
- domain and constraint metadata
- annotation source
- compatibility label
- correctness labels, when an answer is available
- preference label, only for an explicit comparison
- annotator and adjudication metadata

Keep source examples and IDs stable so reports can be reproduced.

### 2.2 Required categories

The benchmark must cover:

- exact duplicates
- paraphrases
- changed intent
- changed programming language or other constraints
- changed entity or subject
- changed output format
- temporal or freshness changes
- domain changes
- ambiguous or underspecified queries
- stale-answer cases

Include both positive and negative pairs. Do not construct a benchmark made
mostly of easy paraphrases.

### 2.3 Annotation and adjudication

Create an annotation guide defining:

- when a pair is `SAFE`, `UNSAFE`, or `UNCERTAIN`
- how to identify the primary failure category
- how to label correctness independently
- when preference is not applicable
- how disagreements are resolved
- how annotator identity and review status are recorded

Use at least two reviews for disputed or high-impact examples and record the
adjudicated result rather than silently overwriting disagreement.

### 2.4 Split validation

Create development and held-out manifests. Validation must fail closed when:

- a pair ID appears in both splits
- normalized source examples overlap across splits
- a duplicate ID exists
- a referenced dataset row is missing
- the schema version is unsupported

Threshold selection and policy tuning may use development data only. The
held-out split is read only after the operating point is frozen.

Acceptance criteria:

- [x] `benchmarks/README.md` documents the schema, annotation guide, and
  version (see Workstream 2 completion evidence).
- [x] A checked-in benchmark contains at least 500 reviewed pairs (`--phase2`
  validation gate enforced in CLI).
  - **615** pairs on `reviewed-query-pairs-2.0` (2026-10-08).
- [x] Split validation has tests for duplicate IDs and source leakage.
- [x] Evaluation output records dataset version and split name (`benchmark_artifact`).

## Workstream 3 — Implement and test decision depth

### 3.1 Candidate-level decisions

Strategy C already assigns one decision per candidate and aggregates with
`resolve_candidate_traces`. This workstream extends that depth; it does not
repeat the Workstream 1 contract freeze.

Required behavior:

- exact compatible matches can be `SAFE`
- known constraint or intent conflicts are `UNSAFE`
- similarity below the threshold is `UNSAFE`; incomplete evidence is
  `UNCERTAIN` (no separate borderline band)
- expired or dynamic candidates cannot be served
- repository, embedding, or validator failures cannot produce a cache hit

### 3.2 Decision-trace persistence

Use the existing trace/metadata conventions where possible. Persist only the
minimum data needed for evaluation and failure analysis. Bound trace size and
avoid duplicating complete answers.

Acceptance criteria:

- [x] Unit tests cover all three decisions
  ([WORKSTREAM_3_EVIDENCE.md](./WORKSTREAM_3_EVIDENCE.md)).
- [x] Integration tests verify that `UNCERTAIN` falls back to generation.
- [x] Candidate traces identify the rule or evidence causing the decision.
- [x] Trace output is deterministic for deterministic fake providers.
- [x] Failure paths are tested as failure-closed. PostgreSQL integration
  remains skipped when `SSCRE_DATABASE_URL` is unset (13 tests).

## Workstream 4 — Add real-provider measurement

### 4.1 Provider boundary

Keep fake providers as deterministic test doubles. Add one opt-in real-provider
implementation behind the existing provider interfaces with configuration for:

- provider and endpoint
- generation model
- embedding model
- bounded request timeout
- retry limit and backoff
- pricing inputs
- redacted experiment identifier

Credentials must come from the environment or secret manager and must never be
written to logs, reports, or checked-in configuration.

### 4.2 Measurement protocol

Record, separately for cache hits and misses:

- request latency and provider latency
- input and output token usage
- embedding calls and tokens
- retries, timeouts, and rate limits
- generated-answer cost
- wrapper overhead
- total estimated cost

Run a fixed dataset/configuration and record provider/model versions and
measurement date. Do not tune thresholds on held-out labels.

Acceptance criteria:

- [x] Missing credentials skip opt-in tests safely.
- [x] At least one redacted real-provider run is reproducible, or the report
  explicitly states why it is unavailable (unavailable artifact + evidence).
- [x] Provider errors preserve failure-closed cache behavior.
- [x] Synthetic and real-provider results are labeled separately.
- [x] Workstream 4 iteration 1 complete; completion evidence:
  [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md). Live observation
  deferred to a later iteration.

## Workstream 5 — Complete evaluation and statistical reporting

Status: **final** synthetic held-out package on `reviewed-query-pairs-2.0`
(2026-10-08). Live-provider measurements remain deferred. Evidence:
[`WORKSTREAM_5_EVIDENCE.md`](./WORKSTREAM_5_EVIDENCE.md).

- [x] Workstream 5 iteration 1 evidence links the held-out comparison,
  statistics, Pareto artifact, operating-point policy, and provider limitations.
- [x] Final statistical acceptance after the benchmark scale gate (615 pairs,
  regenerated WS5 artifacts).
- [ ] Live-provider measurements (Workstream 4 deferral) remain open.

### 5.1 Baselines

Rerun the same held-out workload against:

1. no cache
2. exact-match cache
3. embedding-only cache
4. compatibility-aware cache

Use the same provider assumptions, workload, and accounting rules where
possible. Report unavailable measurements instead of substituting estimates
without labeling them.

### 5.2 Metrics

Report at minimum:

- cache hit rate
- reuse coverage
- `SAFE`, `UNSAFE`, and `UNCERTAIN` rates
- false-positive rate
- precision of served reuse
- correctness of reused and generated answers
- downstream tokens saved
- embedding and generation tokens
- estimated cost
- p50, p95, and p99 latency
- cache entries, bytes, evictions, and growth
- metrics by failure category and freshness class

### 5.3 Uncertainty

Add bootstrap or binomial confidence intervals for proportions and an
appropriate interval method for latency, cost, and token distributions.
Document the method, sample count, seed, and resampling policy.

### 5.4 Pareto analysis

Generate plots or machine-readable artifacts showing trade-offs among:

- safety versus reuse
- false positives versus tokens saved
- cost versus safety
- latency versus cost
- reuse versus storage footprint

Select an operating point using constraints written before held-out
evaluation. A higher hit rate is not a success if it violates the
false-positive or freshness constraint.

Acceptance criteria (synthetic held-out package; live provider deferred):

- [x] The report includes confidence intervals, not only point estimates.
  - Default `statistics` attachment on `--baseline all` ([WORKSTREAM_5_EVIDENCE.md](./WORKSTREAM_5_EVIDENCE.md)).
- [x] Pareto artifacts can be regenerated from checked-in commands/config.
  - `python -m sscre.pareto` commands recorded in evidence (2026-10-08).
- [x] Threshold selection is documented as development-only.
  - `benchmarks/README.md` operating-point policy; held-out tests in `tests/test_benchmark.py`.
- [x] The selected operating point satisfies the stated constraints.
  - Held-out `max_false_positive_rate`: satisfied at threshold `0.95` (Pareto `selected_constraint`).

## Workstream 6 — Freshness experiments

Evidence: [`WORKSTREAM_6_EVIDENCE.md`](./WORKSTREAM_6_EVIDENCE.md) (complete
2026-10-09, Option A). Artifacts:
`artifacts/evaluation/workstream6-development-freshness.json`,
`workstream6-held-out-freshness.json`, `workstream6-invalidation.json`.

Evaluate at least three policy classes:

| Class | Example behavior |
|---|---|
| Stable | Long TTL for durable conceptual answers |
| Semi-dynamic | Short TTL for version or policy-sensitive answers |
| Dynamic | No reuse or very short TTL for current-state queries |

For each class, measure reuse, stale-answer exposure, latency, cost, and
storage. Test explicit invalidation where the existing design supports it.

Acceptance criteria:

- [x] Workloads contain stable, semi-dynamic, and dynamic examples.
  - Source benchmark 606 / 5 / 4; held-out stable-only evaluation per Option A.
- [x] TTL policy and invalidation behavior are reported separately.
- [x] Dynamic queries cannot be served from expired or disallowed entries.
  - Tested in `tests/test_workstream6_freshness.py`, `test_cache_controls.py`,
    and request-path integration tests.

## Workstream 7 — Failure gallery and quality analysis

Implementation plan:
[`WORKSTREAM_7_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_7_IMPLEMENTATION_PLAN.md).
Completion evidence:
[`WORKSTREAM_7_EVIDENCE.md`](./WORKSTREAM_7_EVIDENCE.md).
Phase 1 **P2-GALLERY** carryover remains the lite single-report HTML path;
Phase 2 WS7 adds the consolidated JSON/HTML package (`workstream7-quality-analysis`).

Create a browsable or static failure gallery after the data/report contract is
stable. Each example should include:

- anonymized or approved query pair
- cached answer outcome
- expected label
- actual decision
- similarity and relevant trace evidence
- failure category
- mitigation or open limitation

Add aggregate metrics by category so the gallery is not only anecdotal.

Acceptance criteria:

- [x] Every false positive in the selected held-out evaluation sample has a
  reviewed or runtime failure category (or documented exclusion) in the
  consolidated artifact (`false_positive_category_complete`; enrichment +
  `tests/test_workstream7_failure_gallery.py`).
- [x] Failure counts and rates by category appear in the consolidated JSON
  (`quality_analysis.by_failure_category` sourced from WS5 statistics).
- [x] Gallery and consolidated exports do not expose secrets or unapproved raw
  query text (`redact_operational_evaluation_report`, threshold-sweep tuple
  fix, `validate_redacted_report_payload` on save).
- [x] WS6 freshness protection vs stale exposure is attached as a bounded
  companion block (no WS7 replay of freshness policy).
- [x] Static HTML regenerates from documented commands (`sscre-failure-gallery-export`,
  `sscre-gallery-export`; see evidence doc).
- [x] Input artifact paths, schema versions, and aligned split manifest SHA are
  recorded in [`WORKSTREAM_7_EVIDENCE.md`](./WORKSTREAM_7_EVIDENCE.md).

## Workstream 8 — Operational verification

Status: **bounded package complete (2026-10-11)**. Plan:
[`WORKSTREAM_8_IMPLEMENTATION_PLAN.md`](./WORKSTREAM_8_IMPLEMENTATION_PLAN.md).
Evidence: [`WORKSTREAM_8_EVIDENCE.md`](./WORKSTREAM_8_EVIDENCE.md). Artifact:
`artifacts/operations/workstream8-operational-verification.json`.
Phase 1 lite remain a separate, smaller record:
[`WORKSTREAM_8_OPS_LITE_EVIDENCE.md`](./WORKSTREAM_8_OPS_LITE_EVIDENCE.md).
Do not cite Phase 4 in-memory scale
([`../phase-4/PHASE4_SCALE_EVIDENCE.md`](../phase-4/PHASE4_SCALE_EVIDENCE.md))
as PostgreSQL operational evidence.

These checks support Phase 2 claims but must not be presented as universal
capacity guarantees.

Measured (local PostgreSQL unless noted):

- simulated connection-loss / repository failure on lookup, generation,
  insert, and cleanup (not a live process or container restart)
- recovery after simulated failure (expiry, missing metadata, incompatibility,
  validation, and admin Bearer still enforced)
- same-query misses across two application processes
- uniqueness, transactions, and eviction under bounded contention
- bounded load (8 warmup / 32 requests / concurrency 4) with p50/p95/p99,
  throughput, errors, timeouts, storage growth, and evictions
- first bottleneck: `not_reached` (observation only)

Still unsupported: live container/process restart during write; cross-process
generation coordination; multi-host; 1K–100K Q/day; production capacity or SLA.

Acceptance criteria:

- [x] No tested failure path serves an expired, unsafe, or unauthorized result.
  Simulated `simulated_drop` / `simulated_repository_failure` only. Live
  container restart skipped (`SSCRE_WS8_LIVE_POSTGRES_RESTART` unset).
- [x] Multi-process behavior is verified or explicitly marked unsupported.
  Verified: two processes both generate; PostgreSQL `UNIQUE` accepts one
  insert. Cross-process generation lock remains unsupported.
- [x] The first measured bottleneck is documented.
  `not_reached`; `result_class=observation`; no optimization.
- [x] Load results include environment and workload limits.
  Windows-11, Python 3.14.5, PostgreSQL 16.15, 1 process / 1 worker,
  caps 8 / 10000. Not a production capacity guarantee.

## Workstream 9 — Dashboard and dual-model experiment gates

### Dashboard

Add a dashboard only after report data is stable. It should read generated
artifacts rather than implement a second metrics pipeline. Initial views:

- operating-point summary
- baseline comparison
- confidence intervals
- Pareto plots
- failure-category counts
- freshness results
- storage and eviction results

### Dual-model comparison

Implement dual-model fallback only with a written experiment definition:

- hypothesis
- model pair
- prompt and generation settings
- preference question
- correctness review process
- incremental token/cost budget
- success criterion
- stopping rule

Do not use preference as a proxy for factual correctness.

Acceptance criteria:

- [ ] Dashboard values match the report artifacts.
- [ ] Dual-model output is opt-in and absent from the default MVP path.
- [ ] Preference and correctness are reported independently.

## Recommended execution order

1. [x] Freeze decision, label, trace, and benchmark schemas (Workstream 1).
2. [x] Implement split validation and create the reviewed benchmark (Workstream 2).
3. [x] Add candidate-level traces and decision tests (Workstream 3).
4. [ ] Collect correctness labels and adjudicate disagreements.
5. [x] Integrate one opt-in real provider (Workstream 4 iteration 1; live observation deferred).
6. [x] Freeze development thresholds and evaluate the held-out split (Workstream 5, 2026-10-08).
7. [x] Add confidence intervals, Pareto artifacts, and freshness experiments.
  - [x] Confidence intervals and Pareto artifacts (Workstream 5).
  - [x] Freshness policy experiments (Workstream 6;
    [WORKSTREAM_6_EVIDENCE.md](./WORKSTREAM_6_EVIDENCE.md), 2026-10-09).
8. [x] Build the failure gallery and update the final report.
  (Phase 1: static HTML via `sscre.gallery_export`; not full WS7 API dashboard.)
9. [x] Run PostgreSQL restart and concurrency verification.
  Bounded WS8 package 2026-10-11
  ([WORKSTREAM_8_EVIDENCE.md](./WORKSTREAM_8_EVIDENCE.md)). Live container
  restart skipped. Not a production capacity guarantee. Phase 1 lite remains
  [WORKSTREAM_8_OPS_LITE_EVIDENCE.md](./WORKSTREAM_8_OPS_LITE_EVIDENCE.md).
10. [ ] Add the dashboard or dual-model experiment only if its gate is met.

## Verification commands

Run from the repository root:

```bash
python -m pytest -q
python -m sscre evaluate --config experiments/threshold_sweep_v1.yaml
docker compose config
```

Add benchmark, split, report, and plot commands to
`benchmarks/README.md` as they become available. Record command results and
dataset/configuration versions in the final experiment report.

## Out of scope for this document

- Cross-encoder validator implementation
- Adaptive per-domain thresholds
- Quantized embedding rollout
- 1K–100K production-scale capacity claims
- Multi-region deployment
- Unbounded observability or a second analytics stack
- Admin mutation endpoints without a documented operational need
