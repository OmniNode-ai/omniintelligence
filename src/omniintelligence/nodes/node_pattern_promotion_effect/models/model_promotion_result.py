# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""ModelPromotionResult - result of a single pattern promotion."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.models.domain import ModelGateSnapshot


class ModelPromotionResult(BaseModel):
    """Result of a single pattern promotion.

    Represents the outcome of promoting one pattern from provisional
    to validated status, including the gate snapshot that triggered
    the promotion.
    """

    model_config = ConfigDict(frozen=True)

    pattern_id: UUID = Field(
        ...,
        description="The unique identifier of the promoted pattern",
    )
    pattern_signature: str = Field(
        ...,
        description="The pattern signature for identification",
    )
    from_status: str = Field(
        ...,
        description="The original status before promotion (e.g., 'provisional')",
    )
    to_status: str = Field(
        ...,
        description="The new status after promotion (e.g., 'validated')",
    )
    promoted_at: datetime | None = Field(
        default=None,
        description="Timestamp when promotion occurred; None if dry_run or if Kafka emit failed (see patterns_failed).",
    )
    reason: str = Field(
        default="auto_promote_rolling_window",
        description="The reason for promotion",
    )
    gate_snapshot: ModelGateSnapshot = Field(
        ...,
        description="Snapshot of gate values at promotion time",
    )
    dry_run: bool = Field(
        default=False,
        description="Whether this was a dry run (no actual mutation)",
    )
