# UpMyRank System Diagnostic — 2026-04-14

## Overall Health Score: 7.2/10

The platform is architecturally sound with well-enforced invariants. The main deductions are: two confirmed RULES violations (LaTeX sanitizer missing on `start_session()` non-streaming path; `emotional` response path also missing sanitizer), a second mastery update path in `mock.py` and `student.py`, zero judge evaluation data (pipeline built but never ran yet due to no completed sessions triggering it correctly), and a 683-duplicate-chunk data quality issue in the knowledge base. Core Socratic flow, Level 3 gate, and Redis resilience are all structurally correct.

---

## Traffic Lights

| Dimension | Status | Score |
|---|---|---|
| Retrieval Quality | 🟡 | 6/10 |
| Response Quality | 🟡 | 7/10 |
| Latency | 🟡 | 6/10 |
| Security | 🟡 | 7/10 |
| Data Quality | 🟡 | 7/10 |
| Feedback Calibration | 🔴 | 2/10 |
| Rules Compliance | 🟡 | 7/10 |
| Code Quality | 🟢 | 8/10 |

---

## Top 3 Critical Issues

### CRITICAL-1: LaTeX Sanitizer Missing on Non-Streaming `start_session()` Path (RULES violation #6)

`_sanitize_latex()` is called at 4 places in `engine.py`:
- Line 808: streaming `start_session_stream()` — correct
- Line 1029: misconception correction — correct
- Line 1271: `get_hint()` — correct
- Line 1537: `explanation` intent — correct

**Missing**: the non-streaming `start_session()` path (line 444–465) calls `_call_llm()` and stores `socratic_response` directly without running `_sanitize_latex()`. This affects all non-streaming `/doubt/ask` calls. The sanitizer normalizes `$$` delimiter placement and collapses `\n\n` inside equations — its absence can produce broken KaTeX rendering for the first turn of any non-streaming Socratic session. Additionally, the `emotional` intent path in `handle_non_physics_intent()` (lines 1516–1522) calls `_call_llm()` and returns the result without sanitizing it.

**Impact**: Silent rendering breakage. No error, just broken math in student chat.

### CRITICAL-2: Second Mastery Update Paths in `mock.py` and `student.py` (RULES violation #1)

RULES.md Rule 1 states `_genome_update_task` in `doubt.py` is the **only** place that updates `concept_mastery`. However:
- `app/api/mock.py` line 272: calls `update_concept_mastery()` directly in mock test submission
- `app/api/student.py` line 200: calls `update_concept_mastery()` directly in `PUT /student/{id}/mastery`

These are separate mastery write paths that bypass `_genome_update_task` and do NOT log `session_events`, do NOT apply the misconception 1.5x penalty, do NOT trigger `maybe_compress_profile()`, and do NOT wire into the pedagogy adaptation loop. Mock test mastery updates are "dark" — they won't affect persona evolution.

**Impact**: Mastery scores from mock tests are applied without the confidence modifier and misconception penalty logic. Mock test performance is effectively weighted identically to any other performance — the nuanced EMA in `_genome_update_task` does not apply.

### CRITICAL-3: 683 Duplicate Knowledge Chunks in knowledge_chunks

The DB query found 683 duplicate content rows across 15,069 total chunks (4.5%). These are exact content duplicates (same `content` string, different UUIDs). Duplicate chunks can:
- Inflate similarity scores and make lower-quality chunks appear more "retrieved"
- Push unique relevant content out of the top-k results
- Waste embedding storage
- Introduce subtle bias toward topics with more duplicate ingestion runs

Likely cause: resumable ingestion scripts ran multiple times without proper deduplication on `content` column (no UNIQUE constraint exists on `knowledge_chunks.content`).

---

## Top 5 Recommended Fixes (Priority Order)

### Fix 1 — Add `_sanitize_latex()` to non-streaming `start_session()` and `emotional` path (30 min)

