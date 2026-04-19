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
import time
import uuid
from typing import TYPE_CHECKING, Dict, List, Literal, Optional

import asyncpg
import openai

from app.config import settings
from app.services.doubt.context import get_student_mastery_str
from app.services.doubt.prompts import (
    CONVERSATIONAL_RESPONSE,
    DOUBT_BLOCK_SUMMARIZER_PROMPT,
    EMOTIONAL_RESPONSE_PROMPT,
    EXPLANATION_PROMPT,
    FULL_SOLUTION_PROMPT,
    GREETING_RESPONSES,
    HINT_LEVEL_1_PROMPT,
    HINT_LEVEL_2_PROMPT,
    HINT_LEVEL_3_PROMPT,
    HINT_LEVEL_3_CORRECT_PROMPT,
    HINT_LEVEL_3_WRONG_PROMPT,
    INTENT_CLASSIFIER_PROMPT,
    INTENT_CLASSIFIER_SYSTEM,
    META_RESPONSE,
    META_IDENTITY_RESPONSE,
    META_PRICING_RESPONSE,
    META_COMPETITOR_RESPONSE,
    OUT_OF_SCOPE_RESPONSE,
    PROBLEM_ANALYSIS_PROMPT,
    SOCRATIC_QUESTION_PROMPT,
    SOLUTION_SEEKER_NOTE_FIRST,
    SOLUTION_SEEKER_NOTE_REPEAT,
    SOLUTION_SEEKER_PREAMBLE,
    STUDENT_RESPONSE_ANALYSIS_PROMPT,
    SUBJECT_CLASSIFIER_PROMPT,
    SUBJECT_CLASSIFIER_SYSTEM,
    SYSTEM_PROMPT_FORCED_ATTEMPT,
    TOPIC_LOCK_ADDENDUM,
    TUTOR_SYSTEM_PROMPT,
    build_system_prompt,
    get_subject_context,
    render_personalization,
)
from app.services.memory.context import get_persona_profile
from app.services.policy.engine import select_pedagogy
from app.services.doubt.misconceptions import check_for_misconception
from app.services.eval.judge import score_response
from app.services.eval.logger import log_scaffolding_score
from app.services.eval.turn_scorer import score_turn
from app.services.cache.semantic_cache import cache_response, get_cached_response
from app.services.mastery import update_concept_mastery
from app.services.rag.retriever import Retriever
from app.services.rag.agent import AgenticRetriever

if TYPE_CHECKING:
    from app.services.verify.pipeline import VerificationPipeline

logger = logging.getLogger(__name__)

# ── intent pre-filter constants (no LLM cost) ────────────────────────────────

_CONVERSATIONAL_TOKENS: frozenset = frozenset({
    "yes", "no", "ok", "okay", "sure", "thanks", "thank you",
    "got it", "cool", "alright", "fine", "yep", "nope", "hmm",
    "good", "great", "nice", "awesome", "wow", "oh", "ah", "i see",
    "understood", "makes sense", "got", "k", "noted",
})

_EXPLANATION_TRIGGERS: tuple = (
    "explain ", "what is ", "what are ", "define ", "definition of ",
    "how does ", "how do ", "tell me about ", "describe ", "meaning of ",
    "what's ", "what was ", "who is ", "what does ", "how is ",
)

_PROBLEM_SIGNALS: frozenset = frozenset({
    "find", "calculate", "prove", "derive", "solve",
    "determine", "compute", "evaluate", "obtain", "show that",
})

# ── Distress keyword gate for COUNSELOR mode switching ───────────────────────
# The emotional state classifier sometimes returns "frustrated" for academic
# confusion ("no idea", "don't know"). We only switch to COUNSELOR mode when
# the student's own words contain genuine emotional distress signals.
# Academic confusion ("no idea", "stuck", "confused") is handled by the
# CONFUSED branch in HINT_LEVEL_1/2_PROMPT — it does NOT trigger COUNSELOR mode.
_DISTRESS_KEYWORDS: frozenset = frozenset({
    "give up", "giving up", "can't do this", "cannot do this",
    "too hard", "too difficult", "hopeless", "useless",
    "want to quit", "want to drop", "so stressed", "so anxious",
    "breaking down", "hate this", "hate studying", "hate maths",
    "hate math", "hate physics", "hate chemistry",
    "i'm done", "im done", "i quit", "this is pointless",
})

