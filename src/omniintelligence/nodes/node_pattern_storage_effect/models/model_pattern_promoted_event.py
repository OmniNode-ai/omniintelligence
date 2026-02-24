# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

# Copyright (c) 2025 OmniNode Team
"""ModelPatternPromotedEvent - event model for pattern-promoted.v1 events."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_metrics_snapshot import (
    ModelPatternMetricsSnapshot,
)
from omniintelligence.nodes.node_pattern_storage_effect.models.model_pattern_state import (
    EnumPatternState,
)


class ModelPatternPromotedEvent(BaseModel):
    """Event model for pattern-promoted.v1 events.

    Emitted when a pattern is promoted from one state to another
    (e.g., candidate -> provisional, provisional -> validated).
    Contains audit trail information for governance compliance.

    Attributes:
        pattern_id: Unique identifier of the promoted pattern.
        from_state: Previous state before promotion.
        to_state: New state after promotion.
        reason: Human-readable reason for the promotion.
        metrics_snapshot: Snapshot of metrics at promotion time.
        promoted_at: Timestamp when the promotion occurred.
        correlation_id: Correlation ID for distributed tracing.
        actor: Identifier of the entity that triggered the promotion.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    pattern_id: UUID = Field(
        ...,
        description="Unique identifier of the promoted pattern",
    )
    from_state: EnumPatternState = Field(
        ...,
        description="Previous state before promotion",
    )
    to_state: EnumPatternState = Field(
        ...,
        description="New state after promotion",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Human-readable reason for the promotion",
    )
    metrics_snapshot: ModelPatternMetricsSnapshot | None = Field(
        default=None,
        description="Snapshot of metrics at promotion time (None if not captured)",
    )
    promoted_at: datetime = Field(
        ...,
        description="Timestamp when the promotion occurred (UTC)",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing",
    )
    actor: str | None = Field(
        default=None,
        description="Identifier of the entity that triggered the promotion",
    )

    def is_valid_transition(self) -> bool:
        """Check if the state transition is valid.

        Delegates to the shared transition validation function in constants module.
        Valid transitions are:
        - CANDIDATE -> PROVISIONAL
        - PROVISIONAL -> VALIDATED

        Returns:
            True if the transition is valid, False otherwise.
        """
        from omniintelligence.nodes.node_pattern_storage_effect.constants import (
            is_valid_transition as _is_valid_transition,
        )

        return _is_valid_transition(self.from_state, self.to_state)
