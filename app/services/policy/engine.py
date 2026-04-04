"""
Policy Engine — selects pedagogy configuration for each tutoring interaction.

Entry point:
    select_pedagogy(persona_profile, topic, hint_level) → PedagogyConfig
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


def select_pedagogy(
    persona_profile: dict,
    topic: str,
    hint_level: int,
) -> PedagogyConfig:
    """
    Select a PedagogyConfig based on the student's persona and current hint level.

    Override rules (applied after base config):
    - hint_level 0: always conceptual style regardless of scaffolding
    - hint_level >= 3: always check_in_required = False (forced attempt — no pacing)
    """
    scaffolding = persona_profile.get("scaffolding_level", "HIGH")
    if scaffolding not in _BASE_CONFIG:
        scaffolding = "HIGH"

    base = dict(_BASE_CONFIG[scaffolding])

    # hint_level overrides
    if hint_level == 0:
        base["socratic_style"] = "conceptual"
    if hint_level >= 3:
        base["check_in_required"] = False

    return PedagogyConfig(scaffolding_level=scaffolding, **base)
