-- Migration v12: Feedback tables, judge evaluations, session metrics, onboarding expansion
-- Run with: ./scripts/run_migration.sh scripts/migrate_v12_feedback.sql
-- Safe to re-run: IF NOT EXISTS on all DDL; DROP POLICY IF EXISTS before each CREATE POLICY.

-- ============================================================
-- Table 1: response_feedback (per-message thumbs up/down)
-- ============================================================
CREATE TABLE IF NOT EXISTS response_feedback (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id       UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    doubt_session_id UUID REFERENCES doubt_sessions(id) ON DELETE SET NULL,
    response_idx     INT  NOT NULL,   -- 0-based index of the AI message in conversation
    rating           TEXT NOT NULL CHECK (rating IN ('thumbs_up', 'thumbs_down')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (student_id, doubt_session_id, response_idx)
);
CREATE INDEX IF NOT EXISTS idx_response_feedback_student ON response_feedback(student_id);
CREATE INDEX IF NOT EXISTS idx_response_feedback_session ON response_feedback(doubt_session_id);
ALTER TABLE response_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "student read own feedback"   ON response_feedback;
DROP POLICY IF EXISTS "student insert own feedback" ON response_feedback;
DROP POLICY IF EXISTS "student update own feedback" ON response_feedback;
CREATE POLICY "student read own feedback"   ON response_feedback FOR SELECT USING (auth.uid() = student_id);
CREATE POLICY "student insert own feedback" ON response_feedback FOR INSERT WITH CHECK (auth.uid() = student_id);
CREATE POLICY "student update own feedback" ON response_feedback FOR UPDATE USING (auth.uid() = student_id);

-- ============================================================
-- Table 2: judge_evaluations (4-dimension async LLM judge)
-- ============================================================
CREATE TABLE IF NOT EXISTS judge_evaluations (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_session_id           UUID REFERENCES study_sessions(study_session_id) ON DELETE SET NULL,
    doubt_session_id           UUID REFERENCES doubt_sessions(id) ON DELETE SET NULL,
    question                   TEXT NOT NULL,
    ai_response                TEXT NOT NULL,
    pedagogical_score          SMALLINT,    -- 0|1|2  (Socratic quality)
    factual_score              SMALLINT,    -- 0|1    (factual accuracy)
    context_relevance_score    SMALLINT,    -- 0|1    (RAG context used well)
    hint_appropriateness_score SMALLINT,    -- 0|1    (right hint level for student state)
    overall_score              FLOAT,       -- weighted composite
    rationale_json             JSONB,       -- {"pedagogical":..., "factual":..., ...}
    evaluated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_judge_eval_study_session ON judge_evaluations(study_session_id);
CREATE INDEX IF NOT EXISTS idx_judge_eval_doubt_session ON judge_evaluations(doubt_session_id);
CREATE INDEX IF NOT EXISTS idx_judge_eval_evaluated_at  ON judge_evaluations(evaluated_at);
ALTER TABLE judge_evaluations ENABLE ROW LEVEL SECURITY;

-- Backend connects as postgres superuser (bypasses RLS). Frontend never reads this directly.
DROP POLICY IF EXISTS "allow all for service role" ON judge_evaluations;
CREATE POLICY "allow all for service role" ON judge_evaluations FOR ALL USING (TRUE);

-- ============================================================
-- Table 3: session_metrics (RAG timing + retrieval telemetry)
-- ============================================================
CREATE TABLE IF NOT EXISTS session_metrics (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    study_session_id     UUID REFERENCES study_sessions(study_session_id) ON DELETE SET NULL,
    doubt_session_id     UUID REFERENCES doubt_sessions(id) ON DELETE SET NULL,
    subject              TEXT,
    retrieval_latency_ms INT,
    agent_steps          SMALLINT,
    chunks_retrieved     SMALLINT,
    has_similar_problem  BOOLEAN DEFAULT FALSE,
    tool_trace           JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_session_metrics_study_session ON session_metrics(study_session_id);
CREATE INDEX IF NOT EXISTS idx_session_metrics_created_at    ON session_metrics(created_at);
ALTER TABLE session_metrics ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "allow all for service role" ON session_metrics;
CREATE POLICY "allow all for service role" ON session_metrics FOR ALL USING (TRUE);

-- ============================================================
-- Onboarding expansion: new columns on students table
-- ============================================================
ALTER TABLE students ADD COLUMN IF NOT EXISTS chemistry_prev_marks  SMALLINT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS maths_prev_marks      SMALLINT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS priority_subject      TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS learning_preference   TEXT;
