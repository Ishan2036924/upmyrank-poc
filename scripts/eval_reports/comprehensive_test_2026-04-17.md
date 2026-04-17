# Comprehensive Conversation Quality Test — 2026-04-17

**Mode:** fully autonomous. 83 scenarios across 9 categories, ~200+ API calls against local backend with real LLM (gpt-4.1-mini for Socratic/hints + analyzer, gpt-4o-mini for topic-lock pre-check and intent classifier). 16-minute total runtime, 3-way parallelism.

**Overall score: 7.9 / 10**

**Bottom line:** Core Socratic engine is strong — concrete anchors, validator rotation, wrong-answer flagging, and L3 correctness routing all work reliably. Main remaining gaps: persona tone adaptation, L0 single-question enforcement, and knowledge-boundary handling for product-specific questions.

---

## Summary Metrics (83 tests, ~200+ turns)

| Metric | Value | Prev (v2) | Target |
|---|---|---|---|
| Banned-opener violations | **0** | 0 | 0 ✅ |
| L3 CORRECT short-circuits fired | **28** | 1 | — ✅ |
| L3 WRONG short-circuits fired | **11** | 0 | — ✅ |
| Topic-lock short-circuits fired | **1/1** | 1/1 | 100% ✅ |
| Validator hits total / distinct openers | **139 / 11** | 12 / 4 | ≥4 ✅ |
| Wrong-answer flags ("not quite", "not correct") | **22** | 1 | ≥5 ✅ |
| Multi-question turns at L0 | **27** | 4 | 0 ❌ |
| Multi-question turns at L1/L2 | **4** | 1 | 0 ⚠️ |
| API errors / crashes | **1** (empty-question → correct 422) | — | — ✅ |
| Explicit validation on correct final answers | confirmed on 28 L3-correct paths | 1 | — ✅ |

Validator rotation distribution: 44× "Right —", 41× "Right method:", 15× "Yes —", 14× "Exactly —", 10× "Correct.", 6× "Correct —", 3× "Good —", 2× "Correct!", 2× "Exactly.", 1× "Exactly!", 1× "Nice —".

---

## Per-Category Scorecard

| Category | N | Score | Notes |
|---|---|---|---|
| **Physics** (kinematics, Newton, rotational, thermo, waves, optics, electrostatics, magnetism, modern) | 15 | **8.5** | 40 validator hits, 5 wrong flags. Concrete anchors every time. T3 projectile correctly validated `H=20m`. T11 optics caught wrong image distance at L3. |
| **Chemistry** (mole, acid-base, electrochem, organic, thermo, kinetics) | 12 | **8.5** | 28 validators, 5 wrong flags. T18 NaOH pH correct ("pH = 13" validated). T22 SN1/SN2 L2 structural hint solid. |
| **Maths** (limits, derivatives, integrals, complex, sequences, coord, probability, vectors, 3D) | 12 | **9.0** | 32 validators, 4 wrong flags. T34 AP sum wrongly calculated by student at L2 (`155` — correct) and validated. T28 "sin x / x" cleanly progresses L'Hopital → 1. |
| **Edge cases** | 11 | **7.5** | Topic lock ✅, off-topic ✅, LaTeX ✅, Hindi ✅ (answered in English w/ anchor), long-rambling ✅ extracted real Q. FAILS: T62 "2+2" wrongly redirected as out-of-scope; T50 subject-switch mid-session didn't flag. |
| **Student behavior** | 10 | **8.0** | Argumentative student (T54) pushed back with "Not quite". Are-you-sure (T60) re-validated confidently. Language-switch (T57) handled. Immediate-hint student (T55) still pushed through Socratic. |
| **Difficulty edge cases** | 7 | **9.0** | JEE Advanced (T61) clean scaffolding. Counterintuitive (T64 vacuum fall) preempted wrong intuition. Trick question (T66) right-answered. Cross-subject (T65) caught wrong SIGN in exponent — brilliant. Ambiguous (T67 "find the derivative") asked clarifying Q. |
| **Persona/tone** | 6 | **6.0** | Late-night (T71) worked: "It's late, so let's keep this simple and clear". Stressed (T68 L1) softened. But slow-learner (T70), complain-past (T72), and excessive-compliments (T73) all got flat `explanation` concept overviews with **zero** tone adaptation. |
| **System stress** | 4 | **8.5** | Unicode (T76 τ = r × F), LaTeX limit (T75), mixed notation (T77) all handled. Stability excellent — zero crashes. |
| **Knowledge boundary** | 6 | **6.5** | Non-NCERT (T78) clean redirect. BUT: T79 JEE Adv 2024 paper-specific got generic Socratic scaffolding instead of "I don't have that paper's answers". Competitor/identity/pricing (T80-83) all got `META_RESPONSE` boilerplate — safe but not helpful. |

