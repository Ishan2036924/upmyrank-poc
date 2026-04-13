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
    → Intent classification (greeting / meta / emotional / out_of_scope / subject_doubt / continuation)
    → Subject classification (gpt-4o-mini, routes to Physics/Chemistry/Maths)
    → Problem analysis (GPT, temp=0.1, JSON output)
    → Agentic RAG retrieval (AgenticRetriever: up to 3 tool calls, subject-aware)
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

**Forced Attempt gatekeeper (`HINT_LEVEL_3_PROMPT` + `SYSTEM_PROMPT_FORCED_ATTEMPT`):**
- At hint level 3, **both** the system prompt AND the user prompt are swapped — `TUTOR_SYSTEM_PROMPT` is replaced entirely with `SYSTEM_PROMPT_FORCED_ATTEMPT`
- `SYSTEM_PROMPT_FORCED_ATTEMPT` sets persona to "strict exam proctor", lists 6 ABSOLUTE RULES banning any equations/derivations/hints
- `HINT_LEVEL_3_PROMPT` contains only `{conversation_history}` and `{student_response}` — `{analysis}` and `{context}` slots removed
- RAG retrieval and genome injection are **skipped entirely** at level 3 — LLM cannot leak what it was never given
- `max_tokens=256`, `temperature=0.3` — tight budget prevents verbose drift
- LLM output constrained to exactly 2 sentences: effort acknowledgement + demand for final answer
- Purpose: enforce productive struggle — student must commit a full written attempt before solution is unlocked

### RAG Setup (Supabase / pgvector)

- **Embedding model**: OpenAI `text-embedding-3-small` (1536 dimensions) — confirmed, never all-MiniLM-L6-v2
- **Vector store**: PostgreSQL 16 + pgvector extension, HNSW index (cosine similarity)
- **Retrieval**: Agentic RAG — `AgenticRetriever` runs up to 3 tool calls via gpt-4o-mini function calling; tools: `search_ncert`, `search_jee_problems`, `search_concepts`, `rerank_and_select`
- **Legacy fallback**: Hybrid search (vector similarity + ILIKE, fused via RRF K=60) still available in `retriever.py` but not called directly — only through agentic loop
- **Knowledge base**: 15,069 total chunks — Physics 10,505 (HuggingFace KadamParth/Ncert_dataset) + Chemistry 3,138 (same HF dataset) + Maths 1,426 (NCERT PDFs parsed via pdfplumber from ncert.nic.in)
- **JEE PYQs**: 20 verified seed problems in `jee_problems` table (Physics + Chemistry + Maths)
- **Search functions**: `match_chunks(query_embedding, match_count, filter_subject)`, `match_jee_problems(query_embedding, match_count, filter_subject)`
- **Frontend DB client**: `@supabase/supabase-js` (reads student mastery, sessions)
- **SUPPORTED_SUBJECTS**: `("Physics", "Chemistry", "Maths")` constant in `prompts.py`

---

## Completed Features

### 0. Multi-Subject Knowledge Base (Physics + Chemistry + Maths) ✅

| Subject | Chunks | Source |
|---------|--------|--------|
| Physics | 10,505 | KadamParth/Ncert_dataset (HuggingFace) |
| Chemistry | 3,138 | KadamParth/Ncert_dataset (HuggingFace) |
| Maths | 1,426 | NCERT PDFs parsed via pdfplumber (ncert.nic.in) |
| **Total** | **15,069** | `knowledge_chunks` table |
| JEE PYQs | 20 | `jee_pyq_seed.json` (seed), `jee_problems` table |

- Ingestion scripts: `scripts/ingest_chem_maths.py` (Chem+Maths HF), `scripts/ingest_maths_pdf.py` (Maths PDF fallback), `scripts/ingest_jee_pyq.py` (PYQs)
- All scripts resumable via `.ingest_*_progress.json` files
- Embedding: OpenAI `text-embedding-3-small` (1536-dim) — all tables uniform

### 0b. RLS — Row-Level Security on All Tables ✅ (`migrate_v10_rls.sql`)

All 10 public tables have `rowsecurity = TRUE`:
- **Per-student ownership** (`auth.uid() = student_id`): `students`, `study_sessions`, `doubt_sessions`, `doubt_blocks`, `concept_mastery`, `session_events`, `student_memory`
- **Shared read-only** (any authenticated user): `concepts`, `knowledge_chunks`, `problems`
- FastAPI backend uses `postgres` superuser — bypasses RLS by design. No backend code changes needed for RLS.

