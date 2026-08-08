#!/usr/bin/env python3
"""
portfolio_smoke.py — 15-persona end-to-end smoke test against production.

Written 2026-08-08 after the live demo was reported as "not working" when
opened from a LinkedIn/portfolio link. The single-user weekly diagnostic
(scripts/weekly_diagnostic.py) proves the happy path stays alive; this proves
the path holds across the full parameter space and under concurrency.

What it exercises, per persona:
    /auth/signup -> /onboarding/status -> /onboarding/submit
    -> /session/start -> N x /doubt/ask (with a follow-up) -> /session/end

Parameter coverage across the 15 personas:
    class_level          11th / 12th / dropper       (all three)
    exam_type (signup)   JEE / NEET                  (both)
    exam_type (onboard)  JEE_MAINS / JEE_ADVANCED / NEET
    subject              Physics / Chemistry / Maths (all three)
    learning_preference  formula / analogy / example / visual
    marks bands          weak <50 / medium 50-75 / strong >75
                         -> drives HIGH / MEDIUM / LOW scaffolding

NOTE on the two exam_type vocabularies: /auth/signup takes "JEE" | "NEET"
(app/api/auth.py) while /onboarding/submit takes "JEE_MAINS" | "JEE_ADVANCED" |
"NEET" (app/api/onboarding.py:206). They are different enums on purpose. The
personas below carry both fields separately; do not collapse them.

Emails are all `@upmyrank.test` so scripts/diag_cleanup_test_accounts.py picks
them up for purging afterwards.

Usage:
    python3 scripts/portfolio_smoke.py                 # 15 personas, 5 at a time
    python3 scripts/portfolio_smoke.py --concurrency 1 # fully sequential
    python3 scripts/portfolio_smoke.py --limit 3       # quick check
    python3 scripts/portfolio_smoke.py --report out.md

Only needs stdlib + httpx.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    import httpx
except ImportError:
    sys.exit("httpx required:  pip install httpx")


BACKEND_URL = os.environ.get("BACKEND_URL", "https://upmyrank-poc.onrender.com").rstrip("/")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://upmyrank-poc.vercel.app").rstrip("/")

# A cold Render free-tier instance can take ~60s to boot, and an agentic-RAG
# doubt turn is 12-25s warm. 180s is generous but keeps a genuine hang bounded.
TIMEOUT = httpx.Timeout(180.0, connect=30.0)

RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


# ── Personas ──────────────────────────────────────────────────────────────────

@dataclass
class Persona:
    name: str
    signup_exam: str          # "JEE" | "NEET"
    class_level: str          # "11th" | "12th" | "dropper"
    onboard_exam: str         # "JEE_MAINS" | "JEE_ADVANCED" | "NEET"
    physics: int | None
    chemistry: int | None
    maths: int | None
    hours: float
    preference: str           # formula | analogy | example | visual
    priority: str             # Physics | Chemistry | Maths
    easy: list[str]
    hard: list[str]
    subject: str              # subject sent on the doubt turns
    question: str
    followup: str


PERSONAS: list[Persona] = [
    Persona("Aarav Sharma", "JEE", "12th", "JEE_MAINS", 42, 55, 38, 6.0, "analogy", "Physics",
            ["Units and Dimensions"], ["Rotational Motion", "Thermodynamics"], "Physics",
            "A block slides down a frictionless incline at 30 degrees. What is its acceleration?",
            "Hmm, why does the mass not matter here?"),
    Persona("Diya Patel", "NEET", "11th", "NEET", None, None, None, 4.5, "example", "Chemistry",
            ["Atomic Structure"], ["Chemical Bonding"], "Chemistry",
            "Why is water bent but carbon dioxide linear?",
            "Wait, so what decides the bond angle exactly?"),
    Persona("Rohan Verma", "JEE", "dropper", "JEE_ADVANCED", 78, 82, 88, 9.0, "formula", "Maths",
            ["Calculus", "Algebra"], ["Complex Numbers"], "Maths",
            "Find the derivative of x squared times sin(x).",
            "Can you show the product rule step again?"),
    Persona("Ananya Iyer", "JEE", "12th", "JEE_MAINS", 65, 70, 61, 5.0, "visual", "Physics",
            ["Kinematics"], ["Electrostatics"], "Physics",
            "What is the electric field inside a hollow conducting sphere?",
            "But why is it exactly zero and not just small?"),
    Persona("Kabir Nair", "NEET", "12th", "NEET", 48, 44, None, 7.0, "analogy", "Chemistry",
            ["Periodic Table"], ["Organic Chemistry", "Equilibrium"], "Chemistry",
            "What is Le Chatelier's principle?",
            "How does that apply if I increase the pressure?"),
    Persona("Meera Joshi", "JEE", "11th", "JEE_MAINS", None, None, None, 3.5, "example", "Maths",
            ["Trigonometry"], ["Sequences and Series"], "Maths",
            "What is the sum of an infinite geometric progression?",
            "What happens when the ratio is bigger than 1?"),
    Persona("Arjun Reddy", "JEE", "dropper", "JEE_ADVANCED", 71, 68, 74, 10.0, "formula", "Physics",
            ["Mechanics"], ["Modern Physics"], "Physics",
            "Explain the photoelectric effect and the work function.",
            "So why does brighter light not help below threshold frequency?"),
    Persona("Sanya Gupta", "NEET", "11th", "NEET", 35, 40, None, 4.0, "visual", "Chemistry",
            [], ["Mole Concept", "Stoichiometry"], "Chemistry",
            "What is a mole and why is it 6.022 times 10 to the 23?",
            "I still do not get why we need such a huge number."),
    Persona("Vihaan Kulkarni", "JEE", "12th", "JEE_ADVANCED", 85, 79, 91, 8.5, "formula", "Maths",
            ["Calculus", "Vectors"], ["Probability"], "Maths",
            "Evaluate the integral of x times e to the power x.",
            "Why do we pick x as u and not e to the x?"),
    Persona("Ishita Bose", "JEE", "12th", "JEE_MAINS", 52, 58, 49, 6.5, "analogy", "Maths",
            ["Coordinate Geometry"], ["Calculus"], "Maths",
            "What does the second derivative tell us about a curve?",
            "How do I use that to find a maximum?"),
    Persona("Aditya Menon", "NEET", "dropper", "NEET", 62, 66, None, 8.0, "example", "Chemistry",
            ["Thermodynamics"], ["Coordination Compounds"], "Chemistry",
            "What is hybridisation in coordination complexes?",
            "How do I tell high spin from low spin?"),
    Persona("Nisha Rao", "JEE", "11th", "JEE_MAINS", 44, None, 51, 5.5, "visual", "Physics",
            ["Vectors"], ["Work Energy Power"], "Physics",
            "What is the work energy theorem?",
            "Does friction change the answer?"),
    Persona("Karthik Pillai", "JEE", "dropper", "JEE_ADVANCED", 90, 87, 84, 11.0, "formula", "Physics",
            ["Electrodynamics", "Optics"], ["Fluid Mechanics"], "Physics",
            "Derive the condition for total internal reflection.",
            "What if the second medium is denser instead?"),
    Persona("Tanvi Desai", "NEET", "12th", "NEET", 57, 61, None, 6.0, "analogy", "Chemistry",
            ["Solutions"], ["Electrochemistry"], "Chemistry",
            "What is the Nernst equation used for?",
            "Why does concentration shift the cell potential?"),
    Persona("Yash Chauhan", "JEE", "12th", "JEE_MAINS", 30, 33, 29, 3.0, "example", "Maths",
            [], ["Calculus", "Algebra", "Trigonometry"], "Maths",
            "What is a limit in calculus?",
            "Can you give me a really simple example?"),
]


# ── Result tracking ───────────────────────────────────────────────────────────

@dataclass
class StepResult:
    name: str
    ok: bool
    status: int
    seconds: float
    note: str = ""


@dataclass
class PersonaResult:
    persona: str
    email: str
    steps: list[StepResult] = field(default_factory=list)
    student_id: str | None = None

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)

    @property
    def total_seconds(self) -> float:
        return sum(s.seconds for s in self.steps)


class APIClient:
    """Minimal auth-aware client. Mirrors the pattern in scripts/weekly_diagnostic.py."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._c = client
        self.token: str | None = None

    async def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any, float]:
        headers = {"Content-Type": "application/json", "Origin": FRONTEND_URL}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        t0 = time.perf_counter()
        try:
            resp = await self._c.request(method, f"{BACKEND_URL}{path}", json=body, headers=headers)
        except Exception as exc:  # network error, timeout, cold-start hang
            return -1, f"{type(exc).__name__}: {exc}", time.perf_counter() - t0
        elapsed = time.perf_counter() - t0
        try:
            return resp.status_code, resp.json(), elapsed
        except Exception:
            return resp.status_code, resp.text[:400], elapsed


