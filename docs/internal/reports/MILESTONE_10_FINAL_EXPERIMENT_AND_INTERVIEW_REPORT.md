# Milestone 10 Final Experiment and Interview Report

## Scope and reproducibility

This report consolidates the evidence available at the end of Milestone 10.
It separates measured local behavior from synthetic provider behavior and
unavailable PostgreSQL or remote-provider measurements.

- Software version: `0.1.0`
- Evaluation dataset: `reviewed-query-pairs-1.0`
- Development split: 32 requests
- Held-out split: 16 requests
- Storage-control dataset: `storage-controls-dev-v1`
- Load-test dataset: `synthetic-production-readiness-v1`
- Selected embedding threshold: `0.95`, selected on development data
- Cache policy load test: 8 entries, 10,000 bytes
- Load concurrency: 4
- Recorded Git commit: `98263ea895afe157e36f40e77d0fce46f166b014`
- Worktree state: dirty; the commit alone is not sufficient to reproduce the
  exact final state

Commands:

```powershell
python -m sscre.evaluate `
  --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all `
  --split development `
  --output experiments/milestone10_evaluation_development_report.json

python -m sscre.evaluate `
  --benchmark benchmarks/held_out_test.jsonl `
  --config experiments/evaluation_config.json `
  --baseline all `
  --split held-out `
  --output experiments/milestone10_evaluation_held_out_report.json

python -m sscre.load_test `
  --config experiments/milestone10_load_v1.json `
  --output experiments/milestone10_load_v1_report.json
```

## Safety and reuse results

The development comparison report measured:

- no-cache: 0 cache hits, 0% reuse coverage, 0 tokens saved;
- exact-cache: 4 hits, 12.5% hit rate, 50% safe-reuse coverage, 60 estimated
  tokens saved;
- embedding-only: 4 hits, 12.5% hit rate, 50% safe-reuse coverage, 60
  estimated tokens saved;
- compatibility-aware: 1 hit, 3.125% hit rate, 12.5% safe-reuse coverage,
  17 estimated tokens saved;
- false-positive rate: 0 for the measured development reports;
- estimated cost: `$0.00` because provider prices in the checked-in config are
  placeholders.

The held-out report had 16 requests and recorded zero hits for all four
baselines. That result means the held-out workload did not produce a reusable
candidate under the selected replay and threshold configuration; it must not
be presented as proof that semantic caching has zero recall in general.
Threshold selection remained independent of held-out labels.

Correctness and compatibility remain separate labels. The safety result is
conservative: missing or conflicting evidence produces generation rather than
an unsafe cache hit. These reports do not establish factual correctness of
generated or reused answers.

## Freshness and storage results

The storage-control development report measured:

- 4 workload requests;
- 2 stored entries and 1 canonical answer;
- 307 total bytes and 153.5 average bytes per entry;
- 1 deduplication hit and 32 bytes of deduplication savings;
- 1 expiration event;
- 1 cache hit and 4 estimated output tokens saved;
- 100% safe-reuse coverage for the one reusable opportunity in that workload.

The load workload also exercised dynamic queries, oversized answers,
embedding failures, generation failures, and eviction candidates. Dynamic and
oversized responses were returned without being cached; provider failures
were recorded as errors. The report explicitly labels all provider behavior
as synthetic.

TTL remains a freshness approximation. It prevents reuse after policy
expiration but does not prove factual currency.

## Latency, errors, and load behavior

`experiments/milestone10_load_v1_report.json` compares no-cache, exact-cache,
embedding-only, and compatibility-aware paths under the same 32-item
workload. Each mode has cold and warm passes at concurrency 4.

Cold-pass p50/p95/p99 latency in milliseconds:

- no-cache: `20.458 / 35.723 / 36.347`
- exact-cache: `12.803 / 23.815 / 26.433`
- embedding-only: `11.992 / 14.995 / 16.033`
- compatibility-aware: `13.054 / 15.813 / 17.154`

Warm-pass p50/p95/p99 latency in milliseconds:

- no-cache: `27.389 / 55.733 / 63.052`
- exact-cache: `12.263 / 16.147 / 17.695`
- embedding-only: `10.651 / 14.161 / 15.626`
- compatibility-aware: `13.457 / 19.407 / 20.515`

