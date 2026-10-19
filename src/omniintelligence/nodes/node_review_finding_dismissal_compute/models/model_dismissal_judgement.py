# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""A second voter's judgement of one dismissal (OMN-20910)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelDismissalJudgement(BaseModel):
    """What the judge answered; ``confirmed`` is False on any failure."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    finding_key: str = Field(min_length=1)
    judge_voter: str = Field(min_length=1)
    confirmed: bool
    reason: str = Field(default="")


__all__ = ["ModelDismissalJudgement"]
