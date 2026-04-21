# UpMyRank — Handoff Guide

> **Start here.** If you're a new developer, a new Claude session, or coming back after a break, read this first. It points you to everything else.

## First-read chain (in order)

1. **`CLAUDE.md`** (project root) — mandatory-read for every Claude session. Defines the auto-read rules, banned git operations, and the Version History Rule.
2. **`RULES.md`** (project root) — 10 hard invariants. Rule #7 is the no-commit rule (Claude never runs git add/commit/push). Rule #2 is the sole-mastery-writer rule. Memorise both.
3. **`docs/version_history.md`** — single source of truth for every version shipped. Reverse-chronological. Backfilled from v0.1 (2026-03-17) through current. Read the latest 2–3 entries to know where we are.
4. **`docs/session_log.md`** — tactical context. Top 3 most-recent sessions, written by Claude via `/handoff`. Tells you what's half-done right now.
5. **`MEMORY.md`** — full project state snapshot. Reference, not cover-to-cover read.

## What is UpMyRank?

AI-powered JEE/NEET tutoring platform covering Physics, Chemistry, and Maths (NCERT Class 11 & 12). Architecture: PTB educational-AI framework — Customization layer (global rules) + Personalization layer (student model) + Golden Dataset (truth control). **The LLM is a composer, not the source of knowledge.** The architecture is the product.

## Dual-loop architecture (v0.20, current)

Two coexisting product modes, **one shared Knowledge Genome**:

| Mode | Route | When to use | Primary files |
|---|---|---|---|
| **Study Path** | `/study`, `/study/[subject]/[chapter]/[topic]` | Student wants structure — pick a topic, study concept cards (notes + practice + PYQs) | `app/api/study.py`, `app/services/study/card_composer.py`, `frontend/web/app/study/...` |
| **Ask Anything** | `/doubt` (free-form) | Student has a spontaneous doubt; doesn't want to pre-classify | `app/api/doubt.py`, `app/services/doubt/engine.py`, `frontend/web/app/doubt/page.tsx` |

Both modes feed the same `concept_mastery` table. Both use the same Socratic engine when chatting. Both preserve persona evolution + misconception detection.

## Stack map

- **Frontend:** Next.js 16 + React 19 + TypeScript (strict) + Tailwind v4, token-based design system. Deployed on Vercel.
- **Backend:** FastAPI (Python 3.11), asyncpg, Pydantic v2. Deployed on Render.
- **Database:** Supabase Postgres 16 + pgvector 0.8.2. 15K NCERT chunks, 20+ JEE PYQs indexed.
- **Cache:** Redis (local Docker for dev, Render service for prod).
- **LLMs:** `gpt-4.1-mini` (Socratic, hints, full solutions), `gpt-4o-mini` (intent classify, session summarize, persona compress), `gpt-4o` (vision only). Rule #5.

## How to run locally

```bash
# 1. Start backend (from project root)
PYTHONPATH="" PYTHONHOME="" /opt/miniconda3/bin/python3.11 -m poetry run \
  uvicorn app.main:app --reload --reload-dir app --port 8000

# 2. Start frontend (separate terminal)
cd frontend/web && npm run dev
# open http://localhost:3000

# 3. Redis (local Docker)
docker start upmyrank-redis  # if not running
```

- `DATABASE_URL` in `.env` points to the Supabase cloud pool.
- Migrations: `./scripts/run_migration.sh scripts/migrate_vX_name.sql` — always use this, never Docker, never Supabase CLI.

## The 10 rules in one paragraph

(See `RULES.md` for each in full.) Claude never commits. `_genome_update_task` in `app/api/doubt.py` is the sole mastery writer — never add a second EMA path. `summarize_session()` on `/session/end` must stay blocking (async fire-and-forget once broke the pipeline — see `docs/bugs.md`). Redis errors never propagate — wrap every call in try/except and log as warning. Level 3 (forced attempt) structurally starves the LLM — swap to `SYSTEM_PROMPT_FORCED_ATTEMPT`, skip RAG, skip intent classify. Model routing is strict (see Stack map above). LaTeX sanitizer runs on every LLM response. Migrations are file-based, run via `scripts/run_migration.sh`.

## Where changes get logged

Every user-visible commit writes to these four files in order, **before** the git commit:

1. **`docs/version_history.md`** — new entry at the top. Semver-lite: `v0.X.Y` for pure bug fixes, `v0.X+1` for new features. Template at bottom of file.
2. **`docs/bugs.md`** — only if a bug was fixed. Format: symptom → root cause → fix → **DO NOT** (what regression to prevent).
3. **`docs/session_log.md`** — rewrite top entry; keep only last 3. This is the tactical "what's half-done" view.
4. **`MEMORY.md`** — only if project-state invariants shifted (new feature, new mode, new table). Not for bug fixes.

After those four are up to date, Claude prints the exact `git add / git commit -m / git push origin main` commands in separate code blocks. **The user runs them.** Rule #7.

## "I don't know where to look" decision tree

- **"Why does mastery update this way?"** → `app/api/doubt.py` `_genome_update_task()` + `app/services/mastery.py` + `docs/decisions.md` (EMA α=0.7 decision).
- **"Why is the session summarizer blocking?"** → `docs/bugs.md` "Session summarizer race condition" — DO NOT make it async again.
- **"Why does topic-lock leak sometimes?"** → `app/services/doubt/engine.py` `TOPIC_LOCK_ADDENDUM` + `docs/version_history.md` v0.15/v0.16/v0.20. Prompt-level enforcement has known limits; v0.20 added structural auto-segmentation for the Ask Anything path.
- **"How do I add a new /admin panel?"** → `app/api/admin.py` (endpoint), `frontend/web/app/admin/page.tsx` (section). Use the `tryLoad()` wrapper pattern from v0.19 for errors/toasts.
- **"How is a new concept card built?"** → `app/services/study/card_composer.py`. Add a new section by writing a new `_compose_X()` fn and including it in the final dict. Zero LLM cost is the policy — do not regress.
- **"UI style guide?"** → `UI_PRO_MAX.md` + `frontend/web/tailwind.config.ts` for tokens + `frontend/web/components/ui/*` for primitives (shadcn pattern).

## Quality gates (every change must pass)

- [ ] `cd frontend/web && npx tsc --noEmit` → 0 errors.
- [ ] `cd frontend/web && npm run build` → all routes compile.
- [ ] No dead buttons. Every `onClick` either does something or is disabled with a "coming soon" tooltip.
- [ ] No dead links. Every `<Link>` resolves to a real route.
- [ ] Loading + error + empty states on every async surface.
- [ ] Mobile responsive — sidebars become drawers at <md.
- [ ] Backend eval doesn't regress — if you changed prompts or engine logic, run `scripts/regression_gate.py`.

## What's next (as of v0.20, 2026-04-20)

- Beta with 30 students — monitor topic-shift classifier accuracy, card render errors.
- Optional V1.1: hand-curated Notes overrides for top-30 topics (2.5 h of editorial time, no code change).
- Optional V1.2: admin Study Path usage panel.
- Deferred: teacher dashboard, syllabus editing UI, dark-mode activation (tokens already in `globals.css` `.dark` block), migration `v16_student_profile.sql` for phone/timezone profile fields.
