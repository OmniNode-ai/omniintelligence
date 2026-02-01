"""Model for pattern injection subset.

Lightweight model containing only the fields needed for injecting
learned patterns into Claude Code sessions via the manifest injector.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPatternForInjection(BaseModel):
    """Subset of pattern data needed for injection.

    Used by list_validated_patterns operation to return only
    the fields needed by the manifest injector. Reduces memory
    and network overhead for common injection queries.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        from_attributes=True,
    )

    # Identity
    id: UUID = Field(..., description="Pattern UUID")
    pattern_signature: str = Field(..., description="Pattern signature for matching")
    domain_id: str = Field(..., max_length=50, description="Domain identifier")

    # Content for injection
    compiled_snippet: str = Field(
        ...,
        description="Compiled pattern snippet to inject",
    )

    # Quality (for ranking)
    quality_score: float | None = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Quality score for ranking",
    )
    confidence: float = Field(
        ...,
        ge=0.5,
        le=1.0,
        description="Pattern confidence",
    )

    # State
    status: str = Field(..., description="Pattern status (should be 'validated')")
    is_current: bool = Field(..., description="Should always be True for injection")
    version: int = Field(..., ge=1, description="Pattern version")

    # Token budget
    compiled_token_count: int | None = Field(
        default=None,
        ge=1,
        description="Token count for budget management",
    )


__all__ = ["ModelPatternForInjection"]
