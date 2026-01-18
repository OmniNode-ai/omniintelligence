"""Input model for Pattern Matching Compute."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class PatternMatchingContextDict(TypedDict, total=False):
    """Typed structure for pattern matching context.

    Provides stronger typing for common context fields while allowing
    additional fields via dict[str, Any] union.
    """

    # Source file context
    source_path: str
    file_extension: str
    language: str
    framework: str

    # Pattern matching parameters
    min_confidence: float
    max_results: int
    include_similar: bool
    pattern_categories: list[str]

    # Code context
    surrounding_code: str
    imports: list[str]
    class_name: str
    function_name: str

    # Repository context
    repository_name: str
    branch: str
    commit_hash: str

    # Request metadata
    correlation_id: str
    request_id: str


class ModelPatternMatchingInput(BaseModel):
    """Input model for pattern matching operations.

    This model represents the input for matching code patterns.
    """

    code_snippet: str = Field(
        ...,
        min_length=1,
        description="Code snippet to match patterns against",
    )
    project_name: str | None = Field(
        default=None,
        description="Name of the project for context",
    )
    context: PatternMatchingContextDict | dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for pattern matching with typed common fields",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelPatternMatchingInput", "PatternMatchingContextDict"]