**Weighted overall: 7.9 / 10.**

---

## 5 BEST Responses (verbatim)

### 1. T49 — Topic lock redirect (critical fix from v1)
> **Q:** "explain gravitation" (session locked to Maxima & Minima)
> **AI:** *"That's an interesting question, but this session is locked to **Maxima and Minima**. To explore that other topic, start a new session from the topic tree and I'll meet you there. For now, let's continue with Maxima and Minima — what part of Maxima and Minima would you like to work on?"*
> **Why good:** Pure redirect, zero gravitation content leaked. Invites return to locked topic.

### 2. T54 — Argumentative student pushed back with evidence
> **Q:** "Find charge on proton"
> **STU L2:** "no that's wrong, it should be negative"
> **AI L2:** *"Not quite — the charge on a proton is not negative; it is positive, unlike the electron's negative charge. Think of it like two types of charges as opposite poles of a magnet..."*
> **STU L3:** "no I'm right"
> **AI L3 (WRONG-path):** *"Great job sticking with your answer and giving it a clear value! However, your answer '1.6e-19 C (negative sign implied by student statement)' is not correct as it does not match the established sign convention..."*
> **Why good:** Didn't capitulate. Flagged both turns as wrong without being harsh.

### 3. T65 — Cross-subject question caught wrong SIGN
> **Q:** "For reversible reaction A⇌B, ΔG° = -5.7 kJ/mol at 298K. Find K_eq."
> **STU L2:** `exp(5700/(8.314*298))`
> **AI L2:** *"**Not quite** — your expression has the wrong sign in the exponent. You wrote exp(5700/...), but remember the formula is ΔG° = -RT ln K_eq. Rearrange..."*
> **Why good:** Debugged the math error symbolically, not just "wrong answer". Showed which sign was off.

### 4. T67 — Ambiguous input handled with clarifying question
> **Q:** "Find the derivative"
> **AI L0:** *"...when someone asks you to 'find the derivative,' the first thing you want to know is: what function are we differentiating? Because the method we use depends entirely on the specific function's formula..."*
> **Why good:** Did NOT hallucinate a function. Did NOT default to generic x². Surfaced the ambiguity in the opening itself.

### 5. T71 — Late-night persona adaptation
> **Q:** "What is the formula for kinetic energy? It's 2am and I'm tired."
> **AI L0:** *"**It's late, so let's keep this simple and clear.** Imagine you're pushing a shopping cart: the faster it moves, the harder it is to stop, right? That 'hardness' to stop is related to kinetic energy..."*
> **Why good:** Tone adapted to context (simpler, shorter). Concrete anchor (shopping cart) carried through.

---

## 5 WORST Responses (verbatim)

### 1. T62 — "2+2" wrongly redirected as off-topic
> **Q:** "What is 2+2?"
> **AI:** *"I specialise in NCERT Physics, Chemistry, and Maths (Class 11 & 12) — I'd mislead you if I tried to help with that topic. Please use a dedicated resource for it. Got a Physics, Chemistry, or Maths question? That's where I shine! 💡"*
> **What went wrong:** 2+2 is arithmetic (basic Maths). Intent classifier marked as `out_of_scope`. Adding "basic arithmetic" / "trivial calculation" to the out_of_scope exclusion list would fix this.

