-- migrate_v9_persona_staleness.sql
-- Adds persona_profile_updated_at to student_memory so the context builder
-- can report how fresh the persona is and flag stale profiles.

ALTER TABLE student_memory
ADD COLUMN IF NOT EXISTS persona_profile_updated_at TIMESTAMPTZ;

COMMENT ON COLUMN student_memory.persona_profile_updated_at IS
  'Timestamp of the last persona_profile rewrite (either onboarding or maybe_compress_profile). NULL = onboarding not yet done.';
