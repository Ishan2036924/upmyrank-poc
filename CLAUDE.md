# Claude Code Instructions — UpMyRank

**FIRST ACTION EVERY SESSION: Read `docs/session_log.md` before anything else.**

ALWAYS read `MEMORY.md` and `RULES.md` at the start of any new session. `RULES.md` contains hard invariants — violating them creates silent bugs. `MEMORY.md` has the current project state. Whenever you complete a major feature or make an architectural decision, update `MEMORY.md` to reflect the new state.

## Project Overview
UpMyRank is an AI-powered JEE/NEET tutoring platform. Core architecture follows the PTB (Python Tutor Bot) educational AI framework: Customization layer (global rules) + Personalization layer (student model) + Golden Dataset (truth control). The LLM is a composer — not the source of knowledge. The system architecture is the product.

## 🧠 Conditional Context

- When doing Frontend/UI Tasks: If the user asks you to build, style, or update a React/Next.js UI component, you MUST read `UI_PRO_MAX.md` before writing any code to ensure premium execution.

## Key Principles

- Optimize for **learning gain**, not user satisfaction. Desirable difficulty is intentional.
- **Policy Engine first** — always determine HOW to teach before generating a response.
- **Misconceptions ≠ knowledge gaps** — wrong thinking requires different treatment than wrong answers.
- **Measure pedagogy, not just accuracy** — Judge LLM scores Socratic quality on every response.
- Never add a second mastery update path. `_genome_update_task` in `doubt.py` is the sole owner.
- Session summarizer is always blocking on `/session/end`. Never fire-and-forget.
- Redis failures are always silent. Never crash a user-facing flow on a Redis error.
- Level 3 (FORCED ATTEMPT) structurally starves the LLM — clear RAG + analysis context, swap system prompt. Don't rely on instructions alone to prevent leakage.

## Current Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11), asyncpg, Pydantic v2 |
| LLM | gpt-4.1-mini (Socratic/hints), gpt-4o-mini (classify/summarize), gpt-4o (vision only) |
| Vector DB | pgvector 0.8.2 on Postgres 16 |
| Cache / Hot Context | Redis (redis.asyncio) |
| Embeddings | sentence-transformers (384-dim) |
| Token counting | tiktoken cl100k_base |
| Frontend | Next.js 14, TypeScript, Tailwind, Framer Motion |
| ORM | Raw asyncpg (no ORM) |
| Config | pydantic-settings, `.env` |
| Package manager | Poetry (`.venv` in-project) |
| Infra (local) | Docker Desktop (arm64), named volumes |

## Critical Rules — Do Not Violate

See `RULES.md` for the full invariant list. Summary:

1. **Never `git commit` or `git push`** unless explicitly asked.
2. **`_genome_update_task` is the sole mastery writer** — never add a second EMA update elsewhere in the codebase.
3. **`summarize_session()` must always be awaited** on `/session/end` — never wrap in `create_task()`.
4. **Redis errors must never propagate** — always catch and log as warning, never raise.
5. **Level 3 = zero teaching** — swap prompt to `SYSTEM_PROMPT_FORCED_ATTEMPT`, skip RAG, skip intent classification, skip `_analyze_student_response()`.
6. **Model routing**: `gpt-4.1-mini` for Socratic/hints, `gpt-4o-mini` for classify/summarize, `gpt-4o` for vision only. Never use `gpt-4o` for text.
7. **LaTeX sanitizer runs on every LLM response** — never skip `_sanitize_latex()`.
8. **DB migrations are files** — write to `scripts/migrate_vX_name.sql`, never ad-hoc ALTER TABLE.
9. **DB migration pattern**: always `docker cp file.sql container:/tmp/` then `psql -f /tmp/file.sql`. Heredoc does not work with `docker exec`.

## File Map — Key Files to Know

