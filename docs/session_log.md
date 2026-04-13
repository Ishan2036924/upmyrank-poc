# Session Log — UpMyRank

<!-- Most recent session at top. Keep last 3 entries only. -->
<!-- Written by Claude at end of each session via /handoff command. -->

## Session 2026-04-13
**Focus:** Agentic RAG upgrade — Part 1–4 complete: LLM-driven retrieval loop, NCERT Chemistry+Maths KB expansion, JEE PYQ table, subject router
**Status:** DONE

**Changed files:**
- `scripts/migrate_v11_jee_problems.sql` — creates `jee_problems` table (vector(1536), HNSW index, `match_jee_problems()` function, RLS read-only policy)
- `scripts/ingest_chem_maths.py` — new script: ingests NCERT Chem+Maths from KadamParth/Ncert_dataset HF → knowledge_chunks; grade 11/12 filter; 5 HF fallbacks for Maths; local seed fallback; resumable via progress JSON
- `scripts/ingest_jee_pyq.py` — new script: ingests JEE PYQ from HuggingFace (with seed fallback); UUID5 deterministic IDs; resumable
- `scripts/data/jee_pyq_seed.json` — 20 verified JEE PYQs (Physics, Chemistry, Maths) — already ingested
- `scripts/data/ncert_maths_seed.json` — 32 NCERT Maths Q&A rows covering all key JEE chapters (Class 11+12) — already ingested
- `app/services/rag/tools.py` — 4 retrieval tool functions + TOOL_SCHEMAS OpenAI function calling defs
- `app/services/rag/agent.py` — AgenticRetriever class: MAX_STEPS=3, AGENT_MODEL=gpt-4o-mini, level-3 nuclear override double gate, full tool loop
- `app/services/doubt/prompts.py` — appended SUBJECT_CLASSIFIER_SYSTEM + SUBJECT_CLASSIFIER_PROMPT
- `app/services/doubt/engine.py` — 7 surgical edits: import AgenticRetriever, `_agentic_retriever` init in __init__, new `_classify_subject()` method, replaced `get_rag_context` calls in start_session/start_session_stream/get_hint with agentic retriever

**Current system state:**
- Backend: running on port 8000, fully operational
- DB knowledge_chunks: Physics=10505, Chemistry=3138, Maths=47 chunks
- DB jee_problems: 20 seed PYQs ingested
- Agentic RAG: verified end-to-end (all 3 subjects retrieve correctly, level-3 returns empty)
- Subject classifier: 3/3 questions classified correctly (Physics/Chemistry/Maths)

**In progress / half done:**
Nothing half-done. All 4 parts of Agentic RAG upgrade complete and tested.

**Cliff notes (non-obvious context):**
- KadamParth/Ncert_dataset has NO Mathematics subject — only Physics, Chemistry. Maths fallback uses local seed `scripts/data/ncert_maths_seed.json`.
- All HuggingFace JEE PYQ datasets return 401 (private). `scripts/data/jee_pyq_seed.json` is the primary source.
- Embedding model is `text-embedding-3-small` (1536-dim OpenAI) — NOT all-MiniLM-L6-v2 (384-dim). Both ingest scripts use OpenAI embeddings.
- AgenticRetriever.run() is called in exactly 3 places in engine.py: start_session(), start_session_stream(), get_hint(). Never add a 4th.
- Level-3 nuclear override is double-gated: checked in BOTH agent.py (returns _EMPTY_CONTEXT immediately) AND engine.py (sets rag={context_text:"", chunks:[], ...} before LLM call).
- `_genome_update_task` is untouched — sole mastery writer invariant preserved.
- Maths ingestion progress is tracked in `.ingest_chem_maths_progress.json` (2228 completed after this session).

**Next session — read these files first:**
`app/services/rag/agent.py`, `app/services/rag/tools.py` if modifying RAG behavior.

**Next session — start here:**
- Consider expanding `scripts/data/ncert_maths_seed.json` with more chapters (currently covers all 13 key JEE chapters but with ~2-3 Q&A each)
- Consider expanding `scripts/data/jee_pyq_seed.json` with more verified PYQs
- Run regression gate (`scripts/regression_gate.py`) to confirm pass rate ≥ 90% with new agentic RAG

---

## Session 2026-04-10
**Focus:** RLS security fix, project scaffolding, session handoff system, persona evolution, page margin fixes
**Status:** DONE

