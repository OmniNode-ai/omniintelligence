# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A named refusal of a review rubric file (OMN-21186)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_review_rubric_check_compute.models.enum_review_rubric_refusal import (
    EnumReviewRubricRefusal,
)


class ModelReviewRubricRefusal(BaseModel):
    """The code that names the refusal, the field it concerns, and a message."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    code: EnumReviewRubricRefusal
    field: str = Field(default="", description="Dotted path of the offending field.")
    message: str


__all__ = ["ModelReviewRubricRefusal"]
