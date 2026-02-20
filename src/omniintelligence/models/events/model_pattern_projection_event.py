# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""Pattern projection snapshot event model.

Ticket: OMN-2424
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from omniintelligence.models.repository.model_pattern_summary import ModelPatternSummary


class ModelPatternProjectionEvent(BaseModel):
    """Materialized snapshot of all validated patterns.

    Published to topic: onex.evt.omniintelligence.pattern-projection.v1

    NodePatternProjectionEffect publishes this event whenever a pattern
    lifecycle change occurs (promoted, deprecated, or lifecycle-transitioned).
    Consumers use the snapshot to refresh their in-memory pattern cache
    without needing direct database access.

    Design notes:
        - ``snapshot_at`` must be explicitly injected by the caller.
          No ``datetime.now()`` default to preserve testability and
          determinism.
        - ``frozen=True`` — events are immutable after emission.
        - ``extra="ignore"`` — tolerates additional fields added by future
          envelope layers (e.g., event bus metadata).
        - ``from_attributes=True`` — required for pytest-xdist compatibility
          on frozen models.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        from_attributes=True,
    )

    event_type: Literal["PatternProjection"] = "PatternProjection"

    snapshot_id: UUID = Field(
        ...,
        description="Unique ID for this snapshot emission (UUID4, caller-generated)",
    )
    snapshot_at: AwareDatetime = Field(
        ...,
        description=(
            "UTC timestamp when the snapshot was taken. "
            "Must be explicitly injected by the caller — no datetime.now() default."
        ),
    )
    patterns: list[ModelPatternSummary] = Field(
        default_factory=list,
        description="Full list of validated (and provisional) patterns at snapshot time",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of patterns in the snapshot (matches len(patterns))",
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Snapshot schema version (monotonic integer, increments on schema changes)",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID from the triggering lifecycle event for distributed tracing",
    )


__all__ = ["ModelPatternProjectionEvent"]
