# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Event model for local-vs-cloud savings estimates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ModelSavingsEstimatedEvent(BaseModel):
    """Frozen event payload for savings projection consumers.

    One event represents one measured counterfactual: the observed local model
    cost versus the cloud baseline cost for the same session/call boundary.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)

    event_timestamp: datetime = Field(description="UTC event time for the estimate.")
    session_id: str = Field(min_length=1, description="Session identifier.")
    model_local: str = Field(min_length=1, description="Observed local model.")
    model_cloud_baseline: str = Field(
        min_length=1, description="Cloud model baseline used for the counterfactual."
    )
    local_cost_usd: Decimal = Field(ge=Decimal("0"))
    cloud_cost_usd: Decimal = Field(ge=Decimal("0"))
    savings_usd: Decimal = Field(description="cloud_cost_usd - local_cost_usd")
    repo_name: str | None = Field(default=None)
    machine_id: str | None = Field(default=None)
    correlation_id: str | None = Field(default=None)
    emitted_at: datetime = Field(description="UTC timestamp of event emission.")

    @field_validator("event_timestamp", "emitted_at")
    @classmethod
    def validate_tz_aware(cls, value: datetime) -> datetime:
        """Require timezone-aware datetimes on the wire."""
        if value.tzinfo is None:
            raise ValueError("timestamp fields must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_savings_consistency(self) -> ModelSavingsEstimatedEvent:
        """Savings must exactly equal cloud minus local cost."""
        if self.savings_usd != self.cloud_cost_usd - self.local_cost_usd:
            raise ValueError("savings_usd must equal cloud_cost_usd - local_cost_usd")
        return self


__all__ = ["ModelSavingsEstimatedEvent"]
