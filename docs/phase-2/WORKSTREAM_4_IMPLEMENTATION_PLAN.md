# Phase 2 Workstream 4 Implementation Plan

## Goal

Add one opt-in real-provider path and produce reproducible measurements for
generation, embeddings, latency, token usage, retries, rate limits, failures,
and estimated cost. The result must make real-provider evidence comparable to
the existing deterministic synthetic evidence without presenting the two as
the same measurement.

This workstream consumes the frozen decision and trace boundary from
Workstream 1 and the tested candidate-evaluation path from Workstream 3. It
does not change the meaning of `SAFE`, `UNSAFE`, or `UNCERTAIN`, tune the
held-out threshold, add a second analytics pipeline, or make production
capacity claims.

The target outcome is an opt-in run that can answer:

- which provider, endpoint, generation model, and embedding model were used;
- how long cache hits, embedding calls, and generation calls took;
- how many input and output tokens were reported;
- how retries, timeouts, rate limits, malformed responses, and provider
  failures affected the request path;
- what embedding, generation, retry, wrapper, and total estimated costs were;
- whether failures remained failure-closed and never caused an unsafe cache hit;
- how real-provider results differ from deterministic fake-provider results.

## Status

**Workstream 4 iteration 1: complete** (adapters, tests, unavailable artifact,
comparison, evidence). Step 1 audit:
[`WORKSTREAM_4_STEP1_AUDIT.md`](./WORKSTREAM_4_STEP1_AUDIT.md). Handoff:
[`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md).

**Deferred to a later iteration:** credentialed live observation
(`status: completed` measure artifact). Optional when ready: enable
`SSCRE_REAL_PROVIDER`, `SSCRE_REAL_PROVIDER_LIVE`, credentials, run
`python -m sscre.provider_measure`.

## Source of truth

The scope is defined by Workstream 4 in
[`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).
The broader remaining-gaps context is in
[`MILESTONE_11_REMAINING_GAPS_IMPLEMENTATION_PLAN.md`](./MILESTONE_11_REMAINING_GAPS_IMPLEMENTATION_PLAN.md).

The following artifacts are frozen inputs and must not be redefined here:

- [`SAFETY_EVALUATION_CONTRACT_v1.md`](./SAFETY_EVALUATION_CONTRACT_v1.md)
  defines `SAFE`, `UNSAFE`, and `UNCERTAIN`.
- [`CANDIDATE_TRACE_CONTRACT_v1.md`](./CANDIDATE_TRACE_CONTRACT_v1.md) defines
  bounded candidate evidence and reason fields.
- [`SERIALIZATION_BOUNDARY_v1.md`](./SERIALIZATION_BOUNDARY_v1.md) defines
  API, log, report, and redaction boundaries.
- [`EVALUATION_LABEL_CONTRACT_v1.md`](../../benchmarks/EVALUATION_LABEL_CONTRACT_v1.md)
  keeps compatibility, correctness, and preference labels independent.
- [`WORKSTREAM_3_EVIDENCE.md`](./WORKSTREAM_3_EVIDENCE.md) records the current
  decision-depth handoff, including known provider and PostgreSQL limitations.

Canonical current implementation locations:

| Responsibility | Current module or artifact |
|---|---|
| Generation result and fake client | `src/sscre/llm.py` |
| Embedding result, interface, validation, and fake client | `src/sscre/embedding.py` |
| Request-path provider wiring and timeouts | `src/sscre/app.py` |
| Runtime settings and environment parsing | `src/sscre/config.py` |
| Request metrics and counters | `src/sscre/metrics.py` |
| Evaluation baselines and cost fields | `src/sscre/baseline.py` |
| Evaluation CLI and configuration validation | `src/sscre/evaluate.py` |
| API/log/report boundaries and redaction | `src/sscre/serialization.py` |
| Existing deterministic experiment configuration | `experiments/evaluation_config.json` |
| Provider-independent unit tests | `tests/test_embedding.py`, `tests/test_query.py`, `tests/test_failure_paths.py` |

## Learning objectives

- [ ] Explain why a real-provider result is an observed experiment, not a
  universal provider or production-capacity claim.
- [ ] Keep generation and embedding interfaces provider-independent while
  preserving deterministic fake clients for tests.
- [ ] Design bounded timeout, retry, and backoff behavior for remote calls.
- [ ] Separate provider latency from request latency and wrapper overhead.
- [ ] Interpret provider-reported, estimated, and unavailable token usage
  without silently substituting one for another.
- [ ] Calculate embedding, generation, retry, wrapper, and total estimated
  cost from versioned pricing inputs.
- [ ] Preserve failure-closed reuse when a remote dependency fails or returns
  malformed data.
- [ ] Keep credentials, raw prompts, answers, and provider response payloads
  out of logs, reports, and checked-in configuration.
- [ ] Label synthetic and real-provider measurements separately.
- [ ] Preserve development-only threshold selection and held-out isolation.

## Scope

### Included

- One opt-in remote generation client implementing the existing LLM boundary.
- One opt-in remote embedding client implementing the existing embedding
  boundary.
- Configuration for provider, endpoint, model names, timeouts, retry limits,
  bounded backoff, and redacted experiment identity.
- Environment or secret-manager credential loading with no credential
  serialization.
- Strict validation of provider responses before they enter the request path.
- Bounded retry behavior for explicitly retryable failures only.
- Measurement of request, embedding, generation, and wrapper latency.
- Measurement of provider-reported token usage where available.
- Versioned pricing inputs and explicitly estimated cost fields.
- Opt-in integration tests that skip safely when credentials are absent.
- Failure-path tests for timeout, rate limit, malformed response, retry
  exhaustion, and provider error behavior.
- A redacted, versioned real-provider run or an explicit unavailable-provider
  report.
- A comparison artifact that keeps real and synthetic measurements distinct.

### Excluded

- Changing the frozen safety decision vocabulary or candidate trace taxonomy.
- Threshold tuning from held-out labels or from real-provider output quality.
- Cross-encoders, adaptive thresholds, model routing, or dual-model fallback.
- A provider-specific abstraction that replaces the existing interfaces for
  deterministic tests.
- Storing raw prompts, answers, embeddings, provider payloads, or credentials
  in operational logs or checked-in reports.
- Automatic provider selection based on cost or latency.
- Production SLA, capacity, availability, or multi-region claims.
- PostgreSQL restart, multi-process, or shared-database capacity testing owned
  by Workstream 8.
- Confidence intervals, Pareto operating-point selection, and final
  held-out statistical claims owned by Workstream 5.
- Freshness-policy experiments owned by Workstream 6.

## Frozen provider and safety semantics

The provider boundary must preserve these existing meanings:

