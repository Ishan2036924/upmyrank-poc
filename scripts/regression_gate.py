#!/usr/bin/env python3
"""
regression_gate.py — Pre-deploy Socratic quality regression gate.

Loads data/golden_dataset.json (50 ideal tutor responses), scores each with
the Judge LLM, and exits 1 if the pass-rate drops more than 10% below the
expected baseline.

Baseline: every ideal_socratic_response should score >= 1 (Socratic quality).
Gate threshold: pass_rate < 0.90 → FAIL.

This is designed to be run as a pre-deploy step:
    python scripts/regression_gate.py
    python scripts/regression_gate.py --sample 20   # score first 20 entries only
    python scripts/regression_gate.py --threshold 0.85  # custom gate threshold

Exit codes:
    0 — gate passed (quality is acceptable)
    1 — gate failed (quality degraded — block deploy)
    2 — infrastructure error (Judge LLM unreachable, dataset missing)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("regression_gate")


def _load_env() -> None:
    """Load OPENAI_API_KEY from .env if not already set."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, val = line.partition("=")
            if key not in os.environ:
                os.environ[key] = val


async def _score_entry(client, entry: dict, semaphore: asyncio.Semaphore) -> dict:
    """
    Score a single golden dataset entry.

    Uses the ideal_socratic_response (NOT the engine) so the gate tests
    whether the Judge LLM still classifies known-good responses as Socratic.

    Returns: {"id": str, "score": int, "rationale": str, "passed": bool}
    """
    import openai

    system_prompt = (
        "You are evaluating whether an AI tutor response is Socratic.\n"
        "Score the response:\n"
        "  0 = gave full solution or direct answer — student has nothing left to figure out\n"
        "  1 = gave a hint but too vague or too direct — minimal thought required\n"
        "  2 = asked a leading Socratic question that forces the student to reason\n\n"
        'Return JSON only: {"score": int, "rationale": str}'
    )
    user_content = (
        f"STUDENT QUESTION:\n{entry['student_question']}\n\n"
        f"AI TUTOR RESPONSE:\n{entry['ideal_socratic_response']}"
    )

    async with semaphore:
        try:
            resp = await client.chat.completions.create(
                model="gpt-4.1-mini",
                temperature=0,
                max_tokens=200,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_content},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                lines = raw.splitlines()
                inner = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
                raw = "\n".join(inner).strip()
            result = json.loads(raw)
            score = int(result.get("score", -1))
            if score not in (0, 1, 2):
                score = -1
            return {
                "id":       entry["id"],
                "score":    score,
                "rationale": str(result.get("rationale", "")),
                "passed":   score >= 1,
            }
        except Exception as exc:
            logger.warning("Judge failed for entry %s: %s", entry["id"], exc)
            return {"id": entry["id"], "score": -1, "rationale": "judge_failed", "passed": False}


async def run_gate(sample: int | None, threshold: float, concurrency: int) -> int:
    """
    Run the regression gate.

    Returns:
        0 — gate passed
        1 — gate failed (quality too low)
        2 — infrastructure error
    """
    _load_env()
    import openai

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.error("OPENAI_API_KEY not set — cannot run Judge LLM.")
        return 2

    dataset_path = Path(__file__).parent.parent / "data" / "golden_dataset.json"
    if not dataset_path.exists():
        logger.error("Golden dataset not found at %s", dataset_path)
        return 2

    dataset: list[dict] = json.loads(dataset_path.read_text())
    if sample and sample < len(dataset):
        dataset = dataset[:sample]
        logger.info("Sampling %d / %d entries from golden dataset", sample, len(dataset))
    else:
        logger.info("Scoring all %d entries from golden dataset", len(dataset))

    client    = openai.AsyncOpenAI(api_key=api_key)
    semaphore = asyncio.Semaphore(concurrency)

    tasks   = [_score_entry(client, entry, semaphore) for entry in dataset]
    results = await asyncio.gather(*tasks)

    # ── Tally ──────────────────────────────────────────────────────────────────
    scored   = [r for r in results if r["score"] != -1]
    failed   = [r for r in results if r["score"] == -1]
    passed   = [r for r in scored  if r["passed"]]
    score_0  = [r for r in scored  if r["score"] == 0]
    score_1  = [r for r in scored  if r["score"] == 1]
    score_2  = [r for r in scored  if r["score"] == 2]

    total       = len(results)
    pass_rate   = len(passed) / len(scored) if scored else 0.0
    avg_score   = sum(r["score"] for r in scored) / len(scored) if scored else 0.0

    # ── Print report ───────────────────────────────────────────────────────────
    divider = "─" * 60
    print(f"\n{divider}")
    print(f"  Regression Gate Report — Golden Dataset Eval")
    print(f"  Entries scored  : {len(scored)} / {total}")
    print(f"  Judge failures  : {len(failed)}")
    print(f"  Score breakdown : 0={len(score_0)}  1={len(score_1)}  2={len(score_2)}")
    print(f"  Avg score       : {avg_score:.3f}")
    print(f"  Pass rate       : {pass_rate:.1%}  (threshold: {threshold:.1%})")
    print(divider)

    # Show any score-0 entries (full-solution leakage in ideal responses)
    if score_0:
        print("\n  ⚠️  Entries scored 0 (ideal response gave full solution — review dataset quality):")
        for r in score_0:
            print(f"    {r['id']}  —  {r['rationale'][:80]}")

    # ── Gate decision ──────────────────────────────────────────────────────────
    if len(scored) == 0:
        print("\n  ✗  GATE FAILED — no entries could be scored (Judge LLM issue?)\n")
        return 1

    if pass_rate < threshold:
        print(
            f"\n  ✗  GATE FAILED — pass rate {pass_rate:.1%} is below threshold {threshold:.1%}\n"
            f"     Review Socratic prompt quality and golden dataset integrity.\n"
        )
        return 1

    print(f"\n  ✓  GATE PASSED — {pass_rate:.1%} of ideal responses scored Socratic (≥ 1)\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Regression gate — pre-deploy quality check")
    parser.add_argument(
        "--sample", type=int, default=None,
        help="Score first N entries only (default: all 50)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.90,
        help="Minimum pass-rate to clear the gate (default: 0.90)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=5,
        help="Max parallel Judge LLM calls (default: 5)",
    )
    args = parser.parse_args()
    exit_code = asyncio.run(run_gate(args.sample, args.threshold, args.concurrency))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
