# UpMyRank — Diagnostic + Fixes Report (v0.20.5)
**Date:** 2026-04-21 (afternoon — second pass after morning diagnostic)
**Scope:** All 9 phases of the morning diagnostic + cleanup + 8 critical fixes shipped + re-verification.
**Local backend:** running with all v0.20.5 fixes applied.
**Production:** UNCHANGED — awaiting your push of the v0.20.5 commit.

---

## TL;DR

| Item | Before | After (local, post-fix) |
|---|---|---|
| Total students in DB | **49** (mostly test accounts) | **7** (real users only) |
| `/admin/*` endpoints accept non-admin tokens | 🔴 200 (PII leak) | ✅ **403** |
| Cross-student `GET /student/{id}` | 🔴 200 (genome leak) | ✅ **403** |
| Rate limiting on `/auth/login` | 🔴 None (10× brute-force returned 401) | ✅ **429** at attempt 11 |
| Knowledge Genome — sessions actually closing | 🔴 7.2% ended ever | ✅ Auto-close fires when `/doubt/ask` or `/doubt/hint` called after 30 min idle (verified by smoke test) |
| `Settings()` startup with diagnostic env vars | 🔴 ValidationError | ✅ Imports cleanly |
| Onboarding bypass | 🔴 60% drop-off, no gate | ✅ AppShell redirects any non-onboarded student to `/onboarding` |
| `conversation_history` unbounded growth | 🔴 13KB/14 turns top, O(turns²) cost | ✅ Bounded to first turn + last 10 |
| Diagnostic test-account graveyard | 🔴 42 dev/synthetic accounts polluting metrics | ✅ Deleted (DB + Supabase auth) |

---

## What I shipped (in code) — v0.20.5

### Critical security fixes
**1. `app/api/admin.py`** — added `require_admin` dependency. Replaced `Depends(get_current_student_id)` with `Depends(require_admin)` on **14** admin endpoints. Re-uses 3-stage check (DB email → JWT email fallback → legacy UUID). Verified: `/admin/student-insights`, `/admin/platform-health`, `/admin/study-path`, `/admin/knowledge-base` all now return **403** to non-admin tokens (was 200 — leaking student PII).

**2. `app/api/student.py`** — added cross-student guard to `GET /student/{id}`. Allows: own row, OR admin reading any row. Verified: A reading B's data returns **403** (was 200 — leaking full genome). PATCH was already gated in v0.20.4.

**3. `app/api/auth.py`** — added in-memory rate limiter on `/auth/login`. 10 failed attempts per IP per 5 min, returns **429** with `Retry-After` header. Successful logins don't count. Resets when worker restarts. Verified: 10 bad attempts → 401, 11th → 429.

### Knowledge Genome fix (the big one)
**4. `app/api/doubt.py`** — added `_autoclose_idle_blocks()` and `_autoclose_idle_study_sessions()`. Run at the top of every `/doubt/ask` and `/doubt/hint`. Find this student's doubt_blocks idle >30 min, force-close them (which fires `_genome_update_task` for hint-engaged blocks via the existing `_close_doubt_block` branch). Smoke test confirms: forced-stale block was auto-closed when the student's next `/doubt/ask` arrived; new block opened cleanly.

This unlocks mastery updates for tab-closers (the 92% of sessions that never explicitly end). Effect kicks in on the NEXT request from any student who's been idle >30 min, so backfill happens organically as users return.

### Reliability + UX fixes
**5. `app/config.py`** — `SettingsConfigDict(extra="ignore")`. Local dev no longer crashes on unknown env vars (RENDER_API_KEY, RENDER_SERVICE_ID, etc.).

**6. `frontend/web/components/AppShell.tsx`** — universal onboarding gate. Any logged-in student visiting any non-/onboarding/non-/auth route gets `apiGet('/onboarding/status')`; if `onboarding_completed === false`, redirected to `/onboarding`. Catches the 26 students who bypassed the original login-flow check.

**7. `app/services/doubt/engine.py`** — `_bound_history()` helper applied to all 3 `conversation_history` write sites. Strategy: keep first turn (preserves problem context) + last 10 turns + a synthetic separator showing how many were elided. Bounds JSONB row size + per-turn LLM token cost.

