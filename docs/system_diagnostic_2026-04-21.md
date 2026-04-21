# UpMyRank — Full System Diagnostic Report
**Date:** 2026-04-21
**Trigger:** User-requested comprehensive diagnostic ("biggest of all")
**Scope:** Phases 0–8 (infra, DB, API, security, content quality)
**Backend tested:** `https://upmyrank-poc.onrender.com` (v0.20.4 + migration v17 applied)
**Database:** Supabase prod (`vgctqmhwezmihhmnwtzm`)
**Cost spent:** ~$0.40 (Judge LLM on 15 sessions; no synthetic-persona runs needed beyond what was already verified)

---

## TL;DR — three bugs to fix before beta, in order

| # | Severity | Bug | Fix effort |
|---|---|---|---|
| 1 | 🔴 **CRITICAL** | **Knowledge Genome is silently broken — 44 of 45 students have zero mastery data**. Sessions almost never end → `_genome_update_task` almost never fires → mastery EMA almost never updates. The ENTIRE central feature of the product. | 4-8 hours |
| 2 | 🔴 **CRITICAL (security)** | **Every `/admin/*` endpoint returns student PII to any authenticated user.** Admin gating is missing. | 1 hour |
| 3 | 🔴 **CRITICAL (security)** | **`GET /student/{id}` allows any student to read any other student's full genome.** Auth check missing on read (PATCH is gated; GET isn't). | 30 min |

Plus 7 high-priority bugs and ~10 medium-priority improvements documented below.

---

## What's GREEN (don't worry about these)

To calibrate severity, here's what the diagnostic confirmed is working:

- ✅ Backend health endpoint up; cold start ~22s (Render free tier — known).
- ✅ All 17 migrations applied correctly (v16 columns present, v17 CHECK widened).
- ✅ `PATCH /student/{id}` correctly returns 403 when student A tries to edit student B (the auth check I shipped in v0.20.4 works).
- ✅ Topic-shift demotion firing in prod (logs show `v0.20 topic-shift: demoting...` events).
- ✅ Notes section deduplication works (Projectile Motion = 1 unique chunk; was 3 before v0.20.4).
- ✅ Concept Card override loader works (5 hand-polished cards render correctly).
- ✅ Migration v17 applied + study_card_view events landing in DB (5 rows so far).
- ✅ Socratic quality on prod is **1.47/2 average** — borderline good, AI is asking guiding questions ~80% of the time.
- ✅ No orphan rows in `doubt_blocks` / `concept_mastery` (referential integrity holds).
- ✅ No dead concept_id pointers in recent `doubt_sessions.concepts_involved`.
- ✅ Token expiry properly returns 401.
- ✅ Empty/malformed signup payloads return 422 (validation working).
- ✅ Unauthenticated requests to protected endpoints return 401.
- ✅ Persona profile staleness check: 0 profiles >30 days old (compression is firing).
- ✅ Frontend builds clean (15 routes, all static-prerendered or dynamic as expected).
- ✅ Admin endpoints exist; the panel renders when given data.

The **product machinery is mostly correct.** The three critical bugs are about **data flow** (mastery never updates) and **access control** (admin/cross-student gates missing).

---

## 🔴 CRITICAL — block beta

### #1. Knowledge Genome is functionally non-existent

**Evidence (live prod data):**
- 45 students total, of which **only 1 has any concept_mastery row above zero**.
- 84 `concept_mastery` rows, of which **83 are stuck at score=0** despite multiple attempts.
- 469 study_sessions; only 7.2% (34) have `ended_at` set.
- 409 doubt_blocks; only 3.7% (15) are `solved=TRUE`; 23.5% (96) have `ended_at`.
- All-time `session_terminal` events in `session_events`: **16**. Vs `hint_requested`: 671, `question_asked`: 432.
- 27 of 45 students have NEVER completed onboarding but have study_sessions (60% drop-off).

**Root cause (verified in code):**
The mastery EMA in `_genome_update_task` (`app/api/doubt.py:497`) only fires from these paths:
1. `/doubt/ask` continuation when `hint_result.resolved == True` (line 967-979). Students rarely click "Got it!" — only 3.7% of blocks reach `solved=TRUE`.
2. `/doubt/hint` when `result.resolved == True` (line 1155-1172). Same constraint.
3. `_close_doubt_block(solved=False)` with `hint_level >= 1` (line 363-371). Requires `_close_doubt_block` to be called at all — which only happens when (a) the user explicitly ends the session via `POST /session/end`, or (b) a new `subject_doubt` intent comes in with an active block (line 745-748). Students don't log out cleanly — they close the tab. So `/session/end` never fires for 92% of sessions.

