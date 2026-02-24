# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Input model for Success Criteria Matcher Compute."""

from __future__ import annotations

from typing import TypedDict

from omnibase_core.types import PrimitiveValue
from pydantic import BaseModel, Field


class ExecutionOutcomeDict(TypedDict, total=False):
    """Typed structure for execution outcome data.

    Provides type-safe fields for execution outcomes to match against criteria.
    """

    # Identification
    execution_id: str
    workflow_id: str
    step_id: str

    # Status
    status: str  # "success", "failure", "partial", "skipped"
    exit_code: int
    error_message: str

    # Metrics
    duration_ms: int
    retry_count: int

    # Results
    output_value: str
    output_type: str
    artifacts_generated: list[str]

    # Context
    timestamp: str
    environment: str


class SuccessCriterionDict(TypedDict, total=False):
    """Typed structure for a single success criterion.

    Provides type-safe fields for defining success criteria.
    """

    # Identification
    criterion_id: str
    criterion_name: str

    # Matching rules
    field: str  # Field to match in execution outcome
    operator: str  # "equals", "contains", "greater_than", "less_than", "regex"
    expected_value: PrimitiveValue | None
    case_sensitive: bool

    # Requirements
    required: bool
    weight: float  # For weighted matching

    # Description
    description: str


class ModelSuccessCriteriaInput(BaseModel):
    """Input model for success criteria matching operations.

    This model represents the input for matching execution outcomes against criteria.

    All fields use strong typing without dict[str, Any].
    """

    execution_outcome: ExecutionOutcomeDict = Field(
        ...,
        description="Execution outcome to match against criteria with typed fields",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    criteria_set: list[SuccessCriterionDict] = Field(
        default_factory=list,
        description="Set of success criteria to match against with typed items",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ExecutionOutcomeDict",
    "ModelSuccessCriteriaInput",
    "SuccessCriterionDict",
]
