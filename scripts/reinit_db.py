"""
scripts/reinit_db.py
────────────────────
Migrates embedding columns from vector(384) → vector(1536) in Supabase.

Run this ONCE after deploying the OpenAI embedding migration.
All existing embeddings are 384-dim and must be re-ingested anyway,
so this script drops and recreates the embedding columns + indexes + function.

Usage:
    python scripts/reinit_db.py

Requires DATABASE_URL in .env (or set as environment variable).
"""

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set. Check your .env file.")
    sys.exit(1)


SQL = """
-- ── 1. Drop old HNSW indexes ──────────────────────────────────────────────
DROP INDEX IF EXISTS idx_knowledge_chunks_embedding_hnsw;
DROP INDEX IF EXISTS idx_problems_embedding_hnsw;

-- ── 2. Drop old embedding columns ────────────────────────────────────────
ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding;
ALTER TABLE problems          DROP COLUMN IF EXISTS embedding;

-- ── 3. Recreate as vector(1536) ───────────────────────────────────────────
ALTER TABLE knowledge_chunks ADD COLUMN embedding vector(1536);
ALTER TABLE problems          ADD COLUMN embedding vector(1536);

-- ── 4. Recreate HNSW indexes ─────────────────────────────────────────────
CREATE INDEX idx_knowledge_chunks_embedding_hnsw
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_problems_embedding_hnsw
    ON problems USING hnsw (embedding vector_cosine_ops);

-- ── 5. Recreate match_chunks() with new dimension ─────────────────────────
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1536),
    match_count     INT  DEFAULT 5,
    filter_subject  TEXT DEFAULT NULL
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
"""


async def main():
    print(f"Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        print("Running migration: vector(384) → vector(1536) ...")
        await conn.execute(SQL)
        print("✓ Embedding columns recreated as vector(1536)")
        print("✓ HNSW indexes recreated")
        print("✓ match_chunks() function updated")
        print()
        print("Next step: re-run your ingestion script to re-embed all chunks")
        print("and problems using OpenAI text-embedding-3-small.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
