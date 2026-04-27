#!/usr/bin/env python3
"""
diagnostic_edge_100.py — multi-turn edge-case diagnostic for UpMyRank.

Loads `scripts/data/diagnostic_edge_100.json` (or any compatible flow set),
drives each flow against the backend (signup → onboard → study_session_start
→ multi-turn doubt_ask/hint loop → session_end which fires the
conversation-arc judge), then queries Supabase for `conversation_arc_quality`
+ `judge_evaluations` + `conversation_turn_quality` aggregates and writes
a unified report.

Two turn types per flow:
  - "scripted":  fixed `prompt` string, sent verbatim
  - "strategy":  `strategy` description fed to a "student LLM" (gpt-4o-mini)
                 which generates a contextually appropriate student reply
                 given the AI's previous response

Each flow stamps `flow_id` + `edge_class` into doubt_sessions.analysis so
the arc judge can filter by run when computing rollups.

Usage:
  cd /Users/ishansrivastava/Desktop/Projects/upmyrank
  /opt/miniconda3/bin/python3.11 -m poetry run python scripts/diagnostic_edge_100.py \\
      --backend https://upmyrank-poc.onrender.com \\
      --run-id edge-2026-04-26 \\
      --classes A,E,F,J,G \\
      --judge-wait-s 60 \\
      --out reports/diagnostic_edge_2026-04-26

Or local:
  BACKEND=http://localhost:8000 python scripts/diagnostic_edge_100.py --classes A

Exit 0 if all flows HTTP-OK and avg arc composite ≥ 0.5; 1 otherwise.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import httpx

try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None  # type: ignore

try:
    import openai  # type: ignore
except ImportError:
    openai = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env():
    p = REPO_ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


_load_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("edge100")


# ── Persona presets ─────────────────────────────────────────────────────────
PERSONAS = {
    "high": {
        "name": "Edge HIGH", "level": "dropper",
        "phys": 90, "chem": 85, "math": 92,
        "easy": ["Kinematics", "Laws of Motion", "Integration", "Differentiation"],
        "hard": ["Electromagnetic Induction"],
        "priority": "Physics", "style": "formula",
    },
    "medium": {
        "name": "Edge MEDIUM", "level": "12th",
        "phys": 62, "chem": 58, "math": 55,
        "easy": ["Kinematics"], "hard": ["Integration"],
        "priority": "Physics", "style": "example",
    },
    "low": {
        "name": "Edge LOW", "level": "11th",
        "phys": 32, "chem": 28, "math": 30,
        "easy": [], "hard": ["Kinematics", "Laws of Motion", "Integration"],
        "priority": "Physics", "style": "analogy",
    },
}


# ── API client ──────────────────────────────────────────────────────────────
class APIClient:
    def __init__(self, backend: str, timeout: float = 180.0):
        self.backend = backend.rstrip("/")
        self._cx = httpx.AsyncClient(timeout=timeout)
        self.token: Optional[str] = None
        self.student_id: Optional[str] = None
        self.email: Optional[str] = None
        # v0.20.11 — keep refresh state so we can re-signup mid-run on 401
        self._refresh_persona: Optional[dict] = None
        self._refresh_run_id: Optional[str] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._cx.aclose()

    def _h(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def signup(self, persona: dict, run_id: str, flow_id: str) -> dict:
        # Tag email so cleanup is one query: edge-{run}-{flow}-{rand}@upmyrank.test
        self.email = f"edge-{run_id}-{flow_id.lower()}-{uuid.uuid4().hex[:5]}@upmyrank.test"
        # Save state so we can refresh the JWT on 401 mid-run (v0.20.11).
        self._refresh_persona = persona
        self._refresh_run_id = run_id
        r = await self._cx.post(
            f"{self.backend}/auth/signup",
            json={
                "name": f"{persona['name']} {flow_id}",
                "email": self.email,
                "password": "Edge#2026Run",
                "exam_type": "JEE",
                "target_year": 2027,
            },
            headers=self._h(),
        )
        r.raise_for_status()
        d = r.json()
        self.token = d["token"]
        self.student_id = d["student_id"]
        return d

    async def onboard(self, persona: dict) -> dict:
        r = await self._cx.post(
            f"{self.backend}/onboarding/submit",
            json={
                "class_level": persona["level"],
                "physics_prev_marks": persona["phys"],
                "chemistry_prev_marks": persona["chem"],
                "maths_prev_marks": persona["math"],
                "easy_topics": persona["easy"],
                "hard_topics": persona["hard"],
                "study_hours_per_day": 4.0,
                "exam_type": "JEE_MAINS",
                "exam_date": "2027-04-01",
                "priority_subject": persona["priority"],
                "learning_preference": persona["style"],
            },
            headers=self._h(),
        )
        r.raise_for_status()
        return r.json()

    async def session_start(self) -> dict:
        r = await self._cx.post(
            f"{self.backend}/session/start",
            json={"student_id": self.student_id},
            headers=self._h(),
        )
        # v0.20.11: re-signup on 401. Supabase JWT lifetime is ~50min on free
        # tier; long edge-runs (>50min) hit token expiry mid-run. Without
        # this, the harness crashed on the 2026-04-27 run at flow 36/50.
        if r.status_code == 401 and self._refresh_persona is not None and self._refresh_run_id is not None:
            log.warning("session_start got 401 — JWT expired; re-signing-up persona")
            await self._refresh_token()
            r = await self._cx.post(
                f"{self.backend}/session/start",
                json={"student_id": self.student_id},
                headers=self._h(),
            )
        r.raise_for_status()
        return r.json()

    async def _refresh_token(self) -> None:
        """Re-sign-up with a new email tag to mint a fresh JWT. Onboards the
        new account so /doubt/ask still works. Used when the original JWT
        expires mid-run (Supabase free tier ~50min token lifetime)."""
        if self._refresh_persona is None or self._refresh_run_id is None:
            return
        old_email = self.email
        # Use a 'rfresh' suffix so cleanup script catches both
        new_tag = f"{self._refresh_run_id}-rfresh-{uuid.uuid4().hex[:4]}"
        self.email = f"edge-{new_tag}-{uuid.uuid4().hex[:5]}@upmyrank.test"
        r = await self._cx.post(
            f"{self.backend}/auth/signup",
            json={
                "name": f"{self._refresh_persona['name']} refresh",
                "email": self.email,
                "password": "Edge#2026Run",
                "exam_type": "JEE", "target_year": 2027,
            },
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()
        d = r.json()
        self.token = d["token"]
        self.student_id = d["student_id"]
        # Re-onboard
        await self.onboard(self._refresh_persona)
        log.info(
            "JWT refreshed: old=%s new=%s student=%s",
            old_email, self.email, self.student_id[:8],
        )

    async def session_end(self, ssid: str) -> dict:
        r = await self._cx.post(
            f"{self.backend}/session/end",
            json={"study_session_id": ssid},
            headers=self._h(),
        )
        if r.status_code == 401 and self._refresh_persona is not None:
            log.warning("session_end got 401 — refreshing JWT")
            await self._refresh_token()
            r = await self._cx.post(
                f"{self.backend}/session/end",
                json={"study_session_id": ssid},
                headers=self._h(),
            )
        r.raise_for_status()
        return r.json()

    async def doubt_ask(self, q: str, ssid: str, subject: str) -> dict:
        r = await self._cx.post(
            f"{self.backend}/doubt/ask",
            json={"question": q, "subject": subject, "study_session_id": ssid},
            headers=self._h(),
        )
        # v0.20.11 — refresh JWT and retry once on 401
        if r.status_code == 401 and self._refresh_persona is not None:
            log.warning("doubt_ask got 401 — refreshing JWT")
            await self._refresh_token()
            r = await self._cx.post(
                f"{self.backend}/doubt/ask",
                json={"question": q, "subject": subject, "study_session_id": ssid},
                headers=self._h(),
            )
        # don't raise — caller inspects status
        return r

    async def doubt_hint(self, session_id: str, student_response: str, ssid: str) -> dict:
        body = {
            "session_id": session_id,
            "student_response": student_response,
            "study_session_id": ssid,
        }
        r = await self._cx.post(f"{self.backend}/doubt/hint", json=body, headers=self._h())
        if r.status_code == 401 and self._refresh_persona is not None:
            log.warning("doubt_hint got 401 — refreshing JWT")
            await self._refresh_token()
            r = await self._cx.post(f"{self.backend}/doubt/hint", json=body, headers=self._h())
        return r


# ── Student LLM (drives strategy turns) ─────────────────────────────────────
_STUDENT_SYSTEM = """\
You are simulating a JEE/NEET student in a tutoring chat. The AI tutor
will respond Socratically (asking guiding questions). Your job: produce
the next plausible STUDENT message based on the strategy given.

