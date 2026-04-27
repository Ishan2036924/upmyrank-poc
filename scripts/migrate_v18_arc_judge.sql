-- Migration v18 — conversation_arc_quality
-- Adds whole-flow conversation-quality scoring (vs the existing per-turn
-- scoring in `conversation_turn_quality` and per-response scoring in
-- `judge_evaluations`). Fires once per doubt_session at /session/end via
-- app/services/eval/conversation_arc_judge.py.
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS conversation_arc_quality (
    id                      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    doubt_session_id        UUID         REFERENCES doubt_sessions(id) ON DELETE CASCADE,
    flow_id                 TEXT,                  -- diagnostic flow tag (e.g. "A05") — NULL for organic prod traffic
    edge_class              TEXT,                  -- diagnostic class A-J — NULL for organic
    turn_count              INT,
    coherence               SMALLINT,              -- 0|1|2 — does the conversation feel coherent
    adaptation              SMALLINT,              -- 0|1|2 — does the AI change strategy when needed
    context_persistence     SMALLINT,              -- 0|1   — does the AI remember earlier turns
    closure                 SMALLINT,              -- 0|1|2 — does the conversation reach an end-state
    pedagogy_arc            SMALLINT,              -- 0|1|2 — did the student move toward understanding
    back_and_forth_overall  SMALLINT,              -- 0|1   — would this be useful to a real student
    composite_score         FLOAT,                 -- 0–1 weighted composite
    rationale               TEXT,
    scored_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_arc_quality_session
    ON conversation_arc_quality(doubt_session_id);

CREATE INDEX IF NOT EXISTS idx_arc_quality_class
    ON conversation_arc_quality(edge_class);

CREATE INDEX IF NOT EXISTS idx_arc_quality_scored_at
    ON conversation_arc_quality(scored_at DESC);

ALTER TABLE conversation_arc_quality ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service role all" ON conversation_arc_quality;

-- Backend connects as postgres superuser (bypasses RLS by design — same
-- pattern as judge_evaluations + session_metrics). Frontend never reads
-- this table; service role is the only writer.
CREATE POLICY "service role all"
    ON conversation_arc_quality
    FOR ALL
    USING (TRUE);

COMMIT;
