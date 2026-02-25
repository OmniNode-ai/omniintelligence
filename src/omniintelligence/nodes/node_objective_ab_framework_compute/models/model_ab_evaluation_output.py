# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output models for ObjectiveABFrameworkCompute node (OMN-2571)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_objective_ab_framework_compute.models.enum_variant_role import (
    EnumVariantRole,
)


class ModelVariantEvaluationResult(BaseModel):
    """Result of evaluating an EvidenceBundle against a single variant."""

    model_config = ConfigDict(frozen=True)

    variant_id: str = Field(description="The variant that produced this result.")
    objective_id: str = Field(description="Objective spec ID.")
    objective_version: str = Field(description="Objective spec version.")
    role: EnumVariantRole = Field(description="Whether this was the active or shadow variant.")
    passed: bool = Field(description="Whether the evaluation passed all hard gates.")
    score_correctness: float = Field(default=0.0, description="Correctness score component.")
    score_safety: float = Field(default=0.0, description="Safety score component.")
    score_cost: float = Field(default=0.0, description="Cost score component.")
    score_latency: float = Field(default=0.0, description="Latency score component.")
    score_maintainability: float = Field(default=0.0, description="Maintainability score component.")
    score_human_time: float = Field(default=0.0, description="Human time score component.")
    drives_policy_state: bool = Field(
        description="True only for ACTIVE variant — this result updates policy state."
    )


class ModelABEvaluationOutput(BaseModel):
    """Output from the ObjectiveABFrameworkCompute node."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(description="The run that was evaluated.")
    variant_results: tuple[ModelVariantEvaluationResult, ...] = Field(
        description="One result per registered variant."
    )
    divergence_detected: bool = Field(
        default=False,
        description="True if variants produced divergent outcomes (different passed or large delta).",
    )
    upgrade_ready: bool = Field(
        default=False,
        description="True if a shadow variant has reached statistical significance to be promoted.",
    )
    upgrade_ready_variant_id: str | None = Field(
        default=None,
        description="variant_id of the shadow variant ready for promotion.",
    )


__all__ = ["ModelABEvaluationOutput", "ModelVariantEvaluationResult"]
