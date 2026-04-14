"""
Mock test endpoints — strict MCQ format.

POST /mock/generate  — pick a random problem, generate 4 MCQ options via LLM,
                       cache correct option letter server-side, return options[] to client
POST /mock/submit    — verify by letter comparison (A/B/C/D), no LLM verifier needed
"""
import asyncio
import json
import logging
import random
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.middleware.auth import get_current_student_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mock", tags=["mock"])

# ── MCQ answer cache: problem_id → correct option letter (A/B/C/D) ─────────────
_MCQ_CACHE: dict[str, str] = {}

# ── MCQ generation prompt ────────────────────────────────────────────────────────
_MCQ_PROMPT = """\
You are a JEE/NEET {subject} exam question setter.

Given a {subject} question and its correct answer, generate exactly 4 multiple-choice \
options (A, B, C, D) following these STRICT rules:
1. Exactly ONE option must be the correct answer.
2. The other THREE must be plausible but definitively wrong distractors — \
   common student mistakes, sign errors, unit errors, or closely related values.
3. Options must be concise (≤ 20 words each).
4. Do NOT reveal which option is correct anywhere in the option text.
5. Randomise which letter (A, B, C, or D) holds the correct answer.
6. Return ONLY valid JSON — no markdown fences, no explanation, no extra keys.
7. JSON schema exactly: {{"A": "...", "B": "...", "C": "...", "D": "...", "correct": "X"}}

Question: {question}
Correct answer: {correct_answer}
"""


# ── Request models ───────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    subject: str = "Physics"
    topic: Optional[str] = None          # partial match via ILIKE
    difficulty: Optional[float] = Field(None, ge=0.0, le=1.0)


class SubmitRequest(BaseModel):
    problem_id: str
    answer: str          # expected: "A", "B", "C", or "D"
    student_id: str


# ── Helpers ──────────────────────────────────────────────────────────────────────

