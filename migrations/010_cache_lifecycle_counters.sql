-- Historical lifecycle counters for cache observability.

CREATE TABLE IF NOT EXISTS cache_lifecycle_counters (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    deduplication_hits BIGINT NOT NULL DEFAULT 0,
    deduplication_savings_bytes BIGINT NOT NULL DEFAULT 0,
    expirations BIGINT NOT NULL DEFAULT 0,
    evictions BIGINT NOT NULL DEFAULT 0
);

INSERT INTO cache_lifecycle_counters (singleton)
VALUES (TRUE)
ON CONFLICT (singleton) DO NOTHING;
