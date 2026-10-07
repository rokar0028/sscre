# Workstream 4 evidence

Completion handoff for real-provider measurement on 2026-10-07. This record
describes the current uncommitted worktree. It does not claim a credentialed
provider observation, production capacity, quality, or held-out result.

## Evidence status

- [x] The real-provider path is explicit and opt-in.
- [x] The unavailable-provider artifact is redacted and versioned:
  `artifacts/evaluation/workstream4-real-provider-unavailable.json`.
- [x] The synthetic-versus-real comparison is redacted and keeps the
  environments separate:
  `artifacts/evaluation/workstream4-provider-comparison.json`.
- [x] No synthetic values were copied into unavailable real-provider fields.
- [ ] A credentialed real-provider run is available. It was not run because
  `SSCRE_REAL_PROVIDER_LIVE=true` and provider credentials were not enabled.

## Contracts, implementation, and versions

- [x] Provider configuration: `real-provider-config-1.0`.
- [x] Real-provider measurement: `real-provider-measurement-1.0`.
- [x] Comparison artifact: `provider-measurement-comparison-1.0`.
- [x] Frozen safety boundary: `SAFE`, `UNSAFE`, `UNCERTAIN`.
- [x] Frozen serialization boundary: `1.0.0`.
- [x] Adapter and measurement files:
  `src/sscre/provider_config.py`, `src/sscre/remote_llm.py`,
  `src/sscre/remote_embedding.py`, `src/sscre/retry.py`,
  `src/sscre/pricing.py`, `src/sscre/provider_measure.py`, and
  `src/sscre/provider_compare.py`.
- [x] The adapters use the OpenAI-compatible HTTP contract and the Python
  standard-library `urllib` transport; no provider SDK was added.
- [x] Runtime versions observed during verification: Python 3.14.5,
  FastAPI 0.142.2, httpx 0.28.1, psycopg 3.3.6, and pytest 9.1.1.
  No provider API/SDK version was observed because no live request ran.
- [x] The unavailable artifact records provider, endpoint, and model fields
  as unavailable rather than inventing them.

## Configuration, workload, and pricing

- [x] Evaluation configuration: `evaluation-config-1.0`,
  `experiments/evaluation_config.json`.
- [x] Dataset: `reviewed-query-pairs-1.1`; development split,
  `benchmarks/development.jsonl`, 21 records.
- [x] The attempted real-provider configuration is represented only by the
  redacted configuration boundary. Credentials are not serialized.
- [x] Pricing schedule identity is unavailable for the provider run.
  Synthetic evaluation pricing remains a zero-cost placeholder and is not
  used as a real-provider price.

## Commands and results

- [x] Unavailable-provider artifact:

  ```text
  python -m sscre.provider_measure --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --output artifacts/evaluation/workstream4-real-provider-unavailable.json
  ```

  Result: exit 0; status `unavailable`; reason `live_opt_in_missing`.

- [x] Comparison artifact:

  ```text
  python -m sscre.provider_compare --synthetic artifacts/evaluation/workstream3-development.json --real artifacts/evaluation/workstream4-real-provider-unavailable.json --output artifacts/evaluation/workstream4-provider-comparison.json
  ```

  Result: exit 0; synthetic and real-provider rows remain separate.

- [x] Opt-in live-test command was documented and not enabled:

  ```text
  SSCRE_REAL_PROVIDER_LIVE=true python -m pytest -q -m real_provider
  ```

  Result: skipped because live opt-in and credentials were absent. No remote
  provider request was made.

- [x] Targeted provider verification:

  ```text
  python -m pytest -q tests/test_provider_compare.py tests/test_provider_measure.py
  ```

  Result: 3 passed on 2026-10-07.

- [x] Full suite without credentials:

  ```text
  python -m pytest -q
  ```

  Result: 479 passed, 14 skipped, with one existing Starlette/httpx
  deprecation warning on 2026-10-07. The skips are provider/database
  environment-dependent tests; the default suite made no remote provider
  calls.

## Measurement semantics

- [x] Request latency is total request elapsed time.
- [x] Provider latency is the measured remote generation or embedding call
  duration; wrapper latency is local work outside those calls.
- [x] Retry counts and retry latency are separate from first-attempt provider
  latency and are bounded by the configured request budget.
- [x] Token fields distinguish provider-reported, estimated, and unavailable
  usage. The unavailable run has no token observations.
- [x] Cost fields remain separate for generation, embedding, retry, wrapper,
  and total estimated cost. The unavailable run reports all of them as
  unavailable.

## Failure-closed and redaction evidence

- [x] Controlled timeout, rate-limit, malformed-response, retry, provider
  error, and failure-closed paths are covered by the provider and request
  tests recorded in the implementation plan.
- [x] Provider failure cannot become a cache hit or an unvalidated cache
  entry.
- [x] Artifact redaction flags confirm that raw prompts, raw answers,
  credentials, and provider payloads were not recorded.
- [x] The comparison artifact records unavailable metrics as `null` and
  preserves the limitation that no real quality, latency, token, or cost
  conclusion is available.

## Handoff and limitations

- [x] Workstream 5 may consume the provider-labeled artifact schema and
  comparison rules without treating unavailable values as zero.
- [x] The frozen safety meanings and held-out isolation are unchanged.
- [x] The current evidence supports adapter correctness, bounded local
  failure behavior, and artifact provenance only.
- [ ] Real-provider latency, token usage, pricing, quality, availability,
  capacity, and statistical conclusions remain unavailable until a
  credentialed development-only run is performed.
- [ ] Provider/API drift and live nondeterminism remain unmeasured.