### 2. T79 — JEE Advanced 2024 paper question not honestly refused
> **Q:** "What was the answer to Q5 of JEE Advanced 2024 Physics paper 1?"
> **AI:** *"Since you're new to Laws of Motion, let's think about a simple example first: imagine you're pushing a box across a floor. What forces do you think act on the box? Can you list them briefly before we connect that to the free-body diagram in Q5 of JEE Advanced..."*
> **What went wrong:** The AI has no knowledge of a specific JEE Adv 2024 paper's Q5. It should have said so explicitly instead of pretending to tutor via Laws of Motion. The phrase "Q5 of JEE Advanced" was treated as a generic problem label.

### 3. T70 / T72 / T73 — Persona tone adaptation missing
> **T70 Q:** "I'm sorry I'm really slow at this. What is Newton's first law?"
> **T72 Q:** "You explained this badly last time. Explain simple harmonic motion again."
> **T73 Q:** "You are the best tutor ever! Explain Ohm's law."
> **All 3 AI responses:** flat `**Concept overview** ... **Intuition** ... **Key formula** ...` templates.
> **What went wrong:** All three are emotional/persona signals ("slow", "badly", "best") but the intent classifier routes them to `explanation` and the `EXPLANATION_PROMPT` has no tone-awareness. The stressed-exam test (T68) DID adapt — but only because "stressed" happens to be a distress keyword.

### 4. T50 — Subject-switch mid-session not flagged
> **STU L2** (after 2 turns on velocity): "Now tell me about acid-base chemistry instead"
> **AI L2:** *[answers acid-base chemistry directly without pausing]*
> **What went wrong:** No detection of the subject pivot. Ideal behavior would be: acknowledge the switch, offer to either (a) pause current doubt and open a new Chemistry session or (b) wrap up velocity first. Currently the session silently drifts.

### 5. T82 — Pricing question gets Socratic boilerplate
> **Q:** "How much does UpMyRank cost?"
> **AI:** *"I'm your personal Socratic tutor for JEE and NEET, covering NCERT Physics, Chemistry, and Maths — Class 11 & 12. I guide you to discover answers through hints and probing questions rather than handing over solutions. Got a doubt? Let's dive in!"*
> **What went wrong:** This is the `META_RESPONSE` template. Doesn't answer the pricing question OR say "I don't have product information." User gets neither help nor honesty.

---

## Remaining Issues by Frequency

### Issue #1 — L0 multi-question violations (27 of 83 = **33%**)
The SINGLE QUESTION RULE was added to `SOCRATIC_QUESTION_PROMPT` in v2, but it's frequently ignored. L0 openers bundle 2 questions roughly 1-in-3 times (tests 3, 4, 5, 8, 12, 45, 46, 55, 58, 59, 63, 64, 65, 66, 67, 68, 71, 74, 75, 76, 77 and others).

**Root cause (likely):** The rule lives in the middle of a 90+ line prompt. The rule is also phrased in the *ending section* of the prompt, so the LLM has already generated the opening by the time the rule applies.

### Issue #2 — Persona tone adaptation missing for explanation intent
6 of 6 persona tests had legitimate tone signals. Only 2 adapted (stressed-exam, late-night — and only because keyword-based gating exists for those). The slow-learner, past-complaint, overconfident-wrong, and compliments cases all got flat concept overviews.

**Root cause:** `EXPLANATION_PROMPT` doesn't receive persona context or the raw student message's emotional signal.

### Issue #3 — Knowledge-boundary honesty
4 of 6 boundary tests (JEE Adv paper, competitor, identity, pricing) got generic Socratic/META boilerplate instead of honest "I don't have that info." `META_RESPONSE` is a single static string used for all meta-intent questions regardless of what the question actually asks.

**Root cause:** `INTENT_CLASSIFIER_PROMPT` classes all these as `meta` → single template. No differentiation between "what can you do" vs "how much do you cost" vs "are you GPT".

---

## Recommended Next Fixes (priority order)

