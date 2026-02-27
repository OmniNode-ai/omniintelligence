# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Output model for AntiGamingAlerterEffect node (OMN-2563)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelAlerterOutput(BaseModel):
    """Output from the AntiGamingAlerterEffect node."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(description="Run ID that was processed.")
    alerts_published: int = Field(
        ge=0, description="Number of alert events published to Kafka."
    )
    diversity_violation_published: bool = Field(
        default=False,
        description="True if a diversity constraint violation was published.",
    )
    topic: str = Field(description="Kafka topic alerts were published to.")


__all__ = ["ModelAlerterOutput"]
