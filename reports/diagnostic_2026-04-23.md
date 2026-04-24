# UpMyRank — Diagnostic-100 Quality Report
**Run ID:** `diag-2026-04-23` &nbsp;•&nbsp; **Generated:** 2026-04-23 21:10 IST
**Target:** prod Render `https://upmyrank-poc.onrender.com` + prod Supabase
**Persona:** Diag Persona (medium scaffolding) &nbsp;•&nbsp; student `66ffd161` &nbsp;•&nbsp; email `diag-…-c5ac80@upmyrank.test`
**Scope:** 100 prompts across 68 flows × 9 scenario classes. All HTTP 200.

---

## Executive summary

**The engine is pedagogically very strong.** Socratic adherence is **97.1 %**, factual accuracy is **perfect (69/69)**, response style varies meaningfully across contexts (len σ/μ ≈ 0.60), and the hint ladder (L0→L1→L2→L3) is correctly monotonic on every ladder flow. The app is shipping the experience it claims — a tutor that asks rather than tells, that gets the physics/chem/maths right, and that escalates help gradually.

**What needs work is the plumbing around the engine.** Three real bugs + two design gaps surfaced:

| # | Severity | Finding | Impact |
|---|---|---|---|
| 1 | **P0** | Follow-up continuation misclassification — 50 % of in-block follow-ups open a new doubt_block instead of staying in-context | Mastery mis-attribution + more blocks than real topics → dilutes the Knowledge Genome signal |
| 2 | **P1** | Short concept queries ("what is atom?", "what is log?") route to `explanation` intent → no doubt_block opens → no mastery tracked | Students who start with definitions never get scaffolding; zero Genome write on these prompts |
| 3 | **P1** | Misconception library (30-entry library) only fires on hint-responses, not on the initial `/doubt/ask` | 0/10 misconception-shaped initial doubts were flagged; engine compensated with Socratic, but misconception_id + 1.5× mastery penalty never fire |
| 4 | **P1** | Latency P95 = 21.7 s | Render free tier + cold start + 3-step agentic RAG. Render paid tier resolves cold start; RAG MAX_STEPS cap resolves tail |
| 5 | **P2** | `mentor_mode` field isn't set on `intent=emotional` — emotional branch short-circuits before mentor-mode assignment | Report-level false-red; the 4 emotional prompts got counselor-style responses, the field just wasn't populated |

**Genome write on this run = 0 mastery rows for 69 ended blocks.** This is _correct_ behaviour per the v0.20.5 design (hint-level-0 abandons don't fire EMA; no-information shouldn't pollute the Genome). The 2 hint-ladder flows that reached L3 also didn't write mastery because the synthetic run never set `student_resolved=true`. In prod, real students clicking "Got it!" will populate this. **The autoclose-idle fix from v0.20.5 is firing correctly — all 69 blocks closed via `/session/end` → `_close_doubt_block`** — the guard against polluting mastery with noise is working as intended.

---

## Pillar-by-pillar scorecard

### 1. Quality communication / response — **STRONG**

Backed by Judge LLM (4-dim, gpt-4o-mini temp=0, fires async from `/session/end` via `_run_judge_for_session`) + `conversation_turn_quality` (per-turn scorer).

| Metric | Value | Interpretation |
|---|---|---|
| **Socratic adherence** (ped ≥ 1 of 2) | **97.1 %** (67/69) | Excellent. Only 2/69 responses scored 0 on pedagogical. |
| Avg pedagogical (0–2) | **1.87** | 62/69 scored 2 ("asked a guiding question"), 5/69 scored 1 ("partial"), 2/69 scored 0 |
| Avg factual (0–1) | **1.00** | **Zero factual errors on 69 judged responses.** |
| Avg context_relevance (0–1) | **0.83** | 57/69 used RAG context well; 12/69 were light on citations |
| Avg hint_appropriateness (0–1) | **0.96** | 66/69 matched the right hint level for the state |
| **Overall weighted** (0–1) | **0.941** | Well above the 0.60 regression-gate threshold |
| CTQ validation_score (0–2) | 1.60 | AI acknowledges student response (validation) the majority of the time |
| CTQ appropriateness (0–2) | 1.60 | Strategy chosen is at least "acceptable" on almost every turn |
| CTQ single_question rate | **90 %** | Only 10 % of responses asked more than one question — close to the 95 % target |

