# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ScoreVector model — six-dimensional scoring primitive (OMN-2537).

No scalar reward field is permitted anywhere. ScoreVector is the only
scoring primitive in the objective architecture.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelScoreVector(BaseModel):
    """Six-dimensional score vector (all values in [0.0, 1.0]).

    Dimensions correspond to the six reward target types defined in
    EnumRewardTargetType. Higher values are always better within a
    dimension before lexicographic reordering.

    This model is frozen — no mutation after construction.
    """

    model_config = ConfigDict(frozen=True)

    correctness: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Task correctness / accuracy score.",
    )
    safety: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Safety constraints and guardrails score.",
    )
    cost: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Compute / token cost efficiency score (1.0 = no cost).",
    )
    latency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="End-to-end execution latency score (1.0 = instant).",
    )
    maintainability: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Code quality and long-term maintainability score.",
    )
    human_time: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Human operator time saved score.",
    )

    @classmethod
    def zero(cls) -> "ModelScoreVector":
        """Return an all-zero ScoreVector (the additive identity)."""
        return cls(
            correctness=0.0,
            safety=0.0,
            cost=0.0,
            latency=0.0,
            maintainability=0.0,
            human_time=0.0,
        )


__all__ = ["ModelScoreVector"]
