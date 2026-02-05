"""Input model for Pattern Matching Compute."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from omniintelligence.constants import MAX_PATTERN_MATCH_RESULTS


class ModelPatternRecord(BaseModel):
    """Pattern record for matching operations.

    Represents a pattern from the pattern library that will be matched
    against the code snippet. Patterns are provided by the caller
    (typically an orchestrator that fetches from pattern_storage).

    Attributes:
        pattern_id: Unique identifier for the pattern.
        signature: The pattern signature (text/regex/structure).
        domain: Domain where the pattern belongs.
        keywords: Extracted keywords for keyword-based matching.
        status: Pattern lifecycle status (validated, provisional, etc.).
        confidence: Original pattern confidence score.
        category: Pattern category for filtering.
    """

    pattern_id: str = Field(
        ...,
        description="Unique identifier for the pattern",
    )
    signature: str = Field(
        ...,
        min_length=1,
        description="The pattern signature (text/regex/structure)",
    )
    domain: str = Field(
        ...,
        min_length=1,
        description="Domain where the pattern belongs",
    )
    keywords: list[str] | None = Field(
        default=None,
        description="Extracted keywords for keyword-based matching",
    )
    status: str | None = Field(
        default=None,
        description="Pattern lifecycle status (validated, provisional, etc.)",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Original pattern confidence score",
    )
    category: str | None = Field(
        default=None,
        description="Pattern category for filtering",
    )

    model_config = {"frozen": True, "extra": "forbid"}


class ModelPatternContext(BaseModel):
    """Structured context for pattern matching operations.

    Provides fully typed context fields for pattern matching,
    replacing the previous TypedDict + dict[str, Any] union.
    """

    # Source file context
    source_path: str | None = Field(
        default=None,
        min_length=1,
        description="Path to the source file being analyzed",
    )
    file_extension: str | None = Field(
        default=None,
        description="File extension (e.g., '.py', '.ts')",
    )
    language: str = Field(
        default="python",
        description="Programming language of the code snippet",
    )
    framework: str | None = Field(
        default=None,
        description="Framework context (e.g., 'fastapi', 'django')",
    )

    # Pattern matching parameters
    min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for pattern matches (0.0 to 1.0)",
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=MAX_PATTERN_MATCH_RESULTS,
        description="Maximum number of pattern matches to return",
    )
    include_similar: bool = Field(
        default=True,
        description="Whether to include similar but not exact pattern matches",
    )
    pattern_categories: list[str] = Field(
        default_factory=list,
        description="Filter patterns by these categories (empty = all categories)",
    )

    # Code context
    surrounding_code: str | None = Field(
        default=None,
        description="Additional surrounding code for context",
    )
    imports: list[str] = Field(
        default_factory=list,
        description="List of imports in the source file",
    )
    class_name: str | None = Field(
        default=None,
        description="Name of the containing class, if applicable",
    )
    function_name: str | None = Field(
        default=None,
        description="Name of the containing function, if applicable",
    )

    # Repository context
    repository_name: str | None = Field(
        default=None,
        description="Name of the source repository",
    )
    branch: str | None = Field(
        default=None,
        description="Git branch name",
    )
    commit_hash: str | None = Field(
        default=None,
        description="Git commit hash for traceability",
    )

    # Request metadata
    correlation_id: UUID | None = Field(
        default=None,
        description="Correlation ID for distributed tracing (UUID format enforced)",
    )
    request_id: str | None = Field(
        default=None,
        description="Unique request identifier",
    )

    model_config = {"frozen": True, "extra": "forbid"}


# Supported pattern matching operations
PatternMatchingOperation = Literal[
    "match",  # Find patterns matching the code snippet
    "similarity",  # Compute similarity scores against known patterns
    "classify",  # Classify code snippet into pattern categories
    "validate",  # Validate code against expected patterns
]


class ModelPatternMatchingInput(BaseModel):
    """Input model for pattern matching operations.

    This model represents the input for matching code patterns.
    All fields are fully typed with validation constraints.

    The patterns field contains the pattern library to match against.
    This follows the compute node purity principle - patterns are passed
    in rather than fetched via I/O.
    """

    code_snippet: str = Field(
        ...,
        min_length=1,
        description="Code snippet to match patterns against",
    )
    patterns: list[ModelPatternRecord] = Field(
        default_factory=list,
        description="Pattern library to match against (provided by orchestrator)",
    )
    operation: PatternMatchingOperation = Field(
        default="match",
        description="Type of pattern matching operation to perform",
    )
    project_name: str | None = Field(
        default=None,
        description="Name of the project for context",
    )
    context: ModelPatternContext = Field(
        default_factory=ModelPatternContext,
        description="Structured context for pattern matching",
    )
    match_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum match score threshold (0.0 to 1.0)",
    )

    @field_validator("match_threshold")
    @classmethod
    def validate_match_threshold(cls, v: float) -> float:
        """Validate match_threshold is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"match_threshold must be between 0.0 and 1.0, got {v}")
        return v

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ModelPatternContext",
    "ModelPatternMatchingInput",
    "ModelPatternRecord",
    "PatternMatchingOperation",
]
