# Post–Phase 4 stabilization — Workstream 2 API and auth boundary (Step 2.1)

**Parent:** [`POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md`](../POST_PHASE4_STABILIZATION_IMPLEMENTATION_PLAN.md)  
**Evidence:** [`POST_PHASE4_WS2_EVIDENCE.md`](./POST_PHASE4_WS2_EVIDENCE.md)  
**Machine-readable:** [`../../artifacts/stabilization/ws2-api-auth-boundary.json`](../../artifacts/stabilization/ws2-api-auth-boundary.json)  
**Related:** [`LOCAL_ENVIRONMENT_MODES.md`](./LOCAL_ENVIRONMENT_MODES.md), [`PROVIDER_BOUNDARY.md`](./PROVIDER_BOUNDARY.md), [`POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md`](./POST_PHASE4_WS1_ENVIRONMENT_CONTRACT.md)

This document freezes the **threat model** and **deployment contract** for
public API safety. Step 2.1 is read-only with respect to application behavior;
enforcement is authorized in Steps 2.2–2.8.

## Deployment modes

| Mode | Intent | Authorized use |
| --- | --- | --- |
| **Trusted-local** | Single operator, single implicit tenant, no Internet-facing multi-user API | Local research, Gate A unit tests, development Compose on a private network |
| **External** | Multi-tenant API with authenticated client identity | External or multi-user deployment **only after** Workstream 2 verification gate passes |

**External mode status (Step 2.1 close):** `deferred` — no approved client-auth
adapter, tenant registry, or scoped storage is implemented in code yet. Compose
and the default API remain **trusted-local** evidence only. Operators must not
treat an open host port map (`SSCRE_API_PORT`) as external-mode authorization.

## Trusted-local ingress requirements

- Bind the API to **loopback** (`127.0.0.1`) or a **private** interface that
  is not reachable from the public Internet without an operator-controlled
  boundary (VPN, SSH tunnel, corporate LAN with firewall rules).
- Treat **development Compose** as trusted-local: the `api` service listens on
  `0.0.0.0:8000` inside the container and publishes
  `${SSCRE_API_PORT:-8000}:8000` on the host ([`Dockerfile`](../../Dockerfile),
  [`docker-compose.yml`](../../docker-compose.yml)). That publish is for local
  development convenience, not external deployment readiness.
- Do not expose PostgreSQL (`SSCRE_POSTGRES_PORT`) or admin tokens to untrusted
  networks. Admin bearer tokens (`SSCRE_ADMIN_TOKEN`, `SSCRE_ADMIN_READ_TOKEN`)
  are secrets with cache-read scope; they are not client query credentials.
- Gate A pytest and in-memory `create_app()` tests do not prove ingress or
  tenancy boundaries.

## External-mode requirements (target contract)

Before any route is described as externally reachable:

- **Client authentication:** every `POST /v1/query` request resolves to exactly
  one `tenant_id` and optional `namespace_id` from verified credentials — not
  from an unauthenticated `X-Tenant-ID`, query parameter, or JSON body field.
- **Separate admin plane:** existing admin bearer tokens authorize
  `/v1/cache/stats` only; they must not substitute for tenant client identity
  on `/v1/query`.
- **Transport:** TLS termination at the API or a trusted reverse proxy; no
  cleartext client tokens across untrusted networks.
- **Scoped storage:** cache lookup, vector search, insertion, eviction,
  statistics, and canonical-answer access are isolated per tenant/namespace
  (Steps 2.3–2.5).
- **Abuse controls:** bounded request body size, per-tenant rate limits and
  provider budgets, safe error bodies (Step 2.7).
- **Evidence:** passing isolation and authorization tests plus redacted artifacts
  recorded in WS2 evidence before the stabilization plan’s external-deployment
  verdict applies.

If the deployment cannot supply an approved client-auth adapter, tenant
registry, or trusted ingress, **external mode remains `deferred`** and the
process must fail closed (startup or ingress rejection), not fall back to
anonymous query access.