In `engine.py`, add `socratic_response = self._sanitize_latex(socratic_response)` immediately after the `_call_llm()` return at line ~466 in `start_session()`, before the `out_of_scope` prefix append. Similarly, add `response = self._sanitize_latex(response)` after line 1522 in the `emotional` branch of `handle_non_physics_intent()`.

### Fix 2 — Deduplicate knowledge_chunks (1 migration file)

Create `scripts/migrate_v13_dedup_chunks.sql` that removes duplicate content rows using a `DELETE FROM knowledge_chunks WHERE id NOT IN (SELECT MIN(id) FROM knowledge_chunks GROUP BY content)` pattern with a CTE. Then add a `CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_chunks_content_hash ON knowledge_chunks(md5(content))` to prevent future duplicates. Run via `./scripts/run_migration.sh`.

### Fix 3 — Resolve mock.py mastery update path (1 hour)

Either: (a) wrap the `mock.py` `update_concept_mastery()` call in a proper `_genome_update_task`-compatible function that logs `session_events` and applies confidence modifiers, or (b) document and enforce that mock test mastery updates are intentionally "lightweight" (no session event, no persona update) with a comment explaining the deliberate deviation from Rule 1. Current state is an undocumented exception.

### Fix 4 — Populate judge_evaluations (ops task)

The `judge_evaluations` table has 0 rows despite the pipeline being fully implemented. The judge fires from `_run_judge_for_session()` in `POST /session/end`, which requires:
1. A study session was created
2. Doubt sessions were completed with conversation history
3. The doubt sessions were linked to `doubt_blocks` via `study_session_id`

Given 56 doubt sessions and 66 study sessions in DB, the 0 judge evaluations suggests either: (a) sessions are ending without linked `doubt_blocks` (confirmed: 16 doubt sessions have no blocks), or (b) the query in `_run_judge_for_session` requires a JOIN with `doubt_blocks` and those sessions without blocks are silently skipped. Fixing Fix 5 below would unblock judge eval data.

### Fix 5 — 16 Orphaned Doubt Sessions (no linked doubt_block)

16 out of 56 doubt sessions have no corresponding `doubt_blocks` row. This means: `_genome_update_task` never fires for these (no block close event), judge evaluations are skipped for them, and session end can't summarize them. These are likely sessions where `/doubt/ask` was called but no `study_session_id` was provided (so no `_create_doubt_block()` was called). The frontend should always pass `study_session_id` with every `/doubt/ask` request.

---

## Detailed Findings Per Dimension

### 1. Retrieval Quality (6/10)

**What was measured**: Code analysis of `AgenticRetriever`, database query of `session_metrics` (7 rows), and static analysis of tool schemas.

**Findings**:
- Agentic RAG is structurally sound: MAX_STEPS=3, gpt-4o-mini for tool selection, 4 tools (search_ncert, search_jee_problems, search_concepts, rerank_and_select), fallback NCERT search if no chunks accumulated.
- Session metrics (7 samples, too small for statistical confidence): avg retrieval latency 5,364ms (range: 3,842–6,861ms), avg agent_steps=2.43, avg chunks_retrieved=3.57.
- **5,364ms average retrieval latency is high** — this is the agentic loop calling gpt-4o-mini 2-3 times plus pgvector queries. Each tool LLM call has a 15s timeout.
- Loop termination: the agent terminates when the LLM sends no tool calls OR when MAX_STEPS is hit. No infinite loop risk (MAX_STEPS hard cap). Fallback to direct NCERT search if accumulated==[].
- **JEE PYQ bank too small**: only 20 seed problems (7 Physics, 7 Maths, 6 Chemistry). `search_jee_problems` will almost never return a close match for arbitrary student questions. This is a known deferred issue.
- **Maths knowledge gap**: 1,426 Maths chunks vs 10,505 Physics and 3,138 Chemistry. Maths retrieval is structurally weaker.
- **No similarity threshold enforcement**: The agentic tools return chunks by similarity ranking but do not enforce a minimum similarity threshold before injecting them into context. Low-similarity chunks may be accepted. No evidence of hallucination filtering.
- Semantic cache: scan-all-keys approach (`scan_iter`) is O(n) over all cached keys. At low scale (dev) this is fine, but at production scale with thousands of cached questions this will become a latency bottleneck. Pure-Python cosine similarity on 1536-dim embeddings is also slow.
- **Subject short-circuit**: correctly skips `_classify_subject()` gpt-4o-mini call when subject is pre-known from navigation, saving ~200ms.
- **Concepts table**: only 84 concepts, all Physics. No Chemistry or Maths concepts. `search_concepts` tool returns nothing useful for Chemistry/Maths questions.

