# Bug History — UpMyRank

## Concept Card mastery score showed global average not topic-specific — fixed (v0.20.4, 2026-04-21)
**Symptom:** Every Concept Card a student opened showed the same "Mastery: X%" number, regardless of topic. Render log: `INFO:app.services.study.card_composer:mastery lookup via concepts JOIN failed (column c.concept_id does not exist), falling back`.
**Root cause:** `_compose_mastery()` in `app/services/study/card_composer.py` joined `concepts c ON c.concept_id = concept_mastery.concept_id`. The column on `concepts` is `id`, not `concept_id`. The exception was caught and the function silently fell back to a topic-unfiltered query — returning the student's overall average mastery for every card. Visible to the user as "every card shows the same number."
**Fix:** Corrected the JOIN to `concepts c ON c.id = cm.concept_id` (matches the established pattern in `app/api/student.py:79`). Topic filter is now `c.subtopic ILIKE '%topic%' OR c.topic ILIKE '%topic%'`. Bumped fallback log from INFO → WARNING so future schema drift is visible.
**DO NOT:** add another silent fallback that materially changes response shape. If a fallback returns different data (e.g. global vs. topic-specific), log at WARNING with explicit text saying so. v0.20.4 also added a synthetic-suite assertion on mastery shape — that catch will fire in CI before prod sees it.

## /study/card admin panel showed zero data — TWO constraints rejecting inserts — fixed (v0.20.4, 2026-04-21)
**Symptom:** Admin Study Path usage panel (top concept cards table, daily-views chart, override hit-rate) all showed zero data despite real student traffic. Two distinct constraint failures, the second only visible after the first was fixed.
**Root cause #1 (CHECK):** `session_events.session_type` had a CHECK constraint allowing only `('doubt','practice','mock')`. The v0.20.2 `/study/card` endpoint was inserting `'study'`. Render prod log: `INFO:app.api.study:study_card_view event-log skipped (non-fatal): new row … violates check constraint "session_events_session_type_check"`.
**Root cause #2 (FK):** After v17 widened the CHECK constraint to allow `'study'`, the next insert hit a FOREIGN KEY violation: `session_events.session_id` is `FOREIGN KEY → doubt_sessions(id) ON DELETE CASCADE`. The endpoint was passing `gen_random_uuid()` for session_id — random UUIDs don't exist in `doubt_sessions`, so the FK rejected every insert. Local backend log surfaced it after migration v17 + manual curl: `insert or update on table "session_events" violates foreign key constraint "session_events_session_id_fkey"`.
**Fix:**
1. Migration `scripts/migrate_v17_session_events_study.sql` adds `'study'` to the CHECK constraint (idempotent).
2. `app/api/study.py` `study_card_view` insert now passes `NULL` for `session_id` — the column is nullable in the schema, and the event isn't tied to a doubt_session.
3. Both fallback log lines bumped INFO → WARNING with explicit text noting the consequence ("admin panel will lack data") — silent INFO logs hid this for >24h.
**DO NOT:** (a) ship a new event_type that touches `session_events` without verifying every constraint on the table (CHECK, FK, NOT NULL). (b) leave fallback paths at INFO level when they materially change response shape — use WARNING with explicit consequence text. The synthetic-suite scenario `admin_study_path.records_views` now runs both invariants in CI.

## Topic-shift demotion didn't fire on short questions ("what is molecule?", 16 chars) — fixed (v0.20.3, 2026-04-21)
**Symptom:** Real prod chat. Student opened a physics doubt ("A 5 kg block slides down a 30° incline"), pivoted to math ("wait, what's the integral of sin(x²)?" → topic-shift fired, new block opened ✓), then pivoted to chemistry ("what is molecule?" → counselor mode refused with "molecule is a chemistry concept, not related to integrating sin(x²)..."). Student noticed the inconsistency: "but initally i was asking about accelaration, then suddenly about integration but that time you didn't say no??".
**Root cause:** `_looks_like_new_question()` had `if len(stripped) < 20: return False` as the first gate. The verb regex would have matched "what is molecule?" (16 chars contains "what is"), but the length check short-circuited before reaching it. The 20-char floor was set conservatively in v0.20.2 to avoid false positives on hint replies — but "what is X?" with X being a single noun is a perfectly valid new question well under 20 chars.
**Fix:** Lower the verb-regex floor from 20 → 12 chars. Keep the symbol-only fallback floor at 25 (notation alone needs more weight). Synthetic test extended from 1-pivot to 3-pivot scenario (physics → math → "what is molecule?" chemistry) so this regression is permanently caught.
**DO NOT:** raise the floor back without measuring against a corpus of real student doubts. The floor should be set FROM data ("shortest legitimate new-question observed = N → floor = N"), not guessed.

