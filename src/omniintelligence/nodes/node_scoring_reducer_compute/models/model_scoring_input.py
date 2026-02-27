# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for ScoringReducerCompute node (OMN-2545)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evidence_bundle import (
    ModelEvidenceBundle,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_objective_spec import (
    ModelObjectiveSpec,
)


class ModelScoringInput(BaseModel):
    """Input to the ScoringReducerCompute node.

    Carries the evidence bundle and the objective specification needed
    to evaluate whether a run passes its gates and compute its reward.

    This model is frozen — no mutation after construction.
    """

    model_config = ConfigDict(frozen=True)

    evidence: ModelEvidenceBundle = Field(
        description="Evidence bundle from the agent execution run to evaluate."
    )
    spec: ModelObjectiveSpec = Field(
        description="Objective specification defining gates and shaped reward terms."
    )


__all__ = ["ModelScoringInput"]
