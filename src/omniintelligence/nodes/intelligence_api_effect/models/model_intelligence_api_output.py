"""Output model for Intelligence API Effect."""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class ApiResponseDataDict(TypedDict, total=False):
    """Typed structure for API response data.

    Provides type-safe fields for intelligence API responses.
    """

    # LLM response fields
    content: str
    role: str
    finish_reason: str
    model_used: str
    token_count: int
    prompt_tokens: int
    completion_tokens: int

    # Embedding response fields
    embedding: list[float]
    embeddings: list[list[float]]
    dimensions: int

    # Code analysis response fields
    quality_score: float
    issues: list[str]
    recommendations: list[str]
    patterns_detected: list[str]

    # Error fields
    error_code: str
    error_message: str


class ApiCallMetadataDict(TypedDict, total=False):
    """Typed structure for API call metadata.

    Provides type-safe fields for API operation metadata.
    """

    # Processing info
    request_timestamp: str
    response_timestamp: str

    # Request details
    model_requested: str
    endpoint_called: str

    # Performance
    queue_time_ms: int
    processing_time_ms: int

    # Rate limiting
    rate_limit_remaining: int
    rate_limit_reset: str


class ModelIntelligenceApiOutput(BaseModel):
    """Output model for intelligence API operations.

    This model represents the result of intelligence API calls.

    All fields use strong typing without dict[str, Any].
    """

    success: bool = Field(
        ...,
        description="Whether the API call succeeded",
    )
    response_data: ApiResponseDataDict = Field(
        default_factory=lambda: ApiResponseDataDict(),
        description="Response data from the API with typed fields",
    )
    status_code: int = Field(
        default=200,
        description="HTTP status code from the API",
    )
    latency_ms: float = Field(
        default=0.0,
        description="Request latency in milliseconds",
    )
    metadata: ApiCallMetadataDict | None = Field(
        default=None,
        description="Additional metadata about the API call with typed fields",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ApiCallMetadataDict",
    "ApiResponseDataDict",
    "ModelIntelligenceApiOutput",
]
