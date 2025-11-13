#!/usr/bin/env python3
"""
HTTP Headers Model for Canary Impure Tool

Strongly typed model for HTTP headers to replace Dict[str, str] usage
in HTTP request and response operations.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ModelHttpHeaders(BaseModel):
    """Strongly typed model for HTTP headers."""

    content_type: Optional[str] = Field(default=None, description="Content-Type header")
    authorization: Optional[str] = Field(
        default=None, description="Authorization header"
    )
    accept: Optional[str] = Field(default=None, description="Accept header")
    user_agent: Optional[str] = Field(default=None, description="User-Agent header")
    content_length: Optional[str] = Field(
        default=None, description="Content-Length header"
    )
    cache_control: Optional[str] = Field(
        default=None, description="Cache-Control header"
    )
    x_request_id: Optional[str] = Field(
        default=None, description="X-Request-ID header for tracing"
    )
    x_correlation_id: Optional[str] = Field(
        default=None, description="X-Correlation-ID header for request correlation"
    )
    custom_headers: dict[str, str] = Field(
        default_factory=dict,
        description="Additional custom headers not covered by standard fields",
    )

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary format suitable for HTTP libraries."""
        headers_dict = {}

        # Add standard headers if present
        if self.content_type:
            headers_dict["Content-Type"] = self.content_type
        if self.authorization:
            headers_dict["Authorization"] = self.authorization
        if self.accept:
            headers_dict["Accept"] = self.accept
        if self.user_agent:
            headers_dict["User-Agent"] = self.user_agent
        if self.content_length:
            headers_dict["Content-Length"] = self.content_length
        if self.cache_control:
            headers_dict["Cache-Control"] = self.cache_control
        if self.x_request_id:
            headers_dict["X-Request-ID"] = self.x_request_id
        if self.x_correlation_id:
            headers_dict["X-Correlation-ID"] = self.x_correlation_id

        # Add custom headers
        headers_dict.update(self.custom_headers)

        return headers_dict

    @classmethod
    def from_dict(cls, headers_dict: dict[str, str]) -> "ModelHttpHeaders":
        """Create from dictionary format."""
        known_headers = {
            "content-type": "content_type",
            "authorization": "authorization",
            "accept": "accept",
            "user-agent": "user_agent",
            "content-length": "content_length",
            "cache-control": "cache_control",
            "x-request-id": "x_request_id",
            "x-correlation-id": "x_correlation_id",
        }

        model_data = {}
        custom_headers = {}

        for header_name, header_value in headers_dict.items():
            normalized_name = header_name.lower()
            if normalized_name in known_headers:
                model_data[known_headers[normalized_name]] = header_value
            else:
                custom_headers[header_name] = header_value

        model_data["custom_headers"] = custom_headers
        return cls(**model_data)

    class Config:
        json_schema_extra = {
            "example": {
                "content_type": "application/json",
                "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                "accept": "application/json",
                "user_agent": "ONEX-Canary-Tool/1.0.0",
                "x_request_id": "req_123456789",
                "x_correlation_id": "corr_987654321",
                "custom_headers": {"X-API-Version": "v1", "X-Client-Version": "1.0.0"},
            }
        }
