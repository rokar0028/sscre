# SSCRE Evaluation Baseline: Methods and Limitations

This document records the assumptions behind the Milestone 6 baseline
experiments.

## Label creation

The reviewed dataset contains manually reviewed query pairs. Reviewers assign:

- `reusable`: whether the answer for one query can safely answer the paired
  query.
- `compatibility_label`: whether the pair's requirements are compatible.
- `correctness_label`: whether the recorded reuse judgment is correct.
- `reason`: a short explanation for every non-reusable pair.

The dataset includes exact duplicates, whitespace-equivalent queries,
compatible paraphrases, and incompatible changes to language, format, entity,
audience, length, numeric values, and other constraints. Labels are stored
explicitly; evaluation must not infer compatibility or correctness from the
`reusable` field.

## Development and held-out data

`benchmarks/development.jsonl` is used for implementation and configuration
decisions. `benchmarks/held_out_test.jsonl` has disjoint record IDs and is
reserved for final reporting. Test labels must not be used to choose thresholds
or other configuration values. The evaluation command requires an explicit
split declaration and rejects a benchmark filename that does not match it.
The evaluator also checks the manifest path, dataset version, record count, and
reviewed-record ID coverage before running. Each pair is evaluated in both
directions where directional replay applies.

Keeping the held-out labels separate prevents tuning decisions from making the
final measurements appear better than they generalize to unseen pairs.

## Token estimates

The baseline consumes `input_tokens` and `output_tokens` reported by the model
client. The local mock client estimates both values with whitespace-separated
word counts. For an exact-cache hit, saved input tokens are estimated from the
normalized query and saved output tokens from the cached answer using the same
word-count method.

These are estimates, not provider billing-token counts. A production
evaluation should use the target model provider's tokenizer and usage fields.

## Cost assumptions

Input and output prices are configurable per 1,000 tokens. Exact-cache reports
also accept a per-request cache lookup cost and preprocessing cost. The checked
in development configuration sets all prices to `0.0` because no provider or
deployment pricing has been selected yet. Therefore its cost values are
accounting placeholders, not a claim that production requests are free.

## Latency assumptions

The no-cache baseline sums generation latency reported by the model client.
The exact-cache baseline sums generation latency for misses and measures cache
lookup/preprocessing time locally. The mock client is intentionally fast, so
local latency results are useful for comparing execution paths but are not
representative of a remote model service.

## What exact caching cannot measure

An exact cache only reuses normalized-query matches. It cannot measure:

- safe reuse for paraphrases or semantically similar queries;
- whether two different queries have equivalent answers;
- compatibility of unstated user, tenant, authorization, or freshness
  requirements;
- answer quality, factuality, or safety of a reused response;
- embedding quality, similarity thresholds, or false-positive semantic reuse;
- production network, provider, concurrency, eviction, and persistence costs.

Consequently, the exact-cache baseline is a control condition for measuring
literal reuse savings. It is not evidence that semantic retrieval is safe or
effective.

## Embedding-only Strategy B limitations

Milestone 7 adds Strategy B as an embedding-only comparison. It uses cosine
distance from pgvector (`<=>`) and reports similarity as `1 - distance`; the
threshold is selected on the development split and then evaluated once on the
held-out split. The held-out labels are not used for threshold selection.

The deterministic fake embedding client is useful for repeatable tests and
controlled ranking fixtures, but it is not evidence about production embedding
quality. It does not model provider semantics, network latency, rate limits, or
embedding drift. A high similarity score is therefore only a retrieval signal.
It does not establish compatible intent, entities, constraints, format,
authorization, or freshness. Compatibility-aware validation remains a later
milestone.

Embedding-provider failures and missing pgvector prevent semantic reuse. The
system may generate a response, but it does not persist an entry without a
valid embedding.

## Compatibility-aware Strategy C limitations

Strategy C uses deterministic rules rather than an additional LLM or
cross-encoder. It can reject explicit language, entity, format, domain, and
freshness conflicts, but it cannot reliably infer unstated requirements,
authorization context, tenant context, or answer correctness. `UNCERTAIN`
therefore means "generate conservatively", not "the query is invalid".

