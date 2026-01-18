"""Output model for Intelligence API Effect."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelIntelligenceApiOutput(BaseModel):
    """Output model for intelligence API operations.

    This model represents the result of intelligence API calls.
    """

    success: bool = Field(
        ...,
        description="Whether the API call succeeded",
    )
    response_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Response data from the API",
    )
    status_code: int = Field(
        default=200,
        description="HTTP status code from the API",
    )
    latency_ms: float = Field(
        default=0.0,
        description="Request latency in milliseconds",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the API call",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntelligenceApiOutput"]
