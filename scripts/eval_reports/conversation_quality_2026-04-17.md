# Conversation Quality Eval — 2026-04-17

**Mode:** autonomous end-to-end test. 12 scenarios run against local backend (`http://127.0.0.1:8000`) using real LLM calls (gpt-4.1-mini). Student account freshly created; no prior mastery/persona.

**Score: 5.5/10.** Several high-visibility bugs — topic lock silently fails, banned openers still appear, correct answers at L3 get steamrolled by the forced-attempt template, wrong answers aren't flagged as wrong.

---

## Pass/Fail Matrix

| # | Test | Result | Why |
|---|------|--------|-----|
| 1 | Ball thrown upward, step validation | **⚠️ PARTIAL** | "no idea" handled well (academic nudge, not counselor). Correct "velocity is zero" got "Good — you've got the idea" (weak validation, no "Exactly!"). Final correct formula `v²=u²−2gh` went straight to L3 forced-attempt — **no validation of correctness**. |
| 2 | Newton 3rd law + solution_seeker ×2 | **❌ NOT TESTED** | Classified as `explanation` intent, not `subject_doubt` → bypassed Socratic engine entirely. SOLUTION_SEEKER_PREAMBLE path never reached. |
| 3 | Atwood — wrong vs correct discrimination | **❌ FAIL** | Wrong answer `a=10 m/s²` got "Good — you've got the idea" (not flagged as wrong!). Correct `a=2.5 m/s²` got L3 forced-attempt template ("please provide your final calculated answer before the solution is revealed") — zero acknowledgment it was correct. |
| 4 | Reaction rate & temperature | **❌ FAIL** | L1 response opens with `"I notice you haven't shared your thoughts yet—no worries!"` — **TWO bugs**: (a) banned opener "no worries" violated, (b) hallucinated that student didn't share thoughts when they literally said "molecules move faster?". |
| 5 | pH of 0.01M HCl | **✅ PASS** | Clean progression. "Good — you've got the idea" on correct answer. Still no "Exactly!" but validation is functional. |
| 6 | Derivative of x³sin(x) | **⚠️ PARTIAL** | Student said correct derivative `3x²sin(x) + x³cos(x)` → AI acknowledged the *method* ("Good — you've got the product rule in mind") but **did not confirm the derivative itself was correct**. |
| 7 | Integrate x²eˣ by parts | **✅ PASS** | Clean. Validated both steps. |
| 8 | Just `?` | **✅ PASS** | Defaulted to Laws of Motion with concrete anchor (holding a book). Reasonable. |
| 9 | `lol` | **✅ PASS** | Correctly classified as greeting, returned cheerful prompt. |
| 10 | 500-word rambly question | **⚠️ PARTIAL** | Extracted real question (Mars gravity). But opener `"that's a great sign!"` is adjacent to banned "great" patterns. L1 response didn't acknowledge the correct formula `g=GM/r²`. |
| 11 | Off-topic: capital of France | **❌ FAIL** | AI answered the question directly: `"The capital of France is **Paris**."` before offering physics help. Should have redirected without answering. |
| 12 | Topic lock (Maths/Calculus/Maxima-Minima → "explain gravitation") | **❌ FAIL CRITICAL** | Topic lock is stored in analysis but **AI answered the gravitation question in full**: `"Imagine you hold a small ball... This everyday experience is actually due to gravitation — a force that pulls objects toward each other..."` No redirect. TOPIC_LOCK_ADDENDUM is injected but **not respected** by the LLM. |

**Score: 4 FAIL, 3 PARTIAL, 5 PASS (+ 1 not-tested).**

---

## Exact Quotes — Good and Bad

### ✅ Good validation (but weak)
> Test 5 L2 to `pH = 2`:
> "Good — you've got the idea that HCl fully dissociates and that the concentration of H⁺ ions equals the molarity of HCl, which is 0.01 M here. Now, to calculate the pH..."

> Test 7 L2 to `u = x², dv = eˣdx`:
> "Good — you've got the idea of choosing u as the part that simplifies when differentiated, and dv as the part that's easy to integrate..."

### ✅ Concrete anchoring (working well)
> Test 3 L0 Atwood: "Let's picture this Atwood machine like a simple tug-of-war with two kids on either side of a pulley..."
> Test 6 L0 derivative: "Let's think of this like you're holding a spinning wheel with a stick attached to it..."
> Test 7 L0 integral: "Think of x²eˣ as a growing plant (eˣ) being shaped by a gardener (x²)..."