**Net effect:** 44 of 45 real students get zero pedagogical signal back to the system. The "Knowledge Genome" — the entire product premise — exists in name only.

**Fix (proposed, ~4-8 hours):**
1. **Inactivity-driven session close.** Background task or cron: every 1 hour, find `study_sessions` with `started_at + 30 min` and no recent activity, force-close them via `_close_doubt_block` for active blocks + summary. This unlocks mastery updates for tab-closers.
2. **Per-turn mastery signal (lightweight).** Today, `_genome_update_task` only fires at terminal state. Add a smaller "running EMA" that updates `concept_mastery` after every L1/L2 hint based on whether the student's response was correct. This gives a gradient of signal during a session, not just at end.
3. **Frontend `beforeunload` ping.** When student closes tab, fire a `navigator.sendBeacon('/session/end', ...)`. ~10-line frontend change.

Test with synthetic suite + verify in DB that `concept_mastery.mastery_score > 0` for at least 80% of students who have ≥1 doubt_session.

### #2. `/admin/*` endpoints are not admin-gated

**Evidence:**
Created a fresh non-admin user via `POST /auth/signup`. Hit each admin endpoint:
- `GET /admin/platform-health` → **200 OK** (returned platform metrics)
- `GET /admin/study-path` → **200 OK** (returned card view stats)
- `GET /admin/student-insights` → **200 OK** — **leaked real student UUIDs, topic names, last-seen timestamps**
- `GET /admin/knowledge-base` → **200 OK** (returned chunk counts by subject)

Only `GET /admin/is_admin` correctly returns `{"is_admin": false}` — but that's authoritative-but-unused. The other endpoints don't check the flag.

**Root cause:** `app/api/admin.py` endpoints use `_: str = Depends(get_current_student_id)` (any authenticated user) but **never call `is_admin()`** to gate access. Comparing to `_genome_update_task`, RULES.md, and `migrate_v10_rls.sql` — admin endpoints should require `is_admin = TRUE`.

**Fix (~1 hour):**
Add a dependency `Depends(require_admin)` that wraps `is_admin()` and raises 403 if not. Apply to all 14 `/admin/*` routes. Pattern:

```python
async def require_admin(student_id: str = Depends(get_current_student_id),
                       request: Request = None):
    # Reuse existing is_admin() logic from app/api/admin.py:42
    if not await _is_admin_check(student_id, request.app.state.db_pool, settings):
        raise HTTPException(403, "Admin access required")
    return student_id
```

Then change every `/admin/*` route's `_: str = Depends(get_current_student_id)` to `_: str = Depends(require_admin)`.

### #3. `GET /student/{id}` leaks any student's data to any authenticated user

**Evidence:**
Created two test students A and B. Authenticated as A; hit `GET /student/$B_SID` → **200 OK**, returned B's full genome (name, topic_mastery, weakest_concepts, persona_profile).

**Root cause:** `app/api/student.py:40` `get_student()` only checks that the caller is authenticated, not that path `student_id == authenticated student_id`. The PATCH endpoint I added in v0.20.4 has this check — the GET doesn't.

**Fix (~30 min):**
Add the same `if student_id != current: raise HTTPException(403, ...)` check to `get_student()` that exists in `patch_student()`. Apply same to `POST /student/{id}/update-mastery`.

---

## 🟠 HIGH — fix this week

### #4. `Settings()` extra_forbidden — backend can't start with new env vars

**Evidence:** When I tried to import `from app.config import settings` in the diag script, pydantic raised:
```
ValidationError: 2 validation errors for Settings
render_api_key — Extra inputs are not permitted
render_service_id — Extra inputs are not permitted
```

**Root cause:** The Settings class in `app/config.py` uses pydantic-settings with default `extra='forbid'`. Any new env var added to `.env` that isn't declared in the Settings model crashes startup. Local dev is currently broken for anyone who pulls latest + has the diagnostic-era `.env`.

