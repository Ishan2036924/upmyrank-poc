"""
Doubt-resolution API — intent-gated routing.

POST /doubt/ask    — classify intent → route to non-subject response or Socratic pipeline
POST /doubt/hint   — progressive hint for an active doubt session
POST /doubt/verify — two-layer solution verification
"""
import asyncio
import json
import logging
import re
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


# ── v0.20 dual-loop: topic-shift detection (Mode 2) ───────────────────────────
# Mirror of FIX A3 (2026-04-18) in the opposite direction: A3 promotes
# subject_doubt → continuation for short replies. This helper demotes
# continuation → subject_doubt when the student's message classifies to a
# DIFFERENT topic than the active doubt_block. Triggers the existing
# close-and-start-new-session path at ask_doubt() line ~745, so mastery
# credits the correct concept.
#
# Conservative by design: requires both (a) a nontrivial new-question shape
# and (b) a high-confidence topic mismatch. Otherwise we keep continuation
# semantics and let the existing guards run.

_NEW_QUESTION_MARKERS = re.compile(
    r"\b("
    r"find|calculate|solve|prove|evaluate|compute|simplify|"
    r"derive|differentiate|integrate|expand|factor|"
    r"what(?:\s+is|'s|\sis)?|why|how(?:\s+do|'s|\sdoes)?|"
    r"explain|define|state|describe|show"
    r")\b",
    re.IGNORECASE,
)

# v0.20.7 — follow-up starter phrases. A prompt that BEGINS with any of these
# is overwhelmingly a continuation of the active block, even if the verb
# regex above marks it as "new-question-shaped". Without this guard, messages
# like "why does substitution not help here?" (classified as `continuation`
# by the intent LLM) got demoted back to `subject_doubt` inside
# _detect_topic_shift because a sub-topic re-classification drifted from the
# active block's topic, opening a phantom block and diluting mastery.
#
# Prod evidence: diagnostic_2026-04-23.md bug #1 — 5/10 follow-up turns
# wrongly opened new blocks. All 5 start with a phrase in this list.
_CONTINUATION_STARTERS_RE = re.compile(
    r"^\s*("
    r"why\s+(?:does|doesn't|is|isn't|do|don't|would|wouldn't|can't|would)|"
    r"(?:ok(?:ay)?|so)\s+(?:so\s+)?then|"
    r"(?:ok(?:ay)?|alright|got\s+it|cool)\b|"
    r"but(?:\s+(?:isn't|doesn't|why|what))?\b|"
    r"what\s+(?:about|happens\s+(?:when|if)|if)|"
    r"(?:can|could|would)\s+you\s+(?:explain|show|clarify|repeat).*(?:again|once\s+more|one\s+more\s+time)|"
    r"hmm\b|wait\b|(?:oh\s+(?:wait|but))|(?:i|so)\s+see\b|"
    r"is\s+(?:that|this|it)\s+because|"
    r"(?:so|then)\s+(?:is\s+it|does\s+that\s+mean)|"
    r"is\s+\w+\s+(?:the\s+same|also).*(?:for|too|as\s+well)|"
    r"is\s+\w+\s+\w+\s+(?:too|also)\b"       # "is H2S bent too …" — subj verb adverb
    r")",
    re.IGNORECASE,
)


def _looks_like_continuation(text: str) -> bool:
    """v0.20.7 — asymmetric guard against false topic-shift promotions.

    If the message starts with a continuation marker (why does, ok so, but,
    what happens when, can you explain … again, hmm, wait, …) trust the
    intent classifier's `continuation` label and keep the active block open,
    even when the prompt also trips _looks_like_new_question.

    Symmetry note: this complements FIX A3's "< 100 chars short-reply" net —
    the starter phrase captures continuations that exceed 100 chars OR
    happen to contain a math verb (integrate, differentiate) but are still
    asking "why" about something in the active block.
    """
    if not text:
        return False
    stripped = text.strip().lower()
    return bool(_CONTINUATION_STARTERS_RE.match(stripped))

# Math-symbol heuristic — covers the "wait, what's the integral of sin(x²)?"
# class of pivots that the verb regex misses (no verb present, just notation).
_MATH_SYMBOL_HINTS = re.compile(
    r"(?:∫|∑|∏|√|π|θ|±|≤|≥|≠|→|⇒|"
    r"\^[0-9{(]|"          # x^2, x^{2}, x^(2)
    r"[a-zA-Z]\^?[²³⁰¹⁴⁵⁶⁷⁸⁹]|"  # x², m², F²
    r"\bd[a-z]/d[a-z]\b|"  # dy/dx
    r"\b(?:integral|derivative|limit|matrix|determinant|gradient|pH|mol|atomic)\b)",
    re.IGNORECASE,
)