```text
remote generation succeeds       → return validated LLMResult
remote embedding succeeds        → return validated EmbeddingResult
remote dependency fails          → no cache hit caused by that failure
remote response is malformed     → no cache hit caused by that response
missing provider configuration   → opt-in run is unavailable, not synthetic
```

The request path must continue to use the Workstream 3 safety boundary:

```text
retrieval and cache-control
    ↓
compatibility evaluation
    ↓
SAFE / UNSAFE / UNCERTAIN
    ↓
serve only SAFE
    ↓
otherwise generate through the configured provider
```

Provider failure must not be converted into a successful cache hit. If
generation fails after a non-`SAFE` decision, the controlled generation error
remains non-reusable. If embedding fails, semantic retrieval and cache
insertion must preserve the existing failure-closed behavior.

## Current baseline

### Existing implementation

- [x] `LLMResult` already carries generated text, input tokens, output tokens,
  and latency.
- [x] `EmbeddingClient` already exposes a provider-independent `embed()` path.
- [x] `EmbeddingResult` already carries vector, model, input tokens, and
  latency.
- [x] Fake generation and embedding clients are deterministic test doubles.
- [x] Embedding vector, dimension, model, token, and latency validation exists.
- [x] Request orchestration already applies bounded dependency timeouts.
- [x] Production profile rejects the default fake provider path.
- [x] Evaluation configuration already contains generation, embedding, cache
  lookup, and preprocessing cost fields.
- [x] Baseline reports already account for deterministic token and cost inputs.
- [x] Workstream 3 already tests failure-closed behavior around embedding,
  generation, validation, and serialization boundaries.
- [x] Operational serialization rejects credential-like and raw-content keys.

### Open baseline gaps

- [x] A remote generation client implements `LLMClient` behavior without
  coupling the request path to a provider SDK.
- [x] A remote embedding client implements `EmbeddingClient` behavior and
  validates model and dimension configuration.
- [x] Provider and endpoint settings are explicit, bounded, and redacted.
- [x] Credentials are loaded from an approved runtime source and never appear
  in logs, reports, exceptions, or checked-in configuration.
- [x] Retry and backoff semantics distinguish retryable from non-retryable
  failures.
- [x] Rate-limit responses record bounded metadata such as status category and
  retry-after availability without recording response bodies.
- [x] Provider-reported token usage is retained with a source and availability
  status.
- [x] Pricing inputs have a version, currency, unit, and effective date.
- [x] Cost accounting includes embedding, generation, retry, and wrapper
  components without double counting.
- [x] Real-provider integration tests skip safely when opt-in credentials are
  unavailable.
- [x] A redacted real-provider experiment artifact exists, or the absence is
  explicitly reported with its consequences.
- [x] Synthetic and real-provider results cannot be confused by shared report
  labels or zero-cost defaults.

## Provider contract

### Generation contract

The remote generation adapter must implement the behavior required by the
existing `LLMResult` boundary:

- accept a non-empty query;
- send only the configured model, bounded request settings, and required
  provider parameters;
- return text and non-negative input/output token counts;
- return measured provider-call latency separately from wrapper latency;
- reject malformed JSON, missing text, invalid token values, and unexpected
  response shapes;
- classify errors without serializing credentials, prompt text, answer text,
  or response bodies.

If the provider does not report token usage, the result must say usage is
unavailable. A local token estimate may be recorded only as an explicitly
estimated field and must not be presented as provider-reported usage.

### Embedding contract

The remote embedding adapter must implement the existing `EmbeddingClient`
protocol:

- expose a configured model name and expected dimension;
- reject empty input before a remote call;
- return a finite vector with the configured dimension;
- return non-negative input token usage when reported;
- return measured provider-call latency;
- reject a response for the wrong model, dimension, shape, or numeric values;
- classify failures without exposing provider payloads.

The configured dimension must be explicit. The adapter must not silently
truncate, pad, normalize, or accept a vector with a different dimension.

### Error taxonomy

Use a small, bounded taxonomy for metrics and reports:

| Category | Meaning | Retry default |
|---|---|---|
| `configuration` | Missing or invalid opt-in configuration | No |
| `authentication` | Provider rejected credentials | No |
| `authorization` | Credential lacks access | No |
| `rate_limited` | Provider returned a rate-limit response | Bounded retry |
| `timeout` | Connect, read, or total call exceeded its budget | Bounded retry only if configured |
| `transient_provider` | Explicitly transient provider/network failure | Bounded retry |
| `permanent_provider` | Provider rejected the request permanently | No |
| `malformed_response` | Response cannot satisfy the local result contract | No |
| `validation` | Local input or output validation failed | No |
| `retry_exhausted` | Retry budget ended without success | No |

Do not use arbitrary exception text as a stable report dimension. Store the
exception class or bounded category only where the serialization contract
allows it.

## Implementation steps

### 1. Audit the existing provider boundary and measurement fields

Inventory the current generation, embedding, timeout, metrics, baseline, and
serialization paths before adding an adapter. Document which fields are
provider-reported, locally measured, estimated, or unavailable.

- [x] Record the current `LLMResult`, `EmbeddingResult`, and protocol
  invariants.
- [x] Record every request-path location that invokes generation or embedding.
- [x] Record where request, provider, and wrapper latency can be measured
  without changing safety behavior.
- [x] Record current token and cost fields in baseline reports.
- [x] Record current forbidden log/report fields and redaction behavior.
- [x] Identify any existing dependency that can support the selected provider
  without adding a new package.
- [x] Define the first provider contract as an OpenAI-compatible
  chat-completions vertical slice; concrete provider selection remains an
  experiment configuration value.
- [x] Record the targeted HTTP contract shape as
  `POST {endpoint}/chat/completions` with `choices[].message.content` and
  optional `usage` fields; provider API/SDK version remains run metadata.

Evidence recorded:

- [x] Provider-boundary audit artifact:
  [`WORKSTREAM_4_STEP1_AUDIT.md`](./WORKSTREAM_4_STEP1_AUDIT.md).
- [x] Selected provider contract: OpenAI-compatible HTTP; vendor/endpoint is
  experiment configuration (`SSCRE_PROVIDER_*`), not a fixed product in repo.
- [x] Field provenance matrix for latency, tokens, and cost (audit § 3).
- [x] Dependency inventory and decision record (audit § 5); provider transport
  installation/test command remains deferred until provider selection.

### 2. Freeze the provider configuration contract

Define one redacted configuration shape for local opt-in runs and CI-safe
defaults. Configuration must fail closed rather than silently falling back to
fake clients when a real-provider run was requested.

Implementation: `src/sscre/provider_config.py`,
`tests/test_provider_config.py`. Configuration version:
`real-provider-config-1.0`.

