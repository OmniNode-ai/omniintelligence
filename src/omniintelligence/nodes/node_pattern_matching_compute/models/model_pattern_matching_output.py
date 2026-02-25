# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for Pattern Matching Compute."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_match import (
    MatchAlgorithm,
    ModelPatternMatch,
)
from omniintelligence.nodes.node_pattern_matching_compute.models.model_pattern_matching_metadata import (
    ModelPatternMatchingMetadata,
    OutputMatchingAlgorithm,
)


class ModelPatternMatchingOutput(BaseModel):
    """Output model for pattern matching operations.

    This model represents the result of matching code patterns.
    Includes both simple (patterns_matched, pattern_scores) and
    rich (matches) representations for flexibility.
    """

    success: bool = Field(
        ...,
        description="Whether pattern matching succeeded",
    )
    patterns_matched: list[str] = Field(
        default_factory=list,
        description="List of matched pattern names (simple representation)",
    )
    pattern_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each matched pattern (0.0 to 1.0)",
    )
    matches: list[ModelPatternMatch] = Field(
        default_factory=list,
        description="Rich match details including reasons and algorithms",
    )
    metadata: ModelPatternMatchingMetadata | None = Field(
        default=None,
        description="Typed metadata about the matching operation",
    )

    @field_validator("pattern_scores")
    @classmethod
    def validate_pattern_scores(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate that all pattern scores are within 0.0 to 1.0 range."""
        for pattern_name, score in v.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"Pattern score for '{pattern_name}' must be between 0.0 and 1.0, "
                    f"got {score}"
                )
        return v

    @model_validator(mode="after")
    def validate_pattern_scores_match_patterns(self) -> Self:
        """Validate that pattern_scores keys match patterns_matched list."""
        patterns_set = set(self.patterns_matched)
        scores_keys = set(self.pattern_scores.keys())
        extra_scores = scores_keys - patterns_set
        if extra_scores:
            raise ValueError(
                f"pattern_scores contains patterns not in patterns_matched: "
                f"{sorted(extra_scores)}"
            )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "MatchAlgorithm",
    "ModelPatternMatch",
    "ModelPatternMatchingMetadata",
    "ModelPatternMatchingOutput",
    "OutputMatchingAlgorithm",
]
