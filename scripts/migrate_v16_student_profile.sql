-- v0.20.2 — student profile expansion for /settings save
--
-- Adds the editable fields the v0.19 settings UI scaffolded but couldn't save:
--   phone              — E.164 string, optional
--   avatar_url         — base64 data URL or external HTTPS URL
--   timezone           — IANA tz string, default 'Asia/Kolkata'
--   preferred_language — ISO 639-1 code, default 'en'
--
-- Idempotent — uses ADD COLUMN IF NOT EXISTS so re-running is safe.
-- Run via: ./scripts/run_migration.sh scripts/migrate_v16_student_profile.sql

BEGIN;

ALTER TABLE students
    ADD COLUMN IF NOT EXISTS phone              TEXT,
    ADD COLUMN IF NOT EXISTS avatar_url         TEXT,
    ADD COLUMN IF NOT EXISTS timezone           TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    ADD COLUMN IF NOT EXISTS preferred_language TEXT NOT NULL DEFAULT 'en';

-- Light constraint: phone must look numeric / E.164 if present.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'students_phone_format'
    ) THEN
        ALTER TABLE students
            ADD CONSTRAINT students_phone_format
            CHECK (phone IS NULL OR phone ~ '^[+0-9 ()-]{6,20}$');
    END IF;
END $$;

COMMIT;
