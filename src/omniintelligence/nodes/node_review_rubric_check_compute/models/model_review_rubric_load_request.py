# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Request to read rubric text as a ``review_rubric.v1`` file (OMN-21186)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelReviewRubricLoadRequest(BaseModel):
    """Rubric text to load and the token budget it must fit."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    text: str = Field(description="Rubric file text.")
    token_budget: int = Field(description="Most tokens the rubric prompt may carry.")
    source: str = Field(default="<rubric>", description="Where the text came from.")


__all__ = ["ModelReviewRubricLoadRequest"]
