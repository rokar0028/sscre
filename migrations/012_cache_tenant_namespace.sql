-- Tenant and namespace scope for cache isolation (Workstream 2 Step 2.3).

ALTER TABLE cache_entries
    ADD COLUMN IF NOT EXISTS tenant_id TEXT,
    ADD COLUMN IF NOT EXISTS namespace_id TEXT,
    ADD COLUMN IF NOT EXISTS content_query_hash CHAR(64);

UPDATE cache_entries
SET
    tenant_id = 'legacy-unscoped',
    namespace_id = 'legacy-unscoped',
    content_query_hash = query_hash
WHERE tenant_id IS NULL;

ALTER TABLE cache_entries
    ALTER COLUMN tenant_id SET NOT NULL,
    ALTER COLUMN namespace_id SET NOT NULL,
    ALTER COLUMN content_query_hash SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'cache_entries_content_query_hash_sha256'
    ) THEN
        ALTER TABLE cache_entries
            ADD CONSTRAINT cache_entries_content_query_hash_sha256
            CHECK (content_query_hash ~ '^[0-9a-f]{64}$');
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_cache_entries_tenant_namespace
    ON cache_entries (tenant_id, namespace_id);
