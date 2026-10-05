-- Exact-cache persistence for Milestone 5.
-- This migration is safe to apply more than once.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS cache_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash VARCHAR(64) NOT NULL,
    normalized_query TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cache_entries_query_hash_length CHECK (length(query_hash) = 64),
    CONSTRAINT cache_entries_query_hash_unique UNIQUE (query_hash)
);
