# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Request for deterministic objective variant routing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_objective_variant import (
    ModelObjectiveVariantRegistry,
)


class ModelRouteToVariantRequest(BaseModel):
    """Request for deterministic objective variant routing."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    run_id: str = Field(description="Execution run identifier.")
    registry: ModelObjectiveVariantRegistry = Field(
        description="Registry of variants with traffic weights."
    )


__all__ = ["ModelRouteToVariantRequest"]