## Topic-shift demotion didn't fire on contractions / math-symbol pivots — fixed (v0.20.2, 2026-04-21)
**Symptom:** Student in `/doubt` says `"A 5 kg block slides down a 30° incline. Find acceleration."` then mid-hint pivots with `"wait, what's the integral of sin(x²)?"`. Backend's intent classifier *correctly* flagged the pivot as `subject_doubt`, but FIX A3 immediately demoted it back to `continuation` because the message was <100 chars and didn't match the `find|calculate|solve` regex. v0.20's compensating `_detect_topic_shift()` should have re-promoted it but its `_NEW_QUESTION_MARKERS` regex had `what\s+is` which couldn't match `what's` (apostrophe-s contraction), and didn't include math verbs like `integral`. Result: AI stayed in physics counselor mode, refused the pivot ("integral of sin(x²) is unrelated here"), no new doubt_block opened, mastery for any future answer would credit the wrong concept.
**Root cause:** Regex too narrow. Three gaps: (1) no contractions, (2) no math verbs (`integral`, `derivative`, `differentiate`), (3) no symbol-only fallback for messages that have notation but no verb (e.g. `"the integral of sin(x²)"`).
**Fix:** Widened `_NEW_QUESTION_MARKERS` to cover contractions + math verbs. Added a separate `_MATH_SYMBOL_HINTS` regex (Unicode super/subscripts, `dy/dx`, `∫`, math nouns like `integral`/`derivative`/`pH`/`mol`). `_looks_like_new_question()` now returns True if the verb regex matches OR (length ≥ 25 AND symbol regex matches). Synthetic test repros the exact prod message and confirms `topic_shift.opens_new_block` invariant holds.
**DO NOT:** narrow the regex back. Every word in the verb list and every symbol in the math regex was added in response to a real failure mode. If you must constrain (e.g. to reduce false positives), validate against `scripts/synthetic_beta.py` first.

## Notes section showed the same NCERT chunk three times — fixed (v0.20.2, 2026-04-21)
**Symptom:** Concept Card for Projectile Motion (and other Kinematics topics) rendered three identical "KINEMATICS" Notes blocks with the same text — "Kinematics is the branch of physics that deals with the motion of objects without considering the forces that cause them to move…" — repeated verbatim.
**Root cause:** The NCERT corpus has the same Kinematics intro section appearing in multiple source files; the hybrid Retriever was returning all of them as top-3 because they all match the topic embedding strongly. `_compose_notes()` returned the raw top-k without dedup.
**Fix:** Fetch wider (k×3 = 9 chunks instead of 3), dedupe by sha1 of the normalised first-200-chars of each chunk's content, also prefer chunks with distinct `metadata.section` headings (allow heading repeat only when we'd otherwise return <k chunks). Synthetic test asserts `len(prefixes) == len(set(prefixes))` for every fetched card.
**DO NOT:** dedupe by full content hash — that misses paraphrased duplicates. The first-200-char normalised hash is the right granularity. If you tighten further (e.g. fuzzy dedup), measure recall on a small held-out set first.

