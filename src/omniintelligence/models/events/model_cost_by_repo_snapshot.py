# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Snapshot event model for cost-by-repository projections."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from omniintelligence.models.events.model_cost_summary_snapshot import AggregationWindow


class ModelCostByRepoSnapshotRow(BaseModel):
    """One repository bucket in a cost-by-repo snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    repo_name: str | None = Field(default=None)
    cost_usd: Decimal = Field(ge=Decimal("0"))
    call_count: int = Field(ge=0)


class ModelCostByRepoSnapshot(BaseModel):
    """Frozen payload for ``onex.snapshot.projection.cost.by_repo.v1``."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    window: AggregationWindow
    rows: list[ModelCostByRepoSnapshotRow]
    snapshot_timestamp: datetime

    @field_validator("snapshot_timestamp")
    @classmethod
    def validate_tz_aware(cls, value: datetime) -> datetime:
        """Require timezone-aware snapshot timestamps."""
        if value.tzinfo is None:
            raise ValueError("snapshot_timestamp must be timezone-aware")
        return value


__all__ = ["ModelCostByRepoSnapshot", "ModelCostByRepoSnapshotRow"]
