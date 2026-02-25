# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Applicable pattern model for compliance evaluation.

Ticket: OMN-2256
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelApplicablePattern(BaseModel):
    """A single pattern to check compliance against.

    This model represents a pattern retrieved from the pattern store
    (OMN-2253) that is applicable to the code being evaluated.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the pattern",
    )
    pattern_signature: str = Field(
        ...,
        min_length=1,
        description="Pattern signature text describing what the pattern enforces",
    )
    domain_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Domain the pattern belongs to",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the pattern",
    )


__all__ = ["ModelApplicablePattern"]
