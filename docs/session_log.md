# Session Log — UpMyRank

<!-- Most recent session at top. Keep last 3 entries only. -->
<!-- Written by Claude at end of each session via /handoff command. -->

## Session 2026-04-14 — Feedback Loop + 4-Dim Judge + RAG Metrics + Settings + Multi-Subject Onboarding
**Focus:** Closed feedback loop for pedagogy quality; 4-dimension LLM judge pipeline; RAG telemetry; `/settings` page; multi-subject onboarding expansion (Chemistry + Maths marks, learning preference, subject_strengths persona); sidebar width fix; offline RAGAS eval script.
**Status:** DONE — all 13 steps complete, migration applied, TypeScript 0 errors.

**Changed files:**
- `scripts/migrate_v12_feedback.sql` — NEW: `response_feedback`, `judge_evaluations`, `session_metrics` tables + 4 new `students` columns; idempotent (DROP POLICY IF EXISTS before each CREATE POLICY). ✅ Applied.
- `frontend/web/components/Sidebar.tsx` — `w-[220px]` → `w-[280px]`
- `frontend/web/components/TopicTree.tsx` — chapter name: removed `truncate`, added `break-words`; chevron `self-start mt-[3px]`
- `frontend/web/app/page.tsx`, `doubt/page.tsx`, `practice/page.tsx`, `mock/page.tsx`, `progress/page.tsx` — `md:ml-[236px]` → `md:ml-[296px]`
- `frontend/web/lib/types.ts` — `ChatMessage.feedback?`; `PersonaProfile` adds `subject_strengths?`, `priority_subject?`, `learning_preference?`
- `frontend/web/components/ChatMessage.tsx` — ThumbsUp/ThumbsDown buttons on AI messages; `msgIdx` + `onFeedback` props
- `frontend/web/app/doubt/page.tsx` — `handleFeedback()` with optimistic update; `onFeedback` + `msgIdx` wired to ChatMessage
- `app/api/feedback.py` — NEW: `POST /feedback/response` (upsert), `GET /feedback/summary/{doubt_session_id}`
- `app/main.py` — `feedback` router registered
- `app/services/eval/judge.py` — REWRITTEN: `evaluate_response()` 4-dim output; backward-compat `score_response()` wrapper
- `app/api/session.py` — `_run_judge_for_session()` coroutine + `asyncio.create_task()` in `POST /session/end`
- `app/services/rag/agent.py` — `_EMPTY_CONTEXT` gains `retrieval_latency_ms: 0`
- `app/services/doubt/engine.py` — `_rag_metrics` dict in `start_session()` and `get_hint()` returns; `render_personalization()` calls updated to pass `persona_profile`
- `app/api/doubt.py` — `_write_session_metrics()` helper + fire-and-forget calls after each doubt turn
- `frontend/web/app/settings/page.tsx` — NEW: 4-tab settings page (Profile / My Analytics / System Analytics / Preferences)
- `app/config.py` — `admin_student_id: str = ""`
- `app/api/admin.py` — `GET /admin/is_admin`, `GET /admin/judge-metrics`
- `scripts/eval_ragas.py` — NEW: offline RAGAS-style eval pipeline
- `scripts/data/golden_dataset.json` — NEW: 20 Q&A pairs (8 Physics, 6 Chemistry, 6 Maths)
- `app/api/onboarding.py` — `OnboardingSubmitRequest` + `_PERSONA_PROMPT` expanded to multi-subject; DB UPDATE stores 4 new columns
- `app/services/doubt/prompts.py` — `PERSONALIZATION_PROMPT` + `render_personalization()` updated for learning_preference, subject_strengths, priority_subject
- `frontend/web/app/onboarding/page.tsx` — Step 1: 3 marks inputs; Step 2: subject-tabbed topic chips (36 total: 16+10+10); Step 3: priority_subject + learningPreference selectors
- `MEMORY.md`, `docs/decisions.md`, `docs/session_log.md` — updated

**Current system state:**
- TypeScript: `npx tsc --noEmit` → 0 errors
- DB: migrations v1–v12 all applied; 3 new tables active; 4 new students columns present
- Backend: feedback, judge, RAG metrics all wired and fire-and-forget safe
- Onboarding: full multi-subject persona builder (Physics + Chemistry + Maths marks, 36 topic chips, explicit learning preference)

**In progress / half done:**
Nothing. All 13 steps complete.

**Cliff notes (non-obvious context):**
- `CREATE POLICY` has no `IF NOT EXISTS` in PostgreSQL. Migration is now idempotent via `DROP POLICY IF EXISTS` before each `CREATE POLICY`. Never forget this pattern.
- `_rag_metrics` is a non-user-facing key in engine return dicts — consumed by `doubt.py`, never sent to frontend.
- `render_personalization(pedagogy_config, persona_profile)` — second arg is optional (default None). All 3 call sites in engine.py pass persona_profile as positional arg. Do not break this signature.
- `judge_evaluations` is populated async after session/end. Allow 5-10s delay before checking DB rows.
- `ADMIN_STUDENT_ID` env var must be set in `.env` for System Analytics tab to appear in `/settings`. Format: plain UUID string matching the admin student's `id` in the `students` table.
- `learning_preference` from onboarding overrides `preferred_style` in rendered personalization — they map to the same concept but the explicit student input is authoritative.

**Next session — read these files first:**
Nothing specific needed — project is in clean state.

**Next session — start here:**
Ask the user what to build next. Possible directions: run `python scripts/eval_ragas.py` to get a baseline RAGAS score, expand golden_dataset.json to 50 questions, deploy to Render/Vercel, or build mobile PWA.

---

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