### 2. Response Quality (7/10)

**What was measured**: Static analysis of all 6 prompt templates, Socratic constraint enforcement across hint levels, Level 3 structural gate, personalization injection.

**Findings**:
- **Socratic constraint**: enforced at hint_level 0 via `SOCRATIC_QUESTION_PROMPT` ("ask ONE probing question"), hint_level 1 via `HINT_LEVEL_1_PROMPT` (conceptual nudge, no formulas), hint_level 2 via `HINT_LEVEL_2_PROMPT` (structural, first step visible), hint_level 3 via `SYSTEM_PROMPT_FORCED_ATTEMPT` (exam proctor, zero teaching). Structurally correct.
- **Level 3 is clean**: `HINT_LEVEL_3_PROMPT` contains only `{conversation_history}` and `{student_response}` — no `{analysis}`, no `{context}` slots. `agent.py` returns `_EMPTY_CONTEXT` immediately at `hint_level==3`. Double gate confirmed.
- **LaTeX sanitizer missing on non-streaming `start_session()`**: See CRITICAL-1.
- **CUSTOMIZATION_PROMPT double-escaping**: Verified correct. `\\frac{{u^2 \\sin 2\\theta}}{{g}}` is properly escaped. Rule 13 fixed and correctly applied.
- **`PERSONALIZATION_PROMPT`**: correctly injects `learning_preference`, `subject_strengths_block`, `priority_subject_block` from `persona_profile`. `render_personalization()` falls back gracefully to defaults if `persona_profile` is None.
- **Policy engine fallback**: `build_system_prompt()` call is wrapped in try/except. On failure, falls back to `TUTOR_SYSTEM_PROMPT` with the "Policy engine failed (non-fatal)" warning. This fallback was the source of the Rule 13 bug — the warning should be monitored but the fallback itself is safe now.
- **`emotional` intent path missing sanitizer**: `handle_non_physics_intent()` calls `_call_llm()` for emotional responses but does not run `_sanitize_latex()` on the result. Low impact (emotional responses rarely contain math) but technically a Rule 6 violation.
- **CONTEXT LOCK instructions present**: `HINT_LEVEL_1_PROMPT`, `HINT_LEVEL_2_PROMPT`, `FULL_SOLUTION_PROMPT`, and `SOCRATIC_QUESTION_PROMPT` all include "CONTEXT LOCK — MANDATORY" instructions preventing generic example substitution. Good.
- **0 judge evaluations**: Cannot compute empirical response quality scores. All quality assessments are static analysis only.

### 3. Latency (6/10)

**What was measured**: Code analysis for theoretical latency breakdown, session_metrics data (7 samples).

**Theoretical cold-path latency for a new uncached question**:

| Step | Component | Est. Cost |
|---|---|---|
| Subject classification | gpt-4o-mini (skipped if subject known) | 0–300ms |
| Problem analysis | gpt-4o-mini, 600 tokens | ~500ms |
| Agentic RAG | 2-3 LLM calls × gpt-4o-mini + pgvector | 3,000–6,000ms |
| Genome injection | asyncpg query | ~50ms |
| Policy engine | pure Python | ~5ms |
| Socratic LLM | gpt-4.1-mini, 1024 tokens | ~1,500ms |
| DB writes | asyncpg | ~100ms |
| **TOTAL** | | **~5,000–8,000ms** |

