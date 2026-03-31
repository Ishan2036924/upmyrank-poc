# UpMyRank — Living Project Memory

> **Maintainers:** Update this file whenever a major feature ships or an architectural decision is made.
> **Claude sessions:** Read this file at the start of every new session.

---

## Core Architecture

### "One Question = One Session" Flow

Each student doubt creates exactly one `doubt_session` row. The lifecycle is:

```
Student submits question
  → POST /doubt/ask
    → Intent classification (greeting / meta / emotional / out_of_scope / physics_doubt / continuation)
    → Problem analysis (GPT, temp=0.1, JSON output)
    → RAG retrieval (hybrid: vector + keyword, fused via RRF)
    → Socratic question generated (personalized to mastery level)
    → doubt_session created in DB (hint_level=0, resolved=false)
    → session_id returned to frontend

Student responds iteratively
  → POST /doubt/hint
    → Hint level escalates 0 → 1 → 2 → 3 → (4 = full solution)
    → On resolution: VerificationPipeline runs (SymPy + LLM fallback)
    → Background: concept_mastery EMA update, telemetry logged
```

### Knowledge Genome Mapping

Each student has a mastery score per concept (0–1), tracked via Exponential Moving Average:

```
new_mastery = 0.7 × old_mastery + 0.3 × performance_score
```

Performance scoring:
- Solved at hint_level 0 → 1.0
- After 1 hint → 0.9
- After 2 hints → 0.75
- After 3 hints → 0.55
- Gave up → 0.1

Spaced repetition (SM-2 inspired):
```
interval_days = max(1, int(6 × mastery / 0.3))
```

Mentor mode is selected based on overall mastery %:
- < 40% → COUNSELOR
- 40–60% → COACH
- 60–80% → TASKMASTER
- > 80% → STRATEGIST

### Prompt Engineering Constraints (Engine Invariants)

These are non-negotiable constraints baked into `app/services/doubt/prompts.py`. Do not weaken them.

**LaTeX enforcement (`TUTOR_SYSTEM_PROMPT`):**
- A `CRITICAL FORMATTING` block is injected at the top of the MATH FORMATTING section
- Plain-text fractions (`u / g`, `1/2 mv^2`) are explicitly banned
- Every fraction must use `\frac{}{}`, every vector must use `\vec{}`
- Block equations must have `$$` on their own separate lines — no characters touching delimiters
- This is required for frontend KaTeX rendering stability — violations break the UI

**Forced Attempt gatekeeper (`HINT_LEVEL_3_PROMPT`):**
- Prompt opens with "STOP teaching" — processed before any context
- `{analysis}` and `{context}` slots deliberately removed to prevent derivation leakage
- LLM is constrained to exactly 2 sentences: effort acknowledgement + demand for final answer
- No equations, formulas, derivations, steps, or "almost there" language permitted
- Purpose: enforce productive struggle — student must commit a full written attempt before solution is unlocked

### RAG Setup (Supabase / pgvector)

- **Embedding model**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Vector store**: PostgreSQL 16 + pgvector extension, HNSW index (cosine similarity)
- **Retrieval**: Hybrid search — vector similarity + ILIKE keyword matching, fused via Reciprocal Rank Fusion (K=60)
- **Knowledge base**: NCERT PDFs parsed via PyMuPDF, chunked, embedded, stored in `knowledge_chunks`
- **Search function**: `match_chunks(query_embedding, match_count, filter_subject)`
- **Frontend DB client**: `@supabase/supabase-js` (reads student mastery, sessions)

---

## Completed Features

### 1. Socratic AI Engine
- **File**: `app/services/doubt/engine.py`
- Classifies intent before routing (prevents LLM waste on greetings/off-topic)
- Generates Socratic questions (not answers) at hint_level=0
- 4 progressive hint levels, each more revealing
- Full solution + verification badge at hint_level 4
- Model routing: `gpt-4o-mini` (cheap tasks) vs `gpt-4.1-mini` (quality responses)

