# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for Pattern Matching Compute."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_context import (
    ModelPatternContext,
)
from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_record import (
    ModelPatternRecord,
)

# Supported pattern matching operations
PatternMatchingOperation = Literal[
    "match",  # Find patterns matching the code snippet
    "similarity",  # Compute similarity scores against known patterns
    "classify",  # Classify code snippet into pattern categories
    "validate",  # Validate code against expected patterns
]


class ModelPatternMatchingInput(BaseModel):
    """Input model for pattern matching operations.

    This model represents the input for matching code patterns.
    All fields are fully typed with validation constraints.

    The patterns field contains the pattern library to match against.
    This follows the compute node purity principle - patterns are passed
    in rather than fetched via I/O.
    """

    code_snippet: str = Field(
        ...,
        min_length=1,
        description="Code snippet to match patterns against",
    )
    patterns: list[ModelPatternRecord] = Field(
        default_factory=list,
        description="Pattern library to match against (provided by orchestrator)",
    )
    operation: PatternMatchingOperation = Field(
        default="match",
        description="Type of pattern matching operation to perform",
    )
    project_name: str | None = Field(
        default=None,
        description="Name of the project for context",
    )
    context: ModelPatternContext = Field(
        default_factory=ModelPatternContext,
        description="Structured context for pattern matching",
    )
    match_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum match score threshold (0.0 to 1.0)",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelPatternContext",
    "ModelPatternMatchingInput",
    "ModelPatternRecord",
    "PatternMatchingOperation",
]
