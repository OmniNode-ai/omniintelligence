# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A dismissal a pull request author recorded for one finding on one head (OMN-20910)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelFindingDismissal(BaseModel):
    """One parsed dismissal, before it is judged."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    finding_key: str = Field(min_length=1, description="The finding key it dismisses.")
    head_sha: str = Field(description="The head it was recorded for.")
    evidence: str = Field(description="The author's evidence; may be empty.")
    author: str = Field(description="Who recorded it.")
    source: str = Field(description="A comment id or a file path.")
    authorized: bool = Field(
        description="True when the author is the PR author or a repository writer."
    )


__all__ = ["ModelFindingDismissal"]
