# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Output model for protocol handler effect node.

Represents the result of a protocol handler operation.

Reference:
    - OMN-373: Protocol handlers for declarative effect nodes
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_protocol_handler_effect.models.enum_handler_status import (
    EnumHandlerStatus,
)
from omniintelligence.nodes.node_protocol_handler_effect.models.enum_protocol_type import (
    EnumProtocolType,
)


class ModelProtocolHandlerOutput(BaseModel):
    """Output model for protocol handler operations.

    Contains the result of executing a protocol operation, including
    status, any returned data, and error information.

    Attributes:
        correlation_id: Correlation ID for tracing.
        protocol: The protocol type that handled the operation.
        operation: The operation that was executed.
        status: The status of the operation.
        result: The operation result data (protocol-specific).
        error_message: Error details if the operation failed.
        executed_at: Timestamp when the operation completed.
        duration_ms: Duration of the operation in milliseconds.
        retry_count: Number of attempts made.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for end-to-end tracing",
    )
    protocol: EnumProtocolType = Field(
        ...,
        description="The protocol type that handled the operation",
    )
    operation: str = Field(
        ...,
        description="The operation that was executed",
    )
    status: EnumHandlerStatus = Field(
        ...,
        description="The status of the operation",
    )
    result: dict[str, Any] | None = Field(
        default=None,
        description="The operation result data (protocol-specific)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if the operation failed",
    )
    executed_at: datetime = Field(
        ...,
        description="Timestamp when the operation completed (UTC)",
    )
    duration_ms: float = Field(
        ...,
        ge=0,
        description="Duration of the operation in milliseconds",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of attempts made",
    )


__all__ = [
    "ModelProtocolHandlerOutput",
]
