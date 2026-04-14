#!/usr/bin/env python3
"""
Offline RAGAS-style evaluation pipeline.

Reads golden_dataset.json, runs each question through AgenticRetriever,
calls evaluate_response() on the (question, RAG context) pair, and prints
a per-dimension score report.

Usage:
    python scripts/eval_ragas.py
    python scripts/eval_ragas.py --golden scripts/data/golden_dataset.json
    python scripts/eval_ragas.py --days 7  # also fetch live judge_evaluations for comparison

Exit code 1 if overall_score average < 0.6.

Requirements:
    Run from the project root with Poetry:
    PYTHONPATH="" PYTHONHOME="" /opt/miniconda3/bin/python3.11 -m poetry run python scripts/eval_ragas.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import openai  # noqa: E402
import asyncpg  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.eval.judge import evaluate_response  # noqa: E402
from app.services.rag.agent import AgenticRetriever  # noqa: E402
from app.services.rag.embeddings import EmbeddingService  # noqa: E402
from app.services.rag.retriever import Retriever  # noqa: E402

PASS_THRESHOLD = 0.60   # exit code 1 if avg overall_score < this

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def color_score(score: float, lo: float = 0.5, hi: float = 0.75) -> str:
    c = GREEN if score >= hi else (YELLOW if score >= lo else RED)
    return f"{c}{score:.3f}{RESET}"


async def run_eval(golden_path: Path) -> float:
    """Run evaluation and return average overall_score."""

    # ── Load golden dataset ────────────────────────────────────────────────────
    with open(golden_path) as f:
        golden = json.load(f)

    print(f"\n{BOLD}UpMyRank Offline Eval — {len(golden)} questions{RESET}")
    print(f"Golden dataset: {golden_path}")
    print("─" * 72)

    # ── Init infrastructure ────────────────────────────────────────────────────
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)
    openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    embed_svc = EmbeddingService()
    retriever = Retriever(db_pool=pool, embedding_service=embed_svc)
    agentic = AgenticRetriever(
        openai_client=openai_client,
        retriever=retriever,
        pool=pool,
        embed_service=embed_svc,
    )

    results: list[dict[str, Any]] = []

    for i, item in enumerate(golden, 1):
        question = item["question"]
        subject  = item.get("subject", "Physics")
        hint_lvl = item.get("expected_hint_level", 0)
        tags     = item.get("tags", [])

        print(f"\n[{i}/{len(golden)}] {subject} · {tags[0] if tags else '?'}")
        print(f"  Q: {question[:80]}…" if len(question) > 80 else f"  Q: {question}")

        # ── 1. Retrieve context ────────────────────────────────────────────────
        try:
            rag = await agentic.run(
                question=question,
                subject=subject,
                hint_level=hint_lvl,
            )
            context = rag.get("context_text", "")
            chunks  = rag.get("chunk_count", 0)
            latency = rag.get("retrieval_latency_ms", 0)
            print(f"  RAG: {chunks} chunks, {latency}ms")
        except Exception as exc:
            print(f"  {RED}RAG failed: {exc}{RESET}")
            context = ""
            latency = 0

        # ── 2. Generate a minimal Socratic response for evaluation ─────────────
        # We build a minimal response from the context + question rather than
        # running the full SocraticEngine (avoids DB state + auth dependencies).
        try:
            stub_response = await _generate_stub_response(
                openai_client, question, context, subject
            )
        except Exception as exc:
            print(f"  {RED}Stub response failed: {exc}{RESET}")
            stub_response = "I'm not sure how to approach this."

        # ── 3. Judge the response ──────────────────────────────────────────────
        try:
            scores = await evaluate_response(
                question=question,
                ai_response=stub_response,
                rag_context=context,
                hint_level=hint_lvl,
                prior_attempts=0,
            )
        except Exception as exc:
            print(f"  {RED}Judge failed: {exc}{RESET}")
            scores = {"overall_score": -1.0}

        overall = scores.get("overall_score", -1.0)
        ped     = scores.get("pedagogical_score", -1)
        factual = scores.get("factual_score", -1)
        ctx_rel = scores.get("context_relevance_score", -1)
        hint_ap = scores.get("hint_appropriateness_score", -1)

        print(f"  Scores — pedagogy:{ped}  factual:{factual}  ctx_rel:{ctx_rel}  hint_ap:{hint_ap}  "
              f"overall:{color_score(overall) if overall >= 0 else RED+str(overall)+RESET}")

        results.append({
            "question":                   question,
            "subject":                    subject,
            "overall_score":              overall,
            "pedagogical_score":          ped,
            "factual_score":              factual,
            "context_relevance_score":    ctx_rel,
            "hint_appropriateness_score": hint_ap,
            "retrieval_latency_ms":       latency,
        })

    await pool.close()

    # ── Print summary ─────────────────────────────────────────────────────────
    valid = [r for r in results if r["overall_score"] >= 0]
    if not valid:
        print(f"\n{RED}No valid results — all judge calls failed.{RESET}")
        return 0.0

    avg_overall = sum(r["overall_score"] for r in valid) / len(valid)
    avg_ped     = sum(r["pedagogical_score"] for r in valid if r["pedagogical_score"] >= 0) / max(1, sum(1 for r in valid if r["pedagogical_score"] >= 0))
    avg_fact    = sum(r["factual_score"] for r in valid if r["factual_score"] >= 0) / max(1, sum(1 for r in valid if r["factual_score"] >= 0))
    avg_ctx     = sum(r["context_relevance_score"] for r in valid if r["context_relevance_score"] >= 0) / max(1, sum(1 for r in valid if r["context_relevance_score"] >= 0))
    avg_hint    = sum(r["hint_appropriateness_score"] for r in valid if r["hint_appropriateness_score"] >= 0) / max(1, sum(1 for r in valid if r["hint_appropriateness_score"] >= 0))
    avg_latency = sum(r["retrieval_latency_ms"] for r in results) / len(results)

    pass_count = sum(1 for r in valid if r["overall_score"] >= PASS_THRESHOLD)
    pass_rate  = pass_count / len(valid)

    print("\n" + "═" * 72)
    print(f"{BOLD}EVALUATION SUMMARY — {len(valid)}/{len(golden)} questions scored{RESET}")
    print("─" * 72)
    print(f"  Avg pedagogical score:      {avg_ped:.3f} / 2.0")
    print(f"  Avg factual score:          {avg_fact:.3f} / 1.0")
    print(f"  Avg context relevance:      {avg_ctx:.3f} / 1.0")
    print(f"  Avg hint appropriateness:   {avg_hint:.3f} / 1.0")
    print(f"  Avg retrieval latency:      {avg_latency:.0f} ms")
    print("─" * 72)
    print(f"  Avg OVERALL score:          {color_score(avg_overall, lo=0.5, hi=0.75)} / 1.0")
    print(f"  Pass rate (≥{PASS_THRESHOLD:.0%}):         {color_score(pass_rate)}  ({pass_count}/{len(valid)})")
    print("═" * 72)

    if avg_overall < PASS_THRESHOLD:
        print(f"\n{RED}{BOLD}❌ FAIL — avg overall score {avg_overall:.3f} below threshold {PASS_THRESHOLD}{RESET}")
    else:
        print(f"\n{GREEN}{BOLD}✅ PASS — avg overall score {avg_overall:.3f} ≥ threshold {PASS_THRESHOLD}{RESET}")
    print()

    return avg_overall


async def _generate_stub_response(
    client: openai.AsyncOpenAI,
    question: str,
    context: str,
    subject: str,
) -> str:
    """
    Generate a minimal Socratic tutor response using retrieved context.
    Used only for eval — not the full SocraticEngine pipeline.
    """
    ctx_block = f"\nContext:\n{context[:1200]}\n" if context else ""
    prompt = (
        f"You are a Socratic JEE tutor for {subject}.\n"
        f"{ctx_block}\n"
        f"Student question: {question}\n\n"
        f"Ask ONE guiding Socratic question to help the student think through this. "
        f"Do NOT give the answer. Maximum 60 words."
    )
    resp = await client.chat.completions.create(
        model=settings.model_cheap,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=120,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip()


def main():
    parser = argparse.ArgumentParser(description="UpMyRank offline RAGAS-style evaluation")
    parser.add_argument(
        "--golden",
        default=str(ROOT / "scripts" / "data" / "golden_dataset.json"),
        help="Path to golden dataset JSON",
    )
    args = parser.parse_args()

    golden_path = Path(args.golden)
    if not golden_path.exists():
        print(f"Golden dataset not found: {golden_path}", file=sys.stderr)
        sys.exit(1)

    avg_overall = asyncio.run(run_eval(golden_path))

    if avg_overall < PASS_THRESHOLD:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
