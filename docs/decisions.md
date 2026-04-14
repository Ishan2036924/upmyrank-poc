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

## 2026-04-13 — UI Overhaul: Topic Tree + Quick Doubt FAB + Mobile Responsive
**Decision:** Full sidebar redesign — topic tree navigation (Subject → Chapter → Topic) replaces old nav links. Quick Doubt FAB globally mounted in layout.tsx. Mobile header (hamburger + avatar) replaces bottom nav bar.
**Why:** Old sidebar had text nav links with no syllabus context. Students navigated blindly. New tree shows mastery bars per topic + direct Doubt/Practice/Mock actions — closing the loop between "what to study" and "how to study it".
**Key choices:**
- `/taxonomy` as primary data source; static `lib/syllabus.ts` (62 chapters, 3 subjects) as fallback when subject has 0 API chapters
- `QuickDoubtFAB` navigates to `/doubt?q=<question>` — no new endpoint, classification runs server-side as normal
- Subject short-circuit in `engine.py`: if `subject` ∈ `SUPPORTED_SUBJECTS`, skip `_classify_subject()` gpt-4o-mini call entirely (saves ~200ms per topic-scoped session start)
- Dashboard: 3 subject mastery cards computed by matching `genome.topic_mastery` keys against static syllabus topic names (lowercase), exam countdown using `target_year`
- Mobile layout: `h-[100dvh]` instead of `h-screen`, `fontSize: 16` on all inputs (iOS zoom prevention), `pt-14 md:pt-0` for mobile header clearance
**Files changed:** `lib/syllabus.ts` (new), `components/TopicTree.tsx` (new), `components/QuickDoubtFAB.tsx` (new), `components/Sidebar.tsx` (rewrite), `app/layout.tsx`, `app/doubt/page.tsx`, `app/page.tsx`, `app/practice/page.tsx`, `app/mock/page.tsx`, `app/progress/page.tsx`, `app/globals.css`, `components/ChatInput.tsx`, `app/services/doubt/engine.py`

