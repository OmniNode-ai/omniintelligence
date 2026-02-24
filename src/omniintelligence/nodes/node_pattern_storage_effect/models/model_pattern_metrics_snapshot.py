# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ModelPatternMetricsSnapshot - snapshot of pattern metrics at promotion time."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternMetricsSnapshot(BaseModel):
    """Snapshot of pattern metrics at promotion time.

    Captures the metrics used to justify a pattern state promotion,
    providing auditability for governance decisions.

    Attributes:
        confidence: Current confidence score at promotion time.
        match_count: Number of times the pattern was matched.
        success_rate: Success rate of pattern applications.
        last_matched_at: Timestamp of last pattern match.
        validation_count: Number of validation passes.
        additional_metrics: Extra metrics as key-value pairs.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Current confidence score at promotion time",
    )
    match_count: int = Field(
        default=0,
        ge=0,
        description="Number of times the pattern was matched",
    )
    success_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Success rate of pattern applications (0.0-1.0)",
    )
    last_matched_at: datetime | None = Field(
        default=None,
        description="Timestamp of last pattern match (UTC)",
    )
    validation_count: int = Field(
        default=0,
        ge=0,
        description="Number of validation passes",
    )
    additional_metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Extra metrics as key-value pairs (numeric values only)",
    )
