-- migrate_v16_student_email.sql
-- Add email column to students table so admin email-based auth check can work.
-- The email is sourced from Supabase auth (same UUID as students.id).

ALTER TABLE students ADD COLUMN IF NOT EXISTS email TEXT;

-- Index for fast lookup by email
CREATE INDEX IF NOT EXISTS idx_students_email ON students (email);

-- RLS: allow students to see their own email, admin can see all (read via service role)
-- No new policy needed — existing policies on students apply.
