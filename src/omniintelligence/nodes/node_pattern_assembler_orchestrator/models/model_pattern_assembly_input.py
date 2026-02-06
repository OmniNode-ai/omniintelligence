"""Input model for Pattern Assembler Orchestrator.

This module defines the input models for the pattern assembly orchestrator,
with interfaces aligned to downstream compute nodes for seamless data flow.
"""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class TraceDataDict(TypedDict, total=False):
    """Typed structure for trace data aligned with trace parser input.

    This structure mirrors ModelTraceData from the execution_trace_parser_compute
    node to enable direct data flow without transformation.
    """

    span_id: str
    trace_id: str
    parent_span_id: str
    operation_name: str
    service_name: str
    start_time: str
    end_time: str
    duration_ms: float
    status: str
    tags: dict[str, str]
    logs: list[dict[str, str | dict[str, str]]]


class SuccessCriterionDict(TypedDict, total=False):
    """Typed structure for success criteria aligned with criteria matcher input.

    This structure mirrors SuccessCriterionDict from success_criteria_matcher_compute
    to enable direct data flow without transformation.
    """

    criterion_id: str
    criterion_name: str
    field: str  # Field to match in execution outcome
    operator: str  # "equals", "contains", "greater_than", "less_than", "regex"
    expected_value: str | int | float | bool | None
    case_sensitive: bool
    required: bool
    weight: float
    description: str


class RawAssemblyDataDict(TypedDict, total=False):
    """Typed structure for raw assembly data.

    Provides type-safe fields for input data to assemble.
    The execution_traces field uses structured TraceDataDict for alignment
    with the execution_trace_parser_compute node.
    """

    # Source content
    content: str
    file_path: str
    language: str
    framework: str

    # Execution data - now structured for direct use by trace parser
    execution_traces: list[TraceDataDict]
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

    Interfaces are aligned with downstream compute nodes:
    - execution_traces uses TraceDataDict (aligns with execution_trace_parser_compute)
    - success_criteria uses SuccessCriterionDict (aligns with success_criteria_matcher_compute)
    """

    raw_data: RawAssemblyDataDict = Field(
        ...,
        description="Raw data to assemble into patterns with typed fields",
    )
    assembly_parameters: AssemblyParametersDict = Field(
        default_factory=lambda: AssemblyParametersDict(),
        description="Parameters for the assembly process with typed fields",
    )
    success_criteria: list[SuccessCriterionDict] = Field(
        default_factory=list,
        description="Success criteria for pattern validation, aligned with criteria matcher",
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
    "SuccessCriterionDict",
    "TraceDataDict",
]
