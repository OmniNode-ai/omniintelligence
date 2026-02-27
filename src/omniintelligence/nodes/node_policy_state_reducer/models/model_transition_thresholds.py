# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Transition threshold configuration for PolicyStateReducer (OMN-2557).

Thresholds are table-driven from ObjectiveSpec — not hardcoded in the reducer.
Defaults are provided for standalone operation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelTransitionThresholds(BaseModel):
    """Thresholds controlling lifecycle state transitions.

    These values are sourced from ObjectiveSpec at runtime.
    Defaults represent conservative production-ready values.
    """

    model_config = ConfigDict(frozen=True)

    # CANDIDATE → VALIDATED
    validated_min_runs: int = Field(
        default=10,
        gt=0,
        description="Minimum positive runs required for CANDIDATE → VALIDATED.",
    )
    validated_positive_signal_floor: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum positive signal ratio for CANDIDATE → VALIDATED.",
    )

    # VALIDATED → PROMOTED
    promoted_significance_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Statistical significance score required for VALIDATED → PROMOTED.",
    )
    promoted_min_runs: int = Field(
        default=50,
        gt=0,
        description="Minimum total runs required for VALIDATED → PROMOTED.",
    )

    # PROMOTED → DEPRECATED (reliability floor)
    reliability_floor: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description=(
            "If reliability_0_1 falls below this floor, PROMOTED → DEPRECATED "
            "and tool is auto-blacklisted."
        ),
    )

    # Auto-blacklist floor (for tool_reliability)
    blacklist_floor: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description=(
            "If reliability_0_1 falls below this floor, the tool is auto-blacklisted "
            "and system.alert.tool_degraded is emitted."
        ),
    )


__all__ = ["ModelTransitionThresholds"]
