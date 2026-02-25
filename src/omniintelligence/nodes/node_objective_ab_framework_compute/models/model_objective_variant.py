# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ObjectiveVariant and ObjectiveVariantRegistry models (OMN-2571)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from omniintelligence.nodes.node_objective_ab_framework_compute.models.enum_variant_role import (
    EnumVariantRole,
)


class ModelObjectiveVariant(BaseModel):
    """A single objective variant registered for A/B testing.

    Each variant has a traffic weight. The active variant drives policy state.
    Shadow variants are evaluated in read-only mode.
    """

    model_config = ConfigDict(frozen=True)

    variant_id: str = Field(description="Unique variant identifier.")
    objective_id: str = Field(description="ObjectiveSpec ID.")
    objective_version: str = Field(description="ObjectiveSpec version string.")
    role: EnumVariantRole = Field(description="Whether this is active or shadow.")
    traffic_weight: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Traffic weight [0.0, 1.0] for deterministic routing. "
            "All weights in a registry should sum to 1.0."
        ),
    )
    is_active: bool = Field(
        default=True,
        description="Whether this variant is currently accepting traffic.",
    )


class ModelObjectiveVariantRegistry(BaseModel):
    """Registry of objective variants for A/B testing.

    Backed by PostgreSQL (versioned rows). Contains exactly one ACTIVE
    variant and zero or more SHADOW variants.
    """

    model_config = ConfigDict(frozen=True)

    registry_id: str = Field(description="Unique registry identifier.")
    variants: tuple[ModelObjectiveVariant, ...] = Field(
        description="Registered variants in evaluation order."
    )
    significance_threshold: float = Field(
        default=0.05,
        gt=0.0,
        le=1.0,
        description=(
            "Statistical significance threshold (p-value) for upgrade-ready event. "
            "Emit ObjectiveUpgradeReady when shadow outperforms at this significance."
        ),
    )
    min_runs_for_significance: int = Field(
        default=100,
        gt=0,
        description="Minimum runs before statistical significance can be asserted.",
    )
    divergence_threshold: float = Field(
        default=0.1,
        gt=0.0,
        le=1.0,
        description="ScoreVector L2 distance threshold for divergence event emission.",
    )

    @model_validator(mode="after")
    def validate_exactly_one_active(self) -> ModelObjectiveVariantRegistry:
        active_count = sum(1 for v in self.variants if v.role == EnumVariantRole.ACTIVE)
        if active_count != 1:
            raise ValueError(
                f"Registry must have exactly 1 ACTIVE variant, found {active_count}."
            )
        return self


__all__ = ["ModelObjectiveVariant", "ModelObjectiveVariantRegistry"]