def _looks_like_new_question(text: str) -> bool:
    """True if the message shape suggests a new problem (not a hint reply).

    v0.20.1: widened to catch contractions (what's, how's), math verbs
    (integrate, differentiate), and math-symbol-only pivots that have no
    verb (e.g. "the integral of sin(x²)"). Original v0.20 regex missed
    these — prod log on 2026-04-21 caught it.

    v0.20.3 (2026-04-21): lowered the verb-regex floor from 20→12 chars
    after prod surfaced "what is molecule?" (16 chars) being refused by
    counselor mode instead of opening a new doubt block. The 20-char
    floor was too aggressive for short, unambiguous question shapes
    like "what is X?" / "what's Y?". Symbol-only fallback floor stays
    at 25 (notation alone needs more weight to overcome ambiguity).
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) < 12:
        return False
    if _NEW_QUESTION_MARKERS.search(stripped):
        return True
    # Math-symbol fallback — only triggers on longer messages so a one-token
    # reply like "x²" doesn't open a new doubt block.
    if len(stripped) >= 25 and _MATH_SYMBOL_HINTS.search(stripped):
        return True
    return False


def _topics_differ(a: Optional[str], b: Optional[str]) -> bool:
    """Case- and whitespace-tolerant topic comparison."""
    if not a or not b:
        return False
    na = re.sub(r"[^a-z0-9]+", "", a.lower())
    nb = re.sub(r"[^a-z0-9]+", "", b.lower())
    if not na or not nb:
        return False
    # Neither is a prefix of the other (handles "Kinematics" vs "Kinematics (1D)").
    return not (na.startswith(nb) or nb.startswith(na))


async def _reclassify_block_topic(
    engine,
    pool,
    doubt_session_id: str,
) -> Optional[dict]:
    """
    v0.20.2 backstop: at block close, classify the *dominant* topic from the
    full conversation_history. If the classifier returns a different topic
    than the one stamped at block creation with confidence ≥ threshold, the
    caller should switch attribution before the EMA update.

    Returns {subject, topic} of the dominant topic if a switch is recommended,
    or None to keep the existing session.topic stamp.
    """
    try:
        row = await pool.fetchrow(
            """
            SELECT conversation_history, topic, subject
            FROM doubt_sessions
            WHERE id = $1
            """,
            uuid.UUID(doubt_session_id),
        )
    except Exception as exc:
        logger.warning("_reclassify_block_topic: fetch failed: %s", exc)
        return None
    if not row:
        return None

    history = row["conversation_history"] or []
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except Exception:
            history = []

    # Concatenate student turns only — AI turns reflect block topic, would bias.
    student_turns: List[str] = []
    for turn in history:
        if isinstance(turn, dict) and turn.get("role") == "student":
            content = turn.get("content")
            if content:
                student_turns.append(str(content))
    if not student_turns:
        return None

    # Skip if the block had only 1 student turn — no drift possible.
    if len(student_turns) < 2:
        return None

    sample = "\n".join(student_turns[-5:])  # last 5 student turns
    try:
        cls = await engine.classify_turn_topic(sample)
    except Exception as exc:
        logger.warning("_reclassify_block_topic: classifier failed: %s", exc)
        return None

    new_subject = (cls.get("subject") or "").strip()
    new_topic   = (cls.get("topic") or "").strip()
    old_subject = (row["subject"] or "").strip()
    old_topic   = (row["topic"] or "").strip()

    if not new_topic:
        return None

    subject_diff = bool(new_subject and old_subject and new_subject != old_subject)
    topic_diff   = _topics_differ(old_topic, new_topic)

    if subject_diff or topic_diff:
        logger.info(
            "block-close reclassify: %s/%s → %s/%s (session=%s)",
            old_subject, old_topic, new_subject, new_topic, doubt_session_id,
        )
        return {"subject": new_subject or old_subject, "topic": new_topic}
    return None


async def _detect_topic_shift(
    engine,
    question: str,
    active_block: dict,
) -> bool:
    """
    Returns True when the student's message is (a) shaped like a new question
    AND (b) classifies to a topic/subject materially different from the active
    block. Caller should then treat intent as subject_doubt, not continuation.

    Never raises — classifier failures return False (preserves continuation).
    """
    if not active_block or not _looks_like_new_question(question):
        return False

    # v0.20.7 — asymmetric trust: if the prompt begins with a continuation
    # starter, skip the shift check entirely. The intent LLM already flagged
    # this as `continuation`; our job is to demote `continuation` only when
    # the shape is *really* ambiguous, not to second-guess obvious follow-ups.
    if _looks_like_continuation(question):
        logger.info(
            "v0.20.7 continuation_trusted: starter phrase matched, skipping shift "
            "(block=%s, question=%r)",
            active_block.get("doubt_block_id"), question[:80],
        )
        return False

    try:
        cls = await engine.classify_turn_topic(question)
    except Exception as exc:
        logger.warning("_detect_topic_shift: classifier failed: %s", exc)
        return False

    new_subject = (cls.get("subject") or "").strip()
    new_topic   = (cls.get("topic") or "").strip()
    old_subject = (active_block.get("subject") or "").strip()
    old_topic   = (active_block.get("topic") or "").strip()

    # Subject change is a strong signal (e.g. from Physics → Maths mid-chat).
    if new_subject and old_subject and new_subject != old_subject:
        logger.info(
            "topic_shift: subject %s → %s (block=%s)",
            old_subject, new_subject, active_block.get("doubt_block_id"),
        )
        return True

    # Same subject — require a real topic mismatch.
    if _topics_differ(old_topic, new_topic):
        logger.info(
            "topic_shift: topic %r → %r (block=%s)",
            old_topic, new_topic, active_block.get("doubt_block_id"),
        )
        return True

    return False


# ── request / response models ─────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: Optional[str] = None
    image_url: Optional[str] = None    # Supabase Storage public URL for an image
    student_id: Optional[str] = None   # Ignored when auth header present; kept for legacy clients
    subject: str = "Physics"
    study_session_id: Optional[str] = None
    topic_lock: Optional[str] = None   # When set, skips intent classification and pins the topic
    student_confidence: Optional[str] = None  # low / medium / high — captured at forced attempt

    @field_validator("subject")
    @classmethod
    def subject_must_be_valid(cls, v: str) -> str:
        valid = {"Physics", "Chemistry", "Maths"}
        if v not in valid:
            raise ValueError(f"subject must be one of {sorted(valid)}, got '{v}'")
        return v

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
    student_resolved: bool = False      # True when student clicks "Got it!" — triggers genome update
    student_attempt: Optional[str] = None  # Optional attempt text before full solution
    student_confidence: Optional[str] = None  # low / medium / high — flows into confidence-weighted mastery update
    image_url: Optional[str] = None     # base64/data URL for student image upload in hint reply


class VerifyRequest(BaseModel):
    question: str
    solution: str
    context: str = ""


# ── doubt-block helpers ───────────────────────────────────────────────────────

_INACTIVE_BLOCK_THRESHOLD_MIN = 30  # v0.20.5: blocks idle >30 min are auto-closed


async def _autoclose_idle_blocks(pool, engine, student_id: str) -> int:
    """v0.20.5 — fire mastery for sessions students never explicitly closed.

    The Knowledge Genome was effectively broken in prod: only 7% of
    study_sessions ever ended (students close the tab, no /session/end
    fires), so _genome_update_task was almost never called → 44 of 45
    real users had zero mastery data despite real activity.

    This helper runs at the top of every /doubt/ask + /doubt/hint call.
    For the calling student, it finds doubt_blocks that:
      - belong to study_sessions still marked open
      - have not had their `started_at` updated in > _INACTIVE_BLOCK_THRESHOLD_MIN
      - are not solved + not ended
    and force-closes them (which fires _genome_update_task with
    give_up_flag=True via _close_doubt_block's existing branch).

    Best-effort: failures are logged + swallowed so a stuck close doesn't
    block the user's new request.
    """
    try:
        rows = await pool.fetch(
            """
            SELECT db.doubt_block_id
            FROM doubt_blocks db
            JOIN study_sessions ss ON ss.study_session_id = db.study_session_id
            WHERE db.student_id = $1
              AND db.ended_at IS NULL
              AND db.solved = FALSE
              AND db.started_at < NOW() - ($2 || ' minutes')::interval
              AND ss.ended_at IS NULL
            """,
            uuid.UUID(student_id),
            str(_INACTIVE_BLOCK_THRESHOLD_MIN),
        )
        if not rows:
            return 0
        for r in rows:
            try:
                await _close_doubt_block(pool, engine, str(r["doubt_block_id"]), solved=False)
                logger.info(
                    "autoclose_idle_blocks: closed block=%s for student=%s",
                    str(r["doubt_block_id"])[:8], student_id[:8],
                )
            except Exception as exc:
                logger.warning(
                    "autoclose_idle_blocks: close failed for %s: %s",
                    str(r["doubt_block_id"])[:8], exc,
                )
        return len(rows)
    except Exception as exc:
        logger.warning("autoclose_idle_blocks: query failed: %s", exc)
        return 0


async def _autoclose_idle_study_sessions(pool, student_id: str) -> int:
    """Same idea but at the study_session level — for sessions where ALL
    blocks have been closed but the parent session is still marked open.
    Sets ended_at + writes a placeholder summary so admin dashboards see
    the session as terminated."""
    try:
        rows = await pool.fetch(
            """
            UPDATE study_sessions
            SET ended_at = NOW(),
                session_summary = COALESCE(session_summary, '[auto-closed after inactivity]')
            WHERE student_id = $1
              AND ended_at IS NULL
              AND started_at < NOW() - ($2 || ' minutes')::interval
              AND NOT EXISTS (
                  SELECT 1 FROM doubt_blocks db
                  WHERE db.study_session_id = study_sessions.study_session_id
                    AND db.ended_at IS NULL
              )
            RETURNING study_session_id
            """,
            uuid.UUID(student_id),
            str(_INACTIVE_BLOCK_THRESHOLD_MIN),
        )
        if rows:
            logger.info(
                "autoclose_idle_study_sessions: closed %d session(s) for student=%s",
                len(rows), student_id[:8],
            )
        return len(rows)
    except Exception as exc:
        logger.warning("autoclose_idle_study_sessions: failed: %s", exc)
        return 0


async def _get_active_doubt_block(pool, study_session_id: str) -> Optional[dict]:
    """Get the latest unsolved, unclosed doubt block for a study session.

    v0.20: also JOINs doubt_sessions to surface `subject` for topic-shift
    detection in ask_doubt(). Downstream callers are tolerant of the extra key.
    """
    try:
        row = await pool.fetchrow(
            """
            SELECT db.doubt_block_id, db.doubt_session_id, db.topic,
                   db.hint_level, db.solved, db.misconception_id,
                   ds.subject
            FROM doubt_blocks db
            LEFT JOIN doubt_sessions ds ON ds.id = db.doubt_session_id
            WHERE db.study_session_id = $1
              AND db.ended_at IS NULL
              AND db.solved = FALSE
            ORDER BY db.started_at DESC
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
    """Close a doubt block, fire summarizer, and (if student engaged but didn't
    solve) fire a genome update with give_up_flag=True so mastery captures
    negative signal from abandoned sessions.

    Why: previously `_genome_update_task` fired ONLY on resolved=True. Students
    rarely click "Got it!", so 98% of doubt_blocks produced no mastery signal
    (confirmed: 83/84 concept_mastery rows stuck at 0). Now any block with
    hint_level >= 1 (student engaged) produces a signal on close.

    v0.20.2: passes `engine` through to _genome_update_task so the
    block-close drift reclassify can run.
    """
    block = await pool.fetchrow(
        """
        UPDATE doubt_blocks
        SET ended_at = NOW(), solved = $2
        WHERE doubt_block_id = $1
        RETURNING doubt_session_id, hint_level, misconception_id
        """,
        uuid.UUID(doubt_block_id),
        solved,
    )
    asyncio.create_task(engine.summarize_doubt_block(doubt_block_id))

    # Fire mastery update for abandoned sessions where the student actually
    # engaged with at least one hint. Resolved=True path already fires its
    # own genome update at the call site, so skip here to avoid double-writing.
    if block and not solved and (block["hint_level"] or 0) >= 1:
        asyncio.create_task(
            _genome_update_task(
                pool,
                str(block["doubt_session_id"]),
                give_up_flag=True,
                misconception_id=block["misconception_id"],
                engine=engine,
            )
        )


# ── background genome update ──────────────────────────────────────────────────

# Performance score mapping: hint level reached → how well the student did
_HINT_PERF_MAP = {
    0: 1.0,   # solved from Socratic question alone — excellent
    1: 0.90,  # needed 1 conceptual nudge
    2: 0.75,  # needed structural hint
    3: 0.55,  # needed partial solution
}
_GIVE_UP_PERF = 0.10    # student gave up — minimal positive signal


async def _mock_genome_update_task(
    pool,
    student_id: str,
    concept_ids: list,
    correct: bool,
    topic: str,
) -> None:
    """
    Full mastery pipeline for mock test submissions — mirrors _genome_update_task
    but takes explicit performance data instead of looking up a doubt_session.

    Runs the same 3-step pipeline as _genome_update_task:
      1. INSERT session_terminal event (session_type='mock') → feeds pedagogy_drift_report
      2. UPSERT concept_mastery EMA (α=0.7) → same formula as doubt sessions
      3. Update persona profile + re-infer scaffolding every 5 sessions

    This replaces the raw update_concept_mastery() call in mock.py (Rule 1 fix).
    The deliberate difference from _genome_update_task: no misconception penalty or
    confidence modifier — mock tests don't capture those signals.
    """
    from app.services.mastery import update_concept_mastery

    try:
        student_uuid = uuid.UUID(student_id)
    except ValueError:
        logger.warning("_mock_genome_update_task: invalid student_id %s", student_id)
        return

    try:
        performance: float = 1.0 if correct else 0.0

        # ── 1. INSERT session_terminal event (session_type='mock') ───────────
        await pool.execute(
            """
            INSERT INTO session_events
                (session_id, event_type, student_id, session_type,
                 time_to_solve_seconds, max_hint_level_used,
                 mistake_forensics_tag, give_up_flag, misconception_detected, payload)
            VALUES (gen_random_uuid(), $1, $2, $3,
                    NULL, 0, NULL, FALSE, FALSE, $4::jsonb)
            """,
            "session_terminal",
            student_uuid,
            "mock",
            json.dumps({"resolved": correct, "topic": topic, "source": "mock_test"}),
        )

        # ── 2. UPSERT concept_mastery (EMA α=0.7) ────────────────────────────
        for concept_id in (concept_ids or []):
            try:
                result = await update_concept_mastery(
                    pool=pool,
                    student_id=student_uuid,
                    concept_id=concept_id,
                    performance_score=performance,
                )
                if result is None:
                    # Row missing → seed at baseline for new concept
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
                        1 if not correct else 0,
                    )
            except Exception as exc:
                logger.warning("Mock mastery update failed for concept=%s: %s", concept_id, exc)

        # ── 3. Update persona profile + maybe re-infer scaffolding ───────────
        try:
            from app.services.memory.context import (
                get_persona_profile,
                update_persona_profile,
                infer_scaffolding_level,
                get_sessions_count,
            )
            current_profile = await get_persona_profile(student_id, pool)
            depth_score = float(current_profile.get("interaction_depth_score", 0.0))
            new_depth = min(1.0, depth_score + 0.05) if correct else max(0.0, depth_score - 0.02)
            await update_persona_profile(student_id, {"interaction_depth_score": new_depth}, pool)

            # Re-infer scaffolding level every 5 sessions (same cadence as doubt sessions)
            sessions_count = await get_sessions_count(student_id, pool)
            if sessions_count > 0 and sessions_count % 5 == 0:
                await infer_scaffolding_level(student_id, pool)
        except Exception as persona_exc:
            logger.warning("Mock persona update failed (non-fatal): %s", persona_exc)

        logger.info(
            "Mock genome updated: student=%s concepts=%d correct=%s",
            student_id, len(concept_ids or []), correct,
        )

    except Exception as exc:
        logger.error("_mock_genome_update_task failed for student %s: %s", student_id, exc)


