-- Student Memory System migration
-- Phase 1: error fingerprints, forgetting rates, session summaries, student_memory table
--
-- DB: Supabase cloud (aws-0-us-west-2.pooler.supabase.com)
--
-- Option A — Supabase SQL Editor (recommended):
--   https://supabase.com/dashboard/project/vgctqmhwezmihhmnwtzm/sql
--   Paste the contents of this file and click Run.
--
-- Option B — psql with Supabase connection string:
--   psql "postgresql://postgres.vgctqmhwezmihhmnwtzm:<PASSWORD>@aws-0-us-west-2.pooler.supabase.com:5432/postgres?sslmode=require" \
--     -f scripts/migrate_v4_memory.sql

-- ── concept_mastery additions ─────────────────────────────────────────────────

ALTER TABLE concept_mastery
  ADD COLUMN IF NOT EXISTS error_fingerprint  JSONB   NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS forgetting_rate    FLOAT   NOT NULL DEFAULT 0.3;

COMMENT ON COLUMN concept_mastery.error_fingerprint IS
  'Map of error_type → strength (0–1). Decays 0.7× on correct, grows +0.3 on wrong. Pruned below 0.1.';

COMMENT ON COLUMN concept_mastery.forgetting_rate IS
  'Per-concept Ebbinghaus decay rate. Decreases (×0.9) when concept is retained well, increases (×1.1) when forgotten fast. Capped 0.1–0.9.';

-- ── study_sessions additions ──────────────────────────────────────────────────

ALTER TABLE study_sessions
  ADD COLUMN IF NOT EXISTS session_summary  TEXT,
  ADD COLUMN IF NOT EXISTS topics_covered   TEXT[]   DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS weak_signals     JSONB    NOT NULL DEFAULT '{}';

COMMENT ON COLUMN study_sessions.session_summary IS
  'GPT-4o-mini compressed summary of all doubt_block summaries in this session. Max ~80 words. Written by summarizer.py on session end.';

COMMENT ON COLUMN study_sessions.topics_covered IS
  'Array of topic strings covered in this session, extracted from doubt_blocks.';

COMMENT ON COLUMN study_sessions.weak_signals IS
  'Snapshot of weak concept signals at session end. Written by summarizer.py.';

-- ── student_memory table ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS student_memory (
  student_id              UUID        PRIMARY KEY REFERENCES students(id) ON DELETE CASCADE,
  compressed_profile      TEXT,
  forgetting_rates        JSONB       NOT NULL DEFAULT '{}',
  sessions_since_compress INT         NOT NULL DEFAULT 0,
  profile_last_updated    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE student_memory IS
  'One row per student. compressed_profile is a rolling GPT-4o-mini paragraph rewritten every 5 sessions. forgetting_rates mirrors per-concept decay rates for fast lookup.';

COMMENT ON COLUMN student_memory.compressed_profile IS
  'Rolling 120-word paragraph summarising the student profile. Rewritten by maybe_compress_profile() every 5 sessions.';

COMMENT ON COLUMN student_memory.forgetting_rates IS
  'concept_id → forgetting_rate float. Mirrors concept_mastery.forgetting_rate for batch reads without joining.';

COMMENT ON COLUMN student_memory.sessions_since_compress IS
  'Counter reset to 0 each time compressed_profile is rewritten. Triggers recompression at 5.';

-- Seed a student_memory row for every existing student (safe to run multiple times)
INSERT INTO student_memory (student_id)
SELECT id FROM students
ON CONFLICT (student_id) DO NOTHING;

-- ── Phase 1: student_confidence on doubt_blocks ───────────────────────────────

ALTER TABLE doubt_blocks
  ADD COLUMN IF NOT EXISTS student_confidence VARCHAR(10);

COMMENT ON COLUMN doubt_blocks.student_confidence IS
  'Confidence level captured at forced-attempt stage: low / medium / high';
