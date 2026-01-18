"""Input model for PostgreSQL Pattern Effect."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ModelPostgresPatternInput(BaseModel):
    """Input model for PostgreSQL pattern operations.

    This model represents the input for pattern storage operations.
    """

    operation: Literal["store_pattern", "query_patterns", "update_pattern_score"] = Field(
        default="store_pattern",
        description="Type of pattern storage operation",
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
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPostgresPatternInput"]