# ── Solution-seeker pattern (server-side regex, no LLM cost) ─────────────────
# Catches soft solution-seeking that does NOT trigger the frontend GIVE_UP_RE
# (which sets jump_to_full=True for explicit give-up phrases).
# When matched: acknowledge, inject note into prompt, track ignored_socratic_count.
# After 2 consecutive ignored turns: note escalates to SOLUTION_SEEKER_NOTE_REPEAT.
_SOLUTION_SEEKER_RE = re.compile(
    r'\b('
    r'give\s+me\s+(the\s+)?(solution|answer)|'
    r'with\s+solution|'
    r'tell\s+me\s+(the\s+)?(answer|solution)|'
    r'just\s+(tell|show|give)\s+me\s+(the\s+)?(answer|solution)|'
    r'(show|give)\s+me\s+the\s+(solution|answer)|'
    r'what(?:\'s|\s+is)\s+the\s+(correct\s+)?answer'
    r')\b',
    re.IGNORECASE,
)

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
        # Agentic RAG — reuses the same embed service already held by the retriever.
        # No new dependencies: pool and client are already available here.
        self._agentic_retriever = AgenticRetriever(
            openai_client=openai_client,
            retriever=retriever,
            pool=db_pool,
            embed_service=retriever._embed,
        )

    # ── public API ────────────────────────────────────────────────────────────

    async def extract_question_from_image(self, image_url: str) -> str:
        """
        Vision AI — extract the physics question text from an image URL.

        Uses GPT-4o (not gpt-4o-mini) with vision capability.
        Returns the extracted question as plain text with LaTeX where appropriate.
        Raises RuntimeError on failure.
        """
        try:
            resp = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model="gpt-4o",  # vision requires full GPT-4o, not mini
                    max_tokens=500,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_url, "detail": "high"},
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        "Extract the physics question(s) from this image. "
                                        "Return only the question text. "
                                        "Represent mathematical expressions in LaTeX using $...$ for inline "
                                        "and $$...$$ for block equations. "
                                        "If multiple questions appear, include all of them separated by newlines."
                                    ),
                                },
                            ],
                        }
                    ],
                ),
                timeout=10.0,
            )
            return resp.choices[0].message.content.strip()
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Vision AI timed out (10s)") from exc
        except Exception as exc:
            raise RuntimeError(f"Vision AI failed: {exc}") from exc

    async def start_session(
        self,
        question: str,
        student_id: str,
        subject: str = "Physics",
        study_session_id: Optional[str] = None,
        locked_topic: Optional[str] = None,
        student_context: str = "",
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

        # ── 0a. Topic lock pre-check (short-circuit off-topic requests) ───────
        # When the session is locked to a specific topic but the student's
        # question is clearly about a different subject/topic, bypass the
        # Socratic engine entirely and return a canonical redirect. This is
        # more reliable than asking the LLM to refuse mid-generation (the
        # system-prompt addendum is frequently ignored on long prompts).
        if locked_topic:
            is_off_topic = await self._topic_lock_mismatch(
                question=question,
                locked_topic=locked_topic,
                subject=subject,
            )
            if is_off_topic:
                logger.info(
                    "start_session: topic lock SHORT-CIRCUIT — question %r does NOT match locked_topic=%r",
                    question[:80], locked_topic,
                )
                # Persist a minimal doubt_session so follow-up hints work; but
                # the response itself is the pure redirect.
                redirect_text = (
                    f"That's an interesting question, but this session is locked to "
                    f"**{locked_topic}**. To explore that other topic, start a new "
                    f"session from the topic tree and I'll meet you there. "
                    f"For now, let's continue with {locked_topic} — what part of "
                    f"{locked_topic} would you like to work on?"
                )
                minimal_analysis = {
                    "subject": subject,
                    "topic": locked_topic,
                    "subtopic": locked_topic,
                    "locked_topic": locked_topic,
                    "topic_lock_redirect": True,
                }
                session_id = await self._create_session(
                    student_id=student_id,
                    question=question,
                    subject=subject,
                    analysis=minimal_analysis,
                    socratic_response=redirect_text,
                    concept_ids=[],
                )
                return {
                    "session_id": str(session_id),
                    "analysis": minimal_analysis,
                    "response": redirect_text,
                    "mentor_mode": "TASKMASTER",
                    "concepts_involved": [],
                    "retrieved_context_count": 0,
                    "out_of_scope": False,
                    "cache_hit": False,
                    "_rag_metrics": {
                        "retrieval_latency_ms": 0,
                        "agent_steps": 0,
                        "chunk_count": 0,
                        "has_similar_problem": False,
                        "tool_trace": [],
                        "subject": subject,
                    },
                }

        # ── 0b. Semantic cache lookup (hint_level=0 only) ─────────────────────
        # Compute query embedding once — reused for cache AND skips LLM if hit.
        # Cache is student-agnostic: same question → same Socratic opener.
        # Never cache: only first Socratic question (not follow-up hints).
        _query_embedding: list = []
        try:
            loop = asyncio.get_running_loop()
            _query_embedding = await loop.run_in_executor(
                None, self._retriever._embed.embed_single, question
            )
            cached = await get_cached_response(_query_embedding)
            if cached is not None:
                # Cache hit — re-create a session record so the student's genome
                # pipeline still fires normally, but skip the expensive RAG + LLM.
                logger.info(
                    "Semantic cache HIT for student=%s — skipping RAG + LLM", student_id
                )
                # We still need a session_id — create a lightweight session row.
                cached_response_text = cached.get("response", "")
                cached_analysis      = cached.get("analysis", {})
                cached_mentor_mode   = cached.get("mentor_mode", "COACH")
                cached_concept_ids   = cached.get("concepts_involved", [])

                cached_session_id = await self._create_session(
                    student_id=student_id,
                    question=question,
                    subject=subject,
                    analysis=cached_analysis,
                    socratic_response=cached_response_text,
                    concept_ids=cached_concept_ids,
                )
                await self._log_event(
                    session_id=cached_session_id,
                    event_type="question_asked",
                    payload={
                        "question":    question,
                        "concept_ids": cached_concept_ids,
                        "mentor_mode": cached_mentor_mode,
                        "cache_hit":   True,
                    },
                )
                return {
                    "session_id":              str(cached_session_id),
                    "analysis":                cached_analysis,
                    "response":                cached_response_text,
                    "mentor_mode":             cached_mentor_mode,
                    "concepts_involved":       cached_concept_ids,
                    "retrieved_context_count": cached.get("retrieved_context_count", 0),
                    "out_of_scope":            cached.get("out_of_scope", False),
                    "cache_hit":               True,
                }
        except Exception as cache_exc:
            logger.warning(
                "Semantic cache lookup failed (non-fatal): %s", cache_exc
            )

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
                    subject_context=get_subject_context(subject),
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

        # Store mentor_mode + locked_topic in analysis so get_hint() can retrieve them later
        analysis["mentor_mode"] = mentor_mode
        if locked_topic:
            analysis["locked_topic"] = locked_topic

        # ── 3. Subject classification — pre-seeds the agentic loop ──────────────
        # Short-circuit: if subject is already a known SUPPORTED_SUBJECT (e.g.
        # navigated from TopicTree), skip the gpt-4o-mini classify call entirely.
        from app.services.doubt.prompts import SUPPORTED_SUBJECTS  # noqa: PLC0415
        if subject in SUPPORTED_SUBJECTS:
            logger.info("Subject already known (%s) — skipping _classify_subject", subject)
            subject_meta = {"subject": subject, "question_type": "conceptual"}
        else:
            logger.info("Classifying subject and topic …")
            subject_meta = await self._classify_subject(question)
        _effective_subject = subject_meta.get("subject", subject)
        _question_type     = subject_meta.get("question_type", "conceptual")

        # ── 4. Agentic RAG + concept IDs (concurrent) ────────────────────────
        # The agentic retriever decides which tools to call (NCERT / JEE PYQ /
        # Concepts) and how many retrieval steps to take, up to MAX_STEPS=3.
        logger.info(
            "Running agentic RAG (subject=%s, qtype=%s) …",
            _effective_subject, _question_type,
        )
        analysis_topic = analysis.get("topic", "")
        rag, concept_ids = await asyncio.gather(
            self._agentic_retriever.run(
                question=question,
                subject=_effective_subject,
                topic=analysis_topic,
                hint_level=0,
                question_type=_question_type,
            ),
            self._retriever.get_related_concepts(question),
        )
        # Persist detected subject + question type in analysis so get_hint()
        # can reuse them without re-classifying on every hint turn.
        analysis["detected_subject"] = _effective_subject
        analysis["question_type"]    = _question_type

        # ── 5. Scope check (DB-driven + keyword fallback) ─────────────────────
        out_of_scope = not await self._is_in_scope(question=question, analysis=analysis, rag=rag)
        analysis["out_of_scope"] = out_of_scope

        # ── 6. Targeted genome injection: per-topic mastery string ────────────
        genome_injection = await get_student_mastery_str(
            self._pool, student_id, analysis_topic,
        )

        # ── 7. Fetch session memory (if within a study session) ────────────────
        session_memory = "(no prior context in this session)"
        if study_session_id:
            session_memory = await self.get_session_memory(study_session_id)

        # ── 8. Policy engine — select pedagogy for this student + topic ──────────
        _subject_context = get_subject_context(_effective_subject)
        try:
            import dataclasses
            persona_profile = await get_persona_profile(student_id, self._pool)
            pedagogy_config = select_pedagogy(
                persona_profile, analysis.get("topic", ""), hint_level=0, subject=_effective_subject,
            )
            personalization_block = render_personalization(pedagogy_config, persona_profile)
            active_system_prompt = build_system_prompt(personalization_block, subject=_effective_subject)
            # Store in analysis for reference (persona_profile re-fetched in get_hint)
            analysis["persona_profile"] = persona_profile
            analysis["pedagogy_config"] = dataclasses.asdict(pedagogy_config)
        except Exception as exc:
            logger.warning("Policy engine failed (non-fatal), using default prompt: %s", exc)
            active_system_prompt = TUTOR_SYSTEM_PROMPT.format(
                subject_context=_subject_context,
            )

        # ── Topic lock addendum: PREPEND scope enforcement when topic is pinned
        # LLMs weight the TOP of the system prompt heavily and often ignore
        # instructions buried at the end of long prompts. Prepending ensures
        # the lock is the first thing the model processes.
        if locked_topic:
            active_system_prompt = (
                TOPIC_LOCK_ADDENDUM.format(
                    locked_topic=locked_topic,
                    subject=_effective_subject,
                )
                + "\n\n"
                + active_system_prompt
            )
            logger.info(
                "start_session: TOPIC_LOCK_ADDENDUM prepended for topic=%r subject=%r (prompt length=%d)",
                locked_topic, _effective_subject, len(active_system_prompt),
            )

        # ── 9. Generate personalised Socratic response ────────────────────────
        logger.info("Generating Socratic response (mentor=%s) …", mentor_mode)
        _llm_t0 = time.monotonic()
        _LLM_TIMEOUT_SECONDS = 30.0
        try:
            socratic_response = await asyncio.wait_for(
                self._call_llm(
                    SOCRATIC_QUESTION_PROMPT.format(
                        subject=_effective_subject,
                        subject_context=_subject_context,
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
                        student_context=student_context,
                    ),
                    max_tokens=1024,
                    temperature=0.7,
                    system_prompt=active_system_prompt,
                ),
                timeout=_LLM_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Socratic LLM timed out after %.0fs for student=%s question=%.60s",
                _LLM_TIMEOUT_SECONDS, student_id, question,
            )
            socratic_response = (
                "I'm taking too long to respond right now — the AI service seems slow. "
                "Please try rephrasing your question or try again in a moment. "
                "Your question has been noted and your session is still active. 🔄"
            )
        _response_latency_ms = int((time.monotonic() - _llm_t0) * 1000)
        socratic_response = self._sanitize_latex(socratic_response)  # Rule 6 — every path
        # FIX 8: post-gen single-question enforcement (L0 prompt rule alone
        # was ignored 33% of the time in the comprehensive eval).
        socratic_response = await self._enforce_single_question(socratic_response)

        if out_of_scope:
            socratic_response = (
                f"⚠️ This question appears to be outside the {_effective_subject} syllabus "
                "(NCERT Class 11 & 12). I'll do my best to help, but for detailed "
                "study, refer to the relevant chapter.\n\n" + socratic_response
            )

        # ── 10. Persist doubt_session ─────────────────────────────────────────
        session_id = await self._create_session(
            student_id=student_id,
            question=question,
            subject=subject,
            analysis=analysis,
            socratic_response=socratic_response,
            concept_ids=concept_ids,
        )

        # ── 11. Log session event ─────────────────────────────────────────────
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

        # ── 11b. Fire Judge LLM as background task (same as get_hint) ─────────
        # Scores the initial Socratic question for quality. Never blocks response.
        _max_similarity_start: Optional[float] = None
        if rag.get("chunks"):
            _max_similarity_start = max(
                (float(c.get("similarity_score", 0.0)) for c in rag["chunks"]),
                default=0.0,
            )
        _judge_session_id_start = str(session_id)
        _judge_question_start   = question
        _judge_response_start   = socratic_response
        _judge_sim_start        = _max_similarity_start
        _judge_lat_start        = _response_latency_ms

        async def _run_judge_start() -> None:
            try:
                result = await score_response(_judge_question_start, _judge_response_start)
                await log_scaffolding_score(
                    session_id=_judge_session_id_start,
                    score=result["score"],
                    rationale=result.get("rationale", ""),
                    db=self._pool,
                    retrieval_similarity=_judge_sim_start,
                    response_latency_ms=_judge_lat_start,
                )
            except Exception as exc:
                logger.warning("Background judge (start_session) failed (non-fatal): %s", exc)

        asyncio.create_task(_run_judge_start())

        result = {
            "session_id": str(session_id),
            "analysis": analysis,
            "response": socratic_response,
            "mentor_mode": mentor_mode,
            "concepts_involved": concept_ids,
            "retrieved_context_count": rag["chunk_count"],
            "out_of_scope": out_of_scope,
            "cache_hit": False,
            # RAG telemetry — consumed by doubt.py to write session_metrics
            "_rag_metrics": {
                "retrieval_latency_ms": rag.get("retrieval_latency_ms", 0),
                "agent_steps":          len(rag.get("tool_trace", [])),
                "chunk_count":          rag["chunk_count"],
                "has_similar_problem":  rag.get("similar_problem") is not None,
                "tool_trace":           rag.get("tool_trace", []),
                "subject":              _effective_subject,
            },
        }

        # ── 12. Store in semantic cache (background, never blocks response) ────
        # Only cache hint_level=0 Socratic openers. Student-agnostic: the same
        # question will get the same cached opener regardless of who asks.
        # Strip persona_profile and pedagogy_config — these are student-specific
        # and must not leak to other students who get a cache hit.
        if _query_embedding:
            _cache_analysis = {k: v for k, v in analysis.items()
                               if k not in ("persona_profile", "pedagogy_config")}
            _cache_payload = {
                "response":               socratic_response,
                "analysis":               _cache_analysis,
                "mentor_mode":            mentor_mode,
                "concepts_involved":      concept_ids,
                "retrieved_context_count": rag["chunk_count"],
                "out_of_scope":           out_of_scope,
            }
            asyncio.create_task(cache_response(_query_embedding, _cache_payload))

        return result

    async def start_session_stream(
        self,
        question: str,
        student_id: str,
        subject: str = "Physics",
        study_session_id: Optional[str] = None,
        locked_topic: Optional[str] = None,
        student_context: str = "",
    ):
        """
        Streaming variant of start_session().

        Yields SSE-formatted dicts:
            {"token": str, "done": False}             — each LLM token
            {"token": "", "done": True, **metadata}   — final event with session_id etc.
            {"error": str, "done": True}              — on any fatal error

        The LaTeX sanitizer cannot run token-by-token; it runs on the full
        accumulated response and is noted in the final metadata event.

        Background tasks (genome update, session log) fire as normal after
        the stream completes.

        Cache semantics are identical to start_session():
        - Cache is checked before the LLM; a hit is returned as a single
          non-streaming response (all tokens at once, done=True immediately).
        - A cache miss results in a streamed response that is stored after.
        """
        try:
            # ── 0. Validate student ─────────────────────────────────────────────
            try:
                student_uuid = uuid.UUID(student_id)
            except ValueError as exc:
                yield {"error": f"Invalid student ID: {student_id}", "done": True}
                return

            student_row = await self._pool.fetchrow(
                "SELECT id FROM students WHERE id = $1", student_uuid
            )
            if student_row is None:
                yield {"error": f"Student not found: {student_id}", "done": True}
                return

            # ── 0b. Semantic cache check ────────────────────────────────────────
            _query_embedding: list = []
            try:
                loop = asyncio.get_running_loop()
                _query_embedding = await loop.run_in_executor(
                    None, self._retriever._embed.embed_single, question
                )
                cached = await get_cached_response(_query_embedding)
                if cached is not None:
                    cached_text = cached.get("response", "")
                    cached_analysis = cached.get("analysis", {})
                    cached_mentor_mode = cached.get("mentor_mode", "COACH")
                    cached_concept_ids = cached.get("concepts_involved", [])
                    logger.info(
                        "Semantic cache HIT (stream) for student=%s", student_id
                    )
                    cached_session_id = await self._create_session(
                        student_id=student_id,
                        question=question,
                        subject=subject,
                        analysis=cached_analysis,
                        socratic_response=cached_text,
                        concept_ids=cached_concept_ids,
                    )
                    await self._log_event(
                        session_id=cached_session_id,
                        event_type="question_asked",
                        payload={"question": question, "cache_hit": True},
                    )
                    # Yield full response in one token then done
                    yield {"token": cached_text, "done": False}
                    yield {
                        "token": "",
                        "done": True,
                        "session_id": str(cached_session_id),
                        "analysis": cached_analysis,
                        "mentor_mode": cached_mentor_mode,
                        "concepts_involved": cached_concept_ids,
                        "out_of_scope": cached.get("out_of_scope", False),
                        "cache_hit": True,
                    }
                    return
            except Exception as cache_exc:
                logger.warning("Stream cache lookup failed (non-fatal): %s", cache_exc)

            # ── 1. Student context + mentor mode ────────────────────────────────
            student_ctx = await self._get_student_context(student_id)
            mentor_mode = self._detect_mentor_mode(student_ctx)

            # ── 2. Problem analysis ─────────────────────────────────────────────
            if locked_topic:
                analysis = {
                    "subject": subject, "topic": locked_topic,
                    "subtopic": locked_topic, "concepts_required": [],
                    "difficulty": 5, "problem_type": "conceptual",
                    "key_insight": "", "common_misconceptions": [],
                    "brief_analysis": question,
                }
            else:
                analysis_raw = await self._call_llm(
                    PROBLEM_ANALYSIS_PROMPT.format(
                        subject_context=get_subject_context(subject),
                        question=question,
                        overall_mastery=student_ctx["overall_mastery"],
                        concept_mastery_details=student_ctx["weak_areas"],
                        recent_errors=student_ctx["recent_errors"],
                        session_count=student_ctx["session_count"],
                    ),
                    max_tokens=600, temperature=0.1, model_tier="cheap",
                )
                try:
                    analysis = _parse_json_response(analysis_raw)
                except (ValueError, json.JSONDecodeError):
                    analysis = {
                        "subject": subject, "topic": subject, "subtopic": "General",
                        "concepts_required": [], "difficulty": 5,
                        "problem_type": "conceptual", "key_insight": "",
                        "common_misconceptions": [], "brief_analysis": question,
                    }

            analysis["mentor_mode"] = mentor_mode
            if locked_topic:
                analysis["locked_topic"] = locked_topic

            # ── 3. Subject classification ────────────────────────────────────────
            # Short-circuit: skip gpt-4o-mini call when subject is pre-known
            from app.services.doubt.prompts import SUPPORTED_SUBJECTS  # noqa: PLC0415
            if subject in SUPPORTED_SUBJECTS:
                logger.info("Subject already known (%s) — skipping _classify_subject (stream)", subject)
                stream_subject_meta = {"subject": subject, "question_type": "conceptual"}
            else:
                stream_subject_meta = await self._classify_subject(question)
            _eff_subject_stream = stream_subject_meta.get("subject", subject)
            _qtype_stream       = stream_subject_meta.get("question_type", "conceptual")

            # ── 4. Agentic RAG + concept IDs (concurrent) ───────────────────────
            analysis_topic = analysis.get("topic", "")
            rag, concept_ids = await asyncio.gather(
                self._agentic_retriever.run(
                    question=question,
                    subject=_eff_subject_stream,
                    topic=analysis_topic,
                    hint_level=0,
                    question_type=_qtype_stream,
                ),
                self._retriever.get_related_concepts(question),
            )
            analysis["detected_subject"] = _eff_subject_stream
            analysis["question_type"]    = _qtype_stream

            # ── 5. Scope check ──────────────────────────────────────────────────
            out_of_scope = not await self._is_in_scope(question=question, analysis=analysis, rag=rag)
            analysis["out_of_scope"] = out_of_scope

            # ── 6+7. Genome injection + session memory ──────────────────────────
            genome_injection = await get_student_mastery_str(
                self._pool, student_id, analysis_topic,
            )
            session_memory = "(no prior context in this session)"
            if study_session_id:
                session_memory = await self.get_session_memory(study_session_id)

            # ── 8. Policy engine ────────────────────────────────────────────────
            _stream_subject_context = get_subject_context(_eff_subject_stream)
            try:
                import dataclasses
                persona_profile = await get_persona_profile(student_id, self._pool)
                pedagogy_config = select_pedagogy(
                    persona_profile, analysis.get("topic", ""), hint_level=0,
                    subject=_eff_subject_stream,
                )
                personalization_block = render_personalization(pedagogy_config, persona_profile)
                active_system_prompt = build_system_prompt(
                    personalization_block, subject=_eff_subject_stream,
                )
                analysis["persona_profile"] = persona_profile
                analysis["pedagogy_config"] = dataclasses.asdict(pedagogy_config)
            except Exception as exc:
                logger.warning("Policy engine (stream) failed (non-fatal): %s", exc)
                active_system_prompt = TUTOR_SYSTEM_PROMPT.format(
                    subject_context=_stream_subject_context,
                )

            # ── 8b. Topic lock addendum (stream) — PREPEND ─────────────────────
            if locked_topic:
                active_system_prompt = (
                    TOPIC_LOCK_ADDENDUM.format(
                        locked_topic=locked_topic,
                        subject=_eff_subject_stream,
                    )
                    + "\n\n"
                    + active_system_prompt
                )

            # ── 9. Build messages for streaming LLM call ─────────────────────
            socratic_prompt = SOCRATIC_QUESTION_PROMPT.format(
                subject=_eff_subject_stream,
                subject_context=_stream_subject_context,
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
                student_context=student_context,
            )
            messages: List[dict] = []
            if active_system_prompt:
                messages.append({"role": "system", "content": active_system_prompt})
            messages.append({"role": "user", "content": socratic_prompt})

            # ── 10. Stream the LLM response ─────────────────────────────────────
            # Emit the out-of-scope warning as the first token so the user sees
            # the text immediately — not just the badge shown in metadata.
            _oos_prefix = ""
            if out_of_scope:
                _oos_subject_stream = analysis.get("detected_subject", subject)
                _oos_prefix = (
                    f"⚠️ This question appears to be outside the {_oos_subject_stream} syllabus "
                    "(NCERT Class 11 & 12). I'll do my best to help, but for detailed "
                    "study, refer to the relevant chapter.\n\n"
                )
                yield {"token": _oos_prefix, "done": False}

            _llm_t0_stream = time.monotonic()
            stream = await self._client.chat.completions.create(
                model=_get_model("quality"),
                max_tokens=1024,
                temperature=0.7,
                messages=messages,
                stream=True,
            )
            accumulated = ""
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    accumulated += delta
                    yield {"token": delta, "done": False}
            _stream_latency_ms = int((time.monotonic() - _llm_t0_stream) * 1000)

            # ── 10b. LaTeX sanitizer on full accumulated response ────────────────
            # accumulated contains only LLM tokens; the oos_prefix was yielded
            # separately. For DB storage, prepend the prefix so the persisted
            # response is the complete canonical text.
            socratic_response = self._sanitize_latex(_oos_prefix + accumulated)

            # ── 11. Persist session + log event ─────────────────────────────────
            session_id = await self._create_session(
                student_id=student_id,
                question=question,
                subject=subject,
                analysis=analysis,
                socratic_response=socratic_response,
                concept_ids=concept_ids,
            )
            await self._log_event(
                session_id=session_id,
                event_type="question_asked",
                payload={
                    "question": question,
                    "concept_ids": concept_ids,
                    "mentor_mode": mentor_mode,
                },
            )

            # ── 11b. Fire Judge LLM as background task ───────────────────────────
            _max_sim_stream: Optional[float] = None
            if rag.get("chunks"):
                _max_sim_stream = max(
                    (float(c.get("similarity_score", 0.0)) for c in rag["chunks"]),
                    default=0.0,
                )
            _j_sid  = str(session_id)
            _j_q    = question
            _j_resp = socratic_response
            _j_sim  = _max_sim_stream
            _j_lat  = _stream_latency_ms

            async def _run_judge_stream() -> None:
                try:
                    result = await score_response(_j_q, _j_resp)
                    await log_scaffolding_score(
                        session_id=_j_sid,
                        score=result["score"],
                        rationale=result.get("rationale", ""),
                        db=self._pool,
                        retrieval_similarity=_j_sim,
                        response_latency_ms=_j_lat,
                    )
                except Exception as exc:
                    logger.warning("Background judge (stream) failed (non-fatal): %s", exc)

            asyncio.create_task(_run_judge_stream())

            # ── 12. Cache response (background) ─────────────────────────────────
            # Strip student-specific keys before caching — the cache is student-agnostic.
            if _query_embedding:
                _stream_cache_analysis = {k: v for k, v in analysis.items()
                                          if k not in ("persona_profile", "pedagogy_config")}
                asyncio.create_task(cache_response(_query_embedding, {
                    "response": socratic_response,
                    "analysis": _stream_cache_analysis,
                    "mentor_mode": mentor_mode,
                    "concepts_involved": concept_ids,
                    "retrieved_context_count": rag["chunk_count"],
                    "out_of_scope": out_of_scope,
                }))

            # ── Final metadata event ─────────────────────────────────────────────
            yield {
                "token": "",
                "done": True,
                "session_id": str(session_id),
                "analysis": analysis,
                "mentor_mode": mentor_mode,
                "concepts_involved": concept_ids,
                "retrieved_context_count": rag["chunk_count"],
                "out_of_scope": out_of_scope,
                "cache_hit": False,
                "sanitized_response": socratic_response,
            }

        except Exception as exc:
            logger.error("start_session_stream failed: %s", exc)
            yield {"error": str(exc), "done": True}

    async def get_hint(
        self,
        session_id: str,
        student_response: Optional[str] = None,
        jump_to_full: bool = False,
        student_resolved: bool = False,
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

        # ── 1b. Student self-resolved — mark session done, skip hint generation ─
        # Called by "Got it!" button. Triggers genome update without extra hints.
        if student_resolved:
            await self._pool.execute(
                """
                UPDATE doubt_sessions
                SET resolved = TRUE, current_hint_level = $2
                WHERE id = $1
                """,
                uuid.UUID(session_id),
                current_level,
            )
            logger.info(
                "Student self-resolved session %s at hint_level=%d", session_id, current_level
            )
            return {
                "session_id": session_id,
                "hint_level": current_level,
                "hint": "🎉 Marked as solved! Great work.",
                "response": "🎉 Marked as solved! Great work.",
                "is_full_solution": False,
                "is_forced_attempt": False,
                "resolved": True,
                "verification": None,
                "mentor_mode": mentor_mode,
                "response_analysis": {},
            }

        # ── 1c. FIX 11: subject-switch detection ───────────────────────────────
        # If the student's reply is clearly asking about a different subject
        # mid-session (e.g. physics session → "now tell me about acid-base
        # chemistry"), don't silently drift. Return a gentle redirect asking
        # the student to finish the current doubt or start a new session.
        if student_response and student_response.strip() and current_level < 3:
            _new_subj = self._detect_subject_switch(student_response, subject)
            if _new_subj:
                logger.info(
                    "get_hint: subject-switch REDIRECT — current=%r detected=%r",
                    subject, _new_subj,
                )
                _redir = (
                    f"Looks like you're asking about **{_new_subj}** — but this "
                    f"session is on **{subject}**. To dive into {_new_subj}, "
                    f"start a new session for that topic. "
                    f"Or I can continue helping you with {subject} — did you "
                    f"want to finish this problem first?"
                )
                # Append the student's message + the redirect to history so
                # the next turn has full context.
                history.append({"role": "student", "content": student_response})
                history.append({"role": "tutor", "content": _redir})
                await self._pool.execute(
                    """
                    UPDATE doubt_sessions
                    SET conversation_history = $1::jsonb
                    WHERE id = $2
                    """,
                    json.dumps(history),
                    uuid.UUID(session_id),
                )
                return {
                    "session_id": str(session_id),
                    "hint_level": current_level,
                    "hint": _redir,
                    "response": _redir,
                    "is_full_solution": False,
                    "is_forced_attempt": False,
                    "resolved": False,
                    "verification": None,
                    "mentor_mode": mentor_mode,
                    "response_analysis": {"subject_switch_detected": _new_subj},
                }

        # ── 2. Analyze student response before appending to history ───────────
        # Skip response analysis at the forced-attempt stage (current_level >= 3).
        # At this point ANY response should unlock the full solution — spending
        # an LLM call to detect "frustrated" would route to counselor mode and
        # block the full solution (the "therapist hijack" bug).
        response_analysis: dict = {}
        logger.info(
            "analyzer-gate: student_response=%r current_level=%d will_run=%s",
            (student_response or "")[:60], current_level,
            bool(student_response and student_response.strip() and current_level < 3),
        )
        if student_response and student_response.strip() and current_level < 3:
            try:
                response_analysis = await self._analyze_student_response(
                    question=problem_text,
                    analysis=stored_analysis,
                    conversation_history=history,
                    student_response=student_response,
                )
                # Adapt mentor mode if student shows genuine emotional distress.
                # Guard: only switch to COUNSELOR when the student's own words contain
                # explicit distress keywords — NOT for academic confusion ("no idea",
                # "don't know", "stuck"). Academic confusion is handled by the CONFUSED
                # branch in HINT_LEVEL_1/2_PROMPT without triggering counselor persona.
                if response_analysis.get("emotional_state") == "frustrated":
                    _resp_lower = (student_response or "").lower()
                    if any(kw in _resp_lower for kw in _DISTRESS_KEYWORDS):
                        logger.info(
                            "Student distress confirmed (keyword match) — switching to COUNSELOR mode."
                        )
                        mentor_mode = "COUNSELOR"
                        stored_analysis["mentor_mode"] = "COUNSELOR"
                    else:
                        logger.info(
                            "LLM returned frustrated but no distress keywords found "
                            "(likely academic confusion) — keeping %s mode.", mentor_mode
                        )
            except Exception as exc:
                logger.warning("Response analysis failed (non-fatal): %s", exc)

        # ── 2b. Format response_analysis into human-readable assessment ───────
        # This injects what the student got right/wrong into the LLM's context
        # explicitly, rather than asking the LLM to infer from raw conversation.
        _response_assessment_text = ""
        _answer_check = None  # exposed below for L3 correctness gate
        _answer_student_value = None
        _answer_correct_value = None
        if response_analysis:
            understood = response_analysis.get("understood_correctly", [])
            gaps = response_analysis.get("knowledge_gaps", [])
            suggestion = response_analysis.get("suggested_next_action", "")
            emotional = response_analysis.get("emotional_state", "")
            _answer_check = response_analysis.get("answer_check")
            _answer_student_value = response_analysis.get("student_value")
            _answer_correct_value = response_analysis.get("correct_value")
            mismatch_note = response_analysis.get("mismatch_note")
            parts: list[str] = []
            # Answer-check banner (FIX 3): put this FIRST — it's the most actionable
            # signal the hint prompt needs to decide CORRECT vs WRONG vs CONFUSED.
            if _answer_check == "correct":
                parts.append(
                    f"ANSWER CHECK: ✅ CORRECT — student's value '{_answer_student_value}' matches the expected answer. "
                    "Validate EXPLICITLY (e.g. 'Exactly — [value] is right.'). Do NOT re-ask or restart."
                )
            elif _answer_check == "wrong":
                parts.append(
                    f"ANSWER CHECK: ❌ WRONG — student said '{_answer_student_value}'. "
                    f"The correct value is '{_answer_correct_value}'. "
                    f"{('Mismatch: ' + mismatch_note + '.') if mismatch_note else ''} "
                    "Before anything else in your reply, explicitly say which number/expression is wrong and why, "
                    "then guide (don't just give) the corrected path. Do NOT validate as correct."
                )
            elif _answer_check == "partial":
                parts.append(
                    f"ANSWER CHECK: ⚠️ PARTIAL — student named a relevant method/concept "
                    f"('{_answer_student_value or ''}') but has not produced a final answer yet. "
                    "Validate the method briefly, then push toward the next concrete step."
                )
            else:  # not_an_answer or missing
                parts.append("ANSWER CHECK: — student did not give a numerical/closed-form answer.")
            if understood:
                parts.append(f"Student correctly understood: {', '.join(understood)}")
            else:
                parts.append("Student has not yet demonstrated correct understanding")
            if gaps:
                parts.append(f"Gaps to address: {', '.join(gaps)}")
            if suggestion:
                parts.append(f"Suggested next step: {suggestion}")
            if emotional and emotional not in ("uncertain",):
                parts.append(f"Student emotional state: {emotional}")
            _response_assessment_text = "\n".join(parts)

        # ── 3. Append student response to history ─────────────────────────────
        if student_response and student_response.strip():
            history.append({"role": "student", "content": student_response})

        # ── 3b. Soft solution-seeking detection ───────────────────────────────
        # Regex-based, no LLM cost (same pattern as _CONVERSATIONAL_TOKENS).
        # Does NOT overlap with jump_to_full (explicit give-up from frontend).
        # Tracks consecutive ignored turns in stored_analysis so the count
        # persists across turns without any new DB column.
        is_solution_seeking: bool = False
        if (
            student_response
            and student_response.strip()
            and not jump_to_full
            and not student_resolved
            and current_level < 3
            and _SOLUTION_SEEKER_RE.search(student_response)
        ):
            is_solution_seeking = True
            _ignored = stored_analysis.get("ignored_socratic_count", 0) + 1
            stored_analysis["ignored_socratic_count"] = _ignored
            logger.info(
                "Solution-seeking detected (count=%d) for session %s",
                _ignored, session_id,
            )

        # ── 3d. Misconception check ───────────────────────────────────────────
        # Run before hint level is incremented. Never fires at hint_level >= 3
        # (forced-attempt stage takes full priority). Pure keyword matching — no LLM.
        if student_response and student_response.strip() and current_level < 3:
            _topic = stored_analysis.get("topic", "")
            _mc_subject = stored_analysis.get("detected_subject", subject)
            _mc = check_for_misconception(student_response, _topic, subject=_mc_subject)
            if _mc is not None:
                logger.info(
                    "Misconception detected: id=%s session=%s", _mc.id, session_id
                )
                correction = self._sanitize_latex(_mc.correction_prompt)
                history.append({"role": "tutor", "content": correction})
                # Persist conversation with correction — keep current_level unchanged
                await self._pool.execute(
                    """
                    UPDATE doubt_sessions
                    SET conversation_history = $1::jsonb,
                        analysis             = $2::jsonb
                    WHERE id = $3
                    """,
                    json.dumps(history),
                    json.dumps(stored_analysis),
                    uuid.UUID(session_id),
                )
                await self._log_event(
                    session_id=uuid.UUID(session_id),
                    event_type="misconception_detected",
                    payload={"misconception_id": _mc.id, "hint_level": current_level},
                )
                return {
                    "session_id": session_id,
                    "hint_level": current_level,
                    "hint": correction,
                    "response": correction,
                    "is_full_solution": False,
                    "is_forced_attempt": False,
                    "is_misconception_correction": True,
                    "misconception_id": _mc.id,
                    "resolved": False,
                    "verification": None,
                    "mentor_mode": mentor_mode,
                    "response_analysis": response_analysis,
                }

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

        # ── 4c. L1/L2 NO-INPUT GATE (2026-04-19) ──────────────────────────────
        # When the student clicks "Give me a hint" WITHOUT answering the AI's
        # previous question, don't escalate to the next hint level. Return a
        # deterministic re-prompt that echoes the AI's last question.
        #
        # Why: previously, /doubt/hint with null student_response at L1
        # advanced to L2. The L2 prompt's validator rotation ("Right —",
        # "Exactly —") then fired even though student_response="(no response
        # provided)" — the LLM hallucinated a validation of a non-existent
        # answer, dropped the L1 question, and jumped to a new concept.
        # The user's screenshot showed exactly this: AI asked "Which functional
        # group attachment differentiates alcohols from phenols?" then Hint 2
        # opened with "Right — to set up the key formulas..." skipping the
        # student's turn entirely.
        #
        # L0 → L1 without a reply is still allowed (legit "I don't know where
        # to start" case). L1 → L2 and L2 → L3 without a reply are gated.
        if (
            current_level >= 1
            and not jump_to_full
            and not (student_response and student_response.strip())
        ):
            # Extract the last '?' sentence from the AI's last message
            last_ai_question = ""
            for turn in reversed(history):
                if turn.get("role") in ("tutor", "assistant"):
                    _c = turn.get("content", "") or ""
                    # Find all sentences ending in '?' (outside LaTeX)
                    _qs = re.findall(r'[^.!?\n]*\?', _c)
                    if _qs:
                        last_ai_question = _qs[-1].strip()
                    break
            if last_ai_question:
                gate_msg = (
                    f"Before I give another hint — take a moment on my last question:\n\n"
                    f"**{last_ai_question}**\n\n"
                    f"Even a rough guess or partial thought is fine. I'll build from whatever you share."
                )
            else:
                gate_msg = (
                    "Before I give another hint — give the current question a try, "
                    "even a rough guess. I'll build from whatever you share."
                )
            logger.info(
                "L%d→L%d no-input gate fired — re-prompting for answer instead of escalating",
                current_level, current_level + 1,
            )
            return {
                "session_id": str(session_id),
                "hint_level": current_level,  # stay at same level, don't advance
                "hint": gate_msg,
                "response": gate_msg,
                "is_full_solution": False,
                "is_forced_attempt": False,
                "resolved": False,
                "verification": None,
                "mentor_mode": mentor_mode,
                "response_analysis": {"no_input_reprompt": True},
            }

        # ── 5+6. Agentic RAG context + targeted genome injection (concurrent) ────
        # Nuclear override: hint level 3 (Forced Attempt) receives NO RAG context
        # and NO analysis. Starving the LLM of this material makes solution leakage
        # structurally impossible — it cannot teach what it has not been given.
        # AgenticRetriever.run() also returns empty at hint_level==3 as a double gate.
        if new_level == 3:
            rag = {"context_text": "", "chunks": [], "chunk_count": 0, "tool_trace": []}
            genome_injection = ""
        else:
            analysis_topic = stored_analysis.get("topic", "")
            # Re-use detected subject + question type stored during start_session().
            # For hints, question_type skews toward "numerical" at levels 2+ since the
            # student is deep in problem-solving — JEE PYQ search becomes more useful.
            _hint_subject = stored_analysis.get("detected_subject", subject)
            _hint_qtype = (
                "numerical"
                if new_level >= 2
                else stored_analysis.get("question_type", "conceptual")
            )
            rag, genome_injection = await asyncio.gather(
                self._agentic_retriever.run(
                    question=problem_text,
                    subject=_hint_subject,
                    topic=analysis_topic,
                    hint_level=new_level,
                    question_type=_hint_qtype,
                ),
                get_student_mastery_str(self._pool, str(session_student_id), analysis_topic),
            )

        # Extract max cosine similarity from retrieved chunks (None at level 3)
        _max_similarity: Optional[float] = None
        if new_level != 3 and rag.get("chunks"):
            _max_similarity = max(
                (float(c.get("similarity_score", 0.0)) for c in rag["chunks"]),
                default=0.0,
            )
            if _max_similarity < 0.5:
                logger.warning(
                    "Low retrieval confidence: similarity=%.3f for query: %.50s",
                    _max_similarity, problem_text,
                )

        # ── 7. Format conversation and student response for prompts ───────────
        # Log problem_text to verify context lock is anchored to the correct problem.
        logger.info(
            "get_hint: level=%d session=%s problem_text[0:80]=%r",
            new_level, session_id, problem_text[:80],
        )
        conversation_text = self._format_conversation(history)
        student_response_text = (student_response or "").strip() or "(no response provided)"
        analysis_json = json.dumps(stored_analysis, indent=2)
        _hint_subject = stored_analysis.get("detected_subject", subject)
        _hint_subject_context = get_subject_context(_hint_subject)

        # ── 8. Select & render the appropriate prompt ─────────────────────────
        if new_level == 1:
            prompt = HINT_LEVEL_1_PROMPT.format(
                subject=_hint_subject,
                subject_context=_hint_subject_context,
                problem=problem_text,                  # Fix 1+4: explicit problem anchor
                conversation_history=conversation_text,
                student_response=student_response_text,
                response_assessment=_response_assessment_text or "(no prior analysis available)",
                analysis=analysis_json,
                context=rag["context_text"],
                genome_injection=genome_injection,
            )
            # Fix 2: append solution-seeker instruction if detected this turn
            if is_solution_seeking:
                _count = stored_analysis.get("ignored_socratic_count", 1)
                prompt += SOLUTION_SEEKER_NOTE_REPEAT if _count >= 2 else SOLUTION_SEEKER_NOTE_FIRST
        elif new_level == 2:
            prompt = HINT_LEVEL_2_PROMPT.format(
                subject=_hint_subject,
                subject_context=_hint_subject_context,
                problem=problem_text,                  # Fix 1+4: explicit problem anchor
                conversation_history=conversation_text,
                student_response=student_response_text,
                response_assessment=_response_assessment_text or "(no prior analysis available)",
                analysis=analysis_json,
                context=rag["context_text"],
            )
            # Fix 2: append solution-seeker instruction if detected this turn
            if is_solution_seeking:
                _count = stored_analysis.get("ignored_socratic_count", 1)
                prompt += SOLUTION_SEEKER_NOTE_REPEAT if _count >= 2 else SOLUTION_SEEKER_NOTE_FIRST
        elif new_level == 3:
            # FIX 2: at L3, if the student already gave the correct final answer,
            # validate + derive instead of scolding with the forced-attempt template.
            # If they gave a WRONG final answer, flag it explicitly (without
            # revealing the correct value). Otherwise fall back to forced-attempt.
            if _answer_check == "correct" and _answer_student_value:
                logger.info(
                    "get_hint: L3 CORRECT-answer path — validating %r",
                    _answer_student_value,
                )
                prompt = HINT_LEVEL_3_CORRECT_PROMPT.format(
                    problem=problem_text,
                    student_value=_answer_student_value,
                    conversation_history=conversation_text,
                )
                # Route L3-correct through FULL_SOLUTION system prompt (not forced-
                # attempt proctor persona) since we want a complete, warm closure.
                _l3_short_circuit = "correct"
            elif _answer_check == "wrong" and _answer_student_value:
                logger.info(
                    "get_hint: L3 WRONG-answer path — flagging %r (correct=%r)",
                    _answer_student_value, _answer_correct_value,
                )
                prompt = HINT_LEVEL_3_WRONG_PROMPT.format(
                    problem=problem_text,
                    student_value=_answer_student_value,
                    correct_value=_answer_correct_value or "(see solution)",
                    mismatch_note=response_analysis.get("mismatch_note") or "Numerical mismatch.",
                    conversation_history=conversation_text,
                )
                _l3_short_circuit = "wrong"
            else:
                # Nuclear option: isolated prompt with no analysis or RAG context.
                # System prompt is also swapped to SYSTEM_PROMPT_FORCED_ATTEMPT,
                # removing the helpful-tutor persona entirely for this call.
                prompt = HINT_LEVEL_3_PROMPT.format(
                    conversation_history=conversation_text,
                    student_response=student_response_text,
                )
                _l3_short_circuit = None
        else:
            prompt = FULL_SOLUTION_PROMPT.format(
                subject=_hint_subject,
                subject_context=_hint_subject_context,
                conversation_history=conversation_text,
                question=problem_text,
                analysis=analysis_json,
                context=rag["context_text"],
            )

        # ── 9. Policy engine — re-fetch persona + rebuild system prompt ───────
        # Re-fetch persona_profile directly from DB (never read from stored_analysis
        # to avoid stale data if infer_scaffolding_level ran since session start).
        hint_active_system_prompt = SYSTEM_PROMPT_FORCED_ATTEMPT  # default for level 3
        hint_pedagogy_config = None
        # FIX 2: when L3 short-circuits to correct/wrong paths, we need the warm
        # tutor persona (not the proctor) so the model can validate or flag
        # without falling back to "refuse to teach" instincts.
        _l3_uses_tutor_persona = (
            new_level == 3 and locals().get("_l3_short_circuit") in ("correct", "wrong")
        )
        if new_level != 3 or _l3_uses_tutor_persona:
            try:
                import dataclasses
                hint_persona_profile = await get_persona_profile(str(session_student_id), self._pool)
                hint_pedagogy_config = select_pedagogy(
                    hint_persona_profile,
                    stored_analysis.get("topic", ""),
                    hint_level=new_level,
                    subject=_hint_subject,
                )
                hint_personalization_block = render_personalization(hint_pedagogy_config, hint_persona_profile)
                hint_active_system_prompt = build_system_prompt(
                    hint_personalization_block, subject=_hint_subject,
                )
            except Exception as exc:
                logger.warning("Policy engine in get_hint failed (non-fatal): %s", exc)
                hint_active_system_prompt = TUTOR_SYSTEM_PROMPT.format(
                    subject_context=_hint_subject_context,
                )

        # ── 9b. Re-apply topic lock addendum in hint turns — PREPEND ─────────
        # start_session() prepends TOPIC_LOCK_ADDENDUM to active_system_prompt but
        # get_hint() rebuilds the system prompt from scratch via the policy engine.
        # We store locked_topic in stored_analysis during start_session(); re-apply
        # AT THE TOP here so the LLM weights it heavily.
        _hint_locked_topic = stored_analysis.get("locked_topic")
        # Apply topic lock on all non-proctor paths: normal L1/L2 hints AND the
        # L3 short-circuit paths (correct/wrong) that use the warm tutor persona.
        if _hint_locked_topic and (new_level != 3 or locals().get("_l3_uses_tutor_persona")):
            hint_active_system_prompt = (
                TOPIC_LOCK_ADDENDUM.format(
                    locked_topic=_hint_locked_topic,
                    subject=_hint_subject,
                )
                + "\n\n"
                + hint_active_system_prompt
            )
            logger.info(
                "get_hint: TOPIC_LOCK_ADDENDUM prepended for topic=%r subject=%r level=%d",
                _hint_locked_topic, _hint_subject, new_level,
            )

        # Append max_concepts constraint for HIGH/MEDIUM scaffolding (not LOW = max 5)
        if hint_pedagogy_config is not None and hint_pedagogy_config.max_concepts < 5:
            prompt += (
                f"\n\nRESPONSE CONSTRAINT: Cover at most "
                f"{hint_pedagogy_config.max_concepts} concept(s) in this response."
            )

        # ── 10. Generate hint via LLM ─────────────────────────────────────────
        # Hint level 3 uses SYSTEM_PROMPT_FORCED_ATTEMPT (stripped proctor persona)
        # instead of TUTOR_SYSTEM_PROMPT to prevent persona override.
        active_system_prompt = hint_active_system_prompt
        logger.info(
            "Generating hint level %d for session %s (full=%s, mentor=%s, system=%s)",
            new_level, session_id, is_full_solution, mentor_mode,
            "FORCED_ATTEMPT" if new_level == 3 else "TUTOR",
        )
        # FIX 2: L3-correct path needs room for a full derivation (treat like
        # full-solution budget); L3-wrong stays short; classic L3 forced-attempt
        # stays short.
        _is_l3_correct = new_level == 3 and locals().get("_l3_short_circuit") == "correct"
        _is_l3_short = new_level == 3 and not _is_l3_correct
        _llm_t0 = time.monotonic()
        hint_response = await self._call_llm(
            prompt,
            max_tokens=(
                2048 if (_is_l3_correct or is_full_solution)
                else (256 if _is_l3_short else 1024)
            ),
            temperature=0.3 if _is_l3_short else 0.5,
            system_prompt=active_system_prompt,
        )
        _response_latency_ms = int((time.monotonic() - _llm_t0) * 1000)

        # ── 10b. "Nice Try" prefix — intercepted early jump_to_full ─────────────
        if nice_try_intercepted:
            hint_response = (
                "Nice try, but I'm not going to just give you the answer! "
                "Let's work through this step-by-step.\n\n" + hint_response
            )

        # ── 10c. Solution-seeker acknowledgment preamble ──────────────────────
        # Prepended AFTER the LLM response so the LLM doesn't echo it back.
        # The prompt instruction (SOLUTION_SEEKER_NOTE_*) tells the LLM not to
        # repeat the Socratic question; the preamble gives the student the
        # human-sounding acknowledgment they need.
        if is_solution_seeking:
            hint_response = SOLUTION_SEEKER_PREAMBLE + hint_response

        # ── 10e. LaTeX post-processing sanitizer ──────────────────────────────
        hint_response = self._sanitize_latex(hint_response)

        # ── 11. Verify full solution ───────────────────────────────────────────
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

        # ── 15. Fire Judge LLM as background task (never blocks student response) ──
        # Scores Socratic quality 0/1/2 and writes back to session_events.
        # Skipped at hint_level 3 (forced attempt) — no Socratic content to score.
        if new_level < 3:
            _judge_pool = self._pool
            _judge_session_id = session_id
            _judge_question = problem_text
            _judge_response = hint_response
            _judge_similarity = _max_similarity
            _judge_latency = _response_latency_ms

            async def _run_judge() -> None:
                try:
                    result = await score_response(_judge_question, _judge_response)
                    await log_scaffolding_score(
                        session_id=_judge_session_id,
                        score=result["score"],
                        rationale=result.get("rationale", ""),
                        db=_judge_pool,
                        retrieval_similarity=_judge_similarity,
                        response_latency_ms=_judge_latency,
                    )
                except Exception as exc:
                    logger.warning("Background judge task failed (non-fatal): %s", exc)

            asyncio.create_task(_run_judge())

        # ── 15b. Per-turn quality scorer (levels 1–2 only) ────────────────────
        # Scores: validation quality, strategy appropriateness, restart detection,
        # single-question compliance. Fires async — never blocks student response.
        if new_level in (1, 2) and student_response and student_response.strip():
            asyncio.create_task(
                score_turn(
                    client=self._client,
                    pool=self._pool,
                    doubt_session_id=session_id,
                    turn_index=len(history),  # history already includes student + tutor turns
                    student_message=student_response,
                    ai_response=hint_response,
                )
            )

        logger.info("Hint level %d delivered for session %s", new_level, session_id)
        _hint_subject_for_metrics = stored_analysis.get("detected_subject", subject)
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
            # RAG telemetry — consumed by doubt.py to write session_metrics
            "_rag_metrics": {
                "retrieval_latency_ms": rag.get("retrieval_latency_ms", 0),
                "agent_steps":          len(rag.get("tool_trace", [])),
                "chunk_count":          rag.get("chunk_count", 0),
                "has_similar_problem":  rag.get("similar_problem") is not None,
                "tool_trace":           rag.get("tool_trace", []),
                "subject":              _hint_subject_for_metrics,
            },
        }

    # ── subject classification (for agentic RAG pre-seeding) ─────────────────

    async def _classify_subject(self, question: str) -> dict:
        """
        Lightweight subject + topic + question_type classifier.

        Runs BEFORE the agentic RAG loop in start_session() so the agent's
        first tool call is already filtered to the correct subject.

        Model: gpt-4o-mini (cheap tier), temp=0.0 (deterministic).
        Max tokens: 80 — returns a tiny JSON object.

        Returns:
            {"subject": "Physics"|"Chemistry"|"Maths",
             "topic": str,
             "question_type": "conceptual"|"numerical"|"derivation"}

        Falls back silently to Physics/conceptual on any error.
        """
        _default = {"subject": "Physics", "topic": "", "question_type": "conceptual"}
        _valid_subjects = {"Physics", "Chemistry", "Maths"}

        try:
            raw = await self._call_llm(
                SUBJECT_CLASSIFIER_PROMPT.format(question=question),
                max_tokens=80,
                temperature=0.0,
                system_prompt=SUBJECT_CLASSIFIER_SYSTEM,
                model_tier="cheap",
            )
            result = _parse_json_response(raw)
            subject = result.get("subject", "Physics")
            if subject not in _valid_subjects:
                subject = "Physics"
            question_type = result.get("question_type", "conceptual")
            if question_type not in ("conceptual", "numerical", "derivation"):
                question_type = "conceptual"
            return {
                "subject":       subject,
                "topic":         str(result.get("topic", "")).strip(),
                "question_type": question_type,
            }
        except Exception as exc:
            logger.warning("_classify_subject failed (non-fatal): %s", exc)
            return _default

    # ── intent classification ────────────────────────────────────────────────

    async def classify_intent(
        self,
        message: str,
        has_active_block: bool = False,
        subject: str = "Physics",
    ) -> str:
        """Classify a student message into one of 9 intents.

        Returns one of: greeting, meta, emotional, out_of_scope,
        recap, subject_doubt, continuation, conversational, explanation.
        """
        _VALID_INTENTS = {
            "greeting", "meta", "meta_identity", "meta_pricing", "meta_competitor",
            "emotional",
            "out_of_scope", "subject_doubt", "continuation", "recap",
            "conversational", "explanation",
            # backward-compat alias — old "physics_doubt" treated as subject_doubt
            "physics_doubt",
        }

        stripped = message.strip().lower()

        # ── Pre-check 1: short conversational tokens (no LLM needed) ──────────
        if len(stripped) <= 20 and stripped in _CONVERSATIONAL_TOKENS:
            logger.info("Conversational pre-filter: %r", stripped)
            return "conversational"

        # ── Pre-check 2: explanation requests (no LLM needed for clear signals)
        # Only fires when message has an explanation trigger, no problem-solving
        # signals, and no numerical values (those indicate a problem to solve).
        #
        # FIX A2 (2026-04-18): SKIP this pre-filter entirely when an active
        # doubt block exists AND the message is short (< 80 chars). Short
        # replies like "second derivative of f(x)" or "derivative of the hill"
        # inside an active block are CONTINUATIONS of the current doubt, not
        # fresh explain-this-concept requests. The previous pre-filter was
        # mis-classifying these as `explanation` → returning a generic overview
        # with no session_id / no conversation_history → "0 doubts asked" bug.
        if any(stripped.startswith(t) or (" " + t) in (" " + stripped)
               for t in _EXPLANATION_TRIGGERS):
            has_numbers = bool(re.search(r'\d', stripped))
            has_problem_signal = any(s in stripped for s in _PROBLEM_SIGNALS)
            if has_active_block and len(stripped) < 80:
                # Likely a continuation reply — let the LLM classifier decide
                # (it will usually return "continuation" given has_active_block=true).
                logger.info(
                    "Explanation pre-filter SKIPPED (active block, short reply): %r",
                    stripped[:60],
                )
            elif not has_numbers and not has_problem_signal:
                logger.info("Explanation pre-filter: %r", stripped)
                return "explanation"

        prompt = INTENT_CLASSIFIER_PROMPT.format(
            has_active_block=str(has_active_block).lower(),
            subject=subject,
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

        # Normalise legacy "physics_doubt" alias to "subject_doubt"
        if intent == "physics_doubt":
            intent = "subject_doubt"

        if intent in _VALID_INTENTS:
            return intent

        # Fallback: if there's an active block, treat as continuation;
        # otherwise treat as a new subject doubt.
        logger.warning("Classifier returned unknown intent '%s'; falling back", raw.strip())
        return "continuation" if has_active_block else "subject_doubt"

    async def handle_non_physics_intent(
        self,
        intent: str,
        message: str,
        subject: str = "Physics",
    ) -> dict:
        """Handle greeting / meta / emotional / out_of_scope intents.

        Returns {intent, response, session_id: None}. NO DB writes.
        """
        if intent == "greeting":
            response = random.choice(GREETING_RESPONSES)
        elif intent == "conversational":
            response = CONVERSATIONAL_RESPONSE
        elif intent == "meta":
            response = META_RESPONSE
        elif intent == "meta_identity":
            response = META_IDENTITY_RESPONSE
        elif intent == "meta_pricing":
            response = META_PRICING_RESPONSE
        elif intent == "meta_competitor":
            response = META_COMPETITOR_RESPONSE
        elif intent == "emotional":
            response = await self._call_llm(
                EMOTIONAL_RESPONSE_PROMPT.format(message=message),
                max_tokens=200,
                temperature=0.7,
                model_tier="cheap",
            )
            response = self._sanitize_latex(response)  # Rule 6 — every LLM path
        elif intent == "out_of_scope":
            response = OUT_OF_SCOPE_RESPONSE
        elif intent == "explanation":
            _exp_subject = subject if subject else "Physics"
            # FIX 9: detect tone signal from the raw message so the explanation
            # opens with an appropriate acknowledgement (stressed / frustrated /
            # overconfident / slow_learner / complimentary / default).
            _tone_signal = self._detect_tone_signal(message)
            logger.info("explanation: tone_signal=%r for message=%r", _tone_signal, message[:80])
            response = await self._call_llm(
                EXPLANATION_PROMPT.format(
                    subject=_exp_subject,
                    subject_context=get_subject_context(_exp_subject),
                    message=message,
                    tone_signal=_tone_signal,
                ),
                max_tokens=600,
                temperature=0.5,
                model_tier="quality",
            )
            response = self._sanitize_latex(response)
        else:
            response = "I'm here to help! Ask me a Physics, Chemistry, or Maths question from NCERT Class 11 or 12."

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

    def _detect_subject_switch(self, message: str, current_subject: str) -> Optional[str]:
        """FIX 11: detect when a student's hint reply is asking about a
        different subject than the current doubt_session's subject.

        Returns the NEW subject name (e.g. "Chemistry") if detected, else None.
        Keyword-based so it's cheap and deterministic. Conservative: only
        triggers on clear subject keywords, never on ambiguous tokens.
        """
        if not message or not current_subject:
            return None
        m = message.lower()
        subject_keywords = {
            "Physics": (
                " physics", "newton's", "newtons law", "kinematics",
                "electrostatics", "magnetism", "optics", "thermodynamics of",
                "moment of inertia", "torque", "gravitation", "projectile",
            ),
            "Chemistry": (
                " chemistry", "acid-base", "acid base", "ph of ", "mole concept",
                "oxidation state", "organic chemistry", "sn1", "sn2", "hcl",
                "nacl", "electrochemistry", "periodic table", "reaction mechanism",
                "le chatelier",
            ),
            "Maths": (
                " maths", " math", "derivative", "integral", "differentiation",
                "integration", "calculus", "probability", "complex number",
                "coordinate geometry", "quadratic equation", "matrix",
                "determinant", "trigonometr",
            ),
        }
        # Must also contain a "now/switch/instead" marker to avoid false positives
        # when student is legitimately quoting/referencing a related concept.
        switch_markers = (
            "instead", "now tell me about", "switch to", "change to", "move to",
            "now explain", "now talk about", "let's do", "lets do",
        )
        has_switch_marker = any(sm in m for sm in switch_markers)
        if not has_switch_marker:
            return None
        # Detect which NEW subject they're asking about
        for new_subj, kws in subject_keywords.items():
            if new_subj == current_subject:
                continue
            for kw in kws:
                if kw in m:
                    logger.info(
                        "subject-switch detected: current=%r message has kw=%r → new=%r",
                        current_subject, kw, new_subj,
                    )
                    return new_subj
        return None

    def _detect_tone_signal(self, message: str) -> str:
        """FIX 9: classify the student message into one of 5 tone buckets so the
        EXPLANATION_PROMPT can adapt its opening. Keyword-based so it's
        deterministic and adds zero latency.

        Returns one of: stressed | frustrated | overconfident | slow_learner |
        complimentary | default.
        """
        if not message:
            return "default"
        m = message.lower()
        # Order matters — check specific signals before generic defaults.
        stressed_kw = (
            "exam tomorrow", "exam today", "so stressed", "stressed",
            "so anxious", "anxious", "panicking", "please help", "help me",
            "running out of time", "cannot focus",
        )
        frustrated_kw = (
            "explained this badly", "badly last time", "confusing", "doesn't make sense",
            "doesn’t make sense", "this is frustrating", "i hate this",
            "why is this so hard", "tried multiple times",
        )
        overconfident_kw = (
            "i'm very good at this", "im very good at this", "this is easy",
            "easy question", "i know this", "trivial", "obvious",
        )
        slow_learner_kw = (
            "i'm really slow", "im really slow", "sorry i'm slow", "sorry im slow",
            "i'm bad at this", "im bad at this", "sorry i", "i don't get it",
            "i dont get it", "i am dumb", "i'm dumb", "im dumb",
        )
        complimentary_kw = (
            "best tutor", "you are amazing", "you're amazing", "love you",
            "you're the best", "you are the best", "you rock", "thank you so much",
            "so helpful",
        )
        for kw in stressed_kw:
            if kw in m: return "stressed"
        for kw in frustrated_kw:
            if kw in m: return "frustrated"
        for kw in overconfident_kw:
            if kw in m: return "overconfident"
        for kw in slow_learner_kw:
            if kw in m: return "slow_learner"
        for kw in complimentary_kw:
            if kw in m: return "complimentary"
        return "default"

    async def _enforce_single_question(self, response: str) -> str:
        """Post-generation cleanup: if the response has ≥ 2 question marks,
        rewrite it keeping only the single most important closing question.

        Two-stage strategy:
        1. **LLM cleanup** (soft) — rewrite with gpt-4o-mini preserving prose + math.
           Produces a natural-sounding single-question version.
        2. **Regex fallback** (hard) — if the LLM cleanup still has ≥ 2 '?'s,
           apply a deterministic rewrite that keeps only the LAST question
           (the closing one). Converts earlier '?' sentences to statements.

        The regex fallback guarantees ≤ 1 '?' on exit. LaTeX-internal '?' chars
        (rare) are ignored by the character count since they're wrapped in '$'.

        Fails open: on any exception, returns the original response.
        """
        if not response or response.count("?") < 2:
            return response

        # ── Stage 1: LLM-based soft rewrite ───────────────────────────────────
        rewritten = response
        try:
            prompt = (
                "The following tutor response ends with multiple questions, but a "
                "Socratic tutor should end with EXACTLY ONE focused question.\n\n"
                "Rewrite the response keeping EVERYTHING the same except: merge or "
                "drop all but the single most important closing question. Preserve "
                "all analogies, math notation, LaTeX, formatting, and explanatory "
                "text. Return ONLY the rewritten response — no preamble, no notes.\n\n"
                f"RESPONSE TO REWRITE:\n{response}"
            )
            llm_rewrite = await self._call_llm(
                prompt, max_tokens=1024, temperature=0.0, model_tier="cheap",
            )
            llm_rewrite = (llm_rewrite or "").strip()
            if llm_rewrite and llm_rewrite.count("?") < response.count("?"):
                logger.info(
                    "single-Q cleanup stage1 (LLM): reduced %d → %d questions",
                    response.count("?"), llm_rewrite.count("?"),
                )
                rewritten = llm_rewrite
            else:
                logger.info(
                    "single-Q cleanup stage1: LLM rewrite ineffective (orig_?=%d new_?=%d)",
                    response.count("?"), llm_rewrite.count("?") if llm_rewrite else 0,
                )
        except Exception as exc:
            logger.warning("single-Q cleanup stage1 failed: %s", exc)

        # ── Stage 2: deterministic regex fallback ─────────────────────────────
        # If stage 1 didn't bring it to ≤ 1 '?', keep only the LAST question and
        # turn earlier question-ending sentences into statements.
        if rewritten.count("?") >= 2:
            try:
                final = self._regex_single_question_fallback(rewritten)
                if final.count("?") <= 1:
                    logger.info(
                        "single-Q cleanup stage2 (regex): reduced %d → %d questions",
                        rewritten.count("?"), final.count("?"),
                    )
                    return final
            except Exception as exc:
                logger.warning("single-Q cleanup stage2 (regex) failed: %s", exc)

        return rewritten

    @staticmethod
    def _regex_single_question_fallback(text: str) -> str:
        """Keep only the LAST '?' sentence; convert earlier '?' sentences to '.'.

        Approach: scan the text and find every '?' position. Replace all but
        the last one with '.'. Preserves text structure (paragraphs, LaTeX,
        formatting, etc.).

        Edge case handled: '?' inside LaTeX inline ($...$) or display ($$...$$)
        math is left untouched — we only touch '?' that are outside math.
        """
        if text.count("?") <= 1:
            return text

        # Build a mask of character positions inside math blocks.
        # $$...$$ (display) and $...$ (inline). We'll skip '?' inside these.
        in_math = [False] * len(text)
        i = 0
        while i < len(text):
            if text[i] == "$":
                # Check for $$ first
                if i + 1 < len(text) and text[i + 1] == "$":
                    # Find closing $$
                    j = text.find("$$", i + 2)
                    if j == -1:
                        break
                    for k in range(i, j + 2):
                        in_math[k] = True
                    i = j + 2
                    continue
                else:
                    # Find closing single $
                    j = text.find("$", i + 1)
                    if j == -1:
                        break
                    for k in range(i, j + 1):
                        in_math[k] = True
                    i = j + 1
                    continue
            i += 1

        # Collect '?' positions outside math.
        q_positions = [i for i, ch in enumerate(text) if ch == "?" and not in_math[i]]
        if len(q_positions) <= 1:
            return text

        # Replace all '?' positions except the LAST with '.'.
        chars = list(text)
        for pos in q_positions[:-1]:
            chars[pos] = "."
        return "".join(chars)

    async def _topic_lock_mismatch(
        self,
        question: str,
        locked_topic: str,
        subject: str,
    ) -> bool:
        """Quick cheap-LLM check: is `question` clearly NOT about `locked_topic`?

        Returns True only for clearly off-topic requests (e.g. asking about
        gravitation when locked to 'Maxima and Minima'). Returns False for
        ambiguous or within-scope requests — fail open so students are never
        wrongly blocked.
        """
        try:
            prompt = (
                f"The student's tutoring session is LOCKED to this topic only:\n"
                f"  locked_topic = {locked_topic!r}\n"
                f"  subject      = {subject!r}\n\n"
                f"The student just asked:\n"
                f"  {question!r}\n\n"
                f"Is the question clearly about a DIFFERENT topic/subject that is unrelated to {locked_topic}?\n"
                f"Consider it related if it's the same topic, a sub-aspect of it, or a prerequisite.\n"
                f"Consider it off-topic if it names a clearly different chapter/subject/concept\n"
                f"(e.g. asking about gravitation when locked to Maxima and Minima).\n\n"
                f"Respond with ONLY one word: 'off_topic' or 'on_topic'."
            )
            raw = await self._call_llm(
                prompt, max_tokens=8, temperature=0.0, model_tier="cheap",
            )
            verdict = (raw or "").strip().lower()
            is_off = "off" in verdict
            logger.info(
                "topic-lock-check: locked=%r question=%r → raw=%r is_off=%s",
                locked_topic, question[:60], verdict[:20], is_off,
            )
            return is_off
        except Exception as exc:
            logger.warning("topic-lock-check failed (assuming on_topic): %s", exc)
            return False

    async def _analyze_student_response(
        self,
        question: str,
        analysis: dict,
        conversation_history: list,
        student_response: str,
    ) -> dict:
        """Analyze the student's response to personalize the next hint.

        Uses the QUALITY model tier (gpt-4.1-mini) rather than the cheap tier.
        Rationale: the analyzer now produces `answer_check` + `correct_value`
        which drive L3 validation routing and WRONG-answer flagging. The cheap
        model (gpt-4o-mini) was empirically wrong on JEE-level numerical math
        (e.g. got the Atwood machine acceleration wrong). Accuracy here matters
        more than cost.
        """
        prompt = STUDENT_RESPONSE_ANALYSIS_PROMPT.format(
            question=question,
            analysis=json.dumps(analysis),
            conversation_history=self._format_conversation(conversation_history),
            student_response=student_response,
        )
        raw = await self._call_llm(prompt, max_tokens=400, temperature=0.0, model_tier="quality")
        try:
            parsed = _parse_json_response(raw)
            logger.info(
                "analyzer: student_response=%r → answer_check=%r student_value=%r correct_value=%r",
                student_response[:60], parsed.get("answer_check"),
                parsed.get("student_value"), parsed.get("correct_value"),
            )
            return parsed
        except Exception as exc:
            logger.debug("Response analysis parse failed: %s", exc)
            return {"misconceptions": [], "emotional_state": "uncertain"}

    async def _is_in_scope(
        self, question: str, analysis: dict, rag: dict | None = None
    ) -> bool:
        """
        Determine whether a question falls within the JEE/NEET NCERT curriculum
        (Physics, Chemistry, or Maths — Class 11 & 12).

        Signal priority:
        1. RAG retrieved relevant chunks  → definitely in scope (KB has content for it)
        2. DB topic match                 → in scope
        3. Subject-aware keyword match    → in scope
        4. Default → True                 → trust the intent classifier, which already
                                            filtered genuine out-of-scope questions
                                            (coding, history, biology-for-JEE, etc.)
                                            BEFORE start_session() was ever called.

        The warning should only fire for things that are truly beyond NCERT 11-12
        (e.g. advanced quantum field theory, engineering-level content).  It must
        NOT fire for valid JEE topics such as Raoult's Law, Solutions, Biomolecules,
        or any standard Chemistry / Maths chapter.
        """
        # ── 1. RAG result is the most reliable in-scope signal ──────────────
        # If the agentic retriever found NCERT chunks for this question, the
        # topic IS covered in our knowledge base — no further check needed.
        if rag and rag.get("chunk_count", 0) > 0:
            return True

        # ── 2. DB-driven topic check ─────────────────────────────────────────
        try:
            topics = await self._pool.fetch("SELECT DISTINCT topic FROM concepts")
            topic_names = [t["topic"].lower() for t in topics]
            analysis_topic = analysis.get("topic", "").lower()
            for known_topic in topic_names:
                if known_topic and (
                    known_topic in analysis_topic or analysis_topic in known_topic
                ):
                    return True
        except Exception as exc:
            logger.warning("Topic DB lookup failed in _is_in_scope: %s", exc)

        # ── 3. Subject-aware keyword fallback ────────────────────────────────
        # Each list covers the core NCERT JEE/NEET vocabulary for that subject.
        _SUBJECT_TERMS: dict[str, list[str]] = {
            "physics": [
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
            ],
            "chemistry": [
                "mole", "molarity", "molality", "solution", "solubility",
                "concentration", "acid", "base", "salt", "ph", "buffer",
                "titration", "equilibrium", "reaction", "bond", "orbital",
                "electron", "ion", "oxidation", "reduction", "redox",
                "electrochemistry", "electrolysis", "galvanic", "cell",
                "organic", "alkane", "alkene", "alkyne", "benzene",
                "hydrocarbon", "alcohol", "aldehyde", "ketone", "carboxylic",
                "ester", "amine", "polymer", "biomolecule", "protein",
                "amino acid", "glucose", "thermochemistry", "enthalpy",
                "entropy", "gibbs", "rate", "kinetics", "catalyst",
                "activation", "raoult", "colligative", "osmosis", "vapour",
                "boiling point", "freezing point", "depression", "elevation",
                "distillation", "chromatography", "periodic", "element",
                "compound", "valence", "hybridisation", "hybridization",
                "isomer", "nomenclature", "mole fraction", "van't hoff",
                "coordination", "complex", "ligand", "transition metal",
                "solid state", "crystal", "unit cell", "semiconductor",
                "surface chemistry", "adsorption", "colloid",
            ],
            "maths": [
                "integral", "derivative", "limit", "function", "matrix",
                "determinant", "vector", "probability", "statistics",
                "trigonometry", "sin", "cos", "tan", "logarithm",
                "exponential", "sequence", "series", "binomial", "complex",
                "coordinate", "conic", "ellipse", "parabola", "hyperbola",
                "circle", "permutation", "combination", "differential",
                "equation", "polynomial", "arithmetic", "geometric",
                "progression", "set", "relation", "algebra", "calculus",
                "differentiation", "integration", "inverse", "transpose",
                "eigenvalue", "continuity", "differentiability",
            ],
        }

        question_lower = question.lower()
        detected_subject = analysis.get("detected_subject", "").lower()

        # Check the detected subject's terms first (most precise)
        subject_terms = _SUBJECT_TERMS.get(detected_subject, [])
        if subject_terms and any(term in question_lower for term in subject_terms):
            return True

        # Broad check across all subjects (catches cross-topic questions)
        for terms in _SUBJECT_TERMS.values():
            if any(term in question_lower for term in terms):
                return True

        # ── 4. Default: trust the intent classifier ──────────────────────────
        # If we reach here, the question had no recognisable NCERT keyword AND
        # the RAG found nothing.  Even so, the intent classifier already screened
        # out coding / history / biology-for-JEE before start_session() was called.
        # Returning True avoids a false out-of-scope warning on unusual-phrased
        # but valid JEE questions.  The RAG returning 0 chunks is already a soft
        # signal captured in the response context — no extra banner needed.
        return True

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
