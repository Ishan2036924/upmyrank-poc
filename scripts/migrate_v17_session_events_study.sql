-- v0.20.4 — allow session_type='study' for the v0.20.2 study_card_view event.
--
-- Prod log on 2026-04-21 surfaced the failure mode:
--   "new row for relation \"session_events\" violates check constraint
--    \"session_events_session_type_check\""
-- The original constraint allowed only ('doubt','practice','mock'). The
-- /admin/study-path endpoint shipped in v0.20.2 reads `study_card_view`
-- events with session_type='study' — which the constraint rejected, so
-- the entire admin Study Path usage panel showed zero data.
--
-- Idempotent: drops then re-adds the constraint with the widened set.
-- Run via: ./scripts/run_migration.sh scripts/migrate_v17_session_events_study.sql

BEGIN;

ALTER TABLE session_events
  DROP CONSTRAINT IF EXISTS session_events_session_type_check;

ALTER TABLE session_events
  ADD  CONSTRAINT session_events_session_type_check
       CHECK (session_type IN ('doubt', 'practice', 'mock', 'study'));

COMMIT;
