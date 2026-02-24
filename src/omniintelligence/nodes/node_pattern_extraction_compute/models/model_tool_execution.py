# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tool execution model for Pattern Extraction Compute Node."""

from __future__ import annotations

from datetime import datetime

from omnibase_core.types import JsonType
from pydantic import BaseModel, Field


# TEMP_BOOTSTRAP: Should move to core intelligence input models
# Follow-up ticket: OMN-1608
class ModelToolExecution(BaseModel):
    """Single tool execution record for pattern analysis."""

    tool_name: str = Field(..., description="Tool name (Read, Write, Edit, Bash, etc.)")
    success: bool = Field(..., description="Whether the tool execution succeeded")
    error_message: str | None = Field(
        default=None, description="Error message if failed"
    )
    error_type: str | None = Field(default=None, description="Exception type if failed")
    duration_ms: int | None = Field(
        default=None, ge=0, description="Execution duration"
    )
    # IMPORTANT: Use JsonType | None, NOT dict[str, Any]
    tool_parameters: JsonType | None = Field(
        default=None, description="Tool input parameters (opaque JSON)"
    )
    timestamp: datetime = Field(..., description="When the tool was executed")

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelToolExecution"]
