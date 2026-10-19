# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Result of loading a review rubric file (OMN-21186)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric import (
    ModelReviewRubric,
)
from omniintelligence.nodes.node_review_rubric_check_compute.models.model_review_rubric_refusal import (
    ModelReviewRubricRefusal,
)


class ModelReviewRubricLoad(BaseModel):
    """The rubric, or why not; ``token_count`` is set once the file parsed."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    rubric: ModelReviewRubric | None = None
    refusal: ModelReviewRubricRefusal | None = None
    token_count: int = Field(default=0, ge=0)


__all__ = ["ModelReviewRubricLoad"]