## 2026-04-13 — Socratic flow fixes: context anchoring + solution-seeking detection
**Decision:** Four Socratic flow problems fixed in prompts.py + engine.py only. No new DB tables — `ignored_socratic_count` stored in existing `stored_analysis` JSONB column on `doubt_sessions`.
**Fix 1+4 (context drift + context carry):** Added `{problem}` parameter to `HINT_LEVEL_1_PROMPT` and `HINT_LEVEL_2_PROMPT`. Added "⚠ CONTEXT LOCK" instruction in both hint prompts, `SOCRATIC_QUESTION_PROMPT`, and `FULL_SOLUTION_PROMPT`. Instruction explicitly forbids substituting generic examples and requires anchoring every response to the exact problem setup.
**Fix 2 (repetitive fallback):** Added `_SOLUTION_SEEKER_RE` regex in engine.py (same pattern as `_CONVERSATIONAL_TOKENS` — no LLM cost). When soft solution-seeking detected: (a) `SOLUTION_SEEKER_NOTE_FIRST`/`SOLUTION_SEEKER_NOTE_REPEAT` appended to the hint PROMPT (tells LLM not to repeat Socratic question), (b) `SOLUTION_SEEKER_PREAMBLE` prepended to the LLM response ("I can see you want the answer — let's try one more step first."), (c) `ignored_socratic_count` incremented in `stored_analysis` for persistence across turns.
**Fix 3 (hint rhythm):** Added "THIS IS HINT N OF 3 — DO NOT RESTART" headers to `HINT_LEVEL_1_PROMPT` and `HINT_LEVEL_2_PROMPT`. Pure prompt-level fix — DB state (`current_hint_level`) was correct, the LLM was re-asking Socratic questions instead of delivering structured hints.
**Rejected:** Storing `ignored_socratic_count` in a new DB column (unnecessary — `stored_analysis` JSONB is already persisted on every `get_hint()` call). Using `_analyze_student_response()` for solution-seeking detection (costs an LLM call — regex is sufficient and matches the project's existing pattern for cheap classification).

## 2026-04-14 — 4-dimension judge over 1-dimension Socratic score
**Decision:** Expanded judge from single Socratic quality score (0–2) to 4 dimensions: pedagogical (0–2), factual (0–1), context_relevance (0–1), hint_appropriateness (0–1). Composite `overall_score = 0.4*(ped/2) + 0.3*factual + 0.15*ctx + 0.15*hint`.
**Why:** Socratic score alone missed factual errors (LLM could be Socratically correct but factually wrong) and couldn't distinguish RAG context utilization from good guessing. 4-dim output is the minimum to run a meaningful RAGAS-style eval pipeline.
**Backward compat:** `score_response()` wrapper preserved — calls `evaluate_response()` internally and returns `{score: pedagogical_score, rationale: str}`. All existing callers continue to work unchanged.
**Model:** gpt-4o-mini (not gpt-4.1-mini) at temp=0 — classification task, not Socratic dialogue. Single LLM call for all 4 dimensions (JSON output) to minimize latency.
**Rejected:** Calling judge after every hint turn (too expensive, blocks student response). Instead: fired once at `POST /session/end` for all doubt sessions in the study session.

## 2026-04-14 — Session metrics written fire-and-forget from API layer (not engine)
**Decision:** `_write_session_metrics()` is a fire-and-forget `asyncio.create_task()` in `doubt.py`. RAG telemetry surfaced to API layer via `_rag_metrics` key in engine return dicts (not by direct DB access from engine layer).
**Why:** `AgenticRetriever.run()` is called inside `engine.py` which has no direct access to the DB pool. Rather than threading pool through engine just for metrics, engine includes `_rag_metrics` as a non-user-facing key in its return dict. `doubt.py` consumes it and fires the metrics write. Keeps engine layer clean.
**Rejected:** DB pool injected into engine (would break encapsulation — engine is a service layer, not a data access layer). Metrics written synchronously (would add latency to every student request).
**Cliff note:** `_rag_metrics` key is never included in any API response — only consumed internally by `doubt.py` before returning.

## 2026-04-14 — Admin gate via ADMIN_STUDENT_ID env var (not Supabase roles)
**Decision:** System Analytics tab in Settings page (and `GET /admin/is_admin`) gates on `settings.admin_student_id` — a plain UUID string in `.env`. The authenticated student's UUID is compared with this value.
**Why:** Adding a Supabase RLS role or a custom `is_admin` column would require schema changes and Supabase dashboard access. A UUID comparison in FastAPI config is zero-schema, zero-migration, and just as secure for a POC where there's one admin (the developer).
**Rejected:** Supabase custom role (requires Supabase CLI/dashboard), `is_admin BOOL` column on students (another migration, another sync point), JWT custom claims (Supabase dashboard change needed).
**Revisit if:** Multiple admin users needed, or RBAC required for team usage.

## 2026-04-14 — Preferences stored in localStorage only (no DB)
**Decision:** Settings → Preferences tab (show hint badges, show confidence meter, show RAG hints) stored exclusively in `localStorage` with `upmyrank_pref_` prefix. No DB column, no API call.
**Why:** UI preferences are client-side concerns. They don't affect learning quality metrics, don't need server-side access, and don't affect persona. Storing them in DB adds migration + API surface for zero learning value.
**Rejected:** `preferences JSONB` column on `students` (overkill for 3 boolean flags), `student_memory` JSONB injection (would pollute the persona context with UI toggles).
**Revisit if:** Preferences need to sync across devices (e.g., mobile app), or a preference meaningfully affects backend behavior (e.g., disable Socratic mode entirely).

## 2026-04-14 — Explicit learning_preference in onboarding (not LLM-inferred)
**Decision:** Onboarding Step 3 now asks students directly: "How do you prefer to learn?" with 4 explicit choices (formula-first, analogies, step-by-step examples, visual diagrams). This value is stored as `learning_preference` on the `students` row and passed directly to `_PERSONA_PROMPT` as-is.
**Why:** The original design had the LLM infer `preferred_style` from topic tags ("mostly numerical hard_topics → formula"). This inference was unreliable: a student who struggles with integration isn't necessarily formula-oriented — they may need analogies. Direct student input is more accurate than LLM inference from indirect signals.
**Impact on prompts.py:** `render_personalization()` now accepts `persona_profile` as a second arg. If `learning_preference` is present it overrides `preferred_style` in the rendered personalization block. `PERSONALIZATION_PROMPT` has 3 new placeholders: `{learning_preference}`, `{subject_strengths_block}`, `{priority_subject_block}`.
**Rejected:** Pure LLM inference of learning style (unreliable), separate onboarding step for each preference type (too long), inferring from session behavior after N doubts (too slow — student would get mismatched style for first 10+ sessions).
