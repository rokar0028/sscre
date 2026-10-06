-- Store cache expiration for freshness-aware reuse.
-- This migration is safe to apply more than once.

ALTER TABLE cache_entries
    ADD COLUMN IF NOT EXISTS ttl_expires_at TIMESTAMPTZ;
