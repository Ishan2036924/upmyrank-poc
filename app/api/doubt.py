"""
Doubt-resolution API — intent-gated routing.

POST /doubt/ask    — classify intent → route to non-physics response or Socratic pipeline
POST /doubt/hint   — progressive hint for an active doubt session
POST /doubt/verify — two-layer solution verification
"""
import asyncio
import json
import logging
import uuid
from typing import Optional

import json as _json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator, model_validator

from app.middleware.auth import get_current_student_id

from app.services.memory.context import build_context_bundle, format_context_for_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/doubt", tags=["doubt"])


# ── request / response models ─────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: Optional[str] = None
    image_url: Optional[str] = None    # Supabase Storage public URL for an image
    student_id: Optional[str] = None   # Ignored when auth header present; kept for legacy clients
    subject: str = "Physics"
    study_session_id: Optional[str] = None
    topic_lock: Optional[str] = None   # When set, skips intent classification and pins the topic
    student_confidence: Optional[str] = None  # low / medium / high — captured at forced attempt

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("question must not be empty or whitespace")
        return v.strip() if v else None

    @model_validator(mode="after")
    def at_least_question_or_image(self) -> "AskRequest":
        if not self.question and not self.image_url:
            raise ValueError("at least one of question or image_url must be provided")
        return self


class HintRequest(BaseModel):
    session_id: str
    student_response: Optional[str] = None
    jump_to_full_solution: bool = False
    study_session_id: Optional[str] = None
    give_up_flag: bool = False          # set True when student explicitly gives up
    mistake_tag: Optional[str] = None   # e.g. 'sign_error', 'wrong_formula'


class VerifyRequest(BaseModel):
    question: str
    solution: str
    context: str = ""


# ── doubt-block helpers ───────────────────────────────────────────────────────

async def _get_active_doubt_block(pool, study_session_id: str) -> Optional[dict]:
    """Get the latest unsolved, unclosed doubt block for a study session."""
    try:
        row = await pool.fetchrow(
            """
            SELECT doubt_block_id, doubt_session_id, topic, hint_level, solved,
                   misconception_id
            FROM doubt_blocks
            WHERE study_session_id = $1
              AND ended_at IS NULL
              AND solved = FALSE
            ORDER BY started_at DESC
            LIMIT 1
            """,
            uuid.UUID(study_session_id),
        )
        if row:
            return dict(row)
        return None
    except Exception as exc:
        logger.warning("_get_active_doubt_block failed: %s", exc)
        return None


async def _create_doubt_block(
    pool,
    study_session_id: str,
    student_id: str,
    doubt_session_id: uuid.UUID,
    topic: str,
    student_confidence: Optional[str] = None,
) -> str:
    """Create a new doubt block and increment the study session's doubt_count."""
    block = await pool.fetchrow(
        """
        INSERT INTO doubt_blocks
            (study_session_id, student_id, doubt_session_id, topic, student_confidence)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING doubt_block_id
        """,
        uuid.UUID(study_session_id),
        uuid.UUID(student_id),
        doubt_session_id,
        topic,
        student_confidence,
    )

    await pool.execute(
        """
        UPDATE study_sessions
        SET doubt_count = COALESCE(doubt_count, 0) + 1
        WHERE study_session_id = $1
        """,
        uuid.UUID(study_session_id),
    )

    return str(block["doubt_block_id"])


async def _close_doubt_block(pool, engine, doubt_block_id: str, solved: bool):
    """Close a doubt block and fire-and-forget the summarizer."""
    await pool.execute(
        """
        UPDATE doubt_blocks
        SET ended_at = NOW(), solved = $2
        WHERE doubt_block_id = $1
        """,
        uuid.UUID(doubt_block_id),
        solved,
    )
    asyncio.create_task(engine.summarize_doubt_block(doubt_block_id))


# ── background genome update ──────────────────────────────────────────────────

# Performance score mapping: hint level reached → how well the student did
_HINT_PERF_MAP = {
    0: 1.0,   # solved from Socratic question alone — excellent
    1: 0.90,  # needed 1 conceptual nudge
    2: 0.75,  # needed structural hint
    3: 0.55,  # needed partial solution
}
_GIVE_UP_PERF = 0.10    # student gave up — minimal positive signal


