-- migrate_v5_persona.sql
-- Adds persona_profile JSONB column to student_memory table.
--
-- PREREQUISITE: migrate_v4_memory.sql must have been applied first.
--
-- DB: Supabase cloud (aws-0-us-west-2.pooler.supabase.com)
--
-- Option A — Supabase SQL Editor (recommended):
--   https://supabase.com/dashboard/project/vgctqmhwezmihhmnwtzm/sql
--   Paste the contents of this file and click Run.
--
-- Option B — psql with Supabase connection string:
--   psql "postgresql://postgres.vgctqmhwezmihhmnwtzm:<PASSWORD>@aws-0-us-west-2.pooler.supabase.com:5432/postgres?sslmode=require" \
--     -f scripts/migrate_v5_persona.sql

ALTER TABLE student_memory
ADD COLUMN IF NOT EXISTS persona_profile JSONB DEFAULT '{
  "scaffolding_level": "HIGH",
  "preferred_style": "analogy",
  "common_misconceptions": [],
  "allowed_hint_depth": 3,
  "interaction_depth_score": 0.0,
  "learning_velocity": 0.0
}'::jsonb;
