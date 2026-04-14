"""
Judge LLM — scores AI tutor responses across 4 dimensions.

Entry points:
    evaluate_response(question, ai_response, rag_context, hint_level, prior_attempts)
        → {pedagogical_score, factual_score, context_relevance_score,
           hint_appropriateness_score, overall_score, rationale}

    score_response(student_question, ai_response)  [backward-compat wrapper]
        → {"score": int, "rationale": str}

Dimensions:
    pedagogical_score          (0|1|2)  — Socratic quality (existing dimension)
    factual_score              (0|1)    — factually accurate content
    context_relevance_score    (0|1)    — RAG context used appropriately
    hint_appropriateness_score (0|1)    — right hint level for student's state

overall_score = 0.4*(ped/2) + 0.3*factual + 0.15*ctx + 0.15*hint  → [0.0, 1.0]

Always fires as a background task (asyncio.create_task). Never called inline.
"""
from __future__ import annotations

import json
import logging
import re

import openai

from app.config import settings

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = """\
You are evaluating an AI tutor response across 4 dimensions. Return JSON only — no prose.

DIMENSIONS:
1. pedagogical_score (0|1|2)
   0 = gave full solution or direct answer — student has nothing left to figure out
   1 = hint but too vague or too direct — minimal student thought required
   2 = Socratic question that forces the student to reason through the problem

2. factual_score (0|1)
   0 = contains factual errors, wrong formulas, incorrect physics/chemistry/maths
   1 = factually accurate

3. context_relevance_score (0|1)
   0 = ignores or contradicts the provided context; response seems generic
   1 = the response leverages the context appropriately (or no context was needed)

4. hint_appropriateness_score (0|1)
   0 = hint level is wrong for the student state (e.g., full answer at hint_level=1,
       or still holding back at hint_level=3)
   1 = hint depth is appropriate for the given hint_level and prior attempt count

Return ONLY this JSON structure:
{
  "pedagogical_score": <0|1|2>,
  "factual_score": <0|1>,
  "context_relevance_score": <0|1>,
  "hint_appropriateness_score": <0|1>,
  "rationale": {
    "pedagogical": "<one sentence>",
    "factual": "<one sentence>",
    "context_relevance": "<one sentence>",
    "hint_appropriateness": "<one sentence>"
  }
}
"""


def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON. Raises ValueError on failure."""
    if raw.startswith("```"):
        lines = raw.splitlines()
        inner = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
        raw = "\n".join(inner).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No JSON found in judge response: {raw[:200]}")


async def evaluate_response(
    question: str,
    ai_response: str,
    rag_context: str = "",
    hint_level: int = 0,
    prior_attempts: int = 0,
) -> dict:
    """
    Score an AI tutor response on 4 dimensions using gpt-4o-mini at temp=0.

    Returns on success:
        {
            "pedagogical_score": 0|1|2,
            "factual_score": 0|1,
            "context_relevance_score": 0|1,
            "hint_appropriateness_score": 0|1,
            "overall_score": float,   # weighted composite [0.0, 1.0]
            "rationale": {
                "pedagogical": str,
                "factual": str,
                "context_relevance": str,
                "hint_appropriateness": str,
            }
        }

    Returns on any error:
        {"pedagogical_score": -1, "factual_score": -1, ..., "overall_score": -1.0,
         "rationale": {"pedagogical": "judge_failed", ...}}

    Never raises.
    """
    _error_result = {
        "pedagogical_score": -1,
        "factual_score": -1,
        "context_relevance_score": -1,
        "hint_appropriateness_score": -1,
        "overall_score": -1.0,
        "rationale": {
            "pedagogical": "judge_failed",
            "factual": "judge_failed",
            "context_relevance": "judge_failed",
            "hint_appropriateness": "judge_failed",
        },
    }

    try:
        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

        context_block = (
            f"\nRAG CONTEXT PROVIDED TO TUTOR:\n{rag_context[:1500]}\n"
            if rag_context else "\nRAG CONTEXT: (none provided)\n"
        )

        user_content = (
            f"STUDENT QUESTION:\n{question}\n"
            f"{context_block}"
            f"HINT LEVEL: {hint_level}  |  PRIOR STUDENT ATTEMPTS: {prior_attempts}\n\n"
            f"AI TUTOR RESPONSE:\n{ai_response}"
        )

        resp = await client.chat.completions.create(
            model=settings.model_cheap,  # gpt-4o-mini — never gpt-4o for text
            temperature=0,
            max_tokens=400,
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM},
                {"role": "user",   "content": user_content},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        result = _parse_json(raw)

        ped  = int(result.get("pedagogical_score", -1))
        fact = int(result.get("factual_score", -1))
        ctx  = int(result.get("context_relevance_score", -1))
        hint = int(result.get("hint_appropriateness_score", -1))

        # Clamp to valid ranges
        ped  = ped  if ped  in (0, 1, 2) else -1
        fact = fact if fact in (0, 1)    else -1
        ctx  = ctx  if ctx  in (0, 1)    else -1
        hint = hint if hint in (0, 1)    else -1

        # Weighted composite: only compute if all dimensions succeeded
        if all(v >= 0 for v in (ped, fact, ctx, hint)):
            overall = round(0.4 * (ped / 2) + 0.3 * fact + 0.15 * ctx + 0.15 * hint, 4)
        else:
            overall = -1.0

        rationale = result.get("rationale", {})
        if not isinstance(rationale, dict):
            rationale = {"pedagogical": str(rationale), "factual": "", "context_relevance": "", "hint_appropriateness": ""}

        return {
            "pedagogical_score":          ped,
            "factual_score":              fact,
            "context_relevance_score":    ctx,
            "hint_appropriateness_score": hint,
            "overall_score":              overall,
            "rationale":                  rationale,
        }

    except Exception as exc:
        logger.warning("Judge LLM failed (non-fatal): %s", exc)
        return _error_result


async def score_response(
    student_question: str,
    ai_response: str,
) -> dict:
    """
    Backward-compatible wrapper around evaluate_response().
    Returns {"score": int, "rationale": str} (original shape).

    Existing callers in doubt.py use this signature — do not change it.
    """
    result = await evaluate_response(
        question=student_question,
        ai_response=ai_response,
    )
    ped = result["pedagogical_score"]
    rat = result["rationale"]
    rationale_str = rat.get("pedagogical", "judge_failed") if isinstance(rat, dict) else str(rat)
    return {"score": ped, "rationale": rationale_str}
