# ONEX Header - Pattern Assembler Compute Node Models
# path: src/omniintelligence/nodes/pattern_assembler_compute/models.py
# node_type: COMPUTE_GENERIC
# version: 1.0.0
# status: stub
"""
Pattern Assembler Compute Node Models - STUB

Pydantic models for pattern assembly compute operations.
"""
from typing import Any

from pydantic import BaseModel, Field


class ModelPatternAssemblyComputeInput(BaseModel):
    """Input model for pattern assembly computation.

    Contains data from upstream compute nodes:
    - Parsed execution traces
    - Extracted keywords
    - Classified intents
    - Matched success criteria
    """

    parsed_traces: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Parsed execution trace events from trace parser",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Extracted contextual keywords",
    )
    intent_classification: dict[str, Any] = Field(
        default_factory=dict,
        description="Classified intent with confidence scores",
    )
    matched_criteria: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Matched success criteria from criteria matcher",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for traceability",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )


class ModelPatternAssemblyComputeOutput(BaseModel):
    """Output model for pattern assembly computation.

    Contains the assembled pattern with metadata and confidence information.
    """

    success: bool = Field(
        default=False,
        description="Whether assembly was successful",
    )
    assembled_pattern: dict[str, Any] = Field(
        default_factory=dict,
        description="The assembled pattern structure",
    )
    pattern_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the assembled pattern",
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for the assembled pattern",
    )
    assembly_warnings: list[str] = Field(
        default_factory=list,
        description="Warnings encountered during assembly",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if assembly failed",
    )