## HTTP route inventory

Source: [`src/sscre/app.py`](../../src/sscre/app.py) (`create_app`). No other
HTTP routers are mounted in `src/sscre/` at Step 2.1 close.

| Route | Method | Auth today | Trusted-local | External (target) | Response sensitivity |
| --- | --- | --- | --- | --- | --- |
| `/health` | GET | None | Allowed (liveness) | Allowed if body stays minimal | Low: `{"status":"ok"}` only |
| `/ready` | GET | None | Allowed on trusted ingress | Restrict to probe network or auth gateway | Medium: reveals `repository` kind (`memory` / `postgres`) and migration readiness |
| `/v1/cache/stats` | GET | Bearer admin (`cache:read`) | Allowed with secret token | Admin ingress only; tenant-scoped stats need explicit scope (Step 2.6) | Medium: aggregate storage and in-process request metrics, not answer text |
| `/v1/query` | POST | **None** | Allowed only behind trusted-local ingress | **Requires client auth** before any cache or provider work | **High:** answers, decisions, traces, token/cost metrics |

### `/v1/query` request and validation (baseline)

- Body: JSON `{"query": "<string>"}` via [`QueryRequest`](../../src/sscre/query.py).
- Normalization: trim and collapse whitespace; empty after normalize → `422`.
- Max query length: `8000` characters (`MAX_QUERY_LENGTH`).
- Cache key today: SHA-256 of normalized query only — **global**, not tenant-scoped
  (gap documented for Steps 2.3–2.5).

### Representative `/v1/query` HTTP outcomes (baseline)

| Condition | Status | Notes |
| --- | --- | --- |
| Invalid body / empty query | `422` | Pydantic validation |
| Cache/repository unavailable on lookup | `503` | `X-Request-ID` set |
| Request budget exceeded | `504` | Dependency timeout path |
| Generation failure | `502` | No cache insert; `X-Request-ID` |
| Lock/contention paths | `503` | Documented in failure tests |
| Success | `200` | Cache or generated answer |

## Repository and provider operations reachable from the API

Operations below are invoked from HTTP handlers in `app.py` (directly or via
`run_with_timeout`). CLI evaluation, migrate, and dashboard paths are out of
scope for this HTTP inventory.

### From `POST /v1/query`

| Operation | Repository / client | Purpose |
| --- | --- | --- |
| `get_by_query_hash` | `ExactCacheRepository` | Exact cache lookup (may run twice per request) |
| `record_hit` | optional | Access accounting on cache hit |
| `embed` | `EmbeddingClient` | Semantic retrieval when enabled |
| `search_by_embedding` | `SemanticCacheRepository` when implemented | Top-K vector candidates |
| `generate` / LLM call | `LLMClient` | Miss path |
| `insert_and_evict` or `insert` + `evict_to_limits` | repository | Persist generated answer under caps |
| `delete_by_query_hash` | repository | Unsafe/stale replacement path before re-insert |

Not called from `app.py` today but exist on repositories and matter for tenancy:
`cleanup_expired`, module-level `delete_entries_by_query_hashes` in
[`postgres_cache.py`](../../src/sscre/postgres_cache.py).

### From `GET /ready`

| Operation | Purpose |
| --- | --- |
| `check_ready` | PostgreSQL migration and connectivity probe |

### From `GET /v1/cache/stats`

| Operation | Purpose |
| --- | --- |
| `storage_stats` | Entry counts, bytes, lifecycle counters |
| `MetricsCollector.snapshot` | In-process hit/miss/failure aggregates for current process |

### Authorization helper (admin only today)

`require_admin(authorization, required_scope)` validates Bearer tokens against
`SSCRE_ADMIN_TOKEN` / `SSCRE_ADMIN_READ_TOKEN` with expiry checks and scopes
`cache:read` / `cache:write` (write scope configured for future admin routes).

## Protected assets

