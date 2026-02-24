# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Trace data model for Execution Trace Parser Compute."""

from __future__ import annotations

from pydantic import BaseModel, Field

from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_trace_log import (
    ModelTraceLog,
)


class ModelTraceData(BaseModel):
    """Typed model for trace data.

    Provides strong typing for trace span data used in trace parsing.
    All common trace fields are explicitly typed for type safety.
    """

    span_id: str | None = Field(default=None, description="Unique span identifier")
    trace_id: str | None = Field(default=None, description="Trace identifier")
    parent_span_id: str | None = Field(
        default=None, description="Parent span identifier"
    )
    operation_name: str | None = Field(
        default=None, description="Name of the operation"
    )
    service_name: str | None = Field(default=None, description="Service name")
    start_time: str | None = Field(default=None, description="Span start timestamp")
    end_time: str | None = Field(default=None, description="Span end timestamp")
    duration_ms: float | None = Field(default=None, description="Duration in ms")
    status: str | None = Field(default=None, description="Span status")
    tags: dict[str, str] = Field(default_factory=dict, description="Span tags")
    logs: list[ModelTraceLog] = Field(
        default_factory=list, description="Log entries within the span"
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelTraceData"]
