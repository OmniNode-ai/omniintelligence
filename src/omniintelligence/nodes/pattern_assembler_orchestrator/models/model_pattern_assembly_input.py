"""Input model for Pattern Assembler Orchestrator."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelPatternAssemblyInput(BaseModel):
    """Input model for pattern assembly operations.

    This model represents the input for assembling patterns from components.
    """

    raw_data: dict[str, Any] = Field(
        ...,
        description="Raw data to assemble into patterns",
    )
    assembly_parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the assembly process",
    )
    include_trace_parsing: bool = Field(
        default=True,
        description="Whether to include trace parsing",
    )
    include_keyword_extraction: bool = Field(
        default=True,
        description="Whether to include keyword extraction",
    )
    include_intent_classification: bool = Field(
        default=True,
        description="Whether to include intent classification",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternAssemblyInput"]
