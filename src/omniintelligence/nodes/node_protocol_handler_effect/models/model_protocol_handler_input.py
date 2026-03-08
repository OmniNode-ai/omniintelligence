# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Input model for protocol handler effect node.

Represents a protocol operation request to be executed by the
appropriate protocol handler.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_protocol_handler_effect.models.enum_protocol_type import (
    EnumProtocolType,
)


class ModelProtocolHandlerInput(BaseModel):
    """Input model for protocol handler operations.

    Specifies which protocol handler to use, what operation to perform,
    and the parameters for that operation.

    Attributes:
        correlation_id: Correlation ID for end-to-end tracing.
        protocol: The protocol type determining which handler to use.
        operation: The operation to execute (e.g., GET, query, produce).
        config: Protocol-specific connection configuration.
        params: Operation-specific parameters.
        retry_count: Number of previous attempts.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for end-to-end distributed tracing",
    )
    protocol: EnumProtocolType = Field(
        ...,
        description="The protocol type determining which handler to use",
    )
    operation: str = Field(
        ...,
        min_length=1,
        description="The operation to execute (protocol-specific)",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Protocol-specific connection configuration",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific parameters",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of previous attempts (0 for first attempt)",
    )


__all__ = [
    "ModelProtocolHandlerInput",
]
