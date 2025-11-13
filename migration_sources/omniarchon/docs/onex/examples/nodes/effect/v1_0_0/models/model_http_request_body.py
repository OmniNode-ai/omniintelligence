"""HTTP request body model for canary impure tool."""

from typing import Optional

from pydantic import BaseModel, Field


class ModelHttpRequestBody(BaseModel):
    """Model for HTTP request body data."""

    content_type: str = Field(description="Content type of the request body")
    payload: Optional[str] = Field(
        default=None, description="String representation of the payload"
    )
    size_bytes: int = Field(description="Size of the payload in bytes")
    encoding: str = Field(default="utf-8", description="Encoding of the payload")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "content_type": "application/json",
                    "payload": '{"key": "value"}',
                    "size_bytes": 16,
                    "encoding": "utf-8",
                }
            ]
        }
