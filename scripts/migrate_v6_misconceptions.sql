-- migrate_v6_misconceptions.sql
-- Adds misconception tracking columns to doubt_blocks and session_events.
--
-- DB: Supabase cloud (aws-0-us-west-2.pooler.supabase.com)
-- Run: ./scripts/run_migration.sh scripts/migrate_v6_misconceptions.sql

ALTER TABLE doubt_blocks
  ADD COLUMN IF NOT EXISTS misconception_detected BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS misconception_id       VARCHAR(100);

COMMENT ON COLUMN doubt_blocks.misconception_detected IS
  'True when the misconception detection library matched the student''s response during this block.';

COMMENT ON COLUMN doubt_blocks.misconception_id IS
  'ID of the matched Misconception entry (e.g. "centripetal_outward"). NULL if no misconception detected.';

ALTER TABLE session_events
  ADD COLUMN IF NOT EXISTS misconception_detected BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN session_events.misconception_detected IS
  'True when a misconception was detected at any point during this session.';
