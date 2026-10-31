# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Span tree construction result, including structured build errors."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.protocols import (
    BuildSpanResult,
)


class ModelSpanTreeResponse(BaseModel):
    """Span tree construction result, including structured build errors."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    result: BuildSpanResult


__all__ = ["ModelSpanTreeResponse"]
