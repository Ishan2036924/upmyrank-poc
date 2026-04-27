"""
Conversation-arc judge — scores the WHOLE multi-turn conversation as a unit.

Complement to:
- judge.py            — per-response 4-dim scoring (writes judge_evaluations)
- turn_scorer.py      — per-turn quality scoring (writes conversation_turn_quality)

This module fires once per `doubt_session` at /session/end (via
_run_judge_for_session in app/api/session.py). It receives the full
transcript + metadata and writes ONE row to `conversation_arc_quality`.

Six dimensions:
    coherence               (0|1|2) — does the conversation flow feel coherent vs disjointed
    adaptation              (0|1|2) — does the AI change strategy when the student isn't getting it
    context_persistence     (0|1)   — does the AI remember earlier turns (no contradictions)
    closure                 (0|1|2) — does the conversation reach an appropriate end-state
    pedagogy_arc            (0|1|2) — did the student demonstrably move toward understanding
    back_and_forth_overall  (0|1)   — would this conversation be useful to a real student

composite_score = 0.25*(coherence/2) + 0.20*(adaptation/2) + 0.15*context_persistence
                + 0.15*(closure/2) + 0.20*(pedagogy_arc/2) + 0.05*back_and_forth_overall
                → [0.0, 1.0]

ALWAYS fire-and-forget. NEVER raises. (RULES.md #3.)
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional

import openai

from app.config import settings

logger = logging.getLogger(__name__)


_ARC_SYSTEM = """\
You are evaluating a multi-turn AI tutoring conversation as a whole. The
goal is to score the BACK-AND-FORTH quality, not any single turn.

You will see a transcript of student-AI exchanges. Score the conversation
on six dimensions. Return JSON only — no prose.

DIMENSIONS:

1. coherence (0|1|2)
   0 = the conversation feels disjointed; the AI ignores prior turns or
       jumps between unrelated angles
   1 = mostly coherent but with one or two noticeable threading breaks
   2 = the conversation reads as one continuous tutoring session — every
       AI turn picks up from where the prior turn left off

2. adaptation (0|1|2)
   0 = the AI keeps repeating the same approach even when the student
       clearly isn't getting it
   1 = the AI tries a different angle once but the rest is repetitive
   2 = the AI visibly adapts strategy (different example, simpler
       sub-question, analogy, etc.) when the student is stuck

3. context_persistence (0|1)
   0 = the AI contradicts something it said earlier in the same flow,
       OR forgets a fact the student supplied earlier
   1 = the AI maintains consistent claims across all turns

4. closure (0|1|2)
   0 = the conversation peters out — student is confused at the end with
       no plan; OR the AI just gives up; OR loops forever
   1 = some closure but unsatisfying — partial answer, vague next step
   2 = the conversation reaches a clean end-state — full resolution, OR
       productive struggle with a clear next move, OR graceful redirect
       (out-of-scope, deferred to teacher, etc.)

5. pedagogy_arc (0|1|2)
   0 = student is no closer to understanding at the end than the start
   1 = student demonstrates partial movement (states a piece correctly,
       asks a sharper follow-up, etc.) but hasn't internalised the concept
   2 = student demonstrably moves toward understanding — applies the
       framework, catches their own error, articulates the principle,
       or arrives at the answer through reasoning

6. back_and_forth_overall (0|1)
   0 = a real student would close the tab frustrated
   1 = a real student would feel this was a useful tutoring session

Be strict but fair. Do not give credit for what the AI didn't say. Do
not penalise productive struggle (a student leaving with a clear
sub-question to think about is closure=2, pedagogy_arc=2 even without
a numeric answer). The student-LLM in synthetic tests may be
deliberately stubborn; that is the test, not a bug — score the AI's
ability to handle that student, not the student's correctness.

Return JSON in EXACTLY this shape (no markdown, no extra keys):
{"coherence": 0|1|2, "adaptation": 0|1|2, "context_persistence": 0|1,
 "closure": 0|1|2, "pedagogy_arc": 0|1|2, "back_and_forth_overall": 0|1,
 "rationale": "<2-3 sentences justifying the lowest-scoring dimension>"}
"""


_ARC_USER_TEMPLATE = """\
Subject: {subject}
Topic: {topic}
Number of turns: {turn_count}

TRANSCRIPT:
{transcript}

