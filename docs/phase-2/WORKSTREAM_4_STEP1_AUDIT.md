# Workstream 4 Step 1 Audit

## Audit status

**Completed:** 2026-10-07
**Scope:** provider boundary, request call sites, measurement fields,
serialization boundary, and available HTTP dependencies.
**Result:** the existing fake-provider interfaces are suitable extension
points, but real-provider measurement requires new provider adapters,
provider-aware accounting fields, and an explicit opt-in configuration.

This audit does not add a provider, change the safety contract, or claim that
real-provider measurements exist.

## Evidence reviewed

| Area | Artifact |
|---|---|
| Generation result and fake client | `src/sscre/llm.py` |
| Embedding protocol, result, validation, and fake client | `src/sscre/embedding.py` |
| Request orchestration and dependency budgets | `src/sscre/app.py` |
| Runtime settings and environment parsing | `src/sscre/config.py` |
| Request counters and metrics snapshot | `src/sscre/metrics.py` |
| Synthetic baseline reports and accounting | `src/sscre/baseline.py` |
| Evaluation configuration and report metadata | `src/sscre/evaluate.py` |
| Log/report redaction and bounds | `src/sscre/serialization.py` |
| Declared runtime and development dependencies | `pyproject.toml` |
| Frozen boundary rules | `docs/phase-2/SERIALIZATION_BOUNDARY_v1.md` |

## 1. Provider interface inventory

### Generation

`src/sscre/llm.py` defines:

- `LLMResult(text, input_tokens, output_tokens, latency_ms)`;
- `validate_llm_result()`, which checks result type, text type, and
  non-negative token/latency values;
- `MockLLMClient.generate(query)`, the deterministic local implementation.

There is no shared `LLMClient` protocol in `llm.py`. The baseline module
defines a structural `BaselineLLMClient` protocol containing only
`generate(query) -> LLMResult`, while `app.py` currently types its injected
client as `MockLLMClient | None`. A real generation adapter can preserve the
runtime shape, but a small provider-independent protocol/type boundary should
be made explicit before adapter implementation.

Current generation result gaps:

- no provider or model identity;
- no usage provenance (`provider_reported`, `estimated`, `unavailable`);
- no retry or attempt count;
- no provider-call versus wrapper latency distinction;
- no error category or rate-limit metadata.

### Embedding

`src/sscre/embedding.py` defines:

- `EmbeddingConfig(model_name, dimension)`;
- `EmbeddingResult(vector, model_name, input_tokens, latency_ms)`;
- `EmbeddingClient` protocol with `config` and `embed(text)`;
- `validate_embedding_text()` and `validate_embedding_result()`;
- `FakeEmbeddingClient`, which creates deterministic vectors and configurable
  token/latency values.

The embedding protocol is already a suitable provider-independent adapter
boundary. It requires the remote adapter to expose the configured model and
dimension and return a validated finite vector of the exact configured size.

Current embedding result gaps:

- no usage provenance;
- no provider identity or endpoint/API version;
- no retry or attempt count;
- no distinction between provider-call and wrapper latency;
- no provider error category.

## 2. Request-path call-site inventory

`src/sscre/app.py` has these relevant paths:

| Path | Current behavior | Measurement consequence |
|---|---|---|
| Exact lookup before semantic retrieval | Looks up by query hash | Exact hits avoid embedding and generation; response metrics record total latency only. |
| Semantic lookup | Calls `vector_client.embed()` under the embedding timeout, validates the result, then searches the repository | Embedding result has tokens/latency, but request metrics and logs do not expose embedding-specific fields. |
| Strategy C candidate evaluation | Evaluates candidates using the frozen Workstream 3 boundary | Provider choice must not change candidate decisions, ordering, freshness, or trace serialization. |
| Generation fallback | Calls `model_client.generate()` under the generation timeout, then validates `LLMResult` | Generation result contributes LLM latency/tokens to response metrics; retry/provider provenance is absent. |
| Post-generation embedding | Embeds again when semantic caching is enabled and no earlier embedding exists | This call can incur a second embedding request on a miss after generation; accounting must distinguish it from lookup embedding. |
| Cache insertion | Stores the generated answer only when embedding and cache-control conditions permit | Embedding failure returns the generated answer but skips cache insertion; this must remain failure-closed. |
| Post-generation exact recheck / duplicate recovery | Re-evaluates a raced entry before reuse under Strategy C | Remote provider errors must not bypass this safety boundary. |

`run_with_timeout()` executes dependency calls with bounded budgets and the
request path calculates remaining request time before dependency calls. This
is a local timeout boundary, not provider retry behavior. Provider adapters
must keep their retry budget within the remaining request budget.

## 3. Current measurement fields and provenance