### 0c. Agentic RAG (`app/services/rag/agent.py`, `app/services/rag/tools.py`) ✅

- `AgenticRetriever.run(question, subject, topic, question_type, hint_level)` — up to `MAX_STEPS=3` tool calls
- LLM: `gpt-4o-mini` for tool selection (cheap, fast)
- 4 tools: `search_ncert` (pgvector similarity on knowledge_chunks), `search_jee_problems` (jee_problems table), `search_concepts` (concepts table), `rerank_and_select` (dedup + score)
- Level-3 nuclear gate double-gated: checked in `agent.py` (returns `_EMPTY_CONTEXT` immediately) AND `engine.py` (sets `rag={context_text:"", chunks:[], chunk_count:0}`)
- Subject router: `_classify_subject()` in `engine.py` runs `gpt-4o-mini` at session start, pre-seeds agentic loop
- Called in exactly 3 places in `engine.py`: `start_session()`, `start_session_stream()`, `get_hint()` — never add a 4th

### 1. Socratic AI Engine
- **File**: `app/services/doubt/engine.py`
- Classifies intent before routing (prevents LLM waste on greetings/off-topic)
- Generates Socratic questions (not answers) at hint_level=0
- 4 progressive hint levels, each more revealing
- Full solution + verification badge at hint_level 4
- Model routing: `gpt-4o-mini` (cheap tasks) vs `gpt-4.1-mini` (quality responses)
- **Mastery updates**: exclusively handled by `_genome_update_task` background task in `doubt.py` on block close — never in `engine.py`
- **Mentor mode**: loaded from `stored_analysis["mentor_mode"]` each call; switches to COUNSELOR on frustration detection and is **persisted back** via `UPDATE doubt_sessions SET analysis = ...`
- **LaTeX sanitizer**: `_sanitize_latex()` runs on every LLM response — normalises `$$` delimiters and collapses `\n\n` inside all equation blocks

### 2. Hint Level System (0–4) — Strict 3-Hint Cutoff
- **Level 0**: Socratic question (no hints yet)
- **Level 1**: Conceptual nudge — RAG + genome injected, `TUTOR_SYSTEM_PROMPT`
- **Level 2**: Structural/approach hint — RAG + analysis injected, `TUTOR_SYSTEM_PROMPT`
- **Level 3**: **FORCED ATTEMPT** — RAG, analysis, and genome stripped entirely; `SYSTEM_PROMPT_FORCED_ATTEMPT` replaces `TUTOR_SYSTEM_PROMPT`; `max_tokens=256`, `temperature=0.3`; LLM output constrained to 2 sentences
- **Level 4+**: Full solution with two-layer verification (SymPy → LLM fallback), `max_tokens=2048`

**Enforcement gates** (three layers):
1. **Forced-attempt gate** (`engine.py` → `get_hint()`): If `current_hint_level >= 3` and no `student_response` is provided, the engine returns a static gate message and does NOT call the LLM at all. Student must type their attempt first.
2. **Progressive disclosure gate** (`engine.py` → `get_hint()`): `jump_to_full` is silently overridden to `False` if `current_level < 3`. Student gets the next normal hint with a "Nice try, but I'm not going to just give you the answer!" prefix.
3. **Therapist hijack bypass** (`doubt.py` → `/ask`): If the active doubt block is at `hint_level >= 3`, intent classification is **skipped entirely** — "I don't know", "skip", or emotional messages all route directly to `get_hint()` which produces the full solution. Response analysis (`_analyze_student_response`) is also skipped in `engine.py` at `current_level >= 3` to prevent COUNSELOR mode from intercepting.

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

### 12. Engine Hardening (2026-03-30 → 2026-03-31)
Two rounds of hardening after live test failures:

**Round 1 — Prompt patches (`prompts.py`)**
- `TUTOR_SYSTEM_PROMPT`: injected `CRITICAL FORMATTING` block banning plain-text fractions, mandating `\frac{}{}` + `\vec{}`, and explicitly banning `\n\n` inside equations or copy-pasting broken RAG chunk formatting
- `HINT_LEVEL_3_PROMPT`: rewritten to 10 lines, stripped of `{analysis}` and `{context}`
- `SYSTEM_PROMPT_FORCED_ATTEMPT`: new constant replacing `TUTOR_SYSTEM_PROMPT` at level 3 — "strict exam proctor" persona, 6 ABSOLUTE RULES