### 2. Hint Level System (0–4) — Strict 3-Hint Cutoff
- **Level 0**: Socratic question (no hints yet)
- **Level 1**: Conceptual nudge (identify the principle)
- **Level 2**: Structural/approach hint (how to set up the problem)
- **Level 3**: **FORCED ATTEMPT** — max hints reached; LLM asks student to write their full final answer. No more hints or partial solutions given until student responds.
- **Level 4+**: Full solution with two-layer verification (SymPy → LLM fallback)

**Enforcement gate** (`engine.py` → `get_hint()`): If `current_hint_level >= 3` and no `student_response` is provided (e.g. button click without typing), the engine returns a gate message and does NOT advance to full solution. Student must type their attempt first.

### 3. Two-Layer Verification Pipeline
- **File**: `app/services/verify/`
- Layer 1: SymPy symbolic math verification (extracts and solves equations)
- Layer 2: LLM semantic fallback when SymPy cannot parse
- Displayed as verification badges in UI (✓/✗)

### 4. Next.js Glassmorphic UI Overhaul
- **Stack**: Next.js 16, React 19, Tailwind CSS 4, Framer Motion, KaTeX
- Full dark glassmorphic design system across all pages
- Pages: `/` (home), `/doubt` (chat), `/practice`, `/mock`, `/progress`
- KaTeX math rendering inline in chat messages
- Typing indicator, verification badges, session state in sidebar
- Fixed Vercel build: `useSearchParams` wrapped in Suspense boundary

### 5. Dynamic Syllabus / Taxonomy + Topic-Locking
- **API**: `GET /taxonomy` → returns nested Subject → Chapter → Topic hierarchy
- **Component**: `SyllabusSelector.tsx` — topic picker in doubt UI
- **Wiring**: Selected topic passed as `topic_lock` param to `/doubt/ask`
- **Backend**: `topic_lock` injects into RAG filter and problem analysis context
- Limits RAG retrieval and Socratic context to the locked topic

### 6. V2 Session Schema (Study Sessions + Doubt Blocks)
- **Migration**: `scripts/migrate_v2.sql`
- `study_sessions`: browser-level session (2hr TTL), tracks `doubt_count`
- `doubt_blocks`: one per doubt within a study session, stores summary, hint_level, solved status
- Backward compatible (all new columns nullable)
- Endpoints: `POST /session/start`, `/session/end`, `/session/resume`

### 7. Mock Test Engine
- `POST /mock/generate` — picks random problem, generates 4 MCQ options via GPT
- `POST /mock/submit` — letter comparison, mastery update in background
- Frontend `/mock` page: timed test, topic/difficulty filters, post-test breakdown

### 8. Chat UI Pro Max Redesign
- **ChatMessage.tsx**: Dark student bubble (`bg-slate-900`), frameless AI text, avatar with ring+shadow, entrance animation `y:14→0 scale:0.97→1`, EASE_OUT_EXPO `[0.16,1,0.3,1]`
- **Badge system**: `HINT_LABELS` with icons (💡 Conceptual, 🔩 Structural, ✍️ Forced Attempt), Mentor mode badges, out-of-scope/full-solution/forced-attempt chips
- **Forced Attempt state**: Orange left border on AI frameless text, ✍️ badge, orange chip
- **Confidence badge**: Inside student dark pill with colored dot when `metadata.confidence` present
- **ChatInput.tsx**: Floating pill, `focus-within:ring-2 focus-within:ring-indigo-500/30`, send button `hover:scale-110 active:scale-90`

### 9. Analytics Dashboard Pro Max Redesign
- **progress/page.tsx**: Bento grid — mastery `col-span-2` with `text-6xl font-extrabold`, stagger animations triggered on data load (`animate={genome ? "visible" : "hidden"}`)
- **page.tsx (home)**: Bento action cards — Ask Doubt `col-span-2`, mentor greeting with left stripe + ambient gradient, hover-reveal CTA

