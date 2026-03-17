"""
Two-layer answer verification pipeline.

Layer 1 — SymPy  (fast, deterministic, algebraic)
  Runs when the problem is detectable as:
    • Function composition  (keywords: "f(g(", "g(f(")
    • Function inverse      (keywords: "inverse", "f^{-1}")
    • Expression equality   (keywords: "simplify", "evaluate", "compute")
  Skipped silently on any parse / detection failure.

Layer 2 — LLM adversarial examiner  (always runs)
  Catches logical / proof errors that SymPy cannot see.

Combination logic:
  • Both layers agree    → method="hybrid", boosted confidence
  • Layers disagree      → method="hybrid", flagged_for_review=True
  • SymPy not applicable → method="llm", confidence capped at 0.85
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.services.verify.llm_verify import LLMVerifier
from app.services.verify.math_verify import SymPyChecker

logger = logging.getLogger(__name__)


class VerificationPipeline:
    def __init__(
        self,
        sympy_checker: SymPyChecker,
        llm_verifier: LLMVerifier,
    ) -> None:
        self._checker = sympy_checker
        self._verifier = llm_verifier

    # ── public API ────────────────────────────────────────────────────────────

    async def verify(
        self,
        question: str,
        solution: str,
        context: str = "",
        problem_type: Optional[str] = None,
    ) -> dict:
        """
        Run the two-layer verification pipeline.

        Returns:
            {
                verified:          bool,
                confidence:        float,
                method:            "sympy" | "llm" | "hybrid",
                errors:            list[str],
                severity:          str,
                flagged_for_review: bool,
                details: {
                    sympy_result:  dict | None,
                    llm_result:    dict,
                }
            }
        """
        # ── Layer 1: SymPy ────────────────────────────────────────────────────
        sympy_result: Optional[dict] = None
        try:
            sympy_result = self._try_sympy(question, solution)
            if sympy_result:
                logger.info(
                    "SymPy verification: correct=%s type=%s confidence=%.2f",
                    sympy_result.get("is_correct"),
                    sympy_result.get("type"),
                    sympy_result.get("confidence", 0),
                )
        except Exception as exc:
            logger.warning("SymPy layer raised unexpectedly (non-fatal): %s", exc)

        # ── Layer 2: LLM (always) ─────────────────────────────────────────────
        llm_result = await self._verifier.verify_solution(
            question=question,
            solution=solution,
            subject_context=context,
        )
        logger.info(
            "LLM verification: correct=%s confidence=%.2f severity=%s",
            llm_result.get("is_correct"),
            llm_result.get("confidence", 0),
            llm_result.get("severity"),
        )

        # ── Combine ───────────────────────────────────────────────────────────
        return self._combine(sympy_result, llm_result)

    # ── SymPy detection & dispatch ────────────────────────────────────────────

    def _try_sympy(self, question: str, solution: str) -> Optional[dict]:
        """
        Detect problem type and run the appropriate SymPy check.
        Returns None if the problem is not amenable to SymPy verification.
        """
        # ── Composition: f(g(x)) or g(f(x)) ──────────────────────────────────
        is_fog = bool(re.search(r"f\s*\(\s*g\s*\(", question, re.IGNORECASE))
        is_gof = bool(re.search(r"g\s*\(\s*f\s*\(", question, re.IGNORECASE))

        if is_fog or is_gof:
            funcs = self._extract_functions(question)
            if "f" in funcs and "g" in funcs:
                claimed = self._extract_final_expression(solution)
                if claimed:
                    raw = (
                        self._checker.check_function_composition(
                            funcs["f"], funcs["g"], claimed
                        )
                        if is_fog
                        else self._checker.check_function_composition(
                            funcs["g"], funcs["f"], claimed
                        )
                    )
                    if raw.get("confidence", 0) > 0:
                        return {
                            "is_correct": raw.get("correct", False),
                            "confidence": raw["confidence"],
                            "computed": raw.get("computed"),
                            "type": "composition",
                        }

        # ── Inverse: f⁻¹ ──────────────────────────────────────────────────────
        q_lower = question.lower()
        if (
            "inverse" in q_lower
            or "f^{-1}" in question
            or "f⁻¹" in question
            or "f^(-1)" in question
        ):
            funcs = self._extract_functions(question)
            if "f" in funcs:
                claimed = self._extract_final_expression(solution)
                if claimed:
                    raw = self._checker.check_inverse(funcs["f"], claimed)
                    if raw.get("confidence", 0) > 0:
                        return {
                            "is_correct": raw.get("correct", False),
                            "confidence": raw["confidence"],
                            "type": "inverse",
                        }

        # ── Expression equality: simplify / evaluate / compute ────────────────
        simplify_kws = ("simplify", "evaluate", "compute")
        if any(k in q_lower for k in simplify_kws):
            claimed = self._extract_final_expression(solution)
            lhs = self._extract_lhs_from_question(question)
            if claimed and lhs:
                raw = self._checker.check_expression_equality(lhs, claimed)
                if raw.get("confidence", 0) > 0:
                    return {
                        "is_correct": raw.get("equal", False),
                        "confidence": raw["confidence"],
                        "type": "expression",
                    }

        return None  # SymPy not applicable

    # ── Expression / function extraction helpers ──────────────────────────────

    @staticmethod
    def _extract_functions(question: str) -> dict:
        """
        Extract f(x)=<expr> and g(x)=<expr> definitions from the question text.

        Matches patterns like:
          f(x) = 2x+1      f(x)=x^2       g(x) = x^2 - 3
        """
        result: dict[str, str] = {}
        for name in ("f", "g", "h"):
            # Stop at comma, period, newline, or "and"
            pattern = rf"{name}\s*\(\s*x\s*\)\s*=\s*([^,\.\n]+)"
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                result[name] = match.group(1).strip().rstrip(")")
        return result

    @staticmethod
    def _extract_final_expression(text: str) -> Optional[str]:
        """
        Extract the last concrete mathematical expression from a solution string.

        Works on chains like:
          "f(g(x)) = 2(x^2)+1 = 2x^2+1"   → "2x^2+1"
          "fog = (2x+1)^2 = 4x^2+4x+1"     → "4x^2+4x+1"
        """
        # Try splitting on " = " with spaces first (avoids breaking f(x)=...)
        for sep in (" = ", "="):
            parts = [p.strip().rstrip(".") for p in text.split(sep)]
            for part in reversed(parts):
                # Skip function-call looking parts like f(g(x))
                if re.match(r"^[a-zA-Z]\s*\([a-zA-Z]", part):
                    continue
                # Strip LaTeX noise
                clean = re.sub(r"[\\{}\[\]]", "", part)
                # Must have at least one digit or arithmetic operator
                if re.search(r"[\d+\-*/^]", clean) and len(clean.strip()) >= 2:
                    return clean.strip()
        return None

    @staticmethod
    def _extract_lhs_from_question(question: str) -> Optional[str]:
        """Try to pull the expression being simplified/evaluated from the question."""
        match = re.search(
            r"(?:simplify|evaluate|compute)\s+([^,\.\n?]+)",
            question,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
        return None

    # ── Result combiner ───────────────────────────────────────────────────────

    @staticmethod
    def _combine(sympy_result: Optional[dict], llm_result: dict) -> dict:
        """Merge SymPy and LLM verdicts into a single verification report."""
        errors: list = list(llm_result.get("errors_found") or [])
        severity: str = llm_result.get("severity", "none") or "none"
        llm_correct: bool = bool(llm_result.get("is_correct", False))
        llm_conf: float = float(llm_result.get("confidence", 0.5))

        # ── Both layers available ─────────────────────────────────────────────
        if sympy_result and sympy_result.get("confidence", 0) > 0.9:
            sympy_correct: bool = bool(sympy_result.get("is_correct", False))
            sympy_conf: float = float(sympy_result.get("confidence", 0.95))

            if sympy_correct == llm_correct:
                # Agreement — boost confidence slightly
                verified = sympy_correct
                confidence = min(1.0, (sympy_conf + llm_conf) / 2 + 0.05)
                method = "hybrid"
                flagged = False
            else:
                # Disagreement — flag for human review, trust SymPy for algebra
                verified = sympy_correct
                confidence = 0.60   # express uncertainty
                method = "hybrid"
                flagged = True
                errors.append(
                    f"SymPy says {'CORRECT' if sympy_correct else 'INCORRECT'} "
                    f"but LLM says {'CORRECT' if llm_correct else 'INCORRECT'}. "
                    "Manual review recommended."
                )
                severity = severity if severity != "none" else "minor"

            # Enrich errors with SymPy computed value if available
            if not sympy_correct and sympy_result.get("computed"):
                errors.insert(
                    0,
                    f"SymPy computed the correct answer as: {sympy_result['computed']}",
                )

        # ── Only LLM ran ──────────────────────────────────────────────────────
        else:
            verified = llm_correct
            confidence = min(llm_conf, 0.85)   # cap — LLM-only is less certain
            method = "llm"
            flagged = False

        return {
            "verified": verified,
            "confidence": round(confidence, 3),
            "method": method,
            "errors": errors,
            "severity": severity,
            "flagged_for_review": flagged,
            "details": {
                "sympy_result": sympy_result,
                "llm_result": llm_result,
            },
        }
