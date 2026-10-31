# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request to check statistical significance for a shadow variant."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_objective_variant import (
    ModelObjectiveVariantRegistry,
)


class ModelCheckUpgradeReadyRequest(BaseModel):
    """Request to check statistical significance for a shadow variant."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    shadow_variant_id: str = Field(
        description="Shadow variant ID being checked (reserved for future use)."
    )
    run_count: int = Field(description="Total runs evaluated for this variant.")
    shadow_wins: int = Field(description="Runs where shadow outperformed active.")
    registry: ModelObjectiveVariantRegistry = Field(
        description="Registry containing threshold configuration."
    )


__all__ = ["ModelCheckUpgradeReadyRequest"]
