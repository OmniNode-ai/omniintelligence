"""Input model for PostgreSQL Pattern Effect."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator


class ModelPostgresPatternInput(BaseModel):
    """Input model for PostgreSQL pattern operations.

    This model represents the input for pattern storage operations.

    Operation-specific requirements:
        - store_pattern: requires pattern_data (non-empty dict)
        - query_patterns: allows optional query_filters
        - update_pattern_score: requires pattern_id and pattern_data with score
    """

    operation: Literal["store_pattern", "query_patterns", "update_pattern_score"] = (
        Field(
            default="store_pattern",
            description="Type of pattern storage operation",
        )
    )
    pattern_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Pattern data to store or update",
    )
    query_filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Filters for querying patterns",
    )
    pattern_id: str | None = Field(
        default=None,
        min_length=1,
        description="Pattern ID for update operations",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    @model_validator(mode="after")
    def validate_operation_requirements(self) -> Self:
        """Validate that required fields are provided for each operation type."""
        if self.operation == "store_pattern":
            if not self.pattern_data:
                raise ValueError("store_pattern operation requires pattern_data")
        elif self.operation == "update_pattern_score":
            if not self.pattern_id:
                raise ValueError("update_pattern_score operation requires pattern_id")
            if not self.pattern_data:
                raise ValueError("update_pattern_score operation requires pattern_data")
        # query_patterns has no strict requirements (empty filters returns all)
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPostgresPatternInput"]
