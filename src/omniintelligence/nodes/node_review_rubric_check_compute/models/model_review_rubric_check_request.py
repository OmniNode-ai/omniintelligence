# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Input of the review rubric check node (OMN-21186)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelReviewRubricCheckRequest(BaseModel):
    """A rubric file's text, where it came from, and the token budget it must fit.

    The handler is pure: whoever builds the request reads the file. The source
    is used only in messages.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    rubric_yaml: str = Field(description="The rubric file, as text.")
    rubric_source: str = Field(min_length=1, description="Where it was read from.")
    token_budget: int = Field(gt=0, description="Most tokens the rubric may cost.")
    correlation_id: UUID | None = None


__all__ = ["ModelReviewRubricCheckRequest"]