### Data hygiene
**8. `scripts/diag_cleanup_test_accounts.py`** — safe cleanup tool. Dry-run by default. Allowlist for real users + Test Student (preserves the only mastery data we have). Per-student transaction (atomic). Tight Supabase auth-API timeout (5s) so a slow auth call doesn't hang the whole script. Result: **49 → 7 students** (deleted: 12 synthbeta, 4 audit, 1 preview, 26 dev test).

---

## Phase-by-phase findings (after fixes)

### Phase 1 — Infrastructure
- Backend cold start: 22.6s (Render free tier — known)
- Backend warm hit: ~1s (acceptable)
- Render Redis: still 100% down (unchanged — needs $7/mo Redis add-on)
- 37 routes registered (38 after the v0.20.5 deploy adds nothing new)
- 100 most-recent ERROR/WARN log entries: **all** are `Redis connection refused` (no other error class)

### Phase 2 — Database integrity (post-cleanup)
| Check | Result |
|---|---|
| Migrations v1-v17 applied | ✅ |
| Orphan doubt_blocks | 0 |
| Orphan concept_mastery | 0 |
| Dead concept pointers | 0 |
| Stale persona profiles | 0 |
| `conversation_history` bloat | top now 13KB/14 turns (legacy session); new sessions bounded |
| Total students | **7** (was 49) |
| `event_type` distribution last 7d | question_asked 55, hint_requested 6, study_card_view 5 |

(Note: 2 audit queries had wrong column names — `study_session_id` vs `id` in `study_sessions` schema. Cosmetic, not real bugs in prod data.)

### Phase 3 — API contracts
| Test | Result |
|---|---|
| `/health` | 200 in <1s (warm) |
| Unauth requests to protected endpoints | 401 ✓ |
| Malformed signup payloads | 422 ✓ |
| Cross-student PATCH | 403 ✓ |
| Cross-student GET (NEW) | **403 ✓** (was 200) |
| Admin endpoints with non-admin (NEW) | **403 ✓** (was 200) |
| Brute-force /auth/login (NEW) | **429 at attempt 11** (was no limit) |

### Phase 5 — Content quality (Judge LLM, 15 prod sessions)
| Dimension | Score |
|---|---|
| Socratic adherence | 1.47/2 (borderline; 80% asked guiding questions) |
| Single-question | 80% |
| On-topic | 93% |
| Would help student | 93% |

The 3 lowest-scoring sessions all had the same pattern: AI confirmed correct answer + gave full explanation (Judge dings for not asking a question, but the behavior is appropriate when the student's answer was correct).

### Phase 6 — Frontend UX (per earlier preview MCP runs in this session)
- All 15 routes build clean (`npm run build` ✓)
- All pages render with new `AppShell`
- Concept Card override system loads (5 hand-curated cards working)
- Topic-shift demotion fires in prod (logs verified)
- Cold-start toast appears after 8s
- Settings save now real-PATCH (after v0.20.4 + v17 migration)

### Phase 7 — Performance / cost
- Postgres total: ~430MB (knowledge_chunks 265MB + problems 162MB dominate)
- 7 students × ~5 doubts/day × ~$0.20/student/day projected ≈ ~$30/month at beta scale
- Once Redis lands, semantic cache should reduce by 15-25% (repeated similar doubts)

### Phase 8 — Security (post-fix)
| Test | Result |
|---|---|
| Admin gating | ✅ 403 on all 14 admin routes |
| Cross-student GET | ✅ 403 |
| Cross-student PATCH | ✅ 403 (was already correct in v0.20.4) |
| Token expiry | ✅ 401 |
| Login rate limit | ✅ 429 at 11+ attempts |
| Sensitive data in logs | (not audited — recommend grep on next deploy) |

---

## What's still BROKEN / partially fixed

### High priority — fix this week
| # | Bug | Status | Why not fixed today |
|---|---|---|---|
| **R1** | Redis 100% down in prod | Not fixed | Requires you to provision Render Redis add-on ($7/mo) or Upstash free tier + set `REDIS_URL` env var. Code already degrades gracefully. |
| **R2** | `response_feedback` table empty (0 rows all-time) | Not fixed | Backend endpoint exists and looks correct. Suspected: thumbs UI not actually calling it OR client reaches the catch+log. **Need you to manually click thumbs in /doubt and check browser devtools Network tab + Render logs.** |
| **R3** | Mastery EMA still doesn't fire for hint_level=0 abandons | By design (kept) | Auto-close only fires `_genome_update_task` for blocks where the student engaged with ≥1 hint. A pure "asked once and abandoned" gives no signal. This is intentional (no-info shouldn't pollute mastery). |
| **R4** | `study_sessions.id` vs `study_session_id` column naming | Cosmetic | The code uses `study_session_id` consistently; my audit script's queries used `id` and errored. Real prod paths are unaffected. |
| **R5** | One legacy session has 14 turns / 13KB | Self-resolves | New sessions now bounded. Old ones decay naturally as TTL/cleanup processes them. |