**Observed**: avg 5,364ms retrieval + LLM response overhead → total likely 6,000–8,000ms for first turn.

**Cache hit path**: embedding lookup + Redis scan → ~200–500ms. O(n) Redis scan grows with cache size.

**Key concerns**:
- No timeout on the main Socratic LLM call (`_call_llm()` has no `asyncio.wait_for`). A slow OpenAI response would hang the request indefinitely.
- Session summarizer on `/session/end` is blocking with a 3s timeout on the LLM call. If the LLM is slow, `/session/end` takes 3+ seconds.
- Render cold start addressed via `fetchWithRetry()` on frontend.
- **`--reload` flag noted** in MEMORY.md as planned fix for Render deployment (not yet done).

### 4. Security (7/10)

**What was measured**: Input validation in `AskRequest`, exception string exposure, Redis error handling, RLS policy coverage, `.claude/settings.json`.

**Findings**:

**Input validation (Good)**:
- `AskRequest` has `@field_validator` for `subject` (valid set), `question` (strip, no empty), and `@model_validator` for at_least_one_of.
- `HintRequest` lacks validators on `session_id` (UUID format not validated at model level — validated inside `get_hint()` via `uuid.UUID(session_id)` which raises `ValueError`).

**Raw exception string exposure (Moderate risk)**:
- `doubt.py` lines 583, 586, 613, 616, 697, 700: `raise HTTPException(status_code=4xx/5xx, detail=str(exc))` — internal exception messages (DB errors, asyncpg errors) are exposed in API response bodies. This can leak table names, query structure, and internal state to frontend clients.
- SSE streaming paths (lines 894, 897, 959): `{"error": str(exc), "done": True}` — same issue in streaming context.
- Line 982: `HTTPException(status_code=500, detail=str(exc))`.
- **Recommendation**: Replace `detail=str(exc)` with generic messages (e.g., "Session not found" / "Internal error") and log the full exception server-side only.

**Redis errors**: All Redis calls are properly wrapped in try/except with logger.warning. Rule 3 is structurally enforced. Confirmed in `context.py`, `summarizer.py`, and `semantic_cache.py`.

**RLS coverage**:
- All 14 public tables have `rowsecurity = TRUE`. Coverage: complete.
- Per-student tables (students, study_sessions, doubt_sessions, doubt_blocks, concept_mastery, session_events, student_memory, response_feedback): all have student-ownership policies.
- Shared read-only tables (concepts, knowledge_chunks, problems, jee_problems): authenticated SELECT only.
- Backend tables (judge_evaluations, session_metrics): `USING (TRUE)` — effectively open to all roles. Intentional (backend superuser access pattern), but note that if Supabase client ever reads these tables directly from frontend, all rows are accessible.

**Admin gate**: ADMIN_STUDENT_ID UUID comparison in settings. Secure for POC. No SQL injection risk (comparison is `str(student_id) == settings.admin_student_id`).

**`.claude/settings.json`**: Supabase CLI commands blocked (`npx supabase *`). Destructive DB commands blocked (DROP, DELETE FROM, TRUNCATE). `git push` blocked. Pattern is correct.

**No CORS wildcard**: `allow_origins` is an explicit list + Vercel preview regex. Not using `"*"`. Good.

### 5. Data Quality (7/10)

**What was measured**: DB queries for chunk quality, duplicate detection, mastery range validation, orphan checks.

