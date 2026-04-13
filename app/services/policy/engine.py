"""
Policy Engine — selects pedagogy configuration for each tutoring interaction.

Entry point:
    select_pedagogy(persona_profile, topic, hint_level, subject) → PedagogyConfig
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PedagogyConfig:
    scaffolding_level: str    # HIGH / MEDIUM / LOW
    use_analogies: bool
    max_concepts: int         # max concepts per response
    information_density: str  # low / medium / high
    socratic_style: str       # conceptual / formula / application
    check_in_required: bool   # ask confirmation before moving on
    hint_tone: str            # encouraging / neutral / direct
    subject: str = "Physics"  # active subject for this interaction


# Base config table keyed by scaffolding level
_BASE_CONFIG: dict[str, dict] = {
    "HIGH": {
        "use_analogies": True,
        "max_concepts": 2,
        "information_density": "low",
        "socratic_style": "conceptual",
        "check_in_required": True,
        "hint_tone": "encouraging",
    },
    "MEDIUM": {
        "use_analogies": False,
        "max_concepts": 3,
        "information_density": "medium",
        "socratic_style": "formula",
        "check_in_required": False,
        "hint_tone": "neutral",
    },
    "LOW": {
        "use_analogies": False,
        "max_concepts": 5,
        "information_density": "high",
        "socratic_style": "application",
        "check_in_required": False,
        "hint_tone": "direct",
    },
}

# Subject-specific socratic style overrides at each scaffolding level.
# Chemistry: formula-heavy even at HIGH because stoichiometry benefits from writing equations early.
# Maths: application-skewed even at MEDIUM because procedural practice cements understanding.
_SUBJECT_STYLE_OVERRIDES: dict[str, dict[str, str]] = {
    "Chemistry": {
        "HIGH":   "conceptual",   # build reaction intuition first
        "MEDIUM": "formula",      # stoichiometry and balancing needs explicit equations
        "LOW":    "application",  # exam-level multi-step problems
    },
    "Maths": {
        "HIGH":   "conceptual",   # proof intuition before manipulation
        "MEDIUM": "application",  # worked examples drive understanding
        "LOW":    "application",  # complex derivations at speed
    },
    "Physics": {
        "HIGH":   "conceptual",
        "MEDIUM": "formula",
        "LOW":    "application",
    },
}


def select_pedagogy(
    persona_profile: dict,
    topic: str,
    hint_level: int,
    subject: str = "Physics",
) -> PedagogyConfig:
    """
    Select a PedagogyConfig based on the student's persona, subject, and current hint level.

    Override rules (applied after base config):
    - Subject-specific socratic_style from _SUBJECT_STYLE_OVERRIDES.
    - Chemistry HIGH: use_analogies=False — stoichiometry needs equations, not analogies first.
    - hint_level 0: always conceptual style regardless of scaffolding and subject.
    - hint_level >= 3: always check_in_required = False (forced attempt — no pacing).

    Args:
        persona_profile: Student persona dict with at minimum scaffolding_level key.
        topic: Current topic string (used for future topic-specific overrides).
        hint_level: Current hint depth (0–4+).
        subject: One of "Physics", "Chemistry", "Maths". Defaults to "Physics".
    """
    scaffolding = persona_profile.get("scaffolding_level", "HIGH")
    if scaffolding not in _BASE_CONFIG:
        scaffolding = "HIGH"

    base = dict(_BASE_CONFIG[scaffolding])

    # Subject-specific style override
    _valid_subjects = {"Physics", "Chemistry", "Maths"}
    _effective_subject = subject if subject in _valid_subjects else "Physics"

    subject_styles = _SUBJECT_STYLE_OVERRIDES.get(_effective_subject, _SUBJECT_STYLE_OVERRIDES["Physics"])
    base["socratic_style"] = subject_styles.get(scaffolding, base["socratic_style"])

    # Chemistry at HIGH scaffolding: formulas/equations are the intuition vehicle
    if _effective_subject == "Chemistry" and scaffolding == "HIGH":
        base["use_analogies"] = False

    # Maths at any level: fewer concepts per response — each step needs verification
    if _effective_subject == "Maths":
        base["max_concepts"] = max(1, base["max_concepts"] - 1)

    # hint_level overrides (apply after subject overrides)
    if hint_level == 0:
        base["socratic_style"] = "conceptual"
    if hint_level >= 3:
        base["check_in_required"] = False

    return PedagogyConfig(scaffolding_level=scaffolding, subject=_effective_subject, **base)
