"""Gate snapshot model for pattern promotion decisions.

This model captures the promotion criteria values at the moment a pattern
was evaluated, providing an audit trail for why a pattern was promoted.

This module is placed in the shared domain models to avoid circular imports
between the events module and the pattern promotion effect node.
"""

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


__all__ = ["ModelGateSnapshot"]