### ❌ BANNED OPENER ALIVE
> Test 4 L1: **"I notice you haven't shared your thoughts yet—no worries!"** — violates banned-openers rule AND hallucinated student's input.

### ❌ WRONG ANSWER TREATED AS CORRECT
> Test 3, student says `a = 10 m/s²` (wrong; correct is 2.5):
> AI L2: "**Good — you've got the idea that the net force causing acceleration is due to the difference in the weights**..."
> — No mention of the wrong number. Just moves on.

### ❌ CORRECT ANSWER STEAMROLLED AT L3
> Test 3, student says `a = 2.5 m/s²` (correct):
> AI L3: "You've put in a solid effort working through the problem step-by-step. Now, please provide your final calculated answer for the acceleration along with your complete reasoning before the solution is revealed."
> — The student JUST gave the final answer. AI ignored it.

### ❌ TOPIC LOCK SILENTLY FAILED
> Test 12, `topic_lock="Maxima and Minima"`, student: "explain gravitation":
> AI: "Imagine you hold a small ball in your hand and then let it go. What do you notice happens to the ball? Why do you think it falls down toward the ground rather than floating away? This everyday experience is actually due to gravitation..."
> — Should have said "This session is focused on Maxima and Minima — for gravitation, start a new session." Instead gave a full answer.

### ❌ OFF-TOPIC ANSWERED
> Test 11: "What is the capital of France?"
> AI: "It seems your question... is about general knowledge rather than physics. **The capital of France is Paris.** If you have any physics concepts you'd like explained, feel free to ask!"
> — The redirect is there, but the AI still answered. Leaks capability outside JEE scope.

---

## Metrics

| Metric | Value | Target |
|--------|-------|--------|
| **Banned-opener violations** | **1** (test 4, "no worries") | 0 |
| **Validation rate on correct student answers** | **6/9 weakly validated** (~67%). 0 strong validations (no "Exactly!", "Correct!", "Yes!"). | >80% strong |
| **Validator diversity** | 6/6 validators are the identical phrase "Good — you've got…" | 4+ distinct openers |
| **Wrong answers flagged as wrong** | **0/1** (Atwood `a=10` was NOT flagged) | 100% |
| **Topic lock redirects** | **0/1** (test 12 failed) | 100% |
| **Off-topic redirects without answering** | **0/1** (test 11 answered then redirected) | 100% |
| **Multi-question turns (HINT L1/L2)** | 0 | 0 ✅ |
| **Multi-question turns (L0 Socratic)** | ≥2 (tests 5, 12 have "what do you think... how many moles...") | 0 |
| **Hint-level progression integrity** | 0→1→2→3 clean in all runs | ✅ |
| **Context drift within a session** | 0 observed | 0 ✅ |
| **Mentor mode = COUNSELOR on "no idea"** | Did not trigger counselor (test 1 kept teaching mode) | ✅ |

---

## Root Cause Analysis

### 1. L3 forced-attempt template is applied BEFORE checking if student already gave the answer
Location: `app/services/doubt/engine.py get_hint()` — when `new_level == 3`, the prompt swap to `SYSTEM_PROMPT_FORCED_ATTEMPT` happens regardless of whether `student_response` contains the answer. The L3 prompt has no conditional: "if the student's last message contains a numerical answer or a final expression, validate it first; only then demand their complete reasoning". Result: correct answers at L3 get a generic "provide your final calculated answer" scolding.

### 2. Wrong answers not flagged — `{response_assessment}` LLM output is too soft
Location: `STUDENT_RESPONSE_ANALYSIS_PROMPT` in `prompts.py`. It returns `understood_correctly` + `knowledge_gaps` but doesn't EXPLICITLY say "the student's answer X is numerically wrong". When student says `a=10` for Atwood (wrong), the analyzer still returns "understood: net force concept" which becomes the response_assessment — the hint prompt then validates the concept and never mentions the wrong number.

### 3. Topic lock addendum being ignored by LLM
Location: `app/services/doubt/prompts.py TOPIC_LOCK_ADDENDUM` is appended to the system prompt, but appears as a short block AFTER the ~400-line TUTOR_SYSTEM_PROMPT. LLMs ignore instructions buried deep; the addendum needs to be at the TOP, not the end. Confirmed: test 12 stored `locked_topic=Maxima and Minima` in analysis (code verified), but the LLM answered the off-topic question anyway.

### 4. "No worries" still leaking
Location: appears in test 4 despite prompts.py having a RESPONSE VARIETY section banning it. The L1 hint prompt is long and the banned-openers list is in the SYSTEM prompt, not the HINT prompt template. When there's a mismatch between response_assessment ("student has not yet demonstrated correct understanding" — because analyzer missed the signal in "molecules move faster?") and reality, the LLM defaults to a generic gentle opener — including banned ones.

