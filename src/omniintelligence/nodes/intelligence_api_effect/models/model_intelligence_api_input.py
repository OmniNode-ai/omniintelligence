"""Input model for Intelligence API Effect."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class ApiRequestDataDict(TypedDict, total=False):
    """Typed structure for API request data.

    Provides type-safe fields for intelligence API requests.
    """

    # LLM call fields
    prompt: str
    system_prompt: str
    messages: list[dict[str, str]]  # {"role": "user"|"assistant"|"system", "content": "..."}
    model: str
    temperature: float
    max_tokens: int
    top_p: float

    # Embedding fields
    text: str
    texts: list[str]
    embedding_model: str

    # Code analysis fields
    code: str
    file_path: str
    language: str
    analysis_type: str

    # Common fields
    stream: bool
    metadata: dict[str, str]


class ModelIntelligenceApiInput(BaseModel):
    """Input model for intelligence API operations.

    This model represents the input for making calls to external intelligence APIs.

    All fields use strong typing without dict[str, Any].
    """

    endpoint: str = Field(
        ...,
        min_length=1,
        description="API endpoint to call",
    )
    request_data: ApiRequestDataDict = Field(
        ...,
        description="Request data to send to the API with typed fields",
    )
    operation: Literal["call_llm", "generate_embeddings", "analyze_code"] = Field(
        default="call_llm",
        description="Type of API operation",
    )
    timeout_ms: int = Field(
        default=30000,
        description="Request timeout in milliseconds",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = [
    "ApiRequestDataDict",
    "ModelIntelligenceApiInput",
]
