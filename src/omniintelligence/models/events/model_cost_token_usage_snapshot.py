# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Snapshot event model for token-usage projections."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omniintelligence.models.events.model_cost_summary_snapshot import AggregationWindow


class ModelCostTokenUsageSnapshotRow(BaseModel):
    """One model/time bucket in a token-usage snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    bucket_timestamp: datetime
    model_id: str = Field(min_length=1)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @field_validator("bucket_timestamp")
    @classmethod
    def validate_bucket_tz_aware(cls, value: datetime) -> datetime:
        """Require timezone-aware bucket timestamps."""
        if value.tzinfo is None:
            raise ValueError("bucket_timestamp must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_total_tokens(self) -> ModelCostTokenUsageSnapshotRow:
        """Token total must match prompt plus completion tokens."""
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError(
                "total_tokens must equal prompt_tokens + completion_tokens"
            )
        return self


class ModelCostTokenUsageSnapshot(BaseModel):
    """Frozen payload for ``onex.snapshot.projection.cost.token_usage.v1``."""

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    window: AggregationWindow
    rows: list[ModelCostTokenUsageSnapshotRow]
    snapshot_timestamp: datetime

    @field_validator("snapshot_timestamp")
    @classmethod
    def validate_snapshot_tz_aware(cls, value: datetime) -> datetime:
        """Require timezone-aware snapshot timestamps."""
        if value.tzinfo is None:
            raise ValueError("snapshot_timestamp must be timezone-aware")
        return value


__all__ = ["ModelCostTokenUsageSnapshot", "ModelCostTokenUsageSnapshotRow"]