**Round 2 — Nuclear override + sanitizer (`engine.py`)**
- Level 3 RAG/genome fetch skipped entirely (`rag = {"context_text": "", "chunks": [], "chunk_count": 0}`)
- System prompt swapped to `SYSTEM_PROMPT_FORCED_ATTEMPT` at level 3 only
- `_sanitize_latex()` post-processor runs on every LLM response: normalises `$$` delimiter newlines, collapses `\n\n` inside all `$$` blocks via explicit `while` loop (not regex — handles multiple blocks), caps global newlines at 2

**Bug fixes applied in same session** — see Known Bugs Fixed table above.

### Multi-Subject Expansion (Physics → Physics + Chemistry + Maths) ✅ (2026-04-13)

Full audit and fix of all Physics-only hardcoded strings across the backend:

- **`prompts.py`**: 8 Physics-only spots replaced with multi-subject variants:
  - `INTENT_CLASSIFIER_SYSTEM`: now "JEE/NEET tutor covering Physics, Chemistry, and Maths"
  - `INTENT_CLASSIFIER_PROMPT`: `physics_doubt` → `subject_doubt` (backward-compat alias kept); subject-specific few-shot examples added
  - `GREETING_RESPONSES`, `META_RESPONSE`, `OUT_OF_SCOPE_RESPONSE`, `CONVERSATIONAL_RESPONSE`: all updated
  - `TUTOR_SYSTEM_PROMPT` + `CUSTOMIZATION_PROMPT` hard rules: "NCERT Physics" → "NCERT Physics, Chemistry, or Maths"
  - `SOCRATIC_QUESTION_PROMPT`: Chemistry + Maths probing examples added
  - `SYSTEM_PROMPT_FORCED_ATTEMPT`: "physics involved" → "subject matter involved"
  - `SUPPORTED_SUBJECTS = ("Physics", "Chemistry", "Maths")` constant added
  - `get_subject_context(subject)` and `build_system_prompt(personalization_block, subject)` subject-aware
- **`engine.py`**: `classify_intent()` now accepts `subject` param; `physics_doubt` normalized to `subject_doubt`; fallback intent is `subject_doubt`
- **`doubt.py`**: `AskRequest` has `subject_must_be_valid` field_validator; `classify_intent()` passes `subject=body.subject`; all `"intent": "physics_doubt"` → `"intent": "subject_doubt"`; topic fallback uses `body.subject or "General"` not `"Physics"`
- **`mock.py`**: `_MCQ_PROMPT` now `{subject}`-parameterised; `_generate_mcq_options()` accepts `subject`
- **Confirmed already multi-subject**: `misconceptions.py` (30 entries, Physics+Chemistry+Maths), `policy/engine.py` (`_SUBJECT_STYLE_OVERRIDES` per subject), `summarizer.py`, `onboarding.py`

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

### `jee_problems` (JEE PYQ Bank) — added `migrate_v11_jee_problems.sql`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | UUID5 deterministic from source+question |
| question_text | TEXT | |
| verified_answer | TEXT | |
| subject | TEXT | "Physics" / "Chemistry" / "Maths" |
| topic | TEXT | |
| difficulty | FLOAT | 0–1 |
| year | INT | Exam year |
| embedding | vector(1536) | HNSW cosine index |
| concepts_tested | TEXT[] | |

RLS: authenticated users read-only. `match_jee_problems()` function available.

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
| LLM — classification | OpenAI `gpt-4o-mini` — intent detection, subject routing, agentic tool selection, summarization, memory compression |
| LLM — Socratic | OpenAI `gpt-4.1-mini` — all Socratic responses, hints, full solutions, onboarding persona builder |
| LLM — vision | OpenAI `gpt-4o` — image-to-doubt feature only. Never for text. |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) — confirmed standard, all tables uniform |
| Math Verification | SymPy |
| PDF Parsing | pdfplumber (Maths PDFs), PyMuPDF (legacy) |
| Cache | Redis |
| Deployment | Vercel (frontend), Render (backend), Docker (local) |

---

## Known Bugs Fixed (2026-04-13 Audit)

