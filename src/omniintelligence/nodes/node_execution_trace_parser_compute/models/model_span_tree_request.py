# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Trace data and correlation context for span tree construction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_trace_data import (
    ModelTraceData,
)


class ModelSpanTreeRequest(BaseModel):
    """Trace data and correlation context for span tree construction."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    trace_data: ModelTraceData
    correlation_id: str | None = None


__all__ = ["ModelSpanTreeRequest"]
