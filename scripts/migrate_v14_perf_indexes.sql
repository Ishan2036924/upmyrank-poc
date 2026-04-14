-- migrate_v14_perf_indexes.sql
-- Performance indexes to reduce retrieval latency from ~12s to <2s P95.
--
-- Root-cause analysis of 12,677ms retrieval latency:
--   1. _keyword_search() does ILIKE '%kw%' on knowledge_chunks.content
--      (14,384 rows × 1536-dim content) — full table scan, no index usable.
--   2. Subject filter on knowledge_chunks had no btree index — also scanned.
--   3. jee_problems vector search had no subject+embedding composite support.
--
-- Fixes:
--   1. pg_trgm GIN index on knowledge_chunks.content → ILIKE uses index scan
--   2. btree index on knowledge_chunks.subject → subject filter is O(log n)
--   3. btree index on knowledge_chunks.chunk_index → ORDER BY chunk_index is O(log n)
--   4. btree index on jee_problems.subject → subject filter
--   5. pg_trgm extension safety check (already in Supabase, idempotent)
--
-- Apply with:
--   ./scripts/run_migration.sh scripts/migrate_v14_perf_indexes.sql
--
-- Expected improvement:
--   Before: ILIKE on content = Seq Scan (14,384 rows) ~40-200ms per keyword call
--   After:  GIN trigram scan — typically <5ms per ILIKE on same table size

-- ── 1. Enable pg_trgm (idempotent — already present on Supabase) ─────────────
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── 2. GIN trigram index on knowledge_chunks.content ─────────────────────────
-- Enables ILIKE '%keyword%' to use index instead of sequential scan.
-- Build is slow (one-time, ~30s for 14k rows), but queries drop to <5ms.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_content_trgm
    ON knowledge_chunks USING gin (content gin_trgm_ops);

-- ── 3. btree on knowledge_chunks.subject ─────────────────────────────────────
-- Used by both vector search (WHERE subject = $3) and keyword search.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_subject
    ON knowledge_chunks (subject);

-- ── 4. btree on knowledge_chunks.chunk_index ─────────────────────────────────
-- Keyword search ORDER BY chunk_index — avoids sort on full result set.
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_chunk_index
    ON knowledge_chunks (chunk_index);

-- ── 5. btree on jee_problems.subject ─────────────────────────────────────────
-- search_jee_problems filters by subject; existing HNSW handles embedding ANN.
CREATE INDEX IF NOT EXISTS idx_jee_problems_subject_v2
    ON jee_problems (subject)
    WHERE embedding IS NOT NULL;

-- ── 6. GIN trigram on concepts.subtopic + concepts.description ───────────────
-- search_concepts uses ILIKE on both columns. Concepts table is small (~84+ rows)
-- but this also makes search_concepts faster as it grows.
CREATE INDEX IF NOT EXISTS idx_concepts_subtopic_trgm
    ON concepts USING gin (subtopic gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_concepts_description_trgm
    ON concepts USING gin (description gin_trgm_ops);

-- ── Verify ────────────────────────────────────────────────────────────────────
-- After applying, verify indexes exist:
--   SELECT indexname, indexdef FROM pg_indexes
--   WHERE tablename IN ('knowledge_chunks', 'jee_problems', 'concepts')
--   ORDER BY tablename, indexname;
