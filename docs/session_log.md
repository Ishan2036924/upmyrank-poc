# Session Log — UpMyRank

<!-- Most recent session at top. Keep last 3 entries only. -->
<!-- Written by Claude at end of each session via /handoff command. -->

## Session 2026-04-29 — v0.20.12 + v0.20.13 + v0.20.14 + UptimeRobot keep-alive + login-page redesign + real-user UX hardening

**Focus:** Real-user issue triage. Sir reported "people facing login, loading, no-response issues." Read-only diagnostic (curl + Render API logs + Supabase queries) confirmed every component healthy (Vercel ✓, Render ✓, CORS ✓, Supabase ✓) — but only 12 Render log lines in 12h, suggesting users hit cold-start frustration before the backend even sees them. Plus prod incident from 2026-04-27: LaTeX rendering broken on Units & Dimensions doubt. Plus user request for an amazing login page.

**Status:** DONE + LIVE — three-version bundle pushed in commit `e2fb8c8` (v0.20.12 + v0.20.13 + v0.20.14). Render auto-deployed. UptimeRobot keep-alive ping live (5-min interval, was bouncing on 405 until v0.20.13's HEAD support landed).

**What shipped (chronological):**

1. **v0.20.12 — frontend UX hardening from real-user diagnosis.**
   - Cold-start toast at 3 s (was 8 s) with clearer copy ("Waking up the server — this can take up to a minute on first load. Subsequent requests will be fast. Sit tight!").
   - Session-expired UX: `tryRefresh()` failure now redirects to `/auth/login?reason=session_expired`. Login page reads the query param + shows a clarifying toast ("Your session expired. Please log in again. We rotate tokens for security; this isn't a bug."). Suspense-wrapped the login component (Next.js 16 prerender requirement for `useSearchParams`).
   - Onboarding form recovery: all 12 form-state fields persisted to `localStorage.umr_onboarding_draft` on every change. Restored on mount via one-shot useEffect. Wiped on successful submit. Survives cold-start submit timeouts.
   - Files: `frontend/web/lib/api.ts`, `frontend/web/app/auth/login/page.tsx`, `frontend/web/app/onboarding/page.tsx`.

2. **v0.20.13 — `/health` HEAD support + premium login page redesign + home pingBackend + cold-start telemetry.**
   - `app/api/health.py`: switched from `@router.get("/health")` to `@router.api_route("/health", methods=["GET", "HEAD"])`. UptimeRobot defaults to HEAD; was returning 405 → false-positive monitor-down alerts. Now 200 on both methods.
   - Login page redesign (~530 LOC): animated mesh-gradient background, 3 floating glass orbs, subtle dot grid with mask-fade, 4 floating math symbols (∫, π, Σ, ∂), staggered hero reveal with gradient `think` + animated underline drawing, glassmorphic form card with spring-y icon focus, eye-toggle rotate-flip animation, AnimatePresence on Caps-Lock + inline error, gradient submit with infinite arrow nudge, shake-on-error.
   - `frontend/web/app/page.tsx`: `pingBackend()` on home mount wakes Render before user clicks anything.
   - `app/main.py`: timestamped log lines (`[XXXms] db pool ready`, etc.) for cold-start telemetry. Dropped the `loop.run_in_executor` wrap on `embed_svc.warm_up()` (no-op since v0.7).

3. **v0.20.14 — login-page polish from sir's UX audit.**
   - Em-dashes scrubbed (sounded AI-generated): subhead + session-expired toast.
   - Engineer-facing stat cards (`15K+ NCERT chunks`, `3 Subjects`, `30+ PYQs indexed`) replaced with 3 student-facing benefit cards: 💡 Think it through ("Hints that guide, never spoil"), 🎓 Tutor for you ("Adapts to how you learn"), 🎯 Catch mistakes ("Spot errors before exam day").
   - New `ChatPreview` component: glassmorphic card with pulsing emerald "LIVE TUTOR · Socratic mode" header, student bubble ("I'm stuck on the integral of x²·eˣ"), AI bubble with `Typewriter` component (character-by-character animation, blinking caret).
   - Trust footer: "Bank-grade encryption · Your data never leaves Supabase" → "…never leaves our database". Copyright: "© 2026 UpMyRank · For JEE & NEET aspirants".
   - More motion graphics: pulse-rings rippling outward from logo (2.4s loop, two phases), `SparkleEmit` component fires 6 sparkles around `think` after underline draws, tilt-on-hover (rotateX/Y + perspective: 800) on benefit cards.

**Infra changes:**
- **UptimeRobot** monitor created on `https://upmyrank-poc.onrender.com/health` at 5-min interval. After v0.20.13's HEAD support landed: monitor went green. Render free-tier service stays warm 24/7. Cold-start UX tax for active users effectively eliminated.
- **Vercel "AI Assist" toolbar** flagged as cosmetic — not visible to end users. User can disable in Vercel dashboard if desired.
- **Render paid tier ($7/mo)** declared OPTIONAL (solo project budget). Not pursued.

**Diagnostic findings (the "people are facing issues" investigation):**
- Vercel frontend healthy (200 in 1.6s).
- Render backend healthy (`/health` 200 in 1.18s warm).
- CORS preflight clean for both `/auth/login` and `/doubt/ask`.
- Supabase auth reachable.
- **Real users in DB: 3.** Total signups last 7 days: 22 (so 19 are synthetic accounts from earlier diagnostic harnesses). Real-user activity in last 48h: 0 sessions. Conclusion: real users aren't even getting through onboarding; the cold-start window is the most likely culprit, addressed by UptimeRobot + the v0.20.12 toast + onboarding recovery.

**Cliff notes (non-obvious context):**
- Vercel "Assessment failed: output_config.format.schema: For 'object' type, property 'propertyNames' is not supported" message is a Vercel/Anthropic schema collision in the Vercel AI Toolbar. NOT the user's app failing. NOT visible to end users. Cosmetic only.
- The UptimeRobot 405 was puzzling at first because curl to `/health` returned 200 fine. Root cause: UptimeRobot defaults to HEAD probes; FastAPI `@router.get` only matches GET. The `Allow: GET` response header was the giveaway. Switched to `@router.api_route(..., methods=["GET", "HEAD"])`.
- The login page Suspense wrap is required because Next.js 16 prerenders client components, and `useSearchParams()` cannot run during prerender without `<Suspense>`. Without the wrap: build fails with "useSearchParams() should be wrapped in a suspense boundary at page /auth/login".
- Aggressive lazy-load of engine services (split-phase lifespan with `engine_ready` event) was attempted in v0.20.13 and reverted: 5 endpoints (`/doubt/*`, `/session/end`, `/onboarding/submit`) grab `request.app.state.socratic_engine` synchronously, splitting required ~30 LOC of plumbing across call sites. Net Python boot savings would be 3-5s on free-tier cold start (Render's container provisioning dominates anyway). Not worth the regression risk.
- Em-dashes were SPECIFICALLY called out by sir as an AI-content tell. Future copy reviews must scrub `—` from any user-visible string. Comments in code are fine.

**Deferred to next session:**
- Cleanup synthetic accounts in Supabase (many accumulated across diagnostic runs). Use `scripts/diag_cleanup_test_accounts.py --dry-run` first.
- Real-user E2E walkthrough at `https://upmyrank-poc.vercel.app/auth/signup` with a real Gmail address (sir or user themselves).
- Edge-100 full re-run on prod (the 35-flow salvage from 2026-04-27 missed B/C/D/H/I/J classes; with v0.20.11's JWT-refresh, full 100-flow run should complete in one pass).
- v0.22 — misconception library expansion (~50-100 keyword additions, ~2 hours of mechanical work).
- v0.22 — personalization-prompt strengthening (top-of-system-prompt do/don't per `learning_preference`).

**Next session — read these first:**
1. `MEMORY.md` (top section — covers prod state + recently shipped + next-up).
2. `docs/version_history.md` (top 4 entries: v0.20.14 + v0.20.13 + v0.20.12 + v0.20.11).
3. This file (cliff notes for the 2026-04-29 work).

**Next session — start here:**
1. Verify UptimeRobot monitor stayed green (Render still warm 24/7).
2. Run `scripts/diag_cleanup_test_accounts.py --dry-run` to inventory synthetic accounts; then drop the flag to delete.
3. If sir / user want to test as a real student: walk through signup → onboarding → first doubt at the live URL, time the journey, screenshot any UI bugs.
4. v0.22 work (library expansion + personalization prompt) when ready.

---

## Session 2026-04-25 — v0.20.7 + v0.20.8 + v0.21 + v0.20.7.1 + multi-user retest + cofounder summary + Redis pitch

**Focus:** Ship the 3 fixes for the bugs surfaced in the 2026-04-23 100Q diagnostic (follow-up continuation, short-pivot block-open, misconception-on-initial-doubt), plus a small patch (v0.20.7.1) that closes a regression v0.20.7 introduced. Then re-run the full 100Q diagnostic against a local backend with all fixes live, run a new multi-user diagnostic to validate personalization, and write a 1-2 page summary doc for sir.

**Status:** DONE + LIVE — v0.20.7 + v0.20.8 + v0.21 committed + pushed (`9e1988a`, `cb26e18`); v0.21's diff bundled into v0.20.7's commit hash (functionally identical on prod, history-hash bundling documented in version_history.md v0.21 entry). v0.20.7.1 committed + pushed (`3eb7a67`, live on Render since 2026-04-25 02:04 UTC). **Upstash Redis Free tier provisioned + `REDIS_URL` set on Render — verified live via probe `/doubt/ask` + log inspection: 0 `connection refused` warnings on real traffic.** Cofounder summary + MEMORY.md + session_log + version_history all updated and pushed.

**Changed files (this session):**
- **MODIFIED** `app/api/doubt.py` — v0.20.7 (`_CONTINUATION_STARTERS_RE` + `_looks_like_continuation` + early-return guard); v0.20.7.1 (asymmetric guard with LLM classifier + deterministic `_SUBJECT_KEYWORDS` fallback for short ambiguous prompts); v0.20.8 (block-stamp `misconception_id` after `_create_doubt_block` in both `/doubt/ask` and `/doubt/ask/stream` paths); v0.21 (split `explanation` intent — falls through to `start_session` when `study_session_id` is set, legacy path preserved when not).
- **MODIFIED** `app/services/doubt/engine.py` — v0.20.8 added `check_for_misconception` calls in `start_session` + `start_session_stream` after RAG completes; logs `misconception_detected` session event; injects `is_misconception_correction` + `misconception_id` into result payload.
- **MODIFIED** `app/services/doubt/misconceptions.py` — v0.20.8 added topic-agnostic 2-keyword fallback in `check_for_misconception`; expanded `centripetal_outward_force` keyword list to cover natural phrasings.
- **NEW** `scripts/diagnostic_multiuser.py` — 3-persona × 20-shared-prompt parallel harness with style-keyword + length-divergence + Judge LLM consistency analysis.
- **NEW** `scripts/data/diagnostic_smoke_fixes.json` — bug-#1/#2/#3 smoke fixtures.
- **NEW** `scripts/data/diagnostic_smoke_v0207_1.json` — v0.20.7.1 regression fixtures (4 cross-subject pivots + 5 same-subject regression guards).
- **NEW** `reports/diagnostic_post_fixes_2026-04-25.md` + `.json` — 100Q post-fix run.
- **NEW** `reports/multiuser_post_fixes_2026-04-25.md` + `.json` — 3-persona run.
- **NEW** `reports/comparison_2026-04-25.md` — full before/after with all 4 pillars + the new bug from multi-user.
- **NEW** `docs/cofounder_summary_2026-04-25.md` — 1-2 page tech summary for sir.
- **MODIFIED** `MEMORY.md` — current version → v0.20.7.1, recently shipped + next-up rewritten.
- **MODIFIED** `docs/version_history.md` — v0.20.7 / v0.20.8 / v0.21 / v0.20.7.1 entries + index rows; v0.21 entry notes git-hash bundling.
- **MODIFIED** `docs/session_log.md` (this) — new top entry, oldest pruned.

**Verification (delta vs 2026-04-23):**
- Follow-up continuation rate: 50 % → **100 %** (15/15) — v0.20.7 hits.
- Short-pivot block-open rate: 33.3 % → **100 %** (6/6) — v0.21 hits.
- Topic-shift pass rate: 75 % → 58 % (v0.20.7 over-fire) → patched in v0.20.7.1 (smoke-tested cross-subject + same-subject regression guards).
- Misconception detection: wiring fixed (3/3 smoke when phrasings align with library); diagnostic-100 phrasings still 0/10 because the library's keyword coverage is too narrow → filed as v0.22.
- Multi-user: response length σ/μ = 0.231 (above 0.15 threshold ✅); Judge quality 0.82–0.86 across HIGH/MEDIUM/LOW (consistent ✅); style-keyword diagonal: HIGH→formula ✓, MEDIUM/LOW also lean formula ✗ → filed as v0.22 (prompt engineering).
- Socratic adherence held at 97.1 %; factual 1.00; single-question rate 90 % → 100 %.

**Cliff notes (non-obvious context):**
- **v0.20.7.1 uses BOTH a classifier subject mismatch AND a deterministic keyword fallback.** The LLM classifier is unreliable on short ambiguous prompts (returns empty/wrong subject for "what is pH?"); the keyword regex catches these cases.
- **v0.21 commit-hash quirk:** all three fixes' `app/api/doubt.py` changes were staged together when v0.20.7's `git add` ran, so they shipped under hash `9e1988a` ("v0.20.7" message). v0.21 has no commit of its own — code is on prod, just history-message slightly imprecise. NOT rewriting history (RULES.md). Future commits should stage incrementally with `git add -p` when multiple version changes touch the same file.
- **Misconception library coverage is the v0.22 work.** Wiring (v0.20.8) is correct; library only matches narrow phrasings ("centrifugal" + "outward force"). Natural prompts ("centripetal pulls outward") miss. Need ~50–100 keyword additions across 30 entries.
- **Multi-user new finding (v0.22):** length divergence personalization works (σ/μ=0.231); style-keyword personalization doesn't — gpt-4.1-mini defaults to formula on technical questions regardless of `learning_preference`. Fix is prompt-engineering only — top-of-system-prompt do/don't examples per learning style.
- **Sir is provisioning Upstash Redis (Free tier) → set `REDIS_URL` env var on Render.** Redis was 100 % down in prod per v0.20.5 R1. Free tier is 256 MB / 10 GB / unlimited commands — way more than we need (we'll use ~5 MB / 50 MB / 22k commands per month at 30-student beta scale).

**Deferred to next session:**
- v0.22 — misconception library keyword expansion + personalization-prompt strengthening (do/don't per learning_preference).
- ~~Confirm Redis is alive in prod logs after sir sets `REDIS_URL`.~~ ✅ DONE — Redis verified live, zero `connection refused` warnings on real probe traffic.
- **Render paid tier ($7/mo)** when beta launches — kills 22-116 s cold start. **Strongly recommended before inviting beta students** — cold start is the #1 UX risk.
- Cleanup 9 synthetic accounts in Supabase (smoke + 100Q + multi-user + redis-probe residue) once spot-check is done. Run `scripts/diag_cleanup_test_accounts.py --dry-run` first.

**Beta-readiness verdict (added end-of-session 2026-04-25):**
**YES — ready for a 30-student private beta with one strong recommendation: provision Render Starter ($7/mo) before inviting students.** Engine quality is strong (97 % Socratic, 100 % factual, 100 % follow-up continuation); critical security holes from v0.20.5 are closed; Knowledge Genome plumbing is healthy with autoclose-idle backstop firing; Redis is connected; personalization signal is real (σ/μ = 0.231). The only real UX risk is the free-tier 22-116 s cold start. v0.22 work (misconception library expansion + personalization-prompt strengthening) can land during beta as iterations, not blockers.

**Next session — read these first:**
`docs/cofounder_summary_2026-04-25.md` (overall context), `reports/comparison_2026-04-25.md` (the technical delta — all 4 pillars), `app/api/doubt.py` (`_detect_topic_shift` + `_SUBJECT_KEYWORDS`), `app/services/doubt/misconceptions.py` (library coverage gap for v0.22).

**Next session — start here:**
1. ~~Verify Redis is up~~ ✅ DONE.
2. ~~Push v0.20.7.1~~ ✅ DONE (commit `3eb7a67`, live).
3. **Decide on Render paid tier** ($7/mo). If yes → click "Change Instance Type" → Starter in Render dashboard. After this, run a fresh 100Q + multi-user diagnostic against prod (not local) to baseline beta-launch performance.
4. **Run cleanup** of 9 synthetic accounts (`scripts/diag_cleanup_test_accounts.py --dry-run` then real run) so prod DB is clean for beta.
5. **Start v0.22 work** — library keyword expansion is mechanical (~2 hrs); personalization prompt strengthening is iterative (write + smoke + adjust). Both can ship during early beta as students surface edge cases — not blockers.
6. Wire Sentry for backend exception tracking + OpenAI cost monitoring before beta scales beyond ~30 students.

---

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

<!-- Older entries pruned 2026-04-29 (v0.20.14 — last-3 rule). Pruned: 2026-04-21 v0.20.4 admin panel + mastery hot patches. See docs/version_history.md for the full chronology. -->
