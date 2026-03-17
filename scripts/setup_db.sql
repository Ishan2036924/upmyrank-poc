-- ============================================================
-- UpMyRank POC — Database Schema
-- POC scope: NCERT Class 12 Math, Chapter 1 (Relations & Functions)
-- ============================================================

-- ------------------------------------------------------------
-- 0. Extensions
-- ------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;


-- ------------------------------------------------------------
-- 1. Tables
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS students (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    exam_type   TEXT NOT NULL DEFAULT 'JEE' CHECK (exam_type IN ('JEE', 'NEET')),
    target_year INTEGER DEFAULT 2026,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concepts (
    id               TEXT PRIMARY KEY,
    subject          TEXT NOT NULL,
    topic            TEXT NOT NULL,
    subtopic         TEXT NOT NULL,
    description      TEXT,
    prerequisite_ids TEXT[] DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS concept_mastery (
    student_id      UUID REFERENCES students(id) ON DELETE CASCADE,
    concept_id      TEXT REFERENCES concepts(id) ON DELETE CASCADE,
    mastery_score   FLOAT DEFAULT 0.5 CHECK (mastery_score BETWEEN 0 AND 1),
    error_count     INTEGER DEFAULT 0,
    attempt_count   INTEGER DEFAULT 0,
    last_reviewed   TIMESTAMPTZ,
    next_review_due TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (student_id, concept_id)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_file TEXT NOT NULL,
    subject     TEXT DEFAULT 'Mathematics',
    chapter     TEXT,
    chunk_index INTEGER,
    content     TEXT NOT NULL,
    embedding   vector(384),
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS problems (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject         TEXT DEFAULT 'Mathematics',
    topic           TEXT NOT NULL,
    subtopic        TEXT,
    difficulty      FLOAT CHECK (difficulty BETWEEN 0 AND 1),
    question_text   TEXT NOT NULL,
    question_latex  TEXT,
    verified_answer TEXT,
    solution_steps  JSONB,
    concepts_tested TEXT[],
    source          TEXT,
    embedding       vector(384),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS doubt_sessions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id           UUID REFERENCES students(id) ON DELETE CASCADE,
    problem_text         TEXT NOT NULL,
    subject              TEXT DEFAULT 'Mathematics',
    topic                TEXT,
    difficulty           FLOAT,
    current_hint_level   INTEGER DEFAULT 0,
    resolved             BOOLEAN DEFAULT FALSE,
    conversation_history JSONB DEFAULT '[]',
    concepts_involved    TEXT[],
    analysis             JSONB,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    resolved_at          TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS session_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID REFERENCES doubt_sessions(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);


-- ------------------------------------------------------------
-- 2. Indexes
-- ------------------------------------------------------------

-- Vector similarity indexes (HNSW — no training data needed, scales well)
-- HNSW outperforms ivfflat for small-medium datasets (<1M rows).
-- ivfflat requires lists ≥ sqrt(rows) trained data; HNSW has no such constraint.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding_hnsw
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_problems_embedding_hnsw
    ON problems USING hnsw (embedding vector_cosine_ops);

-- Relational indexes
CREATE INDEX IF NOT EXISTS idx_concept_mastery_student
    ON concept_mastery (student_id);

CREATE INDEX IF NOT EXISTS idx_doubt_sessions_student
    ON doubt_sessions (student_id);


-- ------------------------------------------------------------
-- 3. Similarity search function
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(384),
    match_count     INT     DEFAULT 5,
    filter_subject  TEXT    DEFAULT NULL
)
RETURNS TABLE (
    id         UUID,
    content    TEXT,
    subject    TEXT,
    chapter    TEXT,
    metadata   JSONB,
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        kc.id,
        kc.content,
        kc.subject,
        kc.chapter,
        kc.metadata,
        1 - (kc.embedding <=> query_embedding) AS similarity
    FROM knowledge_chunks kc
    WHERE
        filter_subject IS NULL
        OR kc.subject = filter_subject
    ORDER BY kc.embedding <=> query_embedding
    LIMIT match_count;
$$;


-- ------------------------------------------------------------
-- 4. Seed: Concepts (Relations & Functions — 12 concepts)
-- ------------------------------------------------------------

-- Clear existing data before re-seeding (mastery first due to FK)
DELETE FROM concept_mastery;
DELETE FROM concepts;

INSERT INTO concepts (id, subject, topic, subtopic, description, prerequisite_ids)
VALUES
    (
        'relations.cartesian_product',
        'Mathematics', 'Relations', 'Cartesian Product of Sets',
        'The Cartesian product A × B is the set of all ordered pairs (a, b) where a ∈ A and b ∈ B.',
        '{}'
    ),
    (
        'relations.definition',
        'Mathematics', 'Relations', 'Definition and Examples of Relations',
        'A relation R from set A to set B is a subset of the Cartesian product A × B.',
        '{"relations.cartesian_product"}'
    ),
    (
        'relations.types_reflexive',
        'Mathematics', 'Relations', 'Reflexive Relations',
        'A relation R on set A is reflexive if (a, a) ∈ R for every a ∈ A.',
        '{"relations.definition"}'
    ),
    (
        'relations.types_symmetric',
        'Mathematics', 'Relations', 'Symmetric Relations',
        'A relation R on set A is symmetric if (a, b) ∈ R implies (b, a) ∈ R.',
        '{"relations.definition"}'
    ),
    (
        'relations.types_transitive',
        'Mathematics', 'Relations', 'Transitive Relations',
        'A relation R on set A is transitive if (a, b) ∈ R and (b, c) ∈ R implies (a, c) ∈ R.',
        '{"relations.definition"}'
    ),
    (
        'relations.equivalence',
        'Mathematics', 'Relations', 'Equivalence Relations',
        'A relation that is reflexive, symmetric and transitive. Partitions the set into equivalence classes.',
        '{"relations.types_reflexive", "relations.types_symmetric", "relations.types_transitive"}'
    ),
    (
        'functions.definition',
        'Mathematics', 'Functions', 'Definition and Types of Functions',
        'A function f: A → B assigns to each element of A exactly one element of B. Domain, codomain and range.',
        '{"relations.definition"}'
    ),
    (
        'functions.one_to_one',
        'Mathematics', 'Functions', 'One-to-One (Injective) Functions',
        'f is injective if f(a₁) = f(a₂) implies a₁ = a₂. No two distinct inputs map to the same output.',
        '{"functions.definition"}'
    ),
    (
        'functions.onto',
        'Mathematics', 'Functions', 'Onto (Surjective) Functions',
        'f: A → B is surjective if for every b ∈ B there exists a ∈ A such that f(a) = b. Range equals codomain.',
        '{"functions.definition"}'
    ),
    (
        'functions.bijective',
        'Mathematics', 'Functions', 'Bijective Functions',
        'A function that is both injective (one-to-one) and surjective (onto). Establishes a one-to-one correspondence.',
        '{"functions.one_to_one", "functions.onto"}'
    ),
    (
        'functions.composition',
        'Mathematics', 'Functions', 'Composition of Functions',
        'Given f: A → B and g: B → C, the composition (g∘f)(x) = g(f(x)) defines a function from A to C.',
        '{"functions.definition"}'
    ),
    (
        'functions.inverse',
        'Mathematics', 'Functions', 'Inverse of a Function',
        'A function f has an inverse f⁻¹ if and only if f is bijective. f⁻¹ reverses the mapping of f.',
        '{"functions.bijective"}'
    )
ON CONFLICT (id) DO NOTHING;


-- ------------------------------------------------------------
-- 5. Seed: Test student + concept mastery
-- ------------------------------------------------------------

-- Insert test student (idempotent via DO block)
DO $$
DECLARE
    v_student_id UUID;
BEGIN
    -- Insert only if no test student exists
    INSERT INTO students (name, exam_type, target_year)
    VALUES ('Test Student', 'JEE', 2026)
    ON CONFLICT DO NOTHING
    RETURNING id INTO v_student_id;

    -- If student already existed, look them up
    IF v_student_id IS NULL THEN
        SELECT id INTO v_student_id FROM students WHERE name = 'Test Student' LIMIT 1;
    END IF;

    -- Seed concept_mastery with randomized scores (0.3 – 0.8)
    INSERT INTO concept_mastery (student_id, concept_id, mastery_score, updated_at)
    SELECT
        v_student_id,
        c.id,
        0.3 + random() * 0.5,
        NOW()
    FROM concepts c
    ON CONFLICT (student_id, concept_id) DO NOTHING;
END;
$$;


-- ------------------------------------------------------------
-- 6. Verification queries
-- ------------------------------------------------------------

SELECT 'concepts'       AS table_name, COUNT(*) AS row_count FROM concepts
UNION ALL
SELECT 'students',        COUNT(*) FROM students
UNION ALL
SELECT 'concept_mastery', COUNT(*) FROM concept_mastery;
