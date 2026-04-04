-- migrate_v7_eval.sql
-- Adds evaluation and observability columns to session_events.
--
-- DB: Supabase cloud (aws-0-us-west-2.pooler.supabase.com)
-- Run: ./scripts/run_migration.sh scripts/migrate_v7_eval.sql

ALTER TABLE session_events
  ADD COLUMN IF NOT EXISTS scaffolding_score    INTEGER,      -- 0/1/2 from Judge LLM rubric
  ADD COLUMN IF NOT EXISTS retrieval_similarity FLOAT,        -- max cosine similarity from RAG
  ADD COLUMN IF NOT EXISTS response_latency_ms  INTEGER,      -- LLM call wall-clock time
  ADD COLUMN IF NOT EXISTS hint_was_useful      BOOLEAN;      -- future: student feedback signal

COMMENT ON COLUMN session_events.scaffolding_score IS
  '0 = gave full solution, 1 = vague hint, 2 = leading Socratic question. Scored by Judge LLM (gpt-4.1-mini, temp=0).';

COMMENT ON COLUMN session_events.retrieval_similarity IS
  'Max cosine similarity score from the top RAG chunk retrieved for this event. NULL at hint_level 3.';

COMMENT ON COLUMN session_events.response_latency_ms IS
  'Wall-clock milliseconds from start of LLM call to sanitized response ready.';

COMMENT ON COLUMN session_events.hint_was_useful IS
  'Reserved for future student feedback signal. NULL until student rates the hint.';
