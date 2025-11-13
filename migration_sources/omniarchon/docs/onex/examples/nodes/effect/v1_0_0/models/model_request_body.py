"""Request body model for canary impure tool input state."""

from typing import Optional

from pydantic import BaseModel, Field

from .model_http_headers import ModelHttpHeaders


class ModelRequestBody(BaseModel):
    """Model for HTTP request body in input state."""

    content_type: str = Field(description="Content type of the request body")
    payload: Optional[str] = Field(
        default=None, description="String representation of the payload"
    )
    size_bytes: int = Field(description="Size of the payload in bytes")
    encoding: str = Field(default="utf-8", description="Encoding of the payload")
    headers: Optional[ModelHttpHeaders] = Field(
        default=None, description="Additional headers"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "content_type": "application/json",
                    "payload": '{"key": "value"}',
                    "size_bytes": 16,
                    "encoding": "utf-8",
                    "headers": {"Authorization": "Bearer token"},
                }
            ]
        }