The compatibility evaluation reports both labels independently:
`correctness_label` describes the reviewed judgment quality, while
`compatibility_label` describes whether the paired requirements are compatible.
The reports also save a machine-readable failure gallery containing
embedding-only false positives caught by Strategy C, Strategy C false
positives, false negatives, and unnecessary abstentions. Each example includes
the pair ID, direction, similarity, predicted decision, expected labels,
reason, and failure category.

Failure-gallery examples are benchmark evidence, not proof of production
safety. Results depend on the reviewed dataset, deterministic fake embeddings,
rule coverage, threshold selection, and cache replay order.

Compatibility safety is distinct from Milestone 9 cache controls: TTL
expiration, answer deduplication, canonical-answer storage, LRU eviction, and
storage-cap enforcement are not inferred from these reports.

Reports include the Git commit and whether the worktree was dirty. A dirty
worktree means the commit alone is insufficient to reproduce the exact code
state; the report's configuration and source changes must also be preserved.

Milestone 7 evaluation reports are generated on demand from the versioned
datasets and configuration; generated report files are not checked in as
canonical artifacts. The initial pgvector implementation intentionally omits a
vector index until retrieval behavior and scale measurements justify one.

## Milestone 9 cache-control limitations

TTL is a policy-based freshness approximation. A non-expired answer may still
be factually stale, and expiration does not validate correctness. Dynamic
queries are rejected by default because a short TTL is not automatically a
safe freshness guarantee.

Canonical answer hashes deduplicate byte-identical UTF-8 content only. They do
not establish semantic equivalence, correctness, or compatibility. Query
metadata, temporal class, and TTL remain entry-specific; sharing an answer
body does not authorize sharing a cache decision.

Eviction improves bounded storage at the cost of future reuse. Replaying the
same workload after eviction can generate different answers and produce
different cache-hit, latency, and token results. LRU ordering is deterministic
for the same access sequence, but concurrent arrival order can change that
sequence.

Cache-control failures are failure-closed for reuse where the request path can
detect them; generated responses may still be returned without being cached.
The local storage evaluator measures deterministic lifecycle and storage
properties. It runs both deduplicating and non-deduplicating cache controls,
but still does not establish production concurrency or PostgreSQL performance.
Workload items may provide provider token counts, costs, and generation
latencies; otherwise reports explicitly label whitespace token counts and
configured synthetic generation latency. Synthetic latency is not a remote
provider measurement. PostgreSQL-specific verification requires
`SSCRE_DATABASE_URL`.

## Milestone 10 production-readiness limitations

The final report in `docs/internal/reports/MILESTONE_10_FINAL_EXPERIMENT_AND_INTERVIEW_REPORT.md`
consolidates local container, failure-path, baseline, and load evidence.
Its latency results use in-process deterministic clients and in-memory storage;
they do not represent remote provider or PostgreSQL capacity. The held-out
workload produced no cache hits for the evaluated baselines, so that result is
reported as observed coverage for that split rather than generalized evidence
that semantic reuse has zero recall.

## Phase 1 OPS lite (PostgreSQL / multi-process)

Phase 1 closed a **lite** subset of Workstream 8 (not full restart/load/concurrency
claims). See [`docs/phase-2/WORKSTREAM_8_OPS_LITE_EVIDENCE.md`](../phase-2/WORKSTREAM_8_OPS_LITE_EVIDENCE.md)
for scope, test name, and paper limitation wording.

- Request-path duplicate-generation coordination is **single-process** (in-process
  lock); multi-process and cross-host behavior is **unsupported** unless full WS8
  evidence exists.
- One PostgreSQL integration smoke test asserts **failure-closed** behavior when
  lookup fails after a persisted entry exists (HTTP 503, no cache hit).
- Do not cite Milestone 10 load numbers or this smoke test as production capacity
  or multi-worker safety guarantees.