| Field | Current owner | Current source | Real-provider gap |
|---|---|---|---|
| `LLMResult.latency_ms` | `llm.py` | Client-reported/configured result value | Must define provider-call latency and retry inclusion. |
| `LLMResult.input_tokens` | `llm.py` | Fake word count today | Must preserve provider-reported versus estimated usage. |
| `LLMResult.output_tokens` | `llm.py` | Fake generated-text word count today | Same provenance gap. |
| `EmbeddingResult.latency_ms` | `embedding.py` | Fake configured value today | Exists at result level but is not surfaced in request metrics. |
| `EmbeddingResult.input_tokens` | `embedding.py` | Fake word count/configured value today | Needs provider-reported/estimated/unavailable state. |
| `RequestMetrics.total_latency_ms` | `metrics.py` / `app.py` | Monotonic request elapsed time | Does not break out cache, embedding, generation, retries, or wrapper work. |
| `RequestMetrics.llm_latency_ms` | `metrics.py` / `app.py` | `LLMResult.latency_ms` | Generation-only; no provider identity or attempt details. |
| `RequestMetrics.llm_input_tokens` | `metrics.py` / `app.py` | `LLMResult.input_tokens` | Generation-only; no usage provenance. |
| `RequestMetrics.llm_output_tokens` | `metrics.py` / `app.py` | `LLMResult.output_tokens` | Generation-only; no usage provenance. |
| `embedding_tokens` | `baseline.py` | `EmbeddingResult.input_tokens` | Exists in synthetic reports, but not request metrics or provider metadata. |
| `total_latency_ms` in baselines | `baseline.py` | Fake result latency plus selected local timings | Synthetic aggregate; not a remote provider observation. |
| `p50/p95/p99_latency_ms` | `baseline.py` | Synthetic per-request baseline timings | No provider/retry/wrapper decomposition. |
| `estimated_cost_usd` | `baseline.py` | Configured per-1K token rates and wrapper fields | Current config rates are placeholders/zero and do not include retry provenance. |
| `input_cost_per_1k_tokens` | `evaluate.py` config | JSON configuration | No pricing schedule version, currency, or effective date. |
| `output_cost_per_1k_tokens` | `evaluate.py` config | JSON configuration | Same. |
| `embedding_cost_per_1k_tokens` | `evaluate.py` config | JSON configuration | Same. |
| `cache_lookup_cost_usd` | `evaluate.py` config | JSON configuration | Wrapper accounting exists only in synthetic baseline paths. |
| `preprocessing_cost_usd` | `evaluate.py` config | JSON configuration | Wrapper accounting exists only in synthetic baseline paths. |

The existing fields are enough to retain fake-provider compatibility, but not
enough to support the Workstream 4 requirement to separate provider latency,
wrapper latency, retries, usage provenance, and total estimated cost.

## 4. Measurement emitters and redaction

Current serialization emitters are:

- `POST /v1/query` response metrics and candidate traces;
- `cache_decision` structured logs;
- saved evaluation reports;
- failure examples and observed pair records.

The frozen serialization boundary:

- uses schema version `1.0.0`;
- caps candidate traces at 100;
- caps per-trace metadata at 8 KiB;
- caps the combined trace payload;
- rejects nested forbidden keys including `answer`, `authorization`,
  `normalized_query`, `password`, `prompt`, `provider_secret`, `query`,
  `secret`, and `token`;
- redacts reviewed `query_a`/`query_b` from saved operational failure
  galleries.

Consequences for the provider adapter:

- provider metadata must use approved, bounded names rather than raw payloads;
- credential presence may be represented only as a boolean/configuration
  status, never as a credential value;
- raw prompts, generated answers, embeddings, authorization headers, response
  bodies, and exception payloads cannot be measurement fields;
- any new report fields need boundary tests before they are emitted.

## 5. Dependency and provider selection audit

`pyproject.toml` declares:

- runtime: FastAPI, `psycopg[binary]`, and `uvicorn[standard]`;
- development: pytest and `httpx`.

No provider SDK is declared. `httpx` is already a development dependency and
is therefore available for transport doubles/tests in the current development
environment, but it is not currently a runtime dependency. The repository
contains no existing provider adapter or general remote-provider HTTP client.

Step-1 decision:

- [x] Reuse the existing `LLMResult`, `EmbeddingResult`, and embedding
  protocol boundaries.
- [x] Keep `MockLLMClient` and `FakeEmbeddingClient` as deterministic test
  doubles.
- [x] Implement one provider adapter vertical slice before considering
  multi-provider routing.
- [x] Treat `httpx` as an existing development/test dependency, not as proof
  that runtime provider transport is already implemented.
- [ ] Select and document the first real provider and its API contract in the
  provider-configuration step.
- [ ] Decide whether the selected adapter needs a runtime HTTP dependency;
  record the decision before modifying `pyproject.toml`.

## 6. Required changes identified for later steps

The audit identifies these minimum follow-ups:

1. Make the generation boundary explicit without breaking the existing
   structural client usage.
2. Add provider/model/configuration identity and usage provenance outside the
   frozen safety trace.
3. Add remote generation and embedding adapters with strict response
   validation.
4. Add bounded retry/error taxonomy and keep it inside request budgets.
5. Extend measurement/report schemas for provider, embedding, retry, wrapper,
   and cost fields while preserving redaction.
6. Add provider-specific configuration and a pricing schedule version.
7. Add local transport tests and opt-in live tests.

None of these changes should alter Workstream 3 candidate decisions,
freshness handling, trace limits, or the rule that only `SAFE` is reusable.

## 7. Audit conclusions

- [x] Existing fake generation and embedding clients are deterministic test
  doubles that can remain in the default test path.
- [x] The embedding protocol is an adequate provider-independent extension
  point.
- [x] Generation has an implicit structural boundary that should be made
  explicit before adapter implementation.
- [x] Request-level timeout budgeting exists and must constrain provider retry
  behavior.
- [x] Current metrics expose generation tokens/latency but not embedding,
  retry, provider, or wrapper measurements.
- [x] Synthetic baseline cost fields exist but are not real-provider pricing
  evidence.
- [x] Serialization is bounded and rejects credential/raw-content fields.
- [x] No provider SDK or runtime HTTP adapter currently exists.
- [x] A real-provider run is not currently available from the checked-in
  implementation.

The audit is complete. Step 2 can freeze the redacted provider configuration,
error taxonomy, and first-provider choice using this document as input.