Each load pass recorded three expected synthetic generation failures out of
32 requests. No timeout occurred in this workload. The report stores bounded
per-request status, source, reason, latency, and timing fields.

The first measured bottleneck was wrapper overhead: average measured wrapper
overhead was `1.522 ms`, compared with `0 ms` synthetic LLM latency. This is
not a production capacity claim. Provider, network, PostgreSQL, and
sub-stage preprocessing/retrieval timings were not independently measured.
No production optimization was selected because the evidence does not justify
changing safety-critical request behavior.

## Cost and token accounting

The development and storage reports use whitespace token estimates for local
mock clients and zero configured provider prices. They are accounting
placeholders, not billing results.

The current break-even conclusion is therefore conditional:

```text
production break-even requires real provider token prices,
real embedding cost, cache lookup cost, and remote latency
```

The exact-cache development run saved 60 estimated tokens on 32 requests.
The storage-control run saved 4 estimated output tokens on 4 requests.
Neither result should be extrapolated to a real provider without replacing
the synthetic usage fields.

## Failure and limitation summary

Covered and tested:

- missing, malformed, and invalid admin credentials;
- unavailable repositories and readiness failures;
- incomplete or invalid migration state;
- embedding, generation, and cache-write failures;
- malformed provider responses;
- expired, dynamic, oversized, and incompatible cache candidates;
- concurrent duplicate-query requests;
- entry and byte caps;
- bounded timeouts and request IDs.

Unavailable or synthetic:

- real remote LLM and embedding latency, pricing, rate limits, and drift;
- PostgreSQL restart/load behavior in this environment;
- multi-process or distributed lock behavior;
- production hardware capacity;
- factual answer quality and human correctness labels beyond the reviewed
  benchmark.

The local PostgreSQL integration suite was skipped where
`SSCRE_DATABASE_URL` was unavailable. A disposable fresh-volume Compose smoke
test was later completed with PostgreSQL migrations `000` through `011`,
`/health`, `/ready`, and `POST /v1/query`; the existing local volume was not
destroyed. This smoke test does not establish restart, load, or multi-process
capacity behavior.

## Interview answers

### Why is similarity alone insufficient?

Embedding similarity measures closeness in representation space. It does not
prove equal language, entity, intent, output format, temporal state, audience,
or explicit constraints. Python and Java code requests can be highly similar
while requiring incompatible answers.

### Why does Strategy C reduce false positives?

Strategy C applies explicit compatibility and freshness rules after retrieval.
It rejects conflicts and abstains when evidence is missing, so similarity is
used for candidate retrieval rather than treated as authorization to reuse.

### How were thresholds selected?

The threshold was selected on the development split using the configured
false-positive constraint and then applied to the held-out split without using
held-out labels for tuning. The selected threshold was `0.95`.

### How was benchmark leakage avoided?

Development and held-out IDs are disjoint and validated against the split
manifest. Held-out labels are not used during threshold selection.

### What happens when a provider or database fails?

Repository failure fails closed for cache reuse and returns a controlled
`503`. Embedding failure falls back to generation without caching the result.
Generation failure returns a controlled `502`. Cache-write failure preserves a
valid generated answer when possible.

### How are stale answers prevented?

Freshness classes receive TTLs, and exact and semantic candidates are checked
for expiration before reuse. Dynamic entries are rejected by default. TTL is a
freshness policy, not proof of factual currency.

### What is the main bottleneck at higher traffic?

This milestone did not establish a higher-traffic production bottleneck. In
the bounded synthetic run, wrapper overhead exceeded zero-cost synthetic
generation latency. Real provider and database measurements are required
before claiming a production bottleneck.

### When should the system refuse to cache?

It should refuse when freshness is dynamic or expired, metadata is missing or
incompatible, the answer or metadata exceeds limits, provider output is
invalid, embeddings are unavailable, storage caps cannot be enforced, or
correctness/compatibility evidence is insufficient.

## Final conclusion

SSCRE now has a reproducible production-like boundary, failure-closed cache
reuse, protected administration, bounded dependency behavior, integration
failure coverage, and a repeatable load/evaluation workflow. The available
evidence supports the engineering claim that cache safety and operational
behavior are explicit and measurable. It does not support claims about real
provider economics, PostgreSQL capacity, or production factual accuracy until
those dependencies and workloads are measured.
