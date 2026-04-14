# Bug History — UpMyRank

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
