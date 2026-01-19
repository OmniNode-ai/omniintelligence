"""Output model for Pattern Assembler Orchestrator."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class AssembledPatternOutputDict(TypedDict, total=False):
    """Typed structure for the assembled pattern.

    Provides type-safe fields for the output pattern.
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
    subcategory: str
    tags: list[str]

    # Quality
    confidence: float
    completeness: float
    validity: bool


class ComponentResultsDict(TypedDict, total=False):
    """Typed structure for component processing results.

    Provides type-safe fields for results from each processing component.
    """

    # Trace parsing results
    trace_events_parsed: int
    trace_errors: list[str]

    # Keyword extraction results
    keywords_extracted: int
    keyword_categories: list[str]

    # Intent classification results
    primary_intent: str
    intent_confidence: float
    secondary_intents: list[str]

    # Criteria matching results
    criteria_matched: int
    criteria_unmatched: int
    match_score: float


class AssemblyMetadataDict(TypedDict, total=False):
    """Typed structure for assembly metadata.

    Provides type-safe fields for assembly process metadata.
    """

    # Processing info
    processing_time_ms: int
    timestamp: str

    # Component timing
    trace_parsing_ms: int
    keyword_extraction_ms: int
    intent_classification_ms: int
    criteria_matching_ms: int

    # Status
    status: str
    warnings: list[str]


class ModelPatternAssemblyOutput(BaseModel):
    """Output model for pattern assembly operations.

    This model represents the result of assembling patterns.

    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        ...,
        description="Whether pattern assembly succeeded",
    )
    assembled_pattern: AssembledPatternOutputDict = Field(
        default_factory=lambda: AssembledPatternOutputDict(),
        description="The assembled pattern with typed fields",
    )
    component_results: ComponentResultsDict = Field(
        default_factory=lambda: ComponentResultsDict(),
        description="Results from each component with typed fields",
    )
    metadata: AssemblyMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the assembly with typed fields",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "AssembledPatternOutputDict",
    "AssemblyMetadataDict",
    "ComponentResultsDict",
    "ModelPatternAssemblyOutput",
]
