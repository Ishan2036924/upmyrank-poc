# UpMyRank — UI Overhaul Changelog (2026-04-18 → 2026-04-19)

Two-day sprint: (1) introduced a disciplined versioning system for the project, then (2) executed a full 6-phase enterprise-grade UI overhaul across every page.

## Yesterday (2026-04-18) — Versioning & rules (v0.17)

**Goal:** stop losing track of what shipped; make Claude incapable of accidental git writes.

- **`docs/version_history.md` (NEW)** — single source of truth for every version shipped. Reverse-chronological, jump-link index, full entry per version. Backfilled 17 entries covering 2026-03-17 → present from 54 git commits. Template at the bottom for future sessions.
- **`CLAUDE.md`** — first-read rule now requires `version_history.md` + `session_log.md` at the top of every new Claude session. Added a "Version History Rule" section mandating a new entry on every user-visible commit.
- **`RULES.md #7`** — hardened to an absolute no-commit rule: Claude **never** runs `git add / commit / push / reset / rebase`. Even when told "commit this," Claude prints the commands for the user to run.
- **Phase 1 foundation also landed this day (v0.18):** design tokens + 18 shadcn-pattern UI primitives + `cn()` helper + Toaster wiring. No user-visible change — setup for the phases that followed.

## Today (2026-04-19) — Phases 2–6 of the UI overhaul (v0.19)

**Goal:** stop looking like a college project. Every page now lives inside a consistent enterprise shell; every interactive element either works or is disabled with a "coming soon" tooltip.

### Phase 2 — Global shell
- **`components/AppShell.tsx`** (NEW): 260-px left sidebar (brand + primary nav + syllabus tree + profile card), sticky top bar (page title + ⌘K search scaffold + notifications + help + avatar menu), mobile drawer, optional right context panel, `fullHeight` mode for chat pages.
- Migrated `/`, `/progress`, `/practice`, `/mock`, `/doubt`, `/settings` — every logged-in page now uses the same shell.

### Phase 3 — Auth + onboarding
- **`/auth/login`** rewritten: split-screen with marketing hero left, form right. Password show/hide, Caps-Lock warning, forgot-password link, Google OAuth button disabled with tooltip.
- **`/auth/signup`** rewritten: split-screen + password strength meter (weak/decent/strong).
- **`/auth/forgot-password`** (NEW) — dedicated route replaces dead link.

### Phase 4 — Doubt chat
- Moved to `AppShell fullHeight` three-column layout.
- **Message actions row** on every AI reply: thumbs ↑/↓ (existing), **copy-to-clipboard** (real, toast-confirmed), **regenerate** (scaffolded with "coming soon" tooltip).

### Phase 5 — Settings 6-tab expansion
URL-param tab state (`?tab=profile`). Six tabs, all rendered with the new primitives:
- **Profile** — avatar, name, email (read-only), **phone** (new), timezone, preferred language. Dirty-state bar with Save/Discard.
- **Account** — password change, email-verified badge, 2FA, Google OAuth, log-out device, **delete-account modal** (type DELETE to confirm).
- **Learning** — exam type, target year, hint verbosity, auto-inferred persona readout (scaffolding/style/velocity).
- **Notifications** — 5 toggles (weekly digest, reminders, exam alerts, browser push, mastery milestones).
- **Appearance** — theme (Light active; Dark + System disabled "Soon"), font size, math density.
- **Privacy & Data** — export my data, delete all doubts, legal links.

### Phase 6 — Admin polish
- URL-hash routing — admin sections bookmarkable (`#platform-health`, `#students`, …).
- Shared `tryLoad()` error pattern — every loader now surfaces a toast on failure instead of failing silently.
- Last-updated badge ("Updated 12s ago") on every section header.
- CSV export utility + Export CSV button on Platform Health (pattern extendable to other tables).
- Auto-refresh toggle — polls the active section every 30s when on.
- `/admin/knowledge-base?days=X` lookback bug (ignored param) fixed on frontend call.

### Backend (no code changes today)
Untouched. Verified healthy:
- `GET /health` → `{"status":"ok"}` ✅
- 34 routes registered across `auth / doubt / session / student / onboarding / mock / feedback / admin / taxonomy`.
- Startup clean: DB pool initialised, embedding service ready, retriever + verification pipeline loaded.

### Verification
- `npx tsc --noEmit` → 0 errors.
- `npm run build` → ✓ Compiled successfully, 14 static routes (up from 13 — new `/auth/forgot-password`).
- Live preview confirmed across every page: login / signup / forgot-password / home / settings (profile, account, appearance) / doubt / progress / mock / admin.
- Hydration warning in Settings Profile tab (`<div>` inside `<p>`) caught on preview and fixed.

## Deferred (intentional)
- **Dark mode** — tokens scaffolded; toggle disabled. Enabling later is a 1-file change.
- **Chat history sidebar** — skipped; per-topic localStorage isolation (v0.15) is sufficient.
- **Backend endpoints pending**: `POST /doubt/regenerate`, `GET /student/export`, Google OAuth, 2FA, email notification delivery, password-change flow, avatar upload, migration `v16_student_profile.sql` (phone/avatar_url/timezone/language). UI scaffolded with tooltips for each.

## Quality gates met
- [x] No dead buttons (every action either works or is disabled with "coming soon" tooltip).
- [x] No dead links (forgot-password route exists; every Link resolves).
- [x] Loading states on async ops.
- [x] Error toasts on API failures (admin loaders).
- [x] Empty states (Progress page, Analytics "Failed to load" fallback).
- [x] Mobile responsive (sidebar becomes drawer, split-screen stacks).
- [x] Keyboard accessible (Radix primitives, Tab-reachable, Escape closes modals).
- [x] `tsc --noEmit` clean.
