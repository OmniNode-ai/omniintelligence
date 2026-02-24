# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Error event model for Execution Trace Parser Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelErrorEvent(BaseModel):
    """Typed model for error events extracted from traces.

    Provides strong typing for error information found during trace parsing.
    """

    error_id: str | None = Field(default=None, description="Unique error identifier")
    error_type: str | None = Field(default=None, description="Type of error")
    error_message: str | None = Field(default=None, description="Error message")
    timestamp: str | None = Field(default=None, description="Error timestamp")
    span_id: str | None = Field(default=None, description="Associated span ID")
    stack_trace: str | None = Field(
        default=None, description="Stack trace if available"
    )
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Error attributes"
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelErrorEvent"]