**Findings**:
- **Total chunks**: 15,069 (matches CLAUDE.md documented count exactly)
- **Subject distribution**: Physics 10,505 / Chemistry 3,138 / Maths 1,426 — matches documented values
- **Empty/null content**: 0 rows with empty content, 0 rows with missing embeddings — clean
- **683 duplicate chunks** (same content, different UUID): 4.5% of the corpus. Likely from resumable ingest scripts re-running. No UNIQUE constraint on content. This is a meaningful quality issue.
- **Mastery scores**: min=0.0, max=0.207, avg=0.002 — extremely low. This reflects a very small student base (4 students) in early sessions. No scores outside [0,1]. Constraint enforced by schema CHECK.
- **Orphaned mastery rows**: 0 — all concept_mastery rows reference valid students
- **Concepts table**: 84 concepts, all Physics. No Chemistry/Maths concepts ingested. The `search_concepts` RAG tool returns 0 results for Chemistry and Maths questions.
- **Doubt sessions without doubt_blocks**: 16 out of 56 (28.6%). These sessions were created via `/doubt/ask` without a `study_session_id`, so no `_create_doubt_block()` was called. These sessions are partially tracked — mastery updates and judge evals cannot fire for them.
- **JEE problems**: 20 total (Physics 7, Maths 7, Chemistry 6) — too small for meaningful retrieval. Known deferred issue.
- **Session events**: 124 total — question_asked (56), hint_requested (38), solution_revealed (17), session_terminal (13). The 13 session_terminal events vs 56 doubt sessions indicates most sessions are not properly closed (genome update not firing for the other 43 sessions).

### 6. Feedback Calibration (2/10)

**What was measured**: `response_feedback` table row count, `judge_evaluations` row count.

**Findings**:
- **0 thumbs up/down ratings** in `response_feedback` table. The ThumbsUp/ThumbsDown UI is implemented in `ChatMessage.tsx` and `doubt/page.tsx`, and the `POST /feedback/response` endpoint is wired. Zero data means the feature has not been used yet (likely never triggered in production sessions).
- **0 judge evaluations** in `judge_evaluations` table. The 4-dimension judge pipeline fires from `_run_judge_for_session()` at `POST /session/end`. Given 66 study sessions in DB, this should have data. Root cause: the judge query JOINs `doubt_sessions` with `doubt_blocks` via `study_session_id` — but 16 doubt sessions have no `doubt_blocks` (orphaned sessions), so the JOIN returns 0 rows for those. For the sessions that DO have blocks, the judge may not be getting called (sessions ending without proper doubt block linkage).
- **Correlation analysis**: impossible with 0 data points on both sides.
- **Score**: 2/10 (pipeline built and correct, but 0 data — cannot measure calibration).

### 7. Rules Compliance (7/10)

**RULES.md Invariant Audit** (checked all 13 rules):

| Rule | Check | Status |
|---|---|---|
| Rule 1: Sole mastery writer (`_genome_update_task`) | `mock.py` line 272 and `student.py` line 200 both call `update_concept_mastery()` directly, bypassing `_genome_update_task` | **VIOLATION** |
| Rule 2: Summarizer is blocking | `await summarize_session(...)` at `session.py:230` — correctly blocking | PASS |
| Rule 3: Redis failures are silent | All 3 Redis call sites (context.py, summarizer.py, semantic_cache.py) have try/except with logger.warning | PASS |
| Rule 4: Level 3 = zero teaching | Double-gated: agent.py returns `_EMPTY_CONTEXT` at hint_level==3; engine.py uses `SYSTEM_PROMPT_FORCED_ATTEMPT` + no analysis/context slots in prompt; `_analyze_student_response` skipped at `current_level >= 3` | PASS |
| Rule 5: Model routing | gpt-4o only in `extract_question_from_image()` (vision). gpt-4.1-mini for Socratic/hints. gpt-4o-mini for classify/summarize/agent/judge. Correct. | PASS |
| Rule 6: LaTeX sanitizer on every response | Missing on non-streaming `start_session()` path and `emotional` intent in `handle_non_physics_intent()` | **VIOLATION** |
| Rule 7: No git operations | Not applicable (runtime rule) | N/A |
| Rule 8: DB migrations are files | All schema changes via `scripts/migrate_v*.sql`. Confirmed by session log. | PASS |
| Rule 9: Context bundle 350-token cap | `format_context_for_prompt()` enforces `_MAX_TOKENS = 350` via tiktoken. `_truncate_to_tokens()` applied. | PASS |
| Rule 10: Confidence is misconception signal | `_genome_update_task` applies 1.5× penalty when `student_confidence == "high" and not resolved`. Correctly implemented. | PASS |
| Rule 11: DB is Supabase cloud | DATABASE_URL in `.env` points to Supabase cloud. Docker container not used. | PASS |
| Rule 12: Subject classification degrades gracefully | `_classify_subject()` has try/except returning "Physics" as default on any failure. | PASS |
| Rule 13: LaTeX braces double-escaped | `CUSTOMIZATION_PROMPT` verified: `\\frac{{u^2 \\sin 2\\theta}}{{g}}` correctly escaped. `TUTOR_SYSTEM_PROMPT` verified. All LaTeX examples in `.format()`-called templates checked. | PASS |

