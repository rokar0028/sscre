# SSCRE Request Flow

SSCRE sits between a client and an LLM provider. The client sends a query to
SSCRE instead of calling the provider directly.

1. **Receive the request.** The API accepts the user's query and validates its
   shape and size.
2. **Normalize the query.** SSCRE applies deterministic preprocessing, such as
   trimming leading and trailing whitespace and collapsing repeated spaces.
   This prevents formatting-only differences from creating unnecessary cache
   keys.
3. **Search the cache.** The system first checks for an exact match. When
   semantic retrieval is enabled, the default strategy is C: an exact miss
   embeds the query, retrieves top-K candidates, and serves one only when
   compatibility returns `SAFE`. Strategy B is an explicit opt-in that reuses
   the highest-scoring candidate when it meets the similarity threshold.
   Candidates must use the same embedding model and dimension as the query.
   When semantic retrieval is disabled, the request remains exact-cache-only
   and does not call the embedding client.
4. **Check reuse safety.** A candidate is served only when it is compatible with
   the new query and passes freshness rules. If evidence is insufficient, the
   system must generate a new answer.
5. **Generate on a miss.** SSCRE calls the configured LLM client when no safe
   cached answer exists.
6. **Store an eligible answer.** The generated answer and metadata are stored
   for possible reuse, subject to size, freshness, and safety policies.
7. **Return observability data.** The response identifies whether it came from
   the cache or the model and records useful request metrics. Responses expose
   the selected strategy and semantic similarity when Strategy B serves a hit.

The important invariant is conservative behavior: an uncertain cache decision
must fall back to generation rather than risk returning an incompatible answer.
Strategy B is an embedding-only experiment, not a safety decision. High
similarity does not prove that intent, entities, constraints, format, or
freshness are compatible. Strategy C applies deterministic compatibility
rules and generates conservatively when evidence is missing or conflicting.

Each request also receives a UUID and records total latency. Generated responses
include mock input/output token counts and model latency; cache hits report zero
LLM tokens. The application keeps in-memory hit, miss, and generation-failure
counters for the current process, including exact hits, semantic hits, threshold
rejections, and semantic misses.

Generation failures are failure-closed: the failed answer is not cached, a
controlled `502` response is returned with the request ID in the
`X-Request-ID` header, and a structured decision log records the request ID,
decision, source, zero token counts, and latency without logging the answer.

Application-scoped metrics counters are synchronized so concurrent requests
cannot produce inconsistent hit, miss, or failure totals.

## Milestone 10 operational behavior

`/health` is a public liveness probe; `/ready` is the dependency and migration
readiness probe. Query dependency calls have bounded budgets. Repository and
validator failures cannot produce a cache hit, embedding failures fall back to
generation without caching, and cache-write failures preserve a valid
generated response when possible. Administrative statistics require a bearer
token and return bounded summaries only.

When `SSCRE_DATABASE_URL` is configured, the exact-cache lookup and insert use
PostgreSQL. A generated answer is committed to `cache_entries`, and a later API
process can retrieve it by the same query hash. Without that setting,
`create_app()` uses the in-memory repository for isolated unit tests.

## Milestone 9 cache controls

- Stable entries default to a 30-day TTL; semi-dynamic entries default to a
  24-hour TTL. Dynamic entries are not cached unless explicitly enabled with a
  dynamic TTL.
- Expired or policy-ineligible exact and semantic candidates are rejected
  before reuse. TTL availability is separate from Strategy C compatibility.
- Generated answers are content-addressed by a UTF-8 SHA-256 `answer_hash`.
  Query-specific metadata remains on each cache entry, so identical answer
  bodies do not merge incompatible reuse requirements.
- Answer, metadata, query, entry-count, and byte limits are enforced before or
  immediately after insertion. Oversized answers are returned but not cached.
- Cache hits update recency and hit counts. Least-recently-used entries are
  evicted deterministically by `(last_accessed_at, query_hash)`, and orphaned
  canonical answers are removed.
- `GET /v1/cache/stats` exposes bounded storage and lifecycle metrics without
  returning answers, prompts, credentials, or internal reasoning.

These controls bound storage and stale reuse; they do not prove that a
non-expired answer is factually current.
