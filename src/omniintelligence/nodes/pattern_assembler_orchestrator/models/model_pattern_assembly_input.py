"""Input model for Pattern Assembler Orchestrator."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class RawAssemblyDataDict(TypedDict, total=False):
    """Typed structure for raw assembly data.

    Provides type-safe fields for input data to assemble.
    """

    # Source content
    content: str
    file_path: str
    language: str
    framework: str

    # Execution data
    execution_traces: list[str]
    log_entries: list[str]

    # Context
    project_name: str
    repository: str
    branch: str

    # Metadata
    source_type: str
    timestamp: str


class AssemblyParametersDict(TypedDict, total=False):
    """Typed structure for assembly parameters.

    Provides type-safe fields for configuring the assembly process.
    """

    # Parsing options
    trace_depth: int
    max_events: int

    # Extraction options
    min_keyword_length: int
    max_keywords: int
    keyword_categories: list[str]

    # Classification options
    confidence_threshold: float
    max_intents: int

    # Matching options
    criteria_strictness: str  # "strict", "moderate", "lenient"

    # Output options
    include_debug_info: bool
    verbose_output: bool


class ModelPatternAssemblyInput(BaseModel):
    """Input model for pattern assembly operations.

    This model represents the input for assembling patterns from components.

    All fields use strong typing without dict[str, Any].
    """

    raw_data: RawAssemblyDataDict = Field(
        ...,
        description="Raw data to assemble into patterns with typed fields",
    )
    assembly_parameters: AssemblyParametersDict = Field(
        default_factory=lambda: AssemblyParametersDict(),
        description="Parameters for the assembly process with typed fields",
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


__all__ = [
    "AssemblyParametersDict",
    "ModelPatternAssemblyInput",
    "RawAssemblyDataDict",
]
