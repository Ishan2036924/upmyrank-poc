# Architecture Decisions — UpMyRank

## 2025-XX-XX — all-MiniLM-L6-v2 over text-embedding-3-large
**Decision:** Use sentence-transformers all-MiniLM-L6-v2 (384d) for embeddings
**Why:** Free, local inference, no API cost. Good enough for 10,500 NCERT Physics chunks. OpenAI embedding API would add per-query cost at scale.
**Rejected:** text-embedding-3-large (3072d) — cost prohibitive for POC, documentation referenced it but implementation never used it
**Revisit if:** RAG recall drops below 0.85 on JEE PYQ benchmark, or we scale beyond Physics to all subjects

## 2025-XX-XX — HNSW over ivfflat for pgvector index
**Decision:** HNSW index on pgvector
**Why:** Better recall on small datasets (<50K vectors). ivfflat requires large cluster counts to perform well, which we don't have.
**Rejected:** ivfflat (some docs reference it — legacy, do not use)
**Revisit if:** Vector count exceeds 500K and index build time becomes a concern

## 2025-XX-XX — HuggingFace dataset over PDF parsing for NCERT
**Decision:** Use KadamParth/Ncert_dataset from HuggingFace (10,500+ Physics chunks)
**Why:** PDF parsing breaks math extraction (subscripts, superscripts, equations). HF dataset is pre-cleaned.
**Rejected:** PyMuPDF/pdfplumber PDF parsing — broken LaTeX output
**Revisit if:** Need to ingest non-NCERT content (coaching material, PYQ papers) where HF datasets don't exist

## 2025-XX-XX — GPT-4o-mini + GPT-4.1-mini tiered routing over single model
**Decision:** Two-tier LLM routing — 4o-mini for classification/summarization, 4.1-mini for Socratic/solutions
**Why:** 4o-mini is 10-15x cheaper and fast enough for intent detection and session summaries. 4.1-mini needed only for pedagogically accurate Socratic responses.
**Rejected:** Single model for everything (either too expensive or too low quality)
**Revisit if:** OpenAI releases a model that's both cheap and high-quality enough for Socratic dialogue

## 2025-XX-XX — Supabase over self-hosted PostgreSQL
**Decision:** Supabase managed PostgreSQL + pgvector + Auth + Storage
**Why:** Fastest path to POC. Auth, storage, realtime all bundled. pgvector native support.
**Rejected:** Self-hosted PG (ops overhead for solo dev), Firebase (no vector search), Pinecone (separate vector DB adds complexity)
**Revisit if:** Supabase free tier limits hit, or need multi-region deployment

