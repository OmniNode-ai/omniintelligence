# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for persona_loader: list, load, build_system_prompt.

Ticket: OMN-6228
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_load_known_persona() -> None:
    """load_persona must return ModelPersonaConfig for analytical-strict."""
    from omniintelligence.review_pairing.cli_review_models import ModelPersonaConfig
    from omniintelligence.review_pairing.persona_loader import load_persona

    config = load_persona("analytical-strict")
    assert isinstance(config, ModelPersonaConfig)
    assert config.name == "analytical-strict"
    assert len(config.content) > 100


@pytest.mark.unit
def test_load_unknown_persona_raises() -> None:
    """load_persona must raise ValueError with list of available personas."""
    from omniintelligence.review_pairing.persona_loader import load_persona

    with pytest.raises(ValueError) as exc_info:
        load_persona("nonexistent-persona-xyz")

    error_msg = str(exc_info.value)
    assert "nonexistent-persona-xyz" in error_msg
    assert "analytical-strict" in error_msg


@pytest.mark.unit
def test_list_personas_returns_analytical_strict() -> None:
    """list_personas must include analytical-strict."""
    from omniintelligence.review_pairing.persona_loader import list_personas

    available = list_personas()
    assert "analytical-strict" in available


@pytest.mark.unit
def test_build_system_prompt_with_persona() -> None:
    """build_system_prompt must prepend persona content before base prompt."""
    from omniintelligence.review_pairing.cli_review_models import ModelPersonaConfig
    from omniintelligence.review_pairing.persona_loader import build_system_prompt

    persona = ModelPersonaConfig(name="test", content="# Test Persona\nBe strict.")
    result = build_system_prompt(persona=persona, base_prompt="Review this plan.")
    assert result.startswith("# Test Persona")
    assert "Review this plan." in result


@pytest.mark.unit
def test_build_system_prompt_without_persona() -> None:
    """build_system_prompt with no persona returns base prompt unchanged."""
    from omniintelligence.review_pairing.persona_loader import build_system_prompt

    result = build_system_prompt(persona=None, base_prompt="Review this plan.")
    assert result == "Review this plan."
