-- Store bounded query metadata for compatibility-aware Strategy C reuse.
-- This migration is safe to apply more than once.

ALTER TABLE cache_entries
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