| Asset | Location / exposure | Why it matters |
| --- | --- | --- |
| Cached answers | `cache_entries`, in-memory map | Confidentiality and integrity of reused content |
| Query text and normalized form | Request body, logs (must stay bounded) | Privacy and cache poisoning input |
| Query metadata | JSON on entries | Strategy C compatibility decisions |
| Embeddings | Entry rows / vectors | Semantic retrieval and cross-query linkage |
| Canonical answers | `canonical_answers` / in-memory canonical store | Shared answer bodies; cross-tenant leakage risk if unscoped |
| Provider capacity | Thread pool, semaphores, timeouts | DoS and cost amplification |
| Provider spend | Generation and embedding calls | Financial abuse |
| Storage limits | `max_cache_entries`, `max_cache_bytes` | Exhaustion and eviction side channels |
| Request metrics | Response `metrics`, `/v1/cache/stats` | Operational intelligence; label cardinality abuse |
| Readiness state | `/ready` | Infrastructure fingerprinting |
| Admin tokens | Environment / Compose | Full cache statistics and future purge scope |

## Threat model

| ID | Threat | Affected assets | Baseline exposure | Target control (WS2) |
| --- | --- | --- | --- | --- |
| T-01 | Unauthenticated cache read via `/v1/query` | Answers, metadata | **Open** on any host that can reach the API | Client auth + scoped lookup |
| T-02 | Cache poisoning (insert malicious answers) | Cache integrity | **Open** — any caller can populate cache | Auth + scoped insert |
| T-03 | Cross-tenant exact hit | Answers | **Open** — global `query_hash` | Tenant/namespace key (Step 2.3) |
| T-04 | Cross-tenant semantic selection | Answers, embeddings | **Open** — vector search unscoped | Scoped `search_by_embedding` |
| T-05 | Canonical-answer disclosure across tenants | Canonical store | **Mitigated** — joins scoped; canonical rows may be shared by hash | [`POST_PHASE4_WS2_STORAGE_ISOLATION.md`](./POST_PHASE4_WS2_STORAGE_ISOLATION.md) |
| T-06 | Provider abuse (generation/embedding flood) | Provider spend, capacity | Partial — timeouts only | Rate limits + budgets (Step 2.7) |
| T-07 | Oversized payload DoS | CPU, memory | Partial — `8000` char query limit | HTTP body limit + byte caps (Step 2.7) |
| T-08 | Bearer token leakage | Admin and future client tokens | Ops risk | TLS, rotation, no token logging |
| T-09 | High-cardinality metrics / log abuse | Metrics, logs | Low today (in-process) | Bounded labels (Step 2.7) |
| T-10 | `/ready` infrastructure probing | Readiness | **Open** on published port | Ingress restriction (Step 2.6) |
| T-11 | Admin token used as query credential | Authorization model | Misconfiguration risk | Separate client credentials (Step 2.2) |
| T-12 | Tenant existence oracle via errors | Auth UX | Not applicable until client auth exists | Stable 401/403 without provider calls (Step 2.2) |

## Evidence required before external exposure

| Gate | Evidence |
| --- | --- |
| Contract frozen | This document + `ws2-api-auth-boundary.json` at recorded commit |
| Client auth | Implemented and tested (Step 2.2+) |
| Tenancy | Scoped keys and repository predicates (Steps 2.3–2.5) |
| Abuse | Rate/quota tests (Step 2.7) |
| Verification | WS2 evidence package, redaction audit, optional Gate B PostgreSQL isolation tests |
| Documentation | Stabilization plan WS2 verification gate checked; no claim of multi-user readiness until then |

## Open baseline gaps (Step 2.1)

- `POST /v1/query` has **no** client authentication.
- Cache identity is **global** per normalized query hash.
- Docker API image binds `0.0.0.0` and publishes a host port by default.
- External mode is **`deferred`** until later WS2 steps land.

These gaps are intentional inputs to Step 2.2, not regressions introduced by
Step 2.1.

## Client credential contract (Step 2.2)

