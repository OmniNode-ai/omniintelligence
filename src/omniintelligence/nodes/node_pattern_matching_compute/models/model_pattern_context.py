"""ModelPatternContext - structured context for pattern matching operations."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from omniintelligence.constants import MAX_PATTERN_MATCH_RESULTS


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
