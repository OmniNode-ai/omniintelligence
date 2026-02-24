# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for Execution Trace Parser Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_trace_data import (
    ModelTraceData,
)


class ModelTraceParsingInput(BaseModel):
    """Input model for trace parsing operations.

    This model represents the input for parsing execution traces.
    """

    trace_data: ModelTraceData = Field(
        ...,
        description="Raw trace data to parse (typed for common trace fields)",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    trace_format: str = Field(
        default="json",
        description="Format of the trace data (json, protobuf, etc.)",
    )
    extract_errors: bool = Field(
        default=True,
        description="Whether to extract error events",
    )
    extract_timing: bool = Field(
        default=True,
        description="Whether to extract timing data",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelTraceParsingInput"]