**Summary**: 2 violations (Rules 1 and 6), 10 passes, 1 N/A.

### 8. Code Quality (8/10)

**What was measured**: Code structure, error handling patterns, separation of concerns, TypeScript build.

**Findings**:
- **TypeScript build**: `npx tsc --noEmit` completed with 0 errors (confirmed by session log 2026-04-14 and verified via bash run which produced no output).
- **Encapsulation**: Engine layer (`engine.py`) is clean — no direct DB pool calls from tools layer. `_rag_metrics` pattern for surfacing telemetry without breaking layer boundaries is elegant.
- **Error handling**: most code paths follow the "never raise from non-fatal paths" principle. Main exception is `doubt.py` exposing `str(exc)` in HTTP response detail fields.
- **Background tasks**: `asyncio.create_task()` used correctly for fire-and-forget (judge eval, cache write, metrics write). `maybe_compress_profile()` is background. `summarize_session()` is correctly blocking.
- **`_parse_json_response()`**: robust — handles markdown fences and regex-searches for first `{...}` block on parse failure. Good defensive coding.
- **Semantic cache linear scan**: `scan_iter()` over all `semantic_cache:*` keys with per-key GET + cosine_similarity — O(n) with no batching. At >100 cached questions this will cause measurable latency spikes.
- **`judge.py` creates a new `openai.AsyncOpenAI` client per call**: `client = openai.AsyncOpenAI(api_key=settings.openai_api_key)` inside `evaluate_response()`. This creates a new HTTP client pool per judge invocation (which fires as `asyncio.create_task`). Should reuse the singleton client from `app.state.socratic_engine._client`.
- **`summarizer.py` also creates a new client per call**: same pattern.
- **Import pattern**: `from app.services.doubt.prompts import SUPPORTED_SUBJECTS` inside function bodies (lines 376, 696). These should be top-level imports. Currently they work but add per-call import overhead.
- **`_close_doubt_block()` summarizer is fire-and-forget**: `asyncio.create_task(engine.summarize_doubt_block(...))`. This is intentional per architecture but means the summary may not be written before `session/end` is called if the study session ends immediately after a doubt block closes. This is documented as acceptable.

---

## Database Stats Snapshot

All queries executed via asyncpg against Supabase cloud (2026-04-14).

### Knowledge Chunks
| Metric | Value |
|---|---|
| Total chunks | 15,069 |
| Physics | 10,505 |
| Chemistry | 3,138 |
| Maths | 1,426 |
| Empty content | 0 |
| Missing embeddings | 0 |
| Duplicate content rows | 683 (4.5%) |