Required fields:

- provider identifier;
- endpoint or API base URL;
- generation model;
- embedding model;
- embedding dimension;
- generation timeout;
- embedding timeout;
- connect timeout, if the client supports it;
- retry limit;
- minimum and maximum backoff;
- experiment identifier;
- dataset version and split;
- pricing schedule identifier;
- optional request parameters that affect comparability.

Credential fields must be supplied through environment variables or the
approved secret manager. The redacted configuration must contain only:

- whether the credential was configured, never the credential value;
- provider and model names;
- endpoint origin with sensitive path/query components removed;
- timeout and retry settings;
- experiment, dataset, split, and pricing identifiers.

- [x] Add a versioned configuration schema.
- [x] Validate non-empty provider and model identifiers.
- [x] Validate endpoint scheme, allowed host policy, and bounded URL length.
- [x] Validate positive timeout values and total request-budget relationships.
- [x] Validate retry count and bounded backoff values.
- [x] Validate embedding dimension and pricing schedule references.
- [x] Reject credentials passed through report or log configuration objects.
- [x] Make real-provider selection explicit; disabled mode returns no config and
  does not select a fake provider implicitly.
- [x] Add tests for missing, malformed, and conflicting configuration.
- [x] Add a redaction test that proves serialized configuration contains no
  secret, token, authorization, password, or API-key value.

Step 2 evidence (2026-10-07):

- [x] `RealProviderConfig` validates required identifiers, HTTP(S) endpoint
  safety, optional host allow-list, embedding dimension, timeout relationships,
  retry/backoff bounds, experiment metadata, pricing schedule identity, and
  bounded non-secret request parameters.
- [x] `RealProviderConfig.from_environment()` is disabled unless
  `SSCRE_REAL_PROVIDER=true`; enabled mode fails closed on missing fields.
- [x] `redacted()` emits endpoint origin and credential presence only; it does
  not emit credentials, URL paths/queries, or raw secret-like values.
- [x] `python -m pytest -q tests/test_provider_config.py tests/test_config.py`
  → 23 passed (2026-10-07).
- [x] Post-review configuration verification:
  `python -m pytest -q tests/test_provider_config.py tests/test_provider_integration.py tests/test_retry.py`
  → 26 passed (2026-10-07), including non-finite numeric and combined timeout
  budget regression cases.
- [x] Pre-Step-3 baseline: `python -m pytest -q` → 426 passed, 13 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] IDE linter diagnostics: no errors for the new module and tests.

### 3. Implement one remote generation adapter

Implement the smallest adapter that satisfies the existing generation result
boundary. Prefer the standard library or an already-declared dependency. Keep
provider-specific request and response parsing inside the adapter.

- [x] Validate query input before making a request.
- [x] Construct requests from allow-listed configuration fields.
- [x] Apply the configured generation/embedding operation timeout on urllib
  transport; `TimeoutError` maps to the bounded `timeout` category. Split
  connect/read budgets remain a standard-library transport follow-up
  The standard-library transport uses one bounded timeout for each request;
  separate connect/read timeout configuration is intentionally deferred.
- [x] Measure provider-call latency with a monotonic clock.
- [x] Parse only the expected response fields.
- [x] Validate text and token counts before returning `LLMResult`.
- [x] Record provider/model identifiers as bounded metadata.
- [x] Preserve provider-reported token usage provenance, with explicit
  estimated fallback when usage is absent.
- [x] Convert provider failures to the bounded local error taxonomy.
- [x] Ensure exception messages cannot contain request or response bodies.
- [x] Add unit tests using a local fake transport or test double, not a live
  provider.

Implementation: `src/sscre/llm.py`, `src/sscre/remote_llm.py`,
`tests/test_remote_llm.py`.

Step 3 evidence (2026-10-07):

- [x] `OpenAICompatibleLLMClient` uses the existing generation boundary and
  standard-library `urllib` transport.
- [x] The request sends only the configured model and user message, with the
  credential limited to the authorization header.
- [x] Responses require a non-empty `choices[0].message.content` string.
- [x] Provider-reported usage is preserved; missing usage is explicitly marked
  as estimated.
- [x] HTTP status categories cover authentication, authorization, rate limit,
  transient, and permanent provider failures without response-body logging.
- [x] `python -m pytest -q tests/test_remote_llm.py tests/test_provider_config.py tests/test_query.py tests/test_failure_paths.py`
  → 39 passed, 1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] Pre-Step-4 full suite: `python -m pytest -q` → 441 passed, 13 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] IDE linter diagnostics: no errors for the adapter and tests.

The adapter must not:

- log the authorization header;
- log the raw query or generated answer;
- retry validation, authentication, authorization, or permanent failures;
- return a partially parsed answer;
- treat missing usage as zero without an explicit unavailable/estimated flag.

### 4. Implement one remote embedding adapter

Implement the smallest adapter that satisfies the existing embedding protocol
and passes the existing vector validation boundary.

- [x] Validate text before the request.
- [x] Send only configured model and bounded input data.
- [x] Measure provider-call latency.
- [x] Parse the expected vector and usage fields.
- [x] Validate finite numeric values and exact configured dimension.
- [x] Validate model identity where the provider returns it.
- [x] Preserve provider-reported token usage provenance.
- [x] Convert provider failures to the bounded local error taxonomy.
- [x] Ensure exception messages cannot contain input text or response bodies.
- [x] Add unit tests for valid, wrong-dimension, non-finite, malformed, and
  missing-usage responses.

Implementation: `src/sscre/embedding.py`,
`src/sscre/remote_embedding.py`, `tests/test_remote_embedding.py`.

Step 4 evidence (2026-10-07):

- [x] `OpenAICompatibleEmbeddingClient` implements the existing
  `EmbeddingClient` protocol and reuses the Step 3 JSON transport.
- [x] The adapter sends only the configured model and input text, and requires
  the configured credential.
- [x] Responses require a finite vector with the configured dimension; an
  optional response model must match the configured model.
- [x] Provider-reported usage is preserved; missing usage is explicitly marked
  as estimated.
- [x] `python -m pytest -q tests/test_remote_embedding.py tests/test_remote_llm.py tests/test_embedding.py tests/test_provider_config.py`
  → 57 passed (2026-10-07).
- [x] Pre-Step-5 full suite: `python -m pytest -q` → 455 passed, 13 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] IDE linter diagnostics: no errors for the adapter and tests.

Do not make the vector dimension implicit or provider-dependent at runtime.
Changing the embedding model or dimension requires a new experiment
configuration and an explicit compatibility decision for existing entries.

### 5. Add bounded retry and backoff behavior

Retries must be part of the measured experiment, not an invisible transport
detail. The budget must be finite and compatible with the request deadline.