## 2025-XX-XX — Next.js over React Native for POC
**Decision:** Next.js web app for POC, not React Native mobile
**Why:** Faster iteration, easier to demo, LaTeX rendering ecosystem more mature on web. Mobile can come post-validation.
**Rejected:** React Native (production architecture doc references it — that's the scale target, not the POC)
**Revisit if:** POC validated and ready for mobile deployment

## 2025-XX-XX — Blocking session summarizer over async fire-and-forget
**Decision:** Session summarizer runs as a blocking await before marking doubt block ended
**Why:** Async fire-and-forget caused race condition — next doubt block would start before summary was written, breaking context injection for subsequent doubts.
**Rejected:** Async background task (caused the bug documented in bugs.md)
**Revisit if:** Never. This must always be synchronous in the request lifecycle.

## 2025-XX-XX — Migrations via shell script over Supabase CLI
**Decision:** Run all migrations via `./scripts/run_migration.sh <sql_file>`
**Why:** Supabase CLI had compatibility issues. Shell script gives us direct psql control and works reliably.
**Rejected:** Supabase CLI migrations, Alembic (Python ORM overhead not needed)
**Revisit if:** Team grows and needs migration versioning/rollback tooling

## 2025-XX-XX — Gemini 2.0 Flash deferred for Vision AI
**Decision:** Use GPT-4o multimodal for image-to-doubt feature
**Why:** Gemini Live outputs audio not structured text, breaking downstream LaTeX pipeline. GPT-4o returns structured text directly.
**Rejected:** Gemini Live API (audio output incompatible), YOLOv8+TrOCR pipeline (Gemini 2.0 Flash flagged as simpler replacement — deferred to Phase 2 benchmarking)
**Revisit if:** Phase 2 benchmarking shows Gemini 2.0 Flash (non-Live) outperforms GPT-4o on math OCR accuracy

## 2026-04-07 — Base64 image upload over Supabase Storage
**Decision:** ChatInput sends images as base64 data URLs directly to the backend. No Supabase Storage bucket used.
**Why:** Supabase env vars (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`) are not set on Vercel. Removing the dependency unblocks image upload without any infra changes.
**Rejected:** Supabase Storage (requires env vars in Vercel, adds bucket lifecycle management)
**Revisit if:** Image sizes exceed ~1MB regularly and base64 payload size becomes a latency concern

## 2026-04-07 — Auto-refresh JWT on 401 over forcing re-login
**Decision:** `api.ts` catches 401, calls `/auth/refresh` silently, retries the original request. Redirects to login only if refresh fails.
**Why:** Supabase access tokens expire after 1 hour. Students mid-session were getting kicked out. Silent refresh is transparent to the user.
**Rejected:** Force re-login on every 401 (terrible UX for 1-hour study sessions)
**Revisit if:** Refresh token rotation policy changes or Supabase introduces a client-side SDK that handles this natively

## 2026-04-07 — Persona evolves every 5 sessions via maybe_compress_profile()
**Decision:** `maybe_compress_profile()` fires a second GPT-4o-mini call every 5 sessions to rewrite `persona_profile.persona_summary` using session evidence + mastery data.
**Why:** Onboarding-built persona became stale — beginners in Week 1 were still getting beginner scaffolding in Week 4. Mastery data provides ground truth for ability-level inference.
**Rejected:** Updating persona after every session (too expensive, too noisy), keeping onboarding persona immutable (caused scaffolding drift)
**Revisit if:** 5-session cadence proves too slow for fast learners (could drop to 3)

## 2026-04-08 — run_migration.sh over Supabase CLI for RLS migration
**Decision:** RLS enablement done via `scripts/migrate_v10_rls.sql` + `run_migration.sh`, not Supabase CLI
**Why:** Supabase CLI not installed; established project pattern is shell script migrations. Supabase CLI approach was requested but conflicts with existing tooling decision.
**Rejected:** Supabase CLI (`supabase migration new` + `supabase db push`) — not installed, also blocked in `.claude/settings.json`
**Revisit if:** Never for this project. run_migration.sh is the standard.

## 2026-04-08 — RLS policies use student_id FK directly (not user_id)
**Decision:** All per-student RLS policies use `auth.uid() = student_id` (the actual column name confirmed from schema)
**Why:** The request's template SQL used `user_id` which doesn't exist. Schema inspection showed `student_id` is the FK on every table. `doubt_blocks` has a direct `student_id` column, no join needed.
**Note:** FastAPI backend connects as `postgres` superuser (bypasses RLS). Policies only affect direct Supabase client / anon / authenticated role access.

## 2026-04-13 — Agentic RAG over traditional single-pass RAG
**Decision:** Replace `get_rag_context()` single-pass retrieval with `AgenticRetriever` (native OpenAI function calling, max 3 steps)
**Why:** Single-pass RAG retrieved fixed-k chunks regardless of question type. Agentic loop lets the LLM decide which tools to call (NCERT chunks vs JEE PYQs vs concept graph) and how many steps are needed for sufficient context. Covers multi-hop questions that a single similarity search misses.
**Rejected:** LangChain/LangGraph — too many abstraction layers, harder to debug silent failures, unnecessary for a 4-tool loop. Native OpenAI function calling is transparent and maintainable.
**Note:** Level-3 nuclear gate is double-gated (agent.py + engine.py) so the agentic loop is structurally blocked at forced-attempt stage — cannot leak content through tool results.

## 2026-04-13 — NCERT Maths ingested from official PDFs (not HuggingFace)
**Decision:** `scripts/ingest_maths_pdf.py` downloads and parses Maths PDFs directly from ncert.nic.in using pdfplumber
**Why:** KadamParth/Ncert_dataset on HuggingFace contains Physics and Chemistry only — no Mathematics subject. The same HF dataset that worked for Physics/Chemistry has a structural gap for Maths.
**Rejected:** Using the same HF path for Maths (dataset simply doesn't have it). PyMuPDF was considered but pdfplumber gave cleaner text extraction for NCERT's PDF layout.
**Note:** Maths chunks (1,426) are lower than Physics (10,505) and Chemistry (3,138) because NCERT Maths PDFs have fewer text-dense chapters. Acceptable for JEE prep coverage. Expand by running ingest_maths_pdf.py with more chapters if needed.

## 2026-04-13 — JEE PYQ seed JSON as primary source (HuggingFace gated)
**Decision:** `scripts/data/jee_pyq_seed.json` (20 verified problems) is the primary JEE PYQ source, not HuggingFace
**Why:** All HuggingFace JEE PYQ datasets checked return HTTP 401 (private/gated). No public JEE PYQ dataset found on HF at the time of implementation.
**Rejected:** HuggingFace datasets (gated, inaccessible without approval), scraping external sites (legal/reliability risk)
**Revisit if:** A public HF dataset becomes available, or we build a manual curation pipeline to expand the seed to 200+ verified PYQs.

## 2026-04-13 — text-embedding-3-small (1536-dim) confirmed as project standard
**Decision:** All embeddings use OpenAI `text-embedding-3-small` at 1536 dimensions — this is the confirmed standard across all tables and ingestion scripts.
**Why:** Earlier documentation referenced `all-MiniLM-L6-v2` (384-dim, sentence-transformers) but the actual implementation in `app/services/rag/embeddings.py` uses OpenAI text-embedding-3-small. The 384-dim model was considered in early POC but never shipped. 1536-dim gives better recall for math-heavy NCERT content.
**Rejected:** all-MiniLM-L6-v2 (384-dim, free, local) — was in early docs but not in production code. text-embedding-3-large (3072-dim) — cost prohibitive with no recall gain for NCERT chunk sizes.
**Note:** All pgvector columns are `vector(1536)`. Never insert 384-dim embeddings — schema mismatch will fail silently with wrong similarity scores.
