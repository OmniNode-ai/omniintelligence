# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A pull request comment, as read for dismissals (OMN-20910)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelDismissalComment(BaseModel):
    """The fields of one issue comment the dismissal parser reads."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    comment_id: str = Field(description="The comment's id.")
    author: str = Field(description="The commenter's login.")
    author_association: str = Field(
        default="NONE", description="GitHub's author_association for the comment."
    )
    body: str = Field(default="", description="The comment body.")


__all__ = ["ModelDismissalComment"]
