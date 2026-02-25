# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Alert event models for anti-gaming guardrails (OMN-2563).

Alert events are emitted to:
    {env}.onex.evt.omnimemory.anti-gaming-alert.v1
"""

from __future__ import annotations

from typing import Union

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_anti_gaming_guardrails_compute.models.enum_alert_type import (
    EnumAlertType,
)


class ModelGoodhartViolationAlert(BaseModel):
    """Alert: correlated metric pair diverged beyond threshold.

    Emitted when metric A improves while correlated metric B declines
    by more than the configured threshold.
    """

    model_config = ConfigDict(frozen=True)

    alert_type: EnumAlertType = Field(default=EnumAlertType.GOODHART_VIOLATION)
    run_id: str = Field(description="The run that triggered this alert.")
    objective_id: str = Field(description="Objective spec used in evaluation.")
    improving_metric: str = Field(description="ScoreVector dimension that improved.")
    degrading_metric: str = Field(description="Correlated metric that degraded.")
    improvement_delta: float = Field(
        description="How much the improving metric improved."
    )
    degradation_delta: float = Field(
        description="How much the degrading metric degraded."
    )
    threshold: float = Field(description="The configured divergence threshold.")
    occurred_at_utc: str = Field(description="ISO-8601 UTC timestamp.")


class ModelRewardHackingAlert(BaseModel):
    """Alert: score improved but human acceptance did not.

    Emitted when correctness improves by > X% but acceptance_rate does not.
    """

    model_config = ConfigDict(frozen=True)

    alert_type: EnumAlertType = Field(default=EnumAlertType.REWARD_HACKING)
    run_id: str = Field(description="The run that triggered this alert.")
    objective_id: str = Field(description="Objective spec used in evaluation.")
    score_improvement: float = Field(description="How much correctness improved.")
    acceptance_rate_delta: float = Field(description="Change in human acceptance rate.")
    threshold: float = Field(
        description="Correctness improvement threshold that triggered alert."
    )
    occurred_at_utc: str = Field(description="ISO-8601 UTC timestamp.")


class ModelDistributionalShiftAlert(BaseModel):
    """Alert: evidence input distribution shifted from baseline.

    Emitted when KL-divergence or feature drift exceeds the configured threshold.
    """

    model_config = ConfigDict(frozen=True)

    alert_type: EnumAlertType = Field(default=EnumAlertType.DISTRIBUTIONAL_SHIFT)
    run_id: str = Field(description="The run that triggered this alert.")
    objective_id: str = Field(description="Objective spec used in evaluation.")
    drift_score: float = Field(
        ge=0.0,
        description="Computed drift score (KL-divergence or similar).",
    )
    threshold: float = Field(description="The configured drift threshold.")
    shifted_sources: tuple[str, ...] = Field(
        description="Evidence source keys that showed significant drift."
    )
    occurred_at_utc: str = Field(description="ISO-8601 UTC timestamp.")


class ModelDiversityConstraintViolation(BaseModel):
    """Violation: evaluation uses fewer than N distinct evidence source types.

    This is a VETO — it causes EvaluationResult.passed=False.
    """

    model_config = ConfigDict(frozen=True)

    alert_type: EnumAlertType = Field(
        default=EnumAlertType.DIVERSITY_CONSTRAINT_VIOLATION
    )
    run_id: str = Field(description="The run that triggered this violation.")
    objective_id: str = Field(description="Objective spec used in evaluation.")
    present_sources: tuple[str, ...] = Field(
        description="Evidence source types present in the bundle."
    )
    required_min_sources: int = Field(
        description="Minimum distinct source types required by ObjectiveSpec."
    )
    occurred_at_utc: str = Field(description="ISO-8601 UTC timestamp.")


# Union type for all anti-gaming alert events
ModelAntiGamingAlertUnion = Union[
    ModelGoodhartViolationAlert,
    ModelRewardHackingAlert,
    ModelDistributionalShiftAlert,
    ModelDiversityConstraintViolation,
]

__all__ = [
    "ModelAntiGamingAlertUnion",
    "ModelDistributionalShiftAlert",
    "ModelDiversityConstraintViolation",
    "ModelGoodhartViolationAlert",
    "ModelRewardHackingAlert",
]
