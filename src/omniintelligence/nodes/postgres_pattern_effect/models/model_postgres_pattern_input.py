"""Input model for PostgreSQL Pattern Effect."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelPostgresPatternInput(BaseModel):
    """Input model for PostgreSQL pattern operations.

    This model represents the input for pattern storage operations.
    """

    operation: str = Field(
        default="store_pattern",
        description="Type of operation (store_pattern, query_patterns, update_pattern_score)",
    )
    pattern_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Pattern data to store or update",
    )
    query_filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters for querying patterns",
    )
    pattern_id: Optional[str] = Field(
        default=None,
        description="Pattern ID for update operations",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPostgresPatternInput"]
