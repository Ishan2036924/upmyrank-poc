"""
Judge LLM — scores AI tutor responses for Socratic quality.

Entry point:
    score_response(student_question, ai_response) → {"score": int, "rationale": str}

Rubric:
    0 = gave full solution or direct answer — nothing left for student to figure out
    1 = gave a hint but too vague or too direct — minimal thought required
    2 = asked a leading Socratic question that forces the student to reason

Always fires as a background task (asyncio.create_task). Never called inline during
a student-facing request.
"""
from __future__ import annotations

import json
import logging
import re

import openai

from app.config import settings

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = (
    "You are evaluating whether an AI tutor response is Socratic.\n"
    "Score the response:\n"
    "  0 = gave full solution or direct answer — student has nothing left to figure out\n"
    "  1 = gave a hint but too vague or too direct — minimal thought required\n"
    "  2 = asked a leading Socratic question that forces the student to reason\n\n"
    "Return JSON only: {\"score\": int, \"rationale\": str}"
)


async def score_response(
    student_question: str,
    ai_response: str,
) -> dict:
    """
    Score an AI tutor response for Socratic quality using gpt-4.1-mini at temp=0.

    Returns:
        {"score": 0|1|2, "rationale": str}
        {"score": -1, "rationale": "judge_failed"} on any error.

    Never raises. Always returns a valid dict.
    """
    try:
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        user_content = (
            f"STUDENT QUESTION:\n{student_question}\n\n"
            f"AI TUTOR RESPONSE:\n{ai_response}"
        )
        resp = await client.chat.completions.create(
            model=settings.model_quality,  # gpt-4.1-mini
            temperature=0,
            max_tokens=200,
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user", "content": user_content},
            ],
        )
        raw = resp.choices[0].message.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            inner = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
            raw = "\n".join(inner).strip()

        # Parse JSON
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
            else:
                raise ValueError(f"No JSON found in judge response: {raw[:200]}")

        score = int(result.get("score", -1))
        if score not in (0, 1, 2):
            logger.warning("Judge returned out-of-range score %s — treating as -1", score)
            score = -1

        return {"score": score, "rationale": str(result.get("rationale", ""))}

    except Exception as exc:
        logger.warning("Judge LLM failed (non-fatal): %s", exc)
        return {"score": -1, "rationale": "judge_failed"}
