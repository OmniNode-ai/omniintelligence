# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for AntiGamingGuardrailsCompute node (OMN-2563)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.model_guardrail_config import (
    ModelGuardrailConfig,
)


class ModelScoreVectorSnapshot(BaseModel):
    """Lightweight snapshot of a ScoreVector for comparison."""

    model_config = ConfigDict(frozen=True)

    correctness: float = Field(default=0.0, ge=0.0, le=1.0)
    safety: float = Field(default=0.0, ge=0.0, le=1.0)
    cost: float = Field(default=0.0, ge=0.0, le=1.0)
    latency: float = Field(default=0.0, ge=0.0, le=1.0)
    maintainability: float = Field(default=0.0, ge=0.0, le=1.0)
    human_time: float = Field(default=0.0, ge=0.0, le=1.0)

    def get_dimension(self, name: str) -> float:
        """Get a score dimension by name."""
        return float(getattr(self, name, 0.0))


class ModelGuardrailInput(BaseModel):
    """Input to the AntiGamingGuardrailsCompute node."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(description="The execution run being evaluated.")
    current_score: ModelScoreVectorSnapshot = Field(
        description="Score from the current run."
    )
    previous_score: ModelScoreVectorSnapshot | None = Field(
        default=None,
        description=(
            "Score from the previous run (for delta-based checks). "
            "None for first-time runs."
        ),
    )
    evidence_sources: tuple[str, ...] = Field(
        description="Set of distinct EvidenceItem source types in the current bundle."
    )
    human_acceptance_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Current human acceptance rate for this policy entity. "
            "None if not yet available."
        ),
    )
    previous_acceptance_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Previous human acceptance rate (for delta comparison).",
    )
    baseline_source_distribution: dict[str, float] | None = Field(
        default=None,
        description=(
            "Baseline evidence source value distribution {source: mean_value}. "
            "None if no baseline yet. Used for distributional shift detection."
        ),
    )
    current_source_distribution: dict[str, float] | None = Field(
        default=None,
        description="Current evidence source value distribution {source: value}.",
    )
    config: ModelGuardrailConfig = Field(
        description="Guardrail configuration loaded from ObjectiveSpec."
    )


__all__ = ["ModelGuardrailInput", "ModelScoreVectorSnapshot"]
