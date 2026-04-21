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
