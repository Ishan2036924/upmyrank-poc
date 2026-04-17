-- ─────────────────────────────────────────────────────────────────────────────
-- migrate_v15_feedback_constraint.sql
-- 1. Fix Bug: add missing UNIQUE constraint on response_feedback so ON CONFLICT works
-- 2. New table: conversation_turn_quality for continuous per-turn Socratic scoring
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Bug 2 fix: unique constraint for ON CONFLICT in feedback.py ───────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_feedback_per_turn'
  ) THEN
    ALTER TABLE response_feedback
      ADD CONSTRAINT uq_feedback_per_turn
      UNIQUE (student_id, doubt_session_id, response_idx);
  END IF;
END $$;

-- ── New table: per-turn conversation quality scores ───────────────────────────
CREATE TABLE IF NOT EXISTS conversation_turn_quality (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    doubt_session_id    UUID        REFERENCES doubt_sessions(id) ON DELETE CASCADE,
    turn_index          INT         NOT NULL,
    student_message     TEXT        NOT NULL,
    ai_response         TEXT        NOT NULL,
    -- Scoring dimensions (gpt-4o-mini at temp=0, fires async)
    validation_score    SMALLINT,   -- 0: ignored answer, 1: partial ack, 2: explicit validation
    appropriateness     SMALLINT,   -- 0: wrong strategy, 1: acceptable, 2: ideal
    restart_detected    BOOLEAN,    -- TRUE = AI restarted instead of building on answer
    single_question     BOOLEAN,    -- TRUE = AI asked exactly ONE question (not 2+)
    judge_rationale     TEXT,       -- brief LLM explanation for the scores
    scored_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ctq_session
  ON conversation_turn_quality(doubt_session_id);

CREATE INDEX IF NOT EXISTS idx_ctq_scored_at
  ON conversation_turn_quality(scored_at DESC);

ALTER TABLE conversation_turn_quality ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "admin read ctq" ON conversation_turn_quality;
CREATE POLICY "admin read ctq"
  ON conversation_turn_quality FOR SELECT
  USING (TRUE);
