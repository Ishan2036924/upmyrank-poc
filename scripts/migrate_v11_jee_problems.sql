-- ============================================================
-- Migration v11 — JEE Problems Table (30-Year PYQ Database)
-- ============================================================
-- Creates jee_problems table with:
--   • vector(1536) embedding — matches OpenAI text-embedding-3-small used everywhere
--   • HNSW index (cosine ops) — consistent with knowledge_chunks + problems
--   • match_jee_problems() Postgres function — mirrors match_chunks() interface
--   • RLS: read-only for authenticated users, full access for service role
-- ============================================================

-- ------------------------------------------------------------
-- 1. Table
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS jee_problems (
    problem_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    subject         TEXT        NOT NULL CHECK (subject IN ('Physics', 'Chemistry', 'Maths')),
    topic           TEXT        NOT NULL DEFAULT '',
    year            INTEGER,
    exam_type       TEXT        NOT NULL DEFAULT 'JEE Mains'
                                CHECK (exam_type IN ('JEE Mains', 'JEE Advanced')),
    difficulty      INTEGER     CHECK (difficulty BETWEEN 1 AND 5),
    problem_text    TEXT        NOT NULL,
    solution_text   TEXT,
    solution_steps  JSONB       DEFAULT '[]',
    embedding       vector(1536),
    source_verified BOOLEAN     DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ------------------------------------------------------------
-- 2. HNSW vector index (cosine similarity — matches all other tables)
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_jee_problems_embedding_hnsw
    ON jee_problems USING hnsw (embedding vector_cosine_ops);

-- ------------------------------------------------------------
-- 3. Relational indexes for common filter patterns
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_jee_problems_subject
    ON jee_problems (subject);

CREATE INDEX IF NOT EXISTS idx_jee_problems_year
    ON jee_problems (year);

CREATE INDEX IF NOT EXISTS idx_jee_problems_exam_type
    ON jee_problems (exam_type);

CREATE INDEX IF NOT EXISTS idx_jee_problems_subject_year
    ON jee_problems (subject, year);

-- ------------------------------------------------------------
-- 4. Similarity search function
--    Mirrors match_chunks() — used by search_jee_problems tool.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION match_jee_problems(
    query_embedding  vector(1536),
    match_count      INT     DEFAULT 5,
    filter_subject   TEXT    DEFAULT NULL,
    filter_exam_type TEXT    DEFAULT NULL,
    min_year         INT     DEFAULT NULL,
    max_year         INT     DEFAULT NULL
)
RETURNS TABLE (
    problem_id      UUID,
    subject         TEXT,
    topic           TEXT,
    year            INTEGER,
    exam_type       TEXT,
    difficulty      INTEGER,
    problem_text    TEXT,
    solution_text   TEXT,
    solution_steps  JSONB,
    source_verified BOOLEAN,
    similarity      FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        jp.problem_id,
        jp.subject,
        jp.topic,
        jp.year,
        jp.exam_type,
        jp.difficulty,
        jp.problem_text,
        jp.solution_text,
        jp.solution_steps,
        jp.source_verified,
        1 - (jp.embedding <=> query_embedding) AS similarity
    FROM jee_problems jp
    WHERE
        (filter_subject   IS NULL OR jp.subject   = filter_subject)
        AND (filter_exam_type IS NULL OR jp.exam_type = filter_exam_type)
        AND (min_year         IS NULL OR jp.year      >= min_year)
        AND (max_year         IS NULL OR jp.year      <= max_year)
        AND jp.embedding IS NOT NULL
    ORDER BY jp.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- ------------------------------------------------------------
-- 5. Row-Level Security
--    Authenticated users: read-only (SELECT only).
--    Service role (backend FastAPI / superuser): bypasses RLS by design.
-- ------------------------------------------------------------

ALTER TABLE jee_problems ENABLE ROW LEVEL SECURITY;

-- Read-only policy for authenticated Supabase users (frontend)
CREATE POLICY "jee_problems_authenticated_select"
    ON jee_problems
    FOR SELECT
    TO authenticated
    USING (true);

-- ------------------------------------------------------------
-- 6. Verification query
-- ------------------------------------------------------------

SELECT
    'jee_problems'  AS table_name,
    COUNT(*)        AS row_count
FROM jee_problems;
