"""Output model for Pattern Assembler Orchestrator."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ModelPatternAssemblyOutput(BaseModel):
    """Output model for pattern assembly operations.

    This model represents the result of assembling patterns.
    """

    success: bool = Field(
        ...,
        description="Whether pattern assembly succeeded",
    )
    assembled_pattern: dict[str, Any] = Field(
        default_factory=dict,
        description="The assembled pattern",
    )
    component_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Results from each component (trace, keywords, intent, criteria)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the assembly",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternAssemblyOutput"]
