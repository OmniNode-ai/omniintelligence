# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for personas directory and analytical-strict persona file.

Ticket: OMN-6228
"""

from __future__ import annotations

from pathlib import Path

import pytest

PERSONAS_DIR = Path("src/omniintelligence/review_pairing/personas")


@pytest.mark.unit
def test_analytical_strict_persona_exists() -> None:
    """analytical-strict.md must exist in personas directory."""
    persona_path = PERSONAS_DIR / "analytical-strict.md"
    assert persona_path.exists(), f"Missing persona: {persona_path}"


@pytest.mark.unit
def test_analytical_strict_persona_has_required_sections() -> None:
    """analytical-strict persona must have Mandate, Format Rules, and Focus sections."""
    content = (PERSONAS_DIR / "analytical-strict.md").read_text()
    assert "Review Mandate" in content
    assert "Format Rules" in content
    assert "Contract Semantics" in content
    assert "CRITICAL" in content
    assert "MAJOR" in content
