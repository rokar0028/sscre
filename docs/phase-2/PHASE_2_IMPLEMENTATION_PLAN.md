# SSCRE Phase 2 Implementation Plan

## Goal

Turn the SSCRE semantic-cache MVP into a reproducible evaluation system that
can support defensible conclusions about safety, reuse, quality, cost,
latency, freshness, and storage.

Phase 2 is an evaluation-depth milestone. It does not include cross-encoders,
adaptive thresholds, large-scale infrastructure, or multi-region deployment.
Those are Phase 3 work and require a separate hypothesis and pass/fail
criterion.

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
- [ ] The reviewed benchmark contains at least 500 labeled pairs.
- [ ] Human factual-correctness labels are collected.
- [ ] A real-provider run is recorded.
- [ ] Confidence-aware held-out results are frozen.

## Phase 2 definition of done

- [ ] The benchmark contains at least 500 reviewed pairs and validated,
  disjoint development and held-out splits.
- [ ] Every pair has independent compatibility, correctness, and preference
  fields where applicable.
- [ ] `SAFE`, `UNSAFE`, and `UNCERTAIN` decisions are explicit and tested.
- [ ] Candidate-level traces explain retrieval, rules, thresholds, freshness,
  and the final decision.
- [ ] Results include confidence intervals and Pareto plots.
- [ ] Freshness policies are compared on stable, semi-dynamic, and dynamic
  workloads.
- [ ] Failure categories and representative examples are reported.
- [ ] No-cache, exact-cache, embedding-only, and compatibility-aware
  baselines are rerun on the final held-out split.
- [ ] Real-provider evidence is included, or its absence and consequences are
  explicitly reported.
- [ ] PostgreSQL restart and concurrent-request behavior is tested or
  explicitly documented as unsupported.
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
evidence). The checked-in artifact is a **32-pair** working baseline; the
**500-pair** Phase 2 target remains open (`benchmark_validate --phase2`).

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
- [ ] A checked-in benchmark contains at least 500 reviewed pairs (32-pair
  working artifact; `--phase2` validation gate enforced in CLI).
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

- [ ] Missing credentials skip opt-in tests safely.
- [ ] At least one redacted real-provider run is reproducible, or the report
  explicitly states why it is unavailable.
- [ ] Provider errors preserve failure-closed cache behavior.
- [ ] Synthetic and real-provider results are labeled separately.
- [x] Completion evidence is linked:
  [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md). The record
  explicitly states that the credentialed provider run is unavailable.

## Workstream 5 — Complete evaluation and statistical reporting

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
- latency versus cost
- reuse versus storage footprint

Select an operating point using constraints written before held-out
evaluation. A higher hit rate is not a success if it violates the
false-positive or freshness constraint.

Acceptance criteria:

- [ ] The report includes confidence intervals, not only point estimates.
- [ ] Pareto artifacts can be regenerated from checked-in commands/config.
- [ ] Threshold selection is documented as development-only.
- [ ] The selected operating point satisfies the stated constraints.

## Workstream 6 — Freshness experiments

Evaluate at least three policy classes:

| Class | Example behavior |
|---|---|
| Stable | Long TTL for durable conceptual answers |
| Semi-dynamic | Short TTL for version or policy-sensitive answers |
| Dynamic | No reuse or very short TTL for current-state queries |

For each class, measure reuse, stale-answer exposure, latency, cost, and
storage. Test explicit invalidation where the existing design supports it.

Acceptance criteria:

- [ ] Workloads contain stable, semi-dynamic, and dynamic examples.
- [ ] TTL policy and invalidation behavior are reported separately.
- [ ] Dynamic queries cannot be served from expired or disallowed entries.

## Workstream 7 — Failure gallery and quality analysis

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

- [ ] Every false positive in the selected evaluation sample has a category.
- [ ] Failure counts and rates are included in the final report.
- [ ] Gallery rendering does not expose secrets or unapproved data.

## Workstream 8 — Operational verification

These checks support Phase 2 claims but must not be presented as universal
capacity guarantees.

Test:

- PostgreSQL restart during lookup, generation, insert, and cleanup
- connection loss and recovery
- concurrent requests for the same query from multiple processes
- duplicate prevention and transaction behavior
- eviction under concurrent writes
- bounded load against PostgreSQL

Record hardware, worker count, database version, workload size, p50/p95/p99,
throughput, errors, timeouts, storage growth, and evictions.

Acceptance criteria:

- [ ] No restart path serves an expired, unsafe, or unauthorized result.
- [ ] Multi-process behavior is verified or explicitly marked unsupported.
- [ ] The first measured bottleneck is documented.
- [ ] Load results include environment and workload limits.

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

1. [ ] Freeze decision, label, trace, and benchmark schemas.
2. [ ] Implement split validation and create the reviewed benchmark.
3. [ ] Add candidate-level traces and decision tests.
4. [ ] Collect correctness labels and adjudicate disagreements.
5. [ ] Integrate one opt-in real provider.
6. [ ] Freeze development thresholds and evaluate the held-out split.
7. [ ] Add confidence intervals, Pareto artifacts, and freshness experiments.
8. [ ] Build the failure gallery and update the final report.
9. [ ] Run PostgreSQL restart and concurrency verification.
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
