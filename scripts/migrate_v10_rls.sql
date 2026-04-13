-- migrate_v10_rls.sql
-- Enables Row Level Security on all public tables.
--
-- SAFETY NOTE: The FastAPI backend connects as the 'postgres' superuser role
-- (postgres.vgctqmhwezmihhmnwtzm via Supabase pooler). PostgreSQL superusers
-- bypass RLS by default — no backend query changes needed.
--
-- These policies protect against direct Supabase client / anon/authenticated
-- role access. auth.uid() matches students.id (set from Supabase auth UID at signup).

-- ── Enable RLS ────────────────────────────────────────────────────────────────
ALTER TABLE students          ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_sessions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE doubt_sessions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE doubt_blocks      ENABLE ROW LEVEL SECURITY;
ALTER TABLE concept_mastery   ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_events    ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_memory    ENABLE ROW LEVEL SECURITY;
ALTER TABLE concepts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunks  ENABLE ROW LEVEL SECURITY;
ALTER TABLE problems          ENABLE ROW LEVEL SECURITY;

-- ── Per-student row ownership policies ───────────────────────────────────────

-- students: own row only (id = Supabase auth UID)
CREATE POLICY "students_own_row" ON students
  FOR ALL USING (auth.uid() = id);

-- study_sessions: student_id is the FK (not user_id)
CREATE POLICY "own_study_sessions" ON study_sessions
  FOR ALL USING (auth.uid() = student_id);

-- doubt_sessions: student_id FK
CREATE POLICY "own_doubt_sessions" ON doubt_sessions
  FOR ALL USING (auth.uid() = student_id);

-- doubt_blocks: has direct student_id FK (confirmed from schema)
CREATE POLICY "own_doubt_blocks" ON doubt_blocks
  FOR ALL USING (auth.uid() = student_id);

-- concept_mastery: student_id FK
CREATE POLICY "own_concept_mastery" ON concept_mastery
  FOR ALL USING (auth.uid() = student_id);

-- session_events: student_id FK
CREATE POLICY "own_session_events" ON session_events
  FOR ALL USING (auth.uid() = student_id);

-- student_memory: student_id FK
CREATE POLICY "own_student_memory" ON student_memory
  FOR ALL USING (auth.uid() = student_id);

-- ── Shared read-only content (all authenticated users) ────────────────────────
CREATE POLICY "concepts_read_authenticated" ON concepts
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "chunks_read_authenticated" ON knowledge_chunks
  FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "problems_read_authenticated" ON problems
  FOR SELECT USING (auth.role() = 'authenticated');
