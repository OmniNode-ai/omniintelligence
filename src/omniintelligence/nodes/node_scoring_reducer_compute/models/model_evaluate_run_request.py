# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Evidence and objective specification for scoring a run."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_scoring_reducer_compute.models.model_evidence_bundle import (
    ModelEvidenceBundle,
)
from omniintelligence.nodes.node_scoring_reducer_compute.models.model_objective_spec import (
    ModelObjectiveSpec,
)


class ModelEvaluateRunRequest(BaseModel):
    """Evidence and objective specification for scoring a run."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    evidence: ModelEvidenceBundle
    spec: ModelObjectiveSpec


__all__ = ["ModelEvaluateRunRequest"]