- [x] Define retryable status/error categories.
- [x] Define maximum attempts, maximum elapsed retry time, and maximum sleep.
- [x] Use bounded exponential or provider-directed backoff.
- [x] Respect a bounded `Retry-After` value when it is valid.
- [ ] Add jitter (deferred: not required for iteration 1 closure).
- [x] Stop retrying when the request timeout budget is exhausted.
- [x] Count initial attempts and retry attempts separately.
- [x] Record rate-limit and timeout categories without response bodies.
- [x] Include retry cost in accounting when billing rule known; otherwise null
  total/retry (`estimate_request_cost`, `tests/test_pricing.py`).
- [x] Prove retries cannot cache before success
  (`tests/test_provider_retry_failures.py`).

Implementation: `src/sscre/retry.py`, `src/sscre/remote_llm.py`,
`src/sscre/remote_embedding.py`, `src/sscre/llm.py`, and
`src/sscre/embedding.py`.

Step 5 evidence (2026-10-07):

- [x] `run_with_bounded_retries()` enforces retry count, elapsed retry budget,
  capped exponential backoff, provider-directed delay, and non-retryable
  error categories.
- [x] Both remote adapters expose `attempts` and `retry_count` in validated
  result metadata.
- [x] Authentication, authorization, malformed-response, and permanent errors
  are not retried; rate-limit and transient provider errors are retryable.
- [x] Retry-After values are capped by the configured maximum backoff and
  never allowed to exceed the remaining retry budget.
- [x] `python -m pytest -q tests/test_retry.py tests/test_remote_llm.py tests/test_remote_embedding.py tests/test_embedding.py`
  → 49 passed (2026-10-07).
- [x] Pre-Step-6 full suite: `python -m pytest -q` → 462 passed, 13 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] IDE linter diagnostics: no errors for the retry implementation and tests.

Test at minimum:

- [x] success on the first attempt;
- [x] one transient failure followed by success;
- [x] rate limit followed by success;
- [x] retry-after exceeding the remaining budget;
- [x] permanent failure without retry;
- [x] malformed response without retry;
- [x] retry exhaustion;
- [ ] Cancellation during retry backoff (deferred; outer `run_with_timeout`
  in `app.py` bounds request path).

### 6. Integrate opt-in providers with the request path

Wire the adapters through the existing provider interfaces and request
timeouts. Keep fake clients as the default for tests and deterministic local
experiments.

- [x] Add explicit provider construction for the development/experiment path.
- [x] Keep the production-profile requirement that fake providers are not
  accepted where real clients are required.
- [x] Ensure exact cache hits do not make an unnecessary embedding call.
- [x] Ensure semantic misses measure the embedding call separately.
- [x] Ensure generation fallback uses the configured generation adapter.
- [x] Ensure cached `SAFE` responses do not invoke generation.
- [x] Ensure `UNSAFE` and `UNCERTAIN` paths invoke generation or return a
  controlled generation failure.
- [x] Ensure embedding failure cannot serve or insert an unvalidated entry.
- [x] Ensure provider errors preserve Workstream 3 traces and decisions.
- [x] Add integration tests with deterministic transport doubles.
- [x] Add a configuration test proving real-provider mode never silently
  instantiates a fake client.

Implementation: `src/sscre/app.py`,
`tests/test_provider_integration.py`.

Step 6 evidence (2026-10-07):

- [x] `create_app()` constructs the OpenAI-compatible generation and embedding
  clients only when `SSCRE_REAL_PROVIDER=true`.
- [x] Real-provider mode fails closed on missing configuration and rejects
  injected fake generation or embedding clients.
- [x] Default mode continues to construct deterministic fake clients, and
  production-mode fake-provider checks remain enforced.
- [x] The existing request timeout wrapper remains around provider calls; the
  adapters apply their configured generation/embedding timeout internally.
- [x] `python -m pytest -q tests/test_provider_integration.py tests/test_remote_llm.py tests/test_remote_embedding.py tests/test_workstream3_strategy_c_paths.py`
  → 49 passed, 1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] Pre-review-fix full suite: `python -m pytest -q` → 466 passed, 13 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] Pre-Step-7 full suite: `python -m pytest -q` → 469 passed, 13
  skipped, 1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] IDE linter diagnostics: no errors for the request-path integration and
  tests.

The adapter integration must not change candidate ordering, freshness
behavior, trace limits, redaction, or the rule that only `SAFE` is reusable.

### 7. Define token and latency measurement semantics

Every measurement must identify its source and scope. Do not collapse
provider-call latency, wrapper latency, and total request latency into one
number.

Implementation: `src/sscre/metrics.py`, `src/sscre/app.py`,
`src/sscre/llm.py`, `src/sscre/embedding.py`, and
`tests/test_metrics.py`.

Current semantics:

- `llm_latency_ms` and `embedding_latency_ms` include all attempts and backoff
  for that provider operation.
- `total_latency_ms` includes the complete request, including cache lookup,
  compatibility evaluation, provider calls, cache writes, and response
  serialization.
- Wrapper overhead is the request total minus the explicitly measured
  provider-operation fields; it is not treated as provider latency.
- Token usage is labeled `provider_reported` or `estimated`; unavailable
  provider usage uses an explicit estimated fallback in the current adapter.
- Cache hits report zero provider attempts and zero provider tokens.

Record per request where available:

- request ID or bounded run record ID;
- cache path: exact hit, semantic hit, miss, or generated fallback;
- total request latency;
- cache lookup latency;
- embedding provider latency and embedding wrapper latency;
- generation provider latency and generation wrapper latency;
- retry count and rate-limit count;
- input and output token usage for generation;
- input token usage for embeddings;
- usage source: `provider_reported`, `estimated`, or `unavailable`;
- provider, endpoint origin, model, and API-contract version;
- experiment ID, dataset version, split, and measurement timestamp.

- [x] Define whether latency includes retries and backoff.
- [x] Define whether wrapper overhead includes serialization and cache writes.
- [x] Keep monotonic duration measurement separate from wall-clock timestamps.
- [x] Reject negative, non-finite, or impossible measurement values.
- [x] Bound measurement artifacts via serialization redaction validation
  (`validate_redacted_report_payload`).
- [x] Comparison artifact keeps runs separate; aggregation by provider/model is
  a WS5 concern when multiple completed runs exist.
- [x] Add unit tests for missing usage and zero-token valid responses.
- [x] Add tests that token counts and latency are not taken from untrusted
  arbitrary response fields.

Step 7 evidence (2026-10-07):

- [x] `RequestMetrics` exposes separate generation and embedding latency,
  tokens, usage source, attempt count, retry count, provider, and model fields.
