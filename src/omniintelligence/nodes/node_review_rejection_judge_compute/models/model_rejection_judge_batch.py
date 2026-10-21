# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The rejections of one pull request that await the review bot (OMN-17427)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_rejection_judge_compute.models.model_pending_rejection import (
    ModelPendingRejection,
)


class ModelRejectionJudgeBatch(BaseModel):
    """The ``--pending`` file of ``cli_review judge-rejections``."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo: str = Field(min_length=1)
    pr: int = Field(ge=1)
    head_sha: str = Field(min_length=7)
    items: tuple[ModelPendingRejection, ...] = ()


__all__ = ["ModelRejectionJudgeBatch"]
