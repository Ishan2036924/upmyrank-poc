"""
SymPy-based mathematical expression verifier.

Used for fast, deterministic algebraic checks on:
  • Expression equality   (simplify / evaluate problems)
  • Function composition  (f∘g problems)
  • Function inverses     (f⁻¹ problems)

Falls back gracefully — any parse error returns confidence=0.0 so the
pipeline knows to rely on the LLM layer instead.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _parse_expr(expr_str: str):
    """
    Parse a math expression string into a SymPy expression.

    Handles:
      - Implicit multiplication  (2x → 2*x, 2(x+1) → 2*(x+1))
      - Caret exponentiation     (x^2 → x**2)
      - LaTeX-style artifacts    (strips { } \\ )
    """
    from sympy import symbols
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    transformations = standard_transformations + (
        convert_xor,
        implicit_multiplication_application,
    )

    # Strip common LaTeX artifacts that bleed through
    clean = (
        expr_str.strip()
        .replace("\\", "")
        .replace("{", "")
        .replace("}", "")
        .replace("\\cdot", "*")
        .replace("\\times", "*")
    )

    x = symbols("x")
    return parse_expr(clean, local_dict={"x": x}, transformations=transformations)


class SymPyChecker:
    """Fast algebraic verification using SymPy symbolic computation."""

    # ── public API ────────────────────────────────────────────────────────────

    def check_expression_equality(self, expr1: str, expr2: str) -> dict:
        """
        Check if two expressions are algebraically equivalent.

        Returns:
            {equal: bool, confidence: float (0.95 on success, 0 on parse fail),
             error: str | None}
        """
        try:
            from sympy import simplify

            e1 = _parse_expr(expr1)
            e2 = _parse_expr(expr2)
            equal = simplify(e1 - e2) == 0
            return {"equal": equal, "confidence": 0.95, "error": None}
        except Exception as exc:
            logger.debug("SymPy check_expression_equality failed: %s", exc)
            return {"equal": False, "confidence": 0.0, "error": str(exc)}

    def check_function_composition(
        self,
        f: str,
        g: str,
        claimed: str,
        var: str = "x",
    ) -> dict:
        """
        Verify that f(g(x)) == claimed.

        Substitutes g(x) into f's expression and checks algebraic equality
        against the claimed result.

        Returns:
            {correct: bool, computed: str, confidence: float}
        """
        try:
            from sympy import simplify, symbols

            x = symbols(var)
            f_expr = _parse_expr(f)
            g_expr = _parse_expr(g)
            claimed_expr = _parse_expr(claimed)

            # Compute f(g(x)) by substituting g_expr in place of x in f
            fog = f_expr.subs(x, g_expr)
            fog_simplified = simplify(fog)
            claimed_simplified = simplify(claimed_expr)

            correct = simplify(fog_simplified - claimed_simplified) == 0
            return {
                "correct": correct,
                "computed": str(fog_simplified),
                "confidence": 0.95,
            }
        except Exception as exc:
            logger.debug("SymPy check_function_composition failed: %s", exc)
            return {
                "correct": False,
                "computed": None,
                "confidence": 0.0,
                "error": str(exc),
            }

    def check_inverse(
        self,
        f: str,
        claimed_inv: str,
        var: str = "x",
    ) -> dict:
        """
        Verify that claimed_inv is the inverse of f.

        Checks f(claimed_inv(x)) simplifies to x.

        Returns:
            {correct: bool, confidence: float}
        """
        try:
            from sympy import simplify, symbols

            x = symbols(var)
            f_expr = _parse_expr(f)
            f_inv_expr = _parse_expr(claimed_inv)

            composed = f_expr.subs(x, f_inv_expr)
            correct = simplify(composed - x) == 0
            return {"correct": correct, "confidence": 0.95}
        except Exception as exc:
            logger.debug("SymPy check_inverse failed: %s", exc)
            return {"correct": False, "confidence": 0.0, "error": str(exc)}