**Code:** [`src/sscre/api_auth.py`](../../src/sscre/api_auth.py)  
**Sample registry:** [`experiments/client_auth_registry_sample.json`](../../experiments/client_auth_registry_sample.json)

### Exposure mode

| `SSCRE_API_EXPOSURE_MODE` | `/v1/query` behavior |
| --- | --- |
| `trusted_local` (default) | Anonymous access allowed; implicit single-tenant context for later tenancy steps |
| `external` | Bearer client token required before preprocessing, cache access, or provider calls |

`SSCRE_CLIENT_AUTH_JSON` must point to a registry file when mode is `external`.
`Settings` and `sscre-env-validate` reject external mode without a valid registry.
`create_app()` fails closed if external mode is configured without loadable credentials.

### Token scheme

- Header: `Authorization: Bearer <token>`
- Constant-time comparison via `hmac.compare_digest`
- Minimum token length: 16 characters
- Optional `expires_at` (timezone-aware ISO-8601); expired tokens → `401 authentication expired`
- Registry schema: `sscre-client-auth-registry-1.0`

### Scopes

| Scope | Use |
| --- | --- |
| `query:execute` | Required on credentials that may call `POST /v1/query` |

Admin scopes (`cache:read`, `cache:write`) remain on `SSCRE_ADMIN_TOKEN` /
`SSCRE_ADMIN_READ_TOKEN` only. Presenting an admin token on `/v1/query` returns
`401 invalid authentication` (same message as an unknown token).

### Failure responses (`POST /v1/query`, external mode)

| Condition | Status | `detail` | Provider/cache work |
| --- | --- | --- | --- |
| Missing header | `401` | `authentication required` | None |
| Malformed / unknown token | `401` | `invalid authentication` | None |
| Expired token | `401` | `authentication expired` | None |
| Insufficient scope | `403` | `insufficient privileges` | None |
| Registry unavailable | `503` | `client authentication unavailable` | None |

Protected failures include `X-Request-ID`. `401` responses include
`WWW-Authenticate: Bearer`.

### Request context (internal)

`RequestContext` carries `request_id`, `principal_id`, `tenant_id`,
`namespace_id`, and `scopes`. Raw bearer tokens are not passed to repositories
or logs. Tenancy enforcement in storage uses this context in Steps 2.3–2.5.

## Cache identity and scoped keys (Step 2.3)

**Code:** [`src/sscre/query.py`](../../src/sscre/query.py), [`src/sscre/cache.py`](../../src/sscre/cache.py)

- Canonical tuple: `(tenant_id, namespace_id, normalized_query)`.
- **Content fingerprint** (`content_query_hash`): SHA-256 of normalized query
  text only (v1 diagnostic; same as legacy `hash_query`).
- **Storage key** (`query_hash` in API/repository): SHA-256 of versioned payload
  `v2\\n{tenant_id}\\n{namespace_id}\\n{normalized_query}` (`CACHE_KEY_VERSION`).
- `QueryRequest` rejects extra JSON fields (`extra="forbid"`) so callers cannot
  supply `tenant_id` or `namespace_id` in the body.
- Semantic search filters by authenticated `tenant_id` and `namespace_id`.
- In-memory eviction under caps is scoped per tenant/namespace.
- PostgreSQL: migration `012_cache_tenant_namespace.sql` adds
  `tenant_id`, `namespace_id`, `content_query_hash`; legacy rows backfill to
  `legacy-unscoped`.

**Public responses:** `selected_candidate_query_hash` and trace
`candidate_query_hash` values are **scoped storage keys**. They are opaque to
other tenants and are not authorization credentials.

## Route authorization and operational exposure (Step 2.6)

**Code:** [`src/sscre/api_auth.py`](../../src/sscre/api_auth.py),
[`src/sscre/app.py`](../../src/sscre/app.py)

### Route matrix