```
app/
  api/
    doubt.py          — /doubt/ask, /doubt/hint, /doubt/verify + _genome_update_task
    session.py        — /session/start, /session/end, /session/resume
    student.py        — /student/{id} (includes persona_profile), mastery update
    onboarding.py     — POST /onboarding/submit (GPT-4.1-mini persona builder), GET /onboarding/status
  services/
    doubt/
      engine.py       — SocraticEngine: start_session(), get_hint(), classify_intent()
      prompts.py      — All prompt constants (TUTOR_SYSTEM_PROMPT, SYSTEM_PROMPT_FORCED_ATTEMPT, CUSTOMIZATION_PROMPT, PERSONALIZATION_PROMPT, SOCRATIC_QUESTION_PROMPT, HINT_LEVEL_*_PROMPT) + build_system_prompt(), render_personalization()
      misconceptions.py — 30-entry MISCONCEPTION_LIBRARY + check_for_misconception(response, topic) → Misconception|None
      retriever.py    — RAG: pgvector similarity search
      context.py      — RAG context assembly, genome injection
    memory/
      context.py      — build_context_bundle(), format_context_for_prompt(), update_error_fingerprint(), update_forgetting_rate(), get_persona_profile(), update_persona_profile(), infer_scaffolding_level(), get_sessions_count()
      summarizer.py   — summarize_session() [blocking], update_hot_context() [Redis], maybe_compress_profile() [background]
    policy/
      engine.py       — PedagogyConfig dataclass, select_pedagogy(persona_profile, topic, hint_level) → PedagogyConfig
    eval/
      judge.py        — score_response(question, response) → {score: 0|1|2, rationale} via gpt-4.1-mini temp=0
      logger.py       — log_scaffolding_score(session_id, score, rationale, db, ...) UPDATE session_events
    mastery.py        — update_concept_mastery() EMA helper
  db/
    database.py       — asyncpg pool: init_db(), close_db(), get_pool()
  config.py           — Settings: openai_api_key, redis_url, model_smart, model_cheap
  main.py             — FastAPI lifespan, router registration, app.state setup

scripts/
  setup_db.sql              — Base schema
  migrate_v4_memory.sql     — Student Memory System schema (⚠️ NOT YET APPLIED TO DB)
  migrate_v5_persona.sql    — Adds persona_profile JSONB to student_memory ✅
  migrate_v6_misconceptions.sql — Adds misconception_detected/misconception_id to doubt_blocks + session_events ✅
  migrate_v7_eval.sql           — Adds scaffolding_score, retrieval_similarity, response_latency_ms, hint_was_useful to session_events ✅
  migrate_v8_onboarding.sql     — Adds onboarding_completed, class_level, physics_prev_marks, study_hours_per_day, exam_date to students ✅
  pedagogy_drift_report.py      — Standalone weekly report: avg scaffolding_score per topic, flags < 1.5
  regression_gate.py            — Pre-deploy gate: scores golden dataset with Judge LLM, exit 1 if pass_rate < 0.90

app/
  api/
    admin.py              — GET /admin/metrics?days=N → socratic_adherence_rate, avg_retrieval_similarity, latency_p95, per-topic breakdown
    doubt.py              — POST /doubt/ask/stream — SSE streaming variant; yields {"token","done"} events
  services/
    cache/
      semantic_cache.py   — get_cached_response(embedding, threshold=0.92), cache_response(), cosine_similarity()

frontend/web/
  app/doubt/page.tsx        — Main chat UI; unified SSE streaming for all intents; continuation keepalive; streamingMsgId state
  app/admin/page.tsx        — Eval dashboard: adherence rate, retrieval confidence, latency P95, per-topic score bars
  app/onboarding/page.tsx   — 4-step onboarding flow (class level → topic chips → study plan → persona summary card)
  app/auth/login/page.tsx   — Checks /onboarding/status after login, redirects to /onboarding if needed
  app/auth/signup/page.tsx  — Always redirects new signups to /onboarding
  components/ChatInput.tsx  — Input + ConfidenceMeter with AnimatePresence swap
  components/ChatMessage.tsx — Message renderer with LaTeX + badge display
  components/Sidebar.tsx    — Slim desktop nav + mobile panel; LEARNING PROFILE section (level badge, style, weak concepts)
```

## Auto-Read Rules (for Claude Code sessions)

- **Every session, always:** Read `docs/session_log.md` — it's small (~30 lines) and tells you exactly what was happening last time, what's half-done, and what files matter right now. Never skip it.
- **Default (any coding task):** CLAUDE.md + `docs/session_log.md`. Nothing else unless triggered below.
- **"fix" / "bug" / "broken" / "error" / "failing" / "not working" in my prompt:** Also read `docs/bugs.md`
- **"new feature" / "build" / "implement" / "add" / "create" in my prompt (for a feature):** Also read `docs/decisions.md` + `docs/bugs.md`
- **"review" / "check" / "audit" in my prompt:** CLAUDE.md + `docs/session_log.md` is sufficient
- **"architecture" / "design" / "should we use" / "migrate" / "refactor" in my prompt:** Also read `docs/decisions.md`
- **"deploy" / "migration" / "database" / "schema" in my prompt:** Also read `docs/decisions.md` + `docs/bugs.md`
- **I explicitly say "full context":** Read CLAUDE.md + `docs/session_log.md` + `docs/decisions.md` + `docs/bugs.md`
- **Never auto-load all four unless I say "full context".** Token budget matters.
- **End of session:** Run `/handoff` to write the session entry into `docs/session_log.md`.
