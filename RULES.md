# RULES.md — Critical Invariants

Read this before every session. These are non-negotiable. Violating any of these creates silent bugs.

---

## 1. Sole Mastery Writer
`_genome_update_task` in `app/api/doubt.py` is the **only** place that updates `concept_mastery`.
Never add a second mastery update path anywhere — not in `engine.py`, not in a new endpoint, not inline.

## 2. Summarizer is Always Blocking
`summarize_session()` in `/session/end` must be **awaited** before the response returns.
Never fire-and-forget. Async summarizer = empty context on the next session. This bug already happened once.

## 3. Redis Failures are Always Silent
Every Redis call must be wrapped in `try/except`. A Redis failure must log and return gracefully — never raise, never crash the request. User flow must never depend on Redis being up.

## 4. Level 3 = Zero Teaching
At `hint_level >= 3`:
- Swap system prompt to `SYSTEM_PROMPT_FORCED_ATTEMPT` — never use `TUTOR_SYSTEM_PROMPT`
- Skip RAG entirely — `rag = {"context_text": "", "chunks": [], "chunk_count": 0}`
- Skip intent classification — route directly to `get_hint()`
- Skip `_analyze_student_response()`
If any of these are missing, students can trigger solution leaks through the forced attempt gate.

## 5. Model Routing
- `gpt-4o-mini` — classification, summarization, intent detection, memory compression
- `gpt-4.1-mini` — all Socratic responses, hints, full solutions
- `gpt-4o` — vision only (`_extract_question_from_image`)
Never use `gpt-4o` for text generation — cost is 10x with no quality gain for this use case.

## 6. LaTeX Sanitizer on Every Response
`_sanitize_latex()` must run on **every** LLM response before it is returned to the frontend.
If you add a new response path in `engine.py`, the sanitizer must be called. Missing it breaks KaTeX silently — no error, just broken rendering.

## 7. No Git Operations — Claude Never Commits or Pushes
Claude **never** runs `git add`, `git commit`, `git push`, `git reset`, `git rebase`, or any other git command that mutates history or the index. Even when the user says "commit this" or "push it", Claude only **prints the shell commands** for the user to copy and run themselves. No exceptions — not for small fixes, not for typos, not for documentation-only changes.

What Claude DOES do:
- Edit files (staged in working tree only)
- Print the exact `git add …` + `git commit -m "…"` + `git push origin …` commands
- Print them in separate code blocks so the user can copy one at a time
- Explain what each command will do

Read-only git commands are allowed (`git status`, `git log`, `git diff`, `git show`) for inspection.

Rationale: keeping the human in the loop for every commit prevents accidental pushes of half-finished work, ensures the user reviews the diff, and keeps the commit ritual intentional.

## 8. DB Migrations are Files
Every schema change must be written to a new `scripts/migrate_vX_name.sql` file.
Never run `ALTER TABLE` or `CREATE TABLE` directly in application code or ad-hoc in the shell.

## 11. DB is Supabase Cloud — Not Docker
The production database is Supabase cloud (`aws-0-us-west-2.pooler.supabase.com`, project `vgctqmhwezmihhmnwtzm`).
The `docker-compose.yml` Postgres container (`upmyrank-postgres`) is NOT used by the app — `DATABASE_URL` in `.env` points to Supabase.

**Run any migration with one command:**
```bash
./scripts/run_migration.sh scripts/migrate_vX_name.sql
```
`scripts/run_migration.sh` reads `DATABASE_URL` from `.env` and executes the SQL file via asyncpg (Poetry venv). No manual copy-paste, no Docker, no psql required.
Never reference Docker commands (`docker cp`, `docker exec psql`) for DB migrations.

## 9. Context Bundle Token Cap
`format_context_for_prompt()` hard cap is **350 tokens** enforced via tiktoken `cl100k_base`.
Never remove or raise this cap. Unbounded context injection will silently inflate costs per request.

## 10. Confidence is a Misconception Signal
High confidence + wrong answer = `error_type = "misconception"` — not a normal wrong answer.
Apply 1.5x mastery penalty. Pass `error_type` to `update_error_fingerprint()`. These require different remediation than knowledge gaps.

## 12. Subject Classification Must Degrade Gracefully
`_classify_subject()` in `engine.py` calls `gpt-4o-mini` at session start to route to Physics/Chemistry/Maths.
If the LLM call fails for any reason (timeout, API error, bad response), the method must catch the exception and return `"Physics"` as the default — never raise, never crash the session.
Subject classification failure must be logged as a warning only, not an error.

## 13. LaTeX Braces in Prompt Templates Must Always Be Double-Escaped
Any string constant in `prompts.py` that contains LaTeX `{...}` syntax AND is called with `.format()` will crash with a `KeyError` swallowed silently by the policy engine — causing every student to get the unpersonalized fallback prompt with no error visible in logs.
**Rule**: All `{` and `}` in LaTeX examples inside prompt template strings must be written as `{{` and `}}`.
Example: `\frac{a}{b}` in a format-string → must be written as `\\frac{{a}}{{b}}`.
Check any new prompt constant that both (a) contains LaTeX braces and (b) is passed to `.format()`. This applies to `TUTOR_SYSTEM_PROMPT`, `CUSTOMIZATION_PROMPT`, and any future prompt constants in the same pattern.
