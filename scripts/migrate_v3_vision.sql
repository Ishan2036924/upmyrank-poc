-- Vision AI migration: add image_url column to doubt_sessions
-- Run this against the production DB (Supabase or local Postgres)

ALTER TABLE doubt_sessions
  ADD COLUMN IF NOT EXISTS image_url TEXT;

COMMENT ON COLUMN doubt_sessions.image_url IS
  'Supabase Storage public URL of the image uploaded by the student, if any.';
