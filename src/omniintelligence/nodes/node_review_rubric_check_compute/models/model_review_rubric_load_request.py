# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Request for loading a review rubric under a token budget."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelReviewRubricLoadRequest(BaseModel):
    """The rubric text, its token budget, and its source for refusal messages."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    text: str
    token_budget: int
    source: str = "<rubric>"


__all__ = ["ModelReviewRubricLoadRequest"]
