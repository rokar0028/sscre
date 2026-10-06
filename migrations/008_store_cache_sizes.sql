-- Store per-entry byte accounting for storage statistics and eviction.
-- This migration is safe to apply more than once.

ALTER TABLE cache_entries
    ADD COLUMN IF NOT EXISTS storage_bytes BIGINT NOT NULL DEFAULT 0;

UPDATE cache_entries AS ce
SET storage_bytes =
    octet_length(ce.normalized_query)
    + octet_length(ce.metadata::text)
    + (COALESCE(ce.embedding_dimension, 0) * 4)
FROM canonical_answers AS ca
WHERE ca.answer_hash = ce.canonical_answer_hash;

UPDATE cache_entries
SET storage_bytes =
    octet_length(normalized_query)
    + octet_length(metadata::text)
    + (COALESCE(embedding_dimension, 0) * 4)
WHERE canonical_answer_hash IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cache_entries_storage_bytes_nonnegative'
    ) THEN
        ALTER TABLE cache_entries
            ADD CONSTRAINT cache_entries_storage_bytes_nonnegative
            CHECK (storage_bytes >= 0);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_cache_entries_expiration
    ON cache_entries (ttl_expires_at, query_hash);

CREATE INDEX IF NOT EXISTS idx_cache_entries_canonical_answer
    ON cache_entries (canonical_answer_hash);