async def _generate_mcq_options(
    openai_client,
    question: str,
    correct_answer: str,
    subject: str = "Physics",
) -> dict:
    """
    Call the cheap LLM to produce 4 MCQ options + the correct letter.
    Falls back to a safe placeholder layout if the LLM call fails or returns bad JSON.
    Returns dict with keys A, B, C, D, correct.
    """
    try:
        resp = await openai_client.chat.completions.create(
            model=settings.model_cheap,
            messages=[
                {
                    "role": "user",
                    "content": _MCQ_PROMPT.format(
                        subject=subject,
                        question=question,
                        correct_answer=correct_answer,
                    ),
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=300,
        )
        data = json.loads(resp.choices[0].message.content)
        required = {"A", "B", "C", "D", "correct"}
        if required.issubset(data.keys()) and data["correct"] in {"A", "B", "C", "D"}:
            return data
        logger.warning("MCQ LLM returned unexpected JSON shape: %s", data)
    except Exception as exc:
        logger.warning("MCQ option generation failed: %s", exc)

    # ── Fallback: place correct answer in a random slot ──────────────────────────
    slot = random.choice(["A", "B", "C", "D"])
    others = [lbl for lbl in ["A", "B", "C", "D"] if lbl != slot]
    return {
        slot: correct_answer,
        others[0]: "Cannot be determined from the given data",
        others[1]: "None of the above",
        others[2]: "All of the above",
        "correct": slot,
    }


# ── Endpoints ────────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_mock(
    body: GenerateRequest,
    request: Request,
    _: str = Depends(get_current_student_id),
):
    """
    Pick a random problem from the DB, generate 4 MCQ options via LLM,
    cache the correct option letter server-side, and return the 4 option
    strings to the client (correct answer is never exposed).
    """
    pool = request.app.state.db_pool
    openai_client = request.app.state.socratic_engine._client

    try:
        # Build parameterised WHERE clause incrementally
        conditions = ["subject = $1"]
        params: list = [body.subject]
        idx = 2

        if body.topic:
            conditions.append(f"topic ILIKE ${idx}")
            params.append(f"%{body.topic}%")
            idx += 1

        if body.difficulty is not None:
            lo = max(0.0, body.difficulty - 0.2)
            hi = min(1.0, body.difficulty + 0.2)
            conditions.append(f"difficulty BETWEEN ${idx} AND ${idx + 1}")
            params.extend([lo, hi])
            idx += 2

        where = " AND ".join(conditions)
        query = f"""
            SELECT id, question_text, question_latex, topic, subtopic, difficulty,
                   verified_answer
            FROM   problems
            WHERE  {where}
            ORDER  BY RANDOM()
            LIMIT  1
        """
        row = await pool.fetchrow(query, *params)

        # Fallback: relax all filters, just pick any problem in the subject
        if row is None:
            row = await pool.fetchrow(
                """
                SELECT id, question_text, question_latex, topic, subtopic, difficulty,
                       verified_answer
                FROM   problems
                WHERE  subject = $1
                ORDER  BY RANDOM()
                LIMIT  1
                """,
                body.subject,
            )

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No problems found for subject='{body.subject}'.",
            )

        problem_id = str(row["id"])
        verified_answer = row["verified_answer"] or "See solution steps."

        # Generate MCQ options via LLM (correct answer used server-side only)
        mcq = await _generate_mcq_options(
            openai_client=openai_client,
            question=row["question_text"],
            correct_answer=verified_answer,
            subject=row.get("subject", body.subject),
        )

        # Cache correct letter — never sent to client
        _MCQ_CACHE[problem_id] = mcq["correct"]

        return {
            "problem_id":     problem_id,
            "question_text":  row["question_text"],
            "question_latex": row["question_latex"],
            "topic":          row["topic"],
            "subtopic":       row["subtopic"],
            "difficulty":     row["difficulty"],
            "options":        [mcq["A"], mcq["B"], mcq["C"], mcq["D"]],
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate_mock failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/submit")
async def submit_answer(
    body: SubmitRequest,
    request: Request,
    _: str = Depends(get_current_student_id),
):
    """
    Verify a student's MCQ answer by comparing the submitted letter (A/B/C/D)
    against the cached correct option. Updates concept mastery accordingly.
    """
    pool = request.app.state.db_pool

    # ── Validate UUIDs ───────────────────────────────────────────────────────────
    try:
        student_uuid = uuid.UUID(body.student_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid student_id: {body.student_id}",
        ) from exc

    try:
        problem_uuid = uuid.UUID(body.problem_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid problem_id: {body.problem_id}",
        ) from exc

    try:
        # ── Look up cached correct option ────────────────────────────────────────
        correct_option = _MCQ_CACHE.get(body.problem_id)
        if correct_option is None:
            logger.warning("MCQ cache miss for problem_id=%s", body.problem_id)
            correct_option = "?"

        submitted = body.answer.strip().upper()[:1]   # normalise to single letter
        correct = (submitted == correct_option)
        performance_score: float = 1.0 if correct else 0.0

        # ── Fetch problem metadata for mastery update ────────────────────────────
        problem = await pool.fetchrow(
            """
            SELECT verified_answer, concepts_tested, topic, subtopic, difficulty
            FROM   problems
            WHERE  id = $1
            """,
            problem_uuid,
        )
        if problem is None:
            raise HTTPException(
                status_code=404,
                detail=f"Problem not found: {body.problem_id}",
            )

        verified_answer: str = problem["verified_answer"] or "See solution steps."
        concepts_tested: list = list(problem["concepts_tested"] or [])

        # ── Full mastery pipeline (logs session_events + persona update) ──────────
        # Uses _mock_genome_update_task instead of a direct update_concept_mastery()
        # call so mock results feed the pedagogy loop (Rule 1 compliance).
        mastery_updates: list = []
        student_row = await pool.fetchrow(
            "SELECT id FROM students WHERE id = $1", student_uuid
        )
        if student_row is not None and concepts_tested:
            from app.api.doubt import _mock_genome_update_task
            asyncio.create_task(_mock_genome_update_task(
                pool=pool,
                student_id=str(student_uuid),
                concept_ids=concepts_tested,
                correct=correct,
                topic=problem["topic"] or "Unknown",
            ))

        # ── Pop cache entry ──────────────────────────────────────────────────────
        _MCQ_CACHE.pop(body.problem_id, None)

        explanation = (
            f"Correct! The answer was option {correct_option}."
            if correct
            else (
                f"Incorrect. You chose {submitted}, but the correct answer was "
                f"option {correct_option}: {verified_answer}"
            )
        )

        return {
            "correct":             correct,
            "confidence":          1.0 if correct else 0.0,
            "correct_option":      correct_option,
            "verified_answer":     verified_answer,
            "student_answer":      submitted,
            "explanation":         explanation,
            "concepts_tested":     concepts_tested,
            "verification_method": "mcq_letter_match",
            "flagged_for_review":  False,
            "mastery_updates":     mastery_updates,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("submit_answer failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
