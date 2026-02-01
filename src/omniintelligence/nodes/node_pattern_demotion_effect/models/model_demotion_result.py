"""Output models for pattern_demotion_effect.

This module defines the result models for the pattern demotion effect node,
representing the outcomes of pattern demotion checks and operations.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelDemotionGateSnapshot(BaseModel):
    """Snapshot of gate values at demotion time.

    Captures the demotion criteria values at the moment a pattern
    was evaluated for demotion, providing audit trail for why
    a pattern was demoted.
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
    hours_since_promotion: float | None = Field(
        default=None,
        ge=0.0,
        description="Hours elapsed since pattern was promoted to validated status. "
        "Used to enforce cooldown periods. None if promotion timestamp unavailable.",
    )


class ModelEffectiveThresholds(BaseModel):
    """Effective thresholds used for demotion decision.

    Captures the actual threshold values applied during demotion check,
    including whether overrides were used. Provides transparency into
    the decision criteria.
    """

    model_config = ConfigDict(frozen=True)

    max_success_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Maximum success rate threshold used for demotion check",
    )
    min_failure_streak: int = Field(
        ...,
        ge=0,
        description="Minimum failure streak threshold used for demotion check",
    )
    min_injection_count: int = Field(
        ...,
        ge=0,
        description="Minimum injection count required for eligibility",
    )
    cooldown_hours: int = Field(
        ...,
        ge=0,
        description="Cooldown period in hours since promotion",
    )
    overrides_applied: bool = Field(
        ...,
        description="Whether non-default threshold overrides were applied",
    )


class ModelDemotionResult(BaseModel):
    """Result of a single pattern demotion.

    Represents the outcome of demoting one pattern from validated
    to deprecated status, including the gate snapshot that triggered
    the demotion.
    """

    model_config = ConfigDict(frozen=True)

    pattern_id: UUID = Field(
        ...,
        description="The unique identifier of the demoted pattern",
    )
    pattern_signature: str = Field(
        ...,
        description="The pattern signature for identification",
    )
    from_status: str = Field(
        default="validated",
        description="The original status before demotion (always 'validated')",
    )
    to_status: str = Field(
        default="deprecated",
        description="The new status after demotion (always 'deprecated')",
    )
    deprecated_at: datetime | None = Field(
        default=None,
        description="Timestamp when demotion occurred; None if dry_run",
    )
    reason: str = Field(
        ...,
        description="The reason for demotion. Valid formats: "
        "'manual_disable' (pattern explicitly disabled), "
        "'failure_streak: N consecutive failures' (exceeded failure threshold), "
        "'low_success_rate: 35.0%' (below success rate threshold), "
        "'already_demoted_or_status_changed' (no-op, pattern state changed), "
        "'demotion_failed: ErrorType: message' (error during demotion)",
    )
    gate_snapshot: ModelDemotionGateSnapshot = Field(
        ...,
        description="Snapshot of gate values at demotion time",
    )
    effective_thresholds: ModelEffectiveThresholds = Field(
        ...,
        description="The effective thresholds used for this demotion decision",
    )
    dry_run: bool = Field(
        default=False,
        description="Whether this was a dry run (no actual mutation)",
    )


class ModelDemotionCheckResult(BaseModel):
    """Result of the demotion check operation.

    Aggregates results from checking all validated patterns for
    demotion eligibility, including counts and individual demotion
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
        description="Total number of validated patterns checked",
    )
    patterns_eligible: int = Field(
        ...,
        ge=0,
        description="Number of patterns meeting demotion criteria",
    )
    patterns_demoted: list[ModelDemotionResult] = Field(
        default_factory=list,
        description="List of individual demotion results",
    )
    patterns_skipped_cooldown: int = Field(
        default=0,
        ge=0,
        description="Number of patterns skipped due to cooldown period not elapsed",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for tracing, if provided in request",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if an error occurred during demotion check",
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


__all__ = [
    "ModelDemotionCheckResult",
    "ModelDemotionGateSnapshot",
    "ModelDemotionResult",
    "ModelEffectiveThresholds",
    "ModelPatternDeprecatedEvent",
]