async def run_persona(idx: int, p: Persona, sem: asyncio.Semaphore) -> PersonaResult:
    email = f"smoke-{RUN_TAG}-{idx:02d}@upmyrank.test"
    result = PersonaResult(persona=p.name, email=email)

    async with sem:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as raw:
            api = APIClient(raw)

            def record(name: str, status: int, body: Any, secs: float, ok: bool, note: str = "") -> bool:
                if not ok and not note:
                    note = body if isinstance(body, str) else str(body)[:200]
                result.steps.append(StepResult(name, ok, status, secs, note))
                return ok

            # 1. signup
            status, body, secs = await api.call("POST", "/auth/signup", {
                "name": p.name, "email": email, "password": "SmokeTest!2026x",
                "exam_type": p.signup_exam, "target_year": 2027,
            })
            token = body.get("token") if isinstance(body, dict) else None
            # A 200 with a null token means Supabase email confirmation is on;
            # the account is real but unusable here. Treat as a failure for the
            # smoke test, since a recruiter would be equally stuck.
            ok = status == 200 and bool(token)
            note = "" if ok else ("200 but token is null (email confirmation enabled?)"
                                  if status == 200 else "")
            if not record("signup", status, body, secs, ok, note):
                return result
            api.token = token
            result.student_id = body["student_id"]

            # 2. onboarding status (should be false for a brand new account)
            status, body, secs = await api.call("GET", "/onboarding/status")
            record("onboarding_status", status, body, secs, status == 200)

            # 3. onboarding submit — the mandatory gate before /doubt is usable
            status, body, secs = await api.call("POST", "/onboarding/submit", {
                "class_level": p.class_level,
                "physics_prev_marks": p.physics,
                "chemistry_prev_marks": p.chemistry,
                "maths_prev_marks": p.maths,
                "easy_topics": p.easy,
                "hard_topics": p.hard,
                "study_hours_per_day": p.hours,
                "exam_type": p.onboard_exam,
                "exam_date": "2027-01-20",
                "priority_subject": p.priority,
                "learning_preference": p.preference,
            })
            if not record("onboarding_submit", status, body, secs, status == 200):
                return result

            # 4. session start
            status, body, secs = await api.call("POST", "/session/start", {"student_id": result.student_id})
            study_session_id = body.get("study_session_id") if isinstance(body, dict) else None
            if not record("session_start", status, body, secs, status == 200 and bool(study_session_id)):
                return result

            # 5. first doubt — the core product surface
            status, body, secs = await api.call("POST", "/doubt/ask", {
                "question": p.question, "subject": p.subject,
                "study_session_id": study_session_id,
            })
            resp_text = body.get("response", "") if isinstance(body, dict) else ""
            record("doubt_ask", status, body, secs, status == 200 and bool(resp_text),
                   "" if resp_text else "empty response body")

            # 6. follow-up — exercises continuation vs topic-shift detection
            status, body, secs = await api.call("POST", "/doubt/ask", {
                "question": p.followup, "subject": p.subject,
                "study_session_id": study_session_id,
            })
            resp_text = body.get("response", "") if isinstance(body, dict) else ""
            record("doubt_followup", status, body, secs, status == 200 and bool(resp_text),
                   "" if resp_text else "empty response body")

            # 7. session end — blocking summarizer + judge (RULES.md #2)
            status, body, secs = await api.call("POST", "/session/end",
                                                {"study_session_id": study_session_id})
            record("session_end", status, body, secs, status == 200)

    return result


