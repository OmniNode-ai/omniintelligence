"""Output model for Context Keyword Extractor Compute."""

from __future__ import annotations

from typing import Self, TypedDict

from pydantic import BaseModel, Field, model_validator


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
    keyword_contexts: dict[str, KeywordContextEntry] = Field(
        default_factory=dict,
        description="Context information for each keyword with typed structure",
    )
    metadata: ExtractionMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the extraction with typed fields",
    )

    @model_validator(mode="after")
    def validate_keywords_match_contexts(self) -> Self:
        """Validate that keywords list matches keyword_contexts keys.

        Ensures consistency between the list of keywords and the dictionary
        containing their context information. Every keyword should have a
        corresponding context entry and vice versa.

        Returns:
            Self with validated keyword/context consistency.

        Raises:
            ValueError: If keywords list doesn't match keyword_contexts keys.
        """
        keywords_set = set(self.keywords)
        contexts_set = set(self.keyword_contexts.keys())

        if keywords_set != contexts_set:
            missing_contexts = keywords_set - contexts_set
            extra_contexts = contexts_set - keywords_set
            error_parts = []
            if missing_contexts:
                error_parts.append(
                    f"keywords missing context entries: {sorted(missing_contexts)}"
                )
            if extra_contexts:
                error_parts.append(
                    f"context entries without keywords: {sorted(extra_contexts)}"
                )
            raise ValueError(
                f"keywords list must match keyword_contexts keys. "
                f"{'; '.join(error_parts)}"
            )
        return self

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ExtractionMetadataDict",
    "KeywordContextEntry",
    "ModelKeywordExtractionOutput",
]
