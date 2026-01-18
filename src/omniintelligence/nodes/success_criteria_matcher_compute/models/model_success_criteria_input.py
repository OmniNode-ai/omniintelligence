"""Input model for Success Criteria Matcher Compute."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelSuccessCriteriaInput(BaseModel):
    """Input model for success criteria matching operations.

    This model represents the input for matching execution outcomes against criteria.
    """

    execution_outcome: dict[str, Any] = Field(
        ...,
        description="Execution outcome to match against criteria",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    criteria_set: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Set of success criteria to match against",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelSuccessCriteriaInput"]
