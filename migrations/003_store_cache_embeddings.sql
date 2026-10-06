-- Store embeddings and their provenance for Milestone 7.
-- The dimension is recorded separately so providers with different dimensions
-- can be validated before a future vector-search migration adds an index.

ALTER TABLE cache_entries
    ADD COLUMN IF NOT EXISTS embedding vector,
    ADD COLUMN IF NOT EXISTS embedding_model TEXT,
    ADD COLUMN IF NOT EXISTS embedding_dimension INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cache_entries_embedding_metadata'
    ) THEN
        ALTER TABLE cache_entries
            ADD CONSTRAINT cache_entries_embedding_metadata CHECK (
                (
                    embedding IS NULL
                    AND embedding_model IS NULL
                    AND embedding_dimension IS NULL
                )
                OR (
                    embedding IS NOT NULL
                    AND embedding_model IS NOT NULL
                    AND embedding_dimension IS NOT NULL
                    AND embedding_dimension > 0
                )
            );
    END IF;
END
$$;