async def _genome_update_task(
    pool,
    doubt_session_id: str,
    give_up_flag: bool = False,
    mistake_tag: Optional[str] = None,
    session_type: str = "doubt",
    student_confidence: Optional[str] = None,  # low / medium / high
    misconception_id: Optional[str] = None,    # ID from misconceptions.py if detected
) -> None:
    """
    Terminal-state background task — fires ONLY when a doubt block closes.

    Steps:
      1. Fetch session metadata (hint_level, concepts_involved, resolved, topic).
      2. Compute time_to_solve from doubt_session.created_at.
      3. INSERT a telemetry row into session_events (new pedagogical columns).
      4. UPSERT concept_mastery for every concept tested:
             mastery = 0.7 × old_mastery + 0.3 × performance_score  (EMA α=0.7)
         Also tag mistake_forensics in error_pattern_array if mistake_tag is set.
    """
    from app.services.mastery import update_concept_mastery

    try:
        session_uuid = uuid.UUID(doubt_session_id)
    except ValueError:
        logger.warning("_genome_update_task: invalid session UUID %s", doubt_session_id)
        return

    try:
        session = await pool.fetchrow(
            """
            SELECT student_id, current_hint_level, concepts_involved,
                   resolved, topic, created_at
            FROM doubt_sessions
            WHERE id = $1
            """,
            session_uuid,
        )
        if session is None:
            logger.warning("_genome_update_task: session %s not found", doubt_session_id)
            return

        student_uuid: uuid.UUID   = session["student_id"]
        hint_level:   int         = session["current_hint_level"] or 0
        concept_ids:  list        = list(session["concepts_involved"] or [])
        resolved:     bool        = bool(session["resolved"])
        topic:        str         = session["topic"] or "Unknown"
        created_at                = session["created_at"]

        # ── Time to solve ────────────────────────────────────────────────────
        import datetime
        time_seconds: Optional[int] = None
        if created_at:
            try:
                delta = datetime.datetime.now(datetime.timezone.utc) - created_at
                time_seconds = max(0, int(delta.total_seconds()))
            except Exception:
                pass

        # ── Performance score ────────────────────────────────────────────────
        if give_up_flag:
            performance = _GIVE_UP_PERF
        else:
            performance = _HINT_PERF_MAP.get(min(hint_level, 3), 0.2)

        # ── Confidence modifier (misconception signal) ────────────────────────
        # Applies to the signed deviation from neutral (0.5) so the modifier
        # amplifies or shrinks the effect without breaking the [0, 1] range.
        error_type_override: Optional[str] = None
        if student_confidence:
            delta = performance - 0.5
            if student_confidence == "high" and not resolved:
                # High confidence + wrong → misconception, 1.5× penalty
                performance = max(0.0, min(1.0, 0.5 + delta * 1.5))
                error_type_override = "misconception"
            elif student_confidence == "high" and resolved:
                # High confidence + correct → strong understanding, 1.3× boost
                performance = max(0.0, min(1.0, 0.5 + delta * 1.3))
            elif student_confidence == "low" and resolved:
                # Low confidence + correct → lucky guess, 0.7× boost
                performance = max(0.0, min(1.0, 0.5 + delta * 0.7))

        # ── Misconception penalty (applied before mastery EMA) ───────────────
        # When a misconception was detected AND the student did not solve:
        # apply 1.5× penalty (same signal weight as high-confidence + wrong).
        effective_mistake_tag = mistake_tag
        if misconception_id and not resolved and not give_up_flag:
            delta = performance - 0.5
            performance = max(0.0, min(1.0, 0.5 + delta * 1.5))
            effective_mistake_tag = effective_mistake_tag or "misconception"

        # ── 1. INSERT telemetry into session_events ──────────────────────────
        await pool.execute(
            """
            INSERT INTO session_events
                (session_id, event_type, student_id, session_type,
                 time_to_solve_seconds, max_hint_level_used,
                 mistake_forensics_tag, give_up_flag, misconception_detected, payload)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
            """,
            session_uuid,
            "session_terminal",
            student_uuid,
            session_type,
            time_seconds,
            min(hint_level, 3),
            effective_mistake_tag,
            give_up_flag,
            bool(misconception_id),
            json.dumps({"resolved": resolved, "topic": topic, "misconception_id": misconception_id}),
        )

        # ── 2. UPSERT concept_mastery (EMA α=0.7) ────────────────────────────
        if concept_ids:
            for concept_id in concept_ids:
                try:
                    result = await update_concept_mastery(
                        pool=pool,
                        student_id=student_uuid,
                        concept_id=concept_id,
                        performance_score=performance,
                        mistake_tag=mistake_tag,
                    )
                    if result is None:
                        # Row missing → insert at baseline (new concept for this student)
                        await pool.execute(
                            """
                            INSERT INTO concept_mastery
                                (student_id, concept_id, mastery_score,
                                 error_count, attempt_count, updated_at)
                            VALUES ($1, $2, $3, $4, 1, NOW())
                            ON CONFLICT (student_id, concept_id) DO UPDATE
                                SET mastery_score = 0.7 * concept_mastery.mastery_score
                                                  + 0.3 * EXCLUDED.mastery_score,
                                    attempt_count = concept_mastery.attempt_count + 1,
                                    updated_at    = NOW()
                            """,
                            student_uuid,
                            concept_id,
                            performance,
                            1 if performance < 0.5 else 0,
                        )
                except Exception as exc:
                    logger.warning(
                        "Mastery update failed for concept=%s: %s", concept_id, exc,
                    )

        # ── 3. Update error fingerprint + forgetting rate per concept ─────────
        effective_error_type = error_type_override or (
            "misconception" if misconception_id else mistake_tag
        )
        if concept_ids and effective_error_type:
            from app.services.memory.context import (
                update_error_fingerprint,
                update_forgetting_rate,
            )
            import datetime
            for concept_id in concept_ids:
                try:
                    await update_error_fingerprint(
                        student_id=str(student_uuid),
                        concept_id=concept_id,
                        error_type=effective_error_type,
                        was_correct=resolved and not give_up_flag,
                        db=pool,
                    )
                except Exception as fp_exc:
                    logger.warning("update_error_fingerprint failed for %s: %s", concept_id, fp_exc)

                try:
                    # days_since_last_review: derive from time_seconds if available
                    days = max(1, (time_seconds or 0) // 86400)
                    await update_forgetting_rate(
                        student_id=str(student_uuid),
                        concept_id=concept_id,
                        days_since_last_review=days,
                        performance=performance,
                        db=pool,
                    )
                except Exception as fr_exc:
                    logger.warning("update_forgetting_rate failed for %s: %s", concept_id, fr_exc)

        # ── 4. Update persona profile ─────────────────────────────────────────
        try:
            from app.services.memory.context import (
                get_persona_profile,
                update_persona_profile,
                infer_scaffolding_level,
                get_sessions_count,
            )
            current_profile = await get_persona_profile(str(student_uuid), pool)
            depth_score = float(current_profile.get("interaction_depth_score", 0.0))
            if resolved and hint_level <= 1:
                new_depth = min(1.0, depth_score + 0.05)
            else:
                new_depth = max(0.0, depth_score - 0.02)
            await update_persona_profile(
                str(student_uuid), {"interaction_depth_score": new_depth}, pool
            )

            # Add misconception to persona common_misconceptions (no duplicates)
            if misconception_id and not resolved:
                current_profile = await get_persona_profile(str(student_uuid), pool)
                existing = current_profile.get("common_misconceptions", [])
                if misconception_id not in existing:
                    await update_persona_profile(
                        str(student_uuid),
                        {"common_misconceptions": existing + [misconception_id]},
                        pool,
                    )

            # Re-infer scaffolding level every 5 sessions
            sessions_count = await get_sessions_count(str(student_uuid), pool)
            if sessions_count > 0 and sessions_count % 5 == 0:
                await infer_scaffolding_level(str(student_uuid), pool)
        except Exception as persona_exc:
            logger.warning("Persona update failed (non-fatal): %s", persona_exc)

        logger.info(
            "Genome updated: session=%s student=%s concepts=%d perf=%.2f give_up=%s",
            doubt_session_id, student_uuid, len(concept_ids), performance, give_up_flag,
        )

    except Exception as exc:
        logger.error("_genome_update_task failed for session %s: %s", doubt_session_id, exc)


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ask")
async def ask_doubt(
    body: AskRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_student_id: str = Depends(get_current_student_id),
):
    """
    Intent-gated doubt handler.

    1. Classify intent (greeting, meta, emotional, out_of_scope, physics_doubt, continuation)
    2. Non-physics intents → immediate response, NO DB writes
    3. continuation → delegate to get_hint via active block's doubt_session_id
    4. physics_doubt → start new session + create doubt block
    """
    engine = request.app.state.socratic_engine
    pool = request.app.state.db_pool

    # ── Vision AI: extract question from image if no text question ────────────
    question = body.question
    if not question and body.image_url:
        try:
            question = await engine.extract_question_from_image(body.image_url)
            logger.info("Vision AI: extracted question from image (%d chars)", len(question))
        except Exception as exc:
            logger.error("Vision AI extraction failed: %s", exc)
            raise HTTPException(
                status_code=422, detail=f"Could not extract question from image: {exc}"
            ) from exc
    # question is guaranteed non-empty at this point (model_validator ensures one is present)

    # ── 1. Check for active doubt block ───────────────────────────────────────
    active_block = None
    if body.study_session_id:
        active_block = await _get_active_doubt_block(pool, body.study_session_id)

    has_active_block = active_block is not None and not active_block.get("solved", False)

    # ── 1b. Forced-attempt bypass ─────────────────────────────────────────────
    # If the active block is at hint_level >= 3 (forced attempt), ANY student
    # response — including "I don't know", "skip", emotional messages — must go
    # straight to the full solution.  We skip intent classification entirely to
    # prevent the therapist hijack (emotional intent routing).
    if has_active_block and active_block.get("hint_level", 0) >= 3:
        logger.info(
            "Forced-attempt bypass: block %s at hint_level=%d, routing directly to get_hint (full solution)",
            active_block["doubt_block_id"], active_block["hint_level"],
        )
        intent = "continuation"
        # Fall through to continuation handler below

    # ── 2. Classify intent (skipped when topic_lock is set or forced-attempt) ─
    elif body.topic_lock:
        # Topic is pinned from the syllabus — no LLM classification needed
        intent = "physics_doubt"
        logger.info("topic_lock=%r → bypassing intent classifier, forcing physics_doubt", body.topic_lock)
    else:
        intent = await engine.classify_intent(question, has_active_block)
        logger.info("Intent classified: %s (active_block=%s)", intent, has_active_block)

    # ── 3. Non-physics intents → immediate response, NO DB writes ─────────────
    if intent in ("greeting", "meta", "emotional", "out_of_scope"):
        result = await engine.handle_non_physics_intent(intent, question)
        return result

    # ── 3b. Recap — summarise completed doubt blocks in this session ───────────
    if intent == "recap":
        if body.study_session_id:
            rows = await pool.fetch(
                """
                SELECT topic, summary, solved, started_at
                FROM doubt_blocks
                WHERE study_session_id = $1
                ORDER BY started_at ASC
                """,
                uuid.UUID(body.study_session_id),
            )
            completed = [r for r in rows if r["summary"]]
            if completed:
                lines = ["Here's what we've covered in this session:\n"]
                for i, row in enumerate(completed, 1):
                    topic = row["topic"] or "Physics question"
                    solved_label = "✓ Solved" if row["solved"] else "⟳ In progress"
                    lines.append(f"**{i}. {topic}** — {solved_label}\n{row['summary']}")
                response = "\n\n".join(lines)
            elif rows:
                # Blocks exist but summaries not yet generated (still in progress)
                topics = [r["topic"] or "Physics question" for r in rows]
                topic_list = ", ".join(f"**{t}**" for t in topics)
                response = (
                    f"We're currently working through: {topic_list}. "
                    "Summaries are generated once a question is resolved — "
                    "keep going! 💪"
                )
            else:
                response = (
                    "We haven't covered any topics yet in this session. "
                    "Ask me a Physics question to get started!"
                )
        else:
            response = (
                "I don't have a record of this session. "
                "Start a new session and I'll track everything you cover!"
            )
        return {"intent": "recap", "response": response, "session_id": None}

    # ── 4. Continuation (follow-up to active block) ───────────────────────────
    if intent == "continuation" and active_block:
        try:
            hint_result = await engine.get_hint(
                session_id=str(active_block["doubt_session_id"]),
                student_response=question,
            )

            # Update block hint_level + store confidence + misconception if detected
            _mc_id_ask = hint_result.get("misconception_id")
            await pool.execute(
                """
                UPDATE doubt_blocks
                SET hint_level             = $1,
                    student_confidence     = COALESCE($3::varchar, student_confidence),
                    misconception_detected = CASE WHEN $4::varchar IS NOT NULL THEN TRUE ELSE misconception_detected END,
                    misconception_id       = COALESCE($4::varchar, misconception_id)
                WHERE doubt_block_id = $2
                """,
                hint_result.get("hint_level", active_block["hint_level"]),
                active_block["doubt_block_id"],
                body.student_confidence,
                _mc_id_ask,
            )

            # If resolved, close the block + schedule genome update
            if hint_result.get("resolved"):
                await _close_doubt_block(
                    pool, engine, str(active_block["doubt_block_id"]), solved=True,
                )
                background_tasks.add_task(
                    _genome_update_task,
                    pool,
                    str(active_block["doubt_session_id"]),
                    give_up_flag=False,
                    mistake_tag=None,
                    student_confidence=body.student_confidence,
                    misconception_id=active_block.get("misconception_id") or _mc_id_ask,
                )

            return {
                "intent": intent,
                "doubt_block_id": str(active_block["doubt_block_id"]),
                **hint_result,
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("get_hint failed for continuation: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ── 5. New physics doubt ──────────────────────────────────────────────────
    # Close any existing active block first (if there was one but classified as new doubt)
    if active_block and body.study_session_id:
        await _close_doubt_block(
            pool, engine, str(active_block["doubt_block_id"]), solved=False,
        )

    # Build memory context bundle for this student (never blocks on failure)
    try:
        bundle = await build_context_bundle(current_student_id, pool)
        student_context = format_context_for_prompt(bundle)
    except Exception as exc:
        logger.warning("build_context_bundle failed (non-fatal): %s", exc)
        student_context = ""

    try:
        result = await engine.start_session(
            question=question,
            student_id=current_student_id,
            subject=body.subject,
            study_session_id=body.study_session_id,
            locked_topic=body.topic_lock,
            student_context=student_context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SocraticEngine.start_session failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Create doubt block if within a study session
    doubt_block_id = None
    if body.study_session_id:
        topic = result.get("analysis", {}).get("topic", "Physics")
        doubt_block_id = await _create_doubt_block(
            pool,
            body.study_session_id,
            current_student_id,
            uuid.UUID(result["session_id"]),
            topic,
            student_confidence=body.student_confidence,
        )

    # Get current doubt count
    doubt_count = 0
    if body.study_session_id:
        count_row = await pool.fetchrow(
            "SELECT doubt_count FROM study_sessions WHERE study_session_id = $1",
            uuid.UUID(body.study_session_id),
        )
        if count_row:
            doubt_count = count_row["doubt_count"] or 0

    return {
        "intent": "physics_doubt",
        "doubt_block_id": doubt_block_id,
        "doubt_block_topic": result.get("analysis", {}).get("topic", "Physics"),
        "doubt_block_number": doubt_count,
        **result,
    }


@router.post("/hint")
async def get_hint(
    body: HintRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    _: str = Depends(get_current_student_id),
):
    """
    Request the next progressive hint for an existing doubt session.

    Hint level escalation:
        1 → gentle conceptual nudge
        2 → structural / approach hint
        3 → FORCED ATTEMPT — zero teaching; demands student's final written answer
        4+ → full solution, session marked resolved

    jump_to_full_solution is only honoured if current_hint_level >= 3.
    """
    engine = request.app.state.socratic_engine
    pool = request.app.state.db_pool

    try:
        result = await engine.get_hint(
            session_id=body.session_id,
            student_response=body.student_response,
            jump_to_full=body.jump_to_full_solution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SocraticEngine.get_hint failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # If within a study session, update the doubt block
    if body.study_session_id:
        block = await _get_active_doubt_block(pool, body.study_session_id)
        if block:
            _mc_id_hint = result.get("misconception_id")
            await pool.execute(
                """
                UPDATE doubt_blocks
                SET hint_level             = $1,
                    misconception_detected = CASE WHEN $3::varchar IS NOT NULL THEN TRUE ELSE misconception_detected END,
                    misconception_id       = COALESCE($3::varchar, misconception_id)
                WHERE doubt_block_id = $2
                """,
                result.get("hint_level", block["hint_level"]),
                block["doubt_block_id"],
                _mc_id_hint,
            )
            if result.get("resolved"):
                await _close_doubt_block(
                    pool, engine, str(block["doubt_block_id"]), solved=True,
                )
                # Genome update fires asynchronously after the response is sent
                background_tasks.add_task(
                    _genome_update_task,
                    pool,
                    body.session_id,
                    body.give_up_flag,
                    body.mistake_tag,
                    misconception_id=block.get("misconception_id") or _mc_id_hint,
                )
            result["doubt_block_id"] = str(block["doubt_block_id"])

    return result


@router.post("/ask/stream")
async def ask_doubt_stream(
    body: AskRequest,
    request: Request,
    current_student_id: str = Depends(get_current_student_id),
):
    """
    Streaming variant of POST /doubt/ask.

    Returns text/event-stream (SSE). Each event is a JSON line:
        data: {"token": "...", "done": false}\\n\\n
        data: {"token": "", "done": true, "session_id": "...", ...}\\n\\n
        data: {"error": "...", "done": true}\\n\\n

    Only new physics_doubt sessions are streamed.
    Continuation + non-physics intents fall back to a single non-streamed event.
    Hint levels 1+ are NOT supported via this endpoint — use /doubt/hint as normal.
    """
    engine = request.app.state.socratic_engine
    pool   = request.app.state.db_pool

    # ── Vision AI ─────────────────────────────────────────────────────────────
    question = body.question
    if not question and body.image_url:
        try:
            question = await engine.extract_question_from_image(body.image_url)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Vision AI failed: {exc}") from exc

    # ── Check active block / classify intent ──────────────────────────────────
    active_block = None
    if body.study_session_id:
        active_block = await _get_active_doubt_block(pool, body.study_session_id)
    has_active_block = active_block is not None and not active_block.get("solved", False)

    if has_active_block and active_block.get("hint_level", 0) >= 3:
        intent = "continuation"
    elif body.topic_lock:
        intent = "physics_doubt"
    else:
        intent = await engine.classify_intent(question, has_active_block)

    # ── Non-streaming path: non-physics / continuation ─────────────────────
    # These are cheap (no LLM or fast LLM) — return as a single SSE event.
    async def _single_event(payload: dict):
        data = _json.dumps({"token": "", "done": True, **payload})
        yield f"data: {data}\n\n"

    if intent in ("greeting", "meta", "emotional", "out_of_scope"):
        result = await engine.handle_non_physics_intent(intent, question)
        return StreamingResponse(
            _single_event({"response": result["response"], "intent": intent, "session_id": None}),
            media_type="text/event-stream",
        )

    if intent == "recap":
        if body.study_session_id:
            rows = await pool.fetch(
                """
                SELECT topic, summary, solved, started_at
                FROM doubt_blocks
                WHERE study_session_id = $1
                ORDER BY started_at ASC
                """,
                uuid.UUID(body.study_session_id),
            )
            completed = [r for r in rows if r["summary"]]
            if completed:
                lines = ["Here's what we've covered in this session:\n"]
                for i, row in enumerate(completed, 1):
                    topic = row["topic"] or "Physics question"
                    solved_label = "✓ Solved" if row["solved"] else "⟳ In progress"
                    lines.append(f"**{i}. {topic}** — {solved_label}\n{row['summary']}")
                response = "\n\n".join(lines)
            elif rows:
                topics = [r["topic"] or "Physics question" for r in rows]
                response = (
                    f"We're currently working through: {', '.join(f'**{t}**' for t in topics)}. "
                    "Summaries are generated once a question is resolved — keep going! 💪"
                )
            else:
                response = (
                    "We haven't covered any topics yet in this session. "
                    "Ask me a Physics question to get started!"
                )
        else:
            response = (
                "I don't have a record of this session. "
                "Start a new session and I'll track everything you cover!"
            )
        return StreamingResponse(
            _single_event({"intent": "recap", "response": response, "session_id": None}),
            media_type="text/event-stream",
        )

    if intent == "continuation" and active_block:
        # Capture for closure
        _active_block   = active_block
        _question       = question
        _student_conf   = body.student_confidence
        _doubt_sess_id  = str(active_block["doubt_session_id"])
        _doubt_block_id = str(active_block["doubt_block_id"])

        async def _continuation_stream():
            # ── Send keepalive immediately so Render's proxy doesn't cut the
            # connection while engine.get_hint() (2-3 LLM calls) is running.
            yield f"data: {_json.dumps({'token': '', 'done': False, 'thinking': True})}\n\n"

            try:
                hint_result = await engine.get_hint(
                    session_id=_doubt_sess_id,
                    student_response=_question,
                )
                _mc_id = hint_result.get("misconception_id")
                await pool.execute(
                    """
                    UPDATE doubt_blocks
                    SET hint_level             = $1,
                        student_confidence     = COALESCE($3, student_confidence),
                        misconception_detected = CASE WHEN $4 IS NOT NULL THEN TRUE ELSE misconception_detected END,
                        misconception_id       = COALESCE($4, misconception_id)
                    WHERE doubt_block_id = $2
                    """,
                    hint_result.get("hint_level", _active_block["hint_level"]),
                    _active_block["doubt_block_id"],
                    _student_conf,
                    _mc_id,
                )
                if hint_result.get("resolved"):
                    await _close_doubt_block(pool, engine, _doubt_block_id, solved=True)
                    asyncio.create_task(_genome_update_task(
                        pool,
                        _doubt_sess_id,
                        give_up_flag=False,
                        mistake_tag=None,
                        student_confidence=_student_conf,
                        misconception_id=_active_block.get("misconception_id") or _mc_id,
                    ))
                payload = {
                    "intent":         "continuation",
                    "session_id":     _doubt_sess_id,   # explicit — don't rely on hint_result
                    "doubt_block_id": _doubt_block_id,
                    **hint_result,
                }
                yield f"data: {_json.dumps({'token': '', 'done': True, **payload})}\n\n"
            except ValueError as exc:
                yield f"data: {_json.dumps({'error': str(exc), 'done': True})}\n\n"
            except Exception as exc:
                logger.exception("_continuation_stream failed: %s", exc)
                yield f"data: {_json.dumps({'error': str(exc), 'done': True})}\n\n"

        return StreamingResponse(_continuation_stream(), media_type="text/event-stream")

    # ── Close any existing block + build memory context ───────────────────────
    if active_block and body.study_session_id:
        await _close_doubt_block(pool, engine, str(active_block["doubt_block_id"]), solved=False)

    try:
        bundle = await build_context_bundle(current_student_id, pool)
        student_context = format_context_for_prompt(bundle)
    except Exception:
        student_context = ""

    # ── Streaming generator ───────────────────────────────────────────────────
    async def event_stream():
        try:
            session_id        = None
            doubt_block_id    = None
            final_metadata    = {}

            async for chunk in engine.start_session_stream(
                question=question,
                student_id=current_student_id,
                subject=body.subject,
                study_session_id=body.study_session_id,
                locked_topic=body.topic_lock,
                student_context=student_context,
            ):
                if chunk.get("error"):
                    yield f"data: {_json.dumps({'error': chunk['error'], 'done': True})}\n\n"
                    return

                if chunk.get("done"):
                    # Persist doubt block then emit final event
                    session_id = chunk.get("session_id")
                    analysis   = chunk.get("analysis", {})
                    if body.study_session_id and session_id:
                        topic = analysis.get("topic", "Physics")
                        doubt_block_id = await _create_doubt_block(
                            pool,
                            body.study_session_id,
                            current_student_id,
                            uuid.UUID(session_id),
                            topic,
                            student_confidence=body.student_confidence,
                        )
                    final_metadata = {
                        "intent":           "physics_doubt",
                        "doubt_block_id":   doubt_block_id,
                        "doubt_block_topic": chunk.get("analysis", {}).get("topic", "Physics"),
                        "session_id":       session_id,
                        "mentor_mode":      chunk.get("mentor_mode"),
                        "out_of_scope":     chunk.get("out_of_scope", False),
                        "cache_hit":        chunk.get("cache_hit", False),
                    }
                    yield f"data: {_json.dumps({'token': '', 'done': True, **final_metadata})}\n\n"
                else:
                    yield f"data: {_json.dumps({'token': chunk.get('token', ''), 'done': False})}\n\n"

        except Exception as exc:
            logger.exception("ask_doubt_stream: event_stream failed: %s", exc)
            yield f"data: {_json.dumps({'error': str(exc), 'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/verify")
async def verify_solution(
    body: VerifyRequest,
    request: Request,
    _: str = Depends(get_current_student_id),
):
    """
    Run the two-layer verification pipeline on an arbitrary question + solution.
    """
    verifier = request.app.state.verifier
    try:
        result = await verifier.verify(
            question=body.question,
            solution=body.solution,
            context=body.context,
        )
    except Exception as exc:
        logger.exception("VerificationPipeline.verify failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result