| Bug | File | Fix | Status |
|-----|------|-----|--------|
| `build_system_prompt()` silent KeyError — every student got unpersonalized fallback prompt | `prompts.py:643` | Double-escaped LaTeX braces in `CUSTOMIZATION_PROMPT`: `{u^2 \\sin 2\\theta}` → `{{u^2 \\sin 2\\theta}}`, `{g}` → `{{g}}`. Same fix previously applied to `TUTOR_SYSTEM_PROMPT` | ✅ |

**Root cause pattern**: Any string constant in `prompts.py` that contains `{...}` for LaTeX and is called with `.format()` will crash with a silent `KeyError` swallowed by the policy engine. All LaTeX braces in prompt templates must be `{{}}` double-escaped.

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
| `jump_to_full` bypasses progressive disclosure | `engine.py` | Hard-gate: `jump_to_full` overridden to `False` if `current_level < 3`; "Nice Try" prefix injected | ✅ |
| Therapist hijack at forced-attempt stage | `doubt.py` + `engine.py` | Intent classification skipped when block at hint_level >= 3; response analysis skipped at `current_level >= 3` | ✅ |
| LaTeX `$$` not isolated on own lines | `prompts.py` | Added explicit block isolation mandate with wrong/correct examples to CRITICAL FORMATTING | ✅ |

### Key Architectural Decisions from Audit
- **Mastery update is exclusively owned by `_genome_update_task`** in `doubt.py`. Never add a second update path in `engine.py`.
- **`stored_analysis` is the source of truth for `mentor_mode`** across hint calls. Always mutate it before the `UPDATE doubt_sessions` statement.
- **Level 3 = Forced Attempt (zero teaching). Level 4+ = Full Solution.** These are different states. Do not conflate them.
- **`jump_to_full` is only honoured at `current_level >= 3`.** Below that, it is silently overridden to `False` — never remove this gate.
- **Intent classification is bypassed at forced-attempt stage** (active block `hint_level >= 3`). Any student response — emotional, off-topic, or otherwise — routes to full solution. Never add intent classification back at this stage.

### 15. Policy Engine + Student Persona Profile (Phase 2) ✅ COMPLETE

- **`scripts/migrate_v5_persona.sql`** — adds `persona_profile JSONB` to `student_memory`. ⚠️ NOT YET APPLIED TO DB (requires migrate_v4 first).
- **`app/services/policy/engine.py`** — `PedagogyConfig` dataclass + `select_pedagogy(persona_profile, topic, hint_level) → PedagogyConfig`. Logic table: HIGH → 2 concepts, analogies, encouraging; MEDIUM → 3 concepts, formula style, neutral; LOW → 5 concepts, application style, direct. Overrides: hint_level=0 always conceptual; hint_level≥3 always check_in=False.
- **`app/services/memory/context.py`** — 4 new functions: `get_persona_profile()` (default profile if null), `update_persona_profile()` (merge, not replace), `infer_scaffolding_level()` (avg mastery → HIGH/MEDIUM/LOW), `get_sessions_count()`.
- **`app/services/doubt/prompts.py`** — `CUSTOMIZATION_PROMPT` (global invariants), `PERSONALIZATION_PROMPT` (template), `build_system_prompt(personalization_block)`, `render_personalization(pedagogy_config)`. `TUTOR_SYSTEM_PROMPT` left untouched.
- **`app/services/doubt/engine.py`** — `start_session()` calls `get_persona_profile()` + `select_pedagogy()`, builds personalized system prompt via `build_system_prompt()`. `get_hint()` re-fetches persona from DB (avoids stale), rebuilds system prompt per hint level, appends max_concepts constraint for non-LOW students. Level 3 still uses `SYSTEM_PROMPT_FORCED_ATTEMPT` — rule untouched.
- **`app/api/doubt.py` — `_genome_update_task`** — updates `interaction_depth_score` (+0.05 if solved at hint ≤1, -0.02 otherwise). Re-infers scaffolding level every 5 sessions.

⚠️ Run `migrate_v5_persona.sql` to activate persona_profile column.

### 17. Judge LLM + Golden Dataset (Phase 4) ✅ COMPLETE

