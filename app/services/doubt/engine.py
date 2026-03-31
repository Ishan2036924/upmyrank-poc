"""
Socratic doubt-resolution engine — powered by OpenAI GPT-4o-mini.

Flow for every start_session() call:
  1. Get rich student context (mastery, weak areas, error history)
  2. Detect appropriate mentor mode (COACH / TASKMASTER / COUNSELOR / STRATEGIST)
  3. Analyze the problem with GPT-4o-mini using student context (JSON, temp=0.1)
  4. Retrieve relevant NCERT chunks from pgvector
  5. Scope check against DB topics + physics keywords
  6. Generate personalised Socratic question (temp=0.7)
  7. Persist the doubt_session + first conversation turn in Postgres
  8. Log a session_event

For get_hint() (level > 3 = full solution):
  9. Analyze student's response for misconceptions / emotional state
  10. Select & render the appropriate prompt with full conversation history
  11. Run VerificationPipeline on the generated solution
  12. Attach verification result to the response
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import uuid
from typing import TYPE_CHECKING, Dict, List, Literal, Optional

import asyncpg
import openai

from app.config import settings
from app.services.doubt.context import get_rag_context, get_student_mastery_str
from app.services.doubt.prompts import (
    DOUBT_BLOCK_SUMMARIZER_PROMPT,
    EMOTIONAL_RESPONSE_PROMPT,
    FULL_SOLUTION_PROMPT,
    GREETING_RESPONSES,
    HINT_LEVEL_1_PROMPT,
    HINT_LEVEL_2_PROMPT,
    HINT_LEVEL_3_PROMPT,
    INTENT_CLASSIFIER_PROMPT,
    INTENT_CLASSIFIER_SYSTEM,
    META_RESPONSE,
    OUT_OF_SCOPE_RESPONSE,
    PROBLEM_ANALYSIS_PROMPT,
    SOCRATIC_QUESTION_PROMPT,
    STUDENT_RESPONSE_ANALYSIS_PROMPT,
    SYSTEM_PROMPT_FORCED_ATTEMPT,
    TUTOR_SYSTEM_PROMPT,
)
from app.services.mastery import update_concept_mastery
from app.services.rag.retriever import Retriever

if TYPE_CHECKING:
    from app.services.verify.pipeline import VerificationPipeline

logger = logging.getLogger(__name__)

# ── model tier routing ────────────────────────────────────────────────────────

ModelTier = Literal["cheap", "quality"]


def _get_model(tier: ModelTier) -> str:
    """Return the configured model name for the given tier."""
    return settings.model_cheap if tier == "cheap" else settings.model_quality


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_json_response(raw: str) -> dict:
    """
    Robustly parse a JSON dict from an LLM response.
    Handles optional markdown code-fences (```json … ```) that the model
    might emit despite being told not to.
    """
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
        text = "\n".join(inner).strip()

    # First try: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Second try: find the first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())

    raise ValueError(f"Could not parse JSON from LLM response:\n{raw[:300]}")


# ── main engine ───────────────────────────────────────────────────────────────

class SocraticEngine:
    """
    Orchestrates the full Socratic tutoring pipeline.

    Injected dependencies:
        openai_client  – openai.AsyncOpenAI instance
        retriever      – app.services.rag.retriever.Retriever instance
        db_pool        – asyncpg.Pool
        verifier       – VerificationPipeline (optional; skipped if None)
    """

    def __init__(
        self,
        openai_client: openai.AsyncOpenAI,
        retriever: Retriever,
        db_pool: asyncpg.Pool,
        verifier: Optional["VerificationPipeline"] = None,
    ) -> None:
        self._client = openai_client
        self._retriever = retriever
        self._pool = db_pool
        self._verifier = verifier

    # ── public API ────────────────────────────────────────────────────────────

    async def start_session(
        self,
        question: str,
        student_id: str,
        subject: str = "Physics",
        study_session_id: Optional[str] = None,
        locked_topic: Optional[str] = None,
    ) -> dict:
        """
        Start a new doubt-resolution session and return the Socratic response.

        Returns a dict with:
            session_id, analysis, response, mentor_mode,
            concepts_involved, retrieved_context_count, out_of_scope
        """
        # ── 0. Validate student ───────────────────────────────────────────────
        try:
            student_uuid = uuid.UUID(student_id)
        except ValueError as exc:
            raise ValueError(f"Invalid student ID format: {student_id}") from exc

        student_row = await self._pool.fetchrow(
            "SELECT id FROM students WHERE id = $1", student_uuid
        )
        if student_row is None:
            raise ValueError(f"Student not found: {student_id}")

        # ── 1. Get rich student context ───────────────────────────────────────
        logger.info("Loading student context for %s …", student_id)
        student_ctx = await self._get_student_context(student_id)
        mentor_mode = self._detect_mentor_mode(student_ctx)

        # ── 2. Problem analysis with student context ──────────────────────────
        if locked_topic:
            # Syllabus-pinned session — skip LLM classification entirely and use
            # the exact topic supplied by the student's syllabus selection.
            logger.info("Skipping LLM analysis — topic locked to %r", locked_topic)
            analysis = {
                "subject": subject,
                "topic": locked_topic,
                "subtopic": locked_topic,
                "concepts_required": [],
                "difficulty": 5,
                "problem_type": "conceptual",
                "key_insight": "",
                "common_misconceptions": [],
                "brief_analysis": question,
            }
        else:
            logger.info("Analyzing problem …")
            analysis_raw = await self._call_llm(
                PROBLEM_ANALYSIS_PROMPT.format(
                    question=question,
                    overall_mastery=student_ctx["overall_mastery"],
                    concept_mastery_details=student_ctx["weak_areas"],
                    recent_errors=student_ctx["recent_errors"],
                    session_count=student_ctx["session_count"],
                ),
                max_tokens=600,
                temperature=0.1,
                model_tier="cheap",
            )
            try:
                analysis = _parse_json_response(analysis_raw)
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning("JSON parse failed; using fallback analysis. Error: %s", exc)
                analysis = {
                    "subject": subject,
                    "topic": "Physics",
                    "subtopic": "General",
                    "concepts_required": [],
                    "difficulty": 5,
                    "problem_type": "conceptual",
                    "key_insight": "",
                    "common_misconceptions": [],
                    "brief_analysis": question,
                }

        # Store mentor_mode in analysis so get_hint() can retrieve it later
        analysis["mentor_mode"] = mentor_mode

        # ── 3+4. RAG: top-3 NCERT chunks + 1 similar problem; concept IDs ───────
        logger.info("Retrieving RAG context and concept IDs …")
        analysis_topic = analysis.get("topic", "")
        rag, concept_ids = await asyncio.gather(
            get_rag_context(self._retriever, question, subject, analysis_topic),
            self._retriever.get_related_concepts(question),
        )

        # ── 5. Scope check (DB-driven + keyword fallback) ─────────────────────
        out_of_scope = not await self._is_in_scope(question=question, analysis=analysis)
        analysis["out_of_scope"] = out_of_scope

        # ── 6. Targeted genome injection: per-topic mastery string ────────────
        genome_injection = await get_student_mastery_str(
            self._pool, student_id, analysis_topic,
        )

        # ── 7. Fetch session memory (if within a study session) ────────────────
        session_memory = "(no prior context in this session)"
        if study_session_id:
            session_memory = await self.get_session_memory(study_session_id)

        # ── 8. Generate personalised Socratic response ────────────────────────
        logger.info("Generating Socratic response (mentor=%s) …", mentor_mode)
        socratic_response = await self._call_llm(
            SOCRATIC_QUESTION_PROMPT.format(
                student_name=student_ctx["student_name"],
                overall_mastery=student_ctx["overall_mastery"],
                genome_injection=genome_injection,
                weak_areas=student_ctx["weak_areas"],
                recent_errors=student_ctx["recent_errors"],
                session_count=student_ctx["session_count"],
                mentor_mode=mentor_mode,
                question=question,
                analysis=json.dumps(analysis, indent=2),
                context=rag["context_text"],
                session_memory=session_memory,
            ),
            max_tokens=1024,
            temperature=0.7,
            system_prompt=TUTOR_SYSTEM_PROMPT,
        )

        if out_of_scope:
            socratic_response = (
                "⚠️ This question appears to be outside the Physics syllabus "
                "(NCERT Class 11 & 12). I'll do my best to help, but for detailed "
                "study, refer to the relevant chapter.\n\n" + socratic_response
            )

        # ── 9. Persist doubt_session ──────────────────────────────────────────
        session_id = await self._create_session(
            student_id=student_id,
            question=question,
            subject=subject,
            analysis=analysis,
            socratic_response=socratic_response,
            concept_ids=concept_ids,
        )

        # ── 10. Log session event ─────────────────────────────────────────────
        await self._log_event(
            session_id=session_id,
            event_type="question_asked",
            payload={
                "question": question,
                "concept_ids": concept_ids,
                "mentor_mode": mentor_mode,
            },
        )

        logger.info("Session %s created for student %s (mentor=%s)",
                    session_id, student_id, mentor_mode)
        return {
            "session_id": str(session_id),
            "analysis": analysis,
            "response": socratic_response,
            "mentor_mode": mentor_mode,
            "concepts_involved": concept_ids,
            "retrieved_context_count": rag["chunk_count"],
            "out_of_scope": out_of_scope,
        }

    async def get_hint(
        self,
        session_id: str,
        student_response: Optional[str] = None,
        jump_to_full: bool = False,
    ) -> dict:
        """
        Return the next progressive hint for an existing doubt session.

        Hint levels:
            1 → gentle conceptual nudge
            2 → structural / approach hint
            3 → FORCED ATTEMPT — zero teaching; LLM demands student's final written answer
            4+ → full solution, session marked resolved

        Returns a dict with:
            session_id, hint_level, hint, response (alias), is_full_solution,
            resolved, verification, mentor_mode
        """
        # ── 1. Load session (including stored analysis) ───────────────────────
        row = await self._pool.fetchrow(
            """
            SELECT id, problem_text, subject, current_hint_level,
                   conversation_history, student_id, concepts_involved, analysis
            FROM doubt_sessions
            WHERE id = $1
            """,
            uuid.UUID(session_id),
        )
        if row is None:
            raise ValueError(f"Session {session_id} not found.")

        problem_text: str = row["problem_text"]
        current_level: int = row["current_hint_level"]
        history: list = json.loads(row["conversation_history"]) \
            if isinstance(row["conversation_history"], str) \
            else (row["conversation_history"] or [])
        subject: str = row["subject"] or "Physics"
        session_student_id: uuid.UUID = row["student_id"]
        session_concept_ids: List[str] = list(row["concepts_involved"] or [])

        # Parse stored analysis (contains mentor_mode and topic etc.)
        try:
            stored_analysis: dict = json.loads(row["analysis"]) \
                if isinstance(row["analysis"], str) \
                else (dict(row["analysis"]) if row["analysis"] else {})
        except Exception:
            stored_analysis = {}

        mentor_mode: str = stored_analysis.get("mentor_mode", "COACH")

        # ── 2. Analyze student response before appending to history ───────────
        # Skip response analysis at the forced-attempt stage (current_level >= 3).
        # At this point ANY response should unlock the full solution — spending
        # an LLM call to detect "frustrated" would route to counselor mode and
        # block the full solution (the "therapist hijack" bug).
        response_analysis: dict = {}
        if student_response and student_response.strip() and current_level < 3:
            try:
                response_analysis = await self._analyze_student_response(
                    question=problem_text,
                    analysis=stored_analysis,
                    conversation_history=history,
                    student_response=student_response,
                )
                # Adapt mentor mode if student seems frustrated
                if response_analysis.get("emotional_state") == "frustrated":
                    logger.info("Student seems frustrated — switching to COUNSELOR mode.")
                    mentor_mode = "COUNSELOR"
                    stored_analysis["mentor_mode"] = "COUNSELOR"
            except Exception as exc:
                logger.warning("Response analysis failed (non-fatal): %s", exc)

        # ── 3. Append student response to history ─────────────────────────────
        if student_response and student_response.strip():
            history.append({"role": "student", "content": student_response})

        # ── 4. Determine new hint level ───────────────────────────────────────
        # Progressive disclosure gate: jump_to_full is ONLY honoured if the
        # student has already reached hint level 3 (forced attempt).  If they
        # try to skip early, we silently override the flag and route them to
        # the next normal hint instead, with a "nice try" message injected.
        nice_try_intercepted: bool = False
        if jump_to_full and current_level < 3:
            logger.info(
                "jump_to_full blocked: current_level=%d < 3, overriding to next hint",
                current_level,
            )
            jump_to_full = False
            nice_try_intercepted = True

        if jump_to_full:
            new_level = max(current_level + 1, 4)
        else:
            new_level = current_level + 1
        is_full_solution: bool = new_level > 3

        # ── 4b. FORCED ATTEMPT GATE ───────────────────────────────────────────
        # After 3 hints have been delivered (current_level >= 3), the student
        # MUST type a response before seeing the full solution. If they click
        # "Get hint" without submitting any text, bounce back with the gate
        # message instead of advancing to the full solution.
        if current_level >= 3 and not jump_to_full and not (student_response and student_response.strip()):
            gate_msg = (
                "You've received the maximum 3 hints. "
                "Please type out your final answer and working — "
                "I'll give you complete feedback and then walk through the full solution with you."
            )
            return {
                "session_id": session_id,
                "hint_level": current_level,
                "hint": gate_msg,
                "response": gate_msg,
                "is_full_solution": False,
                "is_forced_attempt": True,
                "resolved": False,
                "verification": None,
                "mentor_mode": mentor_mode,
                "response_analysis": {},
            }

        # ── 5+6. RAG context + targeted genome injection (concurrent) ────────────
        # Nuclear override: hint level 3 (Forced Attempt) receives NO RAG context
        # and NO analysis. Starving the LLM of this material makes solution leakage
        # structurally impossible — it cannot teach what it has not been given.
        if new_level == 3:
            rag = {"context_text": "", "chunks": [], "chunk_count": 0}
            genome_injection = ""
        else:
            analysis_topic = stored_analysis.get("topic", "")
            rag, genome_injection = await asyncio.gather(
                get_rag_context(self._retriever, problem_text, subject, analysis_topic),
                get_student_mastery_str(self._pool, str(session_student_id), analysis_topic),
            )

        # ── 7. Format conversation and student response for prompts ───────────
        conversation_text = self._format_conversation(history)
        student_response_text = (student_response or "").strip() or "(no response provided)"
        analysis_json = json.dumps(stored_analysis, indent=2)

        # ── 8. Select & render the appropriate prompt ─────────────────────────
        if new_level == 1:
            prompt = HINT_LEVEL_1_PROMPT.format(
                conversation_history=conversation_text,
                student_response=student_response_text,
                analysis=analysis_json,
                context=rag["context_text"],
                genome_injection=genome_injection,
            )
        elif new_level == 2:
            prompt = HINT_LEVEL_2_PROMPT.format(
                conversation_history=conversation_text,
                student_response=student_response_text,
                analysis=analysis_json,
                context=rag["context_text"],
            )
        elif new_level == 3:
            # Nuclear option: isolated prompt with no analysis or RAG context.
            # System prompt is also swapped to SYSTEM_PROMPT_FORCED_ATTEMPT,
            # removing the helpful-tutor persona entirely for this call.
            prompt = HINT_LEVEL_3_PROMPT.format(
                conversation_history=conversation_text,
                student_response=student_response_text,
            )
        else:
            prompt = FULL_SOLUTION_PROMPT.format(
                conversation_history=conversation_text,
                question=problem_text,
                analysis=analysis_json,
                context=rag["context_text"],
            )

        # ── 9. Generate hint via LLM ──────────────────────────────────────────
        # Hint level 3 uses SYSTEM_PROMPT_FORCED_ATTEMPT (stripped proctor persona)
        # instead of TUTOR_SYSTEM_PROMPT to prevent persona override.
        active_system_prompt = SYSTEM_PROMPT_FORCED_ATTEMPT if new_level == 3 else TUTOR_SYSTEM_PROMPT
        logger.info(
            "Generating hint level %d for session %s (full=%s, mentor=%s, system=%s)",
            new_level, session_id, is_full_solution, mentor_mode,
            "FORCED_ATTEMPT" if new_level == 3 else "TUTOR",
        )
        hint_response = await self._call_llm(
            prompt,
            max_tokens=256 if new_level == 3 else (2048 if is_full_solution else 1024),
            temperature=0.3 if new_level == 3 else 0.5,
            system_prompt=active_system_prompt,
        )

        # ── 9b. "Nice Try" prefix — intercepted early jump_to_full ────────────
        if nice_try_intercepted:
            hint_response = (
                "Nice try, but I'm not going to just give you the answer! "
                "Let's work through this step-by-step.\n\n" + hint_response
            )

        # ── 9c. LaTeX post-processing sanitizer ───────────────────────────────
        hint_response = self._sanitize_latex(hint_response)

        # ── 10. Verify full solution ───────────────────────────────────────────
        verification_result: Optional[dict] = None
        if is_full_solution and self._verifier is not None:
            try:
                verification_result = await self._verifier.verify(
                    question=problem_text,
                    solution=hint_response,
                    context=rag["context_text"],
                )
                logger.info(
                    "Solution verified for %s: verified=%s confidence=%.2f method=%s",
                    session_id,
                    verification_result.get("verified"),
                    verification_result.get("confidence", 0),
                    verification_result.get("method"),
                )
                if verification_result.get("flagged_for_review"):
                    hint_response += (
                        "\n\n⚠️ *This solution has been automatically flagged "
                        "for review — please double-check the working above.*"
                    )
            except Exception as exc:
                logger.warning("Verification failed (non-fatal): %s", exc)

        # ── 11. (Mastery update removed) ──────────────────────────────────────
        # Mastery is updated by _genome_update_task in doubt.py when the doubt
        # block closes. Updating here too caused a double EMA application with
        # conflicting performance scores, corrupting the student's mastery score.

        # ── 12. Update conversation history ───────────────────────────────────
        history.append({"role": "tutor", "content": hint_response})
        resolved: bool = is_full_solution

        # ── 13. Persist updated session ───────────────────────────────────────
        await self._pool.execute(
            """
            UPDATE doubt_sessions
            SET current_hint_level   = $1,
                conversation_history = $2::jsonb,
                resolved             = $3,
                resolved_at          = CASE WHEN $3 THEN NOW() ELSE NULL END,
                analysis             = $5::jsonb
            WHERE id = $4
            """,
            new_level,
            json.dumps(history),
            resolved,
            uuid.UUID(session_id),
            json.dumps(stored_analysis),
        )

        # ── 14. Log event ─────────────────────────────────────────────────────
        event_type = "solution_revealed" if is_full_solution else "hint_requested"
        await self._log_event(
            session_id=uuid.UUID(session_id),
            event_type=event_type,
            payload={
                "hint_level": new_level,
                "is_full_solution": is_full_solution,
                "mentor_mode": mentor_mode,
                "response_analysis": response_analysis,
                "verification": verification_result,
            },
        )

        logger.info("Hint level %d delivered for session %s", new_level, session_id)
        return {
            "session_id": session_id,
            "hint_level": new_level,
            "hint": hint_response,          # explicit alias
            "response": hint_response,      # backward-compat
            "is_full_solution": is_full_solution,
            "is_forced_attempt": (new_level == 3 and not jump_to_full),
            "resolved": resolved,
            "verification": verification_result,
            "mentor_mode": mentor_mode,
            "response_analysis": response_analysis,
        }

    # ── intent classification ────────────────────────────────────────────────

    async def classify_intent(
        self,
        message: str,
        has_active_block: bool = False,
    ) -> str:
        """Classify a student message into one of 7 intents.

        Returns one of: greeting, meta, emotional, out_of_scope,
        recap, physics_doubt, continuation.
        """
        _VALID_INTENTS = {
            "greeting", "meta", "emotional",
            "out_of_scope", "physics_doubt", "continuation", "recap",
        }

        prompt = INTENT_CLASSIFIER_PROMPT.format(
            has_active_block=str(has_active_block).lower(),
            message=message,
        )
        raw = await self._call_llm(
            prompt,
            max_tokens=20,
            temperature=0.0,
            system_prompt=INTENT_CLASSIFIER_SYSTEM,
            model_tier="cheap",
        )
        intent = raw.strip().lower().replace('"', "").replace("'", "")

        if intent in _VALID_INTENTS:
            return intent

        # Fallback: if there's an active block, treat as continuation;
        # otherwise treat as a new physics doubt.
        logger.warning("Classifier returned unknown intent '%s'; falling back", raw.strip())
        return "continuation" if has_active_block else "physics_doubt"

    async def handle_non_physics_intent(
        self,
        intent: str,
        message: str,
    ) -> dict:
        """Handle greeting / meta / emotional / out_of_scope intents.

        Returns {intent, response, session_id: None}. NO DB writes.
        """
        if intent == "greeting":
            response = random.choice(GREETING_RESPONSES)
        elif intent == "meta":
            response = META_RESPONSE
        elif intent == "emotional":
            response = await self._call_llm(
                EMOTIONAL_RESPONSE_PROMPT.format(message=message),
                max_tokens=200,
                temperature=0.7,
                model_tier="cheap",
            )
        elif intent == "out_of_scope":
            response = OUT_OF_SCOPE_RESPONSE
        else:
            response = "I'm here to help with Physics! Ask me anything from NCERT Class 11 or 12."

        return {"intent": intent, "response": response, "session_id": None}

    # ── session memory ─────────────────────────────────────────────────────────

    async def get_session_memory(self, study_session_id: str) -> str:
        """Fetch summaries of the last 3 completed doubt blocks in a study session.

        Returns a formatted string for injection into the Socratic prompt.
        """
        try:
            rows = await self._pool.fetch(
                """
                SELECT topic, summary
                FROM doubt_blocks
                WHERE study_session_id = $1
                  AND summary IS NOT NULL
                  AND ended_at IS NOT NULL
                ORDER BY ended_at DESC
                LIMIT 3
                """,
                uuid.UUID(study_session_id),
            )
        except Exception as exc:
            logger.warning("Could not fetch session memory: %s", exc)
            return "(no prior context in this session)"

        if not rows:
            return "(no prior context in this session)"

        lines = []
        for r in reversed(rows):  # chronological order
            topic = r["topic"] or "Unknown topic"
            summary = r["summary"] or "No summary"
            lines.append(f"• {topic}: {summary}")

        return "Earlier in this session:\n" + "\n".join(lines)

    async def summarize_doubt_block(self, doubt_block_id: str) -> Optional[str]:
        """Generate and store a 1-2 line summary for a completed doubt block."""
        try:
            block = await self._pool.fetchrow(
                """
                SELECT db.doubt_session_id
                FROM doubt_blocks db
                WHERE db.doubt_block_id = $1
                """,
                uuid.UUID(doubt_block_id),
            )
            if not block or not block["doubt_session_id"]:
                return None

            session = await self._pool.fetchrow(
                "SELECT conversation_history FROM doubt_sessions WHERE id = $1",
                block["doubt_session_id"],
            )
            if not session or not session["conversation_history"]:
                return None

            history = json.loads(session["conversation_history"]) \
                if isinstance(session["conversation_history"], str) \
                else session["conversation_history"]

            conversation_text = self._format_conversation(history)
            summary = await self._call_llm(
                DOUBT_BLOCK_SUMMARIZER_PROMPT.format(conversation=conversation_text),
                max_tokens=100,
                temperature=0.3,
                model_tier="cheap",
            )

            await self._pool.execute(
                "UPDATE doubt_blocks SET summary = $1 WHERE doubt_block_id = $2",
                summary.strip(),
                uuid.UUID(doubt_block_id),
            )
            return summary.strip()
        except Exception as exc:
            logger.error("Doubt block summarization failed (summary will be NULL, recap broken): %s", exc)
            return None

    # ── private helpers ───────────────────────────────────────────────────────

    async def _get_student_context(self, student_id: str) -> dict:
        """Get comprehensive student context for personalised responses."""
        try:
            student_uuid = uuid.UUID(student_id)
        except ValueError:
            return self._default_student_context()

        try:
            student = await self._pool.fetchrow(
                "SELECT * FROM students WHERE id = $1", student_uuid
            )

            mastery_rows = await self._pool.fetch(
                """
                SELECT cm.concept_id, cm.mastery_score, cm.error_count,
                       cm.attempt_count, c.topic, c.subtopic
                FROM   concept_mastery cm
                JOIN   concepts c ON cm.concept_id = c.id
                WHERE  cm.student_id = $1
                ORDER  BY cm.mastery_score ASC
                """,
                student_uuid,
            )

            recent_sessions = await self._pool.fetch(
                """
                SELECT topic, difficulty, current_hint_level, resolved,
                       concepts_involved, created_at
                FROM   doubt_sessions
                WHERE  student_id = $1
                ORDER  BY created_at DESC
                LIMIT  5
                """,
                student_uuid,
            )

            mastery_list = [float(r["mastery_score"]) for r in mastery_rows]
            overall = sum(mastery_list) / len(mastery_list) if mastery_list else 0.0

            weak_concepts = [
                f"{r['subtopic']} ({int(float(r['mastery_score']) * 100)}%)"
                for r in mastery_rows[:5]
            ]
            error_concepts = [
                f"{r['subtopic']} ({r['error_count']} errors)"
                for r in mastery_rows
                if r["error_count"] and r["error_count"] > 0
            ][:5]

            # Build topic → average mastery map
            topic_bucket: Dict[str, list] = {}
            for r in mastery_rows:
                t = r["topic"] or "Unknown"
                topic_bucket.setdefault(t, []).append(float(r["mastery_score"]))
            topic_avg = {t: sum(v) / len(v) for t, v in topic_bucket.items()}

            return {
                "student_name": (student["name"] if student and student["name"] else "Student"),
                "overall_mastery": int(overall * 100),
                "weak_areas": (", ".join(weak_concepts) if weak_concepts else "None identified yet"),
                "recent_errors": (", ".join(error_concepts) if error_concepts else "No recent errors"),
                "session_count": len(recent_sessions),
                "mastery_rows": list(mastery_rows),
                "topic_avg": topic_avg,
            }
        except Exception as exc:
            logger.warning("Could not load student context: %s", exc)
            return self._default_student_context()

    @staticmethod
    def _default_student_context() -> dict:
        return {
            "student_name": "Student",
            "overall_mastery": 50,
            "weak_areas": "None identified yet",
            "recent_errors": "No recent errors",
            "session_count": 0,
            "mastery_rows": [],
            "topic_avg": {},
        }

    @staticmethod
    def _detect_mentor_mode(student_context: dict) -> str:
        """Detect appropriate mentor mode based on student profile."""
        mastery = student_context.get("overall_mastery", 50)
        sessions = student_context.get("session_count", 0)

        if mastery < 25:
            return "COUNSELOR"      # struggling — be gentle
        if sessions == 0:
            return "COACH"          # new student — be welcoming
        if mastery > 60 and sessions > 5:
            return "STRATEGIST"     # advanced — be efficient
        return "COACH"              # default — be encouraging

    @staticmethod
    def _topic_mastery_pct(student_context: dict, topic: str) -> int:
        """Return mastery % for a given topic (fuzzy match). Falls back to overall."""
        topic_avg = student_context.get("topic_avg", {})
        overall = student_context.get("overall_mastery", 50)
        topic_lower = topic.lower()

        for db_topic, avg in topic_avg.items():
            db_lower = db_topic.lower()
            if topic_lower in db_lower or db_lower in topic_lower:
                return int(avg * 100)

        return overall

    async def _analyze_student_response(
        self,
        question: str,
        analysis: dict,
        conversation_history: list,
        student_response: str,
    ) -> dict:
        """Analyze the student's response to personalize the next hint."""
        prompt = STUDENT_RESPONSE_ANALYSIS_PROMPT.format(
            question=question,
            analysis=json.dumps(analysis),
            conversation_history=self._format_conversation(conversation_history),
            student_response=student_response,
        )
        raw = await self._call_llm(prompt, max_tokens=300, temperature=0.1, model_tier="cheap")
        try:
            return _parse_json_response(raw)
        except Exception as exc:
            logger.debug("Response analysis parse failed: %s", exc)
            return {"misconceptions": [], "emotional_state": "uncertain"}

    async def _is_in_scope(self, question: str, analysis: dict) -> bool:
        """
        Check if the question is within the Physics curriculum.

        Primary check: match analysis topic against topics in our concepts table.
        Fallback: keyword scan of the question text.
        """
        # DB-driven topic check
        try:
            topics = await self._pool.fetch("SELECT DISTINCT topic FROM concepts")
            topic_names = [t["topic"].lower() for t in topics]
            analysis_topic = analysis.get("topic", "").lower()

            for known_topic in topic_names:
                if known_topic and (known_topic in analysis_topic or analysis_topic in known_topic):
                    return True
        except Exception as exc:
            logger.warning("Topic DB lookup failed in _is_in_scope: %s", exc)

        # Keyword fallback
        physics_terms = [
            "force", "energy", "momentum", "charge", "field",
            "current", "voltage", "resistance", "wave", "light", "optics",
            "motion", "velocity", "acceleration", "gravity", "mass",
            "electric", "magnetic", "nuclear", "atom", "photon",
            "thermodynamics", "heat", "temperature", "pressure",
            "capacitor", "inductor", "circuit", "semiconductor",
            "friction", "torque", "angular", "oscillation", "frequency",
            "displacement", "refraction", "reflection", "diffraction",
            "interference", "radioactive", "fission", "fusion", "quantum",
            "newton", "coulomb", "faraday", "ohm", "kirchhoff",
            "bernoulli", "viscosity", "entropy", "carnot",
            "projectile", "centripetal", "satellite", "orbit",
        ]
        question_lower = question.lower()
        if any(term in question_lower for term in physics_terms):
            return True

        # Note: we do NOT trust analysis["subject"] here because the
        # PROBLEM_ANALYSIS_PROMPT hardcodes "subject": "Physics" in the schema.
        # The DB-topic + keyword checks above are the reliable signal.
        return False

    @staticmethod
    def _format_conversation(history: list) -> str:
        """Render conversation history as a readable transcript."""
        if not history:
            return "(no prior conversation)"
        lines: list = []
        for turn in history:
            role = turn.get("role", "unknown").capitalize()
            content = turn.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _sanitize_latex(self, text: str) -> str:
        """
        Post-process LLM output to fix common LaTeX rendering bugs before
        sending to the frontend KaTeX renderer.

        Fixes applied:
        1. Ensure every $$ delimiter is on its own line (adds surrounding newlines).
        2. Collapse \\n\\n inside $$ ... $$ blocks — RAG chunks sometimes inject
           blank lines into equations, breaking the renderer.
        3. Collapse 3+ consecutive newlines globally to at most 2.
        """
        # 1. Ensure $$ always has a newline before and after it
        text = re.sub(r'(?<!\n)\$\$', r'\n$$', text)
        text = re.sub(r'\$\$(?!\n)', r'$$\n', text)

        # 2. Inside every $$ block, collapse multiple blank lines to a single newline.
        # Previous implementation used re.sub with a single pattern, which only fixed
        # the FIRST $$ pair due to non-overlapping match semantics. This loop processes
        # all blocks by scanning through the string explicitly.
        result_parts: list[str] = []
        remaining = text
        while True:
            open_idx = remaining.find('\n$$\n')
            if open_idx == -1:
                result_parts.append(remaining)
                break
            close_idx = remaining.find('\n$$\n', open_idx + 4)
            if close_idx == -1:
                # Unclosed $$ block — leave as-is
                result_parts.append(remaining)
                break
            # Append text before the block unchanged
            result_parts.append(remaining[:open_idx])
            # Extract and clean the block interior
            inner = remaining[open_idx + 4 : close_idx]
            inner = re.sub(r'\n{2,}', '\n', inner).strip()
            result_parts.append(f'\n$$\n{inner}\n$$')
            remaining = remaining[close_idx + 4:]
        text = ''.join(result_parts)

        # 3. No more than 2 consecutive newlines anywhere in the output
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text

    async def _call_llm(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        model_tier: ModelTier = "quality",
    ) -> str:
        """Call OpenAI via the async client with tiered model routing.

        model_tier controls which model is used:
            "cheap"   → gpt-4o-mini  (classification, summarization)
            "quality" → gpt-4.1-mini (Socratic responses, solutions)

        If system_prompt is provided it is sent as role="system" before the
        user message, giving the model a stable identity and behaviour contract
        that is not mixed in with the per-call user context.
        """
        messages: List[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = _get_model(model_tier)
        response = await self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        return response.choices[0].message.content

    async def _get_mastery_info(
        self,
        student_id: str,
        concept_ids: List[str],
    ) -> str:
        """Return a human-readable mastery summary for given concepts."""
        if not concept_ids:
            return "No concept-mastery data available for this query."

        try:
            student_uuid = uuid.UUID(student_id)
        except ValueError:
            return "Invalid student ID — no mastery data available."

        rows = await self._pool.fetch(
            """
            SELECT cm.concept_id, cm.mastery_score, c.subtopic
            FROM concept_mastery cm
            JOIN concepts c ON c.id = cm.concept_id
            WHERE cm.student_id = $1
              AND cm.concept_id = ANY($2::text[])
            ORDER BY cm.mastery_score
            """,
            student_uuid,
            concept_ids,
        )

        if not rows:
            return "No mastery data found for the relevant concepts yet."

        lines: list = []
        for row in rows:
            score: float = float(row["mastery_score"])
            level = "beginner" if score < 0.4 else ("developing" if score < 0.7 else "proficient")
            lines.append(f"  • {row['subtopic']}: {score:.0%} ({level})")

        return "\n".join(lines)

    async def _create_session(
        self,
        student_id: str,
        question: str,
        subject: str,
        analysis: dict,
        socratic_response: str,
        concept_ids: List[str],
    ) -> uuid.UUID:
        """Insert a new doubt_session row and return its UUID."""
        conversation_history = [
            {"role": "student", "content": question},
            {"role": "tutor",   "content": socratic_response},
        ]

        # difficulty in analysis is 1–10; DB column expects [0, 1]
        difficulty_raw = analysis.get("difficulty", 5)
        try:
            difficulty = max(0.0, min(1.0, float(difficulty_raw) / 10.0))
        except (TypeError, ValueError):
            difficulty = 0.5

        topic = analysis.get("topic") or analysis.get("subtopic") or subject

        row = await self._pool.fetchrow(
            """
            INSERT INTO doubt_sessions
                (student_id, problem_text, subject, topic, difficulty,
                 concepts_involved, analysis, conversation_history)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
            RETURNING id
            """,
            uuid.UUID(student_id),
            question,
            subject,
            topic,
            difficulty,
            concept_ids,
            json.dumps(analysis),
            json.dumps(conversation_history),
        )
        return row["id"]

    async def _log_event(
        self,
        session_id: uuid.UUID,
        event_type: str,
        payload: Optional[dict] = None,
        doubt_block_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Insert a session_event row."""
        await self._pool.execute(
            """
            INSERT INTO session_events (session_id, event_type, payload, doubt_block_id)
            VALUES ($1, $2, $3::jsonb, $4)
            """,
            session_id,
            event_type,
            json.dumps(payload or {}),
            doubt_block_id,
        )