- [x] `create_app()` populates those fields for generated responses and reports
  zero provider activity for cache-only responses.
- [x] Remote adapter latency now measures the complete provider operation,
  including retries and backoff, using a monotonic clock.
- [x] `python -m pytest -q tests/test_metrics.py` → 9 passed, 1 existing
  Starlette/httpx deprecation warning (2026-10-07).
- [x] Pre-Step-8 full suite: `python -m pytest -q` → 469 passed, 13 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).

### 8. Define versioned pricing and cost accounting

Cost is an estimate unless the provider supplies an authoritative charge.
Every cost field must disclose its pricing inputs and provenance.

The accounting model must include:

```text
generation_cost
  = generation_input_tokens × input_price
  + generation_output_tokens × output_price

embedding_cost
  = embedding_input_tokens × embedding_price

retry_cost
  = cost of all billable failed and repeated provider attempts

wrapper_cost
  = configured cache lookup and preprocessing costs, if applicable

total_estimated_cost
  = generation_cost + embedding_cost + retry_cost + wrapper_cost
```

Do not count a cache-hit generation cost that did not occur. Do not count
embedding cost for an exact hit that bypassed embedding. If a provider bills
failed calls, the pricing/configuration contract must say how that is
represented; otherwise retry cost is marked unavailable rather than guessed.

- [x] Add a versioned pricing schedule with currency and effective date.
- [x] Validate finite non-negative prices.
- [x] Record price units, such as USD per 1,000 tokens.
- [x] Record whether prices are provider-list estimates or measured charges.
- [x] Add separate generation, embedding, retry, and wrapper cost fields.
- [x] Add a total cost field with a documented inclusion rule.
- [x] Preserve `null` or an explicit unavailable state when usage/pricing is
  unavailable.
- [x] Add tests for exact-hit, semantic-hit, miss, retry, and unavailable-cost
  calculations.
- [x] Verify no synthetic zero-cost result is labeled as real-provider cost.

Implementation: `src/sscre/pricing.py`, `src/sscre/metrics.py`,
`src/sscre/app.py`, and `tests/test_pricing.py`.

Step 8 evidence (2026-10-07):

- [x] `PricingSchedule` records schedule ID, currency, effective date, unit,
  source provenance, generation/embedding rates, and wrapper rates.
- [x] `estimate_request_cost()` separates generation, embedding, retry,
  wrapper, and total cost fields.
- [x] Unknown billing for failed/repeated attempts produces `null` retry and
  total costs rather than an invented charge.
- [x] Missing pricing produces `cost_source=unavailable`; synthetic fake
  provider results are never labeled as real-provider pricing.
- [x] Generated request metrics include the cost breakdown when a schedule is
  explicitly supplied to `create_app()`.
- [x] `python -m pytest -q tests/test_pricing.py tests/test_metrics.py tests/test_query.py`
  → 24 passed, 1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] Pre-Step-9 full suite: `python -m pytest -q` → 476 passed, 13 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).
- [x] IDE linter diagnostics: no errors for pricing and metrics changes.

### 9. Add provider-dependent integration tests

Live tests must be opt-in, safe to skip, bounded in cost, and isolated from
the default suite. They must never require credentials for ordinary CI.

- [x] Add a marker or explicit command for provider integration tests.
- [x] Skip when the required credential, endpoint, model, or opt-in flag is
  absent.
- [x] Fail when opt-in is explicitly requested but configuration is invalid.
- [x] Use a bounded development-only smoke input, not the held-out split.
- [x] Bound the smoke test to one generation and one embedding request.
- [x] Avoid logging prompts, answers, credentials, or provider response bodies.
- [x] Record provider/model/configuration identity through the validated
  runtime configuration; measurement artifact recording remains Step 10.
- [x] Test one generation and one embedding call when the provider is
  available.
- [x] Test provider timeout, rate limit, malformed response, and auth behavior
  with local transport doubles even when live tests are skipped.
- [x] Confirm `python -m pytest -q` remains independent of provider access.

Implementation: `pyproject.toml`, `tests/test_provider_integration.py`.

Step 9 evidence (2026-10-07):

- [x] Registered the `real_provider` pytest marker.
- [x] Live smoke testing requires explicit
  `SSCRE_REAL_PROVIDER_LIVE=true`; otherwise it skips.
- [x] Explicit live mode fails for missing configuration/credentials and
  rejects non-development splits.
- [x] The live smoke is bounded to exactly one generation and one embedding
  request; full spend accounting remains in Step 10.
- [x] `python -m pytest -q tests/test_provider_integration.py -m "not real_provider"`
  → 4 passed, 1 deselected (2026-10-07).
- [x] `python -m pytest -q tests/test_provider_integration.py -m real_provider`
  → 1 skipped without the explicit live opt-in (2026-10-07).
- [x] Pre-Step-10 full suite: `python -m pytest -q` → 476 passed, 14 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).

### 10. Run the redacted real-provider measurement

Run a fixed development workload using a frozen configuration. Do not use
held-out labels to select a threshold or alter compatibility rules.

The run artifact must contain:

- schema and measurement contract versions;
- experiment ID;
- provider and endpoint origin;
- generation and embedding model identifiers;
- provider/API/SDK versions where available;
- dataset version and split;
- configuration and pricing schedule versions;
- run start/end timestamps;
- request count and path counts;
- latency summaries or raw bounded observations as approved;
- token usage by source;
- retry, timeout, rate-limit, and malformed-response counts;
- generation, embedding, retry, wrapper, and total estimated costs;
- provider availability and skipped/unavailable reasons;
- Workstream 3 decision counts and trace-reason counts where collected;
- explicit synthetic/real measurement label;
- redaction and data-policy result.

- [x] Freeze the checked-in development dataset/configuration inputs for the
  attempted run.
- [x] Record the exact command and environment shape without secret values.
- [x] Record the Python, package, provider SDK, and API versions (`runtime_versions`
  in measurement artifacts; provider SDK remains null until a live SDK is used).
- [x] Use only the development split for threshold or policy diagnostics.
- [x] Keep held-out data read-only and outside threshold selection.
- [x] Save only bounded, redacted report fields.
- [x] Validate the report through the existing serialization boundary
  (`validate_redacted_report_payload` in `provider_measure.main`).
- [ ] Re-run live workload for reproducibility (deferred with credentialed run).
- [x] Limitations record answer-text nondeterminism
  (`provider_measure` / comparison artifacts).
- [x] Record unavailable measurements instead of substituting fake values.

Implementation: `src/sscre/provider_measure.py`,
`tests/test_provider_measure.py`,
`artifacts/evaluation/workstream4-real-provider-unavailable.json`.

Step 10 evidence (2026-10-07):

