# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the rejection judge node (OMN-17427)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_rejection_judge_compute.models.model_pending_rejection import (
    ModelPendingRejection,
)


class ModelRejectionJudgeRequest(BaseModel):
    """One rejection, the configured judges and the review roster they must differ from.

    Identities are the quorum's distinct-reviewer identities
    (``ModelReviewVoterRoster.identities``): endpoint plus model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str = Field(min_length=1)
    pr: int = Field(ge=1)
    head_sha: str = Field(min_length=7)
    rejection: ModelPendingRejection
    judge_ids: tuple[str, ...] = Field(
        description="The judges the CI overlay declares, in preference order."
    )
    judge_identities: dict[str, str]
    voter_ids: tuple[str, ...] = Field(
        description="Every voter of the review roster; each counts as a raiser."
    )
    voter_identities: tuple[str, ...]
    nonce: str = Field(
        min_length=8,
        description="Fences the pull request's text in the prompt, so it cannot close a fence.",
    )


__all__ = ["ModelRejectionJudgeRequest"]