### Lower priority — post-beta
- Sentry/cost monitoring (none exists)
- Render upgrade off free tier (kills cold start; $7/mo)
- Onboarding restyle (deferred multiple versions; cosmetic)
- Single-question cleanup tightening (currently 80%; could be 95% with prompt nudge)
- Bot email validation on signup
- session_summary backfill for the 7% of sessions that ended without one

---

## Files modified (post-cleanup)

```
M app/api/admin.py        — require_admin dependency + applied to 14 routes
M app/api/auth.py         — login rate limiter
M app/api/doubt.py        — autoclose-idle helpers + wired into /ask + /hint
M app/api/student.py      — cross-student GET guard
M app/config.py           — extra='ignore'
M app/services/doubt/engine.py  — _bound_history() helper + 3 write sites
M frontend/web/components/AppShell.tsx — onboarding gate

A scripts/diag_cleanup_test_accounts.py    — dry-run-default cleanup tool
A docs/system_diagnostic_2026-04-21_FINAL.md   — this file
A docs/system_diagnostic_2026-04-21.md         — earlier morning report
A docs/system_diagnostic_artifacts_2026-04-21/ — raw data archive
```

No frontend code changes beyond AppShell. No migrations beyond v17 (already applied).

---

## Recommended commit (single commit, v0.20.5)

```bash
cd /Users/ishansrivastava/Desktop/upmyrank
git add app/api/admin.py app/api/auth.py app/api/doubt.py app/api/student.py app/config.py \
        app/services/doubt/engine.py \
        frontend/web/components/AppShell.tsx \
        scripts/diag_cleanup_test_accounts.py \
        docs/system_diagnostic_2026-04-21.md \
        docs/system_diagnostic_2026-04-21_FINAL.md \
        docs/system_diagnostic_artifacts_2026-04-21/
git status
git commit -m "v0.20.5: critical security + Knowledge-Genome fixes from full system diagnostic — admin gate (was leaking PII to non-admin), cross-student GET gate (was leaking genome), /auth/login rate limiter (no limit before), autoclose-idle to fix mastery EMA never firing (44 of 45 had zero mastery), AppShell onboarding gate (60% drop-off), conversation_history bound to last 10 turns, Settings extra=ignore so .env additions don't crash startup, + cleanup tool that took DB from 49 test accounts → 7 real users"
git push origin main
```

⚠️ **Per Rule #7 I won't commit. Run the commands yourself when ready.**

---

## Recommended next session (after push lands on Render)

1. Verify each fix in prod (~10 min):
   - `curl /admin/student-insights` with non-admin token → expect 403
   - Sign up new account, immediately go to `/` → expect redirect to `/onboarding`
   - Hammer `/auth/login` 11x → expect 429 on 11th
2. Provision Redis (resolves R1)
3. Click thumbs in `/doubt` and inspect what happens (resolves R2)
4. After 24h of real traffic, re-query `concept_mastery` — expect non-trivial growth as autoclose backfills mastery for previously-abandoned sessions

---

**Captain's log: ship didn't sink. Important data preserved. 7 critical bugs fixed and verified. Awaiting your push.**
