# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for Intelligence Reducer - QUALITY_ASSESSMENT FSM."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from omniintelligence.nodes.node_intelligence_reducer.models.model_quality_assessment_payload import (
    ModelQualityAssessmentPayload,
)


class ModelReducerInputQualityAssessment(BaseModel):
    """Input model for QUALITY_ASSESSMENT FSM operations."""

    fsm_type: Literal["QUALITY_ASSESSMENT"] = Field(
        ...,
        description="FSM type - must be QUALITY_ASSESSMENT",
    )
    entity_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the entity",
    )
    action: str = Field(
        ...,
        min_length=1,
        description="FSM action to execute",
    )
    payload: ModelQualityAssessmentPayload = Field(
        default_factory=ModelQualityAssessmentPayload,
        description="Quality assessment-specific payload",
    )
    correlation_id: UUID = Field(
        ...,
        description="Correlation ID for tracing",
    )
    lease_id: str | None = Field(
        default=None,
        description="Action lease ID for distributed coordination",
    )
    epoch: int | None = Field(
        default=None,
        description="Epoch for action lease management",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")
