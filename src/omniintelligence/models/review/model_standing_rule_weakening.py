# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A mandatory base rule that a pull request removes, demotes or rewords (OMN-20784)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelStandingRuleWeakening(BaseModel):
    """One mandatory rule the pull request's rules file does not keep intact."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    rule_id: str = Field(description="Id of the mandatory base rule.")
    reason: Literal["removed", "demoted", "reworded"] = Field(
        description="removed: absent; demoted: no longer mandatory; reworded: text differs."
    )


__all__ = ["ModelStandingRuleWeakening"]
