#!/usr/bin/env python3
"""
ONEX Canary Impure Tool Input State Model

Model for input state of the Tier 3 Impure/Side Effect canary tool, demonstrating
perfect side effect management patterns with comprehensive validation and security.
"""

from typing import Optional

from omnibase.core.models.model_semver import ModelSemVer
from omnibase.models.canonical import ModelAction
from pydantic import BaseModel, Field

from .model_http_headers import ModelHttpHeaders
from .model_output_field import ModelOutputField
from .model_request_body import ModelRequestBody


class ModelCanaryImpureInputState(BaseModel):
    """Input state for Tier 3 Impure/Side Effect canary tool operations."""

    # Core ONEX fields
    action: ModelAction = Field(description="Impure action to perform")
    version: ModelSemVer = Field(description="Input state version")

    # Side effect operation fields
    side_effect_operation: str = Field(
        description="Side effect operation to perform",
        pattern="^(file_write|file_read|file_delete|http_request|database_query|external_api_call|email_send|audit_log)$",
    )
    target_path: Optional[str] = Field(
        default=None, description="Target file path for file operations"
    )
    content_data: Optional[str] = Field(
        default=None, description="Content data for write operations"
    )
    external_url: Optional[str] = Field(
        default=None, description="External URL for HTTP requests"
    )
    request_method: str = Field(
        default="GET",
        description="HTTP request method",
        pattern="^(GET|POST|PUT|DELETE|PATCH)$",
    )
    request_headers: Optional[ModelHttpHeaders] = Field(
        default=None, description="HTTP request headers"
    )
    request_body: Optional[ModelRequestBody] = Field(
        default=None, description="HTTP request body"
    )
    audit_message: Optional[str] = Field(
        default=None, description="Audit message for audit log operations"
    )
    sandbox_mode: bool = Field(
        default=True, description="Enable sandbox mode to limit side effects"
    )

    # Output configuration
    output_field: Optional[ModelOutputField] = Field(
        default=None, description="Dynamic output field for side effect results"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "action": {
                    "action_name": "perform_file_operation",
                    "action_type": "side_effect",
                    "category": "operation",
                    "display_name": "Write File",
                    "description": "Write content to file with comprehensive auditing",
                    "is_destructive": True,
                    "requires_confirmation": False,
                    "estimated_duration_ms": 100,
                    "required_parameters": [
                        "side_effect_operation",
                        "target_path",
                        "content_data",
                    ],
                    "optional_parameters": ["sandbox_mode"],
                    "tags": ["file", "write", "side_effect"],
                    "security_requirements": ["sandbox_mode"],
                },
                "version": {"major": 1, "minor": 0, "patch": 0},
                "side_effect_operation": "file_write",
                "target_path": "/tmp/canary_output.txt",
                "content_data": "Hello from canary impure tool",
                "sandbox_mode": True,
            }
        }
