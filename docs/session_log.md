# Session Log — UpMyRank

<!-- Most recent session at top. Keep last 3 entries only. -->
<!-- Written by Claude at end of each session via /handoff command. -->

## Session 2026-04-13 (UI Overhaul)
**Focus:** Full UI overhaul — Topic Tree sidebar, Quick Doubt FAB, mobile responsive layout, subject mastery dashboard
**Status:** DONE (steps 1–9 complete, step 10 = manual test at breakpoints)

**Changed files:**
- `frontend/web/lib/syllabus.ts` — NEW: full JEE static syllabus (Physics 20ch, Chemistry 21ch, Maths 21ch), `STATIC_SYLLABUS`, `SYLLABUS_MAP`, `masteryColor()`, `masteryBg()`, `SyllabusChapter/Topic/Subject` interfaces
- `frontend/web/components/TopicTree.tsx` — NEW: Subject tabs (Phy/Che/Mat), ChapterAccordion with mastery bar, TopicRow with Doubt/Practice/Mock icons, `/taxonomy` + genome concurrent fetch via `Promise.allSettled`, static syllabus fallback
- `frontend/web/components/QuickDoubtFAB.tsx` — NEW: 56px FAB, "Quick Doubt" label fades after 3s, bottom-sheet textarea (fontSize:16, iOS safe area), navigates to `/doubt?q=<question>`, hidden on /doubt /auth /onboarding
- `frontend/web/components/Sidebar.tsx` — REWRITE: IdentityCard + TopicTree + footer links; NEW mobile header (hamburger + logo + avatar); Framer Motion drawer; bottom nav bar REMOVED
- `frontend/web/app/layout.tsx` — added `<QuickDoubtFAB />` globally inside AuthProvider
- `frontend/web/app/doubt/page.tsx` — `subjectParam`, `chapterParam`, `topicLock`, `quickDoubtQ` URL params; topic-scoped header with subject badge; all `subject: 'Physics'` → `subject: subjectParam`; QuickDoubtQ auto-submit effect; `h-[100dvh]` + `pt-[calc(56px+12px)] md:pt-3`
- `frontend/web/app/page.tsx` — REWRITE: 3 subject mastery cards (per-subject avg from topic_mastery), exam countdown card (JEE April of target_year), "Continue last session" link, responsive grid (2-col mobile → 3-col desktop)
- `frontend/web/app/practice/page.tsx` — `h-[100dvh]`, `pb-24` → `pb-4`, `pt-14 md:pt-0`
- `frontend/web/app/mock/page.tsx` — `h-[100dvh]`, `pt-14 md:pt-0`
- `frontend/web/app/progress/page.tsx` — `h-[100dvh]`, `pb-24` → `pb-4`, `pt-14 md:pt-0`
- `frontend/web/app/globals.css` — added `.h-dvh`, `.min-h-dvh`, `.scroll-touch`, `.touch-target` utility classes
- `frontend/web/components/ChatInput.tsx` — `style={{ fontSize: 16 }}` on textarea (iOS zoom fix)
- `app/services/doubt/engine.py` — subject short-circuit in both `start_session()` and `start_session_stream()`: skip `_classify_subject()` gpt-4o-mini call when `subject ∈ SUPPORTED_SUBJECTS`
- `docs/ui_overhaul_plan.md` — status updated, all steps marked complete
- `docs/decisions.md` — UI Overhaul decision entry added

**Current system state:**
- TypeScript: `npx tsc --noEmit` → 0 errors after all changes
- Backend: subject short-circuit saves ~200ms per topic-scoped session start
- TopicTree: uses `/taxonomy` as primary, falls back to static SYLLABUS_MAP per subject
- QuickDoubtFAB: globally mounted, hidden on /doubt /auth /onboarding

**In progress / half done:**
Step 10 (manual breakpoint testing at 360px/390px/768px/1280px) not done — requires browser.

**Cliff notes (non-obvious context):**
- Subject mastery on dashboard is derived by matching `genome.topic_mastery` keys (subtopic names) against static SYLLABUS_MAP topic names (lowercase normalize). Expect low match rate until students have sessions — cards show 0% for unstarted subjects.
- `quickDoubtFiredRef` prevents the auto-submit effect from double-firing on re-renders. It fires once when `studySessionId` becomes non-null.
- Mobile header is `h-14` (56px). All scrollable content areas have `pt-14 md:pt-0` to clear it. The `doubt/page.tsx` uses `pt-[calc(56px+12px)]` because it already has outer `p-3`.
- The test phase in mock.tsx uses `flex overflow-hidden` (full-screen, no scroll) so it intentionally has NO `pt-14 md:pt-0`.

