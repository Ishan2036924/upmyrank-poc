"""
Onboarding API — first-time student persona builder.

POST /onboarding/submit  — collect answers, call GPT-4.1-mini, store persona profile
GET  /onboarding/status  — return { onboarding_completed: bool }
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.middleware.auth import get_current_student_id
from app.services.memory.context import update_persona_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ── Request / response models ─────────────────────────────────────────────────

class OnboardingSubmitRequest(BaseModel):
    class_level: str                            # "11th" | "12th" | "dropper"
    physics_prev_marks: Optional[int] = Field(None, ge=0, le=100)    # nullable if 11th
    chemistry_prev_marks: Optional[int] = Field(None, ge=0, le=100)  # NEW
    maths_prev_marks: Optional[int] = Field(None, ge=0, le=100)      # NEW
    easy_topics: List[str] = Field(default_factory=list, max_length=30)
    hard_topics: List[str] = Field(default_factory=list, max_length=30)
    study_hours_per_day: float = Field(ge=0.5, le=16.0)
    exam_type: str                              # "JEE_MAINS" | "JEE_ADVANCED" | "NEET"
    exam_date: Optional[str] = None            # ISO date string "YYYY-MM-DD"
    priority_subject: Optional[str] = None     # NEW: "Physics" | "Chemistry" | "Maths"
    learning_preference: Optional[str] = None  # NEW: "formula"|"analogy"|"example"|"visual"


# ── Persona builder ───────────────────────────────────────────────────────────

_PERSONA_PROMPT = """\
You are building a student profile for an AI JEE/NEET tutor covering Physics, Chemistry, and Maths.

Student answers:
- Class: {class_level}
- Physics marks: {physics_prev_marks}
- Chemistry marks: {chemistry_prev_marks}
- Maths marks: {maths_prev_marks}
- Priority subject (needs most work): {priority_subject}
- Learning preference (explicit): {learning_preference}
- Easy topics: {easy_topics}
- Hard topics: {hard_topics}
- Study hours/day: {study_hours_per_day}
- Exam: {exam_type} on {exam_date}

The easy_topics and hard_topics span Physics, Chemistry, AND Maths.

Output a JSON profile with EXACTLY these fields:
{{
  "scaffolding_level": "HIGH" | "MEDIUM" | "LOW",
  "preferred_style": "analogy" | "formula" | "example" | "visual",
  "weak_concepts": [],
  "strong_concepts": [],
  "predicted_irt_theta": <float between -2.0 and 2.0>,
  "study_intensity": "light" | "moderate" | "intense",
  "learning_velocity": "slow" | "medium" | "fast",
  "common_misconceptions": [],
  "allowed_hint_depth": 3,
  "interaction_depth_score": 0.0,
  "persona_summary": "<3-4 sentence human-readable summary covering all 3 subjects>",
  "subject_strengths": {{
    "Physics": "weak" | "medium" | "strong",
    "Chemistry": "weak" | "medium" | "strong",
    "Maths": "weak" | "medium" | "strong"
  }},
  "priority_subject": "<Physics|Chemistry|Maths or the student-provided value>",
  "learning_preference": "<formula|analogy|example|visual — use student-provided value if given>"
}}

Scoring logic:
- scaffolding_level: use the LOWEST marks across all 3 subjects:
    < 50 (or dropper < 60) → HIGH; 50–75 → MEDIUM; > 75 → LOW; if no marks available → HIGH