| Route | Trusted local | External |
| --- | --- | --- |
| `GET /health` | Unauthenticated; body is `{"status":"ok"}` only | Same — no tenant, provider, DB, or capacity fields |
| `GET /ready` | Unauthenticated on trusted ingress | Bearer admin token with `health:ready` |
| `GET /v1/cache/stats` | Admin `cache:read` | Admin `cache:read` only (not client credentials) |
| `POST /v1/query` | Anonymous | Client bearer with `query:execute` |

### Cache statistics scope

- Default (no query params): **platform-wide** entry and byte counts for operators
  holding admin `cache:read`. Response field `scope` is `platform`.
- Optional `tenant_id` + `namespace_id` query params: **scoped** counts for that
  namespace only (`scope` = `tenant_namespace`). Both parameters are required
  together; partial input returns `422`.
- Client credentials never receive platform-wide stats; they do not include
  `cache:read`.

### Future routes (scopes reserved, not implemented)

| Planned route | Required scope |
| --- | --- |
| `POST /v1/cache/purge` | `cache:purge` |
| `GET /v1/cache/entries` | `cache:inspect` |
| `POST /v1/cache/export` | `cache:export` |
| `POST /v1/evaluation/run` | `evaluation:run` |

Constants live in `FUTURE_ROUTE_SCOPES` in `api_auth.py`.

### Safe HTTP error bodies

Controlled API failures use fixed `detail` strings (for example
`authentication required`, `cache unavailable`, `service not ready`). They do
not echo SQL, provider payloads, cache row contents, bearer tokens, or whether
another tenant holds a matching key.

### Ingress and Compose (development vs external)

[`docker-compose.yml`](../../docker-compose.yml) publishes the API on
`${SSCRE_API_PORT:-8000}` to the host and uses an **unauthenticated** container
`healthcheck` against `http://127.0.0.1:8000/ready`. That layout is for
**trusted-local development** only.

External deployments must:

- Set `SSCRE_API_EXPOSURE_MODE=external` and supply `SSCRE_CLIENT_AUTH_JSON`.
- Terminate TLS at a reverse proxy or API gateway; do not expose cleartext
  bearer tokens on untrusted networks.
- Restrict `/ready` to probe networks that present an admin bearer with
  `health:ready`, or use `/health` for public load-balancer liveness only.
- Bind the API to private interfaces or place it behind authenticated ingress;
  do not treat default Compose host port publishing as a production boundary.
- Run external mode as a single application process, or provide a shared
  rate-limit/budget store and implementation before using multiple workers or
  replicas. The current abuse controller is process-local.

## Abuse controls (Step 2.7)

**Code:** [`src/sscre/api_abuse_controls.py`](../../src/sscre/api_abuse_controls.py)

| Control | Trusted local | External |
| --- | --- | --- |
| `Content-Length` body cap (`SSCRE_MAX_REQUEST_BODY_BYTES`) | Enforced on `POST /v1/query` | Enforced |
| Query UTF-8 byte cap (`SSCRE_CACHE_MAX_QUERY_BYTES`) | Before cache/provider | Before cache/provider |
| Request rate (`SSCRE_RATE_LIMIT_REQUESTS_PER_MINUTE`) | Disabled when `0` | **Required** > 0; sliding 60s window per `tenant_id:principal_id` |
| Tenant concurrency (`SSCRE_TENANT_MAX_CONCURRENT_QUERIES`) | Enforced when external policy active | In-process admission |
| Provider budget (`SSCRE_TENANT_PROVIDER_BUDGET_PER_MINUTE`) | Disabled when `0` | **Required** > 0; counts embedding + generation starts |

Rate-limit and budget exhaustion return `429` with `Retry-After` and safe
`detail` strings. Tenant concurrency exhaustion returns `503`. Rejected
requests do not call providers or insert cache rows.

External mode rejects startup when rate limit or provider budget env values are
missing or non-positive (`Settings` / `sscre-env-validate`). Limits are
process-local; multi-worker deployments need a shared store before claiming
cluster-wide enforcement.
