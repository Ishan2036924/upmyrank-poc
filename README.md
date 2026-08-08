# UpMyRank

**An AI tutor for JEE and NEET that refuses to give you the answer.**

Live demo: **https://upmyrank-poc.vercel.app**

Most "AI tutors" are a chat box wrapped around an LLM. Ask a question, get a
worked solution, learn nothing. UpMyRank is built on the opposite premise: the
model is a *composer*, not the source of truth, and the system's job is to
decide **how** to teach before it decides **what** to say.

---

## The problem

A student stuck on a physics problem at 11pm has two options: give up, or look
up the answer. Both produce the same result, which is that they cannot solve
the next one either. Copying a solution feels like learning and is not.

The hard part is not generating an explanation. It is *withholding* one at the
right moment, and knowing which student, on which concept, at which point in
their own history, needs a nudge versus a worked example versus to be told
plainly to try again.

## The approach

Three layers, following the PTB (Python Tutor Bot) educational AI framework:

| Layer | Role |
|---|---|
| **Customization** | Global pedagogical rules. What "good teaching" means, independent of who is asking. |
| **Personalization** | A per-student model: mastery per concept, error fingerprints, forgetting rate, preferred explanation style, scaffolding level. |
| **Golden dataset** | Truth control. 15,069 NCERT chunks + JEE past papers, so the model composes from retrieved fact rather than from memory. |

The design commitment: **optimize for learning gain, not user satisfaction.**
Desirable difficulty is intentional. A student who leaves slightly frustrated
but able to solve the next problem is a better outcome than one who leaves
happy with a copied solution.

### The Socratic ladder

Every doubt runs through a policy engine *before* generation. It picks a hint
level from the student's genome and the conversation so far:

- **L0**: a question back. No content.
- **L1**: point at the relevant principle.
- **L2**: structured scaffolding, still no arithmetic.
- **L3**: **forced attempt.** The student must try before anything else.

L3 is not a prompt instruction, because prompt instructions leak. The system
*structurally starves* the model at L3: RAG context is cleared, intent
classification is skipped, response analysis is skipped, and the system prompt
is swapped out entirely. There is nothing in the context window to leak.

### Misconceptions are not knowledge gaps

A wrong answer given with **high confidence** is treated differently from a
wrong answer given tentatively. The first is a misconception (the student has
a working mental model that is wrong) and carries a 1.5x mastery penalty plus
different remediation. The second is a gap. A 30-entry misconception library
across all three subjects drives the distinction.

### Measuring pedagogy, not just accuracy

Accuracy is table stakes and easy to measure. Whether the tutor actually
*taught* is neither. Every response is scored 0/1/2 by a judge LLM on Socratic
quality, and every completed conversation is scored on coherence, adaptation,
context persistence, closure, and pedagogical arc. A weekly drift report flags
any topic whose average scaffolding score falls below 1.5, and a pre-deploy
regression gate fails the build if the golden-dataset pass rate drops under 90%.

---

## Architecture

```
Next.js 16 (Vercel)
        |  SSE streaming
        v
FastAPI (Render)
        |
        +-- Policy Engine ......... decides HOW to teach, before generation
        +-- Agentic RAG ........... gpt-4o-mini picks tools, max 3 steps
        |     +-- search_ncert, search_jee_problems,
        |         search_concepts, rerank_and_select
        +-- Socratic Engine ....... gpt-4.1-mini composes the response
        +-- Judge LLM ............. scores pedagogy on every turn
        +-- Knowledge Genome ...... EMA mastery, single writer, no exceptions
        |
        +-- Postgres + pgvector (Supabase) .... 15,069 embedded chunks
        +-- Redis (Upstash) ................... hot context + semantic cache
```

**Knowledge base:** Physics 10,505 · Chemistry 3,138 · Maths 1,426 · 20 JEE PYQs.
All three subjects share one engine, one policy layer, one genome.

### Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.11), asyncpg, Pydantic v2 |
| Frontend | Next.js 16, TypeScript, Tailwind, Framer Motion |
| LLM | gpt-4.1-mini (Socratic/hints), gpt-4o-mini (classify/summarize), gpt-4o (vision only) |
| Vector DB | pgvector 0.8.2 on Postgres 16 |
| Embeddings | text-embedding-3-small, 1536-dim |
| Cache | Redis (redis.asyncio) |
| ORM | none, raw asyncpg |

### Engineering decisions worth defending

- **Raw asyncpg, no ORM.** Every hot query is a hand-written statement with a
  known plan. Vector search plus JSONB aggregation is not what ORMs are good at.
- **One mastery writer.** `_genome_update_task` is the only code path that
  updates `concept_mastery`. A second EMA writer anywhere produces silent,
  unreproducible drift, so the invariant is enforced by convention and review
  rather than discovered later in the data.
- **The summarizer blocks.** `summarize_session()` is awaited on `/session/end`,
  never fire-and-forget. It was fire-and-forget once; the next session started
  with empty context.
- **Redis failures are always silent.** Cache is an optimization. No user flow
  is allowed to depend on it being up.
- **Model routing is a rule, not a default.** `gpt-4o` for text costs 10x with
  no measurable quality gain here, so it is restricted to vision.

Full invariant list in [`RULES.md`](RULES.md). Every shipped version is logged
in [`docs/version_history.md`](docs/version_history.md).

---

## Testing

The interesting failure modes are pedagogical, not functional, so most of the
harness is about behaviour rather than status codes:

| Script | What it does |
|---|---|
| `scripts/portfolio_smoke.py` | 15 personas across every class level, exam type, subject and marks band, run concurrently, full signup to session-end |
| `scripts/diagnostic_100.py` | 100-question harness by scenario class |
| `scripts/weekly_diagnostic.py` | Automated Monday canary: frontend, backend, DB, judge pipeline. Posts a report as a GitHub Issue |
| `scripts/regression_gate.py` | Pre-deploy gate. Judge-scores the golden dataset, exits non-zero under 90% |
| `scripts/pedagogy_drift_report.py` | Weekly per-topic scaffolding scores, flags anything under 1.5 |

Latest full run (2026-08-08, production, 5-way concurrency): **15/15 personas
passed.** Median first-response latency 15.2s, median follow-up 11.6s.

---

## Running locally

```bash
# Backend
poetry install
cp .env.example .env          # add OPENAI_API_KEY, DATABASE_URL, REDIS_URL
./scripts/run_migration.sh scripts/setup_db.sql
poetry run uvicorn app.main:app --reload

# Frontend
cd frontend/web
npm install
npm run dev
```

Migrations are always files under `scripts/migrate_vX_name.sql`, applied with
`./scripts/run_migration.sh`. Never ad-hoc DDL.

---

## Status

Pre-v1, running on free-tier infrastructure, ready for a small private beta.
Engine quality holds at 97% Socratic adherence and 100% factual accuracy on the
current eval set.

**A note on the demo:** the backend runs on Render's free tier, which sleeps
after 15 minutes of inactivity. If you are the first visitor in a while, the
first request can take up to a minute while the instance boots. The UI tells
you this is happening rather than just spinning. Everything after that is fast.
