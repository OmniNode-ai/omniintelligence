# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Error events detected in the requested span and logs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_execution_trace_parser_compute.handlers.protocols import (
    ErrorEventDict,
)


class ModelEventExtractionResponse(BaseModel):
    """Error events detected in the requested span and logs."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", from_attributes=True, arbitrary_types_allowed=True
    )

    error_events: list[ErrorEventDict] = Field(default_factory=list)


__all__ = ["ModelEventExtractionResponse"]
