# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Confidence adjustment record model."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelConfidenceAdjustment(BaseModel):
    """Record of a single confidence adjustment applied to a pattern.

    Attributes:
        pattern_id: The pattern whose confidence was adjusted.
        adjustment: The amount subtracted from quality_score (negative value).
        reason: Human-readable reason for the adjustment.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: UUID = Field(
        ...,
        description="The pattern whose confidence was adjusted",
    )
    adjustment: float = Field(
        ...,
        description="The adjustment applied to quality_score (negative for violations)",
    )
    reason: str = Field(
        ...,
        description="Human-readable reason for the adjustment",
    )


__all__ = ["ModelConfidenceAdjustment"]
