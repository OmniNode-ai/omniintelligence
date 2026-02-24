# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Gate snapshot model for pattern promotion decisions.

This model captures the promotion criteria values at the moment a pattern
was evaluated, providing an audit trail for why a pattern was promoted.

This module is placed in the shared domain models to avoid circular imports
between the events module and the pattern promotion effect node.

Evidence Tier Fields (OMN-2133):
    evidence_tier, measured_attribution_count, and latest_run_result are
    INFORMATIONAL fields captured at decision time for audit purposes.
    The authoritative evidence_tier lives on learned_patterns.evidence_tier
    (denormalized column, attribution binder is sole writer).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.domain.enum_run_result import EnumRunResult

# Valid evidence tier values matching EnumEvidenceTier
EvidenceTierLiteral = Literal["unmeasured", "observed", "measured", "verified"]


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
    evidence_tier: EvidenceTierLiteral | None = Field(
        default=None,
        description="Evidence tier at decision time (informational). "
        "Authority is learned_patterns.evidence_tier column.",
    )
    measured_attribution_count: int = Field(
        default=0,
        ge=0,
        description="Number of measured attribution records for this pattern at decision time",
    )
    latest_run_result: EnumRunResult | None = Field(
        default=None,
        description="Overall result of the latest pipeline run (success|partial|failure). "
        "NULL if no run data available.",
    )


__all__ = ["EvidenceTierLiteral", "ModelGateSnapshot"]