**Fix:** Either declare RENDER_API_KEY/RENDER_SERVICE_ID in Settings (not used by app, just there for scripts) OR change `model_config = SettingsConfigDict(extra="ignore")`. Option B is safer — won't crash on future env-var additions.

### #5. No rate limiting on `/auth/login`

**Evidence:** 10 consecutive POST `/auth/login` with bad credentials all returned 401 with no throttling. No 429 ever.

**Impact:** Brute-force attack surface on every student account. Supabase itself rate-limits, so the impact is mostly cost (each failed login burns a Supabase auth call). Worth a lightweight in-memory rate limiter.

**Fix:** Add `slowapi` or simple Redis-backed rate limit (5 attempts / 5 min per IP). When Redis lands, this is trivial.

### #6. Redis is 100% down in prod (since at least 2026-04-17)

**Evidence:** Render logs from 4+ days back show consistent `Error 111 connecting to localhost:6379. Connection refused` warnings on every doubt request. Three places hit Redis per request: `app/services/memory/context.py` (hot context read), `app/services/cache/semantic_cache.py` (get + set). All silently degrade.

**Impact:**
- **Semantic cache disabled** — repeat doubts hit OpenAI from scratch every time (~$$ wasted)
- **Hot context disabled** — slower cross-session memory loads
- **Persona compression disabled** — wait, this writes to Postgres, so probably still fires

**Fix:** Provision a Render Redis add-on ($7/mo) OR external Upstash Redis (free tier). Update `REDIS_URL` env var on Render. The graceful-degradation is correct; the lack of Redis itself is the issue.

### #7. `response_feedback` table is empty (0 rows all-time)

**Evidence:** SQL count: `SELECT COUNT(*) FROM response_feedback` → 0. Either:
(a) The thumbs UI in `frontend/web/components/ChatMessage.tsx` is broken end-to-end, OR
(b) No student has ever clicked thumbs.

Given we have 45 students × 432 question_asked events, (b) is statistically implausible. Likely (a).

**Test:** Manually click thumbs in `/doubt`, watch browser devtools Network tab + Render logs. The session_log already has a note from 2026-04-17 about adding a console.error log — confirm whether it surfaces.

**Fix:** Likely a missing CORS preflight, malformed body, or an auth header issue. Need to repro and read the network response.

### #8. 60% onboarding drop-off (27 of 45 students never finished)

**Evidence:** SQL: `SELECT COUNT(DISTINCT student_id) FROM study_sessions WHERE student NOT onboarded` → 26. Plus 1 not in any sessions but signed up.

