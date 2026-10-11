# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The fields of a GitHub pull request review the gate reads (OMN-20947)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPullRequestReviewView(BaseModel):
    """One pull request review: who posted it, on which commit, and its text."""

    model_config = ConfigDict(frozen=True, extra="ignore", from_attributes=True)

    author_login: str = Field(description="The account that posted the review.")
    commit_id: str = Field(description="The commit GitHub records the review on.")
    state: str = Field(description="COMMENTED, APPROVED, DISMISSED, ...")
    body: str = Field(description="The review body, which may carry receipts.")


__all__ = ["ModelPullRequestReviewView"]
