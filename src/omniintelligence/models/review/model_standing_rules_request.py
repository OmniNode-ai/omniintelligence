# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input of the standing-rules handler (OMN-20784)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelStandingRulesRequest(BaseModel):
    """Rules file text to validate, optionally compared with a pull request's copy.

    Attributes:
        rules_text: Text of the authoritative rules file (the protected base
            branch's). None means the file does not exist there.
        compare_candidate: True when ``candidate_text`` is to be checked
            against the authoritative rules.
        candidate_text: Text of the pull request's copy of the rules file.
            None means the pull request has no such file.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    rules_text: str | None = Field(description="Authoritative rules file text.")
    compare_candidate: bool = Field(
        default=False, description="Check candidate_text against rules_text."
    )
    candidate_text: str | None = Field(
        default=None, description="The pull request's copy of the rules file."
    )


__all__ = ["ModelStandingRulesRequest"]
