"""
Agentic RAG — LLM-driven retrieval loop.

Instead of a single fixed retrieval at session start, the LLM receives the
student question and a set of retrieval tools, and autonomously decides:
  1. Which tool to call first (NCERT? JEE PYQs? Concepts?)
  2. Whether the first result is sufficient, or if a follow-up retrieval is needed
  3. When it has gathered enough context to generate the Socratic response
  4. How to consolidate results from multiple tools via rerank_and_select

Architecture:
  ┌──────────────────────────────────────────────────────────────┐
  │  AgenticRetriever.run(question, subject, topic, hint_level)  │
  │                                                               │
  │  1. Build initial message with question + subject metadata   │
  │  2. Send to LLM with TOOL_SCHEMAS (function calling)         │
  │  3. Loop (max MAX_STEPS times):                              │
  │     a. If LLM called a tool → execute it → append result    │
  │     b. If LLM sent a message (no tool call) → done          │
  │  4. Assemble final context text from accumulated chunks      │
  │  5. Return {"context_text", "chunks", "chunk_count",         │
  │              "tool_trace", "similar_problem"}                │
  └──────────────────────────────────────────────────────────────┘

Invariants preserved:
  - hint_level == 3 → returns empty context immediately (no RAG at all)
  - Redis semantic cache: caches final assembled context, not individual tool calls
  - LaTeX sanitizer is NOT run here (it runs on the LLM Socratic response in engine.py)
  - _genome_update_task is untouched — this module has no mastery logic

Uses native OpenAI function calling (no LangChain/LangGraph).
Model: gpt-4o-mini (cheap tier) — retrieval decisions don't need expensive reasoning.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import asyncpg
import openai

from app.config import settings
from app.services.rag.embeddings import EmbeddingService
from app.services.rag.retriever import Retriever
from app.services.rag.tools import (
    TOOL_SCHEMAS,
    rerank_and_select,
    search_concepts,
    search_jee_problems,
    search_ncert,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_STEPS = 3          # hard cap on retrieval iterations
AGENT_MODEL = "gpt-4o-mini"   # cheap model for retrieval decisions

# ── System prompt for the retrieval agent ─────────────────────────────────────
_AGENT_SYSTEM_PROMPT = """\
You are a retrieval planner for a JEE/NEET tutoring system. Your job is to
retrieve the most relevant context for a student's question so that a Socratic
tutor can generate a high-quality hint or explanation.

You have access to three retrieval tools:
  • search_ncert         — NCERT textbook theory, concepts, derivations (Physics/Chemistry/Maths)
  • search_jee_problems  — 30 years of JEE past year questions with solutions
  • search_concepts      — Concept definitions and prerequisite chains

Retrieval strategy:
  1. For conceptual / derivation questions → start with search_ncert
  2. For numerical / problem-solving questions → use both search_ncert AND search_jee_problems
  3. When you need to verify prerequisites or concept taxonomy → use search_concepts
  4. After 2+ tool calls, ALWAYS end with rerank_and_select to consolidate

Rules:
  • Maximum {max_steps} tool calls total (including rerank_and_select)
  • Always call rerank_and_select as your final step if you made 2+ retrievals
  • If a single search_ncert call returns 3+ highly relevant chunks, that may be enough
  • Do NOT generate tutoring content — only retrieve context
  • When done, respond with exactly: RETRIEVAL_COMPLETE

