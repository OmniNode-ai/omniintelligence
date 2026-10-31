# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Span, logs, and tracing context for error extraction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.protocols import (
    SpanNodeDict,
)


class ModelEventExtractionRequest(BaseModel):
    """Span, logs, and tracing context for error extraction."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    span: SpanNodeDict
    correlated_logs: list[dict[str, str | None]] = Field(default_factory=list)
    correlation_id: str | None = None


__all__ = ["ModelEventExtractionRequest"]
