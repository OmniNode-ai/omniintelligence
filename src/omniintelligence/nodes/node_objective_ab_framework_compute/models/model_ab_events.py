# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""A/B testing event models (OMN-2571)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelRunEvaluatedEvent(BaseModel):
    """Event emitted for each variant evaluation of a run.

    Emitted separately per variant, tagged with objective_version.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(description="The execution run that was evaluated.")
    variant_id: str = Field(description="The variant that produced this result.")
    objective_id: str = Field(description="Objective spec ID.")
    objective_version: str = Field(description="Objective spec version.")
    role: str = Field(description="'active' or 'shadow'.")
    passed: bool = Field(description="Whether the evaluation passed.")
    occurred_at_utc: str = Field(description="ISO-8601 UTC timestamp.")


class ModelObjectiveVariantDivergenceEvent(BaseModel):
    """Event emitted when active and shadow variants disagree on outcome.

    Divergence: different passed outcomes OR ScoreVector L2 delta > threshold.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(description="The run that triggered divergence.")
    active_variant_id: str = Field(description="Active variant ID.")
    shadow_variant_id: str = Field(description="Shadow variant ID.")
    active_passed: bool = Field(description="Active variant result.")
    shadow_passed: bool = Field(description="Shadow variant result.")
    score_delta: float = Field(
        ge=0.0,
        description="L2 distance between active and shadow ScoreVectors.",
    )
    occurred_at_utc: str = Field(description="ISO-8601 UTC timestamp.")


class ModelObjectiveUpgradeReadyEvent(BaseModel):
    """Event emitted when a shadow variant reaches statistical significance.

    Signals that the shadow variant is ready for operator-promoted upgrade.
    Promotion is NOT automatic — requires explicit confirmation.
    """

    model_config = ConfigDict(frozen=True)

    shadow_variant_id: str = Field(description="Shadow variant ready for promotion.")
    active_variant_id: str = Field(description="Current active variant.")
    win_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Shadow win rate over the evaluation period.",
    )
    total_runs: int = Field(ge=0, description="Total runs evaluated.")
    occurred_at_utc: str = Field(description="ISO-8601 UTC timestamp.")


__all__ = [
    "ModelObjectiveUpgradeReadyEvent",
    "ModelObjectiveVariantDivergenceEvent",
    "ModelRunEvaluatedEvent",
]
