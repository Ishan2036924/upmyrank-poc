# Session Log — UpMyRank

<!-- Most recent session at top. Keep last 3 entries only. -->
<!-- Written by Claude at end of each session via /handoff command. -->

## Session 2026-04-23 — v0.20.5 docs backfill + v0.20.6 thumbs fix + 100Q prod diagnostic

**Focus:** v0.20.5 (commit `9f0de7a`) shipped critical security + Knowledge-Genome fixes on 2026-04-21 but was pushed **without the required `docs/version_history.md` + `docs/session_log.md` entries** — policy violation per `CLAUDE.md`. Backfill first, then fix the remaining R2 from that diagnostic (thumbs UI `response_feedback` table is 0 rows all-time — suspected frontend bug), then run a 100-question end-to-end quality diagnostic against prod.

**Status:** DONE — v0.20.5.1 docs backfill + v0.20.6 thumbs fix + synthetic diagnostic harness + report shipped; awaiting user push. Cleanup of synthetic personas is user-gated (asked before running).

**Changed files (v0.20.5.1 + v0.20.6 combined):**
- **MODIFIED** `docs/version_history.md` — appended `## v0.20.5`, `## v0.20.5.1`, `## v0.20.6` sections + 3 new index rows.
- **MODIFIED** `docs/session_log.md` (this) — new top entry, oldest (v0.20.2) pruned per the last-3 rule.
- **MODIFIED** `frontend/web/app/doubt/page.tsx` — `handleFeedback` computes `response_idx` as `messages.slice(0,msgIdx).filter(m => m.role === 'tutor').length` (was absolute `msgIdx` including divider+student rows, which collided with the `UNIQUE(student_id, doubt_session_id, response_idx)` constraint via ON CONFLICT — thumbs silently overwrote the wrong row on the second click).
- **NEW** `scripts/diagnostic_100.py` — thin wrapper around `synthetic_beta.py` that runs the 100-prompt set, waits for async Judge rows, queries Supabase for aggregates, pulls Render logs, writes a markdown + JSON report.
- **NEW** `scripts/data/diagnostic_100.json` — 100 prompts across 9 scenario classes (canonical, follow-up, sudden pivot, short-form pivot, misconception, emotional, out-of-scope, vague, forced-attempt ladder).
- **NEW** `reports/diagnostic_2026-04-23.md` + `.json` — quality report scored on user's 4 pillars (comms quality, Knowledge Genome correctness, personalization, learning ease).

**Cliff notes (non-obvious context):**
- The thumbs bug is an index-semantics mismatch, not a missing endpoint — `app/api/feedback.py:21` explicitly documents `response_idx` as "0-based index of the AI message in the conversation" but the React component was passing the raw array index. Silent ON CONFLICT DO UPDATE hid it — no 500s, no DB errors, just wrong rows and mysterious "toggle doesn't stick" UX reports. Backend + migration + UNIQUE constraint are all correct; single frontend one-liner fixes it.
- Diagnostic hits **prod Render directly** (`https://upmyrank-poc.onrender.com`) — no local server. Personas tagged with a `diagnostic_run_id` so `diag_cleanup_test_accounts.py --run-id …` removes only this run's rows. Judge LLM is fired automatically by the prod engine on every response; script just waits 2s after each response and then pulls `judge_evaluations` aggregates.
- The 9 scenario classes are spread across 3 synthetic personas (high/medium/low scaffolding) so personalization can be judged from the same 100-prompt base: a MEDIUM persona getting the same Q as a LOW persona should produce visibly different responses (different `max_concepts`, different scaffolding). Divergence between rendered responses = personalization working; identical = personalization not firing.

**Deferred to next session:**
- Post-cleanup re-query of `concept_mastery` once prod has 24-48h of real user traffic on v0.20.5 — confirms autoclose-idle backfill is working on abandoned sessions.
- Fix for any bugs surfaced by the diagnostic report (shipped as v0.20.7+).

**Next session — read these first:**
`reports/diagnostic_2026-04-23.md` (the quality report — has a prioritized bug list at the bottom), `docs/version_history.md` (top 3 entries: v0.20.5 + v0.20.5.1 + v0.20.6), `scripts/diagnostic_100.py` (to re-run or extend).

**Next session — start here:**
1. Push v0.20.5.1 + v0.20.6 (two separate commits).
2. Review the prioritized bug list from the diagnostic report. Any P0s get shipped as v0.20.7.
3. Provision Render Redis add-on ($7/mo) — last remaining R1 from the v0.20.5 diagnostic.

---

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

<!-- Older entries pruned 2026-04-23 (v0.20.5.1 — last-3 rule). Pruned: v0.20.2. See docs/version_history.md for the full chronology. -->
