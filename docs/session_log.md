# Session Log — UpMyRank

<!-- Most recent session at top. Keep last 3 entries only. -->
<!-- Written by Claude at end of each session via /handoff command. -->

## Session 2026-04-20 — Dual-loop architecture (v0.20)

**Focus:** Ship Mode 1 (Study Path) + Mode 2 (Ask Anything) end-to-end per the approved dual-loop plan in `.claude/plans/sunny-marinating-wirth.md`. Sir approved via WhatsApp earlier today. Zero content-generation cost; reuse existing NCERT index + problems + jee_problems.

**Status:** DONE — backend + frontend + docs shipped; awaiting user commit.

**Changed files (v0.20):**
- **NEW** `app/api/study.py` — `GET /study/card` endpoint
- **NEW** `app/services/study/__init__.py` + `app/services/study/card_composer.py` — composes Notes (top-3 NCERT chunks via existing Retriever) / Practice (problems ILIKE topic) / PYQs (jee_problems ILIKE topic) / Mastery
- **NEW** `frontend/web/app/study/page.tsx` — navigator (subject → chapter → topic tree)
- **NEW** `frontend/web/app/study/[subject]/[chapter]/[topic]/page.tsx` — concept card
- **NEW** `docs/handoff_guide.md` — one-page "start here" for new devs / new Claude sessions
- **MODIFIED** `app/api/doubt.py` — topic-shift demotion in both `/ask` and `/ask/stream`; `_get_active_doubt_block` now JOINs `doubt_sessions` for subject
- **MODIFIED** `app/services/doubt/engine.py` — added public `classify_turn_topic()` wrapper
- **MODIFIED** `app/main.py` — registered `study.router`
- **MODIFIED** `frontend/web/app/page.tsx` — home now has two primary CTAs (Study Path + Ask Anything) + 3 secondary (Practice / Mock / Progress)
- **MODIFIED** `frontend/web/components/AppShell.tsx` — primary nav now includes Study Path + Ask Anything
- **MODIFIED** `docs/version_history.md`, `docs/session_log.md` (this file), `MEMORY.md`

**Current system state:**
- Backend: all routes live locally. `GET /study/card` verified returning populated JSON with NCERT chunks.
- Frontend: `npx tsc --noEmit` 0 errors; `npm run build` ✓ 15 static routes; preview E2E green on Home → Study Path → Concept Card (Kinematics > Projectile Motion).
- DB: NO migration in this version. All existing tables reused.

**In progress / half done:**
- None for v0.20 scope. Hand-curated top-30 Notes overrides is deferred post-beta.
- Admin Study Path panel is deferred.

