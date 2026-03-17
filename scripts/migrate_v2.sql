-- ============================================================
-- UpMyRank V2 Migration: Study Sessions + Doubt Blocks
-- Run via: docker cp ... psql -f /tmp/migrate_v2.sql
-- ============================================================

-- 1. study_sessions — one per browser sitting (≤ 2 hours)
CREATE TABLE IF NOT EXISTS study_sessions (
    study_session_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id        UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at          TIMESTAMPTZ,
    doubt_count       INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_study_sessions_student
    ON study_sessions (student_id);

CREATE INDEX IF NOT EXISTS idx_study_sessions_started
    ON study_sessions (started_at DESC);

-- 2. doubt_blocks — one per physics question within a study session
--    Links 1:1 to doubt_sessions via doubt_session_id FK.
CREATE TABLE IF NOT EXISTS doubt_blocks (
    doubt_block_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_session_id  UUID NOT NULL REFERENCES study_sessions(study_session_id) ON DELETE CASCADE,
    student_id        UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    doubt_session_id  UUID REFERENCES doubt_sessions(id) ON DELETE SET NULL,
    topic             VARCHAR(200),
    hint_level        INTEGER DEFAULT 0,
    solved            BOOLEAN DEFAULT FALSE,
    summary           TEXT,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_doubt_blocks_session
    ON doubt_blocks (study_session_id);

CREATE INDEX IF NOT EXISTS idx_doubt_blocks_student
    ON doubt_blocks (student_id);

-- 3. Add doubt_block_id to session_events (nullable, backwards-compatible)
ALTER TABLE session_events
    ADD COLUMN IF NOT EXISTS doubt_block_id UUID
    REFERENCES doubt_blocks(doubt_block_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_session_events_doubt_block
    ON session_events (doubt_block_id);
