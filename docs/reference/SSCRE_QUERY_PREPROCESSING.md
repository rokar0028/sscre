# Query preprocessing

SSCRE normalizes incoming queries before creating exact-cache keys:

1. Trim leading and trailing whitespace.
2. Replace every run of whitespace with one ordinary space.
3. Reject empty or whitespace-only queries.
4. Reject raw request values longer than 8,000 characters before normalization.
5. Hash the normalized UTF-8 text with SHA-256.

This makes formatting-only differences share one exact-cache key while keeping
the transformation deterministic and inexpensive. The limit applies before
normalization so oversized request payloads are rejected consistently, even
when they contain repeated whitespace that would later collapse.

Normalization is intentionally conservative. It does not lowercase text,
remove punctuation, reorder words, or alter Unicode characters. Those changes
can affect programming languages, identifiers, quoted text, and user intent.
Semantic equivalence belongs to the later embedding and safety stages.