## concept_card_overrides.json wasn't loading because Path resolution was off — fixed (v0.20.2, 2026-04-21)
**Symptom:** Synthetic test reported `study_card[Chemical Bonding].notes_deduped — 3 unique chunks` for a topic that *should* have hit a 1-chunk hand-polished override. Auto-assembly was firing instead of override.
**Root cause:** In `app/services/study/card_composer.py`, `_OVERRIDES_FILE = Path(__file__).resolve().parents[2] / "scripts" / "concept_card_overrides.json"`. From `app/services/study/card_composer.py`: parents[0]=`study/`, [1]=`services/`, [2]=`app/`. So the loader was looking for `app/scripts/concept_card_overrides.json` (doesn't exist). The correct path uses `parents[3]` to reach the repo root.
**Fix:** Changed to `parents[3]`. Synthetic test caught it on first run after the migration; second run all 5 seed overrides loaded.
**DO NOT:** hard-code an absolute path. Keep it relative to `__file__` so the repo is portable. If you move `card_composer.py` to a different depth, recount the parents.

## Full solution firing multiple times — fixed
**Symptom:** Student would get 2-3 identical full solutions dumped into chat
**Root cause:** Missing guard check — full solution handler didn't verify if solution was already delivered in current doubt block
**Fix:** Added `solution_delivered` boolean flag on doubt block state. Check before generating.
**DO NOT:** Debounce on frontend — the backend must be idempotent. Frontend debounce masks the real issue.

## Verification confidence returning 0% — fixed
**Symptom:** Every doubt showed 0% confidence score regardless of answer quality
**Root cause:** Embedding dimension mismatch — verification was comparing 3072-dim reference against 384-dim query vectors. Cosine similarity returned near-zero.
**Fix:** Ensured verification pipeline uses same all-MiniLM-L6-v2 (384d) embeddings throughout
**DO NOT:** Hardcode confidence to a default value to "fix" the display. The underlying comparison must work.

## Markdown/LaTeX rendering broken in chat — fixed
**Symptom:** Raw LaTeX strings like `\frac{1}{2}mv^2` showing in chat instead of rendered math
**Root cause:** Missing rehype-katex plugin in react-markdown pipeline, or remark-math not processing inline `$...$` delimiters
**Fix:** Ensured react-markdown uses `remarkPlugins={[remarkMath]}` and `rehypePlugins={[rehypeKatex]}`. Also imported KaTeX CSS.
**DO NOT:** Use dangerouslySetInnerHTML to render LaTeX. Always go through the react-markdown pipeline.

## Intent detection too aggressive — fixed
**Symptom:** Student saying "show me how to start" triggered full solution reveal instead of a hint
**Root cause:** Give-up regex was too broad — matched "show me" anywhere in input
**Fix:** Narrowed regex to explicit give-up phrases: "give up", "i give up", "just show me the answer", "show me the full solution". Must be near-exact match.
**DO NOT:** Use broad substring matching for intent detection. Every pattern must be tested against common student phrases that should NOT trigger it.

## Session summarizer race condition — fixed
**Symptom:** Second doubt in a session had no context from the first doubt's summary
**Root cause:** Summarizer was fired asynchronously (fire-and-forget) when ending a doubt block. The next doubt block started before the summary was written to DB.
**Fix:** Made summarizer a blocking `await` call. Doubt block is only marked "ended" AFTER summary is persisted.
**DO NOT:** Make the summarizer async/background again. This MUST be synchronous in the doubt-end flow. See docs/decisions.md.

## Out-of-scope questions getting Socratic treatment — fixed
**Symptom:** Student asking "what's the weather?" got a Socratic physics dialogue instead of a polite redirect
**Root cause:** Intent classifier defaulted to "physics_doubt" for any unrecognized input
**Fix:** Added explicit out-of-scope category in classifier. Unrecognized inputs now return a friendly redirect message.
**DO NOT:** Add more subjects to the classifier to "catch" out-of-scope queries. The classifier needs a dedicated "not_a_doubt" class.

## "Invalid or expired token" on onboarding — fixed
**Symptom:** Students completing onboarding after >1 hour of inactivity got 401 and were blocked
**Root cause:** Supabase access tokens expire after 1 hour. No refresh mechanism existed — the token in localStorage was used until it expired with no recovery path.
**Fix:** Added `POST /auth/refresh` endpoint. `api.ts` catches 401, silently calls refresh, retries original request. Redirects to login only if refresh token is also expired.
**DO NOT:** Extend token expiry in Supabase settings. Silent refresh is the right UX pattern.

## "Failed to fetch" on Render cold start — fixed
**Symptom:** First API call on login/onboarding pages returned network error, shown as "Failed to fetch / Go back and try again"
**Root cause:** Render free tier spins down after inactivity. Cold start takes up to 50 seconds. Original 3-second retry was insufficient.
**Fix:** `fetchWithRetry()` in `api.ts` with 3 retries at 5s/15s/30s delays. `pingBackend()` called on mount of login, signup, and onboarding pages to trigger warm-up before the user submits.
**DO NOT:** Set a single short timeout and surface the error immediately. The first call on cold start will always fail — retry is mandatory.

## AttributeError: SocraticEngine has no attribute '_openai' — fixed
**Symptom:** `/onboarding/submit` crashed with `AttributeError: 'SocraticEngine' object has no attribute '_openai'`
**Root cause:** `onboarding.py` used `._openai` but the engine stores the client as `._client` (as seen in `mock.py`)
**Fix:** Changed `._openai` → `._client` in `app/api/onboarding.py`
**DO NOT:** Add a `_openai` alias property. Fix the reference at the call site.

## Image upload "supabaseUrl is required" — fixed
**Symptom:** Clicking image upload in ChatInput threw "supabaseUrl is required" and blocked the upload
**Root cause:** `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are not set in Vercel environment. `getSupabase()` threw on initialization.
**Fix:** Removed Supabase Storage entirely. `ChatInput.tsx` now reads the file with `FileReader.readAsDataURL()` and sends base64 to backend. No Supabase env vars needed.
**DO NOT:** Try to fix this by adding Supabase env vars to Vercel — base64 is the correct long-term approach for this use case.

## Knowledge Genome not updating (Analytics shows 0%) — fixed
**Symptom:** Analytics page always showed 0% mastery even after students completed multiple doubts
**Root cause:** `handleGotIt()` was calling `/student/{id}/update-mastery` per-concept directly. This ran the EMA math but never triggered `_genome_update_task` which is the sole writer for session_events and persona updates.
**Fix:** `handleGotIt()` now calls `POST /doubt/hint` with `student_resolved: true`. This triggers the correct `_genome_update_task` background path in `doubt.py`.
**DO NOT:** Add a second mastery update path. `_genome_update_task` in `doubt.py` is the sole owner — see CLAUDE.md invariants.

## Conversational replies starting new Socratic sessions — fixed
**Symptom:** Student typing "yes", "ok", "thanks" after a hint triggered a new doubt session instead of being ignored
**Root cause:** No pre-filter existed for short affirmative tokens. Every non-empty string was passed to the full intent classifier pipeline.
**Fix:** Added `_CONVERSATIONAL_TOKENS` frozenset in `engine.py`. Messages ≤20 chars matching the set return `CONVERSATIONAL_RESPONSE` immediately without touching the LLM.
**DO NOT:** Handle this inside the LLM classifier prompt alone. The pre-filter must be code-level for reliability and cost.

## build_system_prompt() silent KeyError — every student got unpersonalized fallback — fixed
**Symptom:** Every call to `build_system_prompt()` was silently failing. Policy engine logged `"Policy engine failed (non-fatal), using default prompt: 'u^2 \\sin 2\\theta'"`. All students received the `TUTOR_SYSTEM_PROMPT` fallback (no pedagogy personalization, no scaffolding level, no teaching style adaptation).
**Root cause:** `CUSTOMIZATION_PROMPT` in `prompts.py` (line 643) contained `\\frac{u^2 \\sin 2\\theta}{g}` — a LaTeX example with unescaped `{u^2 \\sin 2\\theta}` and `{g}`. When `build_system_prompt()` called `CUSTOMIZATION_PROMPT.format(subject_context=...)`, Python's `.format()` parsed those braces as named format placeholders and raised `KeyError: 'u^2 \\sin 2\\theta'`. The policy engine's `except Exception` clause silently swallowed the error.
**Fix:** Escaped to `\\frac{{u^2 \\sin 2\\theta}}{{g}}` in `prompts.py`. Same double-escaping pattern was already applied to `TUTOR_SYSTEM_PROMPT` — `CUSTOMIZATION_PROMPT` had been missed.
**DO NOT:** Ignore `"Policy engine failed (non-fatal)"` warnings. They indicate every student is getting the unpersonalized fallback. This warning should be treated as a P0 bug.
**Rule added to RULES.md:** Rule 13 — all LaTeX braces in `.format()`-called prompt templates must be `{{}}` double-escaped.

---

## LaTeX sanitizer missing on non-streaming start_session() and emotional path — fixed
**Symptom:** Students on the non-SSE `/doubt/ask` path could receive the first Socratic response with broken KaTeX rendering (unbalanced `$$` delimiters, `\n\n` inside equations). Same for emotional support responses.
**Root cause:** `_sanitize_latex()` was called on `start_session_stream()`, `get_hint()`, and `explanation` paths but NOT on the non-streaming `start_session()` path (RULES violation #6). The `emotional` branch in `handle_non_physics_intent()` also called `_call_llm()` without sanitizing.
**Fix (`app/services/doubt/engine.py`):** Added `socratic_response = self._sanitize_latex(socratic_response)` immediately after `_response_latency_ms` is computed in `start_session()`. Added `response = self._sanitize_latex(response)` after the `emotional` LLM call in `handle_non_physics_intent()`.
**DO NOT:** Remove either sanitizer call. Rule 6 states sanitizer runs on EVERY LLM response path.

## 685 duplicate knowledge chunks — fixed
**Symptom:** 4.5% of knowledge_chunks (685/15,069) had exact content duplicates (different UUIDs). Retrieval bias, inflated similarity scores, wasted embedding storage.
**Root cause:** Resumable ingest scripts (`ingest_chem_maths.py`, `ingest_maths_pdf.py`) had no UNIQUE constraint guard — re-running a script from a checkpoint could insert the same chunk twice.
**Fix:** `scripts/migrate_v13_dedup_chunks.sql` — CTE DELETE keeping lowest UUID per md5(content) group, then `CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_chunks_content_md5 ON knowledge_chunks(md5(content))`. Applied: 15,069 → 14,384 chunks, 0 remaining duplicates. The UNIQUE INDEX prevents all future duplicates at the DB level.
**DO NOT:** Add a UNIQUE constraint on `content` directly (text columns can't be indexed without hashing in Postgres). Always use `md5(content)` for dedup indexing.

## Mock test mastery updates bypassing _genome_update_task — fixed
**Symptom:** Mock test results didn't feed the pedagogy loop — no session_events logged, no persona update, no scaffolding re-inference. Mock performance was "dark" to the student model.
**Root cause:** `mock.py` called `update_concept_mastery()` directly, bypassing `_genome_update_task` in `doubt.py` (RULES violation #1).
**Fix:** Added `_mock_genome_update_task(pool, student_id, concept_ids, correct, topic)` to `doubt.py`. Runs the same 3-step pipeline as `_genome_update_task`: (1) INSERT session_terminal event with `session_type='mock'`, (2) UPSERT concept_mastery EMA, (3) update persona profile + re-infer scaffolding every 5 sessions. `mock.py` now calls this via `asyncio.create_task()` — removed the direct `update_concept_mastery()` loop.
**Deliberate difference from doubt sessions:** No misconception penalty or confidence modifier — mock tests don't capture those signals.
**DO NOT:** Add a second mastery update path. `_genome_update_task` (doubt) and `_mock_genome_update_task` (mock) are the only two callers of `update_concept_mastery()` — both go through the full pipeline.

## Orphaned doubt sessions (no linked doubt_block) — fixed
**Symptom:** 16/56 doubt sessions had no `doubt_blocks` row. `_genome_update_task` never fired for these (no block_close event), judge evaluations were skipped, session end couldn't summarize them.
**Root cause:** If a user submitted a question before the study session init async call completed (~500ms on mount), `studySessionId` was still `null` in React state → `/doubt/ask` was sent with `study_session_id: undefined` → backend got `null` → no doubt_block created.
**Fix (`frontend/web/app/doubt/page.tsx`):** Added `sessionReady` boolean state (default `false`). Set to `true` after each branch of the session init effect (`startFresh()` success, `resume` success, and init error catch). Passed `disabled={isLoading || !sessionReady}` to `ChatInput` so the input is blocked while the session is initializing. Added `'Starting your session…'` placeholder while `!sessionReady`.
**DO NOT:** Remove the `setSessionReady(true)` in the error catch branch — if init fails, we still want to unblock the UI so the user isn't stuck.

## No timeout on Socratic LLM call in start_session() — fixed
**Symptom:** Slow OpenAI responses could hang `/doubt/ask` indefinitely with no feedback to the student.
**Root cause:** `_call_llm()` in `start_session()` had no `asyncio.wait_for()` wrapper. The underlying OpenAI client has internal timeouts but they're not coordinated with the FastAPI request lifecycle.
**Fix (`app/services/doubt/engine.py`):** Wrapped the `_call_llm()` call in `asyncio.wait_for(..., timeout=30.0)`. On `asyncio.TimeoutError`, logs an error and returns a graceful message: "I'm taking too long to respond right now — the AI service seems slow. Please try rephrasing your question or try again in a moment. Your question has been noted and your session is still active. 🔄"
**DO NOT:** Raise the timeout above 30s. Render's proxy timeout is 55s — leaving 25s of headroom for DB writes and the response path.

## "Outside syllabus" warning firing for valid Chemistry/Maths topics — fixed
**Symptom:** Questions like "Raoult's Law" (NCERT Chemistry Class 12, Solutions chapter) showed a ⚠️ "outside the [subject] syllabus" warning banner even though the topic is core JEE content. The warning also always said "Physics" regardless of the detected subject.
**Root cause (two problems in `_is_in_scope` in `engine.py`):**
1. The keyword fallback list (`physics_terms`) was **Physics-only** — it had no Chemistry or Maths terms. Any Chemistry/Maths question that also failed the DB topic check returned `False` → `out_of_scope = True`.
2. `_is_in_scope` ignored the **agentic RAG result** that had just been computed. If `rag["chunk_count"] > 0`, the KB clearly has relevant content → the question is in scope. This signal was thrown away.
3. The default `return False` was too aggressive — the intent classifier is the primary out-of-scope gate and already filters coding/history/biology-for-JEE before `start_session()` is ever called.
**Fix (`app/services/doubt/engine.py`):**
- `_is_in_scope` now accepts `rag: dict | None = None`
- Signal priority: RAG chunk_count > 0 → return True immediately; DB topic match → return True; subject-aware keyword match → return True; default → return True (trust intent classifier)
- Added comprehensive `chemistry` and `maths` keyword lists covering all NCERT Class 11-12 JEE chapters (raoult, colligative, osmosis, molarity, integral, determinant, etc.)
- Both call sites (start_session + start_session_stream) updated to pass `rag=rag`
**DO NOT:** Revert the default `return True`. The intent classifier is the real out-of-scope gate. `_is_in_scope` inside `start_session()` is a secondary filter for genuinely beyond-NCERT content (advanced quantum field theory, etc.) — it should almost never fire for standard JEE questions.

## Known / Deferred Issues

## JEE PYQ bank too small (20 problems) — DEFERRED
**Symptom:** `search_jee_problems` tool in AgenticRetriever rarely finds a matching PYQ. Agentic loop falls back to NCERT chunks for most questions.
**Root cause:** `scripts/data/jee_pyq_seed.json` has only 20 problems. All HuggingFace JEE PYQ datasets are private/gated (return 401).
**Status:** Acceptable for current phase. Agentic loop degrades gracefully to NCERT-only retrieval.
**Fix when ready:** Manually expand `jee_pyq_seed.json` to 200+ problems per subject, or find a public PYQ source. Re-run `scripts/ingest_jee_pyq.py --reset-progress` to re-ingest.

## Maths knowledge base smaller than Physics/Chemistry — DEFERRED
**Symptom:** Some Maths questions get fewer retrieved chunks, reducing response quality slightly.
**Root cause:** Maths has 1,426 chunks vs Physics 10,505 and Chemistry 3,138. NCERT Maths PDFs have sparser text-per-page than Physics/Chemistry chapters.
**Note:** The "outside syllabus" warning that used to accompany this is now fixed (see above) — the warning no longer fires for standard NCERT topics regardless of chunk count.
**Status:** Acceptable for JEE prep coverage of core chapters. Core topics (Calculus, Algebra, Coordinate Geometry, Vectors) are covered.
**Fix when ready:** Run `scripts/ingest_maths_pdf.py` with additional chapters, or add more entries to `scripts/data/ncert_maths_seed.json`.