### 10. Confidence Meter Intercept
- **ConfidenceMeter.tsx**: Glassmorphic card, 3 confidence buttons (🔴 Low / 🟡 Medium / 🟢 High), `whileHover: y:-2`, `whileTap: scale:0.93`
- **doubt/page.tsx**: `forcedAttemptActive` derived from last message metadata; intercepts send when active → shows ConfidenceMeter → on select, fires `/doubt/ask` with confidence attached to student message
- `AnimatePresence mode="wait"` swaps ChatInput ↔ ConfidenceMeter

### 11. Prompt Hardening
- See **Prompt Engineering Constraints** under Core Architecture for full invariant spec
- **`TUTOR_SYSTEM_PROMPT`**: `CRITICAL FORMATTING` block injected — bans plain-text fractions, mandates `\frac{}{}` and `\vec{}`, enforces `$$` block equation rules
- **`HINT_LEVEL_3_PROMPT`**: Stripped to 10 lines — `{analysis}` and `{context}` removed, 2-sentence output only, solution leakage structurally impossible

---

## Database Schema

### `knowledge_chunks` (RAG Knowledge Base)
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| content | TEXT | Raw NCERT chunk text |
| embedding | vector(1536) | HNSW cosine index |
| source_file | TEXT | PDF filename |
| subject | TEXT | e.g. "physics" |
| chapter | TEXT | |
| metadata | JSONB | page, chunk_index, etc. |

### `concept_mastery` (Knowledge Genome)
| Column | Type | Notes |
|--------|------|-------|
| student_id | UUID FK | |
| concept_id | TEXT FK | e.g. "relations.equivalence" |
| mastery_score | FLOAT | 0–1, EMA-tracked |
| error_count | INT | |
| attempt_count | INT | |
| last_reviewed | TIMESTAMP | |
| next_review_due | TIMESTAMP | SM-2 spaced repetition |
| error_pattern_array | JSONB | Mistake forensics tags |

### Other Key Tables
- **`students`**: id, name, exam_type (JEE/NEET), target_year
- **`concepts`**: id (text), subject, topic, subtopic, prerequisite_ids[]
- **`doubt_sessions`**: id, student_id, problem_text, current_hint_level (0–4), resolved, conversation_history (JSONB), concepts_involved, analysis (JSONB), `image_url TEXT` (added in `scripts/migrate_v3_vision.sql`)
- **`problems`**: id, question_text, question_latex, verified_answer, difficulty (0–1), topic, concepts_tested, embedding vector(1536)
- **`session_events`**: telemetry — event_type, time_to_solve_seconds, max_hint_level_used, mistake_forensics_tag, give_up_flag
- **`study_sessions`** (V2): study_session_id, student_id, started_at, ended_at, doubt_count
- **`doubt_blocks`** (V2): doubt_block_id, study_session_id, doubt_session_id FK, topic, hint_level, solved, summary

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| UI Animations | Framer Motion |
| Math Rendering | KaTeX, react-katex, rehype-katex |
| Charts | Recharts |
| Backend | FastAPI, Python 3.11, Uvicorn |
| DB Client (backend) | AsyncPG |
| DB Client (frontend) | @supabase/supabase-js |
| Database | PostgreSQL 16 + pgvector (HNSW, cosine) |
| LLM | OpenAI `gpt-4o-mini` (cheap: classification, summarization) / `gpt-4.1-mini` (quality: all Socratic responses, hints, solutions) |
| Embeddings | OpenAI text-embedding-3-small (1536-dim) |
| Math Verification | SymPy |
| PDF Parsing | PyMuPDF |
| Cache | Redis |
| Deployment | Vercel (frontend), Render (backend), Docker (local) |

---

## Known Bugs Fixed (2026-03-30 Audit) — ✅ All Implemented

Full engine audit was run and all identified bugs were fixed in the same session.

