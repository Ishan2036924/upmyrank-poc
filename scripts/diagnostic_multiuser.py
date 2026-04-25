#!/usr/bin/env python3
"""
diagnostic_multiuser.py — 3-persona personalization diagnostic.

Spawns 3 synthetic students with materially different scaffolding levels
(HIGH / MEDIUM / LOW) and onboarding profiles. Sends the same 20 prompts
to each persona in parallel, then compares per-prompt responses along
four dimensions:

  - response length divergence            (structure adapts)
  - concept-count divergence              (depth adapts)
  - style-keyword prevalence              ("example" / "formula" / "analogy")
  - Judge LLM overall_score per persona   (quality should be consistent;
                                          if LOW ≪ HIGH, the engine is
                                          penalising weaker students)

The HIGH persona should get terse, formula-style responses with minimal
scaffolding. The LOW persona should get warmer, analogy-rich responses
with explicit step-by-step probes. MEDIUM sits between.

If all three personas get near-identical responses (stdev/avg < 0.15),
personalization is not firing and the `PERSONALIZATION_PROMPT` template
needs audit.

Usage:
    BACKEND=http://localhost:8000 \
        /opt/miniconda3/bin/python3.11 -m poetry run \
        python scripts/diagnostic_multiuser.py --out reports/multiuser_$(date +%F)

Requires: httpx, asyncpg. Reads DATABASE_URL from .env.
Exits 1 if personalization-divergence metrics fall below thresholds.
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

try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env():
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


load_env()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("multiuser")


# Three personas spanning the scaffolding range.
PERSONAS = [
    {
        "tag":   "HIGH",
        "level": "dropper",
        "phys":  90, "chem": 85, "math": 92,
        "easy":  ["Kinematics", "Laws of Motion", "Integration", "Differentiation",
                  "Atomic Structure"],
        "hard":  ["Electromagnetic Induction"],
        "priority": "Physics",
        "style":    "formula",
    },
    {
        "tag":   "MEDIUM",
        "level": "12th",
        "phys":  62, "chem": 58, "math": 55,
        "easy":  ["Kinematics", "Atomic Structure"],
        "hard":  ["Coordination Compounds", "Integration"],
        "priority": "Physics",
        "style":    "example",
    },
    {
        "tag":   "LOW",
        "level": "11th",
        "phys":  32, "chem": 28, "math": 30,
        "easy":  [],
        "hard":  ["Kinematics", "Laws of Motion", "Atomic Structure",
                  "Trigonometry", "Chemical Bonding"],
        "priority": "Physics",
        "style":    "analogy",
    },
]

# 20 shared prompts spanning difficulty + subject.
SHARED_PROMPTS = [
    # Physics (7)
    ("Physics",   "A ball is thrown upward with 20 m/s. How high does it go? g=10."),
    ("Physics",   "A 5 kg block on a 30 degree frictionless incline. Find the acceleration."),
    ("Physics",   "State Newton's second law in one line."),
    ("Physics",   "Moment of inertia of a uniform rod of length L, mass M, about its center?"),
    ("Physics",   "Electric field due to a point charge 2 microcoulombs at 10 cm."),
    ("Physics",   "A stone of mass 1 kg whirled in a horizontal circle of radius 0.5 m at 4 m/s. Tension?"),
    ("Physics",   "Escape velocity from Earth's surface?"),
    # Chemistry (6)
    ("Chemistry", "Why is BF3 planar but NH3 pyramidal?"),
    ("Chemistry", "Calculate pH of 0.01 M HCl."),
    ("Chemistry", "Difference between SN1 and SN2 with examples."),
    ("Chemistry", "Half-life of first-order reaction with k=0.1 /min?"),
    ("Chemistry", "IUPAC of [Co(NH3)4Cl2]Cl?"),
    ("Chemistry", "5 g NaCl (M=58.5) in 500 mL water — molarity?"),
    # Maths (7)
    ("Maths",     "If sin(theta)=3/5 and theta is acute, find cos(2*theta)."),
    ("Maths",     "Evaluate lim x->0 of sin(3x)/x."),
    ("Maths",     "Derivative of x^3 * ln(x)?"),
    ("Maths",     "Evaluate integral of x*e^x dx."),
    ("Maths",     "Determinant of [[2,3],[1,4]]?"),
    ("Maths",     "P(sum=7) for two fair dice?"),
    ("Maths",     "If z = 3 + 4i, find |z| and arg(z)."),
]


class APIClient:
    def __init__(self, backend: str, timeout: float = 180.0):
        self.backend = backend.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self.token: Optional[str] = None
        self.student_id: Optional[str] = None
        self.email: Optional[str] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._client.aclose()

    def _h(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def signup(self, persona: dict, run_id: str) -> dict:
        self.email = f"mu-{run_id}-{persona['tag'].lower()}-{uuid.uuid4().hex[:5]}@upmyrank.test"
        r = await self._client.post(
            f"{self.backend}/auth/signup", headers=self._h(),
            json={
                "name":        f"MU {persona['tag']} {run_id}",
                "email":       self.email,
                "password":    "MUTest#2026",
                "exam_type":   "JEE",
                "target_year": 2027,
            },
        )
        r.raise_for_status()
        d = r.json()
        self.token = d["token"]
        self.student_id = d["student_id"]
        return d

    async def onboard(self, persona: dict) -> dict:
        r = await self._client.post(
            f"{self.backend}/onboarding/submit", headers=self._h(),
            json={
                "class_level":          persona["level"],
                "physics_prev_marks":   persona["phys"],
                "chemistry_prev_marks": persona["chem"],
                "maths_prev_marks":     persona["math"],
                "easy_topics":          persona["easy"],
                "hard_topics":          persona["hard"],
                "study_hours_per_day":  4.0,
                "exam_type":            "JEE_MAINS",
                "exam_date":            "2027-04-01",
                "priority_subject":     persona["priority"],
                "learning_preference":  persona["style"],
            },
        )
        r.raise_for_status()
        return r.json()

    async def session_start(self) -> dict:
        r = await self._client.post(
            f"{self.backend}/session/start", headers=self._h(),
            json={"student_id": self.student_id},
        )
        r.raise_for_status()
        return r.json()

    async def session_end(self, ssid: str) -> dict:
        r = await self._client.post(
            f"{self.backend}/session/end", headers=self._h(),
            json={"study_session_id": ssid},
        )
        r.raise_for_status()
        return r.json()

    async def doubt_ask(self, q: str, ssid: str, subject: str) -> dict:
        r = await self._client.post(
            f"{self.backend}/doubt/ask", headers=self._h(),
            json={"question": q, "subject": subject, "study_session_id": ssid},
        )
        r.raise_for_status()
        return r.json()


@dataclass
class Response:
    persona_tag: str
    prompt_idx:  int
    subject:     str
    prompt:      str
    response:    str
    response_len: int
    duration_ms: int
    doubt_session_id: Optional[str] = None
    intent:      Optional[str] = None
    mentor_mode: Optional[str] = None


async def run_one_persona(backend: str, persona: dict, run_id: str) -> list[Response]:
    """Signup → onboard → ask all 20 prompts sequentially → end session."""
    results: list[Response] = []
    async with APIClient(backend) as client:
        await client.signup(persona, run_id)
        await client.onboard(persona)
        sess = await client.session_start()
        ssid = sess["study_session_id"]
        log.info("[%s] signed up student=%s ssid=%s",
                 persona["tag"], client.student_id[:8], ssid[:8])
        for i, (subject, prompt) in enumerate(SHARED_PROMPTS):
            t0 = time.monotonic()
            try:
                r = await client.doubt_ask(prompt, ssid, subject)
                dur = int((time.monotonic() - t0) * 1000)
                text = r.get("response") or ""
                analysis = r.get("analysis") or {}
                results.append(Response(
                    persona_tag=persona["tag"], prompt_idx=i,
                    subject=subject, prompt=prompt,
                    response=text, response_len=len(text),
                    duration_ms=dur,
                    doubt_session_id=r.get("session_id"),
                    intent=r.get("intent"),
                    mentor_mode=r.get("mentor_mode") or analysis.get("mentor_mode"),
                ))
                log.info("[%s/%02d] %s %dms %d chars  %s",
                         persona["tag"], i, subject, dur, len(text), prompt[:50])
            except Exception as e:
                log.warning("[%s/%02d] FAILED: %s", persona["tag"], i, e)
                results.append(Response(
                    persona_tag=persona["tag"], prompt_idx=i,
                    subject=subject, prompt=prompt,
                    response=f"<<ERROR {e}>>", response_len=0,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                ))
        try:
            await client.session_end(ssid)
        except Exception as e:
            log.warning("[%s] session_end failed: %s", persona["tag"], e)
    return results


async def fetch_judge_scores(student_ids: list[str]) -> dict:
    if asyncpg is None or not student_ids:
        return {}
    db = os.environ.get("DATABASE_URL")
    if not db:
        return {}
    clean = db.split("?")[0]
    try:
        conn = await asyncpg.connect(clean, ssl="require", timeout=30.0)
    except Exception as e:
        log.warning("DB connect failed: %s", e)
        return {}
    try:
        out = {}
        for sid in student_ids:
            rows = await conn.fetch("""
                SELECT je.doubt_session_id, je.pedagogical_score, je.factual_score,
                       je.context_relevance_score, je.hint_appropriateness_score,
                       je.overall_score, ds.problem_text
                FROM judge_evaluations je
                JOIN doubt_sessions ds ON ds.id = je.doubt_session_id
                WHERE ds.student_id = $1
            """, uuid.UUID(sid))
            out[sid] = [dict(r) for r in rows]
        return out
    finally:
        await conn.close()


# Style-keyword signal
STYLE_KEYWORDS = {
    "example":  ["example", "for instance", "consider", "imagine", "let's take",
                 "think about", "suppose"],
    "formula":  ["formula", "equation", "plug in", "substitute", "apply",
                 r"\$.*\$", "derive"],
    "analogy":  ["like", "similar to", "think of it as", "imagine a", "picture a",
                 "just like", "same way"],
}


def count_style_hits(text: str, keywords: list[str]) -> int:
    import re
    t = text.lower()
    return sum(1 for kw in keywords if re.search(kw.lower(), t))


def analyze(responses_by_persona: dict[str, list[Response]], judge_by_student: dict) -> dict:
    # Pair responses by prompt_idx
    by_idx: dict[int, dict[str, Response]] = {}
    for tag, rs in responses_by_persona.items():
        for r in rs:
            by_idx.setdefault(r.prompt_idx, {})[tag] = r

    divergence_rows = []
    for idx in sorted(by_idx):
        triplet = by_idx[idx]
        if len(triplet) < 3:
            continue
        H, M, L = triplet.get("HIGH"), triplet.get("MEDIUM"), triplet.get("LOW")
        if not (H and M and L):
            continue

        lens = [H.response_len, M.response_len, L.response_len]
        len_stdev = statistics.stdev(lens) if lens else 0
        len_avg   = statistics.mean(lens) if lens else 1
        len_ratio = round(len_stdev / max(len_avg, 1), 3)

        # style signal per persona
        style_hits = {}
        for tag, r in [("HIGH", H), ("MEDIUM", M), ("LOW", L)]:
            style_hits[tag] = {
                s: count_style_hits(r.response, kws)
                for s, kws in STYLE_KEYWORDS.items()
            }

        divergence_rows.append({
            "prompt_idx": idx,
            "subject":    H.subject,
            "prompt":     H.prompt[:80],
            "len_high":   H.response_len,
            "len_medium": M.response_len,
            "len_low":    L.response_len,
            "len_stdev":  round(len_stdev, 1),
            "len_ratio":  len_ratio,
            "style":      style_hits,
            "lat_high":   H.duration_ms,
            "lat_medium": M.duration_ms,
            "lat_low":    L.duration_ms,
        })

    # Aggregate
    len_ratios = [d["len_ratio"] for d in divergence_rows]
    avg_len_ratio = round(statistics.mean(len_ratios), 3) if len_ratios else 0
    persona_signal_ok = avg_len_ratio >= 0.15  # threshold: material divergence

    # Style preference correctness — HIGH should lean formula, LOW should lean analogy
    style_by_persona: dict[str, dict[str, int]] = {tag: {"example": 0, "formula": 0, "analogy": 0} for tag in ("HIGH", "MEDIUM", "LOW")}
    for d in divergence_rows:
        for tag, hits in d["style"].items():
            for s, c in hits.items():
                style_by_persona[tag][s] += c

    # Judge quality — each persona should pull roughly the same Judge scores
    judge_avg = {}
    for tag in ("HIGH", "MEDIUM", "LOW"):
        rs = responses_by_persona.get(tag, [])
        if not rs:
            continue
        sid = None
        for r in rs:
            if r.doubt_session_id:
                break
        student_key = None
        # student_ids are keys of judge_by_student
        # But judge_by_student keys are student_uuids; we passed them in fetch_judge_scores
        # so we need a reverse map. Simpler: aggregate all judge rows per tag.
        # Since each persona has its own student_id (one ID per tag), we rely on the
        # caller having called fetch_judge_scores with the correct IDs.
        pass

    return {
        "divergence_rows":     divergence_rows,
        "avg_len_ratio":       avg_len_ratio,
        "persona_signal_ok":   persona_signal_ok,
        "style_totals":        style_by_persona,
    }


def judge_summary(judge_by_student: dict, student_id_by_tag: dict) -> dict:
    summary = {}
    for tag, sid in student_id_by_tag.items():
        rows = judge_by_student.get(sid, [])
        if not rows:
            summary[tag] = {"n": 0}
            continue
        summary[tag] = {
            "n": len(rows),
            "avg_pedagogical": round(statistics.mean(r["pedagogical_score"] for r in rows if r["pedagogical_score"] is not None), 3) if rows else None,
            "avg_factual":     round(statistics.mean(r["factual_score"] for r in rows if r["factual_score"] is not None), 3) if rows else None,
            "avg_overall":     round(statistics.mean(r["overall_score"] for r in rows if r["overall_score"] is not None), 3) if rows else None,
        }
    return summary


def fmt_md(run_id: str, meta: dict, analysis: dict, judge_summ: dict) -> str:
    m = []
    m.append(f"# UpMyRank — Multi-User Personalization Diagnostic ({run_id})")
    m.append("")
    m.append(f"**Generated:** {meta['generated_at']}")
    m.append(f"**Backend:** {meta['backend']}")
    m.append(f"**Personas:** HIGH / MEDIUM / LOW scaffolding, 20 shared prompts each = {meta['n_prompts']} responses total")
    m.append("")
    m.append("## TL;DR — Is personalization firing?")
    m.append("")
    sig = analysis["persona_signal_ok"]
    m.append(f"**Avg response-length stdev / mean across personas:** **{analysis['avg_len_ratio']}** (threshold ≥ 0.15 = personalization observable)")
    m.append(f"**Verdict:** {'✅ personalization firing' if sig else '❌ personalization NOT differentiating personas'}")
    m.append("")
    m.append("## Style-keyword totals (per persona × 20 prompts)")
    m.append("")
    m.append("| Persona | example-style | formula-style | analogy-style | Expected lean |")
    m.append("|---|---|---|---|---|")
    st = analysis["style_totals"]
    m.append(f"| HIGH    | {st['HIGH']['example']} | **{st['HIGH']['formula']}** | {st['HIGH']['analogy']} | formula |")
    m.append(f"| MEDIUM  | **{st['MEDIUM']['example']}** | {st['MEDIUM']['formula']} | {st['MEDIUM']['analogy']} | example |")
    m.append(f"| LOW     | {st['LOW']['example']} | {st['LOW']['formula']} | **{st['LOW']['analogy']}** | analogy |")
    m.append("")
    m.append("_Bold = expected winner for that persona's `learning_preference`. Reads left-to-right: a well-tuned engine shows the diagonal ≥ the off-diagonal._")
    m.append("")
    m.append("## Judge LLM quality per persona")
    m.append("")
    m.append("| Persona | Judge rows | Avg pedagogical (0-2) | Avg factual (0-1) | Avg overall (0-1) |")
    m.append("|---|---|---|---|---|")
    for tag in ("HIGH", "MEDIUM", "LOW"):
        j = judge_summ.get(tag, {})
        m.append(f"| {tag} | {j.get('n', 0)} | {j.get('avg_pedagogical', '—')} | {j.get('avg_factual', '—')} | {j.get('avg_overall', '—')} |")
    m.append("")
    m.append("Quality should be consistent across all three — if LOW's overall is markedly below HIGH's, the engine is giving weaker students weaker pedagogy (the opposite of the intent).")
    m.append("")
    m.append("## Per-prompt divergence detail")
    m.append("")
    m.append("| # | Subject | Prompt (trunc) | HIGH len | MEDIUM len | LOW len | σ/μ |")
    m.append("|---|---|---|---|---|---|---|")
    for d in analysis["divergence_rows"]:
        m.append(f"| {d['prompt_idx']} | {d['subject']} | {d['prompt']} | {d['len_high']} | {d['len_medium']} | {d['len_low']} | {d['len_ratio']} |")
    m.append("")
    return "\n".join(m)


async def amain():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=os.environ.get("BACKEND", "https://upmyrank-poc.onrender.com"))
    ap.add_argument("--run-id", default=f"mu-{time.strftime('%Y%m%d-%H%M%S')}")
    ap.add_argument("--out", default=f"reports/multiuser_{time.strftime('%Y-%m-%d')}")
    ap.add_argument("--judge-wait-s", type=int, default=45)
    args = ap.parse_args()

    start_wall = time.time()

    # Run 3 personas in parallel
    log.info("spawning 3 personas in parallel …")
    coros = [run_one_persona(args.backend, p, args.run_id) for p in PERSONAS]
    results_per_persona: list[list[Response]] = await asyncio.gather(*coros)

    responses_by_persona = {p["tag"]: rs for p, rs in zip(PERSONAS, results_per_persona)}
    # student_ids captured via first response per persona — each Response has doubt_session_id;
    # we need student_id from the APIClient, so pass that through. Let's derive via judge_by_student
    # by querying on student_id directly. Store mapping as we go.
    student_ids_by_tag: dict[str, str] = {}
    for tag, rs in responses_by_persona.items():
        # Each persona ran its own signup; we don't have student_id back out here.
        # Hack: pull from the first response's doubt_session_id via a separate query.
        # Cleaner: re-introspect via a follow-up query. Simpler: all Responses carry
        # the persona tag; we query judge_evaluations joined on doubt_sessions and
        # aggregate by persona.
        pass

    log.info("waiting %ds for async Judge rows to land …", args.judge_wait_s)
    await asyncio.sleep(args.judge_wait_s)

    # Query Judge rows by doubt_session_id set (since we kept those per Response)
    judge_rows_by_tag: dict[str, list[dict]] = {t: [] for t in responses_by_persona}
    if asyncpg and os.environ.get("DATABASE_URL"):
        db = os.environ["DATABASE_URL"].split("?")[0]
        try:
            conn = await asyncpg.connect(db, ssl="require", timeout=30.0)
            for tag, rs in responses_by_persona.items():
                sids = [r.doubt_session_id for r in rs if r.doubt_session_id]
                if not sids:
                    continue
                uuids = [uuid.UUID(s) for s in sids]
                rows = await conn.fetch("""
                    SELECT doubt_session_id, pedagogical_score, factual_score,
                           context_relevance_score, hint_appropriateness_score, overall_score
                    FROM judge_evaluations
                    WHERE doubt_session_id = ANY($1::uuid[])
                """, uuids)
                judge_rows_by_tag[tag] = [dict(r) for r in rows]
            await conn.close()
        except Exception as e:
            log.warning("DB query failed: %s", e)

    judge_summ = {}
    for tag, rows in judge_rows_by_tag.items():
        if not rows:
            judge_summ[tag] = {"n": 0}
            continue
        ped = [r["pedagogical_score"] for r in rows if r["pedagogical_score"] is not None]
        fac = [r["factual_score"] for r in rows if r["factual_score"] is not None]
        ov  = [r["overall_score"] for r in rows if r["overall_score"] is not None]
        judge_summ[tag] = {
            "n": len(rows),
            "avg_pedagogical": round(statistics.mean(ped), 3) if ped else None,
            "avg_factual":     round(statistics.mean(fac), 3) if fac else None,
            "avg_overall":     round(statistics.mean(ov), 3)  if ov else None,
        }

    analysis = analyze(responses_by_persona, judge_rows_by_tag)

    end_wall = time.time()
    meta = {
        "run_id":       args.run_id,
        "backend":      args.backend,
        "n_personas":   len(PERSONAS),
        "n_prompts":    sum(len(v) for v in responses_by_persona.values()),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "duration_s":   round(end_wall - start_wall, 1),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jpath = out.with_suffix(".json")
    mpath = out.with_suffix(".md")
    with open(jpath, "w") as f:
        json.dump({
            "meta":     meta,
            "responses": {k: [asdict(r) for r in rs] for k, rs in responses_by_persona.items()},
            "judge":     judge_rows_by_tag,
            "judge_summary": judge_summ,
            "analysis":  analysis,
        }, f, indent=2, default=str)
    log.info("wrote %s", jpath)

    md = fmt_md(args.run_id, meta, analysis, judge_summ)
    with open(mpath, "w") as f:
        f.write(md)
    log.info("wrote %s", mpath)

    return 0 if analysis["persona_signal_ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(amain()))