### 5. Validation stereotyped to "Good — you've got..."
Location: `HINT_LEVEL_1_PROMPT` and `HINT_LEVEL_2_PROMPT` have the CORRECT/PARTIALLY_CORRECT/WRONG/CONFUSED block. The PARTIALLY_CORRECT example uses `"Good — [X] is correct"`. The LLM copies this exact phrase every single time. The rotation/variety rule is in TUTOR_SYSTEM_PROMPT but loses to the concrete example in the hint prompt.

### 6. L0 multi-question — SINGLE QUESTION RULE only in hint prompts, not SOCRATIC_QUESTION_PROMPT
Test 12 and test 5 L0 both end with 2 questions. The SINGLE QUESTION RULE was added to HINT_LEVEL_1 and HINT_LEVEL_2 — not to `SOCRATIC_QUESTION_PROMPT`.

---

## Top 3 Prompt Changes (Highest Leverage)

### FIX 1 — Reorder TOPIC_LOCK_ADDENDUM to the TOP of the system prompt and strengthen it
Current: `active_system_prompt = TUTOR_SYSTEM_PROMPT + ... + TOPIC_LOCK_ADDENDUM`. Buried at end → LLM ignores.

Change `engine.py start_session()` and `get_hint()`:
```python
if locked_topic:
    active_system_prompt = TOPIC_LOCK_ADDENDUM.format(...) + "\n\n" + active_system_prompt
```
And rewrite `TOPIC_LOCK_ADDENDUM` to use stronger imperative language with refusal examples. Expected: test 12 redirect fires.

### FIX 2 — Pre-check correctness at L3 and skip the forced-attempt template if the student's last message contains the answer
Location: `engine.py get_hint()` where `new_level == 3`.

Add a quick LLM call (or regex + the existing `_analyze_student_response`) to check: does the student's latest message contain a numerical final answer or closed-form expression? If yes → validate explicitly ("Exactly — 2.5 m/s² is correct. Here's the complete derivation for your reference: ...") instead of the generic forced-attempt scold. Expected: tests 1 and 3 final answers get validated.

### FIX 3 — Make `STUDENT_RESPONSE_ANALYSIS_PROMPT` output an EXPLICIT correctness verdict on numerical/formula answers, and inject that verdict into the hint prompt
Add a new field to the analyzer output:
```
"answer_check": "correct" | "wrong" | "not_an_answer" | "partial",
"correct_value": "<if you can derive it from context>",
"student_value": "<what they said>"
```
Then in the hint prompt's RESPONSE ANALYSIS section, if `answer_check == "wrong"`, use the WRONG branch which says "Their answer is numerically wrong. Before anything else, say exactly which number is wrong and why, then guide toward the right value." Expected: test 3 wrong answer `a=10` gets flagged instead of ignored.

---

## Other Observations (Nice-to-have)

- **Validator stereotyping:** Add to HINT prompts a hard rule: "Do NOT use 'Good — you've got...' twice in a row. Rotate among 'Exactly!', 'Yes — that's right.', 'Correct — [restate].', 'Nice — [X] is exactly the right idea.'"
- **L0 single-question:** Add SINGLE QUESTION RULE to SOCRATIC_QUESTION_PROMPT.
- **Off-topic handling:** When `out_of_scope=True` (already detected — test 11 had `intent=explanation`), the response should be a pure redirect, not a 2-liner that answers the question first. Need a separate OFF_TOPIC_REDIRECT_PROMPT invoked before answering.
- **Analyzer hallucination:** Test 4's "I notice you haven't shared your thoughts" suggests the `student_response` wasn't passed to the analyzer correctly, or the analyzer defaulted to the "no response" path. Check `_analyze_student_response()` in engine.py — is `student_response` reaching it?

---

## Verdict

**Overall: 5.5/10.**

What's working: hint ladder plumbing, concrete anchors at L0, distinction between confused and distressed (counselor gate), Chemistry/Maths Socratic flows, intent classifier for greetings.

What's broken: topic lock (completely silent fail), wrong-vs-right answer discrimination, correct-answer-at-L3 steamrolling, validator stereotyping ("Good — you've got" on repeat), banned-opener leakage, off-topic handling that answers then redirects.

The system looks smart on happy-path conversations (pH, integration by parts). It breaks in exactly the moments where a real student needs the most precision: when they're wrong, when they finally get it right at the last hint, or when they try to derail the session.