async def check_frontend() -> list[StepResult]:
    """Confirm Vercel is serving real pages, not just any 200."""
    # Marker must be "UpMyRank", not form copy like "Sign in". The auth pages
    # are client components behind a Suspense boundary, so their visible text
    # lives in the JS bundle and never appears in the initial HTML. Asserting
    # on "Sign in" gives a permanent false failure. "UpMyRank" comes from the
    # document metadata and is enough to tell our app apart from a Vercel
    # 404 / DEPLOYMENT_NOT_FOUND page, which is what this check is really for.
    checks = [("/", "UpMyRank"), ("/auth/login", "UpMyRank"), ("/auth/signup", "UpMyRank")]
    out: list[StepResult] = []
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
        for path, marker in checks:
            t0 = time.perf_counter()
            try:
                r = await c.get(f"{FRONTEND_URL}{path}")
                secs = time.perf_counter() - t0
                ok = r.status_code == 200 and marker.lower() in r.text.lower()
                note = "" if ok else f"status={r.status_code} marker '{marker}' present={marker.lower() in r.text.lower()}"
                out.append(StepResult(f"frontend {path}", ok, r.status_code, secs, note))
            except Exception as exc:
                out.append(StepResult(f"frontend {path}", False, -1, time.perf_counter() - t0, str(exc)))
    return out


