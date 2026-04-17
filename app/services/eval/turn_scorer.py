"""
Per-turn conversation quality scorer.

Fires asynchronously after every hint at levels 1–2 to score the AI response
on 4 dimensions:
  - validation_score  (0–2): did the AI acknowledge / validate the student's answer?
  - appropriateness   (0–2): was the strategy right for this answer type?
  - restart_detected  (bool): did the AI restart from scratch instead of building on the answer?
  - single_question   (bool): did the AI end with exactly ONE focused question?

Results are stored in conversation_turn_quality. Never raises — always fire-and-forget.
"""

from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger(__name__)


async def score_turn(
    client,           # openai.AsyncOpenAI
    pool,             # asyncpg pool
    doubt_session_id: str,
    turn_index: int,
    student_message: str,
    ai_response: str,
) -> None:
    """Score a single conversation turn. Fire-and-forget — never raises."""
    try:
        from app.services.doubt.prompts import TURN_QUALITY_SCORER_PROMPT  # noqa: PLC0415

        prompt = TURN_QUALITY_SCORER_PROMPT.format(
            student_message=student_message[:2000],
            ai_response=ai_response[:2000],
        )

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0,
        )

        raw = resp.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        await pool.execute(
            """
            INSERT INTO conversation_turn_quality
              (doubt_session_id, turn_index, student_message, ai_response,
               validation_score, appropriateness, restart_detected, single_question,
               judge_rationale)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            uuid.UUID(doubt_session_id),
            turn_index,
            student_message[:4000],
            ai_response[:4000],
            _safe_int(data.get("validation_score"), 0, 2),
            _safe_int(data.get("appropriateness"), 0, 2),
            bool(data.get("restart_detected", False)),
            bool(data.get("single_question", True)),
            str(data.get("rationale", ""))[:1000],
        )
        logger.debug(
            "score_turn stored: session=%s turn=%d val=%s appropriate=%s restart=%s single_q=%s",
            doubt_session_id, turn_index,
            data.get("validation_score"), data.get("appropriateness"),
            data.get("restart_detected"), data.get("single_question"),
        )

    except Exception as exc:
        logger.warning("score_turn failed (non-fatal): %s", exc)


def _safe_int(val, lo: int, hi: int) -> int | None:
    """Clamp val to [lo, hi] or return None if unparseable."""
    try:
        v = int(val)
        return max(lo, min(hi, v))
    except (TypeError, ValueError):
        return None