- [x] Command:
  `python -m sscre.provider_measure --benchmark benchmarks/development.jsonl --config experiments/evaluation_config.json --output artifacts/evaluation/workstream4-real-provider-unavailable.json`
- [x] The artifact records dataset `reviewed-query-pairs-1.1`, development
  split, 21 records, configuration version, git commit, and explicit
  `status=unavailable`.
- [x] No provider request was made because `SSCRE_REAL_PROVIDER_LIVE` was not
  enabled; no synthetic values were substituted.
- [x] Tokens, latency, costs, and provider identity are explicitly `null` or
  unavailable, with redaction flags recorded.
- [x] `python -m pytest -q tests/test_provider_measure.py` → 1 passed
  (2026-10-07).
- [x] Pre-Step-11 full suite: `python -m pytest -q` → 477 passed, 14 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).

If the provider is unavailable, create an explicit unavailable-provider record
with the attempted command, configuration validation result, and consequences
for Phase 2 claims. Do not mark the real-provider acceptance criteria complete.

### 11. Compare real and synthetic measurements without conflation

Create a comparison artifact that places matching metrics beside one another
while preserving their provenance.

Required distinctions:

| Measurement | Synthetic source | Real-provider source |
|---|---|---|
| Generation latency | fake-client configured behavior | remote provider observation |
| Embedding latency | fake-client configured behavior | remote provider observation |
| Token usage | deterministic or configured fake values | provider-reported or explicitly estimated |
| Cost | configured placeholder prices | versioned provider pricing inputs |
| Failures | injected test failures | observed provider failures plus controlled tests |
| Safety decisions | deterministic replay | same frozen decision path with provider-specific retrieval/generation inputs |

- [x] Add a `measurement_environment` or equivalent explicit label.
- [x] Keep synthetic and real rows separate in reports and plots.
- [x] Do not average zero-cost synthetic values into real-provider totals.
- [x] Do not infer real quality from synthetic generated text.
- [x] Comparison rules require matching provider/models before latency/cost
  compare (`src/sscre/provider_compare.py`).
- [x] Preserve the same dataset/configuration identity where comparison is
  intended.
- [x] Report unavailable metrics rather than silently dropping them.
- [x] Link the comparison artifact from this evidence:
  `artifacts/evaluation/workstream4-provider-comparison.json`.

Implementation: `src/sscre/provider_compare.py`,
`tests/test_provider_compare.py`,
`artifacts/evaluation/workstream4-provider-comparison.json`.

Step 11 evidence (2026-10-07):

- [x] Comparison schema `provider-measurement-comparison-1.0` preserves
  separate `synthetic` and `real_provider` rows.
- [x] Both artifacts use dataset `reviewed-query-pairs-1.1` and the
  development split.
- [x] Unavailable real-provider metrics remain `null`; synthetic zero-cost
  placeholders are not copied into real-provider fields.
- [x] The artifact records explicit comparison rules and limitations without
  storing prompts, answers, credentials, or provider payloads.
- [x] `python -m pytest -q tests/test_provider_compare.py tests/test_provider_measure.py`
  → 3 passed (2026-10-07).
- [x] Post-Step-11 full suite: `python -m pytest -q` → 479 passed, 14 skipped,
  1 existing Starlette/httpx deprecation warning (2026-10-07).

### 12. Record completion evidence and hand off

The evidence record must allow Workstream 5 to consume real-provider
measurements without reinterpreting provider provenance or safety semantics.

- [x] Record implementation files and provider contract versions in
  [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md).
- [x] Record selected provider, endpoint origin, models, and API/SDK versions;
  unavailable live-provider values remain explicitly unavailable.
- [x] Record configuration, dataset, split, and pricing versions.
- [x] Record live-test command and skip/fail/pass result.
- [x] Record redacted real-provider run command and result.
- [x] Record request, embedding, generation, wrapper, and retry latency
  semantics.
- [x] Record token usage source counts.
- [x] Record rate-limit, timeout, malformed-response, and retry counts.
- [x] Record generation, embedding, retry, wrapper, and total cost fields.
- [x] Record failure-closed tests and controlled provider failures.
- [x] Record synthetic-versus-real comparison limitations.
- [x] Record credentials and raw-content redaction verification.
- [x] Record unavailable provider evidence and its effect on conclusions.
- [x] Link the evidence from `PHASE_2_IMPLEMENTATION_PLAN.md`.

Step 12 evidence: [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md).
The provider run is explicitly unavailable; this does not complete the
credentialed real-provider acceptance criterion.

## Test plan

### Unit tests

- [x] Valid generation response becomes a validated `LLMResult`
  (`tests/test_remote_llm.py`, `tests/test_llm.py`).
- [x] Missing generation text is rejected (`tests/test_remote_llm.py`).
- [x] Negative or malformed generation token counts are rejected
  (`tests/test_remote_llm.py`).
- [x] Valid embedding response becomes a validated `EmbeddingResult`
  (`tests/test_remote_embedding.py`).
- [x] Wrong embedding model is rejected (`tests/test_remote_embedding.py`).
- [x] Wrong embedding dimension is rejected (`tests/test_remote_embedding.py`).
- [x] Non-finite embedding values are rejected (`tests/test_remote_embedding.py`).
- [x] Empty generation and embedding input are rejected before transport
  (`tests/test_remote_llm.py`, `tests/test_remote_embedding.py`).
- [x] Provider errors map to bounded categories
  (`tests/test_remote_llm.py`, `tests/test_remote_embedding.py`).
- [x] Exception text and response bodies are not serialized
  (`tests/test_remote_llm.py`, `tests/test_remote_embedding.py`).
- [x] Missing token usage remains unavailable or explicitly estimated
  (`tests/test_remote_llm.py`, `tests/test_remote_embedding.py`).
- [x] Retry count and measured latency remain bounded
  (`tests/test_remote_llm.py`, `tests/test_retry.py`).

### Retry and failure tests

- [x] First-attempt success performs no retry
  (`tests/test_provider_retry_failures.py`).
- [x] Retryable transient error retries within the configured budget
  (`tests/test_provider_retry_failures.py`, `tests/test_remote_llm.py`).
- [x] Rate-limit response records a bounded rate-limit event
  (`tests/test_provider_retry_failures.py`, `tests/test_retry.py`).
- [x] Permanent provider error does not retry
  (`tests/test_provider_retry_failures.py`).
- [x] Authentication and authorization errors do not retry
  (`tests/test_provider_retry_failures.py`).
- [x] Malformed provider response does not retry
  (`tests/test_provider_retry_failures.py`, `tests/test_remote_llm.py`).
- [x] Retry-after cannot exceed the remaining request budget
  (`tests/test_provider_retry_failures.py`, `tests/test_retry.py`).
