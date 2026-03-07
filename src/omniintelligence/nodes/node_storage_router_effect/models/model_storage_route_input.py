# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""Input model for storage router effect node.

Represents a completed compute event that needs to be routed
to the appropriate storage backend.

Reference:
    - OMN-371: Storage router effect node
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelStorageRouteInput(BaseModel):
    """Input model for storage routing operations.

    Represents a compute output event that must be routed to the
    appropriate storage backend based on its event_type.

    Routing Rules:
        - vectorization.completed -> Qdrant vector storage
        - entity.extraction-completed -> Memgraph graph storage
        - pattern.matched -> PostgreSQL pattern storage

    Attributes:
        event_id: Unique identifier for this event.
        event_type: The type of compute event (used for routing).
        correlation_id: Correlation ID for end-to-end tracing.
        payload: The event payload to be stored.
        source_node: The node that produced this event.
        produced_at: Timestamp when the event was produced.
        retry_count: Number of previous routing attempts.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    event_id: UUID = Field(
        ...,
        description="Unique identifier for this event",
    )
    event_type: str = Field(
        ...,
        min_length=1,
        description="The type of compute event (determines routing target)",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for end-to-end distributed tracing",
    )
    payload: dict[str, Any] = Field(
        ...,
        description="The event payload to be stored in the target backend",
    )
    source_node: str = Field(
        ...,
        min_length=1,
        description="Name of the node that produced this event",
    )
    produced_at: datetime = Field(
        ...,
        description="Timestamp when the compute event was produced (UTC)",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of previous routing attempts (0 for first attempt)",
    )


__all__ = [
    "ModelStorageRouteInput",
]
