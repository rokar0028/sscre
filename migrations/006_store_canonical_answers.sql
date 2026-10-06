-- Define content-addressable canonical answer storage.
-- Deduplication and reference population are implemented in a later step.

CREATE TABLE IF NOT EXISTS canonical_answers (
    answer_hash CHAR(64) PRIMARY KEY,
    answer TEXT NOT NULL,
    model_source TEXT,
    preference_label TEXT,
    correctness_label TEXT,
    validation_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT canonical_answers_hash_length
        CHECK (length(answer_hash) = 64),
    CONSTRAINT canonical_answers_preference_label
        CHECK (preference_label IS NULL OR preference_label IN ('A', 'B', 'tie')),
    CONSTRAINT canonical_answers_correctness_label
        CHECK (
            correctness_label IS NULL
            OR correctness_label IN ('correct', 'incorrect', 'uncertain')
        ),
    CONSTRAINT canonical_answers_validation_status
        CHECK (validation_status IS NULL OR validation_status IN ('auto', 'human'))
);

ALTER TABLE cache_entries
    ALTER COLUMN answer DROP NOT NULL;

ALTER TABLE cache_entries
    ADD COLUMN IF NOT EXISTS canonical_answer_hash CHAR(64)
    REFERENCES canonical_answers(answer_hash);
