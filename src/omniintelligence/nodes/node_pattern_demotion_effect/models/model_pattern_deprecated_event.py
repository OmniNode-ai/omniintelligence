# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Pattern deprecated event model for pattern_demotion_effect."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_demotion_effect.models.model_demotion_gate_snapshot import (
    ModelDemotionGateSnapshot,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models.model_effective_thresholds import (
    ModelEffectiveThresholds,
)


class ModelPatternDeprecatedEvent(BaseModel):
    """Event payload for pattern-deprecated Kafka event.

    This model is published to Kafka when a pattern is deprecated, enabling
    downstream consumers to invalidate caches or update their state.
    Published to topic: onex.evt.omniintelligence.pattern-deprecated.v1
    """

    model_config = ConfigDict(frozen=True)

    event_type: str = Field(
        default="PatternDeprecated",
        description="Event type identifier",
    )
    pattern_id: UUID = Field(
        ...,
        description="The deprecated pattern ID",
    )
    pattern_signature: str = Field(
        ...,
        description="The pattern signature for identification",
    )
    from_status: str = Field(
        ...,
        description="Status before demotion",
    )
    to_status: str = Field(
        ...,
        description="Status after demotion",
    )
    reason: str = Field(
        ...,
        description="The reason for demotion",
    )
    gate_snapshot: ModelDemotionGateSnapshot = Field(
        ...,
        description="Snapshot of gate values at demotion time",
    )
    effective_thresholds: ModelEffectiveThresholds = Field(
        ...,
        description="The effective thresholds used for this demotion decision",
    )
    deprecated_at: datetime = Field(
        ...,
        description="Timestamp of demotion",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for tracing",
    )


__all__ = ["ModelPatternDeprecatedEvent"]