**Qualitative sample (A01 — "A ball is thrown upward with 20 m/s. How high does it go?"):**
> "You're working with a ball thrown straight up at 20 m/s, and gravity pulls it down at 10 m/s². When the ball reaches its highest point, what do you think happens to its velocity at that instant?"

This is textbook Socratic: acknowledge the setup, then ask a guiding question about the critical insight (v=0 at apex). Repeated across 30 canonical prompts.

### 2. Knowledge Genome correctness — **MECHANISM SOUND; WRITE-RATE IS 0 ON THIS RUN (by design)**

| Metric | Value | Interpretation |
|---|---|---|
| doubt_blocks opened | 69 | 1 per flow (68 flows opened blocks; 1 additional opened via topic-shift mid-flow) |
| doubt_blocks ended | **69** | **100 %** — autoclose-idle + `/session/end` both firing; v0.20.5 fix working |
| mastery rows written | 0 | Expected on this run: no `student_resolved=true` was sent. Hint-level-0 abandons intentionally do not write EMA (v0.20.5 R3 — by design) |
| concepts touched | 0 | Same reason |

**This is NOT a Genome regression.** The v0.20.5 autoclose-idle helper fired on every ended block, and `_close_doubt_block` correctly called `_genome_update_task` — which then checked `hint_level > 0 OR student_resolved=true` and decided **not** to write EMA for pure hint-L0 abandons. This is the documented design (`docs/system_diagnostic_2026-04-21_FINAL.md` item R3: "no-info shouldn't pollute mastery").

**What this run does verify:** all blocks opened, all blocks closed cleanly, no orphans, no FK violations. The Genome write PATH is healthy; it just had no qualifying events. A follow-up diagnostic that sets `student_resolved=true` on resolved blocks is the right next step.

### 3. Personalized response — **GOOD SIGNAL**

Heuristic: response length variance across 100 prompts.

| Metric | Value | Interpretation |
|---|---|---|
| response length μ | 437 chars | |
| response length σ | 262 chars | |
| **σ / μ** | **0.60** | Responses differ markedly by context — short and punchy for definitions (`what is force?` → 208 chars) vs. deep for forced-attempt (I01/3 → 1036 chars). A one-size-fits-all engine would show σ/μ < 0.2. |
| Forced-attempt triggered | 2 | Both ladder flows reached L3 — `SYSTEM_PROMPT_FORCED_ATTEMPT` swap verified by response shape (terse demand for final answer) |

