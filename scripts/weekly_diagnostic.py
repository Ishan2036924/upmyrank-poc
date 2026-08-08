#!/usr/bin/env python3
"""
Weekly automated end-to-end diagnostic agent.

Runs once a week via GitHub Actions. Creates one realistic synthetic student,
walks the full request path (signup -> onboarding -> session -> 3 doubts across
Physics/Chemistry/Maths -> session_end), then queries Supabase directly to
verify the background pipelines (judge, arc judge, mastery EMA, session_metrics)
fired correctly. Posts a Markdown report as a GitHub Issue.

Primary goal: keep Supabase free-tier active (7-day auto-pause window) AND
catch any silent regression within a week.

Required env vars (set as GitHub Actions repo secrets):
  BACKEND_URL         e.g. https://upmyrank-poc.onrender.com
  DATABASE_URL        Supabase Postgres pooler URL
  GITHUB_TOKEN        Auto-provided by GitHub Actions (issues:write scope)
  GITHUB_REPOSITORY   Auto-provided by GitHub Actions (owner/repo)

Exit code: 0 on PASS, 1 on WARN or FAIL (so the workflow run also turns red).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
import httpx

# Realistic Indian student names — rotated deterministically by ISO week so
# each week's synthetic user has a different name.
NAMES = [
    "Aarav", "Diya", "Rohan", "Ananya", "Vihaan", "Saanvi", "Arjun", "Ishaan",
    "Aditi", "Kabir", "Myra", "Reyansh", "Ira", "Vivaan", "Tanya", "Krishna",
    "Riya", "Aryan", "Pari", "Yash", "Anika", "Dhruv", "Navya", "Karan",
    "Siya", "Veer", "Nisha", "Atharv", "Shanaya", "Rudra",
]

DOUBTS = [
    {
        "subject": "Physics",
        "prompt": "A 5 kg block slides down a 30 degree frictionless incline. "
                  "What is the acceleration?",
    },
    {
        "subject": "Chemistry",
        "prompt": "Why does water have a bent shape while carbon dioxide is linear?",
    },
    {
        "subject": "Maths",
        "prompt": "What is the derivative of x squared times sin(x)?",
    },
]


# ── Result tracking ──────────────────────────────────────────────────────────

@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    duration_ms: int = 0


@dataclass
class WeeklyRun:
    student_name: str
    student_email: str
    started_at: str
    steps: list[StepResult] = field(default_factory=list)
    db_footprint: dict = field(default_factory=dict)

    def record(self, name: str, ok: bool, detail: str = "", duration_ms: int = 0):
        self.steps.append(StepResult(name, ok, detail, duration_ms))
        marker = "OK" if ok else "FAIL"
        print(f"[{marker}] {name} ({duration_ms} ms) {detail}")

    def verdict(self) -> str:
        # Backend or frontend step failure = FAIL
        critical = [s for s in self.steps if s.name.startswith(("step.", "frontend"))]
        if any(not s.ok for s in critical):
            return "FAIL"
        warns = self.db_footprint.get("warnings", [])
        if warns:
            return "WARN"
        return "PASS"


# ── API client (lifted from synthetic_beta.py + diagnostic_100.py) ──────────

class APIClient:
    def __init__(self, backend: str):
        self.backend = backend.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)
        self.token: Optional[str] = None
        self.student_id: Optional[str] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._client.aclose()

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def health(self) -> bool:
        r = await self._client.get(f"{self.backend}/health")
        return r.status_code == 200

    async def signup(self, name: str, email: str) -> dict:
        body = {
            "name": name,
            "email": email,
            "password": "Weekly#Diag2026",
            "exam_type": "JEE",
            "target_year": 2027,
        }
        r = await self._client.post(
            f"{self.backend}/auth/signup", json=body, headers=self._headers(),
        )
        r.raise_for_status()
        d = r.json()
        self.token = d["token"]
        self.student_id = d["student_id"]
        return d

    async def submit_onboarding(self) -> dict:
        body = {
            "class_level": "12th",
            "physics_prev_marks": 65,
            "chemistry_prev_marks": 55,
            "maths_prev_marks": 60,
            "easy_topics": ["Kinematics", "Atomic Structure"],
            "hard_topics": ["Calculus (Integration)", "Rotational Dynamics"],
            "study_hours_per_day": 4.0,
            "exam_type": "JEE_MAINS",
            "exam_date": "2027-04-01",
            "priority_subject": "Physics",
            "learning_preference": "example",
        }
        r = await self._client.post(
            f"{self.backend}/onboarding/submit", json=body, headers=self._headers(),
        )
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

    async def doubt_ask(self, question: str, study_session_id: str, subject: str) -> dict:
        body = {
            "question": question,
            "subject": subject,
            "study_session_id": study_session_id,
        }
        r = await self._client.post(
            f"{self.backend}/doubt/ask", json=body, headers=self._headers(),
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


# ── Frontend availability (Vercel deployment) ────────────────────────────────

# Frontend routes hit weekly to confirm Vercel deployment is up and serving the
# expected pages. These are GETs with no auth — we just check HTTP 200 + a small
# substring match on the response body to detect "Vercel deployment broken" vs
# "page renders but build is stale".
FRONTEND_ROUTES = [
    # 2026-08-08: markers must be "UpMyRank", not form copy. The auth pages are
    # client components behind a Suspense boundary, so "Sign in" / "Create"
    # never appear in the server-rendered HTML — those two rows would have
    # false-failed on every single weekly run. "UpMyRank" comes from the
    # document metadata and still distinguishes a live deploy from a Vercel
    # 404 / DEPLOYMENT_NOT_FOUND page, which is the point of this check.
    ("/",            "UpMyRank"),
    ("/auth/login",  "UpMyRank"),
    ("/auth/signup", "UpMyRank"),
]


async def check_frontend(run: "WeeklyRun", frontend_url: str) -> None:
    """Hit a handful of public frontend routes and check HTTP 200 + body marker."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
        for path, marker in FRONTEND_ROUTES:
            t0 = time.monotonic()
            try:
                r = await c.get(f"{frontend_url.rstrip('/')}{path}")
                ok = r.status_code == 200 and (marker.lower() in r.text.lower())
                detail = f"HTTP {r.status_code}"
                if r.status_code == 200 and marker.lower() not in r.text.lower():
                    detail += f" but body missing '{marker}' (stale build?)"
                run.record(f"frontend{path}", ok, detail,
                           int((time.monotonic() - t0) * 1000))
            except Exception as e:
                run.record(f"frontend{path}", False, f"{type(e).__name__}: {e}",
                           int((time.monotonic() - t0) * 1000))


