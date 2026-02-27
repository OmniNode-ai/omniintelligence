# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for ScoringReducerCompute node (OMN-2545)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evaluation_result import (
    ModelEvaluationResult,
)


class ModelScoringOutput(BaseModel):
    """Output from the ScoringReducerCompute node.

    Wraps the EvaluationResult with node-level metadata for traceability.

    This model is frozen — no mutation after construction.
    """

    model_config = ConfigDict(frozen=True)

    result: ModelEvaluationResult = Field(
        description="The evaluation result from scoring the evidence bundle."
    )
    objective_id: str = Field(
        description="Objective ID from the spec used in this evaluation."
    )
    objective_version: str = Field(
        description="Objective version from the spec used in this evaluation."
    )
    run_id: str = Field(
        description="Run ID from the evidence bundle that was evaluated."
    )


__all__ = ["ModelScoringOutput"]