- [x] Retry exhaustion returns a controlled non-reusable failure
  (`tests/test_provider_retry_failures.py`).
- [x] Timeout does not return a partial answer or vector
  (`tests/test_provider_retry_failures.py`).
- [x] Provider failure does not produce a cache hit
  (`tests/test_provider_retry_failures.py`, `tests/test_metrics.py`).
- [x] Provider failure does not insert an unvalidated cache entry
  (`tests/test_provider_retry_failures.py`,
  `tests/test_workstream3_failure_paths.py`).

### Integration tests

- [x] Exact cache hit avoids embedding and generation provider calls
  (`tests/test_provider_integration.py`).
- [x] Semantic cache hit records embedding measurement and avoids generation
  (`tests/test_provider_integration.py`).
- [x] Semantic miss records embedding and generation measurements
  (`tests/test_provider_integration.py`).
- [x] `UNSAFE` candidate causes generation through the configured adapter
  (`tests/test_provider_integration.py`).
- [x] `UNCERTAIN` candidate causes generation through the configured adapter
  (`tests/test_provider_integration.py`).
- [x] A generation failure preserves the Workstream 3 decision trace
  (`tests/test_provider_integration.py`,
  `tests/test_workstream3_failure_paths.py`).
- [x] An embedding failure preserves failure-closed semantic behavior
  (`tests/test_provider_integration.py`,
  `tests/test_provider_retry_failures.py`).
- [x] Post-generation and duplicate-write paths retain the same safety boundary
  (`tests/test_provider_integration.py`,
  `tests/test_workstream3_strategy_c_paths.py`).
- [x] Provider mode does not change candidate ordering or freshness decisions
  (`tests/test_provider_integration.py`).
- [x] Real-provider integration tests skip safely without credentials
  (`tests/test_provider_integration.py`).
- [x] Explicit opt-in with invalid configuration fails clearly
  (`tests/test_provider_integration.py`, `tests/test_provider_config.py`).

### Accounting and boundary tests

- [x] Provider-reported token usage is distinct from estimates
  (`tests/test_provider_accounting_boundary.py`, `tests/test_remote_llm.py`).
- [x] Exact-hit cost excludes embedding and generation
  (`tests/test_pricing.py`, `tests/test_provider_accounting_boundary.py`).
- [x] Semantic-hit cost includes embedding and excludes generation
  (`tests/test_pricing.py`, `tests/test_provider_accounting_boundary.py`).
- [x] Miss cost includes embedding and generation where both occurred
  (`tests/test_pricing.py`, `tests/test_provider_accounting_boundary.py`).
- [x] Retry costs follow the declared billing rule
  (`tests/test_pricing.py`, `tests/test_provider_accounting_boundary.py`).
- [x] Wrapper cost is included once
  (`tests/test_pricing.py`).
- [x] Unavailable prices or usage remain unavailable, not zero by implication
  (`tests/test_provider_accounting_boundary.py`, `tests/test_provider_measure.py`).
- [x] Real and synthetic measurements carry different environment labels
  (`tests/test_provider_accounting_boundary.py`, `tests/test_provider_compare.py`).
- [x] Reports include dataset, split, configuration, pricing, and schema
  versions (`tests/test_provider_accounting_boundary.py`,
  `tests/test_provider_measure.py`).
- [x] Reports contain no credentials, authorization headers, raw prompts,
  answers, embeddings, response bodies, or secret-like fields
  (`tests/test_provider_accounting_boundary.py`, `tests/test_provider_measure.py`,
  `tests/test_serialization_boundary.py`).
- [x] Boundary serialization preserves `SAFE`, `UNSAFE`, and `UNCERTAIN`
  (`tests/test_provider_accounting_boundary.py`,
  `tests/test_serialization_boundary.py`, `tests/test_workstream1_contract.py`).
- [x] Trace count, metadata, and report payload bounds remain enforced
  (`tests/test_provider_accounting_boundary.py`, `tests/test_trace_contract.py`,
  `tests/test_serialization_boundary.py`).

### Regression tests

- [x] Existing deterministic fake-provider tests remain green
  (`tests/test_workstream4_regression.py`, full suite).
- [x] Existing Workstream 1 contract tests remain green
  (`tests/test_workstream4_regression.py`, `tests/test_workstream1_contract.py`).
- [x] Existing Workstream 3 failure-closed tests remain green
  (`tests/test_workstream4_regression.py`,
  `tests/test_workstream3_failure_paths.py`).
- [x] Default full-suite execution makes no network calls
  (`tests/test_workstream4_regression.py`; verified by `python -m pytest -q`).
- [x] Production configuration continues to require explicit non-fake
  provider clients where applicable
  (`tests/test_workstream4_regression.py`, `tests/test_admin.py`).
- [x] Existing benchmark reports remain labeled synthetic unless generated by
  the real-provider command
  (`tests/test_workstream4_regression.py`, `tests/test_provider_measure.py`).

## Verification commands

Run from the repository root after implementation. Replace placeholders only
in the opt-in commands; never place credential values directly in a command
line or checked-in file.

```bash
python -m pytest -q tests/test_query.py tests/test_embedding.py tests/test_config.py
python -m pytest -q tests/test_failure_paths.py tests/test_workstream3_failure_paths.py
python -m pytest -q tests/test_serialization_boundary.py tests/test_trace_contract.py
python -m pytest -q
python -m sscre.benchmark_validate --benchmark-dir benchmarks
python -m sscre.evaluate \
  --benchmark benchmarks/development.jsonl \
  --config experiments/evaluation_config.json \
  --baseline compatibility-cache \
  --split development \
  --output artifacts/evaluation/workstream4-development.json
```

The live-provider command must be documented after its interface is frozen,
for example:

```bash
SSCRE_REAL_PROVIDER=1 python -m pytest -q -m real_provider
```

The exact command, provider availability, dataset/configuration versions,
test count, skipped tests, and redacted artifact path must be recorded in the
completion evidence. The default full suite must remain runnable without
provider credentials.

For each successful verification, record:

- command and date;
- Python and package versions;
- provider/API/SDK versions, when applicable;
- provider, model, endpoint origin, dataset, split, and pricing versions;
- test count and skipped tests;
- request-path and provider failure counts;
- token usage provenance;
- cost and latency accounting rules;
- repository/provider dependencies used;
- pass/fail result;
- known limitations.

Do not mark live-provider, held-out, quality, statistical, or production
capacity claims complete when the corresponding check was not run
successfully.

## Acceptance criteria

- [x] One real generation provider is implemented behind the existing
  provider-independent interface.
- [x] One real embedding provider is implemented behind the existing
  provider-independent interface.
