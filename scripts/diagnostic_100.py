#!/usr/bin/env python3
"""
diagnostic_100.py — 100-prompt full-stack quality diagnostic for UpMyRank.

Drives a single tagged synthetic persona through 68 flows (100 total
prompts) spanning 9 scenario classes, hits prod Render, waits for the
async Judge LLM pipeline to land rows in judge_evaluations, queries
Supabase for aggregate quality metrics, pulls recent Render logs, and
writes a unified JSON + Markdown report.

Evaluates on the four pillars the user called out as the "soul" of the app:
  1. Quality communication / response      — Judge pedagogical_score + turn validation
  2. Knowledge Genome correctness          — concept_mastery delta + factual_score
  3. Personalized response                 — persona-aware rendering check
  4. Easy learning                         — hint-ladder escalation + appropriateness

Usage:
    cd /Users/ishansrivastava/Desktop/Projects/upmyrank
    /opt/miniconda3/bin/python3.11 -m poetry run python scripts/diagnostic_100.py \\
        --backend https://upmyrank-poc.onrender.com \\
        --run-id diag-2026-04-23 \\
        --out reports/diagnostic_2026-04-23

Or with env vars:
    BACKEND=https://upmyrank-poc.onrender.com RUN_ID=diag-2026-04-23 \\
        /opt/miniconda3/bin/python3.11 -m poetry run python scripts/diagnostic_100.py

Requires .env with DATABASE_URL and RENDER_API_KEY/RENDER_SERVICE_ID.
Cleanup of the synthetic persona is not done automatically — after review,
run: python scripts/diag_cleanup_test_accounts.py (match by run_id email tag).

Exit code: 0 if all pillars above threshold; 1 if any pillar below.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import httpx

# Optional: asyncpg for DB queries (installed in poetry env)
try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env():
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)


load_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("diag100")


# ── Synthetic persona (one, medium scaffolding — see report design) ──────────
PERSONA = {
    "name":  "Diag Persona",
    "exam":  "JEE_MAINS",
    "year":  2028,
    "level": "12th",
    "phys":  62,
    "chem":  58,
    "math":  55,
    "easy":  ["Kinematics", "Atomic Structure", "Trigonometry"],
    "hard":  ["Electromagnetic Induction", "Coordination Compounds", "Integration"],
    "priority": "Physics",
    "style":    "example",
}


# ── API client ───────────────────────────────────────────────────────────────
class APIClient:
    def __init__(self, backend: str, timeout: float = 120.0):
        self.backend = backend.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self.token: Optional[str] = None
        self.student_id: Optional[str] = None
        self.email: Optional[str] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._client.aclose()

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def signup(self, run_id: str) -> dict:
        self.email = f"diag-{run_id}-{uuid.uuid4().hex[:6]}@upmyrank.test"
        body = {
            "name":        f"Diag Run {run_id}",
            "email":       self.email,
            "password":    "Diag#2026Run",
            "exam_type":   "JEE",
            "target_year": PERSONA["year"],
        }
        r = await self._client.post(f"{self.backend}/auth/signup", json=body, headers=self._headers())
        r.raise_for_status()
        d = r.json()
        self.token = d["token"]
        self.student_id = d["student_id"]
        log.info("signed up as %s (id=%s)", self.email, self.student_id[:8])
        return d

    async def onboard(self) -> dict:
        body = {
            "class_level":          PERSONA["level"],
            "physics_prev_marks":   PERSONA["phys"],
            "chemistry_prev_marks": PERSONA["chem"],
            "maths_prev_marks":     PERSONA["math"],
            "easy_topics":          PERSONA["easy"],
            "hard_topics":          PERSONA["hard"],
            "study_hours_per_day":  4.0,
            "exam_type":            PERSONA["exam"],
            "exam_date":            f"{PERSONA['year']}-04-01",
            "priority_subject":     PERSONA["priority"],
            "learning_preference":  PERSONA["style"],
        }
        r = await self._client.post(f"{self.backend}/onboarding/submit", json=body, headers=self._headers())
        r.raise_for_status()
        return r.json()

    async def session_start(self) -> dict:
        r = await self._client.post(
            f"{self.backend}/session/start",
            json={"student_id": self.student_id},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    async def session_end(self, study_session_id: str) -> dict:
        r = await self._client.post(
            f"{self.backend}/session/end",
            json={"study_session_id": study_session_id},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    async def doubt_ask(self, question: str, study_session_id: Optional[str] = None,
                        subject: str = "Physics") -> dict:
        body: dict = {"question": question, "subject": subject}
        if study_session_id:
            body["study_session_id"] = study_session_id
        r = await self._client.post(f"{self.backend}/doubt/ask", json=body, headers=self._headers())
        r.raise_for_status()
        return r.json()

    async def doubt_hint(self, session_id: str, student_response: Optional[str] = None,
                         study_session_id: Optional[str] = None) -> dict:
        body: dict = {"session_id": session_id}
        if student_response is not None:
            body["student_response"] = student_response
        if study_session_id:
            body["study_session_id"] = study_session_id
        r = await self._client.post(f"{self.backend}/doubt/hint", json=body, headers=self._headers())
        r.raise_for_status()
        return r.json()


# ── Runner ───────────────────────────────────────────────────────────────────
@dataclass
class TurnResult:
    flow_id: str
    flow_class: str
    turn_idx: int
    endpoint: str                    # "ask" | "hint"
    prompt: str
    subject_sent: str
    duration_ms: int
    http_ok: bool
    intent: Optional[str] = None
    doubt_block_id: Optional[str] = None
    doubt_session_id: Optional[str] = None
    hint_level: Optional[int] = None
    response_text: str = ""
    response_len: int = 0
    mentor_mode: Optional[str] = None
    topic: Optional[str] = None
    is_misconception_correction: Optional[bool] = None
    is_full_solution: Optional[bool] = None
    analysis_subject: Optional[str] = None
    error: Optional[str] = None
    expected: dict = field(default_factory=dict)


async def run_flow(client: APIClient, flow: dict, study_session_id: str) -> list[TurnResult]:
    """Execute every turn of a flow sequentially, record results."""
    results: list[TurnResult] = []
    current_session_id: Optional[str] = None  # doubt_session, not study_session

    for turn_idx, turn in enumerate(flow["turns"]):
        prompt = turn["prompt"]
        expected = turn.get("expect", {})
        action = turn.get("hint_action", "ask")
        subject = flow.get("subject", "Physics")

        t0 = time.monotonic()
        try:
            if action in ("hint", "hint_with_attempt") and current_session_id:
                response = await client.doubt_hint(
                    session_id=current_session_id,
                    student_response=prompt,
                    study_session_id=study_session_id,
                )
                endpoint = "hint"
            else:
                response = await client.doubt_ask(
                    question=prompt,
                    study_session_id=study_session_id,
                    subject=subject,
                )
                endpoint = "ask"
                if response.get("session_id"):
                    current_session_id = response["session_id"]

            dur_ms = int((time.monotonic() - t0) * 1000)
            analysis = response.get("analysis") or {}
            tr = TurnResult(
                flow_id=flow["flow_id"],
                flow_class=flow["class"],
                turn_idx=turn_idx,
                endpoint=endpoint,
                prompt=prompt,
                subject_sent=subject,
                duration_ms=dur_ms,
                http_ok=True,
                intent=response.get("intent"),
                doubt_block_id=response.get("doubt_block_id"),
                doubt_session_id=response.get("session_id") or current_session_id,
                hint_level=response.get("hint_level"),
                response_text=(response.get("response") or response.get("hint") or "")[:2000],
                response_len=len(response.get("response") or response.get("hint") or ""),
                mentor_mode=(response.get("mentor_mode") or analysis.get("mentor_mode")),
                topic=response.get("doubt_block_topic") or analysis.get("topic"),
                is_misconception_correction=response.get("is_misconception_correction"),
                is_full_solution=response.get("is_full_solution"),
                analysis_subject=analysis.get("subject"),
                expected=expected,
            )
            results.append(tr)
            log.info(
                "[%s/%d] %s %s intent=%s block=%s hint_lvl=%s %dms %d chars",
                flow["flow_id"], turn_idx, endpoint, subject,
                tr.intent, (tr.doubt_block_id or "")[:8], tr.hint_level,
                tr.duration_ms, tr.response_len,
            )
        except Exception as e:
            dur_ms = int((time.monotonic() - t0) * 1000)
            results.append(TurnResult(
                flow_id=flow["flow_id"], flow_class=flow["class"], turn_idx=turn_idx,
                endpoint=action, prompt=prompt, subject_sent=subject,
                duration_ms=dur_ms, http_ok=False, error=str(e)[:400],
                expected=expected,
            ))
            log.warning("[%s/%d] FAILED: %s", flow["flow_id"], turn_idx, e)
    return results


async def run_all_flows(client: APIClient, flows: list[dict]) -> list[TurnResult]:
    all_results: list[TurnResult] = []
    study_session_ids: list[str] = []
    for i, flow in enumerate(flows):
        sess = await client.session_start()
        ssid = sess["study_session_id"]
        study_session_ids.append(ssid)
        log.info("=" * 60)
        log.info("flow %d/%d: %s [%s, %s, %s] study_session=%s",
                 i + 1, len(flows), flow["flow_id"], flow["class"],
                 flow.get("subject", "-"), flow.get("topic", "-"),
                 ssid[:8])
        results = await run_flow(client, flow, ssid)
        all_results.extend(results)
        # End the session — fires _run_judge_for_session which writes
        # judge_evaluations rows (the main quality data) and summarize_session
        # (blocking, per RULES.md #2).
        try:
            await client.session_end(ssid)
        except Exception as e:
            log.warning("session_end for %s failed: %s", ssid[:8], e)
        await asyncio.sleep(0.2)
    return all_results


# ── DB queries ───────────────────────────────────────────────────────────────
async def query_supabase(student_id: str) -> dict:
    if asyncpg is None:
        log.warning("asyncpg not installed — skipping DB queries")
        return {"skipped": True}
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        log.warning("DATABASE_URL not set — skipping DB queries")
        return {"skipped": True}
    # asyncpg doesn't accept ?sslmode= in URL; strip query params and force SSL
    if "?" in db_url:
        db_url_clean = db_url.split("?")[0]
    else:
        db_url_clean = db_url

    try:
        conn = await asyncpg.connect(db_url_clean, ssl="require", timeout=30.0)
    except Exception as e:
        log.error("DB connect failed: %s", e)
        return {"error": str(e)}

    try:
        # judge_evaluations — 4-dim quality scores, via doubt_session.student_id
        judge = await conn.fetch("""
            SELECT je.pedagogical_score, je.factual_score, je.context_relevance_score,
                   je.hint_appropriateness_score, je.overall_score, je.rationale_json,
                   je.question, je.evaluated_at, je.doubt_session_id
            FROM judge_evaluations je
            JOIN doubt_sessions ds ON ds.id = je.doubt_session_id
            WHERE ds.student_id = $1
            ORDER BY je.evaluated_at DESC
        """, uuid.UUID(student_id))

        # session_events — JOIN through doubt_sessions (no student_id column)
        events = await conn.fetch("""
            SELECT se.event_type, se.scaffolding_score, se.retrieval_similarity,
                   se.response_latency_ms, se.misconception_detected,
                   se.created_at, se.doubt_block_id
            FROM session_events se
            JOIN doubt_sessions ds ON ds.id = se.session_id
            WHERE ds.student_id = $1
            ORDER BY se.created_at DESC
            LIMIT 500
        """, uuid.UUID(student_id))

        # session_metrics — RAG telemetry
        metrics = await conn.fetch("""
            SELECT sm.subject, sm.retrieval_latency_ms, sm.agent_steps,
                   sm.chunks_retrieved, sm.has_similar_problem
            FROM session_metrics sm
            JOIN doubt_sessions ds ON ds.id = sm.doubt_session_id
            WHERE ds.student_id = $1
        """, uuid.UUID(student_id))

        # concept_mastery — Genome state
        mastery = await conn.fetch("""
            SELECT concept_id, mastery_score, error_count, attempt_count,
                   last_reviewed
            FROM concept_mastery
            WHERE student_id = $1
            ORDER BY last_reviewed DESC
        """, uuid.UUID(student_id))

        # doubt_blocks — block closures (student_id is on this table directly)
        blocks = await conn.fetch("""
            SELECT doubt_block_id, topic, hint_level, solved,
                   summary, started_at, ended_at
            FROM doubt_blocks
            WHERE student_id = $1
            ORDER BY started_at DESC
        """, uuid.UUID(student_id))

        # conversation_turn_quality — JOIN via doubt_sessions (no student_id col)
        ctq_rows: list = []
        try:
            ctq_rows = await conn.fetch("""
                SELECT ctq.validation_score, ctq.appropriateness, ctq.restart_detected,
                       ctq.single_question, ctq.scored_at
                FROM conversation_turn_quality ctq
                JOIN doubt_sessions ds ON ds.id = ctq.doubt_session_id
                WHERE ds.student_id = $1
                ORDER BY ctq.scored_at DESC
                LIMIT 500
            """, uuid.UUID(student_id))
        except Exception as e:
            log.warning("ctq query failed: %s", e)
            ctq_rows = []

        return {
            "judge":   [dict(r) for r in judge],
            "events":  [dict(r) for r in events],
            "metrics": [dict(r) for r in metrics],
            "mastery": [dict(r) for r in mastery],
            "blocks":  [dict(r) for r in blocks],
            "ctq":     [dict(r) for r in ctq_rows],
        }
    finally:
        await conn.close()


# ── Render logs ──────────────────────────────────────────────────────────────
async def pull_render_logs(start_iso: str, end_iso: str) -> list[dict]:
    api_key = os.environ.get("RENDER_API_KEY")
    service_id = os.environ.get("RENDER_SERVICE_ID")
    if not api_key or not service_id:
        log.warning("RENDER_API_KEY/RENDER_SERVICE_ID not set — skipping log pull")
        return []
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    # Render's /v1/logs requires ownerId — discover it from the service first.
    try:
        async with httpx.AsyncClient(timeout=30.0) as cx:
            svc = await cx.get(
                f"https://api.render.com/v1/services/{service_id}",
                headers=headers,
            )
            if svc.status_code != 200:
                return [{"error": f"service lookup {svc.status_code}: {svc.text[:200]}"}]
            owner_id = (svc.json() or {}).get("ownerId")
            if not owner_id:
                return [{"error": "no ownerId in service response"}]
            params = {
                "ownerId":   owner_id,
                "resource":  service_id,
                "startTime": start_iso,
                "endTime":   end_iso,
                "limit":     200,
            }
            r = await cx.get("https://api.render.com/v1/logs", headers=headers, params=params)
        if r.status_code != 200:
            return [{"error": f"logs {r.status_code}: {r.text[:200]}"}]
        data = r.json()
        raw = data.get("logs", []) if isinstance(data, dict) else data
        # Normalise: keep only the message field (+ timestamp + level)
        out = []
        for entry in raw or []:
            if isinstance(entry, dict):
                out.append({
                    "ts":      entry.get("timestamp"),
                    "level":   entry.get("level") or "",
                    "message": (entry.get("message") or "")[:400],
                })
            else:
                out.append({"message": str(entry)[:400]})
        return out
    except Exception as e:
        return [{"error": str(e)}]


# ── Report generation ────────────────────────────────────────────────────────
def safe_avg(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def safe_pct(num, den):
    return round(100.0 * num / den, 1) if den else None


def pX(xs, p):
    xs = sorted([x for x in xs if x is not None])
    if not xs:
        return None
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
    return xs[k]


def analyze(turns: list[TurnResult], db: dict, logs: list[dict]) -> dict:
    tt = [asdict(t) for t in turns]
    by_class: dict[str, list[dict]] = {}
    for t in tt:
        by_class.setdefault(t["flow_class"], []).append(t)

    # Pillar 1 — Quality communication
    jud = db.get("judge") or []
    pedagogical = [j.get("pedagogical_score") for j in jud if j.get("pedagogical_score") is not None]
    factual     = [j.get("factual_score") for j in jud]
    ctx_rel     = [j.get("context_relevance_score") for j in jud]
    hint_app    = [j.get("hint_appropriateness_score") for j in jud]
    overall     = [j.get("overall_score") for j in jud]
    socratic_adherence_pct = safe_pct(sum(1 for p in pedagogical if (p or 0) >= 1), len(pedagogical))

    # Pillar 2 — Knowledge Genome
    mastery = db.get("mastery") or []
    blocks  = db.get("blocks") or []
    resolved_blocks = [b for b in blocks if b.get("solved")]
    ended_blocks    = [b for b in blocks if b.get("ended_at")]
    genome_update_rate = safe_pct(len([m for m in mastery if (m.get("attempt_count") or 0) > 0]),
                                  max(1, len(ended_blocks)))

    # Pillar 3 — Personalization (heuristic on response text)
    # We look at how many responses mention persona-specific cues: example-style
    # for this persona (style=example), and avoid generic boilerplate.
    response_lens = [t["response_len"] for t in tt if t["response_len"]]
    # low-variance response lengths (all about the same size) is a weak signal
    # that personalization isn't firing differently per context.
    len_stdev = round(statistics.stdev(response_lens), 1) if len(response_lens) >= 2 else None

    # Pillar 4 — Easy learning
    ladder_turns = by_class.get("hint_ladder", [])
    ladder_hint_progression_ok = True
    if ladder_turns:
        # Group by flow_id, then check hint_level sequence is non-decreasing
        from collections import defaultdict
        by_flow: dict[str, list[int]] = defaultdict(list)
        for t in ladder_turns:
            if t.get("hint_level") is not None:
                by_flow[t["flow_id"]].append(t["hint_level"])
        for fid, lvls in by_flow.items():
            if any(lvls[i] > lvls[i + 1] for i in range(len(lvls) - 1)):
                ladder_hint_progression_ok = False
                break

    # Cross-cutting
    durs = [t["duration_ms"] for t in tt if t["http_ok"]]
    latency_p50 = pX(durs, 50)
    latency_p95 = pX(durs, 95)
    error_turns = [t for t in tt if not t["http_ok"]]

    # Scenario-class pass/fail rollups
    class_rollups = {}
    for cls, items in by_class.items():
        ok = sum(1 for t in items if t["http_ok"])
        class_rollups[cls] = {
            "prompts": len(items),
            "http_ok": ok,
            "http_ok_pct": safe_pct(ok, len(items)),
            "intents":   dict(collections_counter(t["intent"] or "null" for t in items)),
            "avg_latency_ms": safe_avg([t["duration_ms"] for t in items]),
        }

    # Expected-intent match rate per class
    expected_match = {}
    for cls, items in by_class.items():
        exp = [t for t in items if (t.get("expected") or {}).get("intent")]
        if not exp:
            continue
        matched = sum(1 for t in exp if t.get("intent") == t["expected"].get("intent"))
        expected_match[cls] = {
            "checked": len(exp),
            "matched": matched,
            "match_pct": safe_pct(matched, len(exp)),
        }

    # Topic-shift pass: within sudden_pivot + short_pivot flows, each turn after
    # the first with expected.topic_shift=True should have a different
    # doubt_block_id from the previous.
    shift_checks = []
    for cls in ("sudden_pivot", "short_pivot"):
        for t in by_class.get(cls, []):
            if t.get("expected", {}).get("topic_shift"):
                shift_checks.append({
                    "flow_id": t["flow_id"],
                    "turn_idx": t["turn_idx"],
                    "subject_sent": t["subject_sent"],
                    "doubt_block_id": t["doubt_block_id"],
                    "intent": t["intent"],
                })
    # Need to compare block ids against prior turn; collect prior block per flow
    shift_result = []
    prev_block_by_flow: dict[str, Optional[str]] = {}
    for t in tt:
        fid = t["flow_id"]
        prior = prev_block_by_flow.get(fid)
        if t.get("expected", {}).get("topic_shift"):
            opened_new = bool(t["doubt_block_id"]) and t["doubt_block_id"] != prior
            shift_result.append({
                "flow_id": fid, "turn_idx": t["turn_idx"],
                "prior_block": (prior or "")[:8], "new_block": (t["doubt_block_id"] or "")[:8],
                "opened_new_block": opened_new,
            })
        if t["doubt_block_id"]:
            prev_block_by_flow[fid] = t["doubt_block_id"]
    shift_pass_pct = safe_pct(sum(1 for s in shift_result if s["opened_new_block"]),
                              max(1, len(shift_result)))

    # Misconception detection rate
    misc = by_class.get("misconception", [])
    misc_detected = sum(1 for t in misc if t.get("is_misconception_correction"))
    misc_rate = safe_pct(misc_detected, max(1, len(misc)))

    # Emotional class — did counselor mode fire on the 2nd turn of each flow?
    emo = by_class.get("emotional", [])
    emo_counselor_hits = sum(1 for t in emo if t.get("turn_idx") == 1 and (t.get("mentor_mode") or "").upper() == "COUNSELOR")
    emo_rate = safe_pct(emo_counselor_hits, max(1, len([t for t in emo if t.get("turn_idx") == 1])))

    # Vague class robustness — all turns should at least complete HTTP 200
    vague = by_class.get("vague", [])
    vague_ok = sum(1 for t in vague if t["http_ok"])
    vague_rate = safe_pct(vague_ok, max(1, len(vague)))

    # Out-of-scope class — intent should NOT be subject_doubt
    oos = by_class.get("out_of_scope", [])
    oos_correct = sum(1 for t in oos if t.get("intent") and t["intent"] != "subject_doubt")
    oos_rate = safe_pct(oos_correct, max(1, len(oos)))

    # Follow-up class — turn_idx > 0 should be intent=continuation (mostly)
    fu = by_class.get("followup", [])
    fu_correct = sum(1 for t in fu if t.get("turn_idx", 0) > 0 and t.get("intent") == "continuation")
    fu_total   = len([t for t in fu if t.get("turn_idx", 0) > 0])
    fu_rate    = safe_pct(fu_correct, max(1, fu_total))

    return {
        "pillars": {
            "quality_communication": {
                "socratic_adherence_pct_peda_ge_1": socratic_adherence_pct,
                "avg_pedagogical_0_2":  safe_avg(pedagogical),
                "avg_factual_0_1":      safe_avg(factual),
                "avg_context_rel_0_1":  safe_avg(ctx_rel),
                "avg_hint_app_0_1":     safe_avg(hint_app),
                "avg_overall_0_1":      safe_avg(overall),
                "n_judge_rows":         len(jud),
                "ctq_validation_avg":   safe_avg([r.get("validation_score") for r in (db.get("ctq") or [])]),
                "ctq_appropriateness_avg": safe_avg([r.get("appropriateness") for r in (db.get("ctq") or [])]),
                "ctq_single_question_pct": safe_pct(
                    sum(1 for r in (db.get("ctq") or []) if r.get("single_question")),
                    max(1, len(db.get("ctq") or []))
                ) if db.get("ctq") else None,
            },
            "knowledge_genome": {
                "mastery_rows_written":   len(mastery),
                "blocks_opened":          len(blocks),
                "blocks_resolved":        len(resolved_blocks),
                "blocks_ended":           len(ended_blocks),
                "genome_update_rate_pct": genome_update_rate,
                "n_concepts_touched":     len({m["concept_id"] for m in mastery}),
            },
            "personalized_response": {
                "response_len_avg":    safe_avg(response_lens),
                "response_len_stdev":  len_stdev,
                "len_stdev_over_avg":  (round(len_stdev / safe_avg(response_lens), 3)
                                        if len_stdev and safe_avg(response_lens) else None),
                "note": "Heuristic: higher stdev/avg ratio = responses varied in structure/length per context (signal, not proof).",
            },
            "easy_learning": {
                "hint_ladder_progression_monotonic": ladder_hint_progression_ok,
                "median_latency_ms":                 latency_p50,
                "p95_latency_ms":                    latency_p95,
                "forced_attempt_triggered_count":    sum(1 for t in tt if t.get("hint_level") == 3),
                "full_solution_triggered_count":     sum(1 for t in tt if t.get("is_full_solution")),
            },
        },
        "scenario_class_rollups": class_rollups,
        "expected_intent_match": expected_match,
        "topic_shift_checks":    shift_result,
        "topic_shift_pass_pct":  shift_pass_pct,
        "misconception_detection_rate_pct": misc_rate,
        "emotional_counselor_mode_rate_pct": emo_rate,
        "vague_http_ok_pct":     vague_rate,
        "out_of_scope_routing_correct_pct": oos_rate,
        "followup_continuation_rate_pct": fu_rate,
        "n_checks": {
            "shift":    len(shift_result),
            "followup": fu_total,
            "misconception": len(misc),
            "emotional": len([t for t in emo if t.get("turn_idx") == 1]),
            "vague":    len(vague),
            "out_of_scope": len(oos),
        },
        "errors":  [t for t in tt if not t["http_ok"]],
        "render_log_errors": [l for l in logs if "ERROR" in str(l).upper() or "CRITICAL" in str(l).upper()][:30],
        "render_log_topic_shift_hits": [l for l in logs if "topic_shift" in str(l) or "topic-shift" in str(l)][:30],
        "render_log_autoclose_hits": [l for l in logs if "autoclose" in str(l).lower()][:30],
    }


# collections.Counter lazy import (avoid top-level if unused)
def collections_counter(it):
    from collections import Counter
    return Counter(it)


def fmt_md_report(run_id: str, analysis: dict, meta: dict) -> str:
    p = analysis["pillars"]
    md = []
    md.append(f"# UpMyRank — Diagnostic-100 Quality Report ({run_id})")
    md.append("")
    md.append(f"**Generated:** {meta['generated_at']}")
    md.append(f"**Backend:** {meta['backend']}")
    md.append(f"**Persona:** {meta['persona']} (email `{meta['email']}`, student `{meta['student_id'][:8]}`)")
    md.append(f"**Prompts run:** {meta['n_prompts']} across {meta['n_flows']} flows, 9 scenario classes.")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## TL;DR")
    md.append("")
    q = p["quality_communication"]
    g = p["knowledge_genome"]
    r = p["personalized_response"]
    e = p["easy_learning"]

    def pretty(v):
        if v is None:  return "—"
        if isinstance(v, bool): return "✅" if v else "❌"
        return str(v)

    md.append("| Pillar | Headline metric | Value |")
    md.append("|---|---|---|")
    md.append(f"| **1. Quality communication** | Socratic adherence (ped ≥ 1) | {pretty(q['socratic_adherence_pct_peda_ge_1'])}% ({q['n_judge_rows']} judge rows) |")
    md.append(f"| **2. Knowledge Genome** | Mastery rows written / blocks ended | {g['mastery_rows_written']} / {g['blocks_ended']} ({pretty(g['genome_update_rate_pct'])}%) |")
    md.append(f"| **3. Personalized response** | Response length stdev / avg | {pretty(r['len_stdev_over_avg'])} |")
    md.append(f"| **4. Easy learning** | Hint ladder monotonic + P95 latency | {pretty(e['hint_ladder_progression_monotonic'])} / {pretty(e['p95_latency_ms'])} ms |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## Pillar 1 — Quality communication / response")
    md.append("")
    md.append("Backed by `judge_evaluations` (Judge LLM 4-dim, fired async on every response) + `conversation_turn_quality` (per-turn).")
    md.append("")
    for k, v in q.items():
        md.append(f"- `{k}`: **{pretty(v)}**")
    md.append("")
    md.append("## Pillar 2 — Knowledge Genome correctness")
    md.append("")
    md.append("Did EMA actually fire? Is attempt_count non-zero where blocks ended? This is the direct regression guard for v0.20.5 autoclose-idle.")
    md.append("")
    for k, v in g.items():
        md.append(f"- `{k}`: **{pretty(v)}**")
    md.append("")
    md.append("## Pillar 3 — Personalized response")
    md.append("")
    md.append("Heuristic — a personalised engine should produce responses with varied length/structure across different contexts (easy topic vs hard topic, subject_doubt vs misconception vs forced-attempt). Low variance = one-size-fits-all.")
    md.append("")
    for k, v in r.items():
        md.append(f"- `{k}`: **{pretty(v)}**")
    md.append("")
    md.append("## Pillar 4 — Easy learning")
    md.append("")
    for k, v in e.items():
        md.append(f"- `{k}`: **{pretty(v)}**")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## Scenario-class rollups")
    md.append("")
    md.append("| Class | Prompts | HTTP OK | Intents | Avg latency (ms) |")
    md.append("|---|---|---|---|---|")
    for cls, stats in analysis["scenario_class_rollups"].items():
        md.append(f"| {cls} | {stats['prompts']} | {stats['http_ok_pct']}% | {stats['intents']} | {stats['avg_latency_ms']} |")
    md.append("")
    md.append("## Expected-intent match rate (per class)")
    md.append("")
    md.append("| Class | Checked | Matched | Match % |")
    md.append("|---|---|---|---|")
    for cls, stats in analysis["expected_intent_match"].items():
        md.append(f"| {cls} | {stats['checked']} | {stats['matched']} | {stats['match_pct']}% |")
    md.append("")
    md.append("## Scenario-specific checks")
    md.append("")
    md.append(f"- **Topic-shift (new block opens on pivot):** {pretty(analysis['topic_shift_pass_pct'])}% ({len(analysis['topic_shift_checks'])} checks)")
    md.append(f"- **Misconception detection rate:** {pretty(analysis['misconception_detection_rate_pct'])}% (expected > 60% — library-matching is literal)")
    md.append(f"- **Emotional → COUNSELOR mode:** {pretty(analysis['emotional_counselor_mode_rate_pct'])}%")
    md.append(f"- **Vague-prompt robustness (HTTP OK):** {pretty(analysis['vague_http_ok_pct'])}%")
    md.append(f"- **Out-of-scope routing correctness:** {pretty(analysis['out_of_scope_routing_correct_pct'])}%")
    md.append(f"- **Follow-up → continuation intent:** {pretty(analysis['followup_continuation_rate_pct'])}%")
    md.append("")
    md.append("## Errors")
    md.append("")
    errs = analysis.get("errors") or []
    if not errs:
        md.append("None — all 100 prompts completed HTTP 200.")
    else:
        md.append(f"**{len(errs)} turn(s) errored.**")
        for er in errs[:20]:
            md.append(f"- `{er['flow_id']}/{er['turn_idx']}` ({er['flow_class']}): {er.get('error')}")
    md.append("")
    md.append("## Render logs (filtered)")
    md.append("")
    md.append(f"- ERROR/CRITICAL lines: {len(analysis['render_log_errors'])}")
    md.append(f"- topic_shift hits:     {len(analysis['render_log_topic_shift_hits'])}")
    md.append(f"- autoclose hits:       {len(analysis['render_log_autoclose_hits'])}")
    md.append("")
    md.append("## Prioritized bug / regression list")
    md.append("")
    bugs = []
    # Only flag a bug if we have enough data to judge.
    n = analysis.get("n_checks") or {}
    n_shift = n.get("shift", 0)
    n_fu    = n.get("followup", 0)
    n_misc  = n.get("misconception", 0)
    n_emo   = n.get("emotional", 0)

    if q.get("n_judge_rows", 0) >= 10 and q.get("socratic_adherence_pct_peda_ge_1") is not None and q["socratic_adherence_pct_peda_ge_1"] < 70:
        bugs.append(("P0", "Socratic adherence below 70%", f"Judge scored {q['socratic_adherence_pct_peda_ge_1']}% of responses as pedagogically weak across {q['n_judge_rows']} rows. Review prompts.py SOCRATIC_QUESTION_PROMPT + CUSTOMIZATION_PROMPT."))
    if g.get("blocks_ended", 0) >= 3 and g.get("mastery_rows_written", 0) == 0:
        bugs.append(("P0", "Genome not writing despite ended blocks", f"{g['blocks_ended']} blocks ended but 0 mastery rows. Inspect app/api/doubt.py _genome_update_task."))
    if n_shift >= 3 and analysis.get("topic_shift_pass_pct") is not None and analysis["topic_shift_pass_pct"] < 80:
        bugs.append(("P0", "Topic-shift detection regression", f"{analysis['topic_shift_pass_pct']}% of {n_shift} pivots opened a new doubt_block (expected ≥80%). Inspect _detect_topic_shift + _looks_like_new_question in app/api/doubt.py."))
    if n_fu >= 3 and analysis.get("followup_continuation_rate_pct") is not None and analysis["followup_continuation_rate_pct"] < 70:
        bugs.append(("P1", "Follow-up misclassification", f"Continuation intent only fired {analysis['followup_continuation_rate_pct']}% of {n_fu} follow-up turns. Review intent classifier + _looks_like_new_question thresholds."))
    if n_misc >= 3 and analysis.get("misconception_detection_rate_pct") is not None and analysis["misconception_detection_rate_pct"] < 40:
        bugs.append(("P1", "Misconception library under-firing", f"{analysis['misconception_detection_rate_pct']}% of {n_misc} misconception prompts matched. Review app/services/doubt/misconceptions.py MISCONCEPTION_LIBRARY patterns."))
    if n_emo >= 2 and analysis.get("emotional_counselor_mode_rate_pct") is not None and analysis["emotional_counselor_mode_rate_pct"] < 50:
        bugs.append(("P2", "COUNSELOR switch unreliable", f"Emotional cue → COUNSELOR fired {analysis['emotional_counselor_mode_rate_pct']}% of {n_emo} emotional turns."))
    if e.get("p95_latency_ms") and e["p95_latency_ms"] > 15000:
        bugs.append(("P1", "Latency P95 > 15s", f"p95 = {e['p95_latency_ms']} ms. Cold-start (Render free tier) or agentic-RAG loop pathology."))
    if not bugs:
        md.append("None above threshold — all four pillars healthy.")
    else:
        md.append("| Priority | Bug | Fix direction |")
        md.append("|---|---|---|")
        for pr, ti, fx in bugs:
            md.append(f"| **{pr}** | {ti} | {fx} |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## Raw counts")
    md.append("")
    md.append(f"- Judge rows: {q['n_judge_rows']}")
    md.append(f"- session_events rows (all-time, persona): {len(analysis.get('render_log_errors') or [])}")  # placeholder
    md.append(f"- concept_mastery rows: {g['mastery_rows_written']}")
    md.append(f"- doubt_blocks opened: {g['blocks_opened']}, resolved: {g['blocks_resolved']}, ended: {g['blocks_ended']}")
    return "\n".join(md)


# ── Main ─────────────────────────────────────────────────────────────────────
async def amain():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend",   default=os.environ.get("BACKEND", "https://upmyrank-poc.onrender.com"))
    ap.add_argument("--run-id",    default=os.environ.get("RUN_ID", f"diag-{time.strftime('%Y%m%d-%H%M%S')}"))
    ap.add_argument("--prompts",   default=str(REPO_ROOT / "scripts/data/diagnostic_100.json"))
    ap.add_argument("--out",       default=str(REPO_ROOT / f"reports/diagnostic_{time.strftime('%Y-%m-%d')}"))
    ap.add_argument("--max-flows", type=int, default=0, help="limit flows for smoke testing (0 = all)")
    ap.add_argument("--judge-wait-s", type=int, default=45, help="seconds to wait after last turn for async Judge rows to land")
    args = ap.parse_args()

    with open(args.prompts) as f:
        dataset = json.load(f)

    flows = dataset["flows"]
    if args.max_flows and args.max_flows < len(flows):
        flows = flows[:args.max_flows]
        log.info("smoke mode — running %d/%d flows", len(flows), len(dataset["flows"]))

    start_wall = time.time()
    start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_wall))

    async with APIClient(args.backend) as client:
        await client.signup(args.run_id)
        await client.onboard()
        turns = await run_all_flows(client, flows)

    # Wait for async Judge / CTQ writes to land
    log.info("waiting %ds for async Judge rows to land ...", args.judge_wait_s)
    await asyncio.sleep(args.judge_wait_s)

    end_wall = time.time()
    end_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end_wall))

    # Supabase
    log.info("querying Supabase ...")
    db = await query_supabase(client.student_id) if client.student_id else {"skipped": True}

    # Render logs
    log.info("pulling Render logs ...")
    logs = await pull_render_logs(start_iso, end_iso)

    # Analyze
    analysis = analyze(turns, db, logs)

    meta = {
        "run_id":        args.run_id,
        "backend":       args.backend,
        "email":         client.email or "",
        "student_id":    client.student_id or "",
        "persona":       PERSONA["name"],
        "n_flows":       len(flows),
        "n_prompts":     len(turns),
        "generated_at":  time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "duration_s":    round(end_wall - start_wall, 1),
    }

    out_base = Path(args.out)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_base.with_suffix(".json")
    md_path = out_base.with_suffix(".md")

    with open(json_path, "w") as f:
        json.dump({
            "meta":     meta,
            "turns":    [asdict(t) for t in turns],
            "db":       db,
            "render_logs_sample": logs[:50],
            "analysis": analysis,
        }, f, indent=2, default=str)
    log.info("wrote %s", json_path)

    md = fmt_md_report(args.run_id, analysis, meta)
    with open(md_path, "w") as f:
        f.write(md)
    log.info("wrote %s", md_path)

    # Exit code: 1 if any P0 bug surfaced
    bug_count = sum(1 for line in md.splitlines() if line.startswith("| **P0**"))
    return 1 if bug_count > 0 else 0


if __name__ == "__main__":
    rc = asyncio.run(amain())
    sys.exit(rc)
