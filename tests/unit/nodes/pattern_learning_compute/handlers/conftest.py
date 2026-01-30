# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for pattern learning compute handler tests."""

from __future__ import annotations

from omniintelligence.nodes.pattern_learning_compute.models import (
    TrainingDataItemDict,
)


def make_training_item(
    item_id: str,
    code_snippet: str,
    pattern_type: str = "compute",
    confidence: float = 0.9,
) -> TrainingDataItemDict:
    """Factory for minimal training items.

    Creates deterministic training items with consistent language and framework
    to ensure reproducible clustering behavior.

    Args:
        item_id: Unique identifier for the training item.
        code_snippet: The code snippet for this training item.
        pattern_type: The type of pattern (default: "compute").
        confidence: The confidence score (default: 0.9).

    Returns:
        A TrainingDataItemDict with all required fields populated.
    """
    return TrainingDataItemDict(
        item_id=item_id,
        source_file=f"{item_id}.py",
        language="python",
        code_snippet=code_snippet,
        pattern_type=pattern_type,
        pattern_name="test_pattern",
        labels=[pattern_type, "test"],
        confidence=confidence,
        context="test",
        framework="onex",
    )
