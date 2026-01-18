"""Input model for Intelligence API Effect."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ModelIntelligenceApiInput(BaseModel):
    """Input model for intelligence API operations.

    This model represents the input for making calls to external intelligence APIs.
    """

    endpoint: str = Field(
        ...,
        description="API endpoint to call",
    )
    request_data: dict[str, Any] = Field(
        ...,
        description="Request data to send to the API",
    )
    operation: Literal["call_llm", "generate_embeddings", "analyze_code"] = Field(
        default="call_llm",
        description="Type of API operation",
    )
    timeout_ms: int = Field(
        default=30000,
        description="Request timeout in milliseconds",
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracing",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )

    model_config = {"frozen": True, "extra": "forbid"}


__all__ = ["ModelIntelligenceApiInput"]
