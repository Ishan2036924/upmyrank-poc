"""
LLM-based adversarial solution verifier.

Uses a second GPT-4o-mini call with a strict "examiner" persona to
find logical, mathematical, and proof errors that SymPy cannot catch.
"""
import json
import logging
import re

import openai

logger = logging.getLogger(__name__)

# ── Adversarial examiner prompt ────────────────────────────────────────────────

_VERIFY_PROMPT = """\
You are a strict IIT JEE Physics examiner reviewing a student's solution.
Your job is to find errors. Be skeptical and thorough.

CRITICAL FORMATTING RULE: For ALL math/physics notation, you MUST use LaTeX \
with dollar sign delimiters. Use $...$ for inline math and $$...$$ \
for display/block math. NEVER use parentheses ( ) or brackets [ ] \
around LaTeX commands. NEVER use bare backslash commands without dollar signs.
Correct: $F = ma$, $E = mc^2$, $\\vec{{v}} = u + at$, $\\frac{{1}}{{2}}mv^2$
Correct display: $$v^2 = u^2 + 2as$$
WRONG: ( F=ma ), [ E=mc^2 ], ( \\sin(\\theta) )

Question: {question}

Proposed Solution: {solution}

Reference material: {subject_context}

Review this solution carefully. Respond with ONLY a JSON object — no markdown, \
no backticks, no extra text. Replace EVERY value below with your actual assessment \
of the solution above:
{{
  "is_correct": <true|false>,
  "confidence": <float 0.0–1.0 reflecting how certain you are of your verdict>,
  "errors_found": ["<specific error 1>", "<specific error 2>"],
  "severity": "<none|minor|major|critical>",
  "corrected_steps": "<brief correction note, or null if correct>",
  "reasoning": "<1-2 sentence summary of your assessment>"
}}

Field definitions (DO NOT copy these into the output — replace with real values):
- "is_correct":       true if the solution is fully correct, false otherwise
- "confidence":       a float from 0.0 (completely uncertain) to 1.0 (absolutely certain);
                      a well-reasoned assessment of a clear solution should be 0.85–0.95
- "errors_found":     list of specific errors as plain strings; empty list [] if none found
- "severity":         "none" if correct, "minor" for small slips, "major" / "critical" for
                      wrong physics or catastrophic errors
- "corrected_steps":  concise correction note if errors exist; null if fully correct
- "reasoning":        1-2 sentence summary of your overall verdict

Be especially careful about:
- Dimensional analysis — every equation must be dimensionally consistent
- Sign conventions — especially for displacement, force, work, and potential
- Newton's laws application — free body diagrams, action-reaction pairs
- Conservation laws — verify energy/momentum is actually conserved, not just assumed
- Kinematics — direction of vectors, correct SUVAT equation selection
- Significant figures and unit conversions
- Unjustified assumptions (e.g. ignoring air resistance without stating it)
- Edge cases, counterexamples, and circular reasoning
"""


class LLMVerifier:
    """Adversarial LLM verifier — uses GPT-4o-mini as a strict JEE examiner."""

    def __init__(
        self,
        openai_client: openai.AsyncOpenAI,
        model: str = "gpt-4o-mini",
    ) -> None:
        self._client = openai_client
        self._model = model

    # ── public API ────────────────────────────────────────────────────────────

    async def verify_solution(
        self,
        question: str,
        solution: str,
        subject_context: str = "",
    ) -> dict:
        """
        Verify a proposed solution by calling the LLM adversarially.

        Returns a dict with:
            is_correct, confidence, errors_found, severity,
            corrected_steps, reasoning
        """
        prompt = _VERIFY_PROMPT.format(
            question=question,
            solution=solution,
            subject_context=subject_context or "(no additional context)",
        )

        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=512,
            temperature=0.1,         # deterministic — we want consistent verdicts
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.choices[0].message.content
        logger.info("LLM verifier raw response: %s", raw[:300])
        result = self._parse_response(raw)
        # confidence == 0.0 usually means the model echoed the placeholder value
        # rather than filling it in. Default to a conservative but non-zero value.
        if result.get("confidence", 0) == 0.0:
            logger.warning(
                "Verifier returned confidence=0.0 — model may have echoed the "
                "JSON template placeholder; defaulting confidence to 0.72"
            )
            result["confidence"] = 0.72
        return result

    # ── parsing ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """Robustly parse JSON from the LLM response."""
        text = raw.strip()

        # Strip optional markdown code fences
        if text.startswith("```"):
            lines = text.splitlines()
            inner = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
            text = "\n".join(inner).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Fallback: pull the first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("LLM verifier: could not parse JSON; returning error fallback")
        return {
            "is_correct": False,
            "confidence": 0.0,
            "errors_found": ["Verifier response could not be parsed."],
            "severity": "minor",
            "corrected_steps": None,
            "reasoning": "Verification failed — could not parse LLM response.",
        }
