# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ObjectiveSpec, GateSpec, ShapedTermSpec, and ModelScoreRange models (OMN-2537).

An ObjectiveSpec is a frozen, versioned declaration of what a "good run" looks
like. It consists of:
  1. Hard gates (GateSpec) — must ALL pass, or the run fails regardless of reward.
  2. Shaped terms (ShapedTermSpec) — weighted scoring components that contribute
     to the ScoreVector when all gates pass.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omniintelligence.nodes.node_scoring_reducer_compute.models.enum_gate_type import (
    EnumGateType,
)


class ModelScoreRange(BaseModel):
    """Defines the valid score range for an objective."""

    model_config = ConfigDict(frozen=True)

    minimum: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum acceptable score."
    )
    maximum: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Maximum achievable score."
    )

    @model_validator(mode="after")
    def validate_range(self) -> "ModelScoreRange":
        if self.minimum > self.maximum:
            raise ValueError(
                f"minimum ({self.minimum}) must be <= maximum ({self.maximum})"
            )
        return self


class ModelGateSpec(BaseModel):
    """A hard gate that must pass for the run to be considered valid.

    Gates are evaluated before shaped reward. A single failing gate
    produces a failed EvaluationResult regardless of shaped term values.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Unique gate identifier within the objective spec.")
    gate_type: EnumGateType = Field(description="Type of gate evaluation.")
    threshold: float = Field(
        description=(
            "Threshold value. For THRESHOLD gates: evidence.value >= threshold. "
            "For BOOLEAN gates: evidence.value > 0 is truthy. "
            "For RANGE gates: used as lower bound (upper bound in range_max). "
            "For REGEX gates: not applicable (threshold=0.0 by convention)."
        )
    )
    weight: float = Field(
        default=1.0,
        gt=0.0,
        description="Relative importance of this gate (informational, not used in pass/fail).",
    )
    evidence_source: str = Field(
        description="The evidence source key to evaluate (must match an EvidenceItem.source)."
    )
    range_max: float | None = Field(
        default=None,
        description="Upper bound for RANGE gate type. Ignored for other gate types.",
    )
    regex_pattern: str | None = Field(
        default=None,
        description="Regex pattern for REGEX gate type. Ignored for other gate types.",
    )

    def passes(self, evidence_value: float) -> bool:
        """Evaluate whether the given evidence value passes this gate.

        Args:
            evidence_value: The normalized evidence value in [0.0, 1.0].
                            For THRESHOLD gates: evidence_value >= threshold.
                            For BOOLEAN gates: evidence_value > 0.
                            For RANGE gates: threshold <= evidence_value <= range_max.
                            For REGEX gates: not applicable (always passes on numeric input).

        Returns:
            True if the gate passes, False otherwise.
        """
        if self.gate_type == EnumGateType.THRESHOLD:
            return evidence_value >= self.threshold
        if self.gate_type == EnumGateType.BOOLEAN:
            return evidence_value > 0.0
        if self.gate_type == EnumGateType.RANGE:
            upper = self.range_max if self.range_max is not None else 1.0
            return self.threshold <= evidence_value <= upper
        # REGEX gate type is not applicable for numeric evidence values
        return evidence_value >= self.threshold


class ModelShapedTermSpec(BaseModel):
    """A weighted shaped reward term contributing to the ScoreVector.

    Shaped terms are only evaluated when all hard gates pass.

    For ``direction="minimize"`` terms, the evidence value is inverted
    (1.0 - value) before contributing to the weighted sum, so that lower
    evidence values yield higher scores.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Unique term identifier within the objective spec.")
    weight: float = Field(
        gt=0.0,
        le=1.0,
        description=(
            "Weight of this term. All weights for a given ScoreVector dimension "
            "must sum to 1.0."
        ),
    )
    direction: Literal["maximize", "minimize"] = Field(
        description=(
            "'maximize': higher evidence value → higher score. "
            "'minimize': lower evidence value → higher score (value is inverted)."
        )
    )
    evidence_source: str = Field(
        description="The evidence source key to use for this term."
    )
    score_dimension: str = Field(
        description=(
            "The ScoreVector dimension this term contributes to. "
            "Must be one of: correctness, safety, cost, latency, maintainability, human_time."
        )
    )

    @field_validator("score_dimension")
    @classmethod
    def validate_score_dimension(cls, v: str) -> str:
        valid = {"correctness", "safety", "cost", "latency", "maintainability", "human_time"}
        if v not in valid:
            raise ValueError(f"score_dimension '{v}' must be one of {sorted(valid)}")
        return v


class ModelObjectiveSpec(BaseModel):
    """Frozen, versioned specification of an objective function.

    An ObjectiveSpec defines:
    - Hard gates that all must pass (fail fast if any gate fails).
    - Shaped terms that contribute weighted scores to the ScoreVector.
    - Score range and lexicographic priority for dimension comparison.

    This model is frozen — no mutation after construction.
    """

    model_config = ConfigDict(frozen=True)

    objective_id: str = Field(description="Unique objective identifier.")
    version: str = Field(
        description="Semantic version string (e.g., '1.0.0')."
    )
    gates: tuple[ModelGateSpec, ...] = Field(
        default=(),
        description="Hard gates that must ALL pass before shaped reward is evaluated.",
    )
    shaped_terms: tuple[ModelShapedTermSpec, ...] = Field(
        default=(),
        description="Weighted shaped reward terms contributing to the ScoreVector.",
    )
    score_range: ModelScoreRange = Field(
        default_factory=ModelScoreRange,
        description="Valid score range for this objective.",
    )
    lexicographic_priority: tuple[str, ...] = Field(
        default=("correctness", "safety", "cost", "latency", "maintainability", "human_time"),
        description=(
            "Ordered list of ScoreVector dimension names for lexicographic comparison. "
            "Earlier dimensions are compared first."
        ),
    )

    @model_validator(mode="after")
    def validate_shaped_term_weights(self) -> "ModelObjectiveSpec":
        """Validate that shaped term weights sum to 1.0 per ScoreVector dimension."""
        from collections import defaultdict

        dimension_weights: dict[str, float] = defaultdict(float)
        for term in self.shaped_terms:
            dimension_weights[term.score_dimension] += term.weight

        for dim, total in dimension_weights.items():
            if abs(total - 1.0) > 1e-6:
                raise ValueError(
                    f"Shaped term weights for dimension '{dim}' sum to {total:.6f}, "
                    f"must sum to 1.0."
                )
        return self


__all__ = [
    "ModelGateSpec",
    "ModelObjectiveSpec",
    "ModelScoreRange",
    "ModelShapedTermSpec",
]
