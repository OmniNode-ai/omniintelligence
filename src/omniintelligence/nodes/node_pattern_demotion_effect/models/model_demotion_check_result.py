# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Demotion check result model for pattern_demotion_effect."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_pattern_demotion_effect.models.model_demotion_result import (
    ModelDemotionResult,
)


class ModelDemotionCheckResult(BaseModel):
    """Result of the demotion check operation.

    Aggregates results from checking all validated patterns for
    demotion eligibility, including counts and individual demotion
    results.
    """

    model_config = ConfigDict(frozen=True)

    dry_run: bool = Field(
        ...,
        description="Whether this was a dry run",
    )
    patterns_checked: int = Field(
        ...,
        ge=0,
        description="Total number of validated patterns checked",
    )
    patterns_eligible: int = Field(
        ...,
        ge=0,
        description="Number of patterns meeting demotion criteria",
    )
    patterns_demoted: list[ModelDemotionResult] = Field(
        default_factory=list,
        description="List of individual demotion results",
    )
    patterns_skipped_cooldown: int = Field(
        default=0,
        ge=0,
        description="Number of patterns skipped due to cooldown period not elapsed",
    )
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for tracing, if provided in request",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if an error occurred during demotion check",
    )


__all__ = ["ModelDemotionCheckResult"]