- [x] Real-provider selection is explicit and opt-in.
- [x] Fake providers remain deterministic test doubles and are not mislabeled
  as real-provider evidence.
- [x] Provider, endpoint, model, timeout, retry, and experiment configuration
  is versioned and validated.
- [x] Credentials come only from an approved runtime secret source.
- [x] Credentials, raw prompts, answers, embeddings, and provider payloads do
  not appear in logs, reports, exceptions, or checked-in configuration.
- [x] Provider responses are validated before entering the request path.
- [x] Retry and backoff behavior is bounded and tested.
- [x] Rate limits, timeouts, malformed responses, and provider errors have
  bounded categories and tests.
- [x] Provider failures cannot produce a cache hit or unvalidated cache entry.
- [x] Existing `SAFE`, `UNSAFE`, and `UNCERTAIN` semantics are unchanged.
- [x] Request, provider, retry, and wrapper latency are separately defined.
- [x] Provider-reported, estimated, and unavailable token usage are distinct.
- [x] Pricing inputs have version, currency, units, and effective date.
- [x] Embedding, generation, retry, wrapper, and total estimated costs are
  accounted for without double counting.
- [x] Exact cache hits do not incur unnecessary embedding or generation cost.
- [x] Opt-in provider tests skip safely when credentials are unavailable.
- [x] The default test suite performs no remote provider calls.
- [x] At least one redacted real-provider run is reproducible from a frozen
  development configuration and versioned dataset, or an unavailable-provider
  report explicitly records why it could not run.
- [x] Synthetic and real-provider results are separately labeled in all
  reports and comparisons.
- [x] Held-out labels are not used to tune thresholds or compatibility rules.
- [x] Completion evidence is linked from the Phase 2 parent plan:
  [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md).

## Completion evidence

Recorded in [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md):

- [x] provider adapter files and interface versions;
- [x] redacted provider configuration and pricing schedule versions;
- [x] provider/API/SDK and Python/package versions (`runtime_versions`; SDK null);
- [x] dataset and split identity;
- [x] live-test command and pass/skip/fail result (skipped iteration 1);
- [x] real-provider run command and artifact path (unavailable artifact);
- [x] request-path counts (unavailable run: zero; paths covered in integration tests);
- [x] provider latency and total request latency summaries (unavailable);
- [x] token usage counts by provenance (unavailable);
- [x] retry, rate-limit, timeout, malformed-response, and auth counts (failure schema in measure artifact);
- [x] generation, embedding, retry, wrapper, and total cost summaries (unavailable);
- [x] failure-closed test results;
- [x] serialization and redaction test results;
- [x] synthetic-versus-real comparison artifact;
- [x] unavailable measurements and their consequences;
- [x] known nondeterminism and provider-drift limitations;
- [x] targeted and full-suite verification results (`557 passed, 14 skipped`).

Do not mark real-provider criteria complete based only on adapter code. Each
completion mark requires a corresponding test, run artifact, or documented
unavailability record.

## Handoff to later workstreams

Workstream 5 consumes provider-labeled measurements for confidence intervals,
baseline comparison, and Pareto analysis. Workstream 6 consumes provider
latency/cost observations only where freshness workloads are explicitly
identified. Workstream 7 consumes bounded provider failure categories and
approved examples. Workstream 8 remains responsible for PostgreSQL and
multi-process behavior.

Handoff requirements (see [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md)):

- [x] Publish provider, model, endpoint, API/SDK, dataset, split, and pricing
  versions (unavailable fields explicit where not observed).
- [x] Publish the redacted run configuration and exact command.
- [x] Publish token and latency field provenance.
- [x] Publish retry, rate-limit, timeout, and malformed-response semantics.
- [x] Publish cost inclusion and unavailable-cost rules.
- [x] Confirm that only `SAFE` remains reusable.
- [x] Confirm that provider failures remain failure-closed.
- [x] Confirm that synthetic and real measurements are separately labeled.
- [x] Confirm that no held-out labels were used for threshold selection.
- [x] Document provider nondeterminism, drift, quotas, and rate-limit limits.
- [x] Link completion evidence from
  [`PHASE_2_IMPLEMENTATION_PLAN.md`](./PHASE_2_IMPLEMENTATION_PLAN.md).

## Execution sequence

1. [x] Audit existing provider interfaces, request paths, metrics, and
   serialization fields.
2. [x] Freeze the redacted provider configuration and error taxonomy.
3. [x] Implement and unit-test one remote generation adapter.
4. [x] Implement and unit-test one remote embedding adapter.
5. [x] Add bounded retry, timeout, rate-limit, and backoff behavior.
6. [x] Integrate the adapters without changing Workstream 3 safety semantics.
7. [x] Add token, latency, pricing, and cost accounting.
8. [x] Add opt-in live tests and local transport failure tests.
9. [x] Run the fixed development workload with a redacted configuration
   (unavailable artifact; live observation deferred).
10. [x] Build the synthetic-versus-real comparison artifact.
11. [x] Run targeted tests and the full suite without credentials.
12. [x] Record evidence, limitations, and the Workstream 5 handoff in
   [`WORKSTREAM_4_EVIDENCE.md`](./WORKSTREAM_4_EVIDENCE.md).

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Credentials leak through logs or exceptions | Load from runtime secrets, redact configuration, reject forbidden fields, and test serialized output. |
| Remote errors become cache hits | Reuse the existing failure-closed boundaries and test provider failures through the full request path. |
| Retry behavior hides provider instability | Bound attempts and elapsed time; record retry and rate-limit counts separately. |
| Provider response shape changes | Validate the response contract and pin/document API or SDK versions. |
| Wrong embedding dimension corrupts retrieval | Require explicit dimension and reject mismatches before cache use or insert. |
| Missing token usage is reported as zero | Preserve `provider_reported`, `estimated`, and `unavailable` provenance. |
| Cost is double counted | Define path-specific accounting and test exact hit, semantic hit, miss, and retry cases. |
| Synthetic zero-cost values contaminate real results | Add explicit environment labels and keep report rows separate. |
| Live tests spend too much or hit quotas | Require opt-in, cap requests and spend, use development data, and skip safely by default. |
| Provider nondeterminism is mistaken for cache behavior | Compare decisions and accounting fields separately from answer-text equality. |
| Held-out labels influence configuration | Freeze configuration before held-out use and limit this workstream to development measurements. |
| Adapter abstraction grows beyond the need | Implement one vertical slice behind existing interfaces and defer multi-provider routing. |
| Provider latency is confused with application capacity | Separate provider measurements from Workstream 8 database and load claims. |
| Provider drift invalidates reproduction | Record model/API/pricing dates and report the limits of replayability. |
