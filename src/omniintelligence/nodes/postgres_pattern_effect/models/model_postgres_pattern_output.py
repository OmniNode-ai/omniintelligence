"""Output model for PostgreSQL Pattern Effect."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelPostgresPatternOutput(BaseModel):
    """Output model for PostgreSQL pattern operations.

    This model represents the result of pattern storage operations.
    """

    success: bool = Field(
        ...,
        description="Whether the pattern operation succeeded",
    )
    pattern_id: str | None = Field(
        default=None,
        description="ID of the stored/updated pattern",
    )
    patterns: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Query results (list of patterns)",
    )
    rows_affected: int = Field(
        default=0,
        description="Number of rows affected by the operation",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the operation",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPostgresPatternOutput"]
