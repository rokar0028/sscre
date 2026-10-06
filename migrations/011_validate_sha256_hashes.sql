-- Require canonical lowercase hexadecimal SHA-256 identities.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cache_entries_query_hash_sha256'
    ) THEN
        ALTER TABLE cache_entries
            ADD CONSTRAINT cache_entries_query_hash_sha256
            CHECK (query_hash ~ '^[0-9a-f]{64}$');
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'canonical_answers_hash_sha256'
    ) THEN
        ALTER TABLE canonical_answers
            ADD CONSTRAINT canonical_answers_hash_sha256
            CHECK (answer_hash ~ '^[0-9a-f]{64}$');
    END IF;
END
$$;
