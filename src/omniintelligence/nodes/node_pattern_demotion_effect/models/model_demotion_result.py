# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Demotion result model for pattern_demotion_effect."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_demotion_effect.models.model_demotion_gate_snapshot import (
    ModelDemotionGateSnapshot,
)
from omniintelligence.nodes.node_pattern_demotion_effect.models.model_effective_thresholds import (
    ModelEffectiveThresholds,
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


__all__ = ["ModelDemotionResult"]
