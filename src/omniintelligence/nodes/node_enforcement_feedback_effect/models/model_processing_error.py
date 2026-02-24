# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Processing error record model for enforcement feedback."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelProcessingError(BaseModel):
    """Record of a failed confidence adjustment for a single pattern.

    Captured when ``_apply_confidence_adjustment`` raises an exception so
    that callers can see exactly which patterns failed and why.

    Attributes:
        pattern_id: The pattern whose adjustment failed.
        pattern_name: Human-readable name for diagnostics.
        error: Sanitized error message describing the failure.
        error_type: The exception class name (e.g., ``"ConnectionError"``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: UUID = Field(
        ...,
        description="The pattern whose adjustment failed",
    )
    pattern_name: str = Field(
        default="",
        description="Human-readable name of the pattern",
    )
    error: str = Field(
        ...,
        description="Sanitized error message describing the failure",
    )
    error_type: str = Field(
        ...,
        description="The exception class name (e.g., 'ConnectionError')",
    )


__all__ = ["ModelProcessingError"]
