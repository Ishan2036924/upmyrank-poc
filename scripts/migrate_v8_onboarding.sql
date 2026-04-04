-- migrate_v8_onboarding.sql
-- Adds onboarding columns to students table.
-- Safe to re-run (uses IF NOT EXISTS / ALTER ... ADD COLUMN ... IF NOT EXISTS).

ALTER TABLE students
    ADD COLUMN IF NOT EXISTS onboarding_completed  BOOLEAN  DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS class_level           VARCHAR(20),
    ADD COLUMN IF NOT EXISTS physics_prev_marks    INTEGER,
    ADD COLUMN IF NOT EXISTS study_hours_per_day   FLOAT,
    ADD COLUMN IF NOT EXISTS exam_date             DATE;