**Next session — read these files first:**
Nothing specific — project is clean.

**Next session — start here:**
Manual test at 360px mobile breakpoint and fix any overflow issues. Then ask user what to build next.

---

## Session 2026-04-13 (cont.)
**Focus:** Multi-subject expansion audit, NCERT Maths PDF ingestion, critical bug fixes, full E2E verification across Physics/Chemistry/Maths
**Status:** DONE

**Changed files:**
- `scripts/ingest_maths_pdf.py` — new script: downloads + ingests 29 NCERT Maths PDFs (Class 11+12) from ncert.nic.in via pdfplumber; 350-token chunks / 50-token overlap; resumable via `.ingest_maths_pdf_progress.json`; URL structure: Class 12 Part 2 uses `lemh2xx`, Stats/Prob use `kest101`/`kesp101`
- `app/services/doubt/prompts.py` — 8 Physics-only hardcoded strings replaced; `INTENT_CLASSIFIER_PROMPT` gains `{subject}` param + `subject_doubt` replaces `physics_doubt`; `SUPPORTED_SUBJECTS` constant added; `get_subject_context()` + `build_system_prompt()` subject-aware; **critical fix**: `CUSTOMIZATION_PROMPT` line 643 LaTeX braces double-escaped `{{u^2 \\sin 2\\theta}}` / `{{g}}` — was causing silent `KeyError` swallowed by policy engine, every student got unpersonalized fallback
- `app/services/doubt/engine.py` — `classify_intent()` gains `subject` param; `physics_doubt` normalized to `subject_doubt`; fallback intent updated
- `app/api/doubt.py` — `subject_must_be_valid` field_validator on `AskRequest`; `classify_intent()` calls pass `subject`; all `physics_doubt` → `subject_doubt`; topic fallback uses `body.subject`
- `app/api/mock.py` — `_MCQ_PROMPT` parameterised with `{subject}`; `_generate_mcq_options()` accepts `subject`
- `MEMORY.md`, `CLAUDE.md`, `RULES.md`, `docs/decisions.md`, `docs/bugs.md` — all updated to reflect full project state

**Current system state:**
- Backend: running on port 8000, fully operational
- DB knowledge_chunks: Physics=10,505 | Chemistry=3,138 | Maths=1,426 | Total=15,069
- DB jee_problems: 20 seed PYQs
- Policy engine: now runs correctly for all 3 subjects (personalized system prompts working)
- All 3 subjects verified E2E: Physics ✅ Chemistry ✅ Maths ✅
- All migrations applied through v11

**In progress / half done:**
Nothing half-done. All changes complete and tested.

**Cliff notes (non-obvious context):**
- The `build_system_prompt()` silent KeyError was a P0 bug — policy engine was silently catching it for every single request. All students were getting unpersonalized responses. Rule 13 added to RULES.md to prevent recurrence.
- `physics_doubt` backward-compat alias is kept in `_VALID_INTENTS` in engine.py and normalized immediately to `subject_doubt`. Old clients sending `physics_doubt` still work.
- NCERT Maths PDF URL structure: Class 12 is split into 2 books — Part 1 (`lemh1xx.pdf`, ch1–6), Part 2 (`lemh2xx.pdf`, ch7–13). Statistics uses `kest101.pdf`, Probability uses `kesp101.pdf`.
- Maths "outside syllabus" warnings are expected for some questions — agentic loop degrades gracefully to NCERT-only retrieval.
- Embedding model confirmed: `text-embedding-3-small` 1536-dim. The `all-MiniLM-L6-v2` 384-dim reference in old docs was never in production code.

**Next session — read these files first:**
Nothing specific — project is in clean state. Run `scripts/regression_gate.py` to confirm ≥90% pass rate with agentic RAG if deploying.

**Next session — start here:**
Ask the user what to build next. Possible directions: expand JEE PYQ bank (manual curation), add more Maths PDF chapters, build student-facing progress dashboard, or deploy.

---

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

