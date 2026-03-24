# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Persona loader for review_pairing.cli_review.

Loads persona .md files from the personas/ subdirectory and builds
system prompts by prepending persona content to the base review prompt.

Ticket: OMN-6228
"""

from __future__ import annotations

from pathlib import Path

from omniintelligence.review_pairing.cli_review_models import ModelPersonaConfig

_PERSONAS_DIR = Path(__file__).parent / "personas"


def list_personas() -> list[str]:
    """Return names of available personas (filename stems, alphabetical).

    Returns:
        Sorted list of persona name strings (e.g., ["analytical-strict"]).
        Empty list if the personas directory does not exist.

    Example::

        available = list_personas()
        assert "analytical-strict" in available
    """
    if not _PERSONAS_DIR.exists():
        return []
    return sorted(p.stem for p in _PERSONAS_DIR.glob("*.md"))


def load_persona(name: str) -> ModelPersonaConfig:
    """Load a persona by name from review_pairing/personas/<name>.md.

    Args:
        name: Persona name (file stem, e.g., "analytical-strict").

    Returns:
        ``ModelPersonaConfig`` with name and full markdown content.

    Raises:
        ValueError: If the persona does not exist. Error message includes
            the available persona list so callers can show helpful output.

    Example::

        config = load_persona("analytical-strict")
        assert config.name == "analytical-strict"
        assert len(config.content) > 100
    """
    persona_path = _PERSONAS_DIR / f"{name}.md"
    if not persona_path.exists():
        available = list_personas()
        available_str = ", ".join(available) if available else "(none found)"
        raise ValueError(
            f"Persona '{name}' not found. "
            f"Available personas: {available_str}. "
            f"Personas directory: {_PERSONAS_DIR}"
        )
    content = persona_path.read_text(encoding="utf-8")
    return ModelPersonaConfig(name=name, content=content)


def build_system_prompt(
    *,
    persona: ModelPersonaConfig | None,
    base_prompt: str,
) -> str:
    """Build the final system prompt by prepending persona content.

    If persona is None, returns base_prompt unchanged.
    If persona is provided, prepends persona.content with a separator.

    Args:
        persona: Loaded persona config, or None for no persona injection.
        base_prompt: The base system prompt for the review task.

    Returns:
        Final system prompt string with persona prepended (if any).

    Example::

        persona = load_persona("analytical-strict")
        prompt = build_system_prompt(
            persona=persona,
            base_prompt="Review this plan."
        )
        assert prompt.startswith("# Persona: Analytical-Strict")
        assert "Review this plan." in prompt
    """
    if persona is None:
        return base_prompt
    return f"{persona.content}\n\n---\n\n{base_prompt}"


__all__ = ["list_personas", "load_persona", "build_system_prompt"]