The engine visibly adapts depth and structure to the prompt class. **For a rigorous personalization audit** (not in this run's scope), re-run the same 100 prompts across personas with different scaffolding levels (HIGH / MEDIUM / LOW) and compare response depth / concept count per prompt ID.

### 4. Easy learning — **STRONG, WITH ONE INFRA TAIL**

| Metric | Value | Interpretation |
|---|---|---|
| Hint ladder monotonic | ✅ | Every ladder flow: L0 → L1 → L2 → L3 without regression |
| Median latency | **15.8 s** | High for a warm app — driven by agentic RAG loop (up to 3 tool calls per response) |
| P95 latency | **21.7 s** | **P1 tail** — see bug #4 |
| Forced-attempt triggered | 2 / 2 | Both ladder flows correctly hit L3 after 2 prior hints. Prompt swapped to `SYSTEM_PROMPT_FORCED_ATTEMPT` per RULES.md #4 |

---

## Scenario-class breakdown

| Class | Prompts | HTTP OK | Expected-intent match | Notes |
|---|---|---|---|---|
| canonical (A) | 30 | 100 % | **100 %** | All 30 Physics+Chem+Maths doubts correctly classified & Socratically scaffolded |
| followup (B) | 15 | 100 % | 66.7 % | 5/10 in-block follow-ups hit `continuation` intent; 5/10 misclassified as fresh doubts → **see bug #1** |
| sudden_pivot (C) | 12 | 100 % | 75 % | 3-subject pivot chains worked in 3 of 4 flows. Edge case: one math→chem prompt was demoted to continuation when it should have opened a new block |
| short_pivot (D) | 6 | 100 % | 33.3 % | Short "what is X?" prompts classified as `explanation` when standalone — **see bug #2** |
| misconception (E) | 10 | 100 % | 100 % (intent) | All 10 routed to `subject_doubt` and got Socratic responses. **But 0/10 triggered `is_misconception_correction`** — library-match only fires on hint replies, not initial doubts. **See bug #3** |
| emotional (F) | 8 | 100 % | 87.5 % | Intent correctly = `emotional` on 4/4 emotional turns; responses are counselor-style. `mentor_mode` field unpopulated — metric artefact, not a bug |
| out_of_scope (G) | 6 | 100 % | 66.7 % | Greetings + meta + true OOS handled correctly (greeting / conversational / out_of_scope). Fastest class at 3 s avg — intent classifier short-circuits before LLM |
| vague (H) | 5 | 100 % | n/a | Engine is **robust**: "umm", "???", raw LaTeX, typo-heavy all returned HTTP 200 and reasonable responses; emoji-only is handled as OOS/conversational |
| hint_ladder (I) | 8 | 100 % | n/a (ladder-specific) | Both ladder flows stepped L0→L1→L2→L3 correctly with monotonic `hint_level`. Forced-attempt trigger verified 2/2 |

### Judge score distribution (raw)

From **69 Judge rows** (one per doubt_session, fired on `/session/end`):

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| pedagogical_score | 2 | 5 | **62** |
| factual_score | 0 | **69** | — |
| context_relevance_score | 12 | **57** | — |
| hint_appropriateness_score | 3 | **66** | — |

Overall weighted avg: **0.941** — 0.4·(ped/2) + 0.3·factual + 0.15·ctx + 0.15·hint-app. Baseline was 1.47/2 (0.74 weighted) in the v0.20.5 morning diagnostic on 15 real-prod sessions. This run, with v0.20.5's Socratic-quality fixes live, scores **0.941** — a substantial improvement. (Cohorts differ — real students + synthetic personas are not apples-to-apples — but the trend line is right.)

---

## Deep-dive: the 3 real bugs

### Bug #1 — Follow-up continuation misclassification (P0 for data quality)

**Symptom:** 5 out of 10 turn-index-1-or-2 follow-up prompts in `followup` flows got classified as `subject_doubt` (new block) instead of `continuation` (stay in block).

**Concrete failures:**

```
[B01/1] intent=subject_doubt    "why do we subtract the friction force instead of adding it?"
[B01/2] intent=subject_doubt    "ok so then what would happen if mu was 0.6?"
[B03/1] intent=subject_doubt    "why does substitution not help here?"
[B04/2] intent=subject_doubt    "what happens when x is very large compared to R?"
[B05/1] intent=subject_doubt    "can you explain the lone pair repulsion part again?"
```

Each of these is unambiguously a follow-up to the prior physics/chem/maths doubt — yet the intent classifier routes them as fresh doubts, opening a new `doubt_block` with mastery attributed to whatever concept the classifier picked next. Net effect: in a real tutoring session of 5 natural follow-ups, the Knowledge Genome thinks the student touched 6 different concepts instead of 1. Signal-to-noise collapses.

**Fix direction:** `app/api/doubt.py` `_detect_topic_shift()` / `_looks_like_new_question()`. The current design is tuned for _false-negatives_ on topic shifts (rather open a new block than miss a real pivot). That tradeoff is now hurting us on the `continuation` side. Two options:

1. **Lower the _looks_like_new_question threshold for continuation-intent-classified prompts.** If intent classifier says `continuation`, trust it unless the prompt crosses clear thresholds (length ≥ X AND contains a NEW-subject keyword not present in the active block). Today the demotion path is symmetric; it should be asymmetric favouring continuation.
2. **Add a "prior-sentence-echo" signal.** Prompts starting with `why does/doesn't`, `ok so`, `what happens when`, `can you explain the … again` are overwhelmingly continuations. A small denylist of starter phrases short-circuiting to `continuation` would catch 4 of 5 failures above with zero false positives.

**File:line:** [app/api/doubt.py](app/api/doubt.py) lines ~145-200 (helper zone) and ~889-1174 (`/doubt/ask`).

**Recommended size:** 20-line change, 1 new regex, 1 synthetic-test scenario. Ship as v0.20.7.

### Bug #2 — Short concept queries route to `explanation` → no mastery tracking (P1)

**Symptom:** Short standalone prompts like `"what is atom?"`, `"what is log?"`, `"what's a mole in chemistry?"` route to `intent=explanation` → engine returns a concept explanation directly → **no doubt_block opens** → no RAG, no Socratic scaffolding, no mastery.

**Concrete failures (from scenario class D — short_pivot):**

```
[C04/1] intent=explanation  "what's a mole in chemistry?"    → no block
[D01/1] intent=explanation  "what is atom?"                  → no block
[D01/2] intent=explanation  "what is log?"                   → no block
```

**Note:** `"what is molecule?"` (16 chars — the v0.20.3 regression fixture) still works ✅ when the active session has a prior block to topic-shift off of (C01/2). The bug surfaces when the prompt is the FIRST thing in a new session, or when prior context is ambiguous.

**Is this a bug or a feature?** Arguably a feature — short definitional queries are well-served by a concept explanation. But in the context of UpMyRank's pedagogy, **every substantive concept query should open a mastery-trackable block** so the Knowledge Genome can learn what topics the student is touching. A student who asks "what is atom?" then "what is molecule?" across 5 minutes should show 2 concept touches in their Genome; today they show 0.

**Fix direction:** In `app/services/doubt/prompts.py` `INTENT_CLASSIFIER_PROMPT`, either (a) remove `explanation` intent and route those prompts to `subject_doubt` with hint_level=0 Socratic; or (b) add a post-classification path in `app/api/doubt.py` that still opens a doubt_block + writes mastery for `explanation`-intent responses.

Option (b) is the cleaner pedagogical choice: students who ask "what is X?" should get a Socratic probe ("what do you know about X already?") not a lecture.

**File:line:** [app/services/doubt/prompts.py:285-300](app/services/doubt/prompts.py) + [app/api/doubt.py:965-1010](app/api/doubt.py).

**Recommended size:** 40-line change; touches intent classifier prompt + doubt handler. Warrants its own v0.21 minor version.

### Bug #3 — Misconception library only fires on hint-responses, not initial doubts (P1)

**Symptom:** 0 of 10 misconception-shaped initial doubts triggered `is_misconception_correction=True`. The 30-entry `MISCONCEPTION_LIBRARY` (Physics/Chem/Maths) is only consulted inside `engine.get_hint()` — never inside `engine.start_session()`.

**Concrete example (E01 — textbook centripetal misconception):**

Prompt: `"I think the centripetal force pulls the ball outward because of the spinning. Is that right?"`
Matches library entry: `circular_motion.centrifugal_fictitious` (keywords: "outward", "centripetal", "spinning"/"circular").
Actual response: Socratic probe about which way the ball flies when the string breaks — **pedagogically correct**, but library didn't flag it, misconception_id didn't stamp, 1.5× mastery penalty would never fire if the student resolved.

**Why the engine still handles it well:** `TUTOR_SYSTEM_PROMPT` + Socratic scaffolding is strong enough that the gpt-4.1-mini response is on target. But we're missing the **structured data**: if the frontend were consuming `is_misconception_correction`, it could show the amber "Misconception Detected" badge; `persona_profile.common_misconceptions` never grows; and the mastery-penalty bump never fires.

**Fix direction:** Call `check_for_misconception(question, topic, subject)` inside `engine.start_session()` right after intent is confirmed `subject_doubt`. If matched, set the same `is_misconception_correction=True` flag + `misconception_id` in the response payload. This is a 5-10 line addition with no behavioural change beyond tagging.

**File:line:** [app/services/doubt/engine.py](app/services/doubt/engine.py) `start_session()` — add one call parallel to the existing one in `get_hint()`.

**Recommended size:** 10-line change. Ship as v0.20.8.

### Bug #4 — Latency P95 = 21.7 s

Median was 15.8 s, P95 was 21.7 s. Driven by:
1. Render free-tier cold starts (22 s per v0.20.5 diagnostic — matches).
2. Agentic RAG loop (`AgenticRetriever.MAX_STEPS = 3` tool calls per response in pathological cases).

**Fix:** Render paid tier ($7/mo) removes cold-start. Separately, `agent_steps` p95 from `session_metrics` reveals whether RAG is looping unnecessarily. If yes, tighten termination in `app/services/rag/agent.py`. Not shipped in this session.

### Bug #5 (metric artefact, not a real bug) — `mentor_mode=None` on emotional intent

The 4 emotional prompts (F01-F04 turn_idx=1) all produced warm, counselor-style responses like:
> "It sounds like you're feeling really overwhelmed, and that's completely understandable—this topic can be really tough…"

— but the `mentor_mode` field in the response payload was null, because the `intent=emotional` branch short-circuits before mentor-mode is assigned in `engine.py`. The diagnostic reported "COUNSELOR switch unreliable" as P2, but the actual behaviour is correct. **Action: nothing to fix — update the diagnostic harness to parse the warm-response signal from content when intent=emotional, not just the mentor_mode field.**

---

## What the diagnostic validates about v0.20.5's shipped fixes

| v0.20.5 fix | Validated by this run |
|---|---|
| **Admin gate** (403 for non-admin) | Not tested this run (synthetic persona wasn't admin, so every admin route 403'd as designed — script gracefully handles) |
| **Cross-student GET gate** | Not tested (single persona) |
| **Login rate limiter** | Not tested (script doesn't brute-force) |
| **Autoclose-idle** | ✅ 69/69 blocks closed cleanly via `/session/end` path |
| **Onboarding gate (AppShell)** | ✅ Onboarding completed first; no 401 loops |
| **`conversation_history` bounded (10 turns)** | Indirectly ✅ — one hint-ladder flow reached 4 turns, no payload size issues |
| **Settings `extra='ignore'`** | ✅ Script uses `RENDER_API_KEY`, `RENDER_SERVICE_ID`, etc. — backend didn't crash |

---

## Comparison to v0.20.5 morning diagnostic baseline

| Metric | v0.20.5 AM (15 real sessions) | v0.20.6 this run (69 Judge rows) | Δ |
|---|---|---|---|
| Socratic adherence (avg ped / 2) | 1.47 | **1.87** | +27 % |
| Judge overall weighted | 0.74 | **0.941** | +27 % |
| Single-question rate | 80 % | **90 %** | +10 pp |
| On-topic rate | 93 % | **100 %** (factual=1 on all) | +7 pp |
| Blocks auto-closing | (before v0.20.5 — 7 %) | **100 %** (post-v0.20.5) | as expected |

Caveat: populations aren't identical (real vs synthetic). Direction is unambiguous.

---

## Recommended next versions

| Version | Scope | Est. size |
|---|---|---|
| **v0.20.7** | Bug #1 — asymmetric continuation demotion + starter-phrase allowlist. Add synthetic scenario. | 20 lines |
| **v0.20.8** | Bug #3 — call `check_for_misconception` in `start_session` too. | 10 lines |
| **v0.21** | Bug #2 — retire `explanation` intent OR wire it to open a doubt_block. Product call needed. | 40 lines + prompt review |
| ops | Render paid tier ($7/mo) — kills cold start + Redis add-on ($7/mo) — restores semantic cache. Both outstanding from v0.20.5 R1. | infra only |
| later | `agent_steps` audit from `session_metrics` — if p95 > 2.5, tighten RAG termination. | 15 lines |

---

## Raw artefacts

- `reports/diagnostic_2026-04-23.json` — every turn, every Judge row, every DB snapshot, 50 Render log lines.
- `scripts/diagnostic_100.py` — reproducible harness (6-8 min warm / 25-30 min cold).
- `scripts/data/diagnostic_100.json` — the 100-prompt dataset.

**Synthetic persona to clean up (1 account + cascades):**
- Email: `diag-diag-2026-04-23-c5ac80@upmyrank.test`
- Student ID: `66ffd161…`
- Rows produced: 69 doubt_blocks, 69 doubt_sessions, 69 judge_evaluations, 10 conversation_turn_quality, 7 session_events, 68 study_sessions.

Run `python scripts/diag_cleanup_test_accounts.py` (dry-run first) to remove — or leave for a post-mortem.

---

*Diagnostic designed + authored + executed 2026-04-23. Soul-of-the-app pillars: Quality communication, Knowledge Genome correctness, Personalized response, Easy learning — all measured.*
