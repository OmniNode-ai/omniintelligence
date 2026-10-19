# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A dismissal that is to be put to a named second voter (OMN-20910)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_finding_dismissal import (
    ModelFindingDismissal,
)
from omniintelligence.review_pairing.models_external_review import ModelQuorumFinding


class ModelDismissalAssignment(BaseModel):
    """The finding, the dismissal of it, and the voter that judges it."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    finding: ModelQuorumFinding
    dismissal: ModelFindingDismissal
    judge_voter: str = Field(min_length=1)
    judge_raised_finding: bool


__all__ = ["ModelDismissalAssignment"]
