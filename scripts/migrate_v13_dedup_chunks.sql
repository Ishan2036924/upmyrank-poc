-- Migration v13: Deduplicate knowledge_chunks + prevent future duplicates
-- Run with: ./scripts/run_migration.sh scripts/migrate_v13_dedup_chunks.sql
-- Safe to re-run: DELETE only fires when duplicates exist; index creation is IF NOT EXISTS.

-- ── Step 1: Remove duplicate rows ────────────────────────────────────────────
-- Keep exactly ONE row per distinct content value — the one with the lowest UUID.
-- Duplicates arise when resumable ingest scripts re-run without dedup guards.
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY md5(content)
            ORDER BY id   -- lowest UUID wins (effectively insertion order for UUID v4)
        ) AS rn
    FROM knowledge_chunks
)
DELETE FROM knowledge_chunks
WHERE id IN (
    SELECT id FROM ranked WHERE rn > 1
);

-- ── Step 2: Prevent future duplicates ────────────────────────────────────────
-- Hash the content column so the index stays narrow (32 bytes per row vs full text).
-- md5() is deterministic and collision-resistant enough for dedup purposes.
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_chunks_content_md5
    ON knowledge_chunks (md5(content));
