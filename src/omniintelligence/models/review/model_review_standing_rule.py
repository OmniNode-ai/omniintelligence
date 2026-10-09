# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""One standing rule of a reviewed repository (OMN-20784)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

RULE_ID_PATTERN: str = r"^[a-z0-9][a-z0-9._-]{1,63}$"
"""Rule ids are lowercase, start alphanumeric, 2 to 64 characters."""


class ModelReviewStandingRule(BaseModel):
    """A rule the reviewer tests every change against.

    Attributes:
        id: Stable identifier a finding cites to bind itself to the rule.
        mandatory: True when a pull request may not remove, demote or reword
            the rule. A violated mandatory rule is a critical finding.
        text: The rule as the reviewer reads it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    id: str = Field(pattern=RULE_ID_PATTERN, description="Stable rule identifier.")
    mandatory: bool = Field(
        default=False,
        description="A pull request cannot remove or weaken a mandatory rule.",
    )
    text: str = Field(
        min_length=1,
        max_length=4000,
        description="The rule as the reviewer reads it.",
    )


__all__ = ["RULE_ID_PATTERN", "ModelReviewStandingRule"]
