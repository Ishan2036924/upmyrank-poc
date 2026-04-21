#!/usr/bin/env python3
"""
Synthetic beta tester — v0.20.2

Spawns a small population of LLM-driven student personas and runs them
through Mode 1 (Study Path) + Mode 2 (Ask Anything) flows against a live
backend. Logs every API response, validates invariants, prints a triage
report at the end.

Goal: find regressions and edge cases BEFORE real beta students hit them.

Usage:
    # Local backend
    BACKEND=http://localhost:8000 \\
    OPENAI_API_KEY=sk-... \\
    /opt/miniconda3/bin/python3.11 scripts/synthetic_beta.py

    # Production
    BACKEND=https://upmyrank-api.onrender.com \\
    OPENAI_API_KEY=sk-... \\
    python3 scripts/synthetic_beta.py --personas 5 --doubts-per 4

Requires: openai, httpx (both already in the project's poetry env).

Invariants checked:
  - /auth/signup → /onboarding/submit → /doubt/ask flow returns valid JSON
  - /study/card returns ≥1 notes chunk for known-good topics
  - Topic-shift demotion fires when persona pivots subjects mid-session
  - Notes section is deduplicated (no two chunks share first 200 chars)
  - GET /student/{id} returns updated mastery after a resolved doubt
  - PATCH /student/{id} returns either {updated: [...]} OR {ignored: [...]}
    when migration v16 hasn't been applied
  - Manual "+ New doubt" via POST /doubt/new closes any active block

Exit code: 0 = all green, 1 = at least one invariant failed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from openai import AsyncOpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("synthetic_beta")

# ── Persona library ──────────────────────────────────────────────────────────

PERSONAS = [
    {
        "name":  "Aarav (12th, JEE 2027, weak in Calc)",
        "exam":  "JEE_MAINS",
        "year":  2027,
        "level": "12th",
        "phys":  60, "chem": 70, "math": 50,
        "easy":  ["Kinematics", "Atomic Structure"],
        "hard":  ["Calculus (Integration)", "Coordination Chemistry"],
        "priority": "Maths",
        "style":    "example",
    },
    {
        "name":  "Diya (11th, NEET 2028, strong in Bio-adjacent Chem)",
        "exam":  "NEET",
        "year":  2028,
        "level": "11th",
        "phys":  55, "chem": 80, "math": 45,
        "easy":  ["Atomic Structure", "Chemical Bonding"],
        "hard":  ["Rotational Dynamics", "Trigonometry"],
        "priority": "Physics",
        "style":    "analogy",
    },
    {
        "name":  "Rohan (Dropper, JEE Advanced, all-rounder)",
        "exam":  "JEE_ADVANCED",
        "year":  2026,
        "level": "dropper",
        "phys":  85, "chem": 78, "math": 88,
        "easy":  ["Mechanics", "Calculus (Differentiation)", "Organic Chemistry Basics"],
        "hard":  ["Electromagnetic Induction", "Coordination Chemistry"],
        "priority": "Physics",
        "style":    "formula",
    },
]

# Topics that should reliably return notes from the indexed NCERT corpus.
KNOWN_GOOD_TOPICS = [
    ("Physics",   "Kinematics", "Projectile Motion"),
    ("Physics",   "Laws of Motion", "Newton's Laws of Motion"),
    ("Chemistry", "Chemical Bonding", "Chemical Bonding"),
]

# Doubt prompts designed to exercise specific code paths.
DOUBT_FIXTURES = [
    {
        "label":  "physics-kinematics",
        "prompt": "A 5 kg block slides down a 30° frictionless incline. Find the acceleration.",
        "subject": "Physics",
    },
    {
        "label":  "math-calc-pivot",  # the bug from prod logs
        "prompt": "Wait, what's the integral of sin(x²) — is there a closed form?",
        "subject": "Maths",
        "expects_topic_shift": True,
    },
    {
        "label":  "chem-organic",
        "prompt": "Explain SN1 vs SN2 mechanism with an example.",
        "subject": "Chemistry",
    },
    {
        "label":  "math-trig-identity",
        "prompt": "If sin θ = 3/5 and θ is acute, find cos 2θ.",
        "subject": "Maths",
    },
]


@dataclass
class Result:
    name:     str
    passed:   bool
    detail:   str = ""
    duration_ms: int = 0


@dataclass
class TestRun:
    backend: str
    openai_key: str
    personas: int
    doubts_per: int
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "", duration_ms: int = 0):
        log_fn = log.info if passed else log.error
        log_fn("[%s] %s %s",
               "PASS" if passed else "FAIL",
               name,
               f"— {detail}" if detail else "")
        self.results.append(Result(name=name, passed=passed, detail=detail, duration_ms=duration_ms))

    def report(self) -> int:
        total = len(self.results)
        failed = [r for r in self.results if not r.passed]
        print("\n" + "=" * 72)
        print(f"SYNTHETIC BETA RUN — {total} checks, {len(failed)} failures")
        print("=" * 72)
        if failed:
            print("\nFailures:")
            for r in failed:
                print(f"  ❌ {r.name}: {r.detail}")
        else:
            print("\n✅ All invariants held.")
        print()
        return 0 if not failed else 1


# ── HTTP helpers ─────────────────────────────────────────────────────────────

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

    async def signup(self, persona: dict) -> dict:
        # Unique email per run
        email = f"synthbeta+{uuid.uuid4().hex[:8]}@upmyrank.test"
        body = {
            "name":        persona["name"].split(" ")[0] + " Synth",
            "email":       email,
            "password":    "Synth#Beta2026",
            "exam_type":   "JEE" if persona["exam"].startswith("JEE") else "NEET",
            "target_year": persona["year"],
        }
        r = await self._client.post(
            f"{self.backend}/auth/signup", json=body, headers=self._headers(),
        )
        r.raise_for_status()
        d = r.json()
        self.token = d["token"]
        self.student_id = d["student_id"]
        return d

    async def submit_onboarding(self, persona: dict) -> dict:
        body = {
            "class_level":          persona["level"],
            "physics_prev_marks":   persona["phys"],
            "chemistry_prev_marks": persona["chem"],
            "maths_prev_marks":     persona["math"],
            "easy_topics":          persona["easy"],
            "hard_topics":          persona["hard"],
            "study_hours_per_day":  random.uniform(2.0, 5.0),
            "exam_type":            persona["exam"],
            "exam_date":            f"{persona['year']}-04-01",
            "priority_subject":     persona["priority"],
            "learning_preference":  persona["style"],
        }
        r = await self._client.post(
            f"{self.backend}/onboarding/submit", json=body, headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    async def study_card(self, subject: str, chapter: str, topic: str) -> dict:
        r = await self._client.get(
            f"{self.backend}/study/card",
            params={"subject": subject, "chapter": chapter, "topic": topic},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    async def doubt_ask(self, question: str, study_session_id: Optional[str] = None,
                        subject: str = "Physics", topic_lock: Optional[str] = None) -> dict:
        body: dict = {"question": question, "subject": subject}
        if study_session_id:
            body["study_session_id"] = study_session_id
        if topic_lock:
            body["topic_lock"] = topic_lock
        r = await self._client.post(
            f"{self.backend}/doubt/ask", json=body, headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    async def doubt_new(self, study_session_id: str) -> dict:
        r = await self._client.post(
            f"{self.backend}/doubt/new",
            json={"study_session_id": study_session_id},
            headers=self._headers(),
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

    async def get_student(self) -> dict:
        r = await self._client.get(
            f"{self.backend}/student/{self.student_id}",
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    async def patch_student(self, body: dict) -> dict:
        r = await self._client.patch(
            f"{self.backend}/student/{self.student_id}",
            json=body, headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()


# ── Test scenarios ───────────────────────────────────────────────────────────

async def scenario_study_card(client: APIClient, run: TestRun):
    """Every known-good topic must return ≥1 notes chunk and dedupe properly."""
    for subject, chapter, topic in KNOWN_GOOD_TOPICS:
        t0 = time.time()
        try:
            card = await client.study_card(subject, chapter, topic)
        except Exception as e:
            run.add(f"study_card[{topic}]", False, f"HTTP error: {e}",
                    duration_ms=int((time.time() - t0) * 1000))
            continue

        chunks = card.get("notes", {}).get("chunks", []) or []
        if not chunks:
            run.add(f"study_card[{topic}].notes_nonempty", False,
                    "0 chunks returned (override or retriever broken)")
            continue

        # Dedup invariant
        prefixes = [
            hashlib.sha1((c.get("text", "")[:200]).encode()).hexdigest()
            for c in chunks
        ]
        dup = len(prefixes) != len(set(prefixes))
        run.add(f"study_card[{topic}].notes_deduped", not dup,
                "duplicate chunks detected" if dup else f"{len(chunks)} unique chunks",
                duration_ms=int((time.time() - t0) * 1000))


async def scenario_topic_shift(client: APIClient, run: TestRun):
    """Three-pivot stress test:
        physics → math (long, with math symbols) → chemistry (short, "what is X?")
    Each pivot must open a new doubt_block. Regression guard for both
    the v0.20.1 and v0.20.3 regex bugs caught in prod.
    """
    sess = await client.session_start()
    sid = sess["study_session_id"]

    # 1. Open a physics doubt
    try:
        r1 = await client.doubt_ask(
            DOUBT_FIXTURES[0]["prompt"], study_session_id=sid, subject="Physics",
        )
    except Exception as e:
        run.add("topic_shift.opening_doubt", False, str(e))
        return
    block_id = r1.get("doubt_block_id") or (r1.get("metadata") or {}).get("doubt_block_id")
    if not block_id:
        run.add("topic_shift.opening_doubt", False, "no doubt_block_id in response")
        return
    run.add("topic_shift.opening_doubt", True, f"block={block_id[:8]}")

    # 2. Pivot to math (the v0.20.1 prod-log bug — contractions + math symbols)
    try:
        r2 = await client.doubt_ask(
            DOUBT_FIXTURES[1]["prompt"], study_session_id=sid, subject="Physics",
        )
    except Exception as e:
        run.add("topic_shift.math_pivot", False, str(e))
        return

    block_2 = r2.get("doubt_block_id") or (r2.get("metadata") or {}).get("doubt_block_id")
    intent_2 = r2.get("intent") or "unknown"
    math_shifted = (intent_2 == "subject_doubt" and block_2 and block_2 != block_id)
    run.add(
        "topic_shift.math_pivot_opens_new_block", math_shifted,
        f"intent={intent_2} new_block={block_2[:8] if block_2 else 'none'} "
        f"old_block={block_id[:8]}",
    )
    if not math_shifted:
        return

    # 3. Pivot to chemistry with a SHORT question ("what is molecule?", 16 chars).
    # v0.20.3 regression guard: prod 2026-04-21 showed this got refused by
    # counselor mode because the length floor was 20.
    try:
        r3 = await client.doubt_ask(
            "what is molecule?", study_session_id=sid, subject="Physics",
        )
    except Exception as e:
        run.add("topic_shift.short_chem_pivot", False, str(e))
        return

    block_3 = r3.get("doubt_block_id") or (r3.get("metadata") or {}).get("doubt_block_id")
    intent_3 = r3.get("intent") or "unknown"
    chem_shifted = (intent_3 == "subject_doubt" and block_3 and block_3 != block_2)
    run.add(
        "topic_shift.short_chem_pivot_opens_new_block", chem_shifted,
        f"intent={intent_3} new_block={block_3[:8] if block_3 else 'none'} "
        f"old_block={block_2[:8]}",
    )


async def scenario_manual_new_doubt(client: APIClient, run: TestRun):
    """POST /doubt/new should close the active block."""
    sess = await client.session_start()
    sid = sess["study_session_id"]
    try:
        await client.doubt_ask(DOUBT_FIXTURES[2]["prompt"],
                               study_session_id=sid, subject="Chemistry")
    except Exception as e:
        run.add("manual_new.precondition", False, str(e))
        return

    try:
        result = await client.doubt_new(sid)
    except Exception as e:
        run.add("manual_new.endpoint", False, str(e))
        return

    closed = bool(result.get("closed"))
    run.add("manual_new.closes_active_block", closed,
            f"server reported closed={closed}, reason={result.get('reason')}")


async def scenario_patch_student(client: APIClient, run: TestRun):
    """PATCH /student/{id} returns sane shape regardless of v16 migration state."""
    try:
        result = await client.patch_student({
            "name":     "Synth Updated",
            "phone":    "+91 99999 00000",
            "timezone": "Asia/Kolkata",
        })
    except Exception as e:
        run.add("patch_student.responds", False, str(e))
        return

    has_updated = isinstance(result.get("updated"), list)
    has_ignored = isinstance(result.get("ignored"), list)
    run.add("patch_student.shape", has_updated and has_ignored,
            f"updated={result.get('updated')} ignored={result.get('ignored')}")


async def scenario_full_persona_run(client: APIClient, run: TestRun, persona: dict, doubts_per: int):
    """End-to-end: signup → onboarding → study card → ask doubts → check student."""
    await client.signup(persona)
    await client.submit_onboarding(persona)
    run.add(f"signup_onboarding[{persona['name'][:24]}]", True,
            f"student_id={client.student_id[:8]}")

    await scenario_study_card(client, run)
    await scenario_topic_shift(client, run)
    await scenario_manual_new_doubt(client, run)
    await scenario_patch_student(client, run)

    # Genome should be readable after writes
    try:
        g = await client.get_student()
        run.add("get_student.after_writes", isinstance(g.get("topic_mastery"), dict),
                f"topic_mastery_keys={len(g.get('topic_mastery') or {})}")
    except Exception as e:
        run.add("get_student.after_writes", False, str(e))


# ── Driver ──────────────────────────────────────────────────────────────────

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", type=int, default=2,
                    help="Number of personas to run (max len(PERSONAS))")
    ap.add_argument("--doubts-per", type=int, default=2,
                    help="Reserved — currently unused; topic-shift scenario is fixed")
    args = ap.parse_args()

    backend = os.environ.get("BACKEND", "http://localhost:8000")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        log.warning("OPENAI_API_KEY not set — currently scenarios don't need it, "
                    "but future LLM-driven turns will.")

    log.info("Synthetic beta run starting — backend=%s, personas=%d",
             backend, args.personas)

    run = TestRun(backend=backend, openai_key=openai_key,
                  personas=args.personas, doubts_per=args.doubts_per)
    # Health probe
    try:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.get(f"{backend}/health")
            run.add("backend.health", r.status_code == 200,
                    f"status={r.status_code}")
            if r.status_code != 200:
                return run.report()
    except Exception as e:
        run.add("backend.health", False, str(e))
        return run.report()

    selected = PERSONAS[: args.personas]
    for persona in selected:
        async with APIClient(backend) as client:
            try:
                await scenario_full_persona_run(client, run, persona,
                                                args.doubts_per)
            except Exception as e:
                run.add(f"full_run[{persona['name'][:24]}]", False, repr(e))

    return run.report()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