**Cliff notes (non-obvious context):**
- Topic-shift detection is a **symmetric mirror** of FIX A3 (v0.15). A3 demoted subject_doubt → continuation for short ambiguous replies; v0.20 demotes continuation → subject_doubt when the message LOOKS like a new question AND classifies to a materially different topic/subject. Both guards coexist.
- Topic-shift check is **skipped when `body.topic_lock` is set** — Focus Mode (entered via Study Path "Ask about this" CTA) should not auto-segment.
- Concept cards are **computed, not stored**. No new DB table. Each render does DB + retriever queries; Redis 7-day cache is the next optimisation (not shipped yet — 30 beta users don't need it).
- `concept_mastery` mastery aggregation in composer does a graceful fallback if the `concepts` JOIN fails (the table name is slightly different across migration variants).
- `/doubt` free-form is already single-inbox without change: `topicSessionKey(null, null, null)` → `general__any__quick` — one key per student.

**Next session — read these files first:**
`docs/version_history.md` (v0.20 entry), `docs/handoff_guide.md`, `app/services/study/card_composer.py`, `app/api/doubt.py` (look at `_detect_topic_shift`).

**Next session — start here:**
Run the beta with 30 students. Monitor `topic_shift` log lines to validate classifier accuracy. If a student's Concept Card has <3 NCERT chunks (rare topic), they see the "Ask the tutor instead" deep link — verify that flow works end-to-end.

---

## Session 2026-04-19 — Enterprise UI Phases 2–6 (v0.19)

**Focus:** Ship AppShell + auth redesign + /doubt message actions + settings 6-tab + admin polish, as a single commit covering five of the six UI overhaul phases.

**Status:** DONE — shipped v0.18 (foundation) + v0.19 (phases 2–6); awaiting user push.

**Changed files:** see `docs/version_history.md` v0.18 and v0.19 entries; also `docs/ui_overhaul_changelog.md`.

**Current system state:**
- Frontend: 14 static routes build clean. AppShell wraps every logged-in page. New `/auth/forgot-password` route.
- Backend: untouched in this sprint. 34 routes confirmed healthy.
- DB: no migration.

**Cliff notes:**
- Dark mode tokens scaffolded in `globals.css` `.dark` block; toggle disabled with tooltip per locked decision #1.
- All "coming soon" features (Google OAuth, 2FA, email notifications, regenerate response) are visible + disabled with tooltips — no dead clicks.
- `/settings` is now 6 tabs; profile section has phone/timezone/language inputs but save is a toast no-op until `v16_student_profile.sql` ships.

---

## Session 2026-04-17 (cont.) — Admin Portal Access + Feedback Debugging + Home Shortcut

**Focus:** Fix `/admin` returning 404 in production; add admin shortcut to home page; debug empty `response_feedback` table.

**Status:** IN PROGRESS — code pushed, but Render env var `ADMIN_EMAILS` not yet set by user (blocks admin access).

**Changed files:**
- `frontend/web/app/admin/page.tsx` — auth guard: `router.replace('/dashboard')` (dead route) → `/`; `is_admin=false` now shows explicit "not configured" screen with Render instructions instead of silent redirect
- `frontend/web/app/page.tsx` — added `isAdmin` state + `GET /admin/is_admin` check on load; Admin Dashboard shortcut card renders at bottom of home page (admin-only)
- `frontend/web/app/doubt/page.tsx` — feedback `.catch` now logs `console.error('[feedback] POST /feedback/response failed:', err)` so failures are visible in devtools

**Current system state:**
- Backend: working on Render (all endpoints ✅ from previous session)
- Frontend: deployed to Vercel (commit `a796d24`), admin page shows "not configured" screen until `ADMIN_EMAILS` env var is set on Render
- DB: no migrations this session; all migrations v1–v15 applied

**In progress / half done:**
`response_feedback` still 0 rows — root cause unconfirmed. Error logging added; user needs to click thumbs in production and check browser devtools console for `[feedback]` error line to diagnose.

**Cliff notes (non-obvious context):**
- The original `/admin` 404 was NOT a missing route — `curl` returned 200. The page loaded, auth guard ran, `is_admin` returned `false` (because `ADMIN_EMAILS` not set on Render), and `router.replace('/dashboard')` redirected to a non-existent route which showed Next.js 404. Two bugs in one.
- `ADMIN_EMAILS` env var is set in local `.env` but was never added to Render environment variables. Backend `settings.admin_emails` defaults to `""` → `allowed = []` → `is_admin = False` for everyone. Fix: Render → upmyrank-api → Environment → `ADMIN_EMAILS=srivastava.ish@northeastern.edu`.
- `ADMIN_STUDENT_ID` (the old fallback) is also checked in `is_admin` endpoint — if it was already set on Render from the previous settings page era, admin access may already work after the redirect fix.
- `response_feedback` table has the `uq_feedback_per_turn` unique constraint from v15 AND an auto-named unique constraint from v12 (both on same columns). `ON CONFLICT` uses the first matching constraint — this is fine and not the bug.
- Admin shortcut on home page silently fails if `is_admin` API errors (`.catch(() => {})`) — card just doesn't show. Intentional: non-admins see no trace of admin features.

**Next session — read these files first:**
`frontend/web/app/admin/page.tsx`, `app/api/admin.py`

**Next session — start here:**
Set `ADMIN_EMAILS=srivastava.ish@northeastern.edu` in Render environment variables, redeploy, then verify `/admin` loads. Then open `/doubt` in production, click a thumbs button, check browser console for `[feedback]` error to diagnose the empty `response_feedback` table.

---
<!-- Older entries pruned 2026-04-20 (v0.20). See docs/version_history.md for the full chronology of every version shipped. -->