Subject hint: {subject}
Topic hint: {topic}
Question type: {question_type}
""".strip()

# ── EMPTY context (returned at hint_level == 3, preserves nuclear override) ──
_EMPTY_CONTEXT: dict = {
    "context_text":        "",
    "chunks":              [],
    "chunk_count":         0,
    "similar_problem":     None,
    "tool_trace":          [],
    "retrieval_latency_ms": 0,
}


class AgenticRetriever:
    """
    LLM-driven retrieval loop using OpenAI function calling.

    Injected dependencies mirror SocraticEngine:
        openai_client:   openai.AsyncOpenAI
        retriever:       app.services.rag.retriever.Retriever
        pool:            asyncpg.Pool
        embed_service:   EmbeddingService (same singleton used by Retriever)
    """

    def __init__(
        self,
        openai_client: openai.AsyncOpenAI,
        retriever: Retriever,
        pool: asyncpg.Pool,
        embed_service: EmbeddingService,
    ) -> None:
        self._client       = openai_client
        self._retriever    = retriever
        self._pool         = pool
        self._embed        = embed_service

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(
        self,
        question: str,
        subject: str = "Physics",
        topic: str = "",
        hint_level: int = 0,
        question_type: str = "conceptual",
    ) -> dict:
        """
        Run the agentic retrieval loop for one Socratic turn.

        Args:
            question:      The student's problem text
            subject:       Subject from classify_subject() or AskRequest
            topic:         Topic from problem analysis (used to seed first call)
            hint_level:    Current hint level — if == 3, returns empty immediately
            question_type: 'conceptual' | 'numerical' | 'derivation'

        Returns:
            {
              "context_text":    str,           # ready-to-inject text block
              "chunks":          list[dict],    # all retrieved chunks
              "chunk_count":     int,
              "similar_problem": dict | None,   # most similar JEE problem (if any)
              "tool_trace":      list[dict],    # log of tool calls made
            }
        """
        # Nuclear override: hint_level == 3 = zero teaching, no RAG at all
        if hint_level == 3:
            logger.debug("AgenticRetriever: hint_level=3 — returning empty context")
            return _EMPTY_CONTEXT.copy()

        t0 = time.monotonic()
        accumulated: List[dict] = []  # chunks collected across all tool calls
        tool_trace:  List[dict] = []  # audit log

        # ── Build initial messages ────────────────────────────────────────────
        system_prompt = _AGENT_SYSTEM_PROMPT.format(
            max_steps=MAX_STEPS,
            subject=subject,
            topic=topic or "unspecified",
            question_type=question_type,
        )
        messages: List[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Student question:\n{question}"},
        ]

        step = 0
        while step < MAX_STEPS:
            step += 1
            logger.debug("AgenticRetriever step %d/%d", step, MAX_STEPS)

            try:
                response = await asyncio.wait_for(
                    self._client.chat.completions.create(
                        model=AGENT_MODEL,
                        messages=messages,
                        tools=TOOL_SCHEMAS,
                        tool_choice="auto",
                        max_tokens=512,
                        temperature=0.0,   # deterministic retrieval decisions
                    ),
                    timeout=15.0,
                )
            except asyncio.TimeoutError:
                logger.warning("AgenticRetriever: LLM call timed out at step %d", step)
                break
            except Exception as exc:
                logger.warning("AgenticRetriever: LLM call failed at step %d: %s", step, exc)
                break

            msg = response.choices[0].message

            # ── No tool calls → agent signalled done ─────────────────────────
            if not msg.tool_calls:
                logger.debug(
                    "AgenticRetriever: no tool calls at step %d — retrieval complete", step
                )
                # Append assistant message so conversation is valid
                messages.append({"role": "assistant", "content": msg.content or ""})
                break

            # ── Execute each tool call ────────────────────────────────────────
            messages.append(msg)  # append assistant tool_calls message

            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(
                    "AgenticRetriever step=%d tool=%s args=%s",
                    step, tool_name, tool_args,
                )

                # ── Dispatch tool ─────────────────────────────────────────────
                tool_result_chunks: List[dict] = []
                error_msg: Optional[str] = None

                try:
                    if tool_name == "search_ncert":
                        tool_result_chunks = await search_ncert(
                            retriever=self._retriever,
                            query=tool_args.get("query", question),
                            subject=tool_args.get("subject", subject),
                            chapter=tool_args.get("chapter"),
                            top_k=int(tool_args.get("top_k", 3)),
                        )

                    elif tool_name == "search_jee_problems":
                        tool_result_chunks = await search_jee_problems(
                            pool=self._pool,
                            embed_service=self._embed,
                            query=tool_args.get("query", question),
                            subject=tool_args.get("subject", subject),
                            exam_type=tool_args.get("exam_type"),
                            difficulty_min=tool_args.get("difficulty_min"),
                            difficulty_max=tool_args.get("difficulty_max"),
                            year_min=tool_args.get("year_min"),
                            year_max=tool_args.get("year_max"),
                            top_k=int(tool_args.get("top_k", 3)),
                        )

                    elif tool_name == "search_concepts":
                        tool_result_chunks = await search_concepts(
                            pool=self._pool,
                            query=tool_args.get("query", question),
                            top_k=int(tool_args.get("top_k", 4)),
                        )

                    elif tool_name == "rerank_and_select":
                        # Run in executor — synchronous but fast
                        loop = asyncio.get_running_loop()
                        reranked = await loop.run_in_executor(
                            None,
                            rerank_and_select,
                            accumulated,
                            tool_args.get("query", question),
                            self._embed,
                            int(tool_args.get("max_chunks", 5)),
                        )
                        # Replace accumulated with reranked selection
                        accumulated = reranked
                        tool_result_chunks = reranked

                    else:
                        error_msg = f"Unknown tool: {tool_name}"
                        logger.warning("AgenticRetriever: %s", error_msg)

                except Exception as exc:
                    error_msg = f"Tool {tool_name} failed: {exc}"
                    logger.warning("AgenticRetriever: %s", error_msg)

                # Record trace
                tool_trace.append({
                    "step":         step,
                    "tool":         tool_name,
                    "args":         tool_args,
                    "result_count": len(tool_result_chunks),
                    "error":        error_msg,
                })

                # Accumulate chunks (except rerank_and_select which replaces)
                if tool_name != "rerank_and_select":
                    accumulated.extend(tool_result_chunks)

                # Build tool result message for LLM
                result_summary = self._summarize_tool_result(
                    tool_name, tool_result_chunks, error_msg
                )
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_call.id,
                    "content":      result_summary,
                })

        # ── Fallback: if no chunks accumulated, run basic NCERT search ────────
        if not accumulated:
            logger.warning(
                "AgenticRetriever: no chunks accumulated — falling back to basic NCERT search"
            )
            try:
                fallback = await search_ncert(
                    retriever=self._retriever,
                    query=question,
                    subject=subject,
                    top_k=3,
                )
                accumulated = fallback
                tool_trace.append({
                    "step": "fallback", "tool": "search_ncert",
                    "args": {"query": question, "subject": subject, "top_k": 3},
                    "result_count": len(fallback), "error": None,
                })
            except Exception as exc:
                logger.warning("AgenticRetriever fallback also failed: %s", exc)

        # ── Final rerank if > MAX_CHUNKS (don't call LLM again, just rerank) ──
        MAX_FINAL_CHUNKS = 5
        if len(accumulated) > MAX_FINAL_CHUNKS:
            loop = asyncio.get_running_loop()
            accumulated = await loop.run_in_executor(
                None,
                rerank_and_select,
                accumulated,
                question,
                self._embed,
                MAX_FINAL_CHUNKS,
            )

        # ── Assemble context text ─────────────────────────────────────────────
        context_text, similar_problem = self._assemble_context(accumulated)

        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "AgenticRetriever: %d chunks in %dms via %d tool calls (steps=%d)",
            len(accumulated), elapsed_ms, len(tool_trace), step,
        )

        return {
            "context_text":         context_text,
            "chunks":               accumulated,
            "chunk_count":          len(accumulated),
            "similar_problem":      similar_problem,
            "tool_trace":           tool_trace,
            "retrieval_latency_ms": elapsed_ms,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _summarize_tool_result(
        self,
        tool_name: str,
        chunks: List[dict],
        error: Optional[str],
    ) -> str:
        """Build a concise summary of a tool result to send back to the LLM."""
        if error:
            return f"Tool {tool_name} failed: {error}. No results."

        if not chunks:
            return f"Tool {tool_name}: no results found."

        parts = [f"Tool {tool_name}: {len(chunks)} result(s)."]
        for i, chunk in enumerate(chunks[:3]):  # show up to 3 previews
            content = chunk.get("content", "")
            preview = content[:150].replace("\n", " ").strip()
            src = chunk.get("source", "?")
            parts.append(f"  [{i+1}] ({src}) {preview}…")
        if len(chunks) > 3:
            parts.append(f"  … and {len(chunks) - 3} more.")

        return "\n".join(parts)

    def _assemble_context(
        self,
        chunks: List[dict],
    ) -> tuple[str, Optional[dict]]:
        """
        Build the final context_text string for injection into the LLM prompt.
        Returns (context_text, similar_problem_or_None).

        Format:
            ── NCERT / CONCEPT CONTEXT ──────────────────────────────────────
            [chunk content blocks separated by ---]

            ── SIMILAR JEE PROBLEM ──────────────────────────────────────────
            Q: …
            Verified answer: …
        """
        ncert_chunks    = [c for c in chunks if c.get("source") in ("ncert", "concept")]
        jee_chunks      = [c for c in chunks if c.get("source") == "jee_pyq"]

        similar_problem: Optional[dict] = jee_chunks[0] if jee_chunks else None

        # NCERT + concept blocks
        ncert_text = "\n\n---\n\n".join(c.get("content", "") for c in ncert_chunks)

        # JEE similar problem block
        jee_block = ""
        if similar_problem:
            jee_block = (
                "\n\n── SIMILAR JEE PROBLEM ─────────────────────────────────────\n"
                f"[{similar_problem.get('exam_type', 'JEE')} "
                f"{similar_problem.get('year', '')}] "
                f"Topic: {similar_problem.get('topic', '')}\n\n"
                f"Q: {similar_problem.get('problem_text', '')}"
            )
            if similar_problem.get("source_verified") and similar_problem.get("solution_text"):
                jee_block += f"\nVerified Answer: {similar_problem['solution_text'][:400]}"

        context_text = (ncert_text + jee_block).strip()

        return context_text, similar_problem
