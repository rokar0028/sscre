-- Enable vector operations before any migration creates vector columns.
-- This migration is safe to apply more than once.

CREATE EXTENSION IF NOT EXISTS vector;
