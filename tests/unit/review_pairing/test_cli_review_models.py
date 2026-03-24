# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for ModelCliReviewArgs and ModelPersonaConfig.

Ticket: OMN-6228
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_model_cli_review_args_import() -> None:
    """ModelCliReviewArgs must be importable from cli_review_models."""
    from omniintelligence.review_pairing.cli_review_models import ModelCliReviewArgs

    assert ModelCliReviewArgs is not None


@pytest.mark.unit
def test_model_persona_config_import() -> None:
    """ModelPersonaConfig must be importable from cli_review_models."""
    from omniintelligence.review_pairing.cli_review_models import ModelPersonaConfig

    assert ModelPersonaConfig is not None


@pytest.mark.unit
def test_model_cli_review_args_fields() -> None:
    """ModelCliReviewArgs must have file, persona, system_prompt_file fields."""
    from omniintelligence.review_pairing.cli_review_models import ModelCliReviewArgs

    fields = set(ModelCliReviewArgs.model_fields.keys())
    assert "file" in fields
    assert "persona" in fields
    assert "system_prompt_file" in fields


@pytest.mark.unit
def test_model_persona_config_fields() -> None:
    """ModelPersonaConfig must have name and content fields."""
    from omniintelligence.review_pairing.cli_review_models import ModelPersonaConfig

    fields = set(ModelPersonaConfig.model_fields.keys())
    assert "name" in fields
    assert "content" in fields
