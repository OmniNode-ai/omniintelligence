# ONEX Header - Pattern Assembler Compute Node Models
# path: src/omniintelligence/nodes/pattern_assembler_compute/models.py
# node_type: COMPUTE_GENERIC
# version: 1.0.0
# status: stub
"""
Pattern Assembler Compute Node Models - STUB

Pydantic models for pattern assembly compute operations.
All models use strong typing without dict[str, Any].
"""
from typing import TypedDict

from pydantic import BaseModel, Field


class ParsedTraceEventDict(TypedDict, total=False):
    """Typed structure for a parsed trace event.

    Provides type-safe fields for execution trace events.
    """

    # Event identification
    event_id: str
    event_type: str
    timestamp: str

    # Execution context
    step_name: str
    function_name: str
    module_path: str

    # Status
    status: str
    duration_ms: int
    error_message: str

    # Data
    input_summary: str
    output_summary: str


class IntentClassificationDict(TypedDict, total=False):
    """Typed structure for intent classification results.

    Provides type-safe fields for classified intents.
    """

    # Classification
    primary_intent: str
    secondary_intents: list[str]

    # Confidence
    confidence: float
    confidence_scores: dict[str, float]

    # Context
    domain: str
    language: str


class MatchedCriterionDict(TypedDict, total=False):
    """Typed structure for a matched success criterion.

    Provides type-safe fields for criteria matching results.
    """

    # Identification
    criterion_id: str
    criterion_name: str

    # Match result
    matched: bool
    match_score: float
    match_reason: str


class AssembledPatternDict(TypedDict, total=False):
    """Typed structure for the assembled pattern.

    Provides type-safe fields for the final pattern structure.
    """

    # Pattern identification
    pattern_id: str
    pattern_name: str
    pattern_type: str

    # Structure
    trigger: str
    actions: list[str]
    conditions: list[str]

    # Classification
    category: str
    tags: list[str]

    # Quality
    completeness: float
    validity: bool


class PatternAssemblyMetadataDict(TypedDict, total=False):
    """Typed structure for pattern assembly metadata.

    Provides type-safe fields for assembly process metadata.
    """

    # Processing info
    processing_time_ms: int
    timestamp: str

    # Assembly stats
    trace_events_used: int
    keywords_used: int
    criteria_matched: int

    # Source tracking
    source_workflow: str
    source_version: str


class ModelPatternAssemblyComputeInput(BaseModel):
    """Input model for pattern assembly computation.

    Contains data from upstream compute nodes:
    - Parsed execution traces
    - Extracted keywords
    - Classified intents
    - Matched success criteria

    All fields use strong typing without dict[str, Any].
    """

    parsed_traces: list[ParsedTraceEventDict] = Field(
        default_factory=list,
        description="Parsed execution trace events from trace parser with typed fields",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Extracted contextual keywords",
    )
    intent_classification: IntentClassificationDict = Field(
        default_factory=lambda: IntentClassificationDict(),
        description="Classified intent with confidence scores and typed fields",
    )
    matched_criteria: list[MatchedCriterionDict] = Field(
        default_factory=list,
        description="Matched success criteria from criteria matcher with typed fields",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for traceability",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )


class ModelPatternAssemblyComputeOutput(BaseModel):
    """Output model for pattern assembly computation.

    Contains the assembled pattern with metadata and confidence information.

    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        default=False,
        description="Whether assembly was successful",
    )
    assembled_pattern: AssembledPatternDict = Field(
        default_factory=lambda: AssembledPatternDict(),
        description="The assembled pattern structure with typed fields",
    )
    pattern_metadata: PatternAssemblyMetadataDict = Field(
        default_factory=lambda: PatternAssemblyMetadataDict(),
        description="Metadata about the assembled pattern with typed fields",
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


__all__ = [
    "AssembledPatternDict",
    "IntentClassificationDict",
    "MatchedCriterionDict",
    "ModelPatternAssemblyComputeInput",
    "ModelPatternAssemblyComputeOutput",
    "ParsedTraceEventDict",
    "PatternAssemblyMetadataDict",
]
