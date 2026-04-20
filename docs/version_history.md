# UpMyRank — Version History

> **Read first in every new Claude session.** This is the 10,000-ft view of
> every improvement, bug fix, regression, and metric shipped in the project.
> For what's half-done right now, read `docs/session_log.md` after this.
>
> **Versioning scheme (semver-lite, pre-v1):**
> - `v0.X+1` — new feature, significant refactor, or eval-quality improvement
> - `v0.X.Y` — pure bug fix, no new features
> - `v1+` — not yet (still POC → early production)
>
> **Policy:** every commit that ships a user-visible change, fix, or
> architectural shift must append a new entry here BEFORE committing.
> Entries go at the TOP (reverse-chronological). Never edit old entries —
> append a new one if history needs a correction.

---

## Version index

| Version | Date | Headline |
|---|---|---|
| [v0.18](#v018--enterprise-ui-phase-1--design-tokens--ui-primitives-2026-04-18) | 2026-04-18 | Enterprise UI Phase 1 — design tokens + 18 shadcn-pattern primitives |
| [v0.17](#v017--version-history-doc--hard-no-commit-rule-2026-04-19) | 2026-04-19 | Version history doc + hard no-commit rule for Claude |
| [v0.16](#v016--preemptive-14-fix-hardening-batch-2026-04-19) | 2026-04-19 | Preemptive 14-fix hardening batch |
| [v0.15](#v015--context-loss-fix--per-topic-chat-isolation--hint-gate-2026-04-18) | 2026-04-18 | Context-loss fix + per-topic chat isolation + hint L1→L2 gate |
| [v0.14](#v014--socratic-quality-v2--v3-79--89-10-2026-04-17) | 2026-04-17 | Socratic quality v2 → v3 (7.9 → 8.9 / 10) |
| [v0.13](#v013--socratic-quality-v1--v2-55--80-10-2026-04-17) | 2026-04-17 | Socratic quality v1 → v2 (5.5 → 8.0 / 10) |
| [v0.12](#v012--mastery-loop-fix--feedback-uuid--fake-settings-removed-2026-04-17) | 2026-04-17 | Mastery loop + feedback UUID casts + fake settings removed |
| [v0.11](#v011--admin-api-500-fixes--topic-lock--counselor-mode--redis-diag-2026-04-17) | 2026-04-17 | Admin API 500 fixes + topic lock + counselor gate + Redis diag |
| [v0.10](#v010--admin-dashboard--8-api-endpoints--8-frontend-sections-2026-04-16) | 2026-04-16 | Admin dashboard — 8 API endpoints + 8 frontend sections |
| [v0.9](#v09--feedback-loop--4-dim-judge--settings--5-eval-fixes-2026-04-14) | 2026-04-14 | Feedback loop + 4-dim Judge + /settings + 5 eval fixes |
| [v0.8](#v08--ui-overhaul--topic-tree--quick-doubt-fab--mobile-2026-04-13) | 2026-04-13 | UI overhaul — Topic Tree + Quick Doubt FAB + mobile responsive |
| [v0.7](#v07--multi-subject-rollout--critical-keyerror-fix-2026-04-13) | 2026-04-13 | Multi-subject rollout — Chemistry + Maths + critical KeyError fix |
| [v0.6](#v06--smart-onboarding--auth-refresh--cold-start-polish-2026-04-04--06) | 2026-04-04 – 06 | Smart onboarding + auth refresh + cold-start polish + intents |
| [v0.5](#v05--poc-consolidation--audit-fixes-2026-04-04) | 2026-04-04 | POC consolidation commit + 5 audit fixes |
| [v0.4](#v04--progressive-disclosure--therapist-hijack-fix-2026-03-31) | 2026-03-31 | Progressive disclosure gate + therapist hijack fix |
| [v0.3](#v03--analytics-dashboard-pro-max--nuclear-l3--latex-sanitizer-2026-03-30) | 2026-03-30 | Analytics Bento Box + Confidence Meter + nuclear L3 + LaTeX sanitizer |
| [v0.2](#v02--glassmorphic-ui-overhaul--taxonomy-api-2026-03-22) | 2026-03-22 | Glassmorphic UI overhaul + Taxonomy API + syllabus selector |
| [v0.1](#v01--initial-commit--render--vercel-deployment-2026-03-17) | 2026-03-17 | Initial commit + Render + Vercel deployment + OpenAI embeddings |

---

## v0.18 — Enterprise UI Phase 1 — design tokens + UI primitives (2026-04-18)

**Status:** shipped (Phase 1 of 6-phase enterprise UI overhaul)
**Commits:** *(staged — commit by user)*

### What shipped
Foundation layer for the enterprise-grade UI overhaul. No user-visible change yet — this phase lays the token system + component primitives that phases 2–6 compose with.

- **`frontend/web/tailwind.config.ts`** (NEW) — token-based theme using HSL CSS variables. Colors: `background`, `foreground`, `primary`, `muted`, `border`, `ring`, `card`, `popover`, `success`, `warning`, `destructive`, plus subject accents (`physics`, `chemistry`, `maths`). Custom shadows: `soft`, `elevated`, `floating`. Custom keyframes: `accordion-down/up`, `fade-in`, `fade-up`. `darkMode: 'class'` scaffolded (not wired — locked decision #1).
- **`frontend/web/app/globals.css`** (MODIFIED) — full token system in `:root` (light). Dark tokens scaffolded in `.dark` (deferred). Radius: 0.75rem (12px). Custom scrollbars, focus rings, selection styles. KaTeX + mobile utilities preserved.
- **`frontend/web/lib/utils.ts`** (NEW) — `cn()` helper (clsx + tailwind-merge), `formatNumber()`, `formatPercent()`, `getInitials()`.
- **`frontend/web/components/ui/*`** (NEW, 18 primitives copied from shadcn/ui pattern — we own them, no CLI dep):
  - `button.tsx` — CVA with 6 variants × 4 sizes + `loading` prop with Loader2 spinner
  - `input.tsx`, `textarea.tsx`, `label.tsx`
  - `card.tsx` (Card/Header/Title/Description/Content/Footer)
  - `badge.tsx` (6 variants: default/secondary/success/warning/destructive/outline)
  - `avatar.tsx` (Radix Avatar + Image + Fallback)
  - `dialog.tsx` (full Radix Dialog)
  - `dropdown-menu.tsx` (full Radix DropdownMenu with checkbox/radio/sub)
  - `tooltip.tsx` (Radix Tooltip)
  - `select.tsx` (Radix Select + scroll buttons)
  - `switch.tsx` (Radix Switch)
  - `tabs.tsx` (Radix Tabs)
  - `separator.tsx`, `progress.tsx`, `scroll-area.tsx`, `skeleton.tsx`
  - `sonner.tsx` (toast wrapper, hard-coded light theme until dark lands)
- **`frontend/web/app/layout.tsx`** (MODIFIED) — wraps app in `<TooltipProvider delayDuration={200}>` and mounts `<Toaster />` globally.
- **Deps added** (one batch): `@radix-ui/react-{avatar,dialog,dropdown-menu,label,progress,scroll-area,select,separator,switch,tabs,tooltip}`, `class-variance-authority`, `clsx`, `tailwind-merge`, `sonner`, `date-fns`, `react-hook-form`, `zod`, `@hookform/resolvers`.

### Locked decisions driving Phase 1 scope
1. **Dark mode deferred.** Tokens use CSS variables so enabling dark later is a 1-file change. `.dark` block exists in `globals.css`, `darkMode: 'class'` set in Tailwind config, but no toggle in UI.
2. **Shadcn-pattern (not CLI).** Primitives live in our repo; we control them; no `shadcn-ui` npm dep.
3. **Ship-all-6-phases policy.** Commit after each phase for review safety, but continue without demo pause.

### Verification
- `cd frontend/web && npx tsc --noEmit` → 0 errors
- `cd frontend/web && npm run build` → ✓ Compiled successfully in 2.6s, all 13 routes static-prerendered
- No existing pages touched — Phase 2 onward will migrate pages to the new primitives.

### What's next (Phase 2)
`AppShell` + global top bar + left sidebar + theme toggle scaffold + command palette scaffold. Migrates every logged-in page onto the new shell.

---

## v0.17 — Version history doc + hard no-commit rule (2026-04-19)

**Status:** shipped
**Commits:** *(staged — commit by user)*

### What shipped
- **`docs/version_history.md`** — single source of truth for every version shipped (v0.1 → this). Reverse-chronological, jump-link index, full entry per version, blank template at the bottom for future sessions.
- **`CLAUDE.md` updates** — first-read rule now explicitly requires `version_history.md` + `session_log.md` at the top of every new session. New "Version History Rule" section defines semver-lite increments and mandates that every commit appends a new version entry before committing.
- **`RULES.md` #7 strengthened** — Claude **never** runs `git add`, `git commit`, `git push`, `git reset`, or `git rebase`. Even when the user says "commit this", Claude's job is to print the exact commands for the user to copy and run themselves. Read-only git stays allowed. Rationale written into the rule.
- **`CLAUDE.md` critical-rules summary** aligned with strengthened RULES.md #7.
- **Retrospective deepened** — version entries regranulated from 15 to 17 (previous lumped March 17–30 into v0.1; now split into v0.1, v0.2, v0.3, v0.4 to capture each shipped improvement).

### Bugs fixed (root cause → symptom)
- **Project history scattered across 4 files** — had to hunt through git log, session_log.md, decisions.md, MEMORY.md + 6 eval reports to understand what shipped. Fixed with single version_history.md.
- **No enforcement of history write-ups** — easy to ship a commit without logging it for future Claude instances. Fixed with CLAUDE.md rule (auto-read).

### Metrics / evidence
- 17 version entries backfilled, spanning 2026-03-17 → 2026-04-19 (~5 weeks of work).
- All 54 commit hashes in git referenced across the 17 entries.
- CLAUDE.md: 5 references to `version_history.md`.
- RULES.md #7 uses "never, even when instructed" language — closes the prior loophole.

### Known issues carried forward
- Not enforced via CI (would need pre-commit hook or GitHub action).
- `session_log.md`, `decisions.md`, `bugs.md` stay as detail stores — not consolidated.

### Files touched
- `docs/version_history.md` — new (this file)
- `CLAUDE.md` — first-read, Version History Rule, auto-read, critical rule #1
- `RULES.md` — #7 expanded from one-liner to full rule with rationale

---

## v0.16 — Preemptive 14-fix hardening batch (2026-04-19)

**Status:** shipped
**Commits:** `8e99d53`

### What shipped
Proactive audit (3 parallel trace agents) surfaced 14 issues in the same class as the v0.15 context-loss bug. All fixed in one batch before they hit users.

- **HIGH:**
  - `image_url` on `/doubt/hint` was silently dropped (`HintRequest` didn't declare field). Added + OCR fallback when no text reply.
  - `student_confidence` now plumbs through to `_genome_update_task` on hint-path resolutions (was only on /doubt/ask path — confidence-weighted mastery broken for ~50% of resolutions).
  - Submit-button double-fire guard: synchronous ref-based re-entry lock (Enter+click or fast double-click previously slipped 2 requests through).
  - Optimistic student bubble no longer orphaned on API error — now shows inline "⚠️ I couldn't send that — please try again" tutor bubble.
- **MEDIUM:**
  - L0 no-student-input injects explicit "no-attempt-yet" banner into `response_assessment` so `HINT_LEVEL_1` stops hallucinating validators on empty input.
  - `/session/end` checks `hint_level > 3` before marking blocks `solved=True`.
  - Intent classifier few-shots for numeric-only replies (`"42"`, `"a=2.5"`, `"x=3"`) with active_block → continuation.
  - Conversational pre-filter (`"idk"`, `"maybe"`, `"yes"`) gated on `has_active_block=False`.
  - `jump_to_full` branch in frontend now sets `give_up_flag=true`.
- **LOW:**
  - `EXPLANATION_PROMPT` "default" tone has explicit forbidden-opener list (`"Great question"`, `"Let me explain"`, etc.) instead of soft guidance.
  - Hinglish few-shots in intent classifier: `"haan samajh gaya"`, `"nahi samjha"`, `"stress ho raha hai"`.
  - `locked_topic` normalization: strip whitespace, empty → None.

### Bugs fixed (root cause → symptom)
- **Pydantic model missing `image_url` on HintRequest** — frontend sent it on 3 code paths; Pydantic silently dropped. Student image uploads during hint replies invisible to engine.
- **`student_confidence` only on `/doubt/ask` path** — asymmetric mastery modifier: ~50% of resolutions skipped confidence weighting.
- **`setState` async race on submit** — rapid Enter+click both entered `handleSend()` before the guard because `setIsLoading(true)` doesn't fire until next render. Fixed with synchronous `useRef` lock.

### Metrics / evidence
- E2E verification batch: **10/10 checks pass**, including regression checks for v0.15 fixes.
- `npx tsc --noEmit` clean, backend imports clean. No DB migrations required.

### Files touched
`app/api/doubt.py`, `app/api/session.py`, `app/services/doubt/engine.py`, `app/services/doubt/prompts.py`, `frontend/web/app/doubt/page.tsx`, `frontend/web/components/ChatInput.tsx`

---

## v0.15 — Context-loss fix + per-topic chat isolation + hint gate (2026-04-18)

**Status:** shipped
**Commits:** `48559c7`, `ba475e6`, `fba16d2`

### What shipped
- **Context-loss fix (critical):** student replies like *"second derivative of f(x)"* now reach the response analyzer. Previously the frontend sent all replies to `/doubt/ask`; the intent classifier mis-routed them as `explanation` → no session, no history, no topic_lock. 3-layer fix: (A1) frontend routes continuations to `/doubt/hint`; (A2) backend skips explanation-trigger pre-filter when `has_active_block=True`; (A3) safety net in `/doubt/ask`.
- **Per-topic chat isolation:** each (subject, chapter, topic) tuple now gets its own `study_session_id` in localStorage. Navigating to a new topic produces a fresh chat. `rebuildMessages()` filters by `topicLock`. `/session/resume` accepts optional `topic` for server-side filter.
- **Hint L1→L2 no-input gate:** clicking "Give me a hint" without typing used to advance the hint level, where the LLM hallucinated a "Right —" validation of a non-existent answer and abandoned its own previous question. Now the backend regex-extracts the AI's last `?` and returns a deterministic re-prompt.

### Bugs fixed (root cause → symptom)
- **Frontend always POSTed to `/doubt/ask`** — short replies classified as `explanation` → no DB writes → "0 doubts asked" despite 193-minute sessions.
- **Validator rotation fires on `{student_response}="(no response provided)"`** — L2 prompt opened with "Right —" hallucinating validation of non-existent answer.
- **Global localStorage session ID** — chat bled across topics.

### Metrics / evidence
- 17/18 topic-isolation E2E checks pass (1 "failure" was test-design issue).
- Context-loss replay: `"second derivative of f(x)"` now produces validated L1, `doubt_count` increments to 1.

### Files touched
`frontend/web/app/doubt/page.tsx`, `app/services/doubt/engine.py`, `app/api/doubt.py`, `app/api/session.py`

---

## v0.14 — Socratic quality v2 → v3 (7.9 → 8.9 / 10) (2026-04-17)

**Status:** shipped
**Commits:** `0614ec0`

### What shipped
Four targeted fixes after 83-scenario autonomous eval. See `scripts/eval_reports/comprehensive_test_2026-04-17-v2.md`.

- **FIX 8 — L0 single-question post-gen:** cheap LLM rewrite when 2+ `?` detected.
- **FIX 9 — Persona-aware `EXPLANATION_PROMPT`:** 5 tone branches (stressed, frustrated, overconfident, slow_learner, complimentary, default).
- **FIX 10 — Meta intent sub-classes:** `meta_identity`, `meta_pricing`, `meta_competitor` + 14 new few-shots → honest canned responses.
- **FIX 11 — Subject-switch detection** in `get_hint()` → graceful redirect.
- **FIX 12 — "2+2" routing:** basic arithmetic now `subject_doubt` instead of out-of-scope.
- **Latent bug caught:** `doubt.py` non-subject-intents list didn't include new `meta_*` classes — classifier routed correctly but API layer dropped them. Patched.

### Metrics / evidence (83-test comprehensive eval)
| Category | v1 | v3 |
|---|---|---|
| Overall | **7.9** | **8.9** |
| Persona/tone | 6.0 | **8.5** |
| Knowledge boundary | 6.5 | **8.5** |
| Maths | 9.0 | 9.5 |
- Validator distinct openers: 1 → **11**
- Wrong-answer flags: 0 → **22**
- Multi-Q at L0: 27 (33%) → **11 (13%)**
- Meta honest redirects: 0/4 → **4/4**
- Crashes across 200+ LLM calls: **0**

### Files touched
`app/services/doubt/prompts.py`, `app/services/doubt/engine.py`, `app/api/doubt.py`

---

## v0.13 — Socratic quality v1 → v2 (5.5 → 8.0 / 10) (2026-04-17)

**Status:** shipped
**Commits:** `fa26380`

### What shipped
7 prompt + engine fixes after 12-scenario Socratic eval showed 4 critical FAILs. See `scripts/eval_reports/conversation_quality_2026-04-17-v2.md`.

- Removed "No worries" hardcoded opener.
- Added `{response_assessment}` injection into HINT_LEVEL_1 + HINT_LEVEL_2.
- New `answer_check` field in `STUDENT_RESPONSE_ANALYSIS_PROMPT` (correct/wrong/partial/not_an_answer) + `student_value` + `correct_value`.
- **Upgraded analyzer to quality model** (gpt-4.1-mini) — cheap model was getting JEE-level math wrong.
- Topic lock **prepended** (not appended) to system prompt.
- Concrete scenario anchoring for mastery < 30%.
- Banned-opener list + 6 rotation styles in TUTOR_SYSTEM_PROMPT.
- L3 CORRECT-answer path (validates + provides derivation instead of forced-attempt scold).
- L3 WRONG-answer path (flags specific value).
- Topic-lock short-circuit via gpt-4o-mini pre-check.
- **Latent bug fixed:** `body.student_attempt` on `/doubt/hint` was only logged, never plumbed into `engine.get_hint(student_response=...)`. Response analyzer was **permanently disabled in production** until this single-line coalesce shipped.

### Metrics / evidence (12-test Socratic eval)
| | v1 | v2 |
|---|---|---|
| Score | **5.5 / 10** | **8.0 / 10** |
| FAIL / PASS | 4 / 5 | 0 / 9 |
| Banned openers | 1 | 0 |
| Topic lock redirects | 0/1 | 1/1 |
| Wrong-answer flagged | 0/1 | 1/1 |
| Validator diversity | 1 opener | 4 openers |

### Files touched
`app/services/doubt/prompts.py`, `app/services/doubt/engine.py`, `app/api/doubt.py`

---

## v0.12 — Mastery loop fix + feedback UUID + fake settings removed (2026-04-17)

**Status:** shipped
**Commits:** `85b766a`

### What shipped
- **Mastery feedback loop — critical bug fix.** `_genome_update_task` only fired when student clicked "Got it!" (`resolved=True`). Students rarely clicked → **83 of 84 `concept_mastery` rows stuck at 0**. Fixed by firing `_genome_update_task(give_up_flag=True)` on abandoned blocks (hint_level ≥ 1). `/session/end` now routes through `_close_doubt_block`.
- **Feedback endpoint hardened** — explicit `uuid.UUID()` casts for `student_id` + `doubt_session_id` + logger.info/exception on every attempt.
- **Fake Preferences tab removed** from settings page — 3 toggles (`show_hint_badges`, `show_confidence_meter`, `compact_messages`) had zero consumers. 130 lines of dead UI deleted.

### Bugs fixed (root cause → symptom)
- **Mastery updates gated on `resolved=True` only** — 98% of doubt_blocks produced zero mastery signal; "AI that learns your weaknesses" value prop was a static prompt.
- **asyncpg UUID silent coercion** — feedback insert sometimes failed silently because `student_id` string wasn't being auto-cast.

### Files touched
`app/api/doubt.py`, `app/api/session.py`, `app/api/feedback.py`, `frontend/web/app/settings/page.tsx`, `frontend/web/app/doubt/page.tsx`

---

## v0.11 — Admin API 500 fixes + topic lock + counselor mode + Redis diag (2026-04-17)

**Status:** shipped
**Commits:** `b9d9015`, `2d4151c`, `a796d24`, `a97250c`

### What shipped
- **6 admin API endpoints that returned HTTP 500** — all caused by `doubt_blocks.subject` column not existing (schema drift). Rewrote queries to use `doubt_sessions.subject`. 3/10 working → **10/10**.
- **Admin `/admin` page 404 fix** — auth guard redirected non-admins to dead `/dashboard` route. Added "access not configured" screen with ADMIN_EMAILS instructions.
- **Admin home shortcut card** on `/` (admins only, checks `/admin/is_admin`).
- **`is_admin` endpoint Supabase JWT email fallback** — works even when `students.email` is NULL (6 of 13 pre-migration students).
- **Topic lock persistence** — `locked_topic` stored in `stored_analysis` during `start_session()` and re-applied in `get_hint()`. Previously lost after first turn.
- **Counselor mode safeguard** — `_DISTRESS_KEYWORDS` gate (23 explicit phrases) filters academic confusion from genuine distress. `STUDENT_RESPONSE_ANALYSIS_PROMPT` updated to distinguish `confused` vs `frustrated`.
- **Redis diagnostic fix** — `request.app.state.redis` AttributeError replaced with fresh `redis.asyncio.from_url()` per-call.

### Metrics / evidence
- 8 admin endpoints: 200 OK after fix (was 500 for 6).
- Topic lock verified: off-topic question redirects correctly.
- Counselor mode verified: "no idea" gets academic nudge, not therapy.

### Files touched
`app/api/admin.py`, `app/services/doubt/engine.py`, `app/services/doubt/prompts.py`, `frontend/web/app/admin/page.tsx`, `frontend/web/app/page.tsx`

---

## v0.10 — Admin dashboard — 8 API endpoints + 8 frontend sections (2026-04-16)

**Status:** shipped (with admin API bugs — fixed in v0.11)
**Commits:** `23f531b`

### What shipped
- **8-section admin dashboard** at `/admin`: Platform Health · Conv Quality · Response Quality · System Perf · User Feedback · Knowledge Base · Student Insights · Diagnostics.
- **10 new backend endpoints**: `/admin/platform-health`, `/conversation-quality`, `/response-quality`, `/system-performance`, `/user-feedback`, `/knowledge-base`, `/student-insights`, `/diagnostics`, `/quality-digest`, `/quality-report`.
- **Email-based admin auth:** `admin_emails` env var replaces `admin_student_id`.
- **Continuous per-turn quality scoring:** `conversation_turn_quality` table + `score_turn()` async service (gpt-4o-mini). Fires after every hint at L1–L2.
- **Fixed `judge_evaluations` empty:** role mismatch in `_run_judge_for_session()` (expected `user`/`assistant`, history has `student`/`tutor`).
- **Fixed `response_feedback` ON CONFLICT:** migration v15 adds explicit UNIQUE constraint.
- **Socratic quality fixes (first pass):** RESPONSE ASSESSMENT block in HINT_LEVEL_1/2, concrete anchoring, response variety, SOLUTION_SEEKER preamble.
- **Topic context lock** via `TOPIC_LOCK_ADDENDUM` (bugs remained — fixed in v0.11, v0.13).

### Known issues (fixed in later versions)
- 6 admin API endpoints returning 500 (→ v0.11)
- `/admin` 404 for non-admins (→ v0.11)
- Topic lock not persisted to hints (→ v0.11)

### Files touched
`app/api/admin.py` (rewrite), `app/services/eval/turn_scorer.py` (new), `app/api/session.py`, `scripts/migrate_v15_feedback_constraint.sql`, `frontend/web/app/admin/page.tsx` (900-line rewrite)

---

## v0.9 — Feedback loop + 4-dim Judge + /settings + 5 eval fixes (2026-04-14)

**Status:** shipped
**Commits:** `c1d0eed`, `b261d90`, `d285714`, `7fa2b24`

### What shipped
- **Thumbs up/down UI** on every AI message + `handleFeedback` optimistic update.
- **4-dimension Judge LLM** (`evaluate_response`) scoring pedagogical, factual, context_relevance, hint_appropriateness. Fires async after `/session/end`.
- **`session_metrics` telemetry** — RAG latency, agent steps, retrieval similarity, chunk count per session.
- **`/settings` page** — 4-tab flow (Profile / My Analytics / System Analytics / Preferences). System Analytics admin-gated.
- **Multi-subject onboarding** — Physics + Chemistry + Maths marks, 36 topic chips, explicit learning preference, priority_subject.
- **Offline RAGAS eval script** (`scripts/eval_ragas.py`) + 20-question golden dataset.
- **5 critical eval fixes:** Chemistry/Maths scope detection (`_is_in_scope`), retrieval latency tuning, Chem/Maths concept seeding.

### Bugs fixed
- **`_is_in_scope` wrongly flagged Chem/Maths as out-of-scope** — was Physics-only. Fixed with subject-aware keywords.
- **Physics retrieval avg 5s, max 12.7s** — tuned via concept seeding + tool pruning.

### Files touched
`scripts/migrate_v12_feedback.sql`, `app/api/feedback.py` (new), `app/services/eval/judge.py`, `frontend/web/app/settings/page.tsx` (new), `scripts/eval_ragas.py` (new)

---

## v0.8 — UI overhaul — Topic Tree + Quick Doubt FAB + mobile (2026-04-13)

**Status:** shipped
**Commits:** `9dc29e9`, `12de4e7`

### What shipped
- **Topic Tree sidebar** with Subject tabs (Phy/Chem/Maths), Chapter accordion with mastery bars, Topic row with Doubt/Practice/Mock icons.
- **Quick Doubt FAB** — floating action button, 56px, "Quick Doubt" label fades after 3s, bottom-sheet textarea.
- **Mobile responsive** — redesigned sidebar (220px desktop, mobile hamburger drawer via Framer Motion).
- **Subject mastery dashboard** — 3 subject cards on `/` home with % mastery + color bars.
- **Exam countdown card** — JEE April countdown from `target_year`.
- **Topic-scoped doubt page** — URL params `?subject=X&chapter=Y&topic=Z` → `topicLock` pinned.
- **Socratic engine conversational flow fixes** — conversational tokens, explanation triggers.

### Files touched
`frontend/web/lib/syllabus.ts` (new — STATIC_SYLLABUS 62 chapters, 300+ topics), `frontend/web/components/TopicTree.tsx` (new), `frontend/web/components/QuickDoubtFAB.tsx` (new), `frontend/web/components/Sidebar.tsx` (rewrite), `frontend/web/app/doubt/page.tsx`, `app/services/doubt/engine.py`

---

## v0.7 — Multi-subject rollout + critical KeyError fix (2026-04-13)

**Status:** shipped
**Commits:** `7f77032`, `fe00a61`

### What shipped
- **NCERT Chemistry + Maths knowledge chunks** ingested. Total: **14,384 knowledge chunks** (Physics 10,505 + Chemistry 3,138 + Maths 1,426 + 20 JEE PYQ seed).
- **`SUPPORTED_SUBJECTS = ("Physics", "Chemistry", "Maths")`** constant in `prompts.py`.
- **8 Physics-only hardcoded strings replaced** in prompts with `{subject}` parameter. `physics_doubt` → `subject_doubt` (backward-compat alias kept).
- **Subject-aware MCQ generation** in mock API.
- **`get_subject_context()` + `build_system_prompt()`** now subject-aware.

### Bugs fixed (root cause → symptom)
- **CRITICAL: `build_system_prompt()` silent KeyError for ALL students ALL subjects** — unescaped LaTeX braces `{u^2 \sin 2θ}` in `CUSTOMIZATION_PROMPT` line 643 were parsed as `.format()` placeholders. Silently crashed the policy engine, falling back to unpersonalized prompt for every single student across every subject. Fixed with `{{u^2 …}}` escaping. This bug had been live in production for days undetected.

### Files touched
`scripts/ingest_chem_maths.py` (new), `scripts/ingest_maths_pdf.py` (new — 29 NCERT PDFs), `scripts/ingest_jee_pyq.py`, `app/services/doubt/prompts.py`, `app/services/doubt/engine.py`

---

## v0.6 — Smart onboarding + auth refresh + cold-start polish (2026-04-04 – 06)

**Status:** shipped
**Commits:** `c84d131`, `a05955c`, `e06b7b1`, `40a446c`, `56702d1`, `2cfc847`, `c865d62`, `a6498da`, `e8f8e41`, `350f267`, `3220b3d`, `3a88061`

### What shipped
- **4-step onboarding flow** — class level + marks (Physics + Chem + Maths), 36 topic chips (easy/hard), study hours + exam target, persona summary card.
- **GPT-4.1-mini persona builder** — `POST /onboarding/submit` synthesizes a JSONB persona with `scaffolding_level`, `preferred_style`, `weak_concepts`, `persona_summary`.
- **Persona evolution every 5 sessions** — `maybe_compress_profile()` rewrites `persona_summary` using last 10 session summaries + top 10 mastery scores. Staleness warning if > 15 sessions old.
- **Auth refresh endpoint** — `POST /auth/refresh`, refresh token in localStorage, auto-refresh on 401 via `tryRefresh()`.
- **Cold-start retry** — `pingBackend()` on mount for login/signup/onboarding (Render cold start can take 30s).
- **Base64 image upload** — replaced Supabase storage with `FileReader.readAsDataURL()` — no Supabase env vars needed on Vercel.
- **Socratic engine conversational + explanation intents** — `_CONVERSATIONAL_TOKENS` + `_EXPLANATION_TRIGGERS` + `EXPLANATION_PROMPT` + `CONVERSATIONAL_RESPONSE`.

### Bugs fixed
- **"Invalid or expired token" on onboarding** — token validated twice, second validation hit stale cache. Fixed with token refresh flow.
- **Render proxy 30s timeout on continuation hints** — `/doubt/ask/stream` now yields keepalive immediately before awaiting `get_hint()`.
- **`_openai` vs `_client` AttributeError** in onboarding — corrected engine attribute name.
- **`supabase` missing from requirements.txt** — Render deploy failed. Fixed.

### Files touched
`app/api/onboarding.py` (new), `app/api/auth.py` (refresh endpoint), `scripts/migrate_v8_onboarding.sql`, `v9_persona_staleness.sql`, `v10_rls.sql`, `frontend/web/app/onboarding/page.tsx` (new), `frontend/web/lib/api.ts`

---

## v0.5 — POC consolidation + audit fixes (2026-04-04)

**Status:** shipped
**Commits:** `961d9b6`, `dc3f4a3`

### What shipped
Massive consolidation commit covering Phases 2–5 from the PTB framework plus an audit round:

- **Feature 12: Memory System** — 3-layer (Redis hot context + Postgres compressed profile + top 5 weak concepts). `build_context_bundle()`, `format_context_for_prompt()`, `update_error_fingerprint()`, `update_forgetting_rate()`, `get_persona_profile()`, `update_persona_profile()`, `infer_scaffolding_level()`. Session summarizer always blocking (Rule 3).
- **Phase 2: Policy Engine** — `PedagogyConfig` dataclass, `select_pedagogy(persona_profile, topic, hint_level)`, `CUSTOMIZATION_PROMPT` + `PERSONALIZATION_PROMPT` + `build_system_prompt()` + `render_personalization()`.
- **Phase 3: Misconception Detection** — 30-entry `MISCONCEPTION_LIBRARY` (Physics + Chemistry + Maths), `check_for_misconception()`, 1.5× mastery penalty.
- **Phase 4: Golden Dataset + Judge LLM** — 50 golden triplets, `score_response()` gpt-4.1-mini temp=0, `log_scaffolding_score()`.
- **Phase 5: Eval Dashboard + Regression Gate** — `GET /admin/metrics`, basic admin page (superseded by v0.10), `scripts/regression_gate.py`.
- **Migrations v4 → v11** applied.
- **5 audit fixes:** judge blind spot, cache persona leak, admin auth, streaming OOS prefix, Vercel SSG crash.

### Bugs fixed (root cause → symptom)
- **Cache persona leak** — student-specific persona leaked into cached responses served to other students. Fixed by stripping persona before cache key.
- **Judge blind spot** — judge never fired for quick doubts. Fixed by adding trigger in `/session/end`.
- **Vercel SSG crash** — `useSearchParams` without Suspense caused build failure. Fixed by wrapping in `<Suspense>`.

### Files touched
`app/services/memory/context.py`, `summarizer.py` (new), `app/services/policy/engine.py` (new), `app/services/doubt/misconceptions.py` (new, 30 entries), `app/services/eval/judge.py`, `logger.py` (new), migrations v4–v11, `app/api/admin.py` v0

---

## v0.4 — Progressive disclosure + therapist hijack fix (2026-03-31)

**Status:** shipped
**Commits:** `9b05e2d`, `d0ddc4e`

### What shipped
- **Blocked early full-solution bypass** — students could previously request the full solution before exhausting hints. Added progressive-disclosure gate: `jump_to_full` is only honored if `current_level >= 3`.
- **Therapist hijack fix at forced attempt** — emotional analysis was still running at L3 and could switch mentor mode to COUNSELOR, blocking the full solution. Added hard gate at `current_level < 3`.
- **LaTeX block isolation** — fixed `$$...$$` display-math rendering when blocks contained inner newlines (breaks KaTeX).
- **Frontend trust backend `is_full_solution`** — previously frontend hardcoded `is_full_solution=true`; now reads from the backend response.

### Bugs fixed (root cause → symptom)
- **Early full-solution bypass** — students at L0 could type "show solution" and skip all hints. Value-prop violated.
- **Therapist hijack** — L3 forced-attempt could flip to COUNSELOR mode if the student's text looked emotional, derailing the forced-attempt pedagogy.
- **LaTeX $$ block newline bug** — RAG chunks sometimes injected blank lines inside display math, breaking the KaTeX renderer silently.

### Files touched
`app/services/doubt/engine.py`, `app/services/doubt/prompts.py`, `frontend/web/app/doubt/page.tsx`

---

## v0.3 — Analytics Bento Box + Confidence Meter + nuclear L3 + LaTeX sanitizer (2026-03-30)

**Status:** shipped
**Commits:** `8cb6d38`, `ac0de45`, `3cc54d0`, `f34f817`, `83a0ece`, `cb037c4`

### What shipped
- **Pro Max Bento Box redesign** of Analytics Dashboard (`/progress` page) — multi-card layout with mastery trends, recent sessions, weakest concepts.
- **Pro Max Confidence Meter intercept** at forced-attempt — student must pick low/medium/high confidence before submitting final answer (signal for mastery update modifier).
- **Nuclear forced-attempt override** at hint_level 3 — `SYSTEM_PROMPT_FORCED_ATTEMPT` replaces `TUTOR_SYSTEM_PROMPT` entirely; RAG + analysis starved; response hard-gated to 2 sentences.
- **LaTeX sanitizer (`_sanitize_latex`)** — runs on every LLM response (Rule 6). Fixes `$$` delimiter placement, blank lines in math blocks, triple-newlines globally.
- **MEMORY.md updated** with prompt engineering constraints.

### Bugs fixed
- **Solution leakage at forced attempt** — full RAG context + tutor persona meant LLM could still teach. Fixed with nuclear override (swap prompt, clear RAG, clear analysis).
- **KaTeX renderer broken on some responses** — no sanitation for common LLM LaTeX mistakes. Added sanitizer.

### Files touched
`app/services/doubt/engine.py` (nuclear override + `_sanitize_latex`), `app/services/doubt/prompts.py` (`SYSTEM_PROMPT_FORCED_ATTEMPT`), `frontend/web/components/ConfidenceMeter.tsx` (new), `frontend/web/app/progress/page.tsx` (Bento Box redesign), `MEMORY.md`

---

## v0.2 — Glassmorphic UI overhaul + Taxonomy API + syllabus selector (2026-03-22)

**Status:** shipped
**Commits:** `1b8172d`, `f4e56dd`, `1ed50f0`, `78dd0be`

### What shipped
- **Chat interface overhaul** to modern glassmorphic design — light theme, frosted glass cards, refined typography hierarchy.
- **Typography + contrast fixes** — restored readable contrast ratios, applied correct light glassmorphic card styles.
- **Taxonomy API** (`GET /taxonomy`) — returns full JEE syllabus (subject → chapter → topic) from DB.
- **Syllabus selector UI** with **topic-lock wiring** — first version of topic-scoped sessions (foundation for v0.8 Topic Tree).
- **Vercel build fix** — wrapped `useSearchParams` in Suspense boundary.

### Files touched
`app/api/taxonomy.py` (new), `frontend/web/components/SyllabusSelector.tsx` (new), `frontend/web/app/doubt/page.tsx` (glassmorphic chat), `frontend/web/app/globals.css`

---

## v0.1 — Initial commit + Render + Vercel deployment (2026-03-17)

**Status:** shipped
**Commits:** `395a56d`, `c962f55`, `aefa49a`, `00e8e4a`, `68ae326`, `9436aa3`, `17cb79b`, `f84639c`, `92e1911`

### What shipped
- **Initial UpMyRank AI tutoring platform POC** — full Socratic engine with L0 → L1 → L2 → L3 → full-solution hint ladder.
- **Agentic RAG** — 4 tools (`search_ncert`, `search_jee_problems`, `search_concepts`, `rerank_and_select`) with MAX_STEPS=3, gpt-4o-mini tool selection.
- **Doubt block + study session lifecycle** — `study_sessions → doubt_blocks → doubt_sessions` hierarchy.
- **Knowledge Genome** — concept-level EMA mastery tracking, weakest concepts, topic averages.
- **Atomic EMA mastery updates** — single SQL statement to prevent race conditions.
- **Robust concept matching for mastery** — 3-layer keyword fallback strategy.
- **Supabase JWT auth** + student profile storage.
- **OpenAI embeddings migration** — switched from sentence-transformers to OpenAI `text-embedding-3-small` (1536-dim).
- **Render deployment config** — Dockerfile + requirements.txt + CORS setup.
- **Vercel deployment** — Next.js 14 frontend with TypeScript strict mode.
- **QA hardening** — input validation, OpenAI timeout, schema hardening, strict LaTeX prompt rules.
- **Multiple TypeScript build fixes for Vercel** — XAxis `interval={0}`, Radar Tooltip formatter, typed ValueType, preserveStartEnd.

### Bugs fixed during this phase
- **Recharts TypeScript errors** blocking Vercel build — XAxis `interval` prop type, Radar Tooltip formatter ValueType undefined. Fixed.
- **Build environment mismatch** — local build passed, Vercel failed. Resolved with explicit prop casts.

### Files touched
Initial POC scaffolding — `app/main.py`, `app/services/doubt/engine.py`, `app/services/rag/agent.py`, `scripts/setup_db.sql`, `frontend/web/app/doubt/page.tsx`, `frontend/web/app/progress/page.tsx`, `Dockerfile`, `requirements.txt`, and everything else under the initial commit tree.

---

## Entry template (copy this for every new version)

```markdown
## vX.Y — Short name (YYYY-MM-DD)

**Status:** shipped | partial | reverted
**Commits:** `abc1234`, `def5678`

### What shipped
- Bullet list of features, fixes, or refactors. Be specific — "added X endpoint"
  not "improved admin".

### Bugs fixed (root cause → symptom)
- **[Root cause]** — symptom observed. Fixed by [what].

### Metrics / evidence
- Hard numbers where applicable (eval scores, latency ms, row counts, etc.).

### Known issues carried forward
- Anything left open or deferred. Link to the next version that addresses it.

### Files touched
- Top 3–5 paths that changed most.
```

---

## References (supporting docs, not the source of truth)

- `docs/session_log.md` — tactical "what's half-done in this session" log
- `docs/decisions.md` — architectural decisions
- `docs/bugs.md` — active bug tracker
- `MEMORY.md` — architecture + feature catalog snapshot
- `scripts/eval_reports/` — all eval runs with full metrics + worst/best turns
- `RULES.md` — 10 hard invariants (never violate)
