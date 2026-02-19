"""ModelPatternRecord - pattern record for matching operations."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