async def _genome_update_task(
    pool,
    doubt_session_id: str,
    give_up_flag: bool = False,
    mistake_tag: Optional[str] = None,
    session_type: str = "doubt",
    student_confidence: Optional[str] = None,  # low / medium / high
    misconception_id: Optional[str] = None,    # ID from misconceptions.py if detected
    engine = None,                              # v0.20.2: optional, enables block-close reclassify
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

        # ── v0.20.2 backstop: dominant-topic drift signal ────────────────────
        # Auto-segmentation in /doubt/ask handles in-flight pivots. This
        # block-close reclassify is the safety net: if the conversation
        # drifted gradually without triggering a topic shift, log it so we
        # can audit attribution accuracy. We do NOT mutate concept_ids
        # here — that would require a fresh RAG pass which is too costly.
        # If beta shows >5% drift rate, v0.21 will re-derive concept_ids.
        drift_topic: Optional[str] = None
        if engine is not None:
            try:
                drift = await _reclassify_block_topic(engine, pool, doubt_session_id)
                if drift:
                    drift_topic = drift.get("topic")
                    logger.warning(
                        "block-close drift detected: stamped=%s dominant=%s "
                        "(session=%s) — concept_ids unchanged for v0.20.x",
                        topic, drift_topic, doubt_session_id,
                    )
            except Exception as exc:
                logger.warning("block-close reclassify skipped: %s", exc)

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
            json.dumps({
                "resolved": resolved,
                "topic": topic,
                "drift_topic": drift_topic,    # v0.20.2 — null when no drift
                "misconception_id": misconception_id,
            }),
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


async def _write_session_metrics(
    pool,
    study_session_id: Optional[str],
    doubt_session_id: Optional[str],
    subject: str,
    rag: dict,
) -> None:
    """
    Fire-and-forget: write RAG telemetry to session_metrics.
    Called after every AgenticRetriever.run() in ask_doubt / ask_doubt_stream / get_hint.
    Never raises — errors are logged as warnings.
    """
    try:
        study_uuid = uuid.UUID(study_session_id) if study_session_id else None
        doubt_uuid = uuid.UUID(doubt_session_id) if doubt_session_id else None

        await pool.execute(
            """
            INSERT INTO session_metrics
              (study_session_id, doubt_session_id, subject,
               retrieval_latency_ms, agent_steps, chunks_retrieved,
               has_similar_problem, tool_trace)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            study_uuid,
            doubt_uuid,
            subject,
            rag.get("retrieval_latency_ms", 0),
            len(rag.get("tool_trace", [])),
            rag.get("chunk_count", 0),
            rag.get("similar_problem") is not None,
            json.dumps(rag.get("tool_trace", [])),
        )
    except Exception as exc:
        logger.warning("_write_session_metrics failed (non-fatal): %s", exc)


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

    1. Classify intent (greeting, meta, emotional, out_of_scope, subject_doubt, continuation)
    2. Non-subject intents → immediate response, NO DB writes
    3. continuation → delegate to get_hint via active block's doubt_session_id
    4. subject_doubt → start new session + create doubt block
    """
    engine = request.app.state.socratic_engine
    pool = request.app.state.db_pool

    # ── v0.20.5: opportunistic mastery-update for tab-closers ─────────────────
    # Before processing this request, close any idle-too-long blocks/sessions
    # so their _genome_update_task fires. Best-effort, never blocks.
    try:
        n = await _autoclose_idle_blocks(pool, engine, current_student_id)
        if n:
            logger.info("ask_doubt: pre-close fired for %d idle block(s)", n)
        await _autoclose_idle_study_sessions(pool, current_student_id)
    except Exception as exc:
        logger.warning("ask_doubt: pre-close skipped (non-fatal): %s", exc)

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
        intent = "subject_doubt"
        logger.info("topic_lock=%r → bypassing intent classifier, forcing subject_doubt", body.topic_lock)
    else:
        intent = await engine.classify_intent(question, has_active_block, subject=body.subject or "Physics")
        logger.info("Intent classified: %s (active_block=%s)", intent, has_active_block)

    # ── 2c. FIX A3 (2026-04-18): safety net for mis-classified continuations ──
    # If the student has an active unsolved doubt block AND the message is a
    # short reply (< 100 chars), and the classifier returned `explanation` or
    # `subject_doubt`, treat it as a continuation instead. This prevents the
    # "0 doubts asked" context-loss bug where short replies like
    # "second derivative of f(x)" got routed to `handle_non_physics_intent`
    # → no doubt_block, no history, no topic_lock injection.
    if (
        has_active_block
        and active_block
        and intent in ("explanation", "subject_doubt")
        and question and len(question.strip()) < 100
        # "short reply" means: no new problem markers like `find`, `calculate`,
        # `solve`, no standalone numbers like "5 kg" etc. — it's a hint answer.
        and not re.search(r'\b(find|calculate|solve|prove|evaluate|compute)\b', question.lower())
    ):
        logger.info(
            "FIX A3 continuation safety net: intent=%s question=%r → routing as continuation",
            intent, question[:60],
        )
        intent = "continuation"

    # ── 2d. v0.20 dual-loop: topic-shift demotion (Mode 2) ─────────────────────
    # Symmetric to FIX A3. If the message LOOKS like a new question AND
    # classifies to a different topic/subject than the active block, demote
    # continuation → subject_doubt so the existing path at line ~745 closes
    # the old block and opens a new one (correct mastery attribution).
    # Skipped when topic_lock is set — a locked session should not auto-segment.
    if (
        has_active_block
        and active_block
        and intent == "continuation"
        and not body.topic_lock
        and question
    ):
        shifted = await _detect_topic_shift(engine, question, active_block)
        if shifted:
            logger.info(
                "v0.20 topic-shift: demoting continuation → subject_doubt "
                "(block=%s, question=%r, old_subject=%s, old_topic=%s)",
                active_block.get("doubt_block_id"), question[:60],
                active_block.get("subject"), active_block.get("topic"),
            )
            intent = "subject_doubt"

    # ── 3. Non-subject intents → immediate response, NO DB writes ─────────────
    # v0.21: `explanation` intent REMOVED from this bucket. Previously short
    # concept queries like "what is atom?" / "what is log?" / "what's a mole?"
    # routed to handle_non_physics_intent() → returned a concept explanation
    # with session_id=None → no doubt_block opened → no mastery tracked. The
    # Knowledge Genome never saw the student touch the concept.
    #
    # Diagnostic 2026-04-23 bug #2: 0 mastery-tracked sessions from the 6
    # short-form concept queries in the 100-prompt set. Fix: let explanation
    # fall through to the full start_session path so RAG + concept-id lookup
    # + mastery writes happen. The engine's Socratic response to "what is
    # atom?" is pedagogically stronger than a lecture anyway ("what do you
    # already know about atoms?") — this aligns response style with UpMyRank's
    # ask-don't-tell thesis.
    if intent in ("greeting", "meta", "meta_identity", "meta_pricing", "meta_competitor",
                  "emotional", "out_of_scope", "conversational"):
        result = await engine.handle_non_physics_intent(intent, question)
        return result

    # v0.21: explanation intent is handled as a lighter variant of subject_doubt.
    # When no study_session_id is present, fall back to the legacy concept-explain
    # response (keeps the classic "what can you do?" style Q&A for unauth'd or
    # pre-session usage). When a study_session IS present, fall through to the
    # start_session path below so mastery is tracked.
    if intent == "explanation" and not body.study_session_id:
        logger.info(
            "v0.21 explanation without study_session → legacy handle_non_physics_intent (q=%r)",
            question[:80],
        )
        result = await engine.handle_non_physics_intent(intent, question, subject=body.subject)
        return result

    if intent == "explanation":
        logger.info(
            "v0.21 explanation WITH study_session → routing through start_session for mastery tracking (q=%r)",
            question[:80],
        )
        # Fall through — the same start_session path as subject_doubt handles it

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
                    "Ask me a Physics, Chemistry, or Maths question to get started!"
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
                    engine=engine,
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

    # ── 5. New subject doubt ──────────────────────────────────────────────────
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

    # Fire-and-forget RAG metrics write
    _rag_m = result.get("_rag_metrics")
    if _rag_m:
        asyncio.create_task(_write_session_metrics(
            pool=pool,
            study_session_id=body.study_session_id,
            doubt_session_id=result.get("session_id"),
            subject=_rag_m.get("subject", body.subject),
            rag=_rag_m,
        ))

    # Create doubt block if within a study session
    doubt_block_id = None
    if body.study_session_id:
        topic = result.get("analysis", {}).get("topic", body.subject or "General")
        doubt_block_id = await _create_doubt_block(
            pool,
            body.study_session_id,
            current_student_id,
            uuid.UUID(result["session_id"]),
            topic,
            student_confidence=body.student_confidence,
        )
        # v0.20.8: stamp misconception_id on the block if engine.start_session
        # detected one on the initial doubt. Mirrors the continuation-path
        # write at line ~1120 so _genome_update_task picks up the 1.5× penalty
        # when the block closes — the whole reason we bothered detecting.
        _mc_id_new = result.get("misconception_id")
        if _mc_id_new and doubt_block_id:
            try:
                await pool.execute(
                    """
                    UPDATE doubt_blocks
                    SET misconception_detected = TRUE,
                        misconception_id       = $1
                    WHERE doubt_block_id = $2
                    """,
                    _mc_id_new, doubt_block_id,
                )
            except Exception as exc:
                logger.warning(
                    "v0.20.8 stamp misconception_id on new block failed (non-fatal): %s", exc,
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
        "intent": "subject_doubt",
        "doubt_block_id": doubt_block_id,
        "doubt_block_topic": result.get("analysis", {}).get("topic", body.subject or "General"),
        "doubt_block_number": doubt_count,
        **result,
    }


@router.post("/hint")
async def get_hint(
    body: HintRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_student_id: str = Depends(get_current_student_id),
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

    # v0.20.5 — autoclose stale blocks for this student before processing
    # (so accumulated mastery from abandoned earlier sessions actually fires).
    try:
        await _autoclose_idle_blocks(pool, engine, current_student_id)
        await _autoclose_idle_study_sessions(pool, current_student_id)
    except Exception as exc:
        logger.warning("get_hint: pre-close skipped (non-fatal): %s", exc)

    # Coalesce student_attempt → student_response. These are two separate fields
    # on HintRequest for historical reasons (attempt was added later for "Got it!"
    # logging); but the Socratic engine only looks at student_response. Without
    # this coalesce, clients sending student_attempt produced empty student_response,
    # which disabled the response analyzer entirely (including answer_check).
    _effective_student_response = body.student_response or body.student_attempt
    if body.student_attempt:
        logger.info(
            "Student attempt before full solution (session=%s): %.200s",
            body.session_id, body.student_attempt,
        )

    # FIX #1 (2026-04-19): image_url on /doubt/hint — if the student uploads an
    # image (e.g. handwritten attempt) without text, OCR it to populate their
    # response. Previously HintRequest didn't declare image_url → silently dropped.
    if body.image_url and not (_effective_student_response and _effective_student_response.strip()):
        try:
            extracted = await engine.extract_question_from_image(body.image_url)
            if extracted and extracted.strip():
                _effective_student_response = extracted.strip()
                logger.info(
                    "hint: OCR'd image (session=%s): %.120s",
                    body.session_id, _effective_student_response,
                )
        except Exception as exc:
            logger.warning("hint: image OCR failed (non-fatal): %s", exc)

    try:
        result = await engine.get_hint(
            session_id=body.session_id,
            student_response=_effective_student_response,
            jump_to_full=body.jump_to_full_solution,
            student_resolved=body.student_resolved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("SocraticEngine.get_hint failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Fire-and-forget RAG metrics write (hint turn)
    _rag_m_hint = result.get("_rag_metrics")
    if _rag_m_hint:
        asyncio.create_task(_write_session_metrics(
            pool=pool,
            study_session_id=body.study_session_id,
            doubt_session_id=body.session_id,
            subject=_rag_m_hint.get("subject", "Physics"),
            rag=_rag_m_hint,
        ))

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
                # Genome update fires asynchronously after the response is sent.
                # FIX #2 (2026-04-19): plumb student_confidence through so the
                # confidence-weighted mastery modifier (engine _genome_update_task)
                # fires on hint-path resolutions too, not just on /doubt/ask.
                background_tasks.add_task(
                    _genome_update_task,
                    pool,
                    body.session_id,
                    body.give_up_flag,
                    body.mistake_tag,
                    student_confidence=body.student_confidence,
                    misconception_id=block.get("misconception_id") or _mc_id_hint,
                    engine=engine,
                )
            result["doubt_block_id"] = str(block["doubt_block_id"])

    return result


# ── v0.20.2: manual "new doubt" lever ────────────────────────────────────────

class NewDoubtRequest(BaseModel):
    study_session_id: str


@router.post("/new")
async def start_new_doubt(
    body: NewDoubtRequest,
    request: Request,
    current_student_id: str = Depends(get_current_student_id),
):
    """
    Manual segmentation lever — closes the active doubt_block (if any) so
    the next question opens a fresh block. Used by the "+ New doubt" button
    in the chat header.

    Response is intentionally minimal — clients just need to know whether a
    block was closed so they can clear local hint-state UI.
    """
    pool = request.app.state.db_pool
    engine = request.app.state.socratic_engine

    try:
        sid_uuid = uuid.UUID(body.study_session_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid study_session_id")

    active = await _get_active_doubt_block(pool, body.study_session_id)
    if not active:
        return {"closed": False, "reason": "no_active_block"}

    try:
        await _close_doubt_block(
            pool, engine, str(active["doubt_block_id"]), solved=False,
        )
    except Exception as exc:
        logger.exception("/doubt/new close failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "closed": True,
        "closed_block_id": str(active["doubt_block_id"]),
        "study_session_id": body.study_session_id,
    }


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

    Only new subject_doubt sessions are streamed.
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
        intent = "subject_doubt"
    else:
        intent = await engine.classify_intent(question, has_active_block, subject=body.subject or "Physics")

    # ── v0.20 dual-loop: topic-shift demotion (mirrors ask_doubt) ─────────────
    # If the student's message looks like a new question AND classifies to a
    # different topic/subject than the active block, demote continuation →
    # subject_doubt so a fresh doubt_block opens with the correct topic.
    if (
        has_active_block
        and active_block
        and intent == "continuation"
        and not body.topic_lock
        and question
    ):
        try:
            if await _detect_topic_shift(engine, question, active_block):
                logger.info(
                    "v0.20 topic-shift (stream): demoting continuation → subject_doubt "
                    "(block=%s)", active_block.get("doubt_block_id"),
                )
                intent = "subject_doubt"
        except Exception as exc:
            logger.warning("topic-shift check failed (stream): %s", exc)

    # ── Non-streaming path: non-subject / continuation ─────────────────────
    # These are cheap (no LLM or fast LLM) — return as a single SSE event.
    async def _single_event(payload: dict):
        data = _json.dumps({"token": "", "done": True, **payload})
        yield f"data: {data}\n\n"

    if intent in ("greeting", "meta", "meta_identity", "meta_pricing", "meta_competitor",
                  "emotional", "out_of_scope"):
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
                    "Ask me a Physics, Chemistry, or Maths question to get started!"
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
                        engine=engine,
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
                        topic = analysis.get("topic", body.subject or "General")
                        doubt_block_id = await _create_doubt_block(
                            pool,
                            body.study_session_id,
                            current_student_id,
                            uuid.UUID(session_id),
                            topic,
                            student_confidence=body.student_confidence,
                        )
                        # v0.20.8: stamp misconception_id on new block if engine detected one
                        _mc_id_stream = chunk.get("misconception_id")
                        if _mc_id_stream and doubt_block_id:
                            try:
                                await pool.execute(
                                    """
                                    UPDATE doubt_blocks
                                    SET misconception_detected = TRUE,
                                        misconception_id       = $1
                                    WHERE doubt_block_id = $2
                                    """,
                                    _mc_id_stream, doubt_block_id,
                                )
                            except Exception as exc:
                                logger.warning(
                                    "v0.20.8 (stream) stamp misconception_id on new block failed (non-fatal): %s",
                                    exc,
                                )
                    final_metadata = {
                        "intent":           "subject_doubt",
                        "doubt_block_id":   doubt_block_id,
                        "doubt_block_topic": chunk.get("analysis", {}).get("topic", body.subject or "General"),
                        "session_id":       session_id,
                        "mentor_mode":      chunk.get("mentor_mode"),
                        "out_of_scope":     chunk.get("out_of_scope", False),
                        "cache_hit":        chunk.get("cache_hit", False),
                        "is_misconception_correction": chunk.get("is_misconception_correction", False),
                        "misconception_id":  chunk.get("misconception_id"),
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
