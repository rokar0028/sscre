# SSCRE Request Flow

SSCRE sits between a client and an LLM provider. The client sends a query to
SSCRE instead of calling the provider directly.

1. **Receive the request.** The API accepts the user's query and validates its
   shape and size.
2. **Normalize the query.** SSCRE applies deterministic preprocessing, such as
   trimming leading and trailing whitespace and collapsing repeated spaces.
   This prevents formatting-only differences from creating unnecessary cache
   keys.
3. **Search the cache.** The system first checks for an exact match. Later
   milestones will also retrieve semantically similar candidates.
4. **Check reuse safety.** A candidate is served only when it is compatible with
   the new query and passes freshness rules. If evidence is insufficient, the
   system must generate a new answer.
5. **Generate on a miss.** SSCRE calls the configured LLM client when no safe
   cached answer exists.
6. **Store an eligible answer.** The generated answer and metadata are stored
   for possible reuse, subject to size, freshness, and safety policies.
7. **Return observability data.** The response identifies whether it came from
   the cache or the model and records useful request metrics.

The important invariant is conservative behavior: an uncertain cache decision
must fall back to generation rather than risk returning an incompatible answer.

Each request also receives a UUID and records total latency. Generated responses
include mock input/output token counts and model latency; cache hits report zero
LLM tokens. The application keeps in-memory hit, miss, and generation-failure
counters for the current process.

Generation failures are failure-closed: the failed answer is not cached, a
controlled `502` response is returned, and a structured decision log records
the request ID, decision, and latency without logging the answer.

When `SSCRE_DATABASE_URL` is configured, the exact-cache lookup and insert use
PostgreSQL. A generated answer is committed to `cache_entries`, and a later API
process can retrieve it by the same query hash. Without that setting,
`create_app()` uses the in-memory repository for isolated unit tests.
