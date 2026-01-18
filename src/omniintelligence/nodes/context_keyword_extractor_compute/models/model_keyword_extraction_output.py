"""Output model for Context Keyword Extractor Compute."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class KeywordContextEntry(TypedDict, total=False):
    """Typed structure for a single keyword's context information.

    Maps keyword to its extracted context details.
    """

    # Position and occurrence info
    frequency: int
    positions: list[int]
    line_numbers: list[int]

    # Semantic context
    category: str
    relevance_score: float
    related_keywords: list[str]

    # Source context
    surrounding_text: str
    sentence: str

    # Classification
    is_technical: bool
    is_domain_specific: bool
    part_of_speech: str


class ExtractionMetadataDict(TypedDict, total=False):
    """Typed structure for extraction metadata.

    Contains information about the extraction process itself.
    """

    # Processing info
    extraction_duration_ms: int
    algorithm_version: str
    model_name: str

    # Input statistics
    input_length: int
    input_word_count: int
    input_language: str

    # Output statistics
    total_keywords_found: int
    keywords_filtered: int
    confidence_threshold: float

    # Request context
    correlation_id: str
    timestamp_utc: str


class ModelKeywordExtractionOutput(BaseModel):
    """Output model for keyword extraction operations.

    This model represents the result of extracting contextual keywords.
    """

    success: bool = Field(
        ...,
        description="Whether keyword extraction succeeded",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="List of extracted keywords",
    )
    keyword_contexts: dict[str, KeywordContextEntry] | dict[str, Any] = Field(
        default_factory=dict,
        description="Context information for each keyword with typed structure",
    )
    metadata: ExtractionMetadataDict | dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata about the extraction with typed fields",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ExtractionMetadataDict",
    "KeywordContextEntry",
    "ModelKeywordExtractionOutput",
]
