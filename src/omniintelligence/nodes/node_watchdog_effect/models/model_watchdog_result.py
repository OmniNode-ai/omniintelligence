# SPDX-License-Identifier: MIT
# Copyright (c) 2025 OmniNode Team
"""ModelWatchdogResult — structured result from WatchdogEffect handler operations.

Reference: OMN-2386
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_watchdog_effect.models.enum_watchdog_observer_type import (
    EnumWatchdogObserverType,
)
from omniintelligence.nodes.node_watchdog_effect.models.enum_watchdog_status import (
    EnumWatchdogStatus,
)


class ModelWatchdogResult(BaseModel):
    """Result of a WatchdogEffect handler operation.

    Frozen because results are immutable once returned from the handler.

    Attributes:
        status: Operation outcome.
        observer_type: Observer backend that was used or attempted.
        watched_paths: Paths being monitored (populated on STARTED).
        correlation_id: Correlation ID for distributed tracing.
        processed_at: UTC timestamp of when the result was produced.
        error_message: Human-readable error description (set on ERROR only).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    status: EnumWatchdogStatus = Field(
        ...,
        description="Outcome of the watchdog operation.",
    )

    observer_type: EnumWatchdogObserverType | None = Field(
        default=None,
        description="Observer backend used or attempted.",
    )

    watched_paths: tuple[str, ...] = Field(
        default=(),
        description="Paths being monitored.  Populated when status=STARTED.",
    )

    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for distributed tracing.",
    )

    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the result was produced.",
    )

    error_message: str | None = Field(
        default=None,
        description="Human-readable error description.  Set when status=ERROR.",
    )


__all__ = ["ModelWatchdogResult"]
