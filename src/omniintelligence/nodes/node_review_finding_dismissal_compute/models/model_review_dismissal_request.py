# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Input of the review finding dismissal node (OMN-20910)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_dismissal_judgement import (
    ModelDismissalJudgement,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_dismissal_voter import (
    ModelDismissalVoter,
)
from omniintelligence.nodes.node_review_finding_dismissal_compute.models.model_finding_dismissal import (
    ModelFindingDismissal,
)
from omniintelligence.review_pairing.models_external_review import ModelQuorumFinding


class ModelReviewDismissalRequest(BaseModel):
    """The blocking findings of one head, the dismissals read, and any judgements made."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    head_sha: str = Field(min_length=7, description="The head the review ran on.")
    blocking_findings: tuple[ModelQuorumFinding, ...] = ()
    dismissals: tuple[ModelFindingDismissal, ...] = ()
    voters: tuple[ModelDismissalVoter, ...] = Field(
        default=(), description="Voters that succeeded in this review."
    )
    judgements: tuple[ModelDismissalJudgement, ...] = ()
    repo: str | None = None
    pr: int | None = None
    correlation_id: UUID | None = None


__all__ = ["ModelReviewDismissalRequest"]