- subject_strengths per subject (based on that subject's marks):
    marks < 50 → "weak"; marks 50–75 → "medium"; marks > 75 → "strong"; no marks → "medium" for 12th, "weak" for 11th
- preferred_style: USE the student-provided learning_preference if it is not null/empty.
    Only infer if learning_preference is null:
    * mostly numerical hard_topics → formula
    * mostly conceptual/theoretical hard_topics → analogy
    * Chemistry-heavy hard_topics → visual
    * mixed → example
- predicted_irt_theta: dropper → -0.5 to +0.5 based on avg marks; 12th → -1.0 to 0.0; 11th → -2.0 to -1.0
- learning_velocity: study_hours >= 6 → fast; 3–5.9 → medium; < 3 → slow
- weak_concepts: map hard_topics to snake_case ids (e.g. "kinematics", "organic_chemistry", "integration")
- strong_concepts: map easy_topics similarly
- persona_summary: 3-4 sentences. Mention class, marks in each subject, priority subject,
  learning style, and which subjects need the most work.

Return ONLY valid JSON, no markdown, no explanation.
"""


async def _build_persona_from_onboarding(
    answers: OnboardingSubmitRequest,
    openai_client,
) -> dict:
    """
    Call gpt-4.1-mini to build a structured persona profile from onboarding answers.
    Returns a dict. On any failure returns safe HIGH-scaffolding defaults.
    """
    def _marks_str(val: Optional[int], subject: str) -> str:
        return f"{val}%" if val is not None else f"not available ({answers.class_level})"

    easy_str = ", ".join(answers.easy_topics) if answers.easy_topics else "none specified"
    hard_str = ", ".join(answers.hard_topics) if answers.hard_topics else "none specified"

    prompt = _PERSONA_PROMPT.format(
        class_level=answers.class_level,
        physics_prev_marks=_marks_str(answers.physics_prev_marks, "Physics"),
        chemistry_prev_marks=_marks_str(answers.chemistry_prev_marks, "Chemistry"),
        maths_prev_marks=_marks_str(answers.maths_prev_marks, "Maths"),
        priority_subject=answers.priority_subject or "not specified",
        learning_preference=answers.learning_preference or "not specified (infer from topics)",
        easy_topics=easy_str,
        hard_topics=hard_str,
        study_hours_per_day=answers.study_hours_per_day,
        exam_type=answers.exam_type,
        exam_date=answers.exam_date or "not set",
    )

    _default_style = answers.learning_preference or "analogy"
    _DEFAULTS = {
        "scaffolding_level":    "HIGH",
        "preferred_style":      _default_style,
        "weak_concepts":        [t.lower().replace(" ", "_").replace("&", "and") for t in answers.hard_topics],
        "strong_concepts":      [t.lower().replace(" ", "_").replace("&", "and") for t in answers.easy_topics],
        "predicted_irt_theta":  -1.0,
        "study_intensity":      "moderate",
        "learning_velocity":    "medium",
        "common_misconceptions": [],
        "allowed_hint_depth":   3,
        "interaction_depth_score": 0.0,
        "persona_summary": (
            f"{answers.class_level} student preparing for {answers.exam_type}. "
            f"Priority subject: {answers.priority_subject or 'not specified'}. "
            f"Will use {_default_style}-based teaching with thorough scaffolding."
        ),
        "subject_strengths": {"Physics": "medium", "Chemistry": "medium", "Maths": "medium"},
        "priority_subject": answers.priority_subject or "Physics",
        "learning_preference": answers.learning_preference or "analogy",
    }

    try:
        resp = await openai_client.chat.completions.create(
            model=settings.model_quality,   # gpt-4.1-mini
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            timeout=15,
        )
        raw = resp.choices[0].message.content.strip()

        # Strip optional markdown fences
        if raw.startswith("```"):
            lines = raw.splitlines()
            inner = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
            raw = "\n".join(inner).strip()

        profile = json.loads(raw)

        # Validate required keys exist; fall back to defaults for missing ones
        for key, default_val in _DEFAULTS.items():
            if key not in profile:
                profile[key] = default_val

        logger.info(
            "Persona built: scaffolding=%s style=%s irt=%.2f",
            profile.get("scaffolding_level"),
            profile.get("preferred_style"),
            profile.get("predicted_irt_theta", 0.0),
        )
        return profile

    except Exception as exc:
        logger.warning("_build_persona_from_onboarding failed (%s), using defaults", exc)
        return _DEFAULTS


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/submit")
async def submit_onboarding(
    body: OnboardingSubmitRequest,
    request: Request,
    current_student_id: str = Depends(get_current_student_id),
):
    """
    Store onboarding answers, build persona profile via GPT-4.1-mini,
    persist to student_memory, mark onboarding_completed = TRUE.
    """
    pool          = request.app.state.db_pool
    openai_client = request.app.state.socratic_engine._client

    if body.class_level not in ("11th", "12th", "dropper"):
        raise HTTPException(status_code=400, detail="class_level must be 11th, 12th, or dropper")
    if body.exam_type not in ("JEE_MAINS", "JEE_ADVANCED", "NEET"):
        raise HTTPException(status_code=400, detail="exam_type must be JEE_MAINS, JEE_ADVANCED, or NEET")

    student_uuid = uuid.UUID(current_student_id)

    # ── 1. Persist raw answers to students table ──────────────────────────────
    import datetime
    exam_date_val = None
    if body.exam_date:
        try:
            exam_date_val = datetime.date.fromisoformat(body.exam_date)
        except ValueError:
            pass

    await pool.execute(
        """
        UPDATE students
        SET class_level            = $2,
            physics_prev_marks     = $3,
            chemistry_prev_marks   = $4,
            maths_prev_marks       = $5,
            study_hours_per_day    = $6,
            exam_date              = $7,
            priority_subject       = $8,
            learning_preference    = $9
        WHERE id = $1
        """,
        student_uuid,
        body.class_level,
        body.physics_prev_marks,
        body.chemistry_prev_marks,
        body.maths_prev_marks,
        body.study_hours_per_day,
        exam_date_val,
        body.priority_subject,
        body.learning_preference,
    )

    # ── 2. Build persona profile from answers via LLM ─────────────────────────
    persona_profile = await _build_persona_from_onboarding(body, openai_client)

    # ── 3. Store in student_memory ────────────────────────────────────────────
    try:
        await update_persona_profile(current_student_id, persona_profile, pool)
    except Exception as exc:
        logger.warning("update_persona_profile failed (non-fatal): %s", exc)

    # ── 4. Mark onboarding complete ───────────────────────────────────────────
    await pool.execute(
        "UPDATE students SET onboarding_completed = TRUE WHERE id = $1",
        student_uuid,
    )

    summary = persona_profile.get("persona_summary", "")
    logger.info("Onboarding complete for student %s", current_student_id)

    return {
        "persona_profile": persona_profile,
        "summary": summary,
    }


@router.get("/status")
async def onboarding_status(
    request: Request,
    current_student_id: str = Depends(get_current_student_id),
):
    """Return whether this student has completed onboarding."""
    pool = request.app.state.db_pool
    row = await pool.fetchrow(
        "SELECT onboarding_completed FROM students WHERE id = $1",
        uuid.UUID(current_student_id),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"onboarding_completed": bool(row["onboarding_completed"])}
