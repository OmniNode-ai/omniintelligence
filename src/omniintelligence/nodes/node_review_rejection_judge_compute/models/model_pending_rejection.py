# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""One rejected finding awaiting the review bot (OMN-17427)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPendingRejection(BaseModel):
    """What the judge reads: the finding, the cited code at the head, the rejection.

    Written by the thread gate of the reviewed repository, which reads the
    review threads and the pull request's git history; this node reads no
    GitHub and no git.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    key: str = Field(min_length=1, description="The rejection's comment id.")
    raised_by: str = Field(
        min_length=1, description="The voter id the finding's thread names."
    )
    finding: str = Field(min_length=1)
    lines_label: str = Field(description="Where the cited lines lie at the head.")
    excerpt: str = Field(description="The cited lines at the head, numbered.")
    rejection: str = Field(min_length=1, description="The rejection as written.")


__all__ = ["ModelPendingRejection"]
