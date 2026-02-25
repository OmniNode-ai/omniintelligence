# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for ObjectiveABFrameworkCompute node (OMN-2571)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_objective_ab_framework_compute.models.model_objective_variant import (
    ModelObjectiveVariantRegistry,
)


class ModelABEvaluationInput(BaseModel):
    """Input to the ObjectiveABFrameworkCompute node."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(description="Execution run identifier.")
    evidence_bundle: dict[str, Any] = Field(
        description=(
            "Serialized EvidenceBundle (as dict) to evaluate against all variants. "
            "Each variant's ScoringReducer receives the same bundle."
        )
    )
    registry: ModelObjectiveVariantRegistry = Field(
        description="Registry of variants to evaluate against."
    )
    run_count_by_variant: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Current run count per variant_id. Used for statistical significance tracking. "
            "Key: variant_id, Value: total runs evaluated so far."
        ),
    )
    shadow_win_count_by_variant: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Current shadow win count per variant_id. "
            "Used for upgrade-ready significance tracking."
        ),
    )


__all__ = ["ModelABEvaluationInput"]
