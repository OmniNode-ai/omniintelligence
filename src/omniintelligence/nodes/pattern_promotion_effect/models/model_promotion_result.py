"""Output models for pattern_promotion_effect.

This module defines the result models for the pattern promotion effect node,
representing the outcomes of pattern promotion checks and operations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelGateSnapshot(BaseModel):
    """Snapshot of gate values at promotion time.

    Captures the promotion criteria values at the moment a pattern
    was evaluated for promotion, providing audit trail for why
    a pattern was promoted.
    """

    model_config = ConfigDict(frozen=True)

    success_rate_rolling_20: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Success rate over the rolling window of last 20 injections",
    )
    injection_count_rolling_20: int = Field(
        ...,
        ge=0,
        description="Number of injections in the rolling window",
    )
    failure_streak: int = Field(
        ...,
        ge=0,
        description="Current consecutive failure count",
    )
    disabled: bool = Field(
        default=False,
        description="Whether the pattern is currently disabled",
    )


class ModelPromotionResult(BaseModel):
    """Result of a single pattern promotion.

    Represents the outcome of promoting one pattern from provisional
    to validated status, including the gate snapshot that triggered
    the promotion.
    """

    model_config = ConfigDict(frozen=True)

    pattern_id: UUID = Field(
        ...,
        description="The unique identifier of the promoted pattern",
    )
    pattern_signature: str = Field(
        ...,
        description="The pattern signature for identification",
    )
    from_status: str = Field(
        ...,
        description="The original status before promotion (e.g., 'provisional')",
    )
    to_status: str = Field(
        ...,
        description="The new status after promotion (e.g., 'validated')",
    )
    promoted_at: datetime | None = Field(
        default=None,
        description="Timestamp when promotion occurred; None if dry_run",
    )
    reason: str = Field(
        default="auto_promote_rolling_window",
        description="The reason for promotion",
    )
    gate_snapshot: ModelGateSnapshot = Field(
        ...,
        description="Snapshot of gate values at promotion time",
    )
    dry_run: bool = Field(
        default=False,
        description="Whether this was a dry run (no actual mutation)",
    )


class ModelPromotionCheckResult(BaseModel):
    """Result of the promotion check operation.

    Aggregates results from checking all provisional patterns for
    promotion eligibility, including counts and individual promotion
    results.
    """

    model_config = ConfigDict(frozen=True)

    dry_run: bool = Field(
        ...,
        description="Whether this was a dry run",
    )
    patterns_checked: int = Field(
        ...,
        ge=0,
        description="Total number of provisional patterns checked",
    )
    patterns_eligible: int = Field(
        ...,
        ge=0,
        description="Number of patterns meeting promotion criteria",
    )
    patterns_promoted: list[ModelPromotionResult] = Field(
        default_factory=list,
        description="List of individual promotion results",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for tracing, if provided in request",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if an error occurred during promotion check",
    )


class ModelPatternPromotedEvent(BaseModel):
    """Event payload for pattern-promoted Kafka event.

    This model is published to Kafka when a pattern is promoted, enabling
    downstream consumers to invalidate caches or update their state.
    Published to topic: onex.evt.omniintelligence.pattern-promoted.v1
    """

    model_config = ConfigDict(frozen=True)

    event_type: str = Field(
        default="PatternPromoted",
        description="Event type identifier",
    )
    pattern_id: UUID = Field(
        ...,
        description="The promoted pattern ID",
    )
    pattern_signature: str = Field(
        ...,
        description="The pattern signature for identification",
    )
    from_status: str = Field(
        ...,
        description="Status before promotion",
    )
    to_status: str = Field(
        ...,
        description="Status after promotion",
    )
    success_rate_rolling_20: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Success rate at time of promotion",
    )
    promoted_at: datetime = Field(
        ...,
        description="Timestamp of promotion",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for tracing",
    )
