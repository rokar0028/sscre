CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    checksum CHAR(64),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
