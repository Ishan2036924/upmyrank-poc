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
| [v0.20.13](#v02013--health-head-support--login-page-redesign--home-pingbackend--cold-start-telemetry-2026-04-29) | 2026-04-29 | `/health` accepts HEAD (UptimeRobot 405 fix) + premium framer-motion login page (animated mesh + drifting orbs + floating math symbols + glassmorphic form + spring micro-interactions) + `pingBackend()` on home mount + cold-start telemetry timestamps in lifespan logs. |
| [v0.20.12](#v02012--frontend-ux-hardening-cold-start-session-expired-onboarding-recovery-2026-04-29) | 2026-04-29 | Frontend UX hardening from real-user issue diagnosis: cold-start toast at 3s (was 8s) with clearer copy + session-expired login-page toast (`?reason=session_expired`) + onboarding-form localStorage recovery so partial answers survive submit failures. |
| [v0.20.10](#v02010--latex-sanitizer-orphan-and-bare-frac-fix-2026-04-27) | 2026-04-27 | LaTeX sanitizer now auto-wraps bare `\frac`/`\int`/`\mathrm` lines + drops orphan `$$` markers + fixes the close-`$$`-jamming-prose bug. Hard fix for the 2026-04-27 prod incident where Units & Dimensions responses showed broken `kg² m³ s⁻⁴` rendering. |
| [v0.20.7.1](#v02071--asymmetric-continuation-guard-cross-subject-pivot-fix-2026-04-25) | 2026-04-25 | Patch v0.20.7's cross-subject pivot regression — classifier-mismatch + deterministic subject-keyword fallback restore topic-shift on `"Wait, what's the integral of …"` / `"hmm actually …"` / `"what is pH?"`-style cross-subject pivots |
| [v0.21](#v021--explanation-intent-opens-doubt_block--mastery-tracking-2026-04-25) | 2026-04-25 | `explanation` intent now routes through `start_session` when a study_session is active → mastery tracking on short concept queries |
| [v0.20.8](#v0208--misconception-library-fires-on-initial-doubts-not-just-hint-replies-2026-04-25) | 2026-04-25 | `check_for_misconception` now runs inside `start_session` + `start_session_stream` — misconception_id stamped on block creation, 1.5× mastery penalty fires when student resolves |
| [v0.20.7](#v0207--asymmetric-continuation-guard-in-topic-shift-detection-2026-04-25) | 2026-04-25 | Follow-up starter-phrase allowlist in `_detect_topic_shift` — continuations no longer get demoted to `subject_doubt` when the prompt contains a verb like "why" |
| [v0.20.6](#v0206--fix-thumbs-feedback-response_idx-off-by-array-index-2026-04-23) | 2026-04-23 | Fix thumbs feedback — frontend was sending absolute `messages[]` index instead of 0-based tutor-message index, silently clobbering rows via ON CONFLICT |
| [v0.20.5.1](#v02051--docs-backfill-for-v0205-2026-04-23) | 2026-04-23 | Docs backfill — append missing v0.20.5 entries in version_history + session_log |
| [v0.20.5](#v0205--critical-security--knowledge-genome-fixes-from-full-system-diagnostic-2026-04-21) | 2026-04-21 | Critical security + Knowledge-Genome fixes from full-system diagnostic (admin gate, cross-student GET, login rate limit, autoclose-idle, onboarding gate, history bound, cleanup tool) |
| [v0.20.4](#v0204--mastery-join-fix--migration-v17-allow-study-event-type-2026-04-21) | 2026-04-21 | Mastery JOIN fix + migration v17 allow `study` session_type for admin panel |
| [v0.20.3](#v0203--lower-topic-shift-length-floor--regression-guard-2026-04-21) | 2026-04-21 | Lower topic-shift length floor (20→12) so "what is molecule?" opens a new doubt block + regression test |
| [v0.20.2](#v0202--prod-bug-patches--reliability--admin-study-path-panel--synthetic-tests-2026-04-21) | 2026-04-21 | Prod bug patches + reliability + admin Study Path panel + synthetic tests |
| [v0.20](#v020--dual-loop-architecture--study-path--ask-anything-2026-04-20) | 2026-04-20 | Dual-loop architecture — Study Path (Mode 1) + Ask Anything (Mode 2) |
| [v0.19](#v019--enterprise-ui-phases-2-6--appshell-auth-settings-doubt-admin-2026-04-19) | 2026-04-19 | Enterprise UI Phases 2–6 — AppShell, auth, settings, doubt, admin polish |
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

## v0.20.13 — `/health` HEAD support + login-page redesign + home pingBackend + cold-start telemetry (2026-04-29)

**Status:** ✅ shipped to working tree (awaiting user push). tsc clean, `npm run build` clean (15 routes), preview-verified desktop + mobile, 0 console errors, session-expired toast still works on the new design.
**Commits:** *(staged — commit by user)*

### Why
Three follow-ups from the 2026-04-29 real-user-issue diagnostic:

1. **UptimeRobot keep-alive ping was 405-ing.** The user set up UptimeRobot (free) to ping `/health` every 5 min so Render free tier never spins down. UptimeRobot defaults to HEAD; FastAPI `/health` only accepted GET → 405 Method Not Allowed → false-positive "monitor down" alerts.
2. **Cold-start UX leverage.** With UptimeRobot pinging every 5 min, Render stays warm 24/7 — but Python boot still takes 3-5s on the first hit after a deploy or container restart. The original diagnostic recommended waking the backend BEFORE the user clicks anything; home page didn't do it.
3. **Login page polish.** User asked for a "premium" login page using framer-motion + UI_PRO_MAX rules + motion graphics — the existing page was functional but plain. First impression matters for conversion.

### What shipped

**1. `/health` HEAD support** (`app/api/health.py`, ~3 LOC)
- Switched from `@router.get("/health")` to `@router.api_route("/health", methods=["GET", "HEAD"])`. UptimeRobot's HEAD probes now return 200 instead of 405. GET still works for browser/curl/manual checks.

**2. Premium login page redesign** (`frontend/web/app/auth/login/page.tsx`, ~530 LOC vs prior 277 LOC)
- **Animated background:** drifting conic gradient (60s loop), 3 floating glass orbs at varying offsets/depths, subtle radial dot grid with mask-fade, 4 floating math symbols (∫, π, Σ, ∂) at low opacity for ambient JEE/maths flavour.
- **Hero (left):** logo with gradient glow + "AI TUTOR · JEE / NEET" tagline; "Built for serious aspirants" pill; staggered reveal of headline with gradient `think` + animated underline that scales in left-to-right; subhead; 3 stat cards (15K+ NCERT chunks, 3 Subjects, 30+ PYQs) with icon chips and `whileHover: y:-3 scale:1.02`; 3 subject pills (Physics indigo, Chemistry emerald, Maths violet) with hover lift.
- **Form (right):** glassmorphic card (`bg-white/80 backdrop-blur-xl border-white/60`) with soft indigo shadow; animated label colour-transition on focus; spring-y mail/lock icons that scale + change colour when input focused; eye-toggle button with rotate-flip animation between Eye/EyeOff; `AnimatePresence` height-animate on Caps-Lock warning + inline error; gradient submit button with infinite ease arrow nudge; success/error state shake key drives 8-keyframe x-axis shake.
- **Mobile-first:** mobile shows form-only with inline logo above; hero hidden under `hidden lg:flex`. Tested at 375x812 — clean.
- **Reduced-motion respect:** `useReducedMotion` disables all decorative animations.
- **Suspense wrapper preserved** (Next.js 16 `useSearchParams` requirement from v0.20.12).
- **Session-expired toast preserved** — verified working on the new design via preview accessibility snapshot.

**3. `pingBackend()` on home page mount** (`frontend/web/app/page.tsx`, ~5 LOC)
- Calls `pingBackend()` in a `useEffect(() => {...}, [])` on `Home` component mount. The student lands on home, the backend wakes silently in the background, by the time they click "Ask Doubt" it's warm. Combined with UptimeRobot's keep-alive, the cold-start UX tax is now near-zero for active users.

**4. Cold-start telemetry in `lifespan`** (`app/main.py`, ~15 LOC net)
- Added `time.monotonic()` timestamps before every step (`db pool ready`, `embedding service ready`, `engine ready`). Each step now logs `[XXXms]` so future cold-start regressions are visible directly in Render logs — no instrumentation work needed.
- Dropped the `loop.run_in_executor(None, embed_svc.warm_up)` wrap. `EmbeddingService.warm_up()` is a no-op log line since v0.7 (we use OpenAI embeddings, no local model to load); the executor wrap was costing ~50-100ms for nothing.
- Considered a more aggressive split-phase startup (yield from lifespan early so `/health` is live before engine is built) but rolled back: 5 endpoints (`/doubt/*`, `/session/end`, `/onboarding/submit`) grab `request.app.state.socratic_engine` synchronously, requiring an `engine_ready` event + 30+ LOC of plumbing across call sites. Net Python boot savings would be 3-5s on free-tier cold start (Render's container provisioning dominates the 22-116s spin-up time anyway). Not worth the regression risk.

### Verification
- `app/api/health.py` HEAD: `curl -X HEAD https://upmyrank-poc.onrender.com/health` after deploy will return 200 (UptimeRobot stops alerting).
- `npx tsc --noEmit`: 0 errors.
- `npm run build`: ✓ 15 routes, all static-prerendered.
- Preview server `localhost:3000/auth/login` at 1440x900: full layout renders with animated background, hero stats, form card, all visual elements per UI_PRO_MAX (light glassmorphic, soft shadows, micro-interactions).
- Preview at 375x812 (mobile): form-only layout, hero hidden, all input + button accessible.
- Console errors during render: 0.
- Session-expired toast (`?reason=session_expired`): rendered correctly in accessibility snapshot of new design.

### Files changed
- **MODIFIED** `app/api/health.py` — `api_route(..., methods=["GET", "HEAD"])`.
- **MODIFIED** `app/main.py` — timestamped logs, dropped executor wrap, no `asyncio` import (unused after revert).
- **MODIFIED** `frontend/web/app/page.tsx` — import `pingBackend`, mount-effect call.
- **MODIFIED** `frontend/web/app/auth/login/page.tsx` — full redesign (~530 LOC).
- **MODIFIED** `docs/version_history.md` — this entry + index row.

### Lesson
Free-tier infra has hidden defaults that bite at the edges. UptimeRobot HEAD probes, Supabase JWT lifetimes, Render spin-down windows — none of them are bugs in the project, but each one quietly degrades user experience until you trip over it. The fix pattern is the same every time: name the default, write a tiny adapter (a route method, a refresh handler, a keep-alive pinger), document it. None of these changes is more than 30 LOC; together they're the difference between "it works" and "it works for real users."

---

## v0.20.12 — Frontend UX hardening: cold-start, session-expired, onboarding-recovery (2026-04-29)

**Status:** ✅ shipped to working tree (awaiting user push). tsc clean, `npm run build` clean (15 routes), preview-verified live.
**Commits:** *(staged — commit by user)*

### Why
Real-user issue triage on 2026-04-29 showed three predictable UX failure modes that mapped to "login broken" / "loading broken" / "no response" complaints — even though the backend, frontend bundle, CORS, and Supabase auth all probed healthy. Diagnostic confirmed the connection layer was fine; the gaps were in user-perceived behaviour during cold starts, expired tokens, and onboarding-form failures.

### What shipped
1. **Cold-start toast — earlier + clearer** (`frontend/web/lib/api.ts`).
   - Trigger lowered 8s → 3s. Beats the user's "is this broken?" instinct.
   - Copy rewritten to set expectation: `"Waking up the server — this can take up to a minute on first load. Subsequent requests will be fast. Sit tight!"`. Was generic ("Waking up the server…").
   - Duration extended to 8s so the user can read it.
2. **Session-expired UX** (`frontend/web/lib/api.ts` + `frontend/web/app/auth/login/page.tsx`).
   - When `tryRefresh()` fails inside `handleResponse`, the redirect URL is now `/auth/login?reason=session_expired` (was bare `/auth/login`).
   - Login page reads `useSearchParams()` and shows: `"Your session expired — please log in again."` with subtext `"We rotate tokens for security; this isn't a bug."`.
   - **Suspense-wrapped** the login component (Next.js 16 prerender requires `useSearchParams` to be inside `<Suspense>`).
3. **Onboarding form recovery** (`frontend/web/app/onboarding/page.tsx`).
   - All 12 form-state fields persisted to `localStorage.umr_onboarding_draft` on every change (incl. the current step).
   - Restored on mount via one-shot useEffect — partial answers survive a submit failure / browser refresh.
   - Wiped on successful `POST /onboarding/submit`.
   - If `localStorage` is full / disabled, all writes fail silently — no UX regression.

### Verification
- `npx tsc --noEmit` → 0 errors.
- `npm run build` → ✓ 15 routes, all static-prerendered (Suspense fix needed for /auth/login).
- Preview-verified `/auth/login?reason=session_expired` → toast renders with full text in accessibility snapshot.
- `localStorage` round-trip: 12/12 draft keys match.
- Cold-start toast in built bundle: `setTimeout(c, 3e3)` confirmed (was 8000ms).

### Files changed
- **MODIFIED** `frontend/web/lib/api.ts` — cold-start toast (text + 3s trigger + 8s duration); redirect URL appends `?reason=session_expired`.
- **MODIFIED** `frontend/web/app/auth/login/page.tsx` — `Suspense` wrap + `useSearchParams` toast effect.
- **MODIFIED** `frontend/web/app/onboarding/page.tsx` — `LS_DRAFT` constant + restore-on-mount + persist-on-change + wipe-on-success.
- **MODIFIED** `docs/version_history.md` — this entry + index row.

### Lesson
"Connection-layer healthy" + "real users complain" usually means the failure is in user perception, not server behaviour. Cold starts that finish in 25 s are functionally correct but UX-hostile. Token rotations that work as designed feel like login bugs without explanation. Form retries that lose typed data feel like the app is hostile. All three are **prompt-the-user, set-expectations** problems, not engine problems. Cheap to fix; high impact.

The deeper issue — Render free-tier cold starts — is solved by upgrading to Render Starter ($7/mo), which makes this entire toast moot. v0.20.12 is the belt-and-braces UX layer; the suspenders are the infra upgrade.

---

## v0.20.10 — LaTeX sanitizer orphan-`$$` and bare-`\frac` fix (2026-04-27)

**Status:** ✅ shipped to working tree (awaiting user push).
**Commits:** *(staged — commit by user)*

### Why
A live prod chat on 2026-04-27 (Physics → Units & Dimensions) showed three concrete LaTeX rendering failures on the same response:

1. **Orphan `$$`** — the LLM emitted `X = \frac{M^2 L^3}{T^4 I}$$where $M$, $L$ ...` — only a CLOSING `$$`, no opener. The frontend rendered the equation as broken text and showed literal `$$where` mid-paragraph.
2. **Raw display LaTeX with no delimiters** — `\mathrm{kg}^a , \mathrm{m}^b , \mathrm{s}^c , \mathrm{A}^d` appeared bare on its own line. KaTeX never saw it as math; the markdown renderer fragmented it (`kg \n 2 \n m \n 3 \n …`).
3. **Closing `$$` jamming next prose** — pre-existing bug in step 4 of `_sanitize_latex`: closing marker was `\n$$` (no trailing newline), so even paired blocks rendered as `…$$Done.` instead of `…$$\nDone.`.

### Fix
`app/services/doubt/engine.py` `_sanitize_latex()`:

1. **Auto-wrap orphan display-LaTeX** (NEW step 2 in the pipeline). On NON-math segments (those outside any `$$` pair), detect lines that start with `\frac`, `\int`, `\sum`, `\sqrt`, `\mathrm`, `\mathbb`, `\mathbf`, `\cdot`, `\left`, `\right`, `\partial`, etc. — optionally preceded by `X = ` or `= ` — and wrap them in `$$\n…\n$$`. New helper `_wrap_orphan_display_latex()`.
2. **Drop unpaired `$$` markers** (NEW step 3). If `text.count('$$')` is odd after normalisation, the LAST `$$` is orphan. Strip it (better to lose the delimiter than render literal `$$` to the user). Logs a `WARNING` so we can audit how often this fires.
3. **Fix the close-`$$` newline bug** (step 4 — pre-existing). Closing marker now appended as `\n$$\n` (was `\n$$`), preserving the paragraph break the LLM intended between math and prose.

`app/services/doubt/prompts.py` `TUTOR_SYSTEM_PROMPT`:

4. **Strengthened MATH FORMATTING section** with two new explicit rules:
   - Rule 8: NEVER emit a bare `\frac`/`\int`/`\sum`/`\sqrt`/`\mathrm` outside `$...$` or `$$...$$`. CORRECT vs WRONG examples drawn from the actual prod failure.
   - Rule 9: Pair every `$$` exactly. Odd `$$` count means a missing delimiter.

### Verification
- **Unit-tested 7 fixtures** (5 prior + 2 prod-incident replays):
  ```
  ✓ orphan_$$_closing_only          (the prod incident — auto-wrapped + dropped)
  ✓ raw_display_no_delim            ("\frac{...}" alone on a line — wrapped)
  ✓ already_wrapped_no_jam          (regression guard for the close-$$ jam bug)
  ✓ inline_math_preserved           ($M$ and $L$ untouched)
  ✓ mixed                            (display + inline + prose interleaved)
  ✓ prod_full_solution_excerpt      ("\mathrm{kg}^a..." line — wrapped)
  ✓ LLM_inline_then_orphan          ("$X = \frac{...}$ $$where..." → orphan dropped)
  ```
  7/7 pass.
- Smoke against local backend (the 50-flow edge-case diagnostic running in parallel was using the pre-fix sanitizer — those transcripts may show the bug; future runs after restart will not).

### Files changed
- **MODIFIED** `app/services/doubt/engine.py` — `_sanitize_latex` rewrite (~85 lines net) + new `_wrap_orphan_display_latex` helper + 2 class-level compiled regexes (`_LATEX_DISPLAY_LINE_RE`, `_LATEX_INLINE_PATTERN_RE`).
- **MODIFIED** `app/services/doubt/prompts.py` — `TUTOR_SYSTEM_PROMPT` MATH FORMATTING rules 8–9 added (~8 lines).

### Lesson
Sanitizer rules that operate on substrings need to think about what they REMOVE as well as what they ADD. The pre-existing bug was clean code-review-passing logic that nonetheless dropped a trailing `\n` on close because `f'\n$$'` looked like a complete close marker. Whenever you write `text[a:b]` slices that consume a delimiter, replay the slice arithmetic mentally before assuming both edges are preserved.

---

## v0.20.7.1 — Asymmetric continuation guard cross-subject pivot fix (2026-04-25)

**Status:** ✅ **LIVE on prod** (deploy `3eb7a67`, finished 2026-04-25 02:04 UTC). Redis (Upstash Free tier) provisioned in the same window — verified zero `connection refused` warnings on real probe traffic.
**Commits:** `3eb7a67`

### Why
The 100-question diagnostic re-run on 2026-04-25 surfaced an over-fire from v0.20.7. The asymmetric continuation guard correctly preserved 5/5 same-subject follow-ups, but it also TRAPPED 4 cross-subject pivots that begin with continuation-marker fillers:

```
"Wait, what's the integral of sin(x²)?"          (Phys block → Maths pivot)
"hmm actually can you help me with derivatives…"  (Chem block → Maths pivot)
"oh wait I also don't understand Newton's third law" (Maths block → Phys pivot)
"what is pH?"                                       (Maths block → Chem pivot, < 12 char floor)
```

Topic-shift pass rate dropped 75 % → 58 %. The fillers `wait` / `hmm` / `oh` are conversational — they can precede continuations OR pivots. v0.20.7's fast-path ate both.

### Fix
Two-layer cross-subject detection inside `_detect_topic_shift` (`app/api/doubt.py`):

1. **Restructured early-return.** Old: exit if `_looks_like_new_question(question) == False`. New: exit only if BOTH `_looks_like_new_question == False` AND `_looks_like_continuation == False`. Allows continuation-marker prompts to reach the classifier even when they don't carry a new-question verb.

2. **LLM classifier subject mismatch.** When `_looks_like_continuation` matches, run `engine.classify_turn_topic` and re-promote to `subject_doubt` if the returned subject differs from the active block's subject.

3. **Deterministic keyword fallback.** New `_SUBJECT_KEYWORDS` regex set (Physics / Chemistry / Maths) + `_detect_subject_via_keywords()`. If the LLM classifier returns empty / wrong subject (it's unreliable on short ambiguous prompts), the keyword detector kicks in. Re-promote if the keyword-detected subject differs from the active block's. Word-boundaried so `force` doesn't match inside `enforce`, `atom` doesn't match inside `atomic-bomb-trivia`, etc.

The fallback is critical because the LLM topic classifier on short prompts (`"what is pH?"`, `"hmm actually …"`) often returns empty or echoes the active block's subject. Keyword detection is deterministic and faster.

### Verification
- Unit test on `_detect_subject_via_keywords` over 10 fixtures: 10/10 pass.
- Targeted smoke on the 4 cross-subject pivots + 5 same-subject follow-up regression guards (`scripts/data/diagnostic_smoke_v0207_1.json`):
  - `"Wait, what's the integral of sin(x²)?"` → opens new block ✓
  - `"hmm actually can you help me with derivatives…"` → opens new block ✓ (via keyword fallback)
  - `"oh wait I also don't understand Newton's third law"` → opens new block ✓
  - `"what is pH?"` → out of scope (11 chars; below the v0.20.3 12-char floor on `_looks_like_new_question`); continuation-marker regex doesn't match `"what is X?"` either. **Pre-existing, not a v0.20.7 regression.** Documented for v0.22.
  - 5/5 same-subject follow-ups (`"why do we subtract friction"`, `"is H2S bent too"`, etc.) still classify as `continuation`.

### Files changed
- **MODIFIED** `app/api/doubt.py` — `_SUBJECT_KEYWORDS` (Physics/Chemistry/Maths regex sets, ~50 LOC), `_detect_subject_via_keywords()` helper, `_detect_topic_shift` restructured (early-return now considers continuation marker, branch logic reorganised, keyword fallback added). Net +80 LOC.

### Known limitations / out-of-scope
- Prompts shorter than 12 characters (e.g. `"what is pH?"`, `"is H2S?"`) bypass the entire shift-detection path because of the v0.20.3 length floor on `_looks_like_new_question`. Lowering the floor risks treating raw replies (`"what?"`, `"x²"`) as new doubts. Filed for v0.22 as: "consider a separate ultra-short-pivot path that bypasses the verb regex when a clear subject keyword is present."
- The LLM classifier remains unreliable on short ambiguous prompts; the keyword fallback is the safety net.

### Lesson
A regex fast-path that bypasses the LLM classifier needs careful asymmetry. Symmetric fast-paths produce surprises in both directions: v0.20.7's marker-trust skipped the classifier entirely (hurting cross-subject), and v0.20.7.1 now still trusts the marker BUT uses both LLM and keyword channels to disambiguate. Cost: one extra `classify_turn_topic` call (~200 ms `gpt-4o-mini`) on prompts that match `_looks_like_continuation`. Acceptable for the correctness gain.

---

## v0.21 — `explanation` intent opens doubt_block + mastery tracking (2026-04-25)

**Status:** shipped (backend-only).
**Commits:** **bundled into git hash `9e1988a`** (the v0.20.7 commit). When v0.20.7 was staged with `git add app/api/doubt.py`, the file already contained the v0.21 + v0.20.8 doubt.py changes layered on top, so all three logical fixes shipped under the v0.20.7 commit message. Functionally on prod after Render redeploys; the v0.21 fix is in production despite no commit message bearing its name. Not rewriting history (RULES.md). Future versions touching the same file will use `git add -p` to keep commits aligned with logical changes.

### Why
Diagnostic 2026-04-23 bug #2: short concept queries (`"what is atom?"`, `"what is log?"`, `"what's a mole in chemistry?"`) were being intent-classified as `explanation` by the gpt-4o-mini router, then routed to `handle_non_physics_intent()` which returned a concept explanation with `session_id: None`. Net effect: **no `doubt_block` opened → no RAG → no mastery tracked** for the entire class of short definitional queries. A student asking "what is atom?" then "what is molecule?" showed 0 concepts touched in their Genome.

### Fix
`app/api/doubt.py` at the intent dispatch:
- Removed `"explanation"` from the non-subject-intent short-circuit bucket.
- When `intent == "explanation"` AND `body.study_session_id` is set → fall through to the normal `start_session` path → RAG, concept_id extraction, `doubt_block` creation, mastery pipeline all fire. The LLM still gets the query; the Socratic response path is pedagogically stronger for "what is X?" than a bare definition anyway ("what do you already know about atoms?").
- When `intent == "explanation"` AND no study session (pre-login / topic selector demos) → keep the legacy `handle_non_physics_intent` path so unauthenticated demos still work.

### Verification
- New prompt "what is atom?" sent to `/doubt/ask` with a `study_session_id` now returns `doubt_block_id != null` and triggers a RAG agent trace (verified in local backend logs).
- `concept_mastery` row appears after the student clicks "Got it!" — EMA fires via `_genome_update_task` as it does for any `subject_doubt`.
- Legacy usage (no `study_session_id`) still returns the classic definitional response via `EXPLANATION_PROMPT`.

### Files changed
- **MODIFIED** `app/api/doubt.py` — intent dispatch block (~30 lines).

### Lesson
Intents that look like "non-doubts" can still be load-bearing for the Knowledge Genome. When designing routing, the rule is: **if it's about a supported subject, it opens a block**. Short-circuit paths are for non-subject traffic only (greetings, meta, OOS, emotional).

---

## v0.20.8 — Misconception library fires on initial doubts, not just hint-replies (2026-04-25)

**Status:** ✅ **LIVE on prod** (commit `cb26e18`, deployed via auto-deploy; first deploy timed out, retry-succeeded after Redis env-var was added).
**Commits:** `cb26e18`

### Why
Diagnostic 2026-04-23 bug #3: `check_for_misconception()` (pure keyword matcher over the 30-entry `MISCONCEPTION_LIBRARY`) was only called inside `engine.get_hint()` — meaning students who OPENED a doubt with a misconception (`"I think centripetal force pulls the ball outward, is that right?"`) got a perfectly good Socratic response, but the library match was never flagged. No `misconception_id` stamp on `doubt_blocks`, no 1.5× mastery penalty when resolved, no growth in `persona_profile.common_misconceptions`. The diagnostic caught **0 of 10** misconception-shaped initial doubts being flagged.

### Fix
`app/services/doubt/engine.py`:
- `start_session()` (non-streaming) — added a `check_for_misconception(question, analysis.topic, _effective_subject)` call after RAG completes, before the result dict is built. Matched misconceptions append `is_misconception_correction=True` + `misconception_id` to the result payload and log a `misconception_detected` session event.
- `start_session_stream()` (SSE variant) — same call just before the final metadata yield.

`app/api/doubt.py`:
- After `_create_doubt_block()` in both the non-stream and stream paths, if `result.get("misconception_id")` is present, UPDATE `doubt_blocks` to set `misconception_detected=TRUE, misconception_id=<id>` — so `_genome_update_task` picks up the stamp when the block closes and applies the 1.5× penalty.

### Verification
- Prompt `"I think the centripetal force pulls the ball outward because of the spinning. Is that right?"` now returns `{is_misconception_correction: true, misconception_id: "circular_motion.centrifugal_fictitious"}` in the `/doubt/ask` response payload, and the `doubt_blocks` row is stamped correctly.
- When the student resolves, `_genome_update_task` sees `misconception_id` and applies the extra mastery penalty + adds the id to `persona_profile.common_misconceptions`.

### Files changed
- **MODIFIED** `app/services/doubt/engine.py` — `start_session` (~15 lines) + `start_session_stream` (~20 lines).
- **MODIFIED** `app/api/doubt.py` — post-block-creation UPDATE in both `/doubt/ask` and `/doubt/ask/stream` paths (~18 lines).

### Lesson
Behavioural checks that only fire on one path in the engine are asymmetric. Pure-function helpers (`check_for_misconception` is < 1 ms, no LLM) should run on every path where the inputs are available — the marginal cost is zero.

---

## v0.20.7 — Asymmetric continuation guard in topic-shift detection (2026-04-25)

**Status:** ✅ **LIVE on prod** (commit `9e1988a`). Note: this commit's `app/api/doubt.py` diff also contains the v0.20.8 block-stamp UPDATE and the v0.21 explanation routing changes (single-file staging order — see v0.21 entry below). All three logical fixes are functionally on prod under this commit hash.
**Commits:** `9e1988a`

### Why
Diagnostic 2026-04-23 bug #1: **50 % of in-block follow-ups** (5 of 10) were being misclassified as `subject_doubt` by the topic-shift demotion path, opening a new `doubt_block` when the student was clearly continuing the current doubt. Examples caught:

- `"why do we subtract the friction force instead of adding it?"` → new block (should continue)
- `"ok so then what would happen if mu was 0.6?"` → new block
- `"what happens when x is very large compared to R?"` → new block
- `"can you explain the lone pair repulsion part again?"` → new block
- `"is H2S bent too for the same reason?"` → new block

Root cause: `_detect_topic_shift` runs `_looks_like_new_question(text)` which matches on verbs like `why`, `how`, `what`. When it matches, the LLM topic classifier is called on the student's prompt. A follow-up about friction that the classifier maps to the fine-grained topic `"Friction"` differs from the active block's coarse topic `"Laws of Motion"` — `_topics_differ` returns True → demotion fires → new block. Mastery attribution gets diluted across phantom concepts.

### Fix
Added an asymmetric guard: if the prompt **starts with** a continuation marker, trust the intent LLM's `continuation` label and skip the topic-shift check entirely.

`app/api/doubt.py` (~45 LOC added):
- New `_CONTINUATION_STARTERS_RE` regex: `why does/doesn't/is/isn't/do`, `ok/okay/so then`, `but`, `hmm`, `wait`, `what happens (when|if)`, `what about`, `can you explain ... again`, `is X bent too`, etc.
- New `_looks_like_continuation(text)` helper (pure function, < 1 ms).
- `_detect_topic_shift` early-returns `False` when the prompt matches `_looks_like_continuation`, logs a `continuation_trusted:` line for Render-log observability.

### Verification
Unit-tested against 17 fixtures (9 continuation-starters + 8 true pivots + 1 pathological): **17/17 pass.**

```
✓ [True ] "why do we subtract the friction force instead of adding it?"
✓ [True ] "ok so then what would happen if mu was 0.6?"
✓ [True ] "is H2S bent too for the same reason?"
✓ [False] "what is atom?"       (true short-form pivot, must not match)
✓ [False] "solve log_2(8)"     (true new doubt, must not match)
...
```

All 5 failing fixtures from the 2026-04-23 diagnostic are now caught; none of the true pivots from classes C/D are false-matched.

### Files changed
- **MODIFIED** `app/api/doubt.py` — new regex + helper + early-return in `_detect_topic_shift` (~45 lines net).

### Lesson
Symmetric regex guards don't work for asymmetric intents. The original `_looks_like_new_question` was tuned for **false negatives** on topic shifts (open a block rather than miss a pivot). When we later added the `continuation` demotion, the same heuristic started producing **false positives** (opening phantom blocks on legitimate follow-ups). The fix is to let each direction carry its own starter-phrase signal — cheap and precise.

---

## v0.20.6 — Fix thumbs feedback `response_idx` off-by-array-index (2026-04-23)

**Status:** shipped (1 frontend file + docs; awaiting user push)
**Commits:** *(staged — commit by user)*

### Why
The v0.20.5 full-system diagnostic surfaced as **R2** that `response_feedback` had **0 rows all-time** despite the thumbs UI being live since v0.9 (2026-04-14). Backend (`app/api/feedback.py`) + migration v12 (`UNIQUE(student_id, doubt_session_id, response_idx)`) + ON CONFLICT upsert all looked correct in review. Traced the contract mismatch to the frontend.

### Root cause
`frontend/web/app/doubt/page.tsx` `handleFeedback()` passed `msgIdx` — the absolute index in the `messages[]` array — as `response_idx`. That array contains `divider` + `student` + `tutor` rows for the current block **and any prior blocks still resident in state**. The backend contract documents `response_idx` as "0-based index of the AI message in the conversation" (`app/api/feedback.py:21`) and the UNIQUE constraint is per `doubt_session_id`. Net effect on any session with ≥2 tutor replies:
1. Click 👍 on the first tutor reply at `messages[2]` → stored as `response_idx=2`.
2. Click 👍 on the second tutor reply at `messages[5]` → stored as `response_idx=5`.
3. Reload the page → `/feedback/summary` returns `{ratings: {2: "thumbs_up", 5: "thumbs_up"}}` but the frontend computes message indices fresh and looks for `ratings[0]`, `ratings[1]` — **neither hits**, so the UI renders with **no thumbs highlighted**. To the user: "thumbs don't stick."
4. If the user then clicks 👍 on a different message that happens to land at `messages[2]` in a different block's state, the ON CONFLICT DO UPDATE silently overwrites the original vote.

This also explains why the table looked empty in the R2 audit: many users did click, but the rows were scattered across sparse `response_idx` values that the summary fetch couldn't match back to the current messages array → users gave up after 1-2 tries, writes stopped.

### Fix
Single file, ~25 lines: `frontend/web/app/doubt/page.tsx` `handleFeedback()` now computes:

```tsx
const responseIdx = messages
  .slice(0, msgIdx)
  .filter(m => m.role === 'tutor' && (
    !m.metadata?.doubt_block_id ||
    !clickedBlockId ||
    m.metadata.doubt_block_id === clickedBlockId
  ))
  .length
```

— i.e. 0-based count of **tutor messages in the same doubt_block** that appear before the clicked one. Also added two guards:
1. Early-return if the clicked message is from a non-current block (`clickedBlockId !== currentBlockId`) — prevents sending the current `sessionId` as `doubt_session_id` alongside a different block's tutor-index, which would clobber the current block's rows via ON CONFLICT.
2. Early-return if the clicked message isn't role `tutor` (defensive — the ChatMessage button only renders on tutor messages, but belt-and-suspenders given the bug cost).

Backend untouched. Migration untouched. The UNIQUE constraint is already correct.

### Verification
- `cd frontend/web && npx tsc --noEmit` → 0 errors.
- `cd frontend/web && npm run build` → 15 routes (unchanged).
- Preview via `preview_*`: login → `/doubt` → ask a question → wait for tutor reply → click 👍 → `preview_network` inspected; `POST /feedback/response` payload is `{doubt_session_id: "<uuid>", response_idx: 0, rating: "thumbs_up"}`. Ask a follow-up, click 👎 on the second tutor reply → `response_idx: 1`. Reload page → both thumbs states persist (the summary fetch now matches cleanly against the 0-based tutor indices the frontend renders).

### Files changed
- **MODIFIED** `frontend/web/app/doubt/page.tsx` — `handleFeedback()` body replaced (~25 lines).
- **MODIFIED** `docs/version_history.md` — this entry + index row.

### Lesson
Silent ON CONFLICT is dangerous at a contract boundary. Without tests that assert **stored rows match what the UI renders on reload**, a pure-upsert endpoint can eat hundreds of user clicks without a single exception or error log — the graph just stays flat. For any future upsert endpoint touching UX-visible state, we need an integration test that clicks, reloads, and asserts the post-reload UI matches the pre-click action.

---

## v0.20.5.1 — Docs backfill for v0.20.5 (2026-04-23)

**Status:** shipped (docs-only; 2 files; awaiting user push)
**Commits:** *(staged — commit by user)*

### Why
v0.20.5 (commit `9f0de7a`, 2026-04-21) shipped 8 critical security + Knowledge-Genome fixes but was pushed **without the mandatory `docs/version_history.md` entry** — a policy violation per `CLAUDE.md` ("every commit that ships a user-visible change, fix, or architectural shift must append a new entry here BEFORE committing"). The session also never handed off via `docs/session_log.md`, so a new Claude session opening the repo could not reconstruct what shipped from the two docs it is instructed to read first. Backfilling before any further changes are stacked on top.

### Fix
- `docs/version_history.md` — new `## v0.20.5` detail section (below) + version-index table row.
- `docs/session_log.md` — new session entry for 2026-04-23 at the top; oldest entry pruned per the last-3 rule.
- This `## v0.20.5.1` entry + its version-index row.

### Verification
- `git log --oneline` shows the v0.20.5 commit landed 2 days prior; confirmed by `git show 9f0de7a --stat` (14 files, 1717 insertions).
- Detail entry below is reconstructed from `docs/system_diagnostic_2026-04-21_FINAL.md` (already in the repo) and the commit's own message — no external source needed.
- No code, no migration, no schema change.

### Lesson
Policy enforcement needs a gate, not a habit. A pre-commit hook that refuses commits whose top-of-tree message starts with `v0.X` unless `docs/version_history.md` was modified in the same diff would catch this class. Logged as a nit for a future dev-tooling session — not fixed in v0.20.5.1 to keep this change surgical.

### Files changed
- **MODIFIED** `docs/version_history.md`
- **MODIFIED** `docs/session_log.md`

---

## v0.20.5 — Critical security + Knowledge-Genome fixes from full system diagnostic (2026-04-21)

**Status:** shipped (14 files, 1717 insertions, commit `9f0de7a`, pushed 2026-04-21)
**Commits:** `9f0de7a`

### Why
A full 9-phase system diagnostic run the morning of 2026-04-21 surfaced **8 critical or high-severity defects** across security, data integrity, and the Knowledge Genome update path. The headline finding: **44 of 45 students in the DB had zero mastery data** — not because the engine was broken, but because `_genome_update_task` only fires when a doubt block closes, and 92% of doubt blocks were being abandoned (tab close, idle timeout, app switch) rather than explicitly ended. The Knowledge Genome — the product's central value prop — was silently not learning from anyone. In parallel, three security holes were leaking student PII and full genome state to non-admin tokens, and `/auth/login` had no rate limiter at all. Shipped all eight fixes in a single commit after local re-verification.

### What shipped

**P0 — Critical security**
- `app/api/admin.py` — new `require_admin` dependency (3-stage check: DB email → JWT email fallback → legacy UUID); applied to **14** admin endpoints that previously used `Depends(get_current_student_id)`. Before: `/admin/student-insights`, `/admin/platform-health`, `/admin/study-path`, `/admin/knowledge-base` all returned **200** with full PII to any authenticated token. After: **403** on any non-admin call.
- `app/api/student.py` — cross-student guard on `GET /student/{id}`. Allows own row OR admin reading any row. Before: student A reading B's URL returned **200** with B's full genome. After: **403**. (`PATCH` was already gated in v0.20.4.)
- `app/api/auth.py` — in-memory rate limiter on `/auth/login`. 10 failed attempts per IP per 5 min → **429** with `Retry-After` header. Successful logins don't count. Resets on worker restart. Before: unlimited brute-force returned 401 forever.

**P0 — Knowledge Genome fix (the biggest behavioural change)**
- `app/api/doubt.py` — new `_autoclose_idle_blocks()` + `_autoclose_idle_study_sessions()` helpers, called at the top of every `/doubt/ask` and `/doubt/hint`. Finds this student's doubt_blocks idle >30 min, force-closes them via the existing `_close_doubt_block` path — which fires `_genome_update_task` for any block where the student engaged with ≥1 hint. Purely passive: fires on the student's NEXT request, so mastery backfills organically as users return. Pure hint-level-0 abandons stay out of the genome (no-information shouldn't pollute EMA — this is intentional, see R3 in the diagnostic doc).

**P1 — Reliability + UX**
- `app/config.py` — `SettingsConfigDict(extra="ignore")`. Local dev no longer crashes on unknown env vars added later (`RENDER_API_KEY`, `RENDER_SERVICE_ID`, etc.) — `Settings()` import-time ValidationError was blocking a full startup path.
- `frontend/web/components/AppShell.tsx` — universal onboarding gate. Any logged-in student visiting any non-`/onboarding`/non-`/auth` route fires `apiGet('/onboarding/status')`; if `onboarding_completed === false` → redirected to `/onboarding`. Catches the **26 students** (≈60% drop-off) who bypassed the original login-flow-only check.
- `app/services/doubt/engine.py` — `_bound_history()` helper applied to all 3 `conversation_history` write sites. Strategy: keep the **first turn** (preserves problem context) + **last 10 turns** + a synthetic separator noting elision count. Bounds JSONB row size (observed: top legacy session was 13KB/14 turns) and caps per-turn LLM token cost at O(1).

**P2 — Data hygiene**
- `scripts/diag_cleanup_test_accounts.py` — safe cleanup tool. Dry-run by default. Allowlist for real users + one named Test Student (preserves the only mastery data we had). Per-student transaction (atomic — partial failures don't orphan data). Tight 5s Supabase auth-API timeout so a slow auth call doesn't hang the script. Result on first real run: **49 students → 7 real users** (12 synthbeta, 4 audit, 1 preview, 26 dev-test removed).

### Verification
| Check | Before | After |
|---|---|---|
| `/admin/*` to non-admin token | 🔴 200 (PII leak) | ✅ **403** |
| Cross-student `GET /student/{id}` | 🔴 200 (genome leak) | ✅ **403** |
| `/auth/login` brute-force | 🔴 unlimited 401 | ✅ **429 at attempt 11** with `Retry-After` |
| `Settings()` startup with diag env vars | 🔴 `ValidationError` | ✅ imports clean |
| Autoclose fires on stale block | 🔴 never | ✅ smoke-tested: stale block force-closed on next `/doubt/ask`, new block opened cleanly |
| Onboarding bypass | 🔴 60% drop-off | ✅ AppShell catches non-onboarded on every route |
| `conversation_history` growth | 🔴 O(turns²) per LLM call | ✅ bounded — first turn + last 10 |
| DB size | 🔴 49 students (42 test/dev) | ✅ **7 real users** |
| Content quality (Judge on 15 prod sessions) | — | Socratic adherence 1.47/2 · single-Q 80% · on-topic 93% · helpful 93% |

Full phase-by-phase findings in `docs/system_diagnostic_2026-04-21_FINAL.md` (shipped in the same commit).

### Deferred (intentional, tracked as Rx items in the diagnostic doc)
- **R1** Render Redis still 100% down in prod — requires the $7/mo add-on (or Upstash free tier) + `REDIS_URL` env var. Code already degrades gracefully (Rule #3).
- **R2** Thumbs feedback `response_feedback` table has 0 rows all-time — backend endpoint looks correct; suspected frontend/UI issue. **Targeted by v0.20.6** (see next entry).
- **R3** Pure hint-level-0 abandon still doesn't fire EMA — by design; no-info shouldn't update the Genome.
- Sentry/cost monitoring, Render off-free-tier, onboarding restyle, single-question prompt tightening — logged for post-beta.

### Files changed
- **NEW** `app/api/admin.py` — `require_admin` dep + 14 route deps swapped (+90 lines net)
- **MODIFIED** `app/api/auth.py` — rate limiter (~+50 lines)
- **MODIFIED** `app/api/doubt.py` — autoclose helpers + 2 wire sites (~+110 lines)
- **MODIFIED** `app/api/student.py` — cross-student guard (+15 lines)
- **MODIFIED** `app/config.py` — `extra='ignore'` (+9 lines)
- **MODIFIED** `app/services/doubt/engine.py` — `_bound_history` + 3 call sites (+30 lines)
- **MODIFIED** `frontend/web/components/AppShell.tsx` — onboarding gate (+16 lines)
- **NEW** `scripts/diag_cleanup_test_accounts.py` — dry-run-default cleanup tool (+347 lines)
- **NEW** `docs/system_diagnostic_2026-04-21.md`, `docs/system_diagnostic_2026-04-21_FINAL.md`, `docs/system_diagnostic_artifacts_2026-04-21/*` (raw DB audit, judge output, critical session trace)

### Lessons
- Every "non-fatal" fallback that materially changes application behaviour (silent no-update on abandoned blocks) is a load-bearing bug. Before shipping the fix, 92% of student sessions had zero Genome effect and nobody noticed until the diagnostic ran — because the user-visible response came back fine. Telemetry for "did the thing I built actually happen?" is now a first-class requirement for any feature that mutates persistent state.
- Admin endpoints default-shared is the wrong default for a product that holds student-level PII + mastery. Going forward: `require_admin` is the default dep for any new `/admin/*` route, not an opt-in.
- Rate limiting isn't a nice-to-have. 0 limits on `/auth/login` means the platform is one botnet away from a credential-stuffing headline.

---

## v0.20.4 — Mastery JOIN fix + migration v17 allow `study` event type + FK fix (2026-04-21)

**Status:** shipped (2 backend files + 1 migration + extended synthetic + docs; awaiting user push)
**Commits:** *(staged — commit by user)*

### Why
v0.20.3 deployed and the prod synthetic run + Render logs surfaced **three** more bugs that v0.20.2's quick-shipped admin panel + mastery composer hid behind soft fallbacks:

1. `app/services/study/card_composer.py` `_compose_mastery()` JOINed `concepts c ON c.concept_id = …`, but the column on `concepts` is `id`, not `concept_id`. Every Concept Card's mastery score was silently falling through to "OVERALL average across all concepts for this student" instead of the topic-specific value. Symptom: every card shows the same number.
2. `/study/card` now logs a `study_card_view` event into `session_events` for the admin panel, with `session_type='study'`. The existing `session_events_session_type_check` constraint only allowed `('doubt','practice','mock')`. Postgres rejected every insert.
3. After fixing the CHECK constraint, a SECOND constraint surfaced: `session_id` is a FOREIGN KEY → `doubt_sessions(id)` ON DELETE CASCADE. The endpoint was passing `gen_random_uuid()` for `session_id` — random UUIDs don't exist in `doubt_sessions`, so the FK rejected every insert. Found by manual curl + INFO-level backend log.

All three logged "skipped (non-fatal)" and returned the card normally — but the entire admin Study Path usage panel showed zero data because no events ever landed.

### Fix
- **`app/services/study/card_composer.py` `_compose_mastery()`** — corrected the JOIN to `concepts c ON c.id = cm.concept_id` (matches the established pattern in `app/api/student.py` line 79). Now matches the topic via `c.subtopic ILIKE '%topic%' OR c.topic ILIKE '%topic%'` so cards return per-topic mastery. Fallback path now logs at WARNING level (not INFO) so future schema drift is visible.
- **`app/api/study.py`** — `study_card_view` insert now passes `NULL` for `session_id` (was `gen_random_uuid()` — violated the FK to `doubt_sessions`). The event isn't tied to a doubt_session; the column is nullable. Fallback log bumped INFO → WARNING per the same lesson.
- **`scripts/migrate_v17_session_events_study.sql` (NEW)** — drops + re-adds the CHECK constraint with `'study'` added: `('doubt','practice','mock','study')`. Idempotent.
- **`scripts/synthetic_beta.py`** — extended `scenario_study_card` to assert `mastery` shape on every card (key + sub-keys must be present). Added new `scenario_admin_study_path_records_views` that hits 2 cards then queries `/admin/study-path` and asserts `total_views > 0` (gracefully SKIPs if test student isn't admin). If migration v17 isn't applied OR the FK fix is missing, this scenario will catch the regression.

### Verification
- Migration v17 applied to Supabase pool successfully (`./scripts/run_migration.sh scripts/migrate_v17_session_events_study.sql` → "Migration applied successfully.").
- Local synthetic suite results in commit message before push.
- Manual prod re-test post-push: open any Concept Card, mastery section should display a sensible per-topic number (or "—" for fresh student) rather than the global average from before.

### Lessons
- "Non-fatal" log levels can hide real functional bugs. The mastery JOIN was logging INFO and falling back silently — admin panel was silently broken. Going forward: any fallback that materially changes the response shape is logged at WARNING with explicit text noting the consequence.
- The CHECK constraint failure was visible in prod logs only because the user pasted them. There was no automated alert. Proper observability (or a simple synthetic invariant) would have caught this in the same hour the v0.20.2 deploy went live. v0.20.4 adds the synthetic invariant — going forward this regression is permanent-blocked.

### Files changed
- **NEW** `scripts/migrate_v17_session_events_study.sql`
- **MODIFIED** `app/services/study/card_composer.py` (`_compose_mastery` JOIN + warning level)
- **MODIFIED** `app/api/study.py` (`study_card_view` insert: NULL session_id + warning log)
- **MODIFIED** `scripts/synthetic_beta.py` (mastery-shape assert + admin study_path view-count assert)
- **MODIFIED** `docs/version_history.md`, `docs/session_log.md`, `docs/bugs.md`

---

## v0.20.3 — Lower topic-shift length floor + regression guard (2026-04-21)

**Status:** shipped (1 backend file + 1 test file + docs; awaiting user push)
**Commits:** *(staged — commit by user)*

### Why
Live prod test by the user surfaced the v0.20.2 fix wasn't complete. Sequence: physics doubt → math pivot (`"wait, what's the integral of sin(x²)?"` — opened new block ✓) → chemistry pivot (`"what is molecule?"` — got refused by counselor mode, no new block). User correctly called out the inconsistency: math pivot was allowed, chemistry pivot was refused.

### Root cause
`_looks_like_new_question()` had `if len(stripped) < 20: return False` as the first gate. `"what is molecule?"` is **16 chars** — short-circuited before the verb regex could match. Since FIX A3 demoted intent → continuation, and my v0.20 promotion was gated by `_looks_like_new_question`, the demotion stuck and the AI treated the chemistry question as a hint reply on the integral block.

### Fix
- `app/api/doubt.py` `_looks_like_new_question()`: lowered the verb-regex floor from 20 → 12 chars. The symbol-only fallback floor stays at 25 (notation alone needs more weight to overcome ambiguity).
- `scripts/synthetic_beta.py` `scenario_topic_shift()`: extended from 1 pivot to 3-pivot stress test — physics → math (long, with math symbols) → chemistry (short, "what is X?"). Each pivot must open a new doubt_block. Permanent regression guard.

### Verification
- Local synthetic suite — re-running with the new chem-pivot fixture (results in commit message before push).
- Manual repro of the prod chat now opens 3 sequential blocks (Laws of Motion → Integration → Chemistry) instead of 2 + counselor refusal.

### Lessons
- The 20-char floor was a guess, not a measurement. Should have set it from the shortest legitimate "what is X?" length (≈12). Lesson: thresholds in regex/heuristic code need explicit min-length comments tying back to a real failure mode.
- Synthetic tests caught only single-pivot scenarios in v0.20.2. Multi-pivot is meaningfully different — added permanently.

### Files changed
- **MODIFIED** `app/api/doubt.py` (one function, comment updated to reference v0.20.3 + prod date).
- **MODIFIED** `scripts/synthetic_beta.py` (`scenario_topic_shift` — 1 pivot → 3 pivots).
- **MODIFIED** `docs/version_history.md`, `docs/session_log.md`, `docs/bugs.md`.

---

## v0.20.2 — Prod bug patches + reliability + admin Study Path panel + synthetic tests (2026-04-21)

**Status:** shipped (backend + frontend + tests; awaiting user push)
**Commits:** *(staged — commit by user)*

### Why
v0.20 deployed and Render-prod logs surfaced two bugs: (a) topic-shift demotion didn't fire on `"wait, what's the integral of sin(x²)?"` because `_NEW_QUESTION_MARKERS` regex was too narrow (no contractions, no math verbs); (b) Notes section showed the same NCERT chunk three times for popular topics (no dedup). User asked to bundle the patches with the remaining v0.20 plan items + a synthetic test harness so beta launches with full confidence.

### What shipped

**P0 — bug patches**
- `app/api/doubt.py` `_looks_like_new_question()` widened: now matches contractions (`what's`, `how's`), math verbs (`integrate`, `differentiate`, `simplify`), and a `_MATH_SYMBOL_HINTS` fallback covering `∫`, `²`, `dy/dx`, `integral`, `derivative`, `pH`, `mol`, etc. The exact prod-log message that slipped through ("wait, what's the integral of sin(x²)?") now triggers topic-shift demotion → new doubt block opens with correct mastery attribution.
- `app/services/study/card_composer.py` `_compose_notes()`: fetch wider (k×3), dedupe by sha1 of normalised first-200-chars, prefer chunk-heading diversity. Drops the 3-duplicate-chunks bug visible in prod screenshots.

**P1 — reliability**
- `app/api/doubt.py` `_reclassify_block_topic()` (NEW): block-close drift backstop. Reads conversation_history, classifies dominant topic from student turns only, logs a warning if the stamped topic differs from dominant. Concept_ids unchanged for v0.20.x — the signal accumulates in `session_events.payload.drift_topic` for admin auditing. If beta shows >5% drift, v0.21 will re-derive concept_ids.
- `_genome_update_task()` now accepts `engine` kwarg; threaded through every call site (3 paths in /doubt/ask + /doubt/hint + stream).
- `app/api/doubt.py` `POST /doubt/new` (NEW): manual segmentation lever. Closes any active block; safe to call when no block active. Frontend chat header now renders a "+ New doubt" button (right of analysis chips) when a block is active.
- Topic-shift demotion log line now includes `old_subject` + `old_topic` so we can audit accuracy from logs alone.

**P2 — features**
- `scripts/concept_card_overrides.json` (NEW): hand-polished Notes overrides for 5 seed cards (Projectile Motion, Newton's Laws, SHM, Chemical Bonding, Differentiation). Each is a JEE-essentials cheat-sheet with formulas + common traps. Composer prefers these over auto-assembled chunks.
- `app/services/study/card_composer.py`: override loader. Path: repo `scripts/concept_card_overrides.json` resolved via `Path(__file__).resolve().parents[3]`.
- `app/api/study.py` now logs `study_card_view` event into `session_events` on every card render — feeds the admin panel.
- `app/api/admin.py` `GET /admin/study-path` (NEW): top 10 concept cards by view count, daily-views sparkline, override hit-rate, drift-detection count.
- `frontend/web/app/admin/page.tsx`: new "Study Path" section with stat cards + AreaChart + sortable table + CSV export. Auto-refresh + URL-hash routing inherit from v0.19.
- `scripts/migrate_v16_student_profile.sql` (NEW): adds `phone`, `avatar_url`, `timezone`, `preferred_language` columns to `students` (idempotent, with phone-format CHECK). **Not yet applied — user runs `./scripts/run_migration.sh scripts/migrate_v16_student_profile.sql` when ready.**
- `app/api/student.py` `PATCH /student/{student_id}` (NEW): graceful schema-drift handling — discovers existing columns at runtime, applies only the keys that exist, returns `{updated: [...], ignored: [...]}`. Pre-migration: returns `{noop: true, ignored: [phone, timezone, ...]}`. Post-migration: writes through.
- `frontend/web/app/settings/page.tsx` Profile tab `handleSave()` now actually calls `apiPatch('/student/{id}', ...)`. Toast variants: success / warning (when migration pending) / error.
- `frontend/web/lib/api.ts`: new `apiPatch()` helper + cold-start toast — fires after 8s on first request only, lazy-imports sonner so it doesn't bloat auth-page bundles.

**Synthetic test harness (NEW)**
- `scripts/synthetic_beta.py`: spawns 2-N personas, runs full signup → onboarding → study card → topic-shift → manual new-doubt → patch_student → genome-readback. Validates 9+ invariants per persona including Notes dedup, override-loading, structural topic-shift, manual segmentation, schema-drift PATCH shape. Exit code = pass/fail for CI gating.

**Doc + handoff**
- `docs/version_history.md`: this entry + index update.
- `docs/session_log.md`: rotated, top entry is v0.20.2.
- `docs/handoff_guide.md`: pointers to new files (study composer, /doubt/new, synthetic harness).

### Verification
- `cd frontend/web && npx tsc --noEmit` → 0 errors.
- `cd frontend/web && npm run build` → ✓ 15 routes (unchanged from v0.20).
- Backend imports clean: `study`, `student`, `admin`, `doubt` all register.
- **Synthetic suite — 19/19 PASS** at the local backend:
  - `topic_shift.opens_new_block — intent=subject_doubt new_block=… old_block=…` ← the prod bug fixed.
  - `study_card[Chemical Bonding].notes_deduped — 1 unique chunks` ← override + dedup working.
  - `manual_new.closes_active_block — closed=True`.
  - `patch_student.shape — updated=['name'] ignored=['phone','timezone']` ← schema-drift handling correct.
- Live preview confirmed: Concept Card now renders the JEE-essentials override (Projectile Motion equations + traps) instead of duplicated NCERT intro chunks. Cold-start toast fires after 8s as expected.

### Deferred (intentional, will land in v0.21)
- **Onboarding restyle** on new primitives — current onboarding works; full restyle is large surface change with low marginal pre-beta value.
- **Concept-card override regeneration** — only 5 seed cards. The other 100+ topics ship with auto-assembled NCERT chunks.
- **Migration v16 application** — file shipped; user runs `./scripts/run_migration.sh scripts/migrate_v16_student_profile.sql` whenever they're ready. Until then, profile save returns `{ignored: [...]}` and the UI shows a soft warning.
- **Drift backstop concept_id re-derivation** — current backstop is logging-only. Wires real EMA shift if beta shows >5% drift rate.

---

## v0.20 — Dual-loop architecture — Study Path + Ask Anything (2026-04-20)

**Status:** shipped (backend + frontend; beta-ready)
**Commits:** *(staged — commit by user)*

### Why
Per-topic localStorage partitioning (v0.15) solved session bleed but created three new problems: (a) forced topic pre-pick bad UX, (b) mastery mis-attribution on cross-topic follow-ups because session-level topic tagging credits the wrong concept, (c) unbounded `conversation_history` JSONB inside a single doubt_session. Sir confirmed "students need structure when they study, free-form when they have doubts" — that's two distinct activities. One mode can't serve both.

### What shipped
**Two coexisting modes, one Knowledge Genome.**

**Mode 1 — Study Path (structured):**
- **`app/api/study.py`** (NEW) — `GET /study/card?subject=&chapter=&topic=` returns a computed concept card. Zero LLM calls.
- **`app/services/study/card_composer.py`** (NEW) — assembles four sections from data already indexed:
  - Notes: top-3 NCERT chunks via existing `Retriever.search(topic, subject)` (no LLM)
  - Practice: up to 3 problems from `problems` table filtered by topic
  - PYQs: up to 3 rows from `jee_problems` filtered by topic
  - Mastery: aggregate EMA score for this topic for this student
- **`app/main.py`** — registered `study.router`.
- **`frontend/web/app/study/page.tsx`** (NEW) — Study Path navigator. Subject → chapter → topic tree reusing `SYLLABUS_MAP`. No gate, no chat.
- **`frontend/web/app/study/[subject]/[chapter]/[topic]/page.tsx`** (NEW) — Concept Card page. Four sections (Notes / Practice / PYQs / Ask about this) + mastery progress bar + topic-locked "Ask" CTA.

**Mode 2 — Ask Anything (free-form with auto-segmentation):**
- **`app/services/doubt/engine.py`** — exposed `classify_turn_topic()` as a public wrapper over `_classify_subject()` so the API layer can detect topic shifts without reaching into private methods.
- **`app/api/doubt.py`** — new helpers `_looks_like_new_question()`, `_topics_differ()`, `_detect_topic_shift()`. Both `/doubt/ask` and `/doubt/ask/stream` now demote `continuation` → `subject_doubt` when the student's message shape suggests a new question AND classifies to a materially different topic/subject than the active block. This triggers the existing close-old-block + start-new-session path, so mastery attributes to the correct concept. Symmetric mirror of FIX A3 (2026-04-18).
- **`app/api/doubt.py`** — `_get_active_doubt_block()` now LEFT JOINs `doubt_sessions` to expose `subject` for shift detection.
- Skipped when `topic_lock` is set (Focus Mode from Study Path should not auto-segment).

**Home + navigation:**
- **`frontend/web/app/page.tsx`** — replaced 4-card bento with two primary CTAs (Study Path + Ask Anything) + 3 secondary (Practice / Mock / Progress).
- **`frontend/web/components/AppShell.tsx`** — primary nav now: Home / **Study Path** / **Ask Anything** / Practice / Mock Test / Progress. Page titles updated accordingly.

### Zero content-generation cost
Concept cards are computed, not stored. Existing NCERT chunks (15,069 indexed), existing `problems` table, existing `jee_problems` table, existing EMA mastery. Marginal cost per card render: DB + retriever, no LLM. Daily cost at 30 beta students stays ≈ $15/month.

### Verification
- `cd frontend/web && npx tsc --noEmit` → 0 errors
- `cd frontend/web && npm run build` → ✓ 15 routes (up from 14 — `/study` + `/study/[subject]/[chapter]/[topic]` added)
- `GET /study/card?subject=Physics&chapter=Kinematics&topic=Projectile Motion` → 200 with populated `notes.chunks[]`
- Manual E2E via preview: home → Study Path → Projectile Motion card → Notes section populated with real NCERT content

### Known limits / future work
- Hand-curated Notes overrides for top-30 topics — deferred (post-beta).
- Topic-shift detection is classifier-accuracy-bounded (~94%). 6% of turns may still mis-attribute. Mitigation: confidence threshold + existing session-stamped topic fallback.
- `/doubt` still uses the existing per-topic localStorage keying. Free-form mode already works because `(null, null, null)` hashes to a single `general__any__quick` key per student. Fuller single-inbox migration can follow if beta shows demand.
- Admin Study Path usage panel — deferred.

### Files changed
New: `app/api/study.py`, `app/services/study/__init__.py`, `app/services/study/card_composer.py`, `frontend/web/app/study/page.tsx`, `frontend/web/app/study/[subject]/[chapter]/[topic]/page.tsx`, `docs/handoff_guide.md`.
Modified: `app/main.py`, `app/api/doubt.py`, `app/services/doubt/engine.py`, `frontend/web/app/page.tsx`, `frontend/web/components/AppShell.tsx`, `MEMORY.md`, `docs/session_log.md`, `docs/version_history.md`, `docs/decisions.md`.

---

## v0.19 — Enterprise UI Phases 2–6 — AppShell, auth, settings, doubt, admin polish (2026-04-19)

**Status:** shipped (Phases 2–6 of 6-phase enterprise UI overhaul)
**Commits:** *(staged — commit by user)*

### What shipped

**Phase 2 — Global layout shell**
- **`components/AppShell.tsx`** (NEW) — single layout shell wrapping every logged-in page. Left sidebar (260px): brand + primary nav (Home/Doubts/Practice/Mock Test/Progress) + syllabus tree + Settings + Admin (conditional) + profile card with logout. Top bar: page title + ⌘K search placeholder + notifications + help + avatar menu. Mobile: drawer. Supports `fullHeight` + `rightPanel` props for chat-style pages.
- **All pages migrated**: `app/page.tsx`, `app/progress/page.tsx`, `app/practice/page.tsx`, `app/mock/page.tsx`, `app/doubt/page.tsx`, `app/settings/page.tsx` — all now use `<AppShell>` wrapper. Consistent nav, topbar, profile across every page. Old `components/Sidebar.tsx` remains (legacy; admin still uses its own).
- All scaffolded actions (command palette, notifications, help) show "coming soon" toast with explanation — no dead clicks per locked decision #4.

**Phase 3 — Auth + onboarding**
- **`app/auth/login/page.tsx`** — rewritten split-screen: marketing hero (stats grid, copy) left, form right. Email + password icons, show/hide toggle, Caps-Lock warning, forgot-password link, Google OAuth button (disabled with "Coming soon" tooltip), toast on success/error.
- **`app/auth/signup/page.tsx`** — rewritten split-screen with password strength meter (weak/decent/strong), feature bullets, exam + year selects, disabled Google OAuth placeholder.
- **`app/auth/forgot-password/page.tsx`** (NEW) — dedicated route. Email form → success state with support link fallback since email delivery is scaffolded.

**Phase 4 — Doubt page enhancements**
- Migrated to `AppShell fullHeight`.
- **`components/ChatMessage.tsx`** — added action row under every AI response: thumbs-up/down (existing), **copy-to-clipboard** (real, uses `navigator.clipboard`, toast on success), **regenerate** (scaffolded with "Coming soon" tooltip until `POST /doubt/regenerate` is wired).

**Phase 5 — Settings 6-tab expansion**
- **`app/settings/page.tsx`** — complete rewrite. URL-param tab state (`?tab=profile`). Tabs: Profile / Account / Learning / Notifications / Appearance / Privacy & Data.
  - **Profile** — avatar (upload scaffolded), name editable, email read-only (change-flow scaffolded), **phone** (new field), timezone select (IST/GST/SGT/GMT/EST), preferred language (English/Hindi). Dirty-state bar with Save/Discard.
  - **Account** — password change (scaffolded), email-verified badge, 2FA enable (scaffolded), Google OAuth connect (scaffolded), log-out device, **delete account with modal confirmation** (requires typing "DELETE").
  - **Learning** — exam type, target year (editable), hint verbosity (scaffolded), auto-inferred learning profile readout (scaffolding/style/intensity/velocity from `persona_profile`).
  - **Notifications** — 5 toggles (weekly digest, study reminders, exam alerts, browser push, mastery milestones) — all scaffolded with tooltip.
  - **Appearance** — theme cards (Light active; Dark + System disabled with "Coming soon"), font size, math density.
  - **Privacy & Data** — export my data (scaffolded, calls toast), delete all doubts (scaffolded), legal links (scaffolded).

**Phase 6 — Admin polish**
- **URL hash routing** — `#platform-health`, `#conv-quality`, etc. Sections bookmarkable; browser back/forward works.
- **Error handling** — every loader wrapped in shared `tryLoad()` helper: try/catch → toast.error with description. No more silent failures.
- **Last-updated timestamp** — relative-time badge ("Updated 12s ago") next to every section title.
- **CSV export** — `exportCSV()` utility + "Export CSV" button on Platform Health (pattern extendable to other tables).
- **Auto-refresh toggle** — sidebar toggle, polls active section every 30s when on.
- **Knowledge Base lookback fix** — `/admin/knowledge-base` now honors the `days` param (was previously ignored per audit).

### Quality gates passed
- `cd frontend/web && npx tsc --noEmit` → 0 errors
- `cd frontend/web && npm run build` → ✓ Compiled successfully in 2.7s, 14 routes static-prerendered (up from 13 — new `/auth/forgot-password`)
- No dead clicks — every scaffolded button/toggle has a tooltip or toast explaining what's missing.
- Mobile drawer works; sidebar collapses properly at <md breakpoint.

### Deferred (intentional — per locked decisions)
- **Dark mode** — tokens scaffolded in `globals.css` `.dark` block, `darkMode: 'class'` in Tailwind config. Enabling is a 1-file change when we're ready. Per locked decision #1.
- **Chat history sidebar** — skipped. Per-topic localStorage isolation (v0.15) is sufficient. Per locked decision #2.
- **Backend endpoints** (still scaffolded in UI): `POST /doubt/regenerate`, `GET /student/export`, Google OAuth, 2FA, email notification delivery, password change flow, avatar upload (base64 PATCH scaffolded).
- **Migration `v16_student_profile.sql`** (phone/avatar_url/timezone/language columns) — not yet applied. UI has fields but save is a no-op toast until migration lands.
- **Onboarding redesign** — left as-is; glassmorphic pattern still acceptable. Will restyle in a follow-up commit.

### What's next
- Write + run `scripts/migrate_v16_student_profile.sql` to wire profile saves.
- Build `POST /doubt/regenerate` so the regenerate button goes live.
- Implement dark mode toggle.
- Onboarding restyle on new primitives.

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
