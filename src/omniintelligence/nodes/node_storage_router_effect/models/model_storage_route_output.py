# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Output model for storage router effect node.

Represents the result of a storage routing operation.

Reference:
    - OMN-371: Storage router effect node
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_storage_router_effect.models.enum_storage_backend import (
    EnumStorageBackend,
)
from omniintelligence.nodes.node_storage_router_effect.models.enum_storage_route_status import (
    EnumStorageRouteStatus,
)


class ModelStorageRouteOutput(BaseModel):
    """Output model for storage routing operations.

    Represents the result of routing a compute event to a storage backend.

    Attributes:
        event_id: The original event ID that was routed.
        correlation_id: Correlation ID for tracing.
        target_backend: The storage backend the event was routed to.
        status: The status of the routing operation.
        routed_at: Timestamp when the routing completed.
        error_message: Error details if the routing failed.
        retry_count: Number of attempts made.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    event_id: UUID = Field(
        ...,
        description="The original event ID that was routed",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for end-to-end tracing",
    )
    target_backend: EnumStorageBackend | None = Field(
        default=None,
        description="The storage backend the event was routed to (None if unroutable)",
    )
    status: EnumStorageRouteStatus = Field(
        ...,
        description="The status of the routing operation",
    )
    routed_at: datetime = Field(
        ...,
        description="Timestamp when the routing completed (UTC)",
    )
    error_message: str | None = Field(
        default=None,
        description="Error details if the routing failed",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of attempts made",
    )


__all__ = [
    "ModelStorageRouteOutput",
]
