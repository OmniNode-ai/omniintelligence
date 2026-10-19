# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Actionability support counts of one rubric rule (OMN-21186)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelReviewActionabilityCounts(BaseModel):
    """Findings behind a rule, by current disposition (plan section 3.4).

    Actionability is never truth; it is kept apart from the truth counts.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    acted_on: int = Field(ge=0)
    not_acted_on: int = Field(ge=0)
    unknown: int = Field(ge=0)


__all__ = ["ModelReviewActionabilityCounts"]