Rules:
- Stay in character. Don't break the fourth wall.
- Reply in 1-3 sentences. Match the register a real student uses on a
  chat app (sometimes lowercase, sometimes typos, conversational).
- Follow the strategy faithfully — if it says "insist X is correct" or
  "give up" or "express frustration", do that; do not be overly compliant.
- Don't reveal you're an AI.
- Don't address the AI as "AI" or "assistant" — just respond.

Output JUST the student's next message. No prefix, no quotes, no JSON.
"""


async def student_reply(
    openai_client,
    persona: dict,
    flow_subject: str,
    flow_topic: str,
    strategy: str,
    transcript: list[dict],
    model: str = "gpt-4o-mini",
) -> str:
    """Generate the next student turn using gpt-4o-mini, conditioned on
    the strategy + recent transcript. Always returns a string; on any
    failure returns a safe fallback that still tests something."""
    persona_blurb = (
        f"persona={persona['name']}, level={persona['level']}, "
        f"physics={persona['phys']}, chem={persona['chem']}, maths={persona['math']}, "
        f"learning_preference={persona['style']}"
    )
    convo = "\n".join(
        f"{('STUDENT' if t['role']=='student' else 'AI')}: {t['content'][:500]}"
        for t in transcript[-6:]  # last 6 turns of context
    )
    user_msg = (
        f"{persona_blurb}\n"
        f"Subject: {flow_subject}\nTopic: {flow_topic}\n\n"
        f"Recent transcript:\n{convo}\n\n"
        f"STRATEGY for your next message: {strategy}\n\n"
        "Now produce ONLY the next student message (1-3 sentences, stay in character)."
    )
    try:
        resp = await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _STUDENT_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=200,
            temperature=0.7,
        )
        out = (resp.choices[0].message.content or "").strip()
        # Strip surrounding quotes if the model added them
        if (out.startswith('"') and out.endswith('"')) or \
           (out.startswith("'") and out.endswith("'")):
            out = out[1:-1].strip()
        return out or "I'm not sure, can you walk me through it?"
    except Exception as e:
        log.warning("student_reply LLM failed: %s — using fallback", e)
        return "I'm not sure, can you walk me through it?"


# ── Per-flow runner ─────────────────────────────────────────────────────────
@dataclass
class TurnResult:
    flow_id: str
    edge_class: str
    turn_idx: int
    role: str                  # "student" | "tutor"
    endpoint: Optional[str]    # "ask" | "hint" | None for student turn
    text: str                  # for student turns: what they said; for tutor: AI response
    duration_ms: int = 0
    http_status: Optional[int] = None
    intent: Optional[str] = None
    hint_level: Optional[int] = None
    doubt_block_id: Optional[str] = None
    doubt_session_id: Optional[str] = None
    is_misconception: Optional[bool] = None
    error: Optional[str] = None


async def run_flow(
    client: APIClient,
    openai_client,
    flow: dict,
    study_session_id: str,
    persona: dict,
) -> tuple[list[TurnResult], list[dict]]:
    """Run one multi-turn flow. Returns (turn_results, transcript)."""
    turns_out: list[TurnResult] = []
    transcript: list[dict] = []  # for the student LLM context
    flow_id = flow["flow_id"]
    edge_class = flow["edge_class"]
    subject = flow.get("subject", "Physics")
    topic = flow.get("topic", "General")
    max_turns = int(flow.get("max_turns", 4))

    current_doubt_session: Optional[str] = None
    turn_specs = list(flow["turns"])
    # If there are fewer specs than max_turns and the last spec is "strategy",
    # pad by repeating the last strategy.
    while len(turn_specs) < max_turns:
        last = turn_specs[-1]
        if last.get("type") == "strategy":
            turn_specs.append(dict(last))
        else:
            break

    student_turn_idx = 0
    for spec in turn_specs[:max_turns]:
        # ── Student turn ─────────────────────────────────────────────────
        if spec.get("type") == "scripted":
            student_msg = spec.get("prompt", "")
        else:
            strategy = spec.get("strategy", "Continue the conversation naturally.")
            student_msg = await student_reply(
                openai_client, persona, subject, topic, strategy, transcript,
            )
        log.info(
            "[%s/%d] STUDENT (%s): %r",
            flow_id, student_turn_idx, spec.get("type"), student_msg[:120],
        )
        turns_out.append(TurnResult(
            flow_id=flow_id, edge_class=edge_class, turn_idx=student_turn_idx,
            role="student", endpoint=None, text=student_msg,
        ))
        transcript.append({"role": "student", "content": student_msg})

        # ── AI turn (HTTP call) ──────────────────────────────────────────
        t0 = time.monotonic()
        is_first = current_doubt_session is None
        try:
            if is_first:
                resp = await client.doubt_ask(student_msg, study_session_id, subject)
                endpoint = "ask"
            else:
                resp = await client.doubt_hint(current_doubt_session, student_msg, study_session_id)
                endpoint = "hint"
            dur = int((time.monotonic() - t0) * 1000)
        except Exception as e:
            dur = int((time.monotonic() - t0) * 1000)
            turns_out.append(TurnResult(
                flow_id=flow_id, edge_class=edge_class, turn_idx=student_turn_idx,
                role="tutor", endpoint="ask" if is_first else "hint", text="",
                duration_ms=dur, http_status=None, error=str(e)[:300],
            ))
            log.warning("[%s/%d] TUTOR HTTP exception: %s", flow_id, student_turn_idx, e)
            student_turn_idx += 1
            break

        if resp.status_code != 200:
            text = ""
            try:
                text = resp.text[:300]
            except Exception:
                pass
            turns_out.append(TurnResult(
                flow_id=flow_id, edge_class=edge_class, turn_idx=student_turn_idx,
                role="tutor", endpoint=endpoint, text=text,
                duration_ms=dur, http_status=resp.status_code,
                error=f"HTTP {resp.status_code}: {text}",
            ))
            log.warning(
                "[%s/%d] TUTOR HTTP %d — %s",
                flow_id, student_turn_idx, resp.status_code, text[:120],
            )
            # If the very first call (the "ask") fails (e.g. validation 422),
            # we cannot continue this flow — there's no doubt_session.
            if is_first:
                student_turn_idx += 1
                break
            student_turn_idx += 1
            continue

        body = resp.json()
        ai_text = body.get("response") or body.get("hint") or ""
        if is_first and body.get("session_id"):
            current_doubt_session = body["session_id"]

        analysis = body.get("analysis") or {}
        turns_out.append(TurnResult(
            flow_id=flow_id, edge_class=edge_class, turn_idx=student_turn_idx,
            role="tutor", endpoint=endpoint, text=ai_text[:4000],
            duration_ms=dur, http_status=200,
            intent=body.get("intent"),
            hint_level=body.get("hint_level"),
            doubt_block_id=body.get("doubt_block_id"),
            doubt_session_id=current_doubt_session,
            is_misconception=body.get("is_misconception_correction"),
        ))
        transcript.append({"role": "tutor", "content": ai_text})
        log.info(
            "[%s/%d] TUTOR %s intent=%s hint=%s %dms %d chars",
            flow_id, student_turn_idx, endpoint,
            body.get("intent"), body.get("hint_level"),
            dur, len(ai_text),
        )
        student_turn_idx += 1

    # Stamp flow tags into doubt_sessions.analysis so arc judge can filter.
    if current_doubt_session and asyncpg and os.environ.get("DATABASE_URL"):
        try:
            db_url = os.environ["DATABASE_URL"].split("?")[0]
            conn = await asyncpg.connect(db_url, ssl="require", timeout=30.0)
            await conn.execute(
                """
                UPDATE doubt_sessions
                SET analysis = COALESCE(analysis, '{}'::jsonb)
                             || jsonb_build_object('flow_id', $2::text, 'edge_class', $3::text)
                WHERE id = $1
                """,
                uuid.UUID(current_doubt_session), flow_id, edge_class,
            )
            await conn.close()
        except Exception as e:
            log.warning("flow tag stamp failed for %s: %s", flow_id, e)

    return turns_out, transcript


# ── Driver ──────────────────────────────────────────────────────────────────
async def run_all_flows(
    client: APIClient,
    flows: list[dict],
    persona: dict,
    openai_client,
) -> list[TurnResult]:
    """Run each flow in its own study_session. End the session at flow-end so
    the per-flow arc judge fires."""
    all_turns: list[TurnResult] = []
    for i, flow in enumerate(flows):
        sess = await client.session_start()
        ssid = sess["study_session_id"]
        log.info("=" * 60)
        log.info(
            "flow %d/%d: %s [class=%s, %s, %s] study_session=%s",
            i + 1, len(flows), flow["flow_id"], flow["edge_class"],
            flow.get("subject", "-"), flow.get("topic", "-"),
            ssid[:8],
        )
        flow_turns, _transcript = await run_flow(client, openai_client, flow, ssid, persona)
        all_turns.extend(flow_turns)
        try:
            await client.session_end(ssid)
        except Exception as e:
            log.warning("session_end failed for %s: %s", ssid[:8], e)
        await asyncio.sleep(0.3)  # let arc-judge async tasks queue
    return all_turns


# ── Supabase queries ────────────────────────────────────────────────────────
async def query_supabase(student_id: str, run_id: str) -> dict:
    if asyncpg is None:
        return {"skipped": "asyncpg not installed"}
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"skipped": "DATABASE_URL not set"}
    clean = db_url.split("?")[0]
    try:
        conn = await asyncpg.connect(clean, ssl="require", timeout=30.0)
    except Exception as e:
        return {"error": f"DB connect failed: {e}"}
    try:
        # Arc judge rows for this run (by flow_id stamp)
        arc = await conn.fetch("""
            SELECT caq.flow_id, caq.edge_class, caq.turn_count,
                   caq.coherence, caq.adaptation, caq.context_persistence,
                   caq.closure, caq.pedagogy_arc, caq.back_and_forth_overall,
                   caq.composite_score, caq.rationale, caq.doubt_session_id
            FROM conversation_arc_quality caq
            JOIN doubt_sessions ds ON ds.id = caq.doubt_session_id
            WHERE ds.student_id = $1
            ORDER BY caq.scored_at DESC
        """, uuid.UUID(student_id))
        # Per-response judge rows
        judge = await conn.fetch("""
            SELECT je.doubt_session_id, je.pedagogical_score, je.factual_score,
                   je.context_relevance_score, je.hint_appropriateness_score,
                   je.overall_score
            FROM judge_evaluations je
            JOIN doubt_sessions ds ON ds.id = je.doubt_session_id
            WHERE ds.student_id = $1
        """, uuid.UUID(student_id))
        # Per-turn quality rows
        ctq = await conn.fetch("""
            SELECT ctq.doubt_session_id, ctq.turn_index, ctq.validation_score,
                   ctq.appropriateness, ctq.restart_detected, ctq.single_question
            FROM conversation_turn_quality ctq
            JOIN doubt_sessions ds ON ds.id = ctq.doubt_session_id
            WHERE ds.student_id = $1
        """, uuid.UUID(student_id))
        # Doubt-blocks
        blocks = await conn.fetch("""
            SELECT doubt_block_id, doubt_session_id, topic, hint_level, solved,
                   started_at, ended_at, misconception_detected, misconception_id
            FROM doubt_blocks
            WHERE student_id = $1
            ORDER BY started_at DESC
        """, uuid.UUID(student_id))
        return {
            "arc":    [dict(r) for r in arc],
            "judge":  [dict(r) for r in judge],
            "ctq":    [dict(r) for r in ctq],
            "blocks": [dict(r) for r in blocks],
        }
    finally:
        await conn.close()


# ── Report ──────────────────────────────────────────────────────────────────
def safe_avg(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def safe_pct(num, den):
    return round(100.0 * num / den, 1) if den else None


def fmt_md(run_id: str, meta: dict, turns: list[dict], db: dict, errors: list[dict]) -> str:
    """Build the human-readable markdown report."""
    arc = db.get("arc") or []
    judge = db.get("judge") or []
    ctq = db.get("ctq") or []

    # Group arc by edge_class
    by_class: dict[str, list[dict]] = {}
    for r in arc:
        cls = r.get("edge_class") or "?"
        by_class.setdefault(cls, []).append(r)

    md = []
    md.append(f"# UpMyRank — Edge-Case Conversation-Quality Report ({run_id})")
    md.append("")
    md.append(f"**Generated:** {meta['generated_at']}  •  **Backend:** {meta['backend']}")
    md.append(f"**Persona:** {meta['persona_name']} (`{meta['persona_key']}`)  •  **Student:** {meta['student_id'][:8]}")
    md.append(f"**Flows run:** {meta['n_flows']}  •  **Classes:** {meta['classes_filter']}  •  **Wall time:** {meta['duration_s']}s")
    md.append("")
    md.append("---")
    md.append("")

    # TL;DR
    overall_arc = safe_avg([r["composite_score"] for r in arc])
    overall_judge = safe_avg([r["overall_score"] for r in judge])
    overall_ctq_val = safe_avg([r["validation_score"] for r in ctq])
    overall_ctq_appr = safe_avg([r["appropriateness"] for r in ctq])
    single_q_pct = safe_pct(sum(1 for r in ctq if r["single_question"]), len(ctq)) if ctq else None
    http_total = sum(1 for t in turns if t["role"] == "tutor" and t.get("endpoint"))
    http_ok = sum(1 for t in turns if t["role"] == "tutor" and t.get("http_status") == 200)
    http_pct = safe_pct(http_ok, http_total) if http_total else None

    md.append("## TL;DR — back-and-forth quality")
    md.append("")
    md.append("| Metric | Result | Threshold | Verdict |")
    md.append("|---|---|---|---|")
    md.append(f"| Arc composite (whole-conversation, 0–1) | **{overall_arc}** | ≥ 0.6 | {'✅' if (overall_arc or 0) >= 0.6 else '⚠️'} |")
    md.append(f"| Per-response Judge overall (0–1) | {overall_judge} | ≥ 0.7 | {'✅' if (overall_judge or 0) >= 0.7 else '⚠️'} |")
    md.append(f"| CTQ validation_score avg (0–2) | {overall_ctq_val} | ≥ 1.5 | {'✅' if (overall_ctq_val or 0) >= 1.5 else '⚠️'} |")
    md.append(f"| CTQ appropriateness avg (0–2) | {overall_ctq_appr} | ≥ 1.5 | {'✅' if (overall_ctq_appr or 0) >= 1.5 else '⚠️'} |")
    md.append(f"| CTQ single-question rate | {single_q_pct}% | ≥ 90% | {'✅' if (single_q_pct or 0) >= 90 else '⚠️'} |")
    md.append(f"| HTTP-OK rate (tutor turns) | {http_pct}% | ≥ 99% | {'✅' if (http_pct or 0) >= 99 else '⚠️'} |")
    md.append(f"| Errored turns | {len(errors)} | 0 | {'✅' if len(errors)==0 else '⚠️'} |")
    md.append(f"| Arc rows captured / flows run | {len(arc)} / {meta['n_flows']} | == | {'✅' if len(arc) >= meta['n_flows'] else '⚠️'} |")
    md.append("")

    # Per-class rollup
    md.append("## Per-class rollup (10 classes × 10 flows)")
    md.append("")
    md.append("| Class | Flows scored | Avg arc composite | Avg coherence | Avg adaptation | Avg pedagogy_arc | Avg closure |")
    md.append("|---|---|---|---|---|---|---|")
    for cls in sorted(by_class):
        rows = by_class[cls]
        md.append(
            f"| {cls} | {len(rows)} "
            f"| {safe_avg([r['composite_score'] for r in rows])} "
            f"| {safe_avg([r['coherence'] for r in rows])} "
            f"| {safe_avg([r['adaptation'] for r in rows])} "
            f"| {safe_avg([r['pedagogy_arc'] for r in rows])} "
            f"| {safe_avg([r['closure'] for r in rows])} |"
        )
    md.append("")

    # Failing flows (composite < 0.6) — give detail
    failing = sorted(arc, key=lambda r: r["composite_score"] or 0)[:15]
    failing = [r for r in failing if (r.get("composite_score") or 0) < 0.6]
    md.append(f"## Lowest-scoring flows (composite < 0.6) — top 15")
    md.append("")
    if not failing:
        md.append("None — every flow scored ≥ 0.6 ✅")
    else:
        md.append("| Flow | Class | Composite | c | a | cp | cl | pa | bf | Rationale |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for r in failing:
            md.append(
                f"| {r.get('flow_id') or '-'} | {r.get('edge_class') or '-'} "
                f"| **{r['composite_score']:.3f}** "
                f"| {r['coherence']} | {r['adaptation']} | {r['context_persistence']} "
                f"| {r['closure']} | {r['pedagogy_arc']} | {r['back_and_forth_overall']} "
                f"| {(r.get('rationale') or '')[:200]} |"
            )
    md.append("")

    # Errors
    md.append("## HTTP errors")
    md.append("")
    if not errors:
        md.append("None — every tutor turn returned 200.")
    else:
        for e in errors[:30]:
            md.append(f"- `{e['flow_id']}/{e['turn_idx']}` HTTP {e.get('http_status')} — {(e.get('error') or '')[:200]}")
    md.append("")

    # Bug list
    md.append("## Prioritized bug / regression list")
    md.append("")
    bugs = []
    if (overall_arc or 0) < 0.5:
        bugs.append(("P0", "Arc composite below 0.5 — back-and-forth fundamentally weak", "Inspect lowest-scoring flows + arc rationale text. Likely prompt-engineering work in `app/services/doubt/prompts.py`."))
    for cls, rows in by_class.items():
        cls_avg = safe_avg([r["composite_score"] for r in rows])
        if cls_avg is not None and cls_avg < 0.5:
            bugs.append((
                "P1",
                f"Class {cls} avg composite {cls_avg} (< 0.5)",
                f"Review the 10 flows in class {cls}; rationale text in arc table will point to the failure mode.",
            ))
    if (single_q_pct or 0) < 90:
        bugs.append(("P1", f"Single-question rate {single_q_pct}% (< 90%)", "Review `_enforce_single_question` in `app/services/doubt/engine.py`."))
    if errors:
        bugs.append(("P1" if len(errors) > 3 else "P2", f"{len(errors)} HTTP errors during run", "See HTTP errors section above."))
    if not bugs:
        md.append("None above threshold — all metrics healthy.")
    else:
        md.append("| Priority | Finding | Direction |")
        md.append("|---|---|---|")
        for p, t, d in bugs:
            md.append(f"| **{p}** | {t} | {d} |")
    md.append("")

    md.append("---")
    md.append("")
    md.append(f"*Cleanup: `python scripts/diag_cleanup_test_accounts.py` removes synthetic emails matching `edge-{run_id}-…@upmyrank.test`.*")
    return "\n".join(md)


# ── Main ────────────────────────────────────────────────────────────────────
async def amain():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=os.environ.get("BACKEND", "https://upmyrank-poc.onrender.com"))
    ap.add_argument("--prompts", default=str(REPO_ROOT / "scripts/data/diagnostic_edge_100.json"))
    ap.add_argument("--persona", default="medium", choices=["high", "medium", "low"])
    ap.add_argument("--run-id", default=f"edge-{time.strftime('%Y%m%d-%H%M%S')}")
    ap.add_argument("--classes", default="", help="comma-separated edge_class filter (e.g. A,E,F,J,G); empty = all")
    ap.add_argument("--limit", type=int, default=0, help="stop after N flows (smoke mode)")
    ap.add_argument("--judge-wait-s", type=int, default=60)
    ap.add_argument("--out", default=str(REPO_ROOT / f"reports/diagnostic_edge_{time.strftime('%Y-%m-%d')}"))
    args = ap.parse_args()

    if openai is None:
        log.error("openai not installed — required for student-LLM strategy turns. pip install openai.")
        return 2

    with open(args.prompts) as f:
        dataset = json.load(f)
    flows = dataset["flows"]

    if args.classes:
        wanted = {c.strip().upper() for c in args.classes.split(",") if c.strip()}
        flows = [f for f in flows if f["edge_class"].upper() in wanted]
        log.info("class filter %s → %d flows", sorted(wanted), len(flows))

    if args.limit and args.limit < len(flows):
        flows = flows[:args.limit]
        log.info("limit %d applied — running %d flows", args.limit, len(flows))

    persona = PERSONAS[args.persona]
    log.info("persona = %s (%s)", args.persona, persona["name"])
    log.info("backend = %s", args.backend)
    log.info("run-id  = %s", args.run_id)

    start = time.time()
    openai_client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async with APIClient(args.backend) as client:
        # Single signup for all flows (one persona drives the whole run)
        # Use first flow's id as a tag-pin for the email
        tag = flows[0]["flow_id"] if flows else "all"
        await client.signup(persona, args.run_id, tag)
        await client.onboard(persona)
        log.info("signed up %s — student=%s", client.email, client.student_id[:8])

        # v0.20.11 — wrap in try/except so a mid-run crash still produces a
        # partial report (the 2026-04-27 run lost 35 flows of data because
        # the JWT-401 exception killed the script before report-write).
        all_turns: list[TurnResult] = []
        try:
            all_turns = await run_all_flows(client, flows, persona, openai_client)
        except Exception as exc:
            log.error("run_all_flows crashed mid-run: %s — writing partial report", exc)

    log.info("waiting %ds for async judges (per-response + arc) to land …", args.judge_wait_s)
    await asyncio.sleep(args.judge_wait_s)

    log.info("querying Supabase …")
    db = await query_supabase(client.student_id, args.run_id)

    end = time.time()
    turn_dicts = [asdict(t) for t in all_turns]
    errors = [t for t in turn_dicts if t["role"] == "tutor" and (t.get("error") or t.get("http_status") not in (None, 200))]

    meta = {
        "run_id": args.run_id,
        "backend": args.backend,
        "persona_key": args.persona,
        "persona_name": persona["name"],
        "student_id": client.student_id or "",
        "email": client.email or "",
        "n_flows": len(flows),
        "classes_filter": args.classes or "ALL",
        "duration_s": round(end - start, 1),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_path = out.with_suffix(".json")
    md_path = out.with_suffix(".md")

    with open(json_path, "w") as f:
        json.dump({
            "meta": meta,
            "turns": turn_dicts,
            "db": db,
            "errors": errors,
        }, f, indent=2, default=str)
    log.info("wrote %s", json_path)

    md = fmt_md(args.run_id, meta, turn_dicts, db, errors)
    with open(md_path, "w") as f:
        f.write(md)
    log.info("wrote %s", md_path)

    # Exit code: 0 if arc avg ≥ 0.5 and no errors; 1 otherwise
    arc = db.get("arc") or []
    arc_avg = safe_avg([r["composite_score"] for r in arc]) or 0
    return 0 if (arc_avg >= 0.5 and not errors) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(amain()))