Score the BACK-AND-FORTH quality of this conversation on the six dimensions.
"""


def _format_transcript(history: list[dict]) -> str:
    """Render the conversation_history JSONB into a transcript string.

    Each turn is one of:
      {"role": "student", "content": "..."}
      {"role": "tutor"|"assistant", "content": "..."}

    The judge sees roles labeled STUDENT and AI for clarity.
    """
    if not history:
        return "(empty)"
    lines: list[str] = []
    for i, turn in enumerate(history):
        if not isinstance(turn, dict):
            continue
        role = turn.get("role", "unknown")
        content = str(turn.get("content", ""))[:1200]
        if role == "student":
            label = "STUDENT"
        elif role in ("tutor", "assistant", "ai"):
            label = "AI"
        else:
            label = role.upper()
        lines.append(f"[Turn {i+1}] {label}: {content}")
    return "\n\n".join(lines)


def _safe_int(value: Any, lo: int, hi: int, default: int = 0) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _strip_markdown_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        # ```json\n...\n``` or ```\n...\n```
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
    return raw


def _composite(c: int, a: int, cp: int, cl: int, pa: int, bf: int) -> float:
    """Weighted composite — see module docstring."""
    return round(
        0.25 * (c / 2.0)
        + 0.20 * (a / 2.0)
        + 0.15 * cp
        + 0.15 * (cl / 2.0)
        + 0.20 * (pa / 2.0)
        + 0.05 * bf,
        4,
    )


async def score_arc(
    pool,
    doubt_session_id: str,
    history: list[dict],
    subject: str,
    topic: str,
    flow_id: Optional[str] = None,
    edge_class: Optional[str] = None,
) -> Optional[dict]:
    """Score the full conversation arc and write one row to
    `conversation_arc_quality`. Fire-and-forget — never raises.

    Args:
        pool:               asyncpg pool
        doubt_session_id:   the session being judged
        history:            list of turn dicts ({role, content, ...})
        subject, topic:     for context
        flow_id, edge_class: diagnostic-run tags (None for organic prod traffic)

    Returns:
        Result dict on success; None on any failure.
    """
    if not history or len(history) < 2:
        # Not enough turns to score back-and-forth.
        return None

    try:
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    except Exception as exc:
        logger.warning("score_arc: OpenAI client init failed (non-fatal): %s", exc)
        return None

    transcript = _format_transcript(history)
    user_msg = _ARC_USER_TEMPLATE.format(
        subject=subject or "Physics",
        topic=topic or "General",
        turn_count=len(history),
        transcript=transcript[:8000],  # safety cap on prompt size
    )

    try:
        resp = await client.chat.completions.create(
            model=settings.model_cheap,           # gpt-4o-mini
            messages=[
                {"role": "system", "content": _ARC_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=400,
            temperature=0,
        )
    except Exception as exc:
        logger.warning("score_arc: LLM call failed (non-fatal): %s", exc)
        return None

    try:
        raw = resp.choices[0].message.content or ""
        raw = _strip_markdown_fences(raw)
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("score_arc: JSON parse failed (non-fatal): %s — raw=%r",
                       exc, (resp.choices[0].message.content or "")[:300])
        return None

    coherence              = _safe_int(data.get("coherence"), 0, 2)
    adaptation             = _safe_int(data.get("adaptation"), 0, 2)
    context_persistence    = _safe_int(data.get("context_persistence"), 0, 1)
    closure                = _safe_int(data.get("closure"), 0, 2)
    pedagogy_arc           = _safe_int(data.get("pedagogy_arc"), 0, 2)
    back_and_forth_overall = _safe_int(data.get("back_and_forth_overall"), 0, 1)
    rationale              = str(data.get("rationale", ""))[:1500]

    composite = _composite(
        coherence, adaptation, context_persistence,
        closure, pedagogy_arc, back_and_forth_overall,
    )

    try:
        await pool.execute(
            """
            INSERT INTO conversation_arc_quality
              (doubt_session_id, flow_id, edge_class, turn_count,
               coherence, adaptation, context_persistence, closure,
               pedagogy_arc, back_and_forth_overall,
               composite_score, rationale)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
            uuid.UUID(doubt_session_id),
            flow_id, edge_class, len(history),
            coherence, adaptation, context_persistence, closure,
            pedagogy_arc, back_and_forth_overall,
            composite, rationale,
        )
        logger.info(
            "score_arc stored: session=%s turns=%d composite=%.3f "
            "(c=%d, a=%d, cp=%d, cl=%d, pa=%d, bf=%d)",
            doubt_session_id, len(history), composite,
            coherence, adaptation, context_persistence,
            closure, pedagogy_arc, back_and_forth_overall,
        )
    except Exception as exc:
        logger.warning("score_arc: DB insert failed (non-fatal): %s", exc)
        return None

    return {
        "coherence": coherence,
        "adaptation": adaptation,
        "context_persistence": context_persistence,
        "closure": closure,
        "pedagogy_arc": pedagogy_arc,
        "back_and_forth_overall": back_and_forth_overall,
        "composite_score": composite,
        "rationale": rationale,
    }