- **`scripts/migrate_v7_eval.sql`** — adds `scaffolding_score INTEGER`, `retrieval_similarity FLOAT`, `response_latency_ms INTEGER`, `hint_was_useful BOOLEAN` to `session_events`. ✅ Applied.
- **`data/golden_dataset.json`** — 50 triplets (id, topic, context_chunk, student_question, ideal_socratic_response, hint_level=0, misconception_addressed). 5 entries × 10 topics: Kinematics, Laws of Motion, Work-Energy, Circular Motion, Rotational Dynamics, Gravitation, Electrostatics, Current Electricity, Waves, Thermodynamics.
- **`app/services/eval/judge.py`** — `score_response(question, response) → {score: 0|1|2, rationale}`. Uses `gpt-4.1-mini` at `temp=0`. Returns `{score: -1, rationale: "judge_failed"}` on any error. Never raises.
- **`app/services/eval/logger.py`** — `log_scaffolding_score(session_id, score, rationale, db, retrieval_similarity, response_latency_ms)`. UPDATEs most recent `hint_requested`/`solution_revealed` event for the session. Never raises.
- **`app/services/doubt/engine.py`** — `get_hint()`: latency timer wraps LLM call (`time.monotonic()`). Max cosine similarity extracted from `rag["chunks"]`. Low similarity (< 0.5) logs a warning. After `_log_event`, fires `asyncio.create_task(_run_judge())` for hint_level < 3 — never blocks student response.
- **`scripts/pedagogy_drift_report.py`** — standalone async script. Queries last N days (default 7) of `session_events` with `scaffolding_score IS NOT NULL`, groups by topic, prints table. Flags topics avg < 1.5. Exit code 1 if any flagged. Run: `python scripts/pedagogy_drift_report.py [--days N]`.

---

### 16. Misconception Detection (Phase 3) ✅ COMPLETE

- **`scripts/migrate_v6_misconceptions.sql`** — adds `misconception_detected BOOLEAN`, `misconception_id VARCHAR(100)` to `doubt_blocks`; `misconception_detected BOOLEAN` to `session_events`. ✅ Applied.
- **`app/services/doubt/misconceptions.py`** — `Misconception` dataclass + 30-entry `MISCONCEPTION_LIBRARY` covering 8 topic areas (Circular Motion, Newton's Laws, Work & Energy, Rotational Dynamics, Electrostatics, Current Electricity, Waves, Thermodynamics). `check_for_misconception(response, topic)` — pure keyword matching, no LLM, < 1 ms.
- **`engine.py get_hint()`** — check fires after student response appended to history, before hint level increment. If matched and `hint_level < 3`: returns `correction_prompt` directly, no LLM call, no level increment, persists updated conversation history. Returns `is_misconception_correction=True, misconception_id=...`.
- **`_genome_update_task`** — `misconception_id: Optional[str]` param. When present + not resolved: 1.5× mastery penalty, `error_type="misconception"` fingerprint, `misconception_id` added to `persona_profile.common_misconceptions` (no duplicates). Session events `misconception_detected` populated.
- **Frontend** — `🧠 Misconception Detected` amber badge in `ChatMessage.tsx`.

---

## Pending / Next Steps

### Student Memory System (PLANNED — NOT STARTED)
3-layer memory with fixed ~300 token cost on every session start. Full build plan saved to Claude memory (`project_student_memory_plan.md`).

**Layers:**
1. **Redis hot context** — `hot:{student_id}` key, last 2 session summaries, 48hr TTL
2. **Postgres compressed profile** — `student_memory` table, one row per student, rewritten every 5 sessions by GPT-4o-mini
3. **Error fingerprints** — `error_fingerprint JSONB` on `concept_mastery`, decay × 0.7 on correct, +0.3 on wrong, prune < 0.1

**Files to create:** `scripts/migrate_v4_memory.sql`, `app/services/memory/context.py`, `app/services/memory/summarizer.py`
**Files to modify:** `app/services/doubt/prompts.py` (add `{student_context}` slot), `app/api/doubt.py` (wire bundle + blocking summarizer on session end)

**Key design decisions:**
- `summarize_session()` must be a **blocking call** on `/session/end` — not fire-and-forget (lesson from async race condition bug)
- Hard cap at 350 tokens via tiktoken — context never grows unbounded
- Redis read-first, Postgres fallback on cache miss

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
- **Supabase cloud**: `aws-0-us-west-2.pooler.supabase.com:5432`, project `vgctqmhwezmihhmnwtzm`
- `DATABASE_URL` in `.env` points to Supabase. Docker postgres container is NOT used.
- Run any migration: `./scripts/run_migration.sh scripts/migrate_vX_name.sql`

**Environment files:**
- Backend: `.env` (copy from `.env.example`)
- Frontend: `frontend/web/.env.local`