**Possible causes:**
1. Onboarding flow is too long/buggy.
2. Students bypass it and go straight to `/doubt` (and the AuthGuard on `/onboarding` doesn't redirect them back).
3. Onboarding submit fails for many.

**Fix:** Add a redirect-to-onboarding gate at the *AppShell* level (currently only login flow checks it). Audit the onboarding form for validation issues.

### #9. Conversation history grows unbounded (top session is 13KB / 14 turns)

**Evidence:** SQL: top-10 `doubt_sessions` by `LENGTH(conversation_history::text)`. Worst: 13126 bytes / 14 turns. Not yet biting at 30 students; will explode at 1000.

**Fix:** v0.21 — bound `conversation_history` to last 10 turns inside a doubt block; rely on summary for older context.

### #10. Only 16 `session_terminal` events ever — Judge LLM has no fresh data to score

**Evidence:** Phase 5 had to sample from old sessions because new sessions don't reach terminal state. Means `app/admin/quality-report` and the regression gate are scoring stale data.

**Fix:** Same as #1 — once sessions actually close, terminal events fire, Judge has fresh data.

---

## 🟡 MEDIUM — quality-of-life

### #11. CORS preflight returns 405 on OPTIONS `/auth/login`

May or may not be a real issue — depends on whether Vercel browser sends preflight. Worth verifying. If real: add a CORS middleware that handles OPTIONS for all routes.

### #12. No 5xx error rate monitoring

If a student hits a 500, you only know if you read Render logs. Add a /healthz endpoint that exposes counts of 5xx in last 5 min, OR ship Sentry/Datadog (free tier).

### #13. No cost monitoring on OpenAI burn

OpenAI usage is invisible to the app. Hard to know when a single buggy session burns $5. Add a `session_metrics.openai_tokens` field updated per LLM call.

### #14. The 80% single-question Judge metric — 20% of AI responses still ask multiple questions

The single-Q cleanup (`engine.py:1813`) is mostly working but slips through 1 in 5 times. Tighten the regex or add a second-pass.

### #15. Concept names like "Maxima, Minima and Monotonicity" leak through the admin response that any user can see

Combined with #2, this isn't strictly a privacy issue (concept names aren't PII) but is "info disclosure" beyond intent.

### #16. Bot-shaped emails are getting through signup

Test signups created `synthbeta+abc@upmyrank.test` style emails — no validation that the domain is real. Not a security issue per se but pollutes student count metrics.

### #17. `session_summary` on `study_sessions` is mostly NULL

Out of 469 study_sessions, 34 have ended (7.2%). Of those 34, summaries should exist. SQL spot-check needed.

---

## 🟢 NITS

- Stale UI plan in `docs/ui_overhaul_plan.md` (superseded; should be archived).
- Some Concept Card sections render `1 unique chunks` (correct singular: "1 chunk").
- Onboarding restyle pending from v0.20 plan.

---

## Performance / cost findings

| Metric | Value | Observation |
|---|---|---|
| Backend cold start (free tier) | 22.6s | Known. `pingBackend()` mitigates. Render Standard tier ($7/mo) eliminates. |
| Backend warm hit p50 | ~1s | Acceptable for now |
| `/doubt/ask` turn (warm) | 4-8s | Dominated by RAG (~5s) + LLM (~3s) |
| Total Postgres data | ~430MB | knowledge_chunks (265MB) + problems (162MB) dominate. Healthy. |
| `concept_mastery` size | 84 rows | Should be ~5x larger if mastery worked (see #1) |
| Avg doubt_sessions per student | 10.4 | Healthy engagement |
| `session_events` last 7d | 1144 | Active product |
| OpenAI cost burn (estimated) | $0.10-0.30 / student / day | Comfortable; 30 students × 30 days × $0.20 = ~$180/mo |

---

## Recommended sprint plan

### Sprint 1 (this week — pre-beta blocker)
1. **Fix #2** — admin gating (1 hour)
2. **Fix #3** — `GET /student/{id}` cross-student leak (30 min)
3. **Fix #4** — Settings extra='ignore' (5 min)
4. **Fix #1** — Knowledge Genome session-close (4-8 hours, biggest win)

→ Verify: synthetic-suite assertions: (a) every signed-up student has ≥1 nonzero `concept_mastery` row after 1 session, (b) `/admin/*` returns 403 to non-admin, (c) cross-student GET returns 403.

### Sprint 2 (week 2 — quality + cost)
5. **Fix #6** — Provision Redis (1 hour for setup, immediate cost win)
6. **Fix #7** — Debug response_feedback (1-2 hours)
7. **Fix #8** — Onboarding gate at AppShell (1 hour)
8. **Fix #5** — Auth rate limiting (1 hour with Redis)

### Sprint 3 (post-beta validation)
9. **Fix #9** — Bound conversation_history (3 hours)
10. **Fix #14** — Tighten single-Q cleanup (1 hour)
11. Add Sentry/cost monitoring (#12, #13)
12. Onboarding restyle (deferred from v0.20)

---

## What I tested but didn't deeply probe (left for future audits)

- **Load test** — 30 students isn't load. Skipped.
- **Vision/photo upload path** — only smoke-tested.
- **Full LLM-driven persona journeys (8 types × 5 personas)** — would have re-confirmed bugs we already know. Skipped to save $$.
- **Mock test mastery flow** — `/mock/submit` → `_mock_genome_update_task` not exercised in this audit.
- **Penetration testing** beyond auth gaps.
- **Browser-matrix testing** (Safari/Firefox).

---

## Appendix — raw outputs

- `/tmp/diag/db_audit.json` — 16 DB integrity checks
- `/tmp/diag/critical_session.txt` — session-termination drilldown
- `/tmp/diag/judge_results.json` — Judge LLM scores per session
- `/tmp/diag/judge_output.txt` — Judge run console output

These should be archived to `docs/system_diagnostic_artifacts_2026-04-21/` before they're cleaned from `/tmp`.

---

**Done.** The product is closer to beta than I feared on the architecture side, and farther on the data-pipeline side. Fix bugs #1, #2, #3 and you're clear to invite 30 students.
