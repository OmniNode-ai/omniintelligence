# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Snapshot event model for cost summary projections."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AggregationWindow = Literal["24h", "7d", "30d"]


class ModelCostSummarySnapshot(BaseModel):
    """Frozen payload for ``onex.snapshot.projection.cost.summary.v1``."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    window: AggregationWindow
    total_cost_usd: Decimal = Field(ge=Decimal("0"))
    total_savings_usd: Decimal = Field(ge=Decimal("0"))
    total_tokens: int = Field(ge=0)
    session_count: int = Field(ge=0)
    snapshot_timestamp: datetime

    @field_validator("snapshot_timestamp")
    @classmethod
    def validate_tz_aware(cls, value: datetime) -> datetime:
        """Require timezone-aware snapshot timestamps."""
        if value.tzinfo is None:
            raise ValueError("snapshot_timestamp must be timezone-aware")
        return value


__all__ = ["AggregationWindow", "ModelCostSummarySnapshot"]
