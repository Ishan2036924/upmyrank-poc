# Session Log — UpMyRank

<!-- Most recent session at top. Keep last 3 entries only. -->
<!-- Written by Claude at end of each session via /handoff command. -->

## Session 2026-04-21 (cont. cont.) — v0.20.4 admin panel + mastery hot patches

**Focus:** v0.20.3 deployed. Prod synthetic + Render logs surfaced THREE more bugs in the v0.20.2 admin Study Path panel + mastery composer — all hidden behind soft "non-fatal" INFO log fallbacks. Fix all three, harden synthetic to catch the regression in CI.

**Status:** DONE — backend + migration + extended synthetic + docs; awaiting user push.

**Three bugs fixed:**
1. `_compose_mastery` JOIN used `c.concept_id`; column is `c.id`. Every Concept Card showed global average mastery instead of topic-specific.
2. `session_events_session_type_check` CHECK constraint rejected `'study'`. Migration v17 widens to `('doubt','practice','mock','study')`.
3. After (2), `session_events_session_id_fkey` FK rejected `gen_random_uuid()` (no matching row in `doubt_sessions`). Pass NULL — `session_id` column is nullable.

**Changed files (v0.20.4):**
- **NEW** `scripts/migrate_v17_session_events_study.sql`
- **MODIFIED** `app/services/study/card_composer.py` — JOIN fix + warning level on fallback
- **MODIFIED** `app/api/study.py` — NULL session_id + warning level on insert failure
- **MODIFIED** `scripts/synthetic_beta.py` — mastery-shape assert + admin study_path view-count assert
- **MODIFIED** `docs/version_history.md`, `docs/session_log.md` (this), `docs/bugs.md`

**Cliff notes (non-obvious context):**
- Three bugs, all in the same code path, all logged INFO `skipped (non-fatal)` for >24h. Lesson: "non-fatal" doesn't mean "non-impactful." Silent fallbacks that materially change response shape get WARNING level + explicit consequence text from now on.
- Bug #3 (FK) only surfaced AFTER bug #2 (CHECK) was fixed. Postgres only reports the first failing constraint per insert — without v17 we'd never have seen the FK issue. Lesson: when adding a new event-type to a multi-constrained table, check ALL constraints before shipping.
- Migration v17 is idempotent (DROP IF EXISTS + ADD). Safe to re-run if applied state is unclear.
- Synthetic test guard: `admin_study_path.records_views` calls 2 cards then queries `/admin/study-path` and asserts `total_views > 0`. If migration v17 isn't applied OR the FK fix is missing OR a future v0.X regresses the inserts, this assertion fails. SKIPs cleanly when the test student isn't admin (returns 401/403), so it doesn't false-fail in CI.

**Next session — read these first:**
`docs/bugs.md` (top entry — the two-constraint trap), `app/api/study.py` (the NULL session_id pattern), `scripts/synthetic_beta.py` (`scenario_admin_study_path_records_views`).

**Next session — start here:**
1. Push v0.20.4. Apply migration v17 to prod via `./scripts/run_migration.sh scripts/migrate_v17_session_events_study.sql`.
2. Re-run prod synthetic — `total_views` should be ≥1.
3. Visit `/admin#study-path` in browser — Top Concept Cards table now populated.
4. Then continue with the v0.20.2 follow-ups (beta with 30 students; monitor topic-shift + drift logs).

---

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

<!-- Older entries pruned 2026-04-21 (v0.20.4). See docs/version_history.md for the full chronology. -->