def build_report(front: list[StepResult], results: list[PersonaResult], cold_start: float) -> str:
    passed = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    front_ok = all(s.ok for s in front)

    lines: list[str] = []
    lines.append(f"# Portfolio smoke test — {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append("")
    verdict = "PASS" if (front_ok and not failed) else "FAIL"
    lines.append(f"**Verdict: {verdict}** — {len(passed)}/{len(results)} personas passed, "
                 f"frontend {'ok' if front_ok else 'FAILING'}.")
    lines.append("")
    lines.append(f"- Backend: `{BACKEND_URL}`")
    lines.append(f"- Frontend: `{FRONTEND_URL}`")
    lines.append(f"- First `/health` (cold-start indicator): **{cold_start:.2f}s** "
                 f"({'cold, keep-alive is not working' if cold_start > 5 else 'warm'})")
    lines.append("")

    lines.append("## Frontend")
    lines.append("")
    lines.append("| Route | Status | Time | Note |")
    lines.append("|---|---|---|---|")
    for s in front:
        lines.append(f"| {s.name} | {'ok' if s.ok else 'FAIL'} {s.status} | {s.seconds:.2f}s | {s.note} |")
    lines.append("")

    lines.append("## Personas")
    lines.append("")
    lines.append("| # | Persona | Class | Exam | Subject | Result | Total |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, (p, r) in enumerate(zip(PERSONAS, results), start=1):
        lines.append(f"| {i} | {r.persona} | {p.class_level} | {p.onboard_exam} | {p.subject} | "
                     f"{'PASS' if r.ok else 'FAIL'} | {r.total_seconds:.1f}s |")
    lines.append("")

    # Latency per step, across personas — the number that decides whether a
    # recruiter waits or leaves.
    lines.append("## Latency by step")
    lines.append("")
    lines.append("| Step | n | min | median | max |")
    lines.append("|---|---|---|---|---|")
    by_step: dict[str, list[float]] = {}
    for r in results:
        for s in r.steps:
            by_step.setdefault(s.name, []).append(s.seconds)
    for name, vals in by_step.items():
        vals.sort()
        median = vals[len(vals) // 2]
        lines.append(f"| {name} | {len(vals)} | {vals[0]:.2f}s | {median:.2f}s | {vals[-1]:.2f}s |")
    lines.append("")

    if failed:
        lines.append("## Failures")
        lines.append("")
        for r in failed:
            lines.append(f"### {r.persona} (`{r.email}`)")
            for s in r.steps:
                if not s.ok:
                    lines.append(f"- **{s.name}** status={s.status} after {s.seconds:.2f}s: {s.note}")
            lines.append("")

    lines.append("## Cleanup")
    lines.append("")
    lines.append(f"Accounts created use the `smoke-{RUN_TAG}-NN@upmyrank.test` pattern. Purge with:")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 scripts/diag_cleanup_test_accounts.py --dry-run")
    lines.append("python3 scripts/diag_cleanup_test_accounts.py --execute")
    lines.append("```")
    return "\n".join(lines)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=5,
                    help="personas in flight at once (default 5, surfaces pool exhaustion)")
    ap.add_argument("--limit", type=int, default=len(PERSONAS), help="run only the first N personas")
    ap.add_argument("--report", default=None, help="write the Markdown report to this path")
    args = ap.parse_args()

    selected = PERSONAS[: args.limit]

    print(f"Backend : {BACKEND_URL}")
    print(f"Frontend: {FRONTEND_URL}")
    print(f"Personas: {len(selected)}  concurrency={args.concurrency}\n")

    # Measure cold start BEFORE anything else — this is the number that
    # explains the "clicking does nothing" report.
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        try:
            await c.get(f"{BACKEND_URL}/health")
        except Exception as exc:
            print(f"  /health failed: {exc}")
    cold_start = time.perf_counter() - t0
    print(f"cold-start probe: {cold_start:.2f}s "
          f"({'COLD — keep-alive not working' if cold_start > 5 else 'warm'})\n")

    front = await check_frontend()
    for s in front:
        print(f"  [{'ok  ' if s.ok else 'FAIL'}] {s.name:24s} {s.seconds:6.2f}s {s.note}")
    print()

    sem = asyncio.Semaphore(args.concurrency)
    tasks = [run_persona(i, p, sem) for i, p in enumerate(selected, start=1)]

    results: list[PersonaResult] = []
    for coro in asyncio.as_completed(tasks):
        r = await coro
        results.append(r)
        mark = "PASS" if r.ok else "FAIL"
        bad = "" if r.ok else "  <- " + ", ".join(s.name for s in r.steps if not s.ok)
        print(f"  [{mark}] {r.persona:18s} {r.total_seconds:6.1f}s{bad}")

    # as_completed scrambles order; restore persona order for the report
    order = {p.name: i for i, p in enumerate(selected)}
    results.sort(key=lambda r: order[r.persona])

    report = build_report(front, results, cold_start)
    if args.report:
        with open(args.report, "w") as fh:
            fh.write(report)
        print(f"\nreport written to {args.report}")

    failed = [r for r in results if not r.ok]
    front_ok = all(s.ok for s in front)
    print(f"\n{'PASS' if (front_ok and not failed) else 'FAIL'}: "
          f"{len(results) - len(failed)}/{len(results)} personas passed")
    return 0 if (front_ok and not failed) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
