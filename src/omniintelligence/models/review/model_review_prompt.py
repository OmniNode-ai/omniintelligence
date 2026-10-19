# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A selected reviewer prompt: version, system text and user templates (OMN-20910)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelReviewPrompt(BaseModel):
    """One reviewer prompt version.

    Attributes:
        version: Semantic version of the prompt.
        system_prompt: The system text, before the standing-rules section.
        user_template_plan: User template for a plan; has a ``{plan_content}`` slot.
        user_template_pr: User template for a PR diff; has a ``{plan_content}`` slot.
        compact_output: True when the reply is the v2 compact verdict, False for
            the v1 findings array.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1, description="Prompt version.")
    system_prompt: str = Field(min_length=1, description="System text.")
    user_template_plan: str = Field(min_length=1, description="Plan user template.")
    user_template_pr: str = Field(min_length=1, description="PR user template.")
    compact_output: bool = Field(
        description="True when the reply is a compact verdict."
    )


__all__ = ["ModelReviewPrompt"]
