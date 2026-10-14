-- Scoped cache identity constraints (Workstream 2 Step 2.4).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cache_entries_tenant_id_length'
    ) THEN
        ALTER TABLE cache_entries
            ADD CONSTRAINT cache_entries_tenant_id_length
            CHECK (
                char_length(tenant_id) >= 1
                AND char_length(tenant_id) <= 128
                AND tenant_id !~ '[\n\r]'
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cache_entries_namespace_id_length'
    ) THEN
        ALTER TABLE cache_entries
            ADD CONSTRAINT cache_entries_namespace_id_length
            CHECK (
                char_length(namespace_id) >= 1
                AND char_length(namespace_id) <= 128
                AND namespace_id !~ '[\n\r]'
            );
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_entries_scoped_content_unique
    ON cache_entries (tenant_id, namespace_id, content_query_hash);

CREATE INDEX IF NOT EXISTS idx_cache_entries_semantic_scope
    ON cache_entries (tenant_id, namespace_id, embedding_dimension)
    WHERE embedding IS NOT NULL;