# ── DB row-count verification ────────────────────────────────────────────────

async def query_db_footprint(student_id: str) -> dict:
    """Replicates the SQL checks from /admin/diagnostics for THIS student."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"error": "DATABASE_URL not set", "warnings": ["db_unreachable"]}
    if "?" in db_url:
        db_url = db_url.split("?")[0]

    try:
        conn = await asyncpg.connect(db_url, ssl="require", timeout=30.0)
    except Exception as e:
        return {"error": f"DB connect failed: {e}", "warnings": ["db_unreachable"]}

    warnings: list[str] = []
    try:
        sid = uuid.UUID(student_id)

        doubt_sessions = await conn.fetchval(
            "SELECT COUNT(*) FROM doubt_sessions WHERE student_id = $1", sid,
        )
        doubt_blocks = await conn.fetchval(
            "SELECT COUNT(*) FROM doubt_blocks WHERE student_id = $1", sid,
        )
        judge_rows = await conn.fetchval(
            """SELECT COUNT(*) FROM judge_evaluations je
               JOIN doubt_sessions ds ON ds.id = je.doubt_session_id
               WHERE ds.student_id = $1""", sid,
        )
        arc_rows = await conn.fetchval(
            """SELECT COUNT(*) FROM conversation_arc_quality caq
               JOIN study_sessions ss ON ss.study_session_id = caq.study_session_id
               WHERE ss.student_id = $1""", sid,
        ) if await _table_exists(conn, "conversation_arc_quality") else 0
        mastery_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM concept_mastery WHERE student_id = $1", sid,
        )
        metrics_rows = await conn.fetchval(
            """SELECT COUNT(*) FROM session_metrics sm
               JOIN doubt_sessions ds ON ds.id = sm.doubt_session_id
               WHERE ds.student_id = $1""", sid,
        )

        # Sanity checks vs. expected minima for a 3-doubt run
        if doubt_sessions < 3:
            warnings.append(f"only_{doubt_sessions}_doubt_sessions_expected_3")
        if judge_rows < 3:
            warnings.append(f"only_{judge_rows}_judge_evaluations_expected_3")
        if metrics_rows < 3:
            warnings.append(f"only_{metrics_rows}_session_metrics_expected_3")
        if mastery_rows < 1:
            warnings.append("no_mastery_rows_genome_pipeline_silent")

        # ── Global system-health checks (not student-scoped) ─────────────────
        null_embed = await conn.fetchval(
            "SELECT COUNT(*) FROM knowledge_chunks WHERE embedding IS NULL"
        ) or 0
        if null_embed > 0:
            warnings.append(f"{null_embed}_null_embeddings_in_kb")

        # Knowledge base size (regression guard — was 15,069 at v0.20.16)
        kb_chunks = await conn.fetchval("SELECT COUNT(*) FROM knowledge_chunks") or 0
        if kb_chunks < 15000:
            warnings.append(f"kb_chunks_dropped_to_{kb_chunks}")

        # Total student / session counts (just for visibility in the report)
        total_students = await conn.fetchval("SELECT COUNT(*) FROM students") or 0
        total_study_sessions = await conn.fetchval(
            "SELECT COUNT(*) FROM study_sessions"
        ) or 0
        total_doubts_all_time = await conn.fetchval(
            "SELECT COUNT(*) FROM doubt_sessions"
        ) or 0

        # Orphaned doubt_sessions (same query as /admin/diagnostics)
        orphaned = await conn.fetchval("""
            SELECT COUNT(*) FROM doubt_sessions ds
            WHERE NOT EXISTS (
              SELECT 1 FROM doubt_blocks db WHERE db.doubt_session_id = ds.id
            )
        """) or 0
        if orphaned > 50:
            warnings.append(f"orphaned_doubt_sessions_{orphaned}_running_high")

        # Slow sessions (retrieval >10s) in last 7 days
        slow = await conn.fetchval("""
            SELECT COUNT(*) FROM session_metrics
            WHERE retrieval_latency_ms > 10000
              AND created_at >= NOW() - INTERVAL '7 days'
        """) or 0

        # Background pipeline activity in last 24h — proves judge + arc judge fired
        # for OUR synthetic run (we slept 8 s, so they should have landed)
        judge_24h = await conn.fetchval("""
            SELECT COUNT(*) FROM judge_evaluations
            WHERE evaluated_at >= NOW() - INTERVAL '24 hours'
        """) or 0
        arc_24h = 0
        if await _table_exists(conn, "conversation_arc_quality"):
            arc_24h = await conn.fetchval("""
                SELECT COUNT(*) FROM conversation_arc_quality
                WHERE scored_at >= NOW() - INTERVAL '24 hours'
            """) or 0

        # Most recent activity timestamp — if older than 24 h something is very wrong
        last_doubt = await conn.fetchval(
            "SELECT MAX(created_at) FROM doubt_sessions"
        )

        return {
            # Per-run footprint
            "doubt_sessions": int(doubt_sessions or 0),
            "doubt_blocks": int(doubt_blocks or 0),
            "judge_evaluations": int(judge_rows or 0),
            "conversation_arc_quality": int(arc_rows or 0),
            "concept_mastery_rows": int(mastery_rows or 0),
            "session_metrics": int(metrics_rows or 0),
            # System-wide health
            "kb_chunks": int(kb_chunks or 0),
            "kb_null_embeddings": int(null_embed or 0),
            "total_students": int(total_students or 0),
            "total_study_sessions": int(total_study_sessions or 0),
            "total_doubts_all_time": int(total_doubts_all_time or 0),
            "orphaned_doubt_sessions": int(orphaned or 0),
            "slow_sessions_7d": int(slow or 0),
            "judge_evaluations_24h": int(judge_24h or 0),
            "conversation_arc_quality_24h": int(arc_24h or 0),
            "last_doubt_at": str(last_doubt) if last_doubt else "never",
            "warnings": warnings,
        }
    finally:
        await conn.close()


async def _table_exists(conn, table: str) -> bool:
    return bool(await conn.fetchval(
        "SELECT to_regclass('public.' || $1) IS NOT NULL", table,
    ))


# ── Report assembly ──────────────────────────────────────────────────────────

def build_report(run: WeeklyRun) -> tuple[str, str]:
    verdict = run.verdict()
    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[verdict]
    title = f"[Weekly Diagnostic] {run.started_at[:10]} {icon} {verdict} — {run.student_name}"

    lines: list[str] = [
        f"# Weekly Diagnostic — {run.started_at[:10]}",
        "",
        f"**Verdict:** {icon} **{verdict}**",
        f"**Synthetic student:** {run.student_name} (`{run.student_email}`)",
        f"**Run started:** {run.started_at}",
        "",
        "## Steps",
        "",
        "| Step | Status | Duration | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for s in run.steps:
        emoji = "✅" if s.ok else "❌"
        lines.append(f"| `{s.name}` | {emoji} | {s.duration_ms} ms | {s.detail} |")

    lines += [
        "",
        "## Database Footprint (rows created by this run)",
        "",
    ]
    fp = run.db_footprint
    if "error" in fp:
        lines.append(f"⚠️ DB query failed: `{fp['error']}`")
    else:
        lines += [
            "| Table | Rows created by THIS run |",
            "| --- | --- |",
            f"| `doubt_sessions` | {fp.get('doubt_sessions', '?')} (expected ≥ 3) |",
            f"| `doubt_blocks` | {fp.get('doubt_blocks', '?')} |",
            f"| `judge_evaluations` | {fp.get('judge_evaluations', '?')} (expected ≥ 3) |",
            f"| `conversation_arc_quality` | {fp.get('conversation_arc_quality', '?')} (expected ≥ 1) |",
            f"| `concept_mastery` | {fp.get('concept_mastery_rows', '?')} |",
            f"| `session_metrics` | {fp.get('session_metrics', '?')} (expected ≥ 3) |",
            "",
            "## System Health (whole-platform snapshot)",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Knowledge base chunks | {fp.get('kb_chunks', '?')} (expected ≥ 15,000) |",
            f"| Chunks with NULL embedding | {fp.get('kb_null_embeddings', '?')} (expected 0) |",
            f"| Total students (all time) | {fp.get('total_students', '?')} |",
            f"| Total study sessions (all time) | {fp.get('total_study_sessions', '?')} |",
            f"| Total doubt sessions (all time) | {fp.get('total_doubts_all_time', '?')} |",
            f"| Orphaned doubt_sessions | {fp.get('orphaned_doubt_sessions', '?')} |",
            f"| Slow sessions (>10s retrieval, 7d) | {fp.get('slow_sessions_7d', '?')} |",
            f"| `judge_evaluations` rows in last 24h | {fp.get('judge_evaluations_24h', '?')} (≥ 3 = this run fired correctly) |",
            f"| `conversation_arc_quality` rows in last 24h | {fp.get('conversation_arc_quality_24h', '?')} (≥ 1 = arc judge fired correctly) |",
            f"| Last doubt across whole platform | `{fp.get('last_doubt_at', '?')}` |",
        ]

    warns = fp.get("warnings", [])
    if warns:
        lines += ["", "## Warnings", ""]
        for w in warns:
            lines.append(f"- ⚠️ `{w}`")

    lines += [
        "",
        "---",
        "*Auto-generated by `scripts/weekly_diagnostic.py` via GitHub Actions.*",
        "*Synthetic users accumulate at 52/year; run `scripts/diag_cleanup_test_accounts.py --execute` to purge.*",
    ]
    return title, "\n".join(lines)


# ── GitHub Issue posting ─────────────────────────────────────────────────────

async def post_github_issue(title: str, body: str) -> Optional[str]:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("[skip] GITHUB_TOKEN or GITHUB_REPOSITORY not set — printing report instead:")
        print(body)
        return None

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"title": title, "body": body, "labels": ["weekly-diagnostic"]}
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(url, json=payload, headers=headers)
        if r.status_code >= 300:
            print(f"[warn] GitHub Issue creation failed: {r.status_code} {r.text[:300]}")
            return None
        return r.json().get("html_url")


# ── Main flow ────────────────────────────────────────────────────────────────

async def main() -> int:
    backend = os.environ.get("BACKEND_URL", "https://upmyrank-poc.onrender.com")
    frontend = os.environ.get("FRONTEND_URL", "https://upmyrank-poc.vercel.app")

    now = datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    name = NAMES[(iso_year * 53 + iso_week) % len(NAMES)]
    email = f"weekly-{iso_year}-W{iso_week:02d}@upmyrank.test"

    print(f"=== Weekly diagnostic | week={iso_year}-W{iso_week:02d} | student={name} ===")

    run = WeeklyRun(
        student_name=name,
        student_email=email,
        started_at=now.isoformat(),
    )

    # Frontend availability (Vercel) — quick HTTP 200 + body-marker checks
    await check_frontend(run, frontend)

    async with APIClient(backend) as client:
        # health
        t0 = time.monotonic()
        try:
            ok = await client.health()
            run.record("step.health", ok, "200" if ok else "non-200",
                       int((time.monotonic() - t0) * 1000))
            if not ok:
                # Backend down — short-circuit; still report
                title, body = build_report(run)
                await post_github_issue(title, body)
                return 1
        except Exception as e:
            run.record("step.health", False, f"{type(e).__name__}: {e}",
                       int((time.monotonic() - t0) * 1000))
            title, body = build_report(run)
            await post_github_issue(title, body)
            return 1

        # signup
        t0 = time.monotonic()
        try:
            await client.signup(name, email)
            run.record("step.signup", True, f"student_id={client.student_id[:8]}",
                       int((time.monotonic() - t0) * 1000))
        except Exception as e:
            run.record("step.signup", False, f"{type(e).__name__}: {e}",
                       int((time.monotonic() - t0) * 1000))
            title, body = build_report(run)
            await post_github_issue(title, body)
            return 1

        # onboarding
        t0 = time.monotonic()
        try:
            await client.submit_onboarding()
            run.record("step.onboarding", True, "persona_profile built",
                       int((time.monotonic() - t0) * 1000))
        except Exception as e:
            run.record("step.onboarding", False, f"{type(e).__name__}: {e}",
                       int((time.monotonic() - t0) * 1000))

        # session start
        study_session_id: Optional[str] = None
        t0 = time.monotonic()
        try:
            sess = await client.session_start()
            study_session_id = sess.get("study_session_id")
            run.record("step.session_start", bool(study_session_id),
                       f"ssid={study_session_id[:8] if study_session_id else 'none'}",
                       int((time.monotonic() - t0) * 1000))
        except Exception as e:
            run.record("step.session_start", False, f"{type(e).__name__}: {e}",
                       int((time.monotonic() - t0) * 1000))

        # 3 doubts
        if study_session_id:
            for i, d in enumerate(DOUBTS, start=1):
                t0 = time.monotonic()
                try:
                    resp = await client.doubt_ask(d["prompt"], study_session_id, d["subject"])
                    intent = resp.get("intent") or "unknown"
                    block = resp.get("doubt_block_id") or (resp.get("metadata") or {}).get("doubt_block_id")
                    rlen = len(resp.get("response") or resp.get("ai_response") or "")
                    run.record(f"step.doubt_{i}_{d['subject'].lower()}", True,
                               f"intent={intent} block={block[:8] if block else 'none'} resp_len={rlen}",
                               int((time.monotonic() - t0) * 1000))
                except Exception as e:
                    run.record(f"step.doubt_{i}_{d['subject'].lower()}", False,
                               f"{type(e).__name__}: {e}",
                               int((time.monotonic() - t0) * 1000))

            # session end (blocking — triggers judge + summarizer per RULES.md #2)
            t0 = time.monotonic()
            try:
                await client.session_end(study_session_id)
                run.record("step.session_end", True, "blocking summarizer ran",
                           int((time.monotonic() - t0) * 1000))
            except Exception as e:
                run.record("step.session_end", False, f"{type(e).__name__}: {e}",
                           int((time.monotonic() - t0) * 1000))

    # Give async background tasks a moment to land judge rows
    await asyncio.sleep(8)

    # DB footprint
    if client.student_id:
        try:
            run.db_footprint = await query_db_footprint(client.student_id)
        except Exception as e:
            run.db_footprint = {"error": str(e), "warnings": ["db_query_exception"]}

    title, body = build_report(run)
    issue_url = await post_github_issue(title, body)
    if issue_url:
        print(f"\nGitHub Issue: {issue_url}")

    verdict = run.verdict()
    print(f"\nVerdict: {verdict}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
