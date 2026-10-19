# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Truth-label support counts of one rubric rule (OMN-21186)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelReviewTruthCounts(BaseModel):
    """Labelled findings behind a rule, by truth label (plan section 3.4).

    The FALSE label is ``false_finding``: an unquoted ``false:`` key in yaml
    loads as the boolean, not the string.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    real: int = Field(ge=0)
    false_finding: int = Field(ge=0)
    contested: int = Field(ge=0)
    unlabelable: int = Field(ge=0)


__all__ = ["ModelReviewTruthCounts"]
