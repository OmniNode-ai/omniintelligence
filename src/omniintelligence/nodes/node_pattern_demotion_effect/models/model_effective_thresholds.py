"""Effective thresholds model for pattern_demotion_effect."""

from pydantic import BaseModel, ConfigDict, Field


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


__all__ = ["ModelEffectiveThresholds"]