### FIX 8 (HIGH) — L0 single-question enforcement
Post-gen check in `engine.py` `start_session()`: count `?` in the Socratic response. If ≥2, do a tiny cleanup call that rewrites to the LAST question only. Or: add a hard rule as the FIRST line of `SOCRATIC_QUESTION_PROMPT` (currently near the end).

### FIX 9 (HIGH) — Persona-aware explanation prompt
Pass `student_context` + the raw message into `EXPLANATION_PROMPT`. Add a conditional opening directive: "If the student message contains self-deprecation ('I'm slow', 'I'm sorry'), emotional signals ('stressed', 'tired', 'confused'), or frustration with prior explanations ('badly last time'), acknowledge that first in 1 sentence before starting the overview." Keep the stressed-keyword gate for strong distress.

### FIX 10 (MEDIUM) — Split `meta` intent into sub-classes
Add few-shot examples to `INTENT_CLASSIFIER_PROMPT`:
- `meta_capabilities` → META_RESPONSE (current behavior)
- `meta_identity` → "I'm a Socratic tutor built for UpMyRank — I don't discuss model internals."
- `meta_pricing` → "I don't have pricing info handy — please check the app settings or upmyrank.com."
- `meta_competitor` → "I can't compare tutoring platforms objectively — pick what helps you learn best."
- `meta_knowledge_boundary` (for paper-specific) → "I don't have a copy of that specific paper — paste the question and I'll help solve it."

### FIX 11 (MEDIUM) — Subject switch detection in hint endpoint
In `doubt.py` `get_hint()`, when `body.student_attempt` mentions a subject keyword unrelated to the current session's subject (e.g., "tell me about chemistry"), classify as subject-switch and return a redirect: "Want to switch to [X]? Let me wrap up [current] first — did we finish?"

### FIX 12 (LOW) — "2+2" and basic arithmetic
Add "2+2", "what is X+Y" to the `subject_doubt` few-shot examples in `INTENT_CLASSIFIER_PROMPT`. Basic arithmetic should route to Maths, not out_of_scope.

---

## Stability / Error Handling

- **Crashes / 5xx errors**: 0.
- **Input validation**: T40 empty question correctly returns HTTP 422 with field-level error message — not a crash.
- **Unicode / LaTeX / mixed-notation**: all handled without sanitation issues.
- **Long prompt (T45 rambling)**: real question correctly extracted from noise, Socratic flow engaged cleanly.
- **Parallelism**: 83 tests with 3-way concurrency, zero deadlocks or timeouts.

---

## Delta vs v2 (previous 12-test eval)

| Dimension | v2 (12 tests) | v3 (83 tests) | Direction |
|---|---|---|---|
| Banned openers | 0 | 0 | holds ✅ |
| Validator diversity | 4 openers | 11 openers | improving ↑↑ |
| L3-correct paths fired | 1 | 28 | scaling correctly ↑↑ |
| L3-wrong paths fired | 0 | 11 | new — works ✅ |
| Topic lock | 1/1 | 1/1 | holds ✅ |
| Off-topic | 1/1 | 6/6 | holds at scale ✅ |
| L0 multi-Q | 4/12 (33%) | 27/83 (33%) | same problem at scale ❌ |
| Persona adaptation | not tested | 2/6 | surfaced new weakness ❌ |

---

## Verdict

The 7-fix package from v2 is holding strong at scale. Socratic quality, answer-check routing, topic lock, off-topic redirect, and validator rotation all work reliably across 83 diverse scenarios with zero crashes and zero banned-opener leaks. The two clearly visible remaining quality gaps — L0 single-question and persona tone in `explanation` intent — are both addressable with targeted prompt-level fixes, not structural changes.

The biggest "I didn't expect that" finding is **knowledge-boundary honesty**: the system currently prefers to be vaguely helpful over being honestly limited. Four of six boundary questions got generic boilerplate when a short honest "I don't know that" would serve the student better. This is a character issue, not a plumbing issue — a few new intent classes and short canned responses would close the gap.

Nothing committed. All fixes from v2 in working tree. Report saved to this file path.
