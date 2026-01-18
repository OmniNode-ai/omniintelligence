"""Output model for Pattern Matching Compute."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class ModelPatternMatchingOutput(BaseModel):
    """Output model for pattern matching operations.

    This model represents the result of matching code patterns.
    """

    success: bool = Field(
        ...,
        description="Whether pattern matching succeeded",
    )
    patterns_matched: list[str] = Field(
        default_factory=list,
        description="List of matched pattern names",
    )
    pattern_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Confidence scores for each matched pattern (0.0 to 1.0)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the matching",
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
        """Validate that pattern_scores keys match patterns_matched list.

        Ensures consistency between the list of matched patterns and the
        dictionary containing their confidence scores. Every scored pattern
        must be in the matched patterns list.

        Note: Not all matched patterns require scores (scores are optional),
        but all scored patterns must be in the matched list.

        Returns:
            Self with validated pattern/score consistency.

        Raises:
            ValueError: If pattern_scores contains patterns not in patterns_matched.
        """
        patterns_set = set(self.patterns_matched)
        scores_keys = set(self.pattern_scores.keys())

        # Scores are optional, so we only check that scored patterns exist in matched
        extra_scores = scores_keys - patterns_set
        if extra_scores:
            raise ValueError(
                f"pattern_scores contains patterns not in patterns_matched: "
                f"{sorted(extra_scores)}"
            )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternMatchingOutput"]
