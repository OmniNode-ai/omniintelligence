# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""One persona of a review voter, as review_voters_overlay.v2 declares it (OMN-20910)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PERSONA_ID_PATTERN = r"^[a-z][a-z0-9-]{0,62}$"
MAX_PERSONAS_PER_VOTER = 3


class ModelReviewPersona(BaseModel):
    """A persona: one more focused pass of the same model, never one more vote."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    persona_id: str = Field(
        pattern=PERSONA_ID_PATTERN,
        description="Names the persona in cost events and results; unique in the overlay.",
    )
    focus: str = Field(
        min_length=1,
        description="The persona's review emphasis; it adds scrutiny, never narrows the remit.",
    )
    tier: Literal["required", "budgeted"] = Field(
        description="required: always run. budgeted: run only while the roster "
        "budget admits it.",
    )
    mode: Literal["inline", "advisory"] = Field(
        description="inline: findings are unioned into the voter's result and "
        "the voter stays ONE reviewer identity. advisory: runs after the gate, "
        "never enters the quorum.",
    )


__all__ = ["MAX_PERSONAS_PER_VOTER", "PERSONA_ID_PATTERN", "ModelReviewPersona"]
