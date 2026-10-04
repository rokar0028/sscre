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
