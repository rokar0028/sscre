# Provider boundary (Gate C)

**Parent:** Workstream 1 Step 1.5 — [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Code:** [`src/sscre/provider_config.py`](../../src/sscre/provider_config.py), [`src/sscre/provider_measure.py`](../../src/sscre/provider_measure.py)

Workstream 1 does **not** add a provider SDK or run live provider calls under
Gate A.

## Supported integration model

A production or research provider must implement the existing **OpenAI-compatible**
HTTP boundary already assumed by the configuration layer:

- Generation and embedding requests through a documented endpoint URL
- Model identifiers supplied via `SSCRE_PROVIDER_GENERATION_MODEL` and
  `SSCRE_PROVIDER_EMBEDDING_MODEL`
- Embedding dimension declared via `SSCRE_PROVIDER_EMBEDDING_DIMENSION`

Compatible hosted stacks (Gemini, OpenRouter, Ollama with an OpenAI-compatible
facade, or similar) may be used **only** after explicit review that the
endpoint, models, and dimensions match this contract. A provider-specific SDK or
transport requires a **separately reviewed adapter** — out of scope for WS1.

## Opt-in environment (not in `.env.example`)

Real provider measurement uses `SSCRE_REAL_PROVIDER=true` and the `SSCRE_PROVIDER_*`
variables defined in `provider_config.py`. Live network calls additionally require
`SSCRE_REAL_PROVIDER_LIVE=true` and `SSCRE_PROVIDER_CREDENTIAL`.

Pricing replay uses `SSCRE_PROVIDER_PRICING_JSON` and
`SSCRE_PROVIDER_PRICING_SCHEDULE_ID` (see
[`PHASE4_PROVIDER_EVIDENCE.md`](../phase-4/PHASE4_PROVIDER_EVIDENCE.md)).

## Gate rules

| Gate | Provider behavior |
| --- | --- |
| A (unit tests, default pytest) | Fake/deterministic clients only |
| B (PostgreSQL) | No live provider required |
| C (authorized provider) | Credentials, quota, pricing, and approval out of band; redacted artifacts only |

When credentials or authorization are missing, commands must fail closed with
`unavailable` (for example `live_opt_in_missing`) — **never** substitute
synthetic measurements for live provider evidence.

Free-tier or trial endpoints are not assumed unlimited or production-suitable.

## Related commands

```powershell
# Fail-closed unavailable path (no credential) — Gate A safe
$env:SSCRE_REAL_PROVIDER_LIVE = 'false'
$env:SSCRE_REAL_PROVIDER = 'false'
$env:SSCRE_PROVIDER_PRICING_JSON = 'experiments/real_provider_pricing.json'
python -m sscre.provider_measure --benchmark benchmarks/development.jsonl `
  --config experiments/evaluation_config.json `
  --output artifacts/evaluation/phase4-provider-validation.json
```

Opt-in live tests: `pytest -m real_provider` with `SSCRE_REAL_PROVIDER_LIVE=true`
(see [`LOCAL_ENVIRONMENT_MODES.md`](./LOCAL_ENVIRONMENT_MODES.md)).