**Changed files:**
- `scripts/migrate_v9_persona_staleness.sql` — adds `persona_profile_updated_at TIMESTAMPTZ` to student_memory (applied to production)
- `scripts/migrate_v10_rls.sql` — enables RLS on all 10 public tables with 10 policies (applied to production)
- `app/services/memory/summarizer.py` — `maybe_compress_profile()` now fires 2nd GPT-4o-mini call every 5 sessions to rewrite `persona_profile.persona_summary` using mastery data
- `app/services/memory/context.py` — `build_context_bundle()` fetches persona freshness; `format_context_for_prompt()` renders STUDENT PERSONA block with staleness warning if >15 sessions old
- `docs/decisions.md` — created, backfilled 11 architecture decisions + 2 new (RLS approach, run_migration over Supabase CLI)
- `docs/bugs.md` — created, backfilled 11 bugs including all fixes from recent sessions
- `docs/session_log.md` — created (this file), rolling 3-session handoff log
- `.claude/settings.json` — created, Bash allow/deny rules (blocks git push, rm -rf, DROP, Supabase CLI)
- `.claude/commands/handoff.md` — created, `/project:handoff` command for session handoff
- `.claude/commands/review.md`, `fix.md`, `feature.md`, `debug.md` — created
- `CLAUDE.md` — appended Auto-Read Rules (session_log.md always read, trigger rules for other docs)

**Current system state:**
- Backend: working, no pending changes
- Frontend: working, no pending changes
- DB: Last migration v10_rls applied. All 10 tables have RLS enabled. 10 policies active.

**In progress / half done:**
Nothing half-done. Project is in a clean state.

**Cliff notes (non-obvious context):**
- `/project:handoff` command not working in current Claude Code version — user must say "do a handoff" instead. File and format are fully set up.
- RLS policies use `auth.uid() = student_id` NOT `user_id` — original request had wrong column names. Always inspect schema before writing RLS SQL.
- FastAPI backend connects as `postgres` superuser — bypasses RLS by design. No backend changes needed for RLS ever.
- Supabase CLI is NOT installed and blocked in `.claude/settings.json`. All migrations go through `./scripts/run_migration.sh`. Never suggest Supabase CLI.
- `persona_profile` is a JSONB dict — `persona_summary` is a free-text key inside it. Other keys (`scaffolding_level`, `preferred_style`, etc.) preserved via dict merge in `maybe_compress_profile()`. Never overwrite the whole JSONB.
- Sidebar is 220px inside m-3 = 236px total offset. All main pages use `md:ml-[236px]`.

**Next session — read these files first:**
Nothing specific needed — project is clean.

**Next session — start here:**
Ask the user what to build next.

---

## Session 2026-04-07 / 2026-04-08
**Focus:** Auth refresh, cold-start fix, intent improvements, sidebar redesign, persona evolution, RLS prep
**Status:** DONE

**Changed files:**
- `app/api/auth.py` — added /auth/refresh endpoint, refresh_token in login/signup responses
- `app/api/doubt.py` — student_resolved + student_attempt params on HintRequest
- `app/api/onboarding.py` — fixed ._openai → ._client, max_length 5→15 for topics
- `app/services/doubt/engine.py` — conversational/explanation pre-filters, student_resolved early-return path
- `app/services/doubt/prompts.py` — CONVERSATIONAL_RESPONSE, EXPLANATION_PROMPT, updated classifier examples
- `app/services/memory/summarizer.py` — maybe_compress_profile now rewrites persona_profile.persona_summary every 5 sessions using mastery data
- `app/services/memory/context.py` — build_context_bundle fetches persona freshness; format_context_for_prompt renders STUDENT PERSONA block with staleness warning
- `frontend/web/lib/api.ts` — fetchWithRetry (5s/15s/30s), pingBackend, auto-refresh on 401
- `frontend/web/lib/auth.tsx` — refreshToken(), LS_REFRESH_TOKEN
- `frontend/web/components/ChatInput.tsx` — base64 image via FileReader (Supabase storage removed)
- `frontend/web/components/Sidebar.tsx` — full redesign: 220px wide, student identity, working logout
- `frontend/web/app/doubt/page.tsx` — attempt box (20-char min), handleGotIt fixed to use /doubt/hint
- All pages — ml-[80px] → ml-[236px] for new sidebar width
- `scripts/migrate_v9_persona_staleness.sql` — adds persona_profile_updated_at column (applied)

**Current system state:**
- Backend: working
- Frontend: working, sidebar is 220px (pages use ml-[236px] offset)
- DB: migrate_v9 applied to production

**In progress / half done:**
Nothing half-done.

**Cliff notes (non-obvious context):**
- Sidebar is 220px inside m-3 container = 236px total offset for page content
- Image upload is base64 only — no Supabase Storage, no env vars needed on Vercel
- handleGotIt must call /doubt/hint with student_resolved=true — NOT /student/{id}/update-mastery. The latter skips _genome_update_task.
- Conversational pre-filter is case-sensitive frozenset — input must be .lower()'d before lookup
- EXPLANATION_PROMPT bypasses Socratic engine entirely — no RAG, no intent classification, direct LLM call
