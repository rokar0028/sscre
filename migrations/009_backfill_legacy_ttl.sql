-- Backfill legacy rows created before TTL support as stable entries.
-- New rows receive an explicit TTL in the application.

UPDATE cache_entries
SET ttl_expires_at = created_at + INTERVAL '30 days'
WHERE ttl_expires_at IS NULL;
