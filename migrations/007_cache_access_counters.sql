-- Store bounded-cache access counters for deterministic LRU eviction.
-- This migration is safe to apply more than once.

ALTER TABLE cache_entries
    ADD COLUMN IF NOT EXISTS hit_count BIGINT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_cache_entries_lru
    ON cache_entries (last_accessed_at, query_hash);