### Students & Sessions
| Metric | Value |
|---|---|
| Total students | 4 |
| Onboarding completed | 3 |
| Onboarding not done | 1 |
| Study sessions | 66 |
| Doubt sessions | 56 |
| Doubt sessions (resolved) | 16 |
| Doubt sessions (unresolved) | 40 |
| Avg hint level at resolution | 1.29 |
| Doubt sessions with no blocks | 16 (28.6%) |

### Concept Mastery
| Metric | Value |
|---|---|
| Total records | 84 |
| Min mastery score | 0.000 |
| Max mastery score | 0.207 |
| Avg mastery score | 0.002 |
| Out of range [0,1] | 0 |
| Orphaned rows | 0 |

### Concepts Table
| Subject | Count |
|---|---|
| Physics | 84 |
| Chemistry | 0 |
| Maths | 0 |
| **Total** | **84** |

### JEE Problems
| Subject | Count |
|---|---|
| Physics | 7 |
| Maths | 7 |
| Chemistry | 6 |
| **Total** | **20** |

### Session Events
| Event Type | Count |
|---|---|
| question_asked | 56 |
| hint_requested | 38 |
| solution_revealed | 17 |
| session_terminal | 13 |
| **Total** | **124** |

### Session Metrics (7 rows)
| Metric | Value |
|---|---|
| Avg retrieval latency | 5,364ms |
| Max retrieval latency | 6,861ms |
| Min retrieval latency | 3,842ms |
| Avg agent steps | 2.43 |
| Avg chunks retrieved | 3.57 |

### Judge Evaluations
| Metric | Value |
|---|---|
| Total rows | 0 |
| Avg pedagogical score | N/A |
| Avg factual score | N/A |
| Avg overall score | N/A |

### Feedback
| Metric | Value |
|---|---|
| Total feedback rows | 0 |
| Thumbs up | 0 |
| Thumbs down | 0 |

### RLS Coverage
All 14 public tables have `rowsecurity = TRUE`. 16 policies total:
- Per-student ownership (7 tables): students, study_sessions, doubt_sessions, doubt_blocks, concept_mastery, session_events, student_memory
- Read-only authenticated (4 tables): concepts, knowledge_chunks, problems, jee_problems
- Open service role (2 tables): judge_evaluations, session_metrics
- Per-student with 3 operations (1 table): response_feedback (SELECT / INSERT / UPDATE)

---

## Methodology

### Files Read
- Project docs: CLAUDE.md, RULES.md, MEMORY.md (chunked), docs/bugs.md, docs/decisions.md, docs/session_log.md
- Backend source: engine.py (full, 1900+ lines), prompts.py, agent.py, tools.py (partial), doubt.py, session.py, feedback.py, admin.py, judge.py, context.py, summarizer.py, policy/engine.py, semantic_cache.py, config.py, main.py
- Schema files: setup_db.sql (partial), migrate_v12_feedback.sql

### Queries Executed
All DB queries ran successfully against Supabase cloud via asyncpg using project `.venv`. Tables queried: knowledge_chunks, students, study_sessions, doubt_sessions, concept_mastery, judge_evaluations, session_metrics, response_feedback, jee_problems, session_events, concepts, doubt_blocks, pg_tables, pg_policies.

### Items Not Measured
- **Live API response quality**: no live requests were sent — all response quality analysis is static prompt inspection only.
- **Actual Redis state**: Redis container state not queried (semantic cache contents, hot context data).
- **Frontend runtime behavior**: TypeScript build verified (0 errors), but no browser testing.
- **Render deployment state**: production deployment not queried. Cold start behavior is code-analyzed only.
- **Regression gate score**: `scripts/regression_gate.py` not run — would require OpenAI API call. Golden dataset has 20 Q&A pairs.
- **RAGAS eval**: `scripts/eval_ragas.py` not run — requires live API.
- **Retrieval recall rate**: no benchmark run against JEE PYQ test set.
- **Model latency variance**: 7 session_metrics rows is insufficient for statistical confidence (P95, outliers).
