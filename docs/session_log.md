# Session Log — UpMyRank

<!-- Most recent session at top. Keep last 3 entries only. -->
<!-- Written by Claude at end of each session via /handoff command. -->

## Session 2026-04-21 (cont.) — v0.20.3 hot patch: shorten topic-shift length floor

**Focus:** v0.20.2 deployed and fixed the `"what's the integral of sin(x²)?"` pivot, but real-prod usage by user immediately surfaced a sibling bug — `"what is molecule?"` (16 chars) still got refused by counselor because `_looks_like_new_question()` had a 20-char floor that short-circuited before the verb regex could match. User correctly called out the UX inconsistency.

**Status:** DONE — patch + extended synthetic test (now 3-pivot) + docs; awaiting user push.

**Changed files (v0.20.3):**
- **MODIFIED** `app/api/doubt.py` `_looks_like_new_question()` — verb-regex floor 20 → 12; symbol-only fallback floor stays 25.
- **MODIFIED** `scripts/synthetic_beta.py` `scenario_topic_shift()` — extended from 1-pivot to 3-pivot stress test (physics → math → "what is molecule?" chemistry). Permanent regression guard.
- **MODIFIED** `docs/version_history.md`, `docs/session_log.md` (this), `docs/bugs.md`.

**Cliff notes (non-obvious context):**
- The 20-char floor in v0.20.2 was a guess, not a measurement. The fix sets 12 = length of `"what is x?"` (shortest plausible new-question). Going lower risks treating raw replies like `"what?"` as a new doubt.
- Symbol-only fallback floor stays at 25 because notation without a verb is more ambiguous (a single fragment like `"x²"` shouldn't open a new block).
- The synthetic test would NOT have caught this in v0.20.2 because the only pivot tested was the long math one. Multi-pivot is now permanent.

**Next session — read these files first:**
`docs/bugs.md` (top entry — the length-floor failure mode), `app/api/doubt.py` (`_looks_like_new_question`), `scripts/synthetic_beta.py` (`scenario_topic_shift` — the 3-pivot guard).

**Next session — start here:**
1. Push v0.20.3 to Render.
2. Re-test the prod 3-pivot manually: physics → integral pivot → "what is molecule?" — all three should open separate blocks now.
3. Then proceed with the original v0.20.2 follow-ups (apply migration v16 if not done, beta with 30 students).

---

## Session 2026-04-21 — v0.20.2 patches + admin Study Path + synthetic tests

**Focus:** Fix two bugs surfaced by Render-prod logs (regex too narrow → topic-shift didn't fire on `"what's the integral…"`; Notes section duplicated chunks). Bundle with remaining v0.20 plan items: block-close drift backstop, manual `+ New doubt` lever, admin Study Path usage panel, hand-curated 5 seed concept-card overrides, profile-save wire-up, cold-start toast, synthetic LLM test harness.

**Status:** DONE — backend + frontend + tests + docs shipped; awaiting user push. Onboarding restyle deferred to v0.21 (works, low marginal pre-beta value).

**Changed files (v0.20.2):**
- **NEW** `app/services/study/__init__.py` already shipped in v0.20; no change here.
- **NEW** `scripts/concept_card_overrides.json` — 5 hand-polished concept cards (Projectile Motion, Newton's Laws, SHM, Chemical Bonding, Differentiation).
- **NEW** `scripts/migrate_v16_student_profile.sql` — phone/avatar_url/timezone/preferred_language; idempotent.
- **NEW** `scripts/synthetic_beta.py` — async test harness, 19 invariants per persona-run, validates topic-shift fix end-to-end.
- **MODIFIED** `app/api/doubt.py` — widened `_NEW_QUESTION_MARKERS` regex + math-symbol fallback; added `_reclassify_block_topic` block-close drift backstop; new `POST /doubt/new` endpoint; threaded `engine` kwarg through every `_genome_update_task` call site; topic-shift demote log now includes old_subject + old_topic.
- **MODIFIED** `app/services/study/card_composer.py` — Notes dedup (sha1 of normalised first-200-chars + heading-diversity); override-loader prefers hand-polished cards; **fixed path bug** (`parents[3]` not `parents[2]`).
- **MODIFIED** `app/api/study.py` — logs `study_card_view` event into `session_events` for admin panel.
- **MODIFIED** `app/api/student.py` — new `PATCH /student/{student_id}` with graceful schema-drift (returns `updated`/`ignored` lists).
- **MODIFIED** `app/api/admin.py` — new `GET /admin/study-path` endpoint.
- **MODIFIED** `frontend/web/lib/api.ts` — new `apiPatch` helper + 8s cold-start toast (lazy sonner import).
- **MODIFIED** `frontend/web/app/doubt/page.tsx` — "+ New doubt" button in chat header; `handleStartNewDoubt` calls `/doubt/new`.
- **MODIFIED** `frontend/web/app/settings/page.tsx` — Profile tab `handleSave()` now real-PATCH to backend with success/warning/error toast variants.
- **MODIFIED** `frontend/web/app/admin/page.tsx` — new "Study Path" section (StatCards + AreaChart + sortable table + CSV export).
- **MODIFIED** `docs/version_history.md`, `docs/session_log.md` (this), `docs/handoff_guide.md` (TBD touch).

**Synthetic test result:** 19/19 PASS at local backend including the prod-log bug repro (`topic_shift.opens_new_block — intent=subject_doubt new_block=…`).

**Cliff notes (non-obvious context):**
- The block-close drift reclassify is **logging-only for v0.20.x** — it stores `drift_topic` in `session_events.payload` but does NOT re-derive concept_ids. Wiring real EMA shift requires a fresh RAG pass which is too costly for every block close. If beta shows >5% drift rate, v0.21 enables it.
- `_NEW_QUESTION_MARKERS` regex was the culprit for the prod bug — original v0.20 had `what\s+is` which couldn't match `what's` (apostrophe-s). Now also matches math symbols (`∫`, `²`, etc.) so notation-only pivots like "the integral of sin(x²)" trigger correctly even without a verb.
- Override loader path uses `parents[3]` to get from `app/services/study/card_composer.py` to repo root. v0.21 first-pass had `parents[2]` which landed on `app/scripts/` (doesn't exist) — synthetic test caught it on first run.
- `/admin/study-path` endpoint requires `study_card_view` events — these only start being logged at v0.20.2. Pre-v0.20.2 sessions won't appear. Beta data accumulates from now.
- `PATCH /student/{id}` schema-drift handling means the migration v16 SQL file can ship in this commit but be applied to prod whenever — UI gracefully handles both states. Saves a coordinated deploy.
- Cold-start toast fires only on the FIRST request in a 60s window (then re-arms). Avoids spam when the user does many quick actions during a real cold start.

**Next session — read these files first:**
`docs/version_history.md` (v0.20.2 entry), `scripts/synthetic_beta.py`, `app/services/study/card_composer.py` (override loader), `app/api/doubt.py` (`_detect_topic_shift` + `_reclassify_block_topic`).

**Next session — start here:**
1. Apply migration: `./scripts/run_migration.sh scripts/migrate_v16_student_profile.sql` (so settings save actually persists phone/timezone).
2. Beta with 30 students. Watch Render logs for `topic_shift:` and `block-close drift detected:` lines — first 24h tells us classifier accuracy.
3. After beta runs for 3 days, query: `SELECT subject, topic, COUNT(*) FROM session_events WHERE event_type='study_card_view' GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20;` — pick the next 25 topics to hand-polish overrides for.

---

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

<!-- Older entries pruned 2026-04-21 (v0.20.3). See docs/version_history.md for the full chronology. -->