| Bug | File | Fix | Status |
|-----|------|-----|--------|
| Double mastery update (race condition) | `engine.py` | Removed entire eager EMA block from `get_hint()`; `_genome_update_task` in `doubt.py` is the sole canonical updater | ✅ |
| Mentor mode reassignment not persisted | `engine.py:354-356` | Mutates `stored_analysis["mentor_mode"]` at switch point; `UPDATE doubt_sessions` now writes `analysis` column on every hint | ✅ |
| RAG dict missing keys at hint level 3 | `engine.py` | `rag = {"context_text": "", "chunks": [], "chunk_count": 0}` — full shape even when empty | ✅ |
| Hint level 3 docstring said "70-80% solution" | `engine.py`, `prompts.py` | Updated to "FORCED ATTEMPT — zero teaching" | ✅ |
| LaTeX sanitizer only fixed first `$$` block | `engine.py` | Replaced `re.sub` with explicit `while` loop scanning all `$$` pairs | ✅ |
| Summarization failure logged as WARNING | `engine.py` | Escalated to `logger.error` with message noting recap will be broken | ✅ |

### Key Architectural Decisions from Audit
- **Mastery update is exclusively owned by `_genome_update_task`** in `doubt.py`. Never add a second update path in `engine.py`.
- **`stored_analysis` is the source of truth for `mentor_mode`** across hint calls. Always mutate it before the `UPDATE doubt_sessions` statement.
- **Level 3 = Forced Attempt (zero teaching). Level 4+ = Full Solution.** These are different states. Do not conflate them.

## Pending / Next Steps

### Vision AI — Image-to-Doubt (IN PROGRESS)
**Goal:** Let students photograph a textbook problem or handwritten question and submit it as an image instead of typed text.

**Stack:**
- **Storage**: Supabase Storage — `doubt-images` bucket (already created)
- **Vision model**: GPT-4o (multimodal — pass image URL in messages array)
- **DB migration**: `scripts/migrate_v3_vision.sql` — ✅ DONE (`image_url TEXT` column added to `doubt_sessions`)

**Remaining items:**

1. **`app/api/doubt.py`**: Change `question: str` → `question: str = ""`, add `image_url: Optional[str] = None`, replace `@field_validator` with `@model_validator(mode='after')` (allow empty question when image_url provided), pass `image_url` to `engine.start_session()`

2. **`app/services/doubt/engine.py`**: Add `image_url: Optional[str] = None` to `start_session()`, add `_extract_question_from_image(image_url, caption) → str` using GPT-4o vision, update `_create_session()` INSERT to include `image_url`

3. **`frontend/web/lib/supabase.ts`**: Create shared Supabase client (`NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY`)

4. **`frontend/web/lib/types.ts`**: Add `image_url?: string` to `ChatMessage.metadata`

5. **`frontend/web/components/ChatInput.tsx`**: Full rewrite — hidden file input (triggered by Plus button), instant local preview via `URL.createObjectURL()`, Supabase upload to `doubt-images` bucket, glass spinner overlay while uploading, remove (×) button, `canSend` true when text OR image present AND not uploading

6. **`frontend/web/components/ChatMessage.tsx`**: Add image thumbnail inside student dark bubble when `metadata.image_url` is present

7. **`frontend/web/app/doubt/page.tsx`**: Update `handleSend` signature to `(text, imageUrl?)`, pass `image_url` to `/doubt/ask`, attach to student message metadata

---

## Local Development Quick Reference

```bash
# Start DB + Redis
export DOCKER_HOST="unix://$HOME/.docker/run/docker.sock"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker compose up -d

# Start backend
PYTHONPATH="" PYTHONHOME="" /opt/miniconda3/bin/python3.11 -m poetry run uvicorn app.main:app --reload --reload-dir app --port 8000

# Start frontend
cd frontend/web && npm run dev
```

**Postgres connection:**
- Host: localhost:5432, DB: upmyrank, User: upmyrank, Password: upmyrank

**Environment files:**
- Backend: `.env` (copy from `.env.example`)
- Frontend: `frontend/web/.env.local`
