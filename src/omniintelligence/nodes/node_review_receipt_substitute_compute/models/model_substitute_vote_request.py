# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the review receipt substitute node (OMN-20947)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_receipt_substitute_compute.models.model_pull_request_review_view import (
    ModelPullRequestReviewView,
)
from omniintelligence.nodes.node_review_voters_overlay_compute.models.model_substitute_vote_policy import (
    ModelSubstituteVotePolicy,
)
from omniintelligence.review_pairing.models_external_review import (
    ModelMultiReviewResult,
)


class ModelSubstituteVoteRequest(BaseModel):
    """Everything the decision reads. The handler does no I/O and reads no clock."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    result: ModelMultiReviewResult = Field(description="The voters' own results.")
    policy: ModelSubstituteVotePolicy | None = Field(
        description="The overlay's substitute_votes policy; None accepts nothing."
    )
    reviews: tuple[ModelPullRequestReviewView, ...] = Field(default=())
    repo: str = Field(description="owner/name of the pull request.")
    pr: int = Field(gt=0)
    head_sha: str = Field(description="The head commit the gate run reviews.")
    key: bytes | None = Field(
        default=None, description="The receipt signing key; None accepts nothing."
    )
    now: datetime = Field(description="The gate run's clock, timezone-aware.")


__all__ = ["ModelSubstituteVoteRequest"]
