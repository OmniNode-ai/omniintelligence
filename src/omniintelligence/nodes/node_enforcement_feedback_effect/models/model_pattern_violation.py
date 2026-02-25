# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Pattern violation model for enforcement events.

Reference: OMN-2270
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternViolation(BaseModel):
    """A single pattern violation detected during enforcement.

    Represents one pattern that was checked and found violated during
    a PostToolUse enforcement check in omniclaude.

    Attributes:
        pattern_id: The pattern that was violated.
        pattern_name: Human-readable name for logging and audit.
        was_advised: Whether the agent was advised about this violation.
        was_corrected: Whether the agent subsequently corrected the violation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: UUID = Field(
        ...,
        description="The ID of the pattern that was violated",
    )
    pattern_name: str = Field(
        default="",
        description="Human-readable name of the violated pattern",
    )
    was_advised: bool = Field(
        default=False,
        description="Whether the agent was advised about this violation",
    )
    was_corrected: bool = Field(
        default=False,
        description="Whether the agent subsequently corrected the violation",
    )


__all__ = ["ModelPatternViolation"]
